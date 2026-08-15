"""Create-only durable snapshots for the Issue #39 R2 journal."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from backend.r2_production_binding import ApprovedCutoverBindingV3
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2

from .durable_io import (
    MAX_SEGMENT_BYTES,
    guard_directory,
    read_segment,
    write_segment,
)


_MAX_SEGMENTS = 384


class Issue39LedgerStatusV1(str, Enum):
    CREATED = "ISSUE39_LEDGER_CREATED"
    APPENDED = "ISSUE39_LEDGER_APPENDED"
    VERIFIED = "ISSUE39_LEDGER_VERIFIED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39LedgerLocationV1:
    directory: Path = field(repr=False)


@dataclass(frozen=True, slots=True, repr=False)
class Issue39LedgerResultV1:
    status: Issue39LedgerStatusV1
    segment_count: int
    journal: R2TransactionJournalV2 | None = field(repr=False)


def _create_issue39_ledger_v1(*, location, binding, journal):
    try:
        _require_inputs(location, binding, journal)
        if journal.record_count != 1 or os.path.lexists(location.directory):
            raise ValueError
        with guard_directory(location.directory.parent, flush=True):
            location.directory.mkdir(mode=0o700)
        with guard_directory(location.directory, flush=True):
            _write_segment(location.directory, journal)
            verified = _verify_segments(location.directory, binding)
        if verified.to_framed_bytes() != journal.to_framed_bytes():
            raise ValueError
        return Issue39LedgerResultV1(Issue39LedgerStatusV1.CREATED, 1, journal)
    except Exception:
        return _blocked()


def _append_issue39_journal_v1(*, location, binding, previous, journal):
    try:
        _require_inputs(location, binding, previous)
        _require_inputs(location, binding, journal)
        before = previous.to_framed_bytes()
        after = journal.to_framed_bytes()
        if (
            not previous.record_count < journal.record_count <= _MAX_SEGMENTS
            or not after.startswith(before)
        ):
            raise ValueError
        with guard_directory(location.directory, flush=True):
            _verify_matches_journal(location.directory, previous)
            cursor = len(before)
            for payload in _successor_payloads(before, after):
                successor = R2TransactionJournalV2.from_framed_bytes(
                    payload,
                    binding=binding,
                )
                _write_segment(location.directory, successor, payload[cursor:])
                cursor = len(payload)
            _verify_matches_journal(location.directory, journal)
        return Issue39LedgerResultV1(
            Issue39LedgerStatusV1.APPENDED,
            journal.record_count,
            journal,
        )
    except Exception:
        return _blocked()


def _reopen_issue39_ledger_v1(*, location, binding):
    try:
        if (
            type(location) is not _Issue39LedgerLocationV1
            or type(binding) is not ApprovedCutoverBindingV3
        ):
            raise TypeError
        with guard_directory(location.directory, flush=False):
            journal = _verify_segments(location.directory, binding)
        return Issue39LedgerResultV1(
            Issue39LedgerStatusV1.VERIFIED,
            journal.record_count,
            journal,
        )
    except Exception:
        return _blocked()


def _write_segment(
    directory: Path,
    journal: R2TransactionJournalV2,
    payload: bytes | None = None,
) -> None:
    payload = journal.to_framed_bytes() if payload is None else payload
    if not 1 <= len(payload) <= MAX_SEGMENT_BYTES:
        raise ValueError
    path = directory / _segment_name(journal)
    write_segment(path, payload)


def _verify_segments(directory: Path, binding):
    entries = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    if not 1 <= len(entries) <= _MAX_SEGMENTS:
        raise ValueError
    frames = []
    for index, path in enumerate(entries):
        if path.name != _expected_name_prefix(index, path.name):
            raise ValueError
        payload = read_segment(path)
        if not _is_one_frame(payload):
            raise ValueError
        frames.append(payload)
    latest = R2TransactionJournalV2.from_framed_bytes(
        b"".join(frames), binding=binding
    )
    if latest.record_count != len(entries):
        raise ValueError
    heads = (latest.genesis.head_fingerprint,) + tuple(
        record.head_fingerprint for record in latest.records
    )
    if any(
        path.name != f"{index:06d}-{head}.r2j"
        for index, (path, head) in enumerate(zip(entries, heads, strict=True))
    ):
        raise ValueError
    return latest


def _verify_matches_journal(directory: Path, journal) -> None:
    entries = tuple(sorted(directory.iterdir(), key=lambda item: item.name))
    frames = _split_frames(journal.to_framed_bytes())
    heads = (journal.genesis.head_fingerprint,) + tuple(
        record.head_fingerprint for record in journal.records
    )
    if len(entries) != len(frames) or len(frames) != len(heads):
        raise ValueError
    for index, (path, frame, head) in enumerate(
        zip(entries, frames, heads, strict=True)
    ):
        if (
            path.name != f"{index:06d}-{head}.r2j"
            or read_segment(path) != frame
        ):
            raise ValueError


def _successor_payloads(before: bytes, after: bytes) -> tuple[bytes, ...]:
    cursor = len(before)
    values = []
    while cursor < len(after):
        if (
            cursor + 9 > len(after)
            or after[cursor + 8:cursor + 9] != b":"
            or any(value not in b"0123456789abcdef" for value in after[cursor:cursor + 8])
        ):
            raise ValueError
        size = int(after[cursor:cursor + 8], 16)
        end = cursor + 9 + size + 1
        if size < 1 or end > len(after) or after[end - 1:end] != b"\n":
            raise ValueError
        values.append(after[:end])
        cursor = end
    if not values:
        raise ValueError
    return tuple(values)


def _is_one_frame(payload: bytes) -> bool:
    if (
        len(payload) < 11
        or payload[8:9] != b":"
        or any(value not in b"0123456789abcdef" for value in payload[:8])
    ):
        return False
    size = int(payload[:8], 16)
    return size >= 1 and len(payload) == size + 10 and payload[-1:] == b"\n"


def _split_frames(payload: bytes) -> tuple[bytes, ...]:
    values = []
    cursor = 0
    while cursor < len(payload):
        if cursor + 9 > len(payload):
            raise ValueError
        size = int(payload[cursor:cursor + 8], 16)
        end = cursor + size + 10
        frame = payload[cursor:end]
        if not _is_one_frame(frame):
            raise ValueError
        values.append(frame)
        cursor = end
    return tuple(values)


def _segment_name(journal) -> str:
    index = journal.record_count - 1
    return f"{index:06d}-{journal.current_head_fingerprint}.r2j"


def _expected_name_prefix(index: int, name: str) -> str:
    if type(name) is not str or len(name) != 75:
        raise ValueError
    return name if name.startswith(f"{index:06d}-") and name.endswith(".r2j") else ""


def _require_inputs(location, binding, journal) -> None:
    if (
        type(location) is not _Issue39LedgerLocationV1
        or type(location.directory) is not type(Path())
        or not location.directory.is_absolute()
        or type(binding) is not ApprovedCutoverBindingV3
        or type(journal) is not R2TransactionJournalV2
        or journal.binding_fingerprint != binding.binding_fingerprint
    ):
        raise TypeError


def _blocked():
    return Issue39LedgerResultV1(Issue39LedgerStatusV1.INCIDENT_STOP, 0, None)
