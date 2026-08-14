"""Fixed two-file create-only publication in the Git common directory."""
from __future__ import annotations
import ctypes
import os
from pathlib import Path
import stat
from ._canonical import is_fingerprint
from .contracts import ClosureErrorCode, SoloMaintainerClosureError
from .repository import ROOT
_TARGET = "r2-solo-maintainer-closure-v1"
_FILES = ("solo-maintainer-closure-manifest-v1.json", "solo-maintainer-attestation-receipt-v1.json")
_INVALID_HANDLE, _PENDING, _WAIT_TIMEOUT = ctypes.c_void_p(-1).value, 997, 258; _FILE_STREAM_INFO, _FILE_ID_INFO, _ERROR_HANDLE_EOF = 7, 18, 38
_FILE_ID_BOTH_DIR, _FILE_ID_BOTH_DIR_RESTART, _NO_MORE_FILES = 10, 11, 18
class CreateOnlyClosureStorage:
    def publish(self, manifest: bytes, receipt: bytes, fingerprint: str, before_commit) -> None:
        if (os.name != "nt" or type(manifest) is not bytes or not manifest or type(receipt) is not bytes
                or not receipt or not is_fingerprint(fingerprint) or not callable(before_commit)):
            raise SoloMaintainerClosureError(ClosureErrorCode.PUBLICATION_REJECTED)
        common = _git_common_dir()
        target = common / _TARGET
        stage = common / f".{_TARGET}.stage-{fingerprint}"
        if _publication_conflict(common):
            raise SoloMaintainerClosureError(ClosureErrorCode.ALREADY_EXISTS)
        try:
            parent_identity = _identity(os.lstat(common))
            stage.mkdir(mode=0o700)
            stage_identity = _identity(os.lstat(stage))
            for name, payload in zip(_FILES, (manifest, receipt), strict=True):
                _write_exclusive(stage / name, payload)
            _require_exact(stage, (manifest, receipt))
            if (_identity(os.lstat(common)) != parent_identity
                    or _identity(os.lstat(stage)) != stage_identity
                    or os.path.lexists(target)):
                raise SoloMaintainerClosureError()
            _commit_no_replace(stage, target, stage_identity, (manifest, receipt), before_commit)
        except SoloMaintainerClosureError: raise
        except Exception: raise SoloMaintainerClosureError(ClosureErrorCode.PUBLICATION_REJECTED) from None
def read_closure_artifacts() -> tuple[bytes, bytes]:
    directory = _git_common_dir() / _TARGET
    try:
        payloads = tuple((directory / name).read_bytes() for name in _FILES)
        _require_exact(directory, payloads)
        return payloads
    except Exception:
        raise SoloMaintainerClosureError(ClosureErrorCode.PUBLICATION_REJECTED) from None
def _git_common_dir() -> Path:
    marker = ROOT / ".git"
    if marker.is_dir():
        return _safe_directory(marker)
    try:
        text = marker.read_text(encoding="utf-8")
        if not text.startswith("gitdir: ") or not text.endswith("\n") or "\n" in text[:-1]: raise SoloMaintainerClosureError()
        admin = Path(text[8:-1])
        if not admin.is_absolute(): admin = marker.parent / admin
        admin = _safe_directory(admin)
        common_text = (admin / "commondir").read_text(encoding="utf-8")
        if not common_text.endswith("\n") or "\n" in common_text[:-1]: raise SoloMaintainerClosureError()
        return _safe_directory(admin / common_text[:-1])
    except SoloMaintainerClosureError: raise
    except Exception: raise SoloMaintainerClosureError() from None
