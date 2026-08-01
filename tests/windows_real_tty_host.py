"""Detached host for one fresh hidden Windows console TTY test."""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from backend.r2_preflight_process import PREFLIGHT_ACKNOWLEDGEMENT
from tests.r2_preflight_process_fixture import valid_hidden_envelope


_STD_INPUT_HANDLE = -10
_KEY_EVENT = 0x0001


class _Character(ctypes.Union):
    _fields_ = (
        ("UnicodeChar", wintypes.WCHAR),
        ("AsciiChar", ctypes.c_char),
    )


class _KeyEvent(ctypes.Structure):
    _fields_ = (
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _Character),
        ("dwControlKeyState", wintypes.DWORD),
    )


class _Event(ctypes.Union):
    _fields_ = (
        ("KeyEvent", _KeyEvent),
        ("Padding", ctypes.c_byte * 16),
    )


class _InputRecord(ctypes.Structure):
    _fields_ = (("EventType", wintypes.WORD), ("Event", _Event))


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    target = Path(sys.argv[1])
    if target.exists() or not target.parent.is_dir():
        return 3
    try:
        result = _run_operator(target.parent)
    except Exception:
        result = {"status": "rejected", "exit_code": -1}
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


def _run_operator(workdir=None) -> dict[str, object]:
    root = Path(__file__).resolve().parents[1]
    workdir = Path(workdir) if workdir is not None else root
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(root)
    python = Path(sys.executable).with_name("python.exe")
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    process = subprocess.Popen(
        (
            str(python),
            "-B",
            "-m",
            "tests.r2_preflight_process_worker",
            "current-topology",
        ),
        cwd=workdir,
        env=environment,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=startup,
        close_fds=True,
    )
    try:
        _inject_console_input(
            process.pid,
            PREFLIGHT_ACKNOWLEDGEMENT + "\r" + valid_hidden_envelope() + "\r",
        )
        exit_code = process.wait(timeout=10)
    except Exception:
        process.kill()
        process.wait(timeout=5)
        raise
    return {"status": "complete", "exit_code": exit_code}


def _inject_console_input(process_id: int, text: str) -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _configure(kernel)
    time.sleep(0.08)
    if not kernel.AttachConsole(process_id):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        handle = kernel.GetStdHandle(_STD_INPUT_HANDLE)
        if not handle or handle == ctypes.c_void_p(-1).value:
            raise RuntimeError("REAL_TTY_INPUT_UNAVAILABLE")
        if not kernel.FlushConsoleInputBuffer(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        records = (_InputRecord * len(text))()
        for index, character in enumerate(text):
            records[index].EventType = _KEY_EVENT
            records[index].Event.KeyEvent = _KeyEvent(
                True,
                1,
                0,
                0,
                _Character(UnicodeChar=character),
                0,
            )
        written = wintypes.DWORD()
        if not kernel.WriteConsoleInputW(
            handle,
            records,
            len(records),
            ctypes.byref(written),
        ) or written.value != len(records):
            raise RuntimeError("REAL_TTY_INPUT_REJECTED")
    finally:
        kernel.FreeConsole()


def _configure(kernel) -> None:
    kernel.AttachConsole.argtypes = (wintypes.DWORD,)
    kernel.AttachConsole.restype = wintypes.BOOL
    kernel.GetStdHandle.argtypes = (wintypes.DWORD,)
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.FlushConsoleInputBuffer.argtypes = (wintypes.HANDLE,)
    kernel.FlushConsoleInputBuffer.restype = wintypes.BOOL
    kernel.WriteConsoleInputW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_InputRecord),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel.WriteConsoleInputW.restype = wintypes.BOOL
    kernel.FreeConsole.restype = wintypes.BOOL


if __name__ == "__main__":
    raise SystemExit(main())
