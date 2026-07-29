"""Bound direct kernel32 and ntdll functions used by Issue #55."""

from __future__ import annotations

import ctypes


def load_kernel32():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
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
    _bind_path_functions(kernel)
    return kernel


def load_ntdll(io_status_type):
    library = ctypes.WinDLL("ntdll")
    library.NtSetInformationFile.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(io_status_type),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_int,
    )
    library.NtSetInformationFile.restype = ctypes.c_long
    library.RtlNtStatusToDosError.argtypes = (ctypes.c_long,)
    library.RtlNtStatusToDosError.restype = ctypes.c_uint32
    return library


def load_ntdll_for_directory(io_status_type, object_attributes_type):
    library = ctypes.WinDLL("ntdll")
    library.NtCreateFile.argtypes = (
        ctypes.POINTER(ctypes.c_void_p),
        ctypes.c_uint32,
        ctypes.POINTER(object_attributes_type),
        ctypes.POINTER(io_status_type),
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    library.NtCreateFile.restype = ctypes.c_long
    library.RtlNtStatusToDosError.argtypes = (ctypes.c_long,)
    library.RtlNtStatusToDosError.restype = ctypes.c_uint32
    return library


def _bind_path_functions(kernel) -> None:
    kernel.GetFinalPathNameByHandleW.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_wchar),
        ctypes.c_uint32,
        ctypes.c_uint32,
    )
    kernel.GetFinalPathNameByHandleW.restype = ctypes.c_uint32
    kernel.GetVolumeInformationByHandleW.restype = ctypes.c_int
    kernel.GetDriveTypeW.argtypes = (ctypes.c_wchar_p,)
    kernel.GetDriveTypeW.restype = ctypes.c_uint32
    kernel.GetFileType.argtypes = (ctypes.c_void_p,)
    kernel.GetFileType.restype = ctypes.c_uint32
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
