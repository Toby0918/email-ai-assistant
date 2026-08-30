"""Fixed Windows storage adapter for same-parent no-clobber evidence rollover."""

from __future__ import annotations

import ctypes
import hashlib
import os
from pathlib import Path

from backend.r2_solo_maintainer_closure._canonical import fingerprint
from backend.r2_solo_maintainer_closure.contracts import (
    SoloMaintainerAttestationReceiptV1, SoloMaintainerClosureManifestV1)
from backend.r2_solo_maintainer_closure.storage import (
    _FILES, _Overlapped, _TARGET, _WAIT_TIMEOUT, _api, _close_handles,
    _dacl_bytes, _git_common_dir, _identity, _prepare_windows_terminal,
    _publication_conflict_names, _read_locked_acl, _release_file_guards,
    _request_oplock, _require_exact, _safe_directory, _settle_oplocks, _wait,
    _windows_identity, _windows_names, _windows_open, _windows_streams)
from .contracts import ClosureEvidenceRolloverError, RolloverErrorCode
from .repository import (
    ClosureEvidenceObservationV1, create_evidence_observation as _create_observation,
    historical_target_name as _target_name,
    require_closure_cross_binding as _require_cross_binding)

_LOCKED_DACL = "D:P(A;;0x001200a9;;;WD)"
_OWNER_DELETE_DACL = "D:P(A;;0x001200a9;;;WD)(A;;SD;;;OW)"

class FixedClosureEvidenceStorage:
    """Observe and retain only the fixed active closure in its Git common directory."""

    def collect(self) -> ClosureEvidenceObservationV1:
        try:
            if os.name != "nt":
                raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
            common = _git_common_dir()
            source = common / _TARGET
            payloads = tuple((source / name).read_bytes() for name in _FILES)
            _require_exact(source, payloads)
            manifest = SoloMaintainerClosureManifestV1.from_json(payloads[0])
            receipt = SoloMaintainerAttestationReceiptV1.from_json(payloads[1])
            _require_cross_binding(manifest, receipt)
            target_name = _target_name(manifest.final_commit_oid,
                                       manifest.manifest_fingerprint)
            _require_target_absent(common, target_name)
            identity, parent_identity, parent_dacl = _observe_identity(
                common, source, payloads)
            return _create_observation(
                manifest=payloads[0], receipt=payloads[1],
                historical_commit_oid=manifest.final_commit_oid,
                historical_tree_oid=manifest.final_tree_oid,
                manifest_fingerprint=manifest.manifest_fingerprint,
                receipt_fingerprint=receipt.receipt_fingerprint,
                evidence_identity_fingerprint=identity,
                parent_identity_fingerprint=parent_identity,
                parent_dacl_sha256=parent_dacl,
                historical_target_name=target_name, source=source)
        except ClosureEvidenceRolloverError:
            raise
        except Exception:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED) from None

    def commit(self, observation: ClosureEvidenceObservationV1, before_commit) -> None:
        if (type(observation) is not ClosureEvidenceObservationV1
                or observation.source is None or not callable(before_commit)):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        try:
            source = observation.source
            target = source.parent / observation.historical_target_name
            before_identity = _identity(os.lstat(source))
            _guarded_rollover(
                source, target, before_identity,
                (observation.manifest, observation.receipt),
                observation.parent_identity_fingerprint,
                observation.parent_dacl_sha256, before_commit)
            if os.path.lexists(source):
                raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
            _require_exact(target, (observation.manifest, observation.receipt))
            after, parent_identity, parent_dacl = _observe_identity(
                target.parent, target, (observation.manifest, observation.receipt))
            if (after != observation.evidence_identity_fingerprint
                    or parent_identity != observation.parent_identity_fingerprint
                    or parent_dacl != observation.parent_dacl_sha256):
                raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        except ClosureEvidenceRolloverError:
            raise
        except Exception:
            raise ClosureEvidenceRolloverError(
                RolloverErrorCode.PUBLICATION_REJECTED) from None
def _require_target_absent(common: Path, target_name: str) -> None:
    names = tuple(item.name.casefold() for item in common.iterdir())
    if target_name.casefold() in names or os.path.lexists(common / target_name):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
