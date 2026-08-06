"""Detached-signature verification and fixed atomic no-clobber installation."""
from __future__ import annotations
import ctypes, os, stat, sys
from dataclasses import dataclass; from pathlib import Path; from types import SimpleNamespace
from backend.r2_final_master_closure import (ClosureGate, FinalMasterBindingV1, R2GlobalGateCoordinatorV1, R2GlobalGateEvidenceV1, gate_evidence_registry)
from backend.r2_final_master_closure._canonical import canonical_json, is_fingerprint, strict_json_object
from backend.r2_production_binding import ApprovedCutoverBindingV2, require_reviewed_production_binding_v2
from backend.r2_production_composition import build_production_binding_candidate_v1
from .derivation import _rederive_external_evidence_v1; from .review_inputs import R2ExternalArtifactError
from .unsigned_package import R2UnsignedExternalArtifactPackageV1, _BINDING_FILENAME, _require_package_integrity_v1, _unsigned_body
_FINAL_DIRECTORY, _INVALID_HANDLE = "r2-final-master-closure-v1", ctypes.c_void_p(-1).value
_FILE_FLAG_OPEN_REQUIRING_OPLOCK, _FILE_FLAG_OPEN_REPARSE_POINT, _FSCTL_REQUEST_OPLOCK = 0x00040000, 0x00200000, 0x00090240
_OPLOCK_LEVEL_READ, _OPLOCK_LEVEL_READ_HANDLE, _OPLOCK_LEVEL_RWH = 1, 3, 7
_ERROR_IO_PENDING, _ERROR_HANDLE_EOF, _WAIT_TIMEOUT, _OPLOCK_IO_WAIT_MS = 997, 38, 258, 5_000; _FILE_STANDARD_INFO, _FILE_STREAM_INFO, _FILE_ID_BOTH_INFO, _FILE_ID_BOTH_RESTART_INFO, _FILE_ID_INFO = 1, 7, 10, 11, 18
class _FileIdValue(ctypes.Union): _fields_ = (("file_id", ctypes.c_uint64), ("extended", ctypes.c_ubyte * 16))
class _FileIdDescriptor(ctypes.Structure): _anonymous_ = ("value",); _fields_ = (("size", ctypes.c_uint32), ("kind", ctypes.c_int), ("value", _FileIdValue))
class _OplockInput(ctypes.Structure): _fields_ = (("version", ctypes.c_ushort), ("length", ctypes.c_ushort), ("level", ctypes.c_uint32), ("flags", ctypes.c_uint32))
class _OplockOutput(ctypes.Structure): _fields_ = (("version", ctypes.c_ushort), ("length", ctypes.c_ushort), ("original", ctypes.c_uint32), ("new", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("access", ctypes.c_uint32), ("share", ctypes.c_ushort), ("padding", ctypes.c_ushort))
class _Overlapped(ctypes.Structure): _fields_ = (("internal", ctypes.c_void_p), ("internal_high", ctypes.c_void_p), ("offset", ctypes.c_uint32), ("offset_high", ctypes.c_uint32), ("event", ctypes.c_void_p))
@dataclass(frozen=True, slots=True)
class R2ExternalArtifactInstallResultV1:
    status: str; artifact_count: int; signed_gate_count: int; signature_count: int; overwrite_count: int; deletion_count: int
def install_signed_external_artifacts_v1(*, unsigned_package, detached_signatures, confirmed_manifest_fingerprint):
    """Verify external signatures, then publish only to the fixed Git location."""
    try:
        binding, signed_files = _validate_signed_set(unsigned_package, detached_signatures, confirmed_manifest_fingerprint)
        if binding.binding_fingerprint != unsigned_package.final_master_binding_fingerprint: raise R2ExternalArtifactError()
        files = ((_BINDING_FILENAME, unsigned_package.reviewed_production_binding_json), *signed_files)
        fresh = unsigned_package.supporting_provenance_records[0].source_mapping
        _publish_validated_files_v1(_fixed_git_common_dir(), confirmed_manifest_fingerprint, files, fresh_master_source=fresh)
        return R2ExternalArtifactInstallResultV1("R2_EXTERNAL_ARTIFACTS_INSTALLED", 15, 14, 14, 0, 0)
    except R2ExternalArtifactError: raise
    except Exception: raise R2ExternalArtifactError() from None
def _validate_signed_set(package, signatures, confirmed):
    invalid = (type(package) is not R2UnsignedExternalArtifactPackageV1 or not is_fingerprint(confirmed)
        or confirmed != package.issuance_manifest_fingerprint or type(signatures) is not tuple
        or len(signatures) != len(ClosureGate) or any(type(item) is not bytes or len(item) != 64 for item in signatures))
    if invalid: raise R2ExternalArtifactError()
    _require_package_integrity_v1(package)
    final_master, binding = _binding_from_package(package)
    derived = _rederive_external_evidence_v1(package, final_master, binding)
    evidence, files = [], []
    for registration, artifact, signature, expected in zip(gate_evidence_registry(), package.unsigned_gate_artifacts, signatures, derived, strict=True):
        body = strict_json_object(artifact.unsigned_body_json)
        if artifact.unsigned_body_json != canonical_json(_unsigned_body(SimpleNamespace(binding=final_master), registration, expected)): raise R2ExternalArtifactError()
        signed = canonical_json({**body, "signature_hex": signature.hex()})
        evidence.append(R2GlobalGateEvidenceV1.from_signed_json(signed, binding=final_master))
        files.append((artifact.filename, signed))
    R2GlobalGateCoordinatorV1.create(binding=final_master, evidence=tuple(evidence))
    return binding, tuple(files)
def _binding_from_package(package):
    source = strict_json_object(package.reviewed_production_binding_json)
    final_master = FinalMasterBindingV1.create(**{name: source[name] for name in ("final_commit_oid", "final_tree_oid", "source_package_fingerprint", "runbook_fingerprint", "workflow_fingerprint")}); binding = ApprovedCutoverBindingV2.from_json(package.reviewed_production_binding_json, final_master_binding=final_master)
    expected = build_production_binding_candidate_v1(final_master_binding=final_master, verification_public_keys=dict(binding.verification_public_keys))
    if expected.to_canonical_json() != binding.to_canonical_json(): raise R2ExternalArtifactError()
    require_reviewed_production_binding_v2(final_master, binding)
    return final_master, binding
def _require_fresh_master_v1(source):
    if type(source) is not dict or canonical_json(_current_frozen_master_v1().to_mapping()) != canonical_json(source): raise R2ExternalArtifactError()
def _current_frozen_master_v1(): from scripts.prepare_r2_external_artifacts import _freeze_current_master_v1; return _freeze_current_master_v1()
def _fixed_git_common_dir():
    from scripts import verify_r2_final_master_closure as fixed
    if fixed.ROOT != Path(__file__).resolve().parents[2]: raise R2ExternalArtifactError()
    return _safe_directory(fixed._git_common_dir())
def _publish_validated_files_v1(common_dir, manifest_fingerprint, files, *, fresh_master_source=None):
    common = _safe_directory(common_dir)
    expected_names = (_BINDING_FILENAME, *(f"{index:02d}-{gate.value}.json" for index, gate in enumerate(ClosureGate, 1)))
    invalid = (not is_fingerprint(manifest_fingerprint) or type(files) is not tuple
        or tuple(name for name, _payload in files) != expected_names
        or any(type(payload) is not bytes or not payload for _name, payload in files))
    if invalid: raise R2ExternalArtifactError()
    if fresh_master_source is not None: _require_fresh_master_v1(fresh_master_source)
    target, stage = common / _FINAL_DIRECTORY, common / f".{_FINAL_DIRECTORY}.stage-{manifest_fingerprint}"
    if os.path.lexists(target) or os.path.lexists(stage): raise R2ExternalArtifactError()
    parent_identity = _identity(os.lstat(common))
    stage.mkdir(mode=0o700)
    stage_identity = _identity(os.lstat(stage))
    for name, payload in files:
        _write_exclusive(stage / name, payload)
    _fsync_directory(stage)
    changed = (_identity(os.lstat(common)) != parent_identity or _identity(os.lstat(stage)) != stage_identity
        or os.path.lexists(target) or tuple(sorted(item.name for item in stage.iterdir())) != tuple(sorted(expected_names)))
    if changed: raise R2ExternalArtifactError()
    _require_exact_files(stage, files)
    if os.name == "nt": _windows_commit_with_file_id_guards(stage, target, stage_identity, files, fresh_master_source); return
    if fresh_master_source is not None: _require_fresh_master_v1(fresh_master_source)
    _rename_no_replace(stage, target, stage_identity)
    if os.path.lexists(stage) or _identity(os.lstat(target)) != stage_identity: raise R2ExternalArtifactError()
    _require_exact_files(target, files)
    _fsync_directory(common)
def _write_exclusive(path, payload):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags, 0o600)
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written < 1: raise R2ExternalArtifactError()
            offset += written
        os.fsync(descriptor)
        opened = os.fstat(descriptor)
    except R2ExternalArtifactError: raise
    except Exception: raise R2ExternalArtifactError() from None
    finally: os.close(descriptor) if "descriptor" in locals() else None
    if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or path.read_bytes() != payload: raise R2ExternalArtifactError()
