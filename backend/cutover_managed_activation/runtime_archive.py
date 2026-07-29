"""Bounded validation for reviewed wheel archives."""

from __future__ import annotations

import struct
import zipfile

from .canonical import fail

MAX_CAPTURED_WHEEL_BYTES = 256 * 1024 * 1024
MAX_WHEEL_PAYLOAD_BYTES = 100_000_000
MAX_WHEEL_MEMBERS = 4096
MAX_WHEEL_MEMBER_BYTES = 128 * 1024 * 1024
MAX_WHEEL_EXPANDED_BYTES = 512 * 1024 * 1024
MAX_WHEEL_COMPRESSION_RATIO = 1000
MAX_WHEEL_CENTRAL_DIRECTORY_BYTES = 8 * 1024 * 1024
_ALLOWED_COMPRESSION = {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
_ERROR = "runtime_wheel_invalid"
_EOCD = b"PK\x05\x06"
_CENTRAL_ENTRY = b"PK\x01\x02"


def preflight_wheel_payload(payload: bytes) -> None:
    if type(payload) is not bytes or not 22 <= len(payload) <= (
        MAX_WHEEL_PAYLOAD_BYTES
    ):
        fail(_ERROR)
    offset = payload.rfind(_EOCD, max(0, len(payload) - 65_557))
    if offset < 0 or offset + 22 > len(payload):
        fail(_ERROR)
    fields = struct.unpack_from("<4s4H2LH", payload, offset)
    _, disk, central_disk, disk_entries, entries, size, start, comment = fields
    if (
        disk != 0
        or central_disk != 0
        or disk_entries != entries
        or not 1 <= entries <= MAX_WHEEL_MEMBERS
        or size > MAX_WHEEL_CENTRAL_DIRECTORY_BYTES
        or start + size != offset
        or offset + 22 + comment != len(payload)
        or entries == 0xFFFF
        or size == 0xFFFFFFFF
        or start == 0xFFFFFFFF
    ):
        fail(_ERROR)
    _scan_central_directory(payload, start, size, entries)


def review_wheel_archive(
    archive,
    *,
    max_members: int = MAX_WHEEL_MEMBERS,
    max_member_bytes: int = MAX_WHEEL_MEMBER_BYTES,
    max_expanded_bytes: int = MAX_WHEEL_EXPANDED_BYTES,
    max_compression_ratio: int = MAX_WHEEL_COMPRESSION_RATIO,
):
    try:
        infos = archive.infolist()
    except (OSError, RuntimeError, zipfile.BadZipFile):
        fail(_ERROR)
    _require_positive_limits(
        max_members,
        max_member_bytes,
        max_expanded_bytes,
        max_compression_ratio,
    )
    if not infos or len(infos) > max_members:
        fail(_ERROR)
    safe_wheel_members([info.filename for info in infos])
    expanded = 0
    for info in infos:
        expanded = _review_info(
            info,
            expanded,
            max_member_bytes,
            max_expanded_bytes,
            max_compression_ratio,
        )
    return tuple(infos)


def safe_wheel_members(names: object) -> tuple[str, ...]:
    from pathlib import PurePosixPath

    if type(names) is not list or not names:
        fail(_ERROR)
    if any(type(name) is not str for name in names):
        fail(_ERROR)
    if len(set(names)) != len(names):
        fail(_ERROR)
    result = []
    for name in names:
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or any(part in {"", ".", ".."} for part in path.parts)
            or path.suffix.casefold() == ".pth"
            or path.name.casefold()
            in {"sitecustomize.py", "usercustomize.py"}
        ):
            fail(_ERROR)
        result.append(name)
    return tuple(result)


def _review_info(info, expanded, member_limit, total_limit, ratio_limit):
    if (
        type(info.file_size) is not int
        or type(info.compress_size) is not int
        or info.file_size < 0
        or info.compress_size < 0
        or info.file_size > member_limit
        or info.compress_type not in _ALLOWED_COMPRESSION
        or info.flag_bits & 1
        or _zip_link(info)
    ):
        fail(_ERROR)
    expanded += info.file_size
    if expanded > total_limit:
        fail(_ERROR)
    if info.file_size > ratio_limit * max(1, info.compress_size):
        fail(_ERROR)
    if info.is_dir() and info.file_size != 0:
        fail(_ERROR)
    return expanded


def _scan_central_directory(payload, start, size, entries) -> None:
    position = start
    end = start + size
    for _index in range(entries):
        if (
            position + 46 > end
            or payload[position : position + 4] != _CENTRAL_ENTRY
        ):
            fail(_ERROR)
        name_length = int.from_bytes(
            payload[position + 28 : position + 30], "little"
        )
        extra_length = int.from_bytes(
            payload[position + 30 : position + 32], "little"
        )
        comment_length = int.from_bytes(
            payload[position + 32 : position + 34], "little"
        )
        if not 1 <= name_length <= 4096:
            fail(_ERROR)
        position += 46 + name_length + extra_length + comment_length
        if position > end:
            fail(_ERROR)
    if position != end:
        fail(_ERROR)


def _require_positive_limits(*values: int) -> None:
    if any(type(value) is not int or value <= 0 for value in values):
        fail(_ERROR)


def _zip_link(info: zipfile.ZipInfo) -> bool:
    return (info.external_attr >> 16) & 0o170000 == 0o120000