def _guarded_rollover(
    source, target, identity, payloads, parent_identity, parent_dacl, before_commit
) -> None:
    if (os.name != "nt" or source.parent != target.parent
            or os.path.lexists(target) or _identity(os.lstat(source)) != identity):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    rename, pointer, size, close = _prepare_windows_terminal(target)
    guards = []
    try:
        _open_rollover_guards(source, target, payloads, identity, parent_identity,
                              parent_dacl, guards, close)
        expected_acl = tuple(_read_locked_acl(item[0], False) for item in guards)
        _require_rollover_guards(guards, payloads, expected_acl, pending=True)
        _settle_oplocks(guards[:2])
        _require_exact(source, payloads)
        _require_rollover_guards(guards, payloads, expected_acl, pending=False)
        _require_source_guard(guards[-1], expected_acl[-1], pending=True)
        before_commit()
        _require_exact(source, payloads)
        _require_rollover_guards(guards, payloads, expected_acl, pending=False)
        _release_file_guards(guards, close)
        _require_exact(source, payloads)
        _require_source_guard(guards[-1], expected_acl[-1], pending=True)
        _open_rollover_parent(source, target, guards, close)
        _require_source_guard(guards[-1], expected_acl[-1], pending=True)
        _require_parent_guard(guards[0], parent_identity, parent_dacl,
                              source.name, target.name)
        if rename(guards[-1][0], 22, pointer, size) != 1:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    finally:
        _close_handles(guards, close)
def _open_rollover_guards(
    source, target, payloads, identity, parent_identity, parent_dacl, guards, close
) -> None:
    for name, payload in zip(_FILES, payloads, strict=True):
        handle = _windows_open(source / name, 0x80120080, 0x5, 0x40200000)
        guards.append((handle, None, None, None, None, (0, 0, 0)))
        observed = _identity(os.lstat(source / name))
        guards[-1] = (handle, *_request_oplock(handle, 7, close), observed)
        if _windows_streams(handle) != (("::$DATA", len(payload)),):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    guards.append(_open_source_guard(source, target, identity, parent_identity,
                                     parent_dacl, close))
def _open_source_guard(
    source, target, identity, parent_identity, parent_dacl, close
):
    namespace_guards, control, rename_handle, escalated = [], None, None, False
    try:
        _open_rollover_parent(source, target, namespace_guards, close)
        _require_parent_guard(namespace_guards[0], parent_identity, parent_dacl,
                              source.name, target.name)
        control = _windows_open(source, 0x00060080, 0x7, 0x42200000)
        original = _fixed_dacl(control, _LOCKED_DACL, apply=False)
        if (_windows_streams(control) != ()
                or _windows_identity(control) != identity[:2]
                or _read_locked_acl(control, False) != original):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        escalated = True
        _fixed_dacl(control, _OWNER_DELETE_DACL, apply=True)
        rename_handle = _windows_open(source, 0x00030080, 0x5, 0x42200000)
        _fixed_dacl(control, _LOCKED_DACL, apply=True)
        escalated = False
        if (_windows_streams(rename_handle) != ()
                or _windows_identity(rename_handle) != identity[:2]
                or _read_locked_acl(rename_handle, False) != original):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        _require_parent_guard(namespace_guards[0], parent_identity, parent_dacl,
                              source.name, target.name)
        guard = (rename_handle, *_request_oplock(rename_handle, 1, close), identity)
        rename_handle = None
        return guard
    finally:
        try:
            if escalated and control is not None:
                _fixed_dacl(control, _LOCKED_DACL, apply=True)
        finally:
            for handle in (rename_handle, control):
                if handle is not None:
                    close(handle)
            _close_handles(namespace_guards, close)
