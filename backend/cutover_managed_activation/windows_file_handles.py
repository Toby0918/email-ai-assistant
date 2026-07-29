"""Narrow Windows read handles with optional write/delete sharing denial."""
from __future__ import annotations

import ctypes
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from .canonical import fail
FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
_GENERIC_READ = 0x80000000
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_OPEN_REPARSE = 0x00200000
_BACKUP_SEMANTICS = 0x02000000
_FILE_TYPE_DISK = 0x0001
_FILE_ID_INFO_CLASS = 0x12
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_BEGIN = 0
_INVALID_HANDLE = ctypes.c_void_p(-1).value
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
@dataclass(frozen=True, slots=True, repr=False)
class WindowsFileIdentity:
    volume_serial_number: int
    file_id: bytes
    file_attributes: int
    reparse_tag: int
    normalized_path: str
    filesystem_name: str
    fixed_drive: bool

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
class WindowsReadHandleApi:
    """Only open/read identity/stability/close; no mutation operation."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            fail("managed_activation_windows_required")
        self._kernel = ctypes.WinDLL(
            "kernel32", use_last_error=True
        )
        _configure(self._kernel)

    def open_existing(self, path: Path, *, deny_write: bool) -> int:
        share = _FILE_SHARE_READ
        if not deny_write:
            share |= _FILE_SHARE_WRITE
        handle = self._kernel.CreateFileW(
            str(path),
            _GENERIC_READ | _FILE_READ_ATTRIBUTES,
            share,
            None,
            _OPEN_EXISTING,
            _OPEN_REPARSE | _BACKUP_SEMANTICS,
            None,
        )
        if handle is None or handle == _INVALID_HANDLE:
            fail("managed_activation_handle_open_failed")
        return handle

    def observe(self, handle: int) -> WindowsFileIdentity:
        if self._kernel.GetFileType(handle) != _FILE_TYPE_DISK:
            fail("managed_activation_handle_invalid")
        identity = _FileIdInfo()
        attributes = _FileAttributeTagInfo()
        if not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_ID_INFO_CLASS,
            ctypes.byref(identity),
            ctypes.sizeof(identity),
        ) or not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_ATTRIBUTE_TAG_INFO_CLASS,
            ctypes.byref(attributes),
            ctypes.sizeof(attributes),
        ):
            fail("managed_activation_handle_invalid")
        normalized = self._final_path(handle)
        filesystem = ctypes.create_unicode_buffer(261)
        if not self._kernel.GetVolumeInformationByHandleW(
            handle, None, 0, None, None, None, filesystem, 261
        ):
            fail("managed_activation_handle_invalid")
        fixed = (
            len(normalized) >= 7
            and normalized.startswith("\\\\?\\")
            and normalized[5:7] == ":\\"
            and self._kernel.GetDriveTypeW(normalized[4:7]) == 3
        )
        return WindowsFileIdentity(
            volume_serial_number=identity.volume_serial_number,
            file_id=bytes(identity.file_id.identifier),
            file_attributes=attributes.file_attributes,
            reparse_tag=(
                attributes.reparse_tag
                if attributes.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
                else 0
            ),
            normalized_path=normalized,
            filesystem_name=filesystem.value.upper(),
            fixed_drive=fixed,
        )

    def require_stable(
        self,
        handle: int,
        expected: WindowsFileIdentity,
        path: Path,
    ) -> None:
        current = self.observe(handle)
        if (
            current != expected
            or current.filesystem_name != "NTFS"
            or not current.fixed_drive
            or current.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
            or current.normalized_path.casefold()
            != _expected_path(path).casefold()
        ):
            fail("managed_activation_handle_changed")

    def close(self, handle: int) -> None:
        if not self._kernel.CloseHandle(handle):
            fail("managed_activation_handle_close_failed")

    def read_bounded(self, handle: int, *, limit: int) -> bytes:
        size = self.require_size_bounded(handle, limit=limit)
        position = ctypes.c_int64()
        if not self._kernel.SetFilePointerEx(
            handle, 0, ctypes.byref(position), _FILE_BEGIN
        ):
            fail("managed_activation_handle_invalid")
        result = bytearray()
        while len(result) < size:
            length = min(64 * 1024, size - len(result))
            result.extend(self.read_block(handle, length=length))
        if len(result) != size:
            fail("managed_activation_handle_invalid")
        return bytes(result)

    def require_size_bounded(self, handle: int, *, limit: int) -> int:
        size = ctypes.c_int64()
        if (
            type(limit) is not int
            or limit < 0
            or not self._kernel.GetFileSizeEx(handle, ctypes.byref(size))
            or not 0 <= size.value <= limit
        ):
            fail("managed_activation_handle_invalid")
        return size.value

    def hash_bounded(self, handle: int, *, limit: int) -> tuple[int, str]:
        size = self.require_size_bounded(handle, limit=limit)
        self.reset(handle)
        digest = hashlib.sha256()
        remaining = size
        while remaining:
            block = self.read_block(
                handle, length=min(64 * 1024, remaining)
            )
            digest.update(block)
            remaining -= len(block)
        return size, digest.hexdigest()

    def reset(self, handle: int) -> None:
        position = ctypes.c_int64()
        if not self._kernel.SetFilePointerEx(
            handle, 0, ctypes.byref(position), _FILE_BEGIN
        ):
            fail("managed_activation_handle_invalid")

    def read_block(self, handle: int, *, length: int) -> bytes:
        if type(length) is not int or not 1 <= length <= 64 * 1024:
            fail("managed_activation_handle_invalid")
        buffer = ctypes.create_string_buffer(length)
        read = ctypes.c_uint32()
        if (
            not self._kernel.ReadFile(
                handle, buffer, length, ctypes.byref(read), None
            )
            or read.value == 0
            or read.value > length
        ):
            fail("managed_activation_handle_invalid")
        return buffer.raw[: read.value]

    def _final_path(self, handle: int) -> str:
        size = 512
        for _attempt in range(3):
            buffer = ctypes.create_unicode_buffer(size)
            result = self._kernel.GetFinalPathNameByHandleW(
                handle, buffer, size, 0
            )
            if result == 0 or result > 32_768:
                fail("managed_activation_handle_invalid")
            if result < size:
                return buffer.value
            size = result
        fail("managed_activation_handle_invalid")


def _expected_path(path: Path) -> str:
    resolved = str(path.resolve(strict=True))
    if resolved.startswith("\\\\"):
        return "\\\\?\\UNC\\" + resolved[2:]
    return "\\\\?\\" + resolved


def _configure(kernel: object) -> None:
    kernel.CreateFileW.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.GetFileInformationByHandleEx.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    kernel.GetFileInformationByHandleEx.restype = ctypes.c_int
    kernel.GetFinalPathNameByHandleW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    )
    kernel.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    kernel.GetFileType.argtypes = (ctypes.c_void_p,)
    kernel.GetFileType.restype = ctypes.c_uint32
    kernel.GetVolumeInformationByHandleW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_wchar_p,
        ctypes.c_uint32,
    )
    kernel.GetVolumeInformationByHandleW.restype = ctypes.c_int
    kernel.GetDriveTypeW.argtypes = (ctypes.c_wchar_p,)
    kernel.GetDriveTypeW.restype = ctypes.c_uint32
    _configure_read_api(kernel)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int


def _configure_read_api(kernel) -> None:
    kernel.ReadFile.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    )
    kernel.ReadFile.restype = ctypes.c_int
    kernel.GetFileSizeEx.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int64),
    )
    kernel.GetFileSizeEx.restype = ctypes.c_int
    kernel.SetFilePointerEx.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int64,
        ctypes.POINTER(ctypes.c_int64),
        ctypes.c_uint32,
    )
    kernel.SetFilePointerEx.restype = ctypes.c_int
