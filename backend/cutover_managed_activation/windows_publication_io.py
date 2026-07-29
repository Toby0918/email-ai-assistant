"""Handle-relative create-only I/O for synthetic Windows publication."""

from __future__ import annotations

import ctypes
import hashlib
import sys
from pathlib import Path

from .canonical import fail

_FILE_LIST_DIRECTORY = 0x00000001
_FILE_READ_ATTRIBUTES = 0x00000080
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_SYNCHRONIZE = 0x00100000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_ATTRIBUTE_NORMAL = 0x00000080
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_CREATE = 2
_FILE_DIRECTORY_FILE = 0x00000001
_FILE_NON_DIRECTORY_FILE = 0x00000040
_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
_FILE_OPEN_REPARSE_POINT = 0x00200000
_OBJ_CASE_INSENSITIVE = 0x00000040
_FILE_BEGIN = 0
_MAX_FILE_BYTES = 1024 * 1024 * 1024


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ushort),
        ("maximum_length", ctypes.c_ushort),
        ("buffer", ctypes.c_void_p),
    ]


class _ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ulong),
        ("root_directory", ctypes.c_void_p),
        ("object_name", ctypes.POINTER(_UnicodeString)),
        ("attributes", ctypes.c_ulong),
        ("security_descriptor", ctypes.c_void_p),
        ("security_quality_of_service", ctypes.c_void_p),
    ]


class _IoStatusBlock(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_void_p),
        ("information", ctypes.c_void_p),
    ]


class WindowsCreateOnlyApi:
    """Create one child relative to a held parent and use its exact handle."""

    def __init__(self) -> None:
        if sys.platform != "win32":
            fail("managed_activation_windows_required")
        self._ntdll = ctypes.WinDLL("ntdll")
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        _configure(self._ntdll, self._kernel)

    def create_directory(self, parent: int, name: str) -> int:
        return self._create(parent, name, directory=True)

    def create_file(self, parent: int, name: str) -> int:
        return self._create(parent, name, directory=False)

    def _create(self, parent: int, name: str, *, directory: bool) -> int:
        _validate_name(name)
        name_buffer = ctypes.create_unicode_buffer(name)
        unicode_name = _unicode_string(name_buffer, name)
        attributes = _object_attributes(parent, unicode_name)
        handle = ctypes.c_void_p()
        io_status = _IoStatusBlock()
        access = _FILE_READ_ATTRIBUTES | _SYNCHRONIZE
        access |= _FILE_LIST_DIRECTORY if directory else (
            _GENERIC_READ | _GENERIC_WRITE
        )
        options = _FILE_SYNCHRONOUS_IO_NONALERT | _FILE_OPEN_REPARSE_POINT
        options |= _FILE_DIRECTORY_FILE if directory else _FILE_NON_DIRECTORY_FILE
        share = _FILE_SHARE_READ
        if directory:
            share |= _FILE_SHARE_WRITE
        status = self._ntdll.NtCreateFile(
            ctypes.byref(handle),
            access,
            ctypes.byref(attributes),
            ctypes.byref(io_status),
            None,
            _FILE_ATTRIBUTE_DIRECTORY if directory else _FILE_ATTRIBUTE_NORMAL,
            share,
            _FILE_CREATE,
            options,
            None,
            0,
        )
        if status != 0 or not handle.value:
            fail("managed_activation_target_collision")
        return int(handle.value)

    def write_all(self, handle: int, payload: bytes) -> None:
        offset = 0
        while offset < len(payload):
            block = payload[offset : offset + 64 * 1024]
            written = ctypes.c_uint32()
            buffer = ctypes.create_string_buffer(block)
            if not self._kernel.WriteFile(
                handle, buffer, len(block), ctypes.byref(written), None
            ) or written.value != len(block):
                fail("managed_activation_target_write_failed")
            offset += written.value

    def copy_from_path(self, handle: int, source: Path) -> None:
        try:
            with source.open("rb") as input_file:
                while True:
                    block = input_file.read(64 * 1024)
                    if not block:
                        break
                    self.write_all(handle, block)
        except OSError:
            fail("managed_activation_source_read_failed")

    def flush(self, handle: int) -> None:
        if not self._kernel.FlushFileBuffers(handle):
            fail("managed_activation_target_flush_failed")

    def read_all(self, handle: int) -> bytes:
        size = ctypes.c_int64()
        if not self._kernel.GetFileSizeEx(handle, ctypes.byref(size)):
            fail("managed_activation_target_read_failed")
        if not 0 <= size.value <= _MAX_FILE_BYTES:
            fail("managed_activation_target_read_failed")
        position = ctypes.c_int64()
        if not self._kernel.SetFilePointerEx(
            handle, 0, ctypes.byref(position), _FILE_BEGIN
        ):
            fail("managed_activation_target_read_failed")
        result = bytearray()
        while len(result) < size.value:
            length = min(64 * 1024, size.value - len(result))
            buffer = ctypes.create_string_buffer(length)
            read = ctypes.c_uint32()
            if not self._kernel.ReadFile(
                handle, buffer, length, ctypes.byref(read), None
            ):
                fail("managed_activation_target_read_failed")
            if read.value == 0:
                break
            result.extend(buffer.raw[: read.value])
        if len(result) != size.value:
            fail("managed_activation_target_read_failed")
        return bytes(result)

    def hash_all(self, handle: int, *, limit: int) -> tuple[int, str]:
        size = ctypes.c_int64()
        if (
            type(limit) is not int
            or limit < 0
            or not self._kernel.GetFileSizeEx(handle, ctypes.byref(size))
            or not 0 <= size.value <= limit
        ):
            fail("managed_activation_target_read_failed")
        position = ctypes.c_int64()
        if not self._kernel.SetFilePointerEx(
            handle, 0, ctypes.byref(position), _FILE_BEGIN
        ):
            fail("managed_activation_target_read_failed")
        digest = hashlib.sha256()
        remaining = size.value
        while remaining:
            length = min(64 * 1024, remaining)
            buffer = ctypes.create_string_buffer(length)
            read = ctypes.c_uint32()
            if (
                not self._kernel.ReadFile(
                    handle, buffer, length, ctypes.byref(read), None
                )
                or read.value == 0
            ):
                fail("managed_activation_target_read_failed")
            digest.update(buffer.raw[: read.value])
            remaining -= read.value
        return size.value, digest.hexdigest()


