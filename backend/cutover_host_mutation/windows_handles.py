"""Narrow direct Windows handle and file-identity bindings."""
from __future__ import annotations
import ctypes
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from backend.real_host_preflight.windows_paths import expected_final_path

from .errors import CutoverHostMutationError
from .windows_native_bindings import load_kernel32, load_ntdll
READ_CONTROL = 0x00020000
WRITE_DAC = 0x00040000
DELETE_ACCESS = 0x00010000
FILE_READ_ATTRIBUTES = 0x00000080
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
FILE_SHARE_READ = 0x00000001
FILE_SHARE_WRITE = 0x00000002
FILE_SHARE_DELETE = 0x00000004

_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_TYPE_DISK = 0x0001
_FILE_TYPE_UNKNOWN = 0x0000
_DRIVE_FIXED = 3
_FILE_ID_INFO_CLASS = 0x12
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_RENAME_INFORMATION_CLASS = 10
_FILE_NAME_BUFFER_LIMIT = 32_768
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
ERROR_FILE_NOT_FOUND = 2
ERROR_PATH_NOT_FOUND = 3
ERROR_FILE_EXISTS = 80
ERROR_ALREADY_EXISTS = 183


class _FileId128(ctypes.Structure):
    _fields_ = [("identifier", ctypes.c_ubyte * 16)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [
        ("volume_serial_number", ctypes.c_uint64),
        ("file_id", _FileId128),
    ]


class _FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [
        ("file_attributes", ctypes.c_uint32),
        ("reparse_tag", ctypes.c_uint32),
    ]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_void_p),
        ("information", ctypes.c_void_p),
    ]


@dataclass(frozen=True, slots=True, repr=False)
class NativeObjectIdentity:
    volume_serial_number: int
    file_id: bytes
    file_attributes: int
    reparse_tag: int
    normalized_path: str
    filesystem_name: str
    drive_type: str

    @property
    def object_identity_fingerprint(self) -> str:
        kind = (
            b"directory"
            if self.file_attributes & FILE_ATTRIBUTE_DIRECTORY
            else b"file"
        )
        return hashlib.sha256(
            self.volume_serial_number.to_bytes(8, "little")
            + self.file_id
            + kind
        ).hexdigest()

    @property
    def volume_fingerprint(self) -> str:
        return hashlib.sha256(
            self.volume_serial_number.to_bytes(8, "little")
        ).hexdigest()