def _write_exclusive(path: Path, payload: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = None
    try:
        descriptor = os.open(path, flags, 0o600)
        offset = 0
        while offset < len(payload):
            written = os.write(descriptor, payload[offset:])
            if written < 1: raise SoloMaintainerClosureError()
            offset += written
        os.fsync(descriptor)
        metadata = os.fstat(descriptor)
    finally:
        if descriptor is not None: os.close(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1: raise SoloMaintainerClosureError()
def _commit_no_replace(source: Path, target: Path, identity: tuple[int, int, int], payloads: tuple[bytes, bytes], before_commit) -> None:
    if (source.parent != target.parent or os.path.lexists(target)
            or _identity(os.lstat(source)) != identity or os.name != "nt"):
        raise SoloMaintainerClosureError()
    _windows_guarded_commit(source, target, identity, payloads, before_commit)
def _publication_conflict(common: Path, allowed: str = "") -> bool: return _publication_conflict_names((item.name for item in common.iterdir()), allowed)
def _publication_conflict_names(names, allowed: str = "") -> bool: return any((name := item.casefold()) != allowed.casefold() and (name in (_TARGET, "r2-final-master-closure-v1") or name.startswith((f".{_TARGET}.stage-", ".r2-final-master-closure-v1.stage-"))) for item in names)
class _Overlapped(ctypes.Structure): _fields_ = (("internal", ctypes.c_void_p), ("internal_high", ctypes.c_void_p), ("offset", ctypes.c_uint32), ("offset_high", ctypes.c_uint32), ("event", ctypes.c_void_p))
class _OplockInput(ctypes.Structure): _fields_ = (("version", ctypes.c_ushort), ("length", ctypes.c_ushort), ("level", ctypes.c_uint32), ("flags", ctypes.c_uint32))
class _OplockOutput(ctypes.Structure): _fields_ = (("version", ctypes.c_ushort), ("length", ctypes.c_ushort), ("original", ctypes.c_uint32), ("new", ctypes.c_uint32), ("flags", ctypes.c_uint32), ("access", ctypes.c_uint32), ("share", ctypes.c_ushort), ("padding", ctypes.c_ushort))
def _windows_guarded_commit(source: Path, target: Path, identity: tuple[int, int, int], payloads: tuple[bytes, bytes], before_commit) -> None:
    rename, rename_pointer, rename_size, close = _prepare_windows_terminal(target)
    guards = []
    try:
        _open_windows_guards(source, payloads, identity, guards, close)
        expected_acl = _lock_read_execute_acl(tuple(item[0] for item in guards))
        _require_windows_guards(guards, payloads, True)
        _require_locked_acl(guards, expected_acl)
        _settle_oplocks(guards[:2])
        _require_exact(source, payloads)
        _require_windows_guards(guards, payloads, False)
        _require_locked_acl(guards, expected_acl)
        if _identity(os.lstat(source)) != identity: raise SoloMaintainerClosureError()
        _flush_windows_guards(guards)
        before_commit(*payloads)
        _release_file_guards(guards, close)
        _require_exact(source, payloads)
        _require_windows_guards(guards[-1:], (), False)
        _require_locked_acl(guards[-1:], expected_acl[-1:])
        parent_acl = _open_parent_guard(source, guards, close)
        _require_windows_guards(guards[-1:], (), False)
        _require_locked_acl(guards[-1:], expected_acl[-1:])
        _require_parent_guard(guards[0], parent_acl)
        if rename(guards[-1][0], 22, rename_pointer, rename_size) != 1:
            raise SoloMaintainerClosureError()
    finally:
        _close_handles(guards, close)
def _prepare_windows_terminal(target: Path):
    class _RenameInfo(ctypes.Structure): _fields_ = (("flags", ctypes.c_uint32), ("root", ctypes.c_void_p), ("length", ctypes.c_uint32), ("name", ctypes.c_wchar * (len(str(target)) + 1)))
    info = _RenameInfo(0x2, None, len(str(target)) * ctypes.sizeof(ctypes.c_wchar), str(target))
    rename = _api("SetFileInformationByHandle", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32))
    return rename, ctypes.byref(info), ctypes.sizeof(info), _api("CloseHandle", (ctypes.c_void_p,))
def _open_windows_guards(source: Path, payloads, identity, guards, close) -> None:
    for name, payload in zip(_FILES, payloads, strict=True):
        handle = _windows_open(source / name, 0xC0040000, 0x1, 0x40240000)
        guards.append((handle, None, None, None, None, (0, 0, 0)))
        identity_value = _identity(os.lstat(source / name))
        guards[-1] = (handle, *_request_oplock(handle, 7, close), identity_value)
        if _windows_streams(handle) != (("::$DATA", len(payload)),):
            raise SoloMaintainerClosureError()
    directory = _windows_open(source, 0xC0050000, 0x1, 0x02240000)
    guards.append((directory, None, None, None, None, identity))
    if _windows_streams(directory) != ():
        raise SoloMaintainerClosureError()
def _open_parent_guard(source: Path, guards, close) -> bytes:
    common, parent_identity = source.parent, _identity(os.lstat(source.parent))
    parent = _windows_open(common, 0x00020081, 0x7, 0x42200000)
    guards.insert(0, (parent, None, None, None, None, parent_identity))
    guards[0] = (parent, *_request_oplock(parent, 1, close), parent_identity)
    if _publication_conflict_names(_windows_names(parent), source.name):
        raise SoloMaintainerClosureError()
    return _read_locked_acl(parent, False)
def _windows_open(path: Path, access: int, share: int, flags: int):
    operation = _api("CreateFileW", (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p), ctypes.c_void_p)
    handle = operation(str(path), access, share, None, 3, flags, None)
    if handle in (None, _INVALID_HANDLE): raise SoloMaintainerClosureError()
    return handle
def _request_oplock(handle, level: int, close):
    event = _api("CreateEventW", (ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_wchar_p), ctypes.c_void_p)(None, 1, 0, None)
    source = _OplockInput(1, ctypes.sizeof(_OplockInput), level, 1)
    output, overlapped = _OplockOutput(), _Overlapped(); overlapped.event = event
    ctypes.set_last_error(0)
    operation = _api("DeviceIoControl", (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), ctypes.POINTER(_Overlapped)))
    result = operation(handle, 0x00090240, ctypes.byref(source), ctypes.sizeof(source), ctypes.byref(output), ctypes.sizeof(output), None, ctypes.byref(overlapped))
    if result != 0 or ctypes.get_last_error() != _PENDING or _wait(event, 0) != _WAIT_TIMEOUT:
        close(event); raise SoloMaintainerClosureError()
    return event, overlapped, source, output