def _rename_no_replace(source, target, expected_identity, windows_handle=None):
    if source.parent != target.parent or os.path.lexists(target) or _identity(os.lstat(source)) != expected_identity: raise R2ExternalArtifactError()
    if os.name == "nt":
        _windows_rename_no_replace(source, target, expected_identity, windows_handle); return
    if windows_handle is not None: raise R2ExternalArtifactError()
    if sys.platform.startswith("linux"):
        library = ctypes.CDLL(None, use_errno=True)
        operation = getattr(library, "renameat2", None)
        if operation is None: raise R2ExternalArtifactError()
        operation.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint); operation.restype = ctypes.c_int
        if operation(-100, os.fsencode(source), -100, os.fsencode(target), 1) != 0: raise R2ExternalArtifactError()
        return
    raise R2ExternalArtifactError()
def _windows_rename_no_replace(source, target, expected_identity, handle=None):
    commit = _windows_api("SetFileInformationByHandle", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32))
    owned = handle is None
    if owned: handle = _windows_open(source, 0x10080, 0x3, 0x02200000)
    class _RenameInfo(ctypes.Structure):
        _fields_ = (("flags", ctypes.c_uint32), ("root", ctypes.c_void_p), ("length", ctypes.c_uint32), ("name", ctypes.c_wchar * (len(str(target)) + 1)))
    try:
        if _identity(os.lstat(source)) != expected_identity or _handle_file_id(handle) != expected_identity[:2]: raise R2ExternalArtifactError()
        info = _RenameInfo(0x2, None, len(str(target)) * ctypes.sizeof(ctypes.c_wchar), str(target))
        if commit(handle, 22, ctypes.byref(info), ctypes.sizeof(info)) != 1: raise R2ExternalArtifactError()
    finally:
        if owned: _close_windows_handle(handle)
