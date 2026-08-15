"""Fixed no-input Windows console identity gate for Issue #39."""

from __future__ import annotations

import ctypes
import os
import sys


def require_fixed_windows_console_v1() -> bool:
    """Accept only three live character-device console streams."""

    try:
        if os.name != "nt" or not all(
            stream.isatty() for stream in (sys.stdin, sys.stdout, sys.stderr)
        ):
            return False
        kernel = ctypes.windll.kernel32
        mode = ctypes.c_uint32()
        for identifier in (-10, -11, -12):
            handle = kernel.GetStdHandle(identifier)
            if handle in (0, -1) or kernel.GetFileType(handle) != 0x0002:
                return False
            if not kernel.GetConsoleMode(handle, ctypes.byref(mode)):
                return False
        return True
    except Exception:
        return False