def _lock_read_execute_acl(handles: tuple[object, ...]) -> tuple[bytes, ...]:
    convert = _api("ConvertStringSecurityDescriptorToSecurityDescriptorW",
        (ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
         ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int, "advapi32")
    descriptor, length = ctypes.c_void_p(), ctypes.c_uint32()
    try:
        if convert("D:P(A;;GRGX;;;WD)", 1, ctypes.byref(descriptor), ctypes.byref(length)) != 1: raise SoloMaintainerClosureError()
        secure = _api("SetKernelObjectSecurity", (ctypes.c_void_p, ctypes.c_uint32,
                      ctypes.c_void_p), ctypes.c_int, "advapi32")
        if any(secure(handle, 0x80000004, descriptor) != 1 for handle in handles):
            raise SoloMaintainerClosureError()
        return tuple(_read_locked_acl(handle) for handle in handles)
    finally:
        if descriptor.value:
            _api("LocalFree", (ctypes.c_void_p,), ctypes.c_void_p)(descriptor)
def _dacl_bytes(descriptor, protected: bool = True) -> bytes:
    present, dacl, defaulted, control, revision = ctypes.c_int(), ctypes.c_void_p(), ctypes.c_int(), ctypes.c_ushort(), ctypes.c_uint32()
    inspect_control = _api("GetSecurityDescriptorControl", (ctypes.c_void_p, ctypes.POINTER(ctypes.c_ushort), ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int, "advapi32")
    operation = _api("GetSecurityDescriptorDacl", (ctypes.c_void_p,
                     ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_void_p),
                     ctypes.POINTER(ctypes.c_int)), ctypes.c_int, "advapi32")
    if (inspect_control(descriptor, ctypes.byref(control), ctypes.byref(revision)) != 1
            or (protected and control.value & 0x1004 != 0x1004)
            or operation(descriptor, ctypes.byref(present), ctypes.byref(dacl), ctypes.byref(defaulted)) != 1
            or defaulted.value or not present.value or not dacl.value):
        raise SoloMaintainerClosureError()
    header = ctypes.string_at(dacl, 8); size = int.from_bytes(header[2:4], "little")
    result = ctypes.string_at(dacl, size); return result if protected else control.value.to_bytes(2, "little") + result
def _read_locked_acl(handle, protected: bool = True) -> bytes:
    operation = _api("GetKernelObjectSecurity", (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)), ctypes.c_int, "advapi32")
    security = 0x80000004 if protected else 0x00000004
    needed = ctypes.c_uint32()
    operation(handle, security, None, 0, ctypes.byref(needed))
    buffer = ctypes.create_string_buffer(needed.value)
    if not needed.value or operation(handle, security, buffer, len(buffer), ctypes.byref(needed)) != 1: raise SoloMaintainerClosureError()
    return _dacl_bytes(buffer, protected)
