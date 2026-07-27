"""Narrow read-only ctypes bindings for Windows file observations."""

from __future__ import annotations

import ctypes
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

from .errors import RealHostPreflightError


FILE_ATTRIBUTE_DIRECTORY = 0x00000010
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
ERROR_FILE_NOT_FOUND = 2

_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FILE_TYPE_DISK = 0x0001
_FILE_TYPE_UNKNOWN = 0x0000
_DRIVE_FIXED = 3
_FILE_NAME_NORMALIZED_DOS = 0
_FILE_NAME_BUFFER_START = 512
_FILE_NAME_BUFFER_LIMIT = 32_768
_FILESYSTEM_NAME_BUFFER = 261
_FILE_STANDARD_INFO_CLASS = 1
_FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
_FILE_ID_INFO_CLASS = 0x12
_INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value


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


class _FileStandardInfo(ctypes.Structure):
    _fields_ = [
        ("allocation_size", ctypes.c_int64),
        ("end_of_file", ctypes.c_int64),
        ("number_of_links", ctypes.c_uint32),
        ("delete_pending", ctypes.c_ubyte),
        ("directory", ctypes.c_ubyte),
    ]


@dataclass(frozen=True, slots=True, repr=False)
class _NativeObservation:
    volume_serial_number: int
    file_id_128: bytes
    file_attributes: int
    reparse_tag: int
    normalized_path: str
    filesystem_name: str
    drive_type: str
    file_type: int
    number_of_links: int


class _WindowsApiFailure(Exception):
    """An internal native failure that never renders its numeric detail."""

    def __init__(self, *, is_file_not_found: bool = False) -> None:
        self.is_file_not_found = is_file_not_found
        super().__init__("windows_api_failed")

    def __repr__(self) -> str:
        return "_WindowsApiFailure()"


class _WindowsApi:
    """The exact read-only Windows API surface used by the observer."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            raise RealHostPreflightError("host_platform_unsupported")
        self._kernel = _load_kernel32()

    def open_existing(self, path: Path) -> int:
        handle = self._kernel.CreateFileW(
            str(path),
            0,
            _FILE_SHARE_READ | _FILE_SHARE_WRITE,
            None,
            _OPEN_EXISTING,
            _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if handle is None or handle == _INVALID_HANDLE_VALUE:
            _raise_last_error()
        return handle

    def observe(self, handle: int) -> _NativeObservation:
        file_type = self._file_type(handle)
        attributes = self._attribute_tag(handle)
        identity = self._file_id(handle)
        standard = self._standard_info(handle)
        normalized_path = self._final_path(handle)
        return _NativeObservation(
            volume_serial_number=identity.volume_serial_number,
            file_id_128=bytes(identity.file_id.identifier),
            file_attributes=attributes.file_attributes,
            reparse_tag=(
                attributes.reparse_tag
                if attributes.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
                else 0
            ),
            normalized_path=normalized_path,
            filesystem_name=self._filesystem_name(handle),
            drive_type=self._drive_type(normalized_path),
            file_type=file_type,
            number_of_links=standard.number_of_links,
        )

    def close(self, handle: int) -> None:
        if not self._kernel.CloseHandle(handle):
            _raise_last_error()

    def _file_type(self, handle: int) -> int:
        ctypes.set_last_error(0)
        file_type = self._kernel.GetFileType(handle)
        if file_type == _FILE_TYPE_UNKNOWN:
            _raise_last_error()
        if file_type != _FILE_TYPE_DISK:
            raise _WindowsApiFailure()
        return file_type

    def _attribute_tag(self, handle: int) -> _FileAttributeTagInfo:
        value = _FileAttributeTagInfo()
        if not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_ATTRIBUTE_TAG_INFO_CLASS,
            ctypes.byref(value),
            ctypes.sizeof(value),
        ):
            _raise_last_error()
        return value

    def _file_id(self, handle: int) -> _FileIdInfo:
        value = _FileIdInfo()
        if not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_ID_INFO_CLASS,
            ctypes.byref(value),
            ctypes.sizeof(value),
        ):
            _raise_last_error()
        return value

    def _standard_info(self, handle: int) -> _FileStandardInfo:
        value = _FileStandardInfo()
        if not self._kernel.GetFileInformationByHandleEx(
            handle,
            _FILE_STANDARD_INFO_CLASS,
            ctypes.byref(value),
            ctypes.sizeof(value),
        ):
            _raise_last_error()
        return value

    def _final_path(self, handle: int) -> str:
        size = _FILE_NAME_BUFFER_START
        for _attempt in range(3):
            buffer = ctypes.create_unicode_buffer(size)
            result = self._kernel.GetFinalPathNameByHandleW(
                handle,
                buffer,
                size,
                _FILE_NAME_NORMALIZED_DOS,
            )
            if result == 0:
                _raise_last_error()
            if result < size:
                return buffer.value
            if result > _FILE_NAME_BUFFER_LIMIT:
                raise _WindowsApiFailure()
            size = result
        raise _WindowsApiFailure()

    def _filesystem_name(self, handle: int) -> str:
        buffer = ctypes.create_unicode_buffer(_FILESYSTEM_NAME_BUFFER)
        if not self._kernel.GetVolumeInformationByHandleW(
            handle,
            None,
            0,
            None,
            None,
            None,
            buffer,
            _FILESYSTEM_NAME_BUFFER,
        ):
            _raise_last_error()
        return buffer.value.upper()

    def _drive_type(self, normalized_path: str) -> str:
        if (
            len(normalized_path) < 7
            or not normalized_path.startswith("\\\\?\\")
            or normalized_path[5:7] != ":\\"
        ):
            raise _WindowsApiFailure()
        drive_root = normalized_path[4:7]
        if self._kernel.GetDriveTypeW(drive_root) != _DRIVE_FIXED:
            raise _WindowsApiFailure()
        return "fixed"


def _raise_last_error() -> None:
    is_file_not_found = ctypes.get_last_error() == ERROR_FILE_NOT_FOUND
    raise _WindowsApiFailure(is_file_not_found=is_file_not_found) from None


def _volume_fingerprint(volume_serial_number: int) -> str:
    payload = volume_serial_number.to_bytes(8, "little", signed=False)
    return hashlib.sha256(payload).hexdigest()


def _text_fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _load_kernel32():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _bind_open_and_file_information(kernel)
    _bind_path_and_volume_information(kernel)
    _bind_type_and_close(kernel)
    return kernel


def _bind_open_and_file_information(kernel) -> None:
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


def _bind_path_and_volume_information(kernel) -> None:
    kernel.GetFinalPathNameByHandleW.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_uint32,
        ctypes.c_uint32,
    )
    kernel.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    kernel.GetVolumeInformationByHandleW.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_uint32,
    )
    kernel.GetVolumeInformationByHandleW.restype = ctypes.c_int


def _bind_type_and_close(kernel) -> None:
    kernel.GetDriveTypeW.argtypes = (ctypes.c_wchar_p,)
    kernel.GetDriveTypeW.restype = ctypes.c_uint32
    kernel.GetFileType.argtypes = (ctypes.c_void_p,)
    kernel.GetFileType.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