def _fixed_dacl(handle, sddl: str, *, apply: bool) -> bytes:
    convert = _api("ConvertStringSecurityDescriptorToSecurityDescriptorW", (
        ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
        ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int, "advapi32")
    descriptor, length = ctypes.c_void_p(), ctypes.c_uint32()
    try:
        if convert(sddl, 1, ctypes.byref(descriptor), ctypes.byref(length)) != 1:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        expected = _dacl_bytes(descriptor, False)
        if apply:
            secure = _api("SetKernelObjectSecurity", (
                ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p),
                ctypes.c_int, "advapi32")
            if (secure(handle, 0x80000004, descriptor) != 1
                    or _read_locked_acl(handle, False) != expected):
                raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        return expected
    finally:
        if descriptor.value:
            _api("LocalFree", (ctypes.c_void_p,), ctypes.c_void_p)(descriptor)
def _require_rollover_guards(guards, payloads, expected_acl, pending: bool) -> None:
    if (_windows_streams(guards[-1][0]) != ()
            or _windows_identity(guards[-1][0]) != guards[-1][5][:2]
            or tuple(_read_locked_acl(item[0], False) for item in guards) != expected_acl):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    for guard, payload in zip(guards[:-1], payloads, strict=True):
        if (_windows_streams(guard[0]) != (("::$DATA", len(payload)),)
            or _windows_identity(guard[0]) != guard[5][:2]
                or _read_handle(guard[0], len(payload), overlapped=True) != payload):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    if pending and any(_wait(item[1], 0) != _WAIT_TIMEOUT for item in guards[:-1]):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
def _require_source_guard(guard, expected_acl: bytes, *, pending: bool) -> None:
    if (pending and _wait(guard[1], 0) != _WAIT_TIMEOUT
            or _windows_streams(guard[0]) != ()
            or _windows_identity(guard[0]) != guard[5][:2]
            or _read_locked_acl(guard[0], False) != expected_acl):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
def _open_rollover_parent(source, target, guards, close) -> None:
    identity = _identity(os.lstat(source.parent))
    handle = _windows_open(source.parent, 0x00020081, 0x7, 0x42200000)
    guards.insert(0, (handle, None, None, None, None, identity))
    guards[0] = (handle, *_request_oplock(handle, 1, close), identity)
    _require_parent_names(handle, source.name, target.name)
def _require_parent_guard(
    guard, expected_identity, expected_dacl, source_name, target_name
) -> None:
    if (_wait(guard[1], 0) != _WAIT_TIMEOUT
            or _windows_streams(guard[0]) != ()
            or _handle_identity_fingerprint(guard[0]) != expected_identity
            or hashlib.sha256(_read_locked_acl(guard[0], False)).hexdigest()
            != expected_dacl):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    _require_parent_names(guard[0], source_name, target_name)
def _require_parent_names(handle, source_name: str, target_name: str) -> None:
    names = _windows_names(handle)
    folded = tuple(name.casefold() for name in names)
    if (folded.count(source_name.casefold()) != 1
            or target_name.casefold() in folded
            or _publication_conflict_names(names, source_name)):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
def _observe_identity(common: Path, directory: Path, payloads: tuple[bytes, bytes]):
    _safe_directory(common); _safe_directory(directory)
    close, handles = _api("CloseHandle", (ctypes.c_void_p,)), []
    try:
        handles.extend((_windows_open(common, 0x00020080, 0x7, 0x02200000),
                        _windows_open(directory, 0x00020080, 0x7, 0x02200000)))
        handles.extend(_windows_open(directory / name, 0x80020080, 0x5, 0x00200000)
                       for name in _FILES)
        stats = (os.lstat(common), os.lstat(directory)) + tuple(
            os.lstat(directory / name) for name in _FILES)
        actual = tuple(_read_handle(handle, len(payload)) for handle, payload in zip(
            handles[2:], payloads, strict=True))
        streams = tuple(_windows_streams(handle) for handle in handles)
        acls = tuple(_read_locked_acl(handle, False) for handle in handles)
        if (actual != payloads or streams[:2] != ((), ())
                or streams[2:] != tuple((("::$DATA", len(item)),) for item in payloads)):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
        body = {"stat_identities": [list(_identity(item)) + [item.st_nlink, item.st_size]
                                    for item in stats],
                "windows_identities": [list(_windows_identity(item)) for item in handles],
                "streams": [list(map(list, item)) for item in streams],
                "dacl_sha256": [hashlib.sha256(item).hexdigest() for item in acls],
                "payload_sha256": [hashlib.sha256(item).hexdigest() for item in actual]}
        return (fingerprint("r2-closure-evidence-identity-v1", body),
                _handle_identity_fingerprint(handles[0]),
                hashlib.sha256(acls[0]).hexdigest())
    finally:
        _close_handles([(item, None, None, None, None, (0, 0, 0))
                        for item in handles], close)
def _handle_identity_fingerprint(handle) -> str:
    return fingerprint("r2-closure-evidence-parent-identity-v1",
                       list(_windows_identity(handle)))
def _read_handle(handle, expected_size: int, *, overlapped: bool = False) -> bytes:
    size = ctypes.c_int64(); get_size = _api(
        "GetFileSizeEx", (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)))
    read = _api("ReadFile", (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
                             ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p))
    if get_size(handle, ctypes.byref(size)) != 1 or size.value != expected_size:
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    if overlapped: return _read_overlapped(handle, expected_size, read)
    buffer, count = ctypes.create_string_buffer(expected_size), ctypes.c_uint32()
    if (read(handle, buffer, expected_size, ctypes.byref(count), None) != 1
            or count.value != expected_size):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
    return buffer.raw[:count.value]


def _read_overlapped(handle, size: int, read) -> bytes:
    close = _api("CloseHandle", (ctypes.c_void_p,)); event = _api(
        "CreateEventW", (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p))(
            None, 1, 0, None)
    buffer, operation = ctypes.create_string_buffer(size), _Overlapped(); operation.event = event
    try:
        ctypes.set_last_error(0); outcome = read(
            handle, buffer, size, None, ctypes.byref(operation))
        if (outcome != 1 and ctypes.get_last_error() != 997
                or outcome != 1 and _wait(event, 1_000) != 0):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        count = ctypes.c_uint32(); result = _api(
            "GetOverlappedResult", (ctypes.c_void_p, ctypes.POINTER(_Overlapped),
                                    ctypes.POINTER(ctypes.c_uint32), ctypes.c_int))
        if (result(handle, ctypes.byref(operation), ctypes.byref(count), 0) != 1
                or count.value != size):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.PUBLICATION_REJECTED)
        return buffer.raw[:count.value]
    finally: close(event)