def _windows_open(path, access, share, flags):
    create = _windows_api("CreateFileW", (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p), ctypes.c_void_p); handle = create(str(path), access, share, None, 3, flags, None)
    if handle in (None, _INVALID_HANDLE): raise R2ExternalArtifactError()
    return handle
def _close_windows_handle(handle): _windows_api("CloseHandle", (ctypes.c_void_p,))(handle)
def _windows_commit_with_file_id_guards(source, target, identity, files, fresh_source):
    guards = []
    try:
        guards.extend(_open_file_id_guards(source, files))
        if fresh_source is not None: _require_fresh_master_v1(fresh_source)
        _require_guarded_commit(files, guards)
        try: _rename_no_replace(source, target, identity, guards[-1][0])
        except Exception: pass
        committed = (not os.path.lexists(source) and os.path.lexists(target)
            and _identity(os.lstat(target)) == identity)
        if not committed: raise R2ExternalArtifactError()
        _require_guarded_files(target, files, guards, require_quiet=False)
    finally: _close_file_id_guards(guards)
def _open_file_id_guards(directory, files):
    guards = []
    if len(directory.drive) != 2 or directory.drive[1] != ":": raise R2ExternalArtifactError()
    volume = _windows_open(f"\\\\.\\{directory.drive}", 0, 0x7, 0)
    try:
        for name, payload in files:
            metadata = os.lstat(directory / name); expected = _identity(metadata)
            guards.append([_windows_open_by_id(volume, metadata.st_ino), None, name, expected, None, None, None, None, None])
            guards[-1][1], guards[-1][4], guards[-1][5], guards[-1][6], guards[-1][7], guards[-1][8] = _request_oplock(guards[-1][0], _OPLOCK_LEVEL_RWH)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or _identity(os.lstat(directory / name)) != expected or _handle_file_id(guards[-1][0], True) != expected[:2] or _guarded_streams(guards[-1][0]) != (("::$DATA", len(payload)),) or not _guarded_bytes_equal(guards[-1][0], payload): raise R2ExternalArtifactError()
        expected = _identity(os.lstat(directory)); guards.append([_windows_open(directory, 0x80050000, 0x3, 0x42240000), None, None, expected, None, None, None, None, None])
        guards[-1][1], guards[-1][4], guards[-1][5], guards[-1][6], guards[-1][7], guards[-1][8] = _request_oplock(guards[-1][0], _OPLOCK_LEVEL_READ)
        if _handle_file_id(guards[-1][0]) != expected[:2] or _identity(os.lstat(directory)) != expected: raise R2ExternalArtifactError()
        _lock_guard_acls(guards)
        _require_guarded_files(directory, files, guards, require_quiet=False)
        _require_guarded_commit(files, guards)
        return tuple(guards)
    except Exception: _close_file_id_guards(guards); raise R2ExternalArtifactError() from None
    finally: _close_windows_handle(volume)
