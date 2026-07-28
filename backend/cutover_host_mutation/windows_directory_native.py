"""Atomic handle-relative create-only directory operation."""

from __future__ import annotations

import ctypes

from .windows_handles import (
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WRITE_DAC,
    _NativeWindowsFailure,
)
from .windows_native_bindings import load_ntdll_for_directory


_FILE_LIST_DIRECTORY = 0x00000001
_SYNCHRONIZE = 0x00100000
_FILE_SHARE_READ = 0x00000001
_FILE_SHARE_WRITE = 0x00000002
_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
_FILE_CREATE = 2
_FILE_DIRECTORY_FILE = 0x00000001
_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
_FILE_OPEN_REPARSE_POINT = 0x00200000
_OBJ_CASE_INSENSITIVE = 0x00000040


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


def create_directory_relative(
    *,
    parent_handle: int,
    target_name: str,
    security_descriptor: ctypes.c_void_p | None = None,
    guarded: bool,
) -> int:
    _validate_name(target_name)
    name_buffer = ctypes.create_unicode_buffer(target_name)
    unicode_name = _unicode_string(name_buffer, target_name)
    attributes = _object_attributes(
        root_directory=parent_handle,
        name=unicode_name,
        security_descriptor=security_descriptor,
    )
    return _create(
        attributes=attributes,
        guarded=guarded,
    )


def _unicode_string(buffer, value: str) -> _UnicodeString:
    byte_length = len(value.encode("utf-16-le"))
    return _UnicodeString(
        length=byte_length,
        maximum_length=byte_length + ctypes.sizeof(ctypes.c_wchar),
        buffer=ctypes.cast(buffer, ctypes.c_void_p),
    )


def _object_attributes(
    *,
    root_directory: int,
    name: _UnicodeString,
    security_descriptor: ctypes.c_void_p | None,
) -> _ObjectAttributes:
    return _ObjectAttributes(
        length=ctypes.sizeof(_ObjectAttributes),
        root_directory=root_directory,
        object_name=ctypes.pointer(name),
        attributes=_OBJ_CASE_INSENSITIVE,
        security_descriptor=security_descriptor,
        security_quality_of_service=None,
    )


def _create(*, attributes: _ObjectAttributes, guarded: bool) -> int:
    library = load_ntdll_for_directory(_IoStatusBlock, _ObjectAttributes)
    handle = ctypes.c_void_p()
    io_status = _IoStatusBlock()
    access = FILE_READ_ATTRIBUTES | READ_CONTROL | _SYNCHRONIZE
    if guarded:
        access |= WRITE_DAC | _FILE_LIST_DIRECTORY
    status = library.NtCreateFile(
        ctypes.byref(handle),
        access,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        _FILE_ATTRIBUTE_DIRECTORY,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
        _FILE_CREATE,
        (
            _FILE_DIRECTORY_FILE
            | _FILE_SYNCHRONOUS_IO_NONALERT
            | _FILE_OPEN_REPARSE_POINT
        ),
        None,
        0,
    )
    if status != 0 or not handle.value:
        raise _NativeWindowsFailure(
            library.RtlNtStatusToDosError(status)
        )
    return int(handle.value)


def _validate_name(value: object) -> None:
    if (
        type(value) is not str
        or not value
        or value in {".", ".."}
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise _NativeWindowsFailure()
