"""Current-user Windows DPAPI wrapper with lazy native loading."""

from __future__ import annotations

import ctypes
import os
from dataclasses import dataclass, field
from typing import Callable, Protocol

from .errors import VaultError
from .models import SecretBuffer


CRYPTPROTECT_UI_FORBIDDEN = 0x1
CRYPTPROTECT_LOCAL_MACHINE = 0x4


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


@dataclass(frozen=True)
class NativeAllocation:
    success: bool
    handle: object = field(repr=False)
    size: int


class NativeDpapiApi(Protocol):
    def protect(self, data: bytearray, flags: int) -> NativeAllocation: ...
    def unprotect(self, data: bytearray, flags: int) -> NativeAllocation: ...
    def read(self, allocation: NativeAllocation) -> bytes: ...
    def wipe(self, allocation: NativeAllocation) -> None: ...
    def free(self, allocation: NativeAllocation) -> None: ...


class DpapiBackend(Protocol):
    def protect(self, data: bytearray, flags: int) -> SecretBuffer: ...
    def unprotect(self, data: bytearray, flags: int) -> SecretBuffer: ...


class _CtypesDpapiApi:
    def __init__(self) -> None:
        if os.name != "nt":
            raise VaultError("unsupported_platform")
        try:
            win_dll = getattr(ctypes, "WinDLL")
            self._crypt32 = win_dll("crypt32", use_last_error=True)
            self._kernel32 = win_dll("kernel32", use_last_error=True)
            self._configure_signatures()
        except VaultError:
            raise
        except (AttributeError, OSError):
            raise VaultError("unsupported_platform") from None

    def _configure_signatures(self) -> None:
        blob_pointer = ctypes.POINTER(DATA_BLOB)
        self._crypt32.CryptProtectData.argtypes = [
            blob_pointer,
            ctypes.c_wchar_p,
            blob_pointer,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            blob_pointer,
        ]
        self._crypt32.CryptProtectData.restype = ctypes.c_int
        self._crypt32.CryptUnprotectData.argtypes = [
            blob_pointer,
            ctypes.POINTER(ctypes.c_wchar_p),
            blob_pointer,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_uint32,
            blob_pointer,
        ]
        self._crypt32.CryptUnprotectData.restype = ctypes.c_int
        self._kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        self._kernel32.LocalFree.restype = ctypes.c_void_p

    @staticmethod
    def _input_blob(data: bytearray) -> tuple[DATA_BLOB, object]:
        buffer_type = ctypes.c_ubyte * len(data)
        buffer = buffer_type.from_buffer(data)
        return DATA_BLOB(len(data), buffer), buffer

    def _call(self, operation: str, data: bytearray, flags: int) -> NativeAllocation:
        input_blob, keepalive = self._input_blob(data)
        output_blob = DATA_BLOB()
        if operation == "protect":
            success = self._crypt32.CryptProtectData(
                ctypes.byref(input_blob), None, None, None, None, flags,
                ctypes.byref(output_blob),
            )
        else:
            success = self._crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None,
                None, None, flags, ctypes.byref(output_blob),
            )
        _ = keepalive
        address = ctypes.cast(output_blob.pbData, ctypes.c_void_p).value or 0
        return NativeAllocation(bool(success), address, int(output_blob.cbData))

    def protect(self, data: bytearray, flags: int) -> NativeAllocation:
        return self._call("protect", data, flags)

    def unprotect(self, data: bytearray, flags: int) -> NativeAllocation:
        return self._call("unprotect", data, flags)

    def read(self, allocation: NativeAllocation) -> bytes:
        if not allocation.handle or allocation.size < 0:
            raise VaultError("dpapi_unprotect_failed")
        return ctypes.string_at(allocation.handle, allocation.size)

    def wipe(self, allocation: NativeAllocation) -> None:
        if allocation.handle and allocation.size:
            ctypes.memset(allocation.handle, 0, allocation.size)

    def free(self, allocation: NativeAllocation) -> None:
        if allocation.handle:
            result = self._kernel32.LocalFree(ctypes.c_void_p(allocation.handle))
            if result:
                raise VaultError("dpapi_cleanup_failed")


class _WindowsDpapiBackend:
    def __init__(
        self,
        *,
        api_loader: Callable[[], NativeDpapiApi] = _CtypesDpapiApi,
    ) -> None:
        self._api_loader = api_loader

    def _transform(self, operation: str, data: bytearray, flags: int) -> SecretBuffer:
        error_code = f"dpapi_{operation}_failed"
        try:
            api = self._api_loader()
            allocation = getattr(api, operation)(data, flags)
        except VaultError:
            raise
        except Exception:
            raise VaultError(error_code) from None
        result: SecretBuffer | None = None
        failed = not allocation.success
        try:
            if not failed:
                result = SecretBuffer(api.read(allocation))
        except Exception:
            failed = True
        cleanup_failed = _cleanup_allocation(api, allocation)
        if cleanup_failed:
            if result is not None:
                result.wipe()
            raise VaultError("dpapi_cleanup_failed") from None
        if failed or result is None:
            raise VaultError(error_code) from None
        return result

    def protect(self, data: bytearray, flags: int) -> SecretBuffer:
        return self._transform("protect", data, flags)

    def unprotect(self, data: bytearray, flags: int) -> SecretBuffer:
        return self._transform("unprotect", data, flags)


def _cleanup_allocation(api: NativeDpapiApi, allocation: NativeAllocation) -> bool:
    failed = False
    try:
        api.wipe(allocation)
    except Exception:
        failed = True
    try:
        api.free(allocation)
    except Exception:
        failed = True
    return failed


class DpapiProtector:
    def __init__(self, *, backend: DpapiBackend | None = None) -> None:
        self._backend = _WindowsDpapiBackend() if backend is None else backend

    def protect(self, data: bytes | bytearray) -> bytes:
        local = SecretBuffer(data)
        protected: SecretBuffer | None = None
        try:
            protected = self._backend.protect(local, CRYPTPROTECT_UI_FORBIDDEN)
            return bytes(protected)
        except VaultError:
            raise
        except Exception:
            raise VaultError("dpapi_protect_failed") from None
        finally:
            local.wipe()
            if protected is not None:
                protected.wipe()

    def unprotect(self, data: bytes | bytearray) -> SecretBuffer:
        local = SecretBuffer(data)
        try:
            return self._backend.unprotect(local, CRYPTPROTECT_UI_FORBIDDEN)
        except VaultError:
            raise
        except Exception:
            raise VaultError("dpapi_unprotect_failed") from None
        finally:
            local.wipe()

    def __repr__(self) -> str:
        return "DpapiProtector(<redacted>)"