def _windows_open_by_id(volume, file_id):
    if type(file_id) is not int or not 0 < file_id < 2**64: raise R2ExternalArtifactError()
    descriptor = _FileIdDescriptor(); descriptor.size, descriptor.kind, descriptor.file_id = ctypes.sizeof(descriptor), 0, file_id
    operation = _windows_api("OpenFileById", (ctypes.c_void_p, ctypes.POINTER(_FileIdDescriptor), ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32), ctypes.c_void_p)
    flags = 0x40000000 | _FILE_FLAG_OPEN_REQUIRING_OPLOCK | _FILE_FLAG_OPEN_REPARSE_POINT
    handle = operation(volume, ctypes.byref(descriptor), 0x80040000, 0x7, None, flags)
    if handle in (None, _INVALID_HANDLE): raise R2ExternalArtifactError()
    return handle
def _lock_guard_acls(guards):
    convert = _windows_api("ConvertStringSecurityDescriptorToSecurityDescriptorW", (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int, "advapi32"); descriptor, length = ctypes.c_void_p(), ctypes.c_uint32()
    try:
        if convert("D:P(A;;GRGX;;;WD)", 1, ctypes.byref(descriptor), ctypes.byref(length)) != 1: raise R2ExternalArtifactError()
        secure = _windows_api("SetKernelObjectSecurity", (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p), ctypes.c_int, "advapi32")
        if any(secure(guard[0], 0x80000004, descriptor) != 1 for guard in guards): raise R2ExternalArtifactError()
    finally: _windows_api("LocalFree", (ctypes.c_void_p,), ctypes.c_void_p)(descriptor) if descriptor.value is not None else None
def _request_oplock(handle, level):
    create = _windows_api("CreateEventW", (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p), ctypes.c_void_p); close = _windows_api("CloseHandle", (ctypes.c_void_p,))
    event, pending = create(None, 1, 0, None), False
    if event in (None, _INVALID_HANDLE): raise R2ExternalArtifactError()
    try:
        operation = _windows_api("DeviceIoControl", (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(_Overlapped))); wait = _windows_api("WaitForSingleObject", (ctypes.c_void_p, ctypes.c_uint32), ctypes.c_uint32)
        cancel = _windows_api("CancelIoEx", (ctypes.c_void_p, ctypes.POINTER(_Overlapped))); reap = _windows_api("GetOverlappedResult", (ctypes.c_void_p, ctypes.POINTER(_Overlapped), ctypes.POINTER(ctypes.c_uint32), ctypes.c_int))
        source = _OplockInput(1, ctypes.sizeof(_OplockInput), level, 1); output, overlapped = _OplockOutput(), _Overlapped(); overlapped.event = event
        ctypes.set_last_error(0)
        granted = operation(handle, _FSCTL_REQUEST_OPLOCK, ctypes.byref(source), ctypes.sizeof(source), ctypes.byref(output), ctypes.sizeof(output), None, ctypes.byref(overlapped))
        pending = granted == 0 and ctypes.get_last_error() == _ERROR_IO_PENDING
        if not pending or wait(event, 0) != _WAIT_TIMEOUT: raise R2ExternalArtifactError()
        return event, source, output, overlapped, cancel, reap
    except Exception:
        try: _cancel_overlapped(handle, overlapped, ctypes.c_uint32(), cancel, reap) if pending else None
        finally: close(event)
        raise R2ExternalArtifactError() from None
def _wait_for_handle(handle, milliseconds): return _windows_api("WaitForSingleObject", (ctypes.c_void_p, ctypes.c_uint32), ctypes.c_uint32)(handle, milliseconds)
def _guarded_directory_entries(handle):
    operation = _windows_api("GetFileInformationByHandleEx", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)); entries, information_class = [], _FILE_ID_BOTH_RESTART_INFO
    while True:
        buffer = ctypes.create_string_buffer(65_536); ctypes.set_last_error(0)
        if operation(handle, information_class, buffer, len(buffer)) != 1:
            if ctypes.get_last_error() == 18: return tuple(sorted(entries))
            raise R2ExternalArtifactError()
        offset = 0
        while True:
            next_offset, name_length = int.from_bytes(buffer.raw[offset:offset + 4], "little"), int.from_bytes(buffer.raw[offset + 60:offset + 64], "little")
            name = buffer.raw[offset + 104:offset + 104 + name_length].decode("utf-16-le"); entries += [(name, int.from_bytes(buffer.raw[offset + 96:offset + 104], "little"))] if name not in (".", "..") else []
            if next_offset == 0: break
            offset += next_offset
        information_class = _FILE_ID_BOTH_INFO
