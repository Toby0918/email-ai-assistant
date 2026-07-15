"""Current-user Windows DPAPI key protector with lazy native loading."""

from __future__ import annotations

import ctypes
import os
from typing import Callable, Protocol

from .errors import PrivateKnowledgeError


_UI_FORBIDDEN = 0x1


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", ctypes.c_uint32),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class DpapiBackend(Protocol):
    def protect(self, value: bytearray) -> bytes: ...
    def unprotect(self, value: bytearray) -> bytes: ...


class _WindowsDpapiBackend:
    def _transform(self, operation: str, value: bytearray) -> bytes:
        if os.name != "nt":
            raise PrivateKnowledgeError("unsupported_platform")
        output = _DataBlob()
        kernel32: object | None = None
        try:
            crypt32, kernel32 = _load_libraries()
            input_blob, keepalive = _input_blob(value)
            function = (
                crypt32.CryptProtectData
                if operation == "protect" else crypt32.CryptUnprotectData
            )
            if operation == "protect":
                success = function(
                    ctypes.byref(input_blob), None, None, None, None,
                    _UI_FORBIDDEN, ctypes.byref(output),
                )
            else:
                success = function(
                    ctypes.byref(input_blob), None, None,
                    None, None, _UI_FORBIDDEN, ctypes.byref(output),
                )
            _ = keepalive
            if not success or not output.pbData or output.cbData <= 0:
                raise OSError
            result = ctypes.string_at(output.pbData, output.cbData)
            return result
        except PrivateKnowledgeError:
            raise
        except Exception:
            raise PrivateKnowledgeError(f"dpapi_{operation}_failed") from None
        finally:
            if output.pbData:
                cleanup_error = _release_output(output, kernel32)
                if cleanup_error is not None:
                    raise cleanup_error

    def protect(self, value: bytearray) -> bytes:
        return self._transform("protect", value)

    def unprotect(self, value: bytearray) -> bytes:
        return self._transform("unprotect", value)


class CurrentUserDpapiProtector:
    def __init__(
        self,
        *,
        backend_factory: Callable[[], DpapiBackend] = _WindowsDpapiBackend,
    ) -> None:
        self._backend_factory = backend_factory

    def protect(self, value: bytes) -> bytes:
        return self._apply("protect", value)

    def unprotect(self, value: bytes) -> bytes:
        return self._apply("unprotect", value)

    def _apply(self, operation: str, value: bytes) -> bytes:
        if type(value) is not bytes or not value:
            raise PrivateKnowledgeError(f"dpapi_{operation}_failed")
        local = bytearray(value)
        try:
            result = getattr(self._backend_factory(), operation)(local)
            if type(result) is not bytes or not result:
                raise ValueError
            return result
        except PrivateKnowledgeError:
            raise
        except Exception:
            raise PrivateKnowledgeError(f"dpapi_{operation}_failed") from None
        finally:
            for index in range(len(local)):
                local[index] = 0

    def __repr__(self) -> str:
        return "CurrentUserDpapiProtector(<redacted>)"


def _load_libraries() -> tuple[object, object]:
    try:
        loader = getattr(ctypes, "WinDLL")
        crypt32 = loader("crypt32", use_last_error=True)
        kernel32 = loader("kernel32", use_last_error=True)
        pointer = ctypes.POINTER(_DataBlob)
        crypt32.CryptProtectData.argtypes = [
            pointer, ctypes.c_wchar_p, pointer, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_uint32, pointer,
        ]
        crypt32.CryptProtectData.restype = ctypes.c_int
        crypt32.CryptUnprotectData.argtypes = [
            pointer, ctypes.POINTER(ctypes.c_wchar_p), pointer, ctypes.c_void_p,
            ctypes.c_void_p, ctypes.c_uint32, pointer,
        ]
        crypt32.CryptUnprotectData.restype = ctypes.c_int
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        return crypt32, kernel32
    except (AttributeError, OSError):
        raise PrivateKnowledgeError("unsupported_platform") from None


def _input_blob(value: bytearray) -> tuple[_DataBlob, object]:
    buffer_type = ctypes.c_ubyte * len(value)
    keepalive = buffer_type.from_buffer(value)
    return _DataBlob(len(value), keepalive), keepalive


def _release_output(
    output: _DataBlob,
    kernel32: object | None,
) -> PrivateKnowledgeError | None:
    try:
        if kernel32 is None:
            raise OSError
        if output.cbData:
            ctypes.memset(output.pbData, 0, output.cbData)
        if kernel32.LocalFree(ctypes.cast(output.pbData, ctypes.c_void_p)):
            raise OSError
        return None
    except Exception:
        return PrivateKnowledgeError("dpapi_cleanup_failed")
