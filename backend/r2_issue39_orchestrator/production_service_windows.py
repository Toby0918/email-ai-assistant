"""Windows process, port, and loopback-health observation for Issue #39."""

from __future__ import annotations

import ctypes
import hashlib
import json
import socket
import struct
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass


PORT = 8765
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_STILL_ACTIVE = 259


@dataclass(frozen=True, slots=True, repr=False)
class ProcessObservation:
    pid: int
    image: str
    command_hash: str
    creation_time: int


def command_hash(command):
    return hashlib.sha256(
        subprocess.list2cmdline(command).encode("utf-16-le")
    ).hexdigest()


def observe_process(pid):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetExitCodeProcess.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)
    )
    kernel.QueryFullProcessImageNameW.argtypes = (
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_wchar_p,
        ctypes.POINTER(ctypes.c_uint32),
    )
    kernel.GetProcessTimes.argtypes = (
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p,
    )
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid
    )
    if not handle:
        return None
    try:
        return _observe_open_process(kernel, handle, pid)
    finally:
        kernel.CloseHandle(handle)


def _observe_open_process(kernel, handle, pid):
    code = ctypes.c_uint32()
    if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    if code.value != _STILL_ACTIVE:
        return None
    size = ctypes.c_uint32(32768)
    image = ctypes.create_unicode_buffer(size.value)
    if not kernel.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    times = tuple(ctypes.c_uint64() for _ in range(4))
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(item) for item in times)):
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    command = process_command_line(handle)
    return ProcessObservation(
        pid, image.value,
        hashlib.sha256(command.encode("utf-16-le")).hexdigest(),
        times[0].value,
    )


class _UnicodeString(ctypes.Structure):
    _fields_ = [
        ("length", ctypes.c_ushort),
        ("maximum", ctypes.c_ushort),
        ("buffer", ctypes.c_void_p),
    ]


def process_command_line(handle):
    ntdll = ctypes.WinDLL("ntdll")
    ntdll.NtQueryInformationProcess.argtypes = (
        ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
        ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong),
    )
    ntdll.NtQueryInformationProcess.restype = ctypes.c_long
    needed = ctypes.c_ulong()
    ntdll.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(needed))
    if needed.value < ctypes.sizeof(_UnicodeString) or needed.value > 64 * 1024:
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    buffer = ctypes.create_string_buffer(needed.value)
    status = ntdll.NtQueryInformationProcess(
        handle, 60, buffer, needed.value, ctypes.byref(needed)
    )
    value = _UnicodeString.from_buffer(buffer)
    if status != 0 or value.length > 60 * 1024 or value.length % 2:
        raise ValueError("R2_ISSUE39_SERVICE_PROCESS_INVALID")
    return ctypes.wstring_at(value.buffer, value.length // 2)


def port_owner():
    iphlp = ctypes.WinDLL("iphlpapi", use_last_error=True)
    iphlp.GetExtendedTcpTable.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong), ctypes.c_int,
        ctypes.c_ulong, ctypes.c_uint32, ctypes.c_ulong,
    )
    iphlp.GetExtendedTcpTable.restype = ctypes.c_ulong
    size = ctypes.c_ulong()
    iphlp.GetExtendedTcpTable(None, ctypes.byref(size), False, 2, 5, 0)
    if size.value < 4 or size.value > 4 * 1024 * 1024:
        raise ValueError("R2_ISSUE39_SERVICE_PORT_INVALID")
    buffer = ctypes.create_string_buffer(size.value)
    if iphlp.GetExtendedTcpTable(buffer, ctypes.byref(size), False, 2, 5, 0) != 0:
        raise ValueError("R2_ISSUE39_SERVICE_PORT_INVALID")
    return _owner_from_table(buffer.raw, size.value)


def _owner_from_table(payload, size):
    count = int.from_bytes(payload[:4], "little")
    if count > 65536 or 4 + count * 24 > size:
        raise ValueError("R2_ISSUE39_SERVICE_PORT_INVALID")
    expected_port = socket.htons(PORT)
    expected_addr = int.from_bytes(socket.inet_aton("127.0.0.1"), "little")
    owners = []
    for index in range(count):
        fields = struct.unpack_from("<6I", payload, 4 + index * 24)
        state, address, port, _remote_address, _remote_port, pid = fields
        if state == 2 and address == expected_addr and port == expected_port:
            owners.append(pid)
    if len(owners) > 1:
        raise ValueError("R2_ISSUE39_SERVICE_PORT_INVALID")
    return owners[0] if owners else None


def health():
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{PORT}/api/health", timeout=1
        ) as response:
            payload = response.read(4097)
        value = json.loads(payload, object_pairs_hook=_strict_pairs)
        return response.status == 200 and value == {"ok": True, "status": "ok"}
    except (OSError, urllib.error.URLError, ValueError, json.JSONDecodeError):
        return False


def _strict_pairs(pairs):
    value = {}
    for name, item in pairs:
        if name in value:
            raise ValueError("R2_ISSUE39_SERVICE_HEALTH_INVALID")
        value[name] = item
    return value