def _handle_file_id(handle, single_file=False):
    operation = _windows_api("GetFileInformationByHandleEx", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)); buffer = ctypes.create_string_buffer(24)
    if operation(handle, _FILE_ID_INFO, buffer, len(buffer)) != 1: raise R2ExternalArtifactError()
    if single_file:
        standard = ctypes.create_string_buffer(24)
        if operation(handle, _FILE_STANDARD_INFO, standard, len(standard)) != 1 or int.from_bytes(standard.raw[16:20], "little") != 1 or standard.raw[20] != 0 or standard.raw[21] != 0: raise R2ExternalArtifactError()
    return int.from_bytes(buffer.raw[:8], "little"), int.from_bytes(buffer.raw[8:24], "little")
def _guarded_streams(handle):
    operation = _windows_api("GetFileInformationByHandleEx", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)); buffer = ctypes.create_string_buffer(65_536); ctypes.set_last_error(0)
    if operation(handle, _FILE_STREAM_INFO, buffer, len(buffer)) != 1:
        if ctypes.get_last_error() != _ERROR_HANDLE_EOF: raise R2ExternalArtifactError()
        return ()
    streams, offset = [], 0
    while True:
        next_offset = int.from_bytes(buffer.raw[offset:offset + 4], "little"); name_length = int.from_bytes(buffer.raw[offset + 4:offset + 8], "little"); end = offset + 24 + name_length
        if offset + 24 > len(buffer) or name_length % 2 or end > len(buffer): raise R2ExternalArtifactError()
        streams.append((buffer.raw[offset + 24:end].decode("utf-16-le"), int.from_bytes(buffer.raw[offset + 8:offset + 16], "little", signed=True)))
        if next_offset == 0: return tuple(streams)
        if next_offset < 24 or offset + next_offset > len(buffer): raise R2ExternalArtifactError()
        offset += next_offset
def _guarded_bytes_equal(handle, expected):
    size = ctypes.c_int64(); query = _windows_api("GetFileSizeEx", (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)))
    if query(handle, ctypes.byref(size)) != 1 or size.value != len(expected) or len(expected) > 0xFFFFFFFF: return False
    event = _windows_api("CreateEventW", (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p), ctypes.c_void_p)(None, 1, 0, None)
    if event in (None, _INVALID_HANDLE): raise R2ExternalArtifactError()
    try:
        buffer, transferred, overlapped = ctypes.create_string_buffer(len(expected)), ctypes.c_uint32(), _Overlapped(); overlapped.event = event
        read = _windows_api("ReadFile", (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(_Overlapped)))
        result = _windows_api("GetOverlappedResult", (ctypes.c_void_p, ctypes.POINTER(_Overlapped), ctypes.POINTER(ctypes.c_uint32), ctypes.c_int))
        ctypes.set_last_error(0)
        completed = read(handle, buffer, len(expected), ctypes.byref(transferred), ctypes.byref(overlapped))
        pending = completed == 0 and ctypes.get_last_error() == _ERROR_IO_PENDING
        if completed == 0 and not pending: return False
        if pending and _wait_for_handle(event, _OPLOCK_IO_WAIT_MS) != 0: _cancel_overlapped(handle, overlapped, transferred); return False
        if result(handle, ctypes.byref(overlapped), ctypes.byref(transferred), 0) != 1: return False
        return transferred.value == len(expected) and buffer.raw == expected
    finally: _close_windows_handle(event)