def _require_locked_acl(guards, expected: tuple[bytes, ...]) -> None:
    if tuple(_read_locked_acl(guard[0]) for guard in guards) != expected: raise SoloMaintainerClosureError()
def _settle_oplocks(guards) -> None:
    cancel = _api("CancelIoEx", (ctypes.c_void_p, ctypes.POINTER(_Overlapped)))
    result = _api("GetOverlappedResult", (ctypes.c_void_p, ctypes.POINTER(_Overlapped), ctypes.POINTER(ctypes.c_uint32), ctypes.c_int))
    for handle, event, overlapped, _source, _output, _identity_value in guards:
        if cancel(handle, ctypes.byref(overlapped)) != 1 or _wait(event, 1_000) != 0:
            raise SoloMaintainerClosureError()
        transferred = ctypes.c_uint32()
        ctypes.set_last_error(0)
        if result(handle, ctypes.byref(overlapped), ctypes.byref(transferred), 0) != 0 or ctypes.get_last_error() != 995:
            raise SoloMaintainerClosureError()
def _flush_windows_guards(guards) -> None:
    if any(_api("FlushFileBuffers", (ctypes.c_void_p,))(item[0]) != 1 for item in guards): raise SoloMaintainerClosureError()
def _release_file_guards(guards, close) -> None:
    for index in (0, 1):
        handle, event, *tail = guards[index]
        if close(event) != 1 or close(handle) != 1: raise SoloMaintainerClosureError()
        guards[index] = (None, None, *tail)
def _close_handles(guards, close) -> None:
    for handle, event, _overlapped, _source, _output, _identity_value in guards:
        for value in (event, handle):
            if value is not None:
                try: close(value)
                except Exception: pass
def _require_windows_guards(guards, payloads, pending: bool) -> None:
    if (_windows_streams(guards[-1][0]) != ()
            or _windows_identity(guards[-1][0]) != guards[-1][5][:2]):
        raise SoloMaintainerClosureError()
    for guard, payload in zip(guards[:-1], payloads, strict=True):
        if (_windows_streams(guard[0]) != (("::$DATA", len(payload)),)
                or _windows_identity(guard[0]) != guard[5][:2]):
            raise SoloMaintainerClosureError()
    if pending and any(item[1] is None or _wait(item[1], 0) != _WAIT_TIMEOUT for item in guards[:-1]): raise SoloMaintainerClosureError()
def _require_parent_guard(guard, expected_acl: bytes) -> None:
    if (_wait(guard[1], 0) != _WAIT_TIMEOUT or _windows_streams(guard[0]) != ()
            or _windows_identity(guard[0]) != guard[5][:2]
            or _read_locked_acl(guard[0], False) != expected_acl
            or _wait(guard[1], 0) != _WAIT_TIMEOUT):
        raise SoloMaintainerClosureError()
def _windows_identity(handle):
    buffer = ctypes.create_string_buffer(24)
    operation = _api("GetFileInformationByHandleEx", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32))
    if operation(handle, _FILE_ID_INFO, buffer, len(buffer)) != 1:
        raise SoloMaintainerClosureError()
    return (int.from_bytes(buffer.raw[:8], "little"), int.from_bytes(buffer.raw[8:24], "little"))