def _unicode_string(buffer, value: str) -> _UnicodeString:
    length = len(value.encode("utf-16-le"))
    return _UnicodeString(
        length=length,
        maximum_length=length + ctypes.sizeof(ctypes.c_wchar),
        buffer=ctypes.cast(buffer, ctypes.c_void_p),
    )


def _object_attributes(parent: int, name: _UnicodeString) -> _ObjectAttributes:
    return _ObjectAttributes(
        length=ctypes.sizeof(_ObjectAttributes),
        root_directory=parent,
        object_name=ctypes.pointer(name),
        attributes=_OBJ_CASE_INSENSITIVE,
        security_descriptor=None,
        security_quality_of_service=None,
    )


def _validate_name(value: object) -> None:
    require_safe_component(value)


def require_safe_component(value: object) -> None:
    if (
        type(value) is not str
        or not value
        or value in {".", ".."}
        or any(character in '<>:"/\\|?*' for character in value)
        or any(ord(character) < 32 for character in value)
        or value[-1] in {" ", "."}
        or _reserved_component(value)
    ):
        fail("managed_activation_target_invalid")


def _reserved_component(value: str) -> bool:
    stem = value.split(".", 1)[0].upper()
    device_numbers = set("123456789") | {"¹", "²", "³"}
    return (
        stem in {"CON", "PRN", "AUX", "NUL"}
        or stem.startswith("COM") and stem[3:] in device_numbers
        or stem.startswith("LPT") and stem[3:] in device_numbers
    )


def _configure(ntdll, kernel) -> None:
    ntdll.NtCreateFile.argtypes = (
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_ulong,
        ctypes.POINTER(_ObjectAttributes),
        ctypes.POINTER(_IoStatusBlock),
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_ulong,
        ctypes.c_void_p,
        ctypes.c_ulong,
    )
    ntdll.NtCreateFile.restype = ctypes.c_long
    kernel.WriteFile.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.c_void_p,
    )
    kernel.WriteFile.restype = ctypes.c_int
    kernel.ReadFile.argtypes = kernel.WriteFile.argtypes
    kernel.ReadFile.restype = ctypes.c_int
    kernel.FlushFileBuffers.argtypes = (ctypes.c_void_p,)
    kernel.FlushFileBuffers.restype = ctypes.c_int
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
