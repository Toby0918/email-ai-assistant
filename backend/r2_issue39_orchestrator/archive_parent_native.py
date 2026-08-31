"""Native create-only directory primitive for the fixed archive hierarchy."""

from __future__ import annotations

import ctypes

from backend.cutover_host_mutation.windows_handles import (
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WRITE_DAC,
)


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
    _fields_ = [("status", ctypes.c_void_p), ("information", ctypes.c_void_p)]


def create_directory(parent, name, security_descriptor):
    if type(name) is not str or not name or any(item in name for item in "\\/:\x00"):
        raise ArchiveParentNativeFailure()
    ntdll = ctypes.WinDLL("ntdll")
    _configure_ntdll(ntdll)
    name_buffer = ctypes.create_unicode_buffer(name)
    encoded = name.encode("utf-16-le")
    unicode_name = _UnicodeString(
        len(encoded),
        len(encoded) + ctypes.sizeof(ctypes.c_wchar),
        ctypes.cast(name_buffer, ctypes.c_void_p),
    )
    attributes = _ObjectAttributes(
        ctypes.sizeof(_ObjectAttributes),
        parent,
        ctypes.pointer(unicode_name),
        _OBJ_CASE_INSENSITIVE,
        security_descriptor,
        None,
    )
    return _native_create(ntdll, attributes)


def _native_create(ntdll, attributes):
    handle = ctypes.c_void_p()
    status = _IoStatusBlock()
    desired = (
        _FILE_LIST_DIRECTORY
        | FILE_READ_ATTRIBUTES
        | READ_CONTROL
        | WRITE_DAC
        | _SYNCHRONIZE
    )
    result = ntdll.NtCreateFile(
        ctypes.byref(handle),
        desired,
        ctypes.byref(attributes),
        ctypes.byref(status),
        None,
        _FILE_ATTRIBUTE_DIRECTORY,
        _FILE_SHARE_READ | _FILE_SHARE_WRITE,
        _FILE_CREATE,
        _FILE_DIRECTORY_FILE
        | _FILE_SYNCHRONOUS_IO_NONALERT
        | _FILE_OPEN_REPARSE_POINT,
        None,
        0,
    )
    if result != 0 or not handle.value:
        raise ArchiveParentNativeFailure()
    return int(handle.value)


class SecurityDescriptor:
    def __init__(self, sddl):
        self._advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        self._kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.pointer = ctypes.c_void_p()
        length = ctypes.c_uint32()
        operation = (
            self._advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
        )
        operation.argtypes = (
            ctypes.c_wchar_p,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint32),
        )
        operation.restype = ctypes.c_int
        self._kernel.LocalFree.argtypes = (ctypes.c_void_p,)
        if not operation(sddl, 1, ctypes.byref(self.pointer), ctypes.byref(length)):
            raise ArchiveParentNativeFailure()

    def close(self):
        if self.pointer.value:
            self._kernel.LocalFree(self.pointer)
            self.pointer = ctypes.c_void_p()


def _configure_ntdll(ntdll):
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


class ArchiveParentNativeFailure(Exception):
    pass