def _windows_names(handle) -> tuple[str, ...]:
    buffer = ctypes.create_string_buffer(65_536); operation = _api("GetFileInformationByHandleEx", (ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32))
    result, information = [], _FILE_ID_BOTH_DIR_RESTART
    while True:
        ctypes.set_last_error(0); outcome = operation(handle, information, buffer, len(buffer))
        if outcome != 1:
            if ctypes.get_last_error() == _NO_MORE_FILES: return tuple(result)
            raise SoloMaintainerClosureError()
        information, offset = _FILE_ID_BOTH_DIR, 0
        while True:
            next_offset = int.from_bytes(buffer.raw[offset:offset + 4], "little")
            length = int.from_bytes(buffer.raw[offset + 60:offset + 64], "little"); end = offset + 104 + length
            if length % 2 or end > len(buffer): raise SoloMaintainerClosureError()
            result.append(buffer.raw[offset + 104:end].decode("utf-16-le"))
            if next_offset == 0: break
            if next_offset < 104 or offset + next_offset >= len(buffer): raise SoloMaintainerClosureError()
            offset += next_offset
def _windows_streams(handle):
    buffer = ctypes.create_string_buffer(65_536)
    operation = _api("GetFileInformationByHandleEx", (
        ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32))
    ctypes.set_last_error(0)
    if operation(handle, _FILE_STREAM_INFO, buffer, len(buffer)) != 1:
        if ctypes.get_last_error() == _ERROR_HANDLE_EOF:
            return ()
        raise SoloMaintainerClosureError()
    result, offset = [], 0
    while True:
        next_offset = int.from_bytes(buffer.raw[offset:offset + 4], "little")
        length = int.from_bytes(buffer.raw[offset + 4:offset + 8], "little")
        end = offset + 24 + length
        if length % 2 or end > len(buffer):
            raise SoloMaintainerClosureError()
        result.append((buffer.raw[offset + 24:end].decode("utf-16-le"),
                       int.from_bytes(buffer.raw[offset + 8:offset + 16], "little", signed=True)))
        if next_offset == 0:
            return tuple(result)
        if next_offset < 24 or offset + next_offset > len(buffer):
            raise SoloMaintainerClosureError()
        offset += next_offset
def _wait(handle, milliseconds: int) -> int: return _api("WaitForSingleObject", (ctypes.c_void_p, ctypes.c_uint32), ctypes.c_uint32)(handle, milliseconds)
def _api(name: str, arguments: tuple[object, ...], result=ctypes.c_int,
         library: str = "kernel32"):
    operation = getattr(ctypes.WinDLL(library, use_last_error=True), name)
    operation.argtypes, operation.restype = arguments, result; return operation
def _require_exact(directory: Path, payloads: tuple[bytes, bytes]) -> None:
    _safe_directory(directory)
    if tuple(sorted(item.name for item in directory.iterdir())) != tuple(sorted(_FILES)):
        raise SoloMaintainerClosureError()
    for name, payload in zip(_FILES, payloads, strict=True):
        metadata = os.lstat(directory / name)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or _is_reparse(metadata) or (directory / name).read_bytes() != payload):
            raise SoloMaintainerClosureError()
def _safe_directory(path: Path) -> Path:
    if not isinstance(path, Path) or not path.is_absolute():
        raise SoloMaintainerClosureError()
    resolved = path.resolve(strict=True)
    if os.path.normcase(os.path.abspath(path)) != os.path.normcase(str(resolved)):
        raise SoloMaintainerClosureError()
    metadata = os.lstat(resolved)
    if (not stat.S_ISDIR(metadata.st_mode) or _is_reparse(metadata) or resolved.is_symlink() or resolved.is_junction()):
        raise SoloMaintainerClosureError()
    return resolved
def _is_reparse(metadata: os.stat_result) -> bool: return bool(getattr(metadata, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0))
def _identity(metadata: os.stat_result) -> tuple[int, int, int]: return metadata.st_dev, metadata.st_ino, metadata.st_mode
