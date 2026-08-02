"""Windows source handle that permits reads while denying write/delete sharing."""

from __future__ import annotations

import ctypes
import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

_GENERIC_READ = 0x80000000
_FILE_READ_ATTRIBUTES = 0x00000080
_FILE_SHARE_READ = 0x00000001
_OPEN_EXISTING = 3
_OPEN_REPARSE_POINT = 0x00200000
_FILE_TYPE_DISK = 1
_FILE_ID_INFO = 0x12
_FILE_ATTRIBUTE_TAG_INFO = 9
_FILE_BEGIN = 0
_INVALID_HANDLE = ctypes.c_void_p(-1).value


class _FileId128(ctypes.Structure):
    _fields_ = [("identifier", ctypes.c_ubyte * 16)]


class _FileIdInfo(ctypes.Structure):
    _fields_ = [
        ("volume_serial_number", ctypes.c_uint64),
        ("file_id", _FileId128),
    ]


class _AttributeTagInfo(ctypes.Structure):
    _fields_ = [
        ("file_attributes", ctypes.c_uint32),
        ("reparse_tag", ctypes.c_uint32),
    ]


@dataclass(frozen=True, slots=True, repr=False)
class SourceHandleObservationV1:
    identity_fingerprint: str
    normalized_path: str
    filesystem_name: str
    file_attributes: int


class SourceHandle:
    """One exact disk handle; the share mask is read-only."""

    def __init__(self, path: Path) -> None:
        if sys.platform != "win32":
            raise ValueError("database_windows_required")
        self._path = path
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        _configure(self._kernel)
        self._handle = self._open()

    def observe(self) -> SourceHandleObservationV1:
        if self._kernel.GetFileType(self._handle) != _FILE_TYPE_DISK:
            raise ValueError("database_source_handle_invalid")
        identity = _FileIdInfo()
        attributes = _AttributeTagInfo()
        for info_class, target in (
            (_FILE_ID_INFO, identity),
            (_FILE_ATTRIBUTE_TAG_INFO, attributes),
        ):
            if not self._kernel.GetFileInformationByHandleEx(
                self._handle,
                info_class,
                ctypes.byref(target),
                ctypes.sizeof(target),
            ):
                raise ValueError("database_source_handle_invalid")
        filesystem = ctypes.create_unicode_buffer(261)
        if not self._kernel.GetVolumeInformationByHandleW(
            self._handle, None, 0, None, None, None, filesystem, 261
        ):
            raise ValueError("database_source_handle_invalid")
        native = identity.volume_serial_number.to_bytes(8, "little")
        native += bytes(identity.file_id.identifier)
        return SourceHandleObservationV1(
            hashlib.sha256(native + b"file").hexdigest(),
            self._final_path(),
            filesystem.value.upper(),
            attributes.file_attributes,
        )

    def read_all(self, *, limit: int) -> bytes:
        size = self._size(limit)
        self._reset()
        result = bytearray()
        while len(result) < size:
            length = min(64 * 1024, size - len(result))
            result.extend(self._read(length))
        if len(result) != size:
            raise ValueError("database_source_handle_invalid")
        return bytes(result)

    def hash_all(self, *, limit: int) -> tuple[int, str]:
        payload = self.read_all(limit=limit)
        return len(payload), hashlib.sha256(payload).hexdigest()

    def close(self) -> None:
        if self._handle is not None:
            if not self._kernel.CloseHandle(self._handle):
                raise ValueError("database_source_handle_close_failed")
            self._handle = None

    def _open(self):
        handle = self._kernel.CreateFileW(
            str(self._path),
            _GENERIC_READ | _FILE_READ_ATTRIBUTES,
            _FILE_SHARE_READ,
            None,
            _OPEN_EXISTING,
            _OPEN_REPARSE_POINT,
            None,
        )
        if handle is None or handle == _INVALID_HANDLE:
            raise ValueError("database_source_handle_open_failed")
        return handle

    def _size(self, limit: int) -> int:
        size = ctypes.c_int64()
        if (
            type(limit) is not int
            or limit < 1
            or not self._kernel.GetFileSizeEx(self._handle, ctypes.byref(size))
            or not 0 <= size.value <= limit
        ):
            raise ValueError("database_source_handle_invalid")
        return size.value

    def _reset(self) -> None:
        position = ctypes.c_int64()
        if not self._kernel.SetFilePointerEx(
            self._handle, 0, ctypes.byref(position), _FILE_BEGIN
        ):
            raise ValueError("database_source_handle_invalid")

    def _read(self, length: int) -> bytes:
        buffer = ctypes.create_string_buffer(length)
        count = ctypes.c_uint32()
        if not self._kernel.ReadFile(
            self._handle, buffer, length, ctypes.byref(count), None
        ) or not 0 < count.value <= length:
            raise ValueError("database_source_handle_invalid")
        return buffer.raw[: count.value]

    def _final_path(self) -> str:
        buffer = ctypes.create_unicode_buffer(32_768)
        length = self._kernel.GetFinalPathNameByHandleW(
            self._handle, buffer, len(buffer), 0
        )
        if not 0 < length < len(buffer):
            raise ValueError("database_source_handle_invalid")
        return buffer.value


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
    kernel.GetFileType.argtypes = (ctypes.c_void_p,)
    kernel.GetFileType.restype = ctypes.c_uint32
    kernel.GetFileInformationByHandleEx.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    kernel.GetFileInformationByHandleEx.restype = ctypes.c_int
    _configure_reading(kernel)
    _configure_identity(kernel)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int


def _configure_reading(kernel: object) -> None:
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
    kernel.ReadFile.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    )
    kernel.ReadFile.restype = ctypes.c_int


def _configure_identity(kernel: object) -> None:
    kernel.GetFinalPathNameByHandleW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    )
    kernel.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
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
