"""Bounded subprocess-tree ownership for local Git commands."""

from __future__ import annotations

import os
import signal
import subprocess
import threading

from .errors import MigrationEvidenceError

if os.name == "nt":
    import ctypes


_JOB_OBJECT_EXTENDED_LIMIT_INFORMATION = 9
_JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000


if os.name == "nt":
    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = (
            ("process_time", ctypes.c_int64),
            ("job_time", ctypes.c_int64),
            ("limit_flags", ctypes.c_uint32),
            ("minimum_working_set", ctypes.c_size_t),
            ("maximum_working_set", ctypes.c_size_t),
            ("active_process_limit", ctypes.c_uint32),
            ("affinity", ctypes.c_size_t),
            ("priority_class", ctypes.c_uint32),
            ("scheduling_class", ctypes.c_uint32),
        )


    class _IoCounters(ctypes.Structure):
        _fields_ = (
            ("read_operations", ctypes.c_uint64),
            ("write_operations", ctypes.c_uint64),
            ("other_operations", ctypes.c_uint64),
            ("read_bytes", ctypes.c_uint64),
            ("write_bytes", ctypes.c_uint64),
            ("other_bytes", ctypes.c_uint64),
        )


    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = (
            ("basic", _BasicLimitInformation),
            ("io", _IoCounters),
            ("process_memory", ctypes.c_size_t),
            ("job_memory", ctypes.c_size_t),
            ("peak_process_memory", ctypes.c_size_t),
            ("peak_job_memory", ctypes.c_size_t),
        )


class ProcessTree:
    """Own one process group or kill-on-close Windows Job Object."""

    def __init__(self, job_handle: int | None) -> None:
        self._job_handle = job_handle
        self._process_group: int | None = None
        self._lock = threading.Lock()

    @classmethod
    def prepare(cls) -> ProcessTree:
        job = _create_windows_job() if os.name == "nt" else None
        return cls(job)

    def popen_options(self) -> dict[str, object]:
        if os.name == "nt":
            return {
                "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP,
            }
        return {"start_new_session": True}

    def attach(self, process: subprocess.Popen) -> None:
        self._process_group = process.pid
        if os.name == "nt" and not _assign_windows_job(
            self._job_handle,
            process,
        ):
            self.terminate(process)
            raise MigrationEvidenceError()

    def terminate(self, process: subprocess.Popen | None) -> None:
        with self._lock:
            if os.name == "nt":
                _close_windows_job(self._job_handle)
                self._job_handle = None
            elif self._process_group is not None:
                _kill_posix_group(self._process_group)
                self._process_group = None
            _kill_parent_if_running(process)
        _wait_parent(process)


def _create_windows_job() -> int:
    kernel = _windows_kernel()
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise MigrationEvidenceError()
    limits = _ExtendedLimitInformation()
    limits.basic.limit_flags = _JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(
        handle,
        _JOB_OBJECT_EXTENDED_LIMIT_INFORMATION,
        ctypes.byref(limits),
        ctypes.sizeof(limits),
    ):
        kernel.CloseHandle(handle)
        raise MigrationEvidenceError()
    return handle


def _assign_windows_job(
    handle: int | None,
    process: subprocess.Popen,
) -> bool:
    if handle is None:
        return False
    process_handle = getattr(process, "_handle", None)
    if process_handle is None:
        return False
    return bool(
        _windows_kernel().AssignProcessToJobObject(
            handle,
            process_handle,
        )
    )


def _close_windows_job(handle: int | None) -> None:
    if handle is None:
        return
    try:
        _windows_kernel().CloseHandle(handle)
    except Exception:
        pass


def _kill_posix_group(process_group: int) -> None:
    try:
        os.killpg(process_group, signal.SIGKILL)
    except (OSError, ProcessLookupError):
        pass


def _kill_parent_if_running(
    process: subprocess.Popen | None,
) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        process.kill()
    except OSError:
        pass


def _wait_parent(process: subprocess.Popen | None) -> None:
    if process is None:
        return
    try:
        process.wait(timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        pass


def _windows_kernel():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.argtypes = (
        ctypes.c_void_p,
        ctypes.c_wchar_p,
    )
    kernel.CreateJobObjectW.restype = ctypes.c_void_p
    kernel.SetInformationJobObject.argtypes = (
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    kernel.SetInformationJobObject.restype = ctypes.c_int
    kernel.AssignProcessToJobObject.argtypes = (
        ctypes.c_void_p,
        ctypes.c_void_p,
    )
    kernel.AssignProcessToJobObject.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    return kernel
