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
_CREATE_SUSPENDED = 0x00000004


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
        self._posix_open = True
        self._lock = threading.Lock()

    @classmethod
    def prepare(cls) -> ProcessTree:
        job = _create_windows_job() if os.name == "nt" else None
        return cls(job)

    def popen_options(self) -> dict[str, object]:
        if os.name == "nt":
            return {
                "creationflags": (
                    subprocess.CREATE_NEW_PROCESS_GROUP
                    | _CREATE_SUSPENDED
                ),
            }
        return {"start_new_session": True}

    def attach(self, process: subprocess.Popen) -> None:
        if os.name == "nt":
            try:
                attached = _assign_windows_job(
                    self._job_handle,
                    process,
                )
                resumed = attached and _resume_windows_process(process)
            except Exception:
                resumed = False
            if not resumed:
                self.terminate(process)
                raise MigrationEvidenceError()
            return
        self._process_group = process.pid

    def finish(self, process: subprocess.Popen) -> int:
        """Close a POSIX group while its leader identity is reserved."""

        if os.name != "nt":
            _wait_posix_parent_without_reap(process)
            with self._lock:
                if self._posix_open:
                    process_group = (
                        self._process_group
                        if self._process_group is not None
                        else process.pid
                    )
                    self._process_group = None
                    self._posix_open = False
                    _kill_posix_group(process_group)
        return process.wait()

    def terminate(self, process: subprocess.Popen | None) -> None:
        cleanup_failed = False
        with self._lock:
            if os.name == "nt":
                if _close_windows_job(self._job_handle):
                    self._job_handle = None
                else:
                    cleanup_failed = True
            elif self._posix_open and process is not None:
                process_group = (
                    self._process_group
                    if self._process_group is not None
                    else process.pid
                )
                self._process_group = None
                self._posix_open = False
                try:
                    _kill_posix_group(process_group)
                except MigrationEvidenceError:
                    cleanup_failed = True
            _kill_parent_if_running(process)
        _wait_parent(process)
        if cleanup_failed:
            raise MigrationEvidenceError()


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


def _close_windows_job(handle: int | None) -> bool:
    if handle is None:
        return True
    kernel = _windows_kernel()
    try:
        if kernel.CloseHandle(handle):
            return True
    except Exception:
        pass
    try:
        kernel.TerminateJobObject(handle, 1)
    except Exception:
        pass
    return False


def _resume_windows_process(process: subprocess.Popen) -> bool:
    process_handle = getattr(process, "_handle", None)
    if process_handle is None:
        return False
    return _windows_ntdll().NtResumeProcess(process_handle) == 0


def _wait_posix_parent_without_reap(
    process: subprocess.Popen,
) -> None:
    try:
        waitid = os.waitid
        process_id_type = os.P_PID
        flags = os.WEXITED | os.WNOWAIT
    except AttributeError:
        raise MigrationEvidenceError() from None
    try:
        waitid(process_id_type, process.pid, flags)
    except ChildProcessError:
        if process.returncode is None:
            raise MigrationEvidenceError() from None
    except OSError:
        raise MigrationEvidenceError() from None


def _kill_posix_group(process_group: int) -> None:
    try:
        os.killpg(process_group, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        raise MigrationEvidenceError() from None


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
    kernel.TerminateJobObject.argtypes = (
        ctypes.c_void_p,
        ctypes.c_uint32,
    )
    kernel.TerminateJobObject.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    return kernel


def _windows_ntdll():
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtResumeProcess.argtypes = (ctypes.c_void_p,)
    ntdll.NtResumeProcess.restype = ctypes.c_long
    return ntdll