class WindowsHandleApi:
    """The exact kernel32 surface used by Issue #55."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            _fail("host_platform_unsupported")
        self._kernel = load_kernel32()
        self._ntdll = load_ntdll(_IoStatusBlock)

    def open_existing(
        self,
        path: Path,
        *,
        access: int,
        share_delete: bool = False,
    ) -> int:
        share = FILE_SHARE_READ | FILE_SHARE_WRITE
        if share_delete:
            share |= FILE_SHARE_DELETE
        handle = self._kernel.CreateFileW(
            str(path),
            access,
            share,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle is None or handle == _INVALID_HANDLE_VALUE:
            raise _NativeWindowsFailure(ctypes.get_last_error())
        return handle

    def rename_no_replace(
        self,
        source_handle: int,
        target_parent_handle: int,
        target_name: str,
    ) -> None:
        _validate_rename_target(target_name)
        buffer = _rename_buffer(target_parent_handle, target_name)
        io_status = _IoStatusBlock()
        status = self._ntdll.NtSetInformationFile(
            source_handle,
            ctypes.byref(io_status),
            buffer,
            len(buffer),
            _FILE_RENAME_INFORMATION_CLASS,
        )
        if status != 0:
            code = self._ntdll.RtlNtStatusToDosError(status)
            raise _NativeWindowsFailure(code)

    def observe(self, handle: int) -> NativeObjectIdentity:
        if self._file_type(handle) != _FILE_TYPE_DISK:
            raise _NativeWindowsFailure()
        identity = _FileIdInfo()
        attributes = _FileAttributeTagInfo()
        if not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_ID_INFO_CLASS,
            ctypes.byref(identity),
            ctypes.sizeof(identity),
        ):
            raise _NativeWindowsFailure()
        if not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_ATTRIBUTE_TAG_INFO_CLASS,
            ctypes.byref(attributes),
            ctypes.sizeof(attributes),
        ):
            raise _NativeWindowsFailure()
        normalized = self._final_path(handle)
        return NativeObjectIdentity(
            volume_serial_number=identity.volume_serial_number,
            file_id=bytes(identity.file_id.identifier),
            file_attributes=attributes.file_attributes,
            reparse_tag=(
                attributes.reparse_tag
                if attributes.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
                else 0
            ),
            normalized_path=normalized,
            filesystem_name=self._filesystem_name(handle),
            drive_type=self._drive_type(normalized),
        )

    def close(self, handle: int) -> None:
        if not self._kernel.CloseHandle(handle):
            raise _NativeWindowsFailure()

    def require_stable(
        self,
        handle: int,
        expected: NativeObjectIdentity,
        path: Path,
    ) -> None:
        current = self.observe(handle)
        if (
            current != expected
            or current.filesystem_name != "NTFS"
            or current.drive_type != "fixed"
            or current.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
            or current.normalized_path.casefold()
            != expected_final_path(path).casefold()
        ):
            _fail("filesystem_identity_changed")

    def _file_type(self, handle: int) -> int:
        ctypes.set_last_error(0)
        result = self._kernel.GetFileType(handle)
        if result == _FILE_TYPE_UNKNOWN:
            raise _NativeWindowsFailure()
        return result

    def _final_path(self, handle: int) -> str:
        size = 512
        for _attempt in range(3):
            buffer = ctypes.create_unicode_buffer(size)
            result = self._kernel.GetFinalPathNameByHandleW(
                handle, buffer, size, 0
            )
            if result == 0 or result > _FILE_NAME_BUFFER_LIMIT:
                raise _NativeWindowsFailure()
            if result < size:
                return buffer.value
            size = result
        raise _NativeWindowsFailure()

    def _filesystem_name(self, handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(261)
        if not self._kernel.GetVolumeInformationByHandleW(
            handle, None, 0, None, None, None, buffer, 261
        ):
            raise _NativeWindowsFailure()
        return buffer.value.upper()

    def _drive_type(self, normalized_path: str) -> str:
        if (
            len(normalized_path) < 7
            or not normalized_path.startswith("\\\\?\\")
            or normalized_path[5:7] != ":\\"
        ):
            raise _NativeWindowsFailure()
        if self._kernel.GetDriveTypeW(normalized_path[4:7]) != _DRIVE_FIXED:
            raise _NativeWindowsFailure()
        return "fixed"


class _NativeWindowsFailure(Exception):
    def __init__(self, code: int = 0) -> None:
        self.code = code
        super().__init__("windows_api_failed")

    def __repr__(self) -> str:
        return "_NativeWindowsFailure()"


class _FileRenameInfoHeader(ctypes.Structure):
    _fields_ = [
        ("replace_if_exists", ctypes.c_ubyte),
        ("root_directory", ctypes.c_void_p),
        ("file_name_length", ctypes.c_uint32),
    ]


def _validate_rename_target(target_name: object) -> None:
    if (
        type(target_name) is not str
        or not target_name
        or target_name in {".", ".."}
        or "\\" in target_name
        or "/" in target_name
        or "\x00" in target_name
    ):
        raise _NativeWindowsFailure()


def _rename_buffer(parent_handle: int, target_name: str):
    encoded = target_name.encode("utf-16-le")
    name_offset = _FileRenameInfoHeader.file_name_length.offset + 4
    size = max(ctypes.sizeof(_FileRenameInfoHeader), name_offset + len(encoded))
    buffer = ctypes.create_string_buffer(size)
    header = ctypes.cast(
        buffer,
        ctypes.POINTER(_FileRenameInfoHeader),
    ).contents
    header.replace_if_exists = 0
    header.root_directory = parent_handle
    header.file_name_length = len(encoded)
    ctypes.memmove(
        ctypes.addressof(buffer) + name_offset,
        encoded,
        len(encoded),
    )
    return buffer


def _fail(code: str) -> None:
    raise CutoverHostMutationError(code) from None