def _cancel_overlapped(handle, overlapped, transferred, cancel=None, result=None):
    cancel = cancel or _windows_api("CancelIoEx", (ctypes.c_void_p, ctypes.POINTER(_Overlapped))); result = result or _windows_api("GetOverlappedResult", (ctypes.c_void_p, ctypes.POINTER(_Overlapped), ctypes.POINTER(ctypes.c_uint32), ctypes.c_int))
    try: cancel(handle, ctypes.byref(overlapped))
    finally: result(handle, ctypes.byref(overlapped), ctypes.byref(transferred), 1)
def _require_guarded_files(directory, files, guards, *, require_quiet=True):
    _safe_directory(directory)
    if len(guards) != len(files) + 1: raise R2ExternalArtifactError()
    children, parent = guards[:-1], guards[-1]
    if _guarded_streams(parent[0]) or _guarded_directory_entries(parent[0]) != tuple(sorted((guard[2], guard[3][1]) for guard in children)): raise R2ExternalArtifactError()
    if tuple(guard[2] for guard in children) != tuple(name for name, _payload in files): raise R2ExternalArtifactError()
    if parent[2] is not None or _handle_file_id(parent[0]) != parent[3][:2] or _identity(os.lstat(directory)) != parent[3]: raise R2ExternalArtifactError()
    for guard, (_name, payload) in zip(children, files, strict=True):
        if guard[0] is None or _handle_file_id(guard[0], True) != guard[3][:2] or _guarded_streams(guard[0]) != (("::$DATA", len(payload)),) or not _guarded_bytes_equal(guard[0], payload): raise R2ExternalArtifactError()
    if require_quiet and any(_wait_for_handle(guard[1], 0) != _WAIT_TIMEOUT for guard in guards): raise R2ExternalArtifactError()
def _require_guarded_commit(files, guards):
    children, parent = guards[:-1], guards[-1]
    if _handle_file_id(parent[0]) != parent[3][:2] or _guarded_streams(parent[0]) or _guarded_directory_entries(parent[0]) != tuple(sorted((guard[2], guard[3][1]) for guard in children)): raise R2ExternalArtifactError()
    if any(_handle_file_id(guard[0], True) != guard[3][:2] or _guarded_streams(guard[0]) != (("::$DATA", len(payload)),) or not _guarded_bytes_equal(guard[0], payload) for guard, (_name, payload) in zip(children, files, strict=True)): raise R2ExternalArtifactError()
    if any(guard[1] is None or _wait_for_handle(guard[1], 0) != _WAIT_TIMEOUT for guard in guards): raise R2ExternalArtifactError()
def _close_file_id_guards(guards):
    for guard in guards:
        if guard[0] is not None and guard[1] is not None and guard[6] is not None: _cancel_overlapped(guard[0], guard[6], ctypes.c_uint32(), guard[7], guard[8])
        if guard[0] is not None: _close_windows_handle(guard[0]); guard[0] = None
        if guard[1] is not None: _close_windows_handle(guard[1]); guard[1] = None
def _windows_api(name, arguments, result=ctypes.c_int, library="kernel32"): operation = getattr(ctypes.WinDLL(library, use_last_error=True), name); operation.argtypes, operation.restype = arguments, result; return operation
def _require_exact_files(directory, files):
    _safe_directory(directory)
    names = tuple(sorted(item.name for item in directory.iterdir()))
    if names != tuple(sorted(name for name, _payload in files)): raise R2ExternalArtifactError()
    for name, payload in files:
        path, metadata = directory / name, os.lstat(directory / name)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or path.read_bytes() != payload: raise R2ExternalArtifactError()
def _safe_directory(path):
    if not isinstance(path, Path) or not path.is_absolute(): raise R2ExternalArtifactError()
    resolved = path.resolve(strict=True)
    if os.path.normcase(os.path.abspath(path)) != os.path.normcase(str(resolved)): raise R2ExternalArtifactError()
    current = resolved
    while True:
        metadata = os.lstat(current)
        reparse = bool(getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
        if current.is_symlink() or current.is_junction() or reparse or not stat.S_ISDIR(metadata.st_mode): raise R2ExternalArtifactError()
        if current.parent == current: return resolved
        current = current.parent
def _fsync_directory(path):
    if os.name == "nt": return
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try: os.fsync(descriptor)
    finally: os.close(descriptor)
def _identity(metadata): return metadata.st_dev, metadata.st_ino, metadata.st_mode
