"""Durable four-fact journal for Runtime PREPARE and PUBLISH."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import canonical, fingerprint, is_fingerprint


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeJournalRecordV1:
    sequence: int
    boundary: str
    fact: str
    material_fingerprint: str = field(repr=False)
    previous_record_hash: str = field(repr=False)
    record_hash: str = field(repr=False)


class RuntimeJournal:
    def __init__(self, path: Path) -> None:
        self._records: list[RuntimeJournalRecordV1] = []
        self._handle = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY,
            0o600,
        )

    @property
    def records(self) -> tuple[RuntimeJournalRecordV1, ...]:
        return tuple(self._records)

    @property
    def head(self) -> str:
        return self._records[-1].record_hash if self._records else "0" * 64

    def append(self, boundary: str, fact: str, material: str) -> None:
        if (
            boundary not in {"runtime_prepare", "runtime_publish", "runtime_recovery"}
            or fact not in {"intent", "effect_observed", "stable_verified", "committed", "classified"}
            or not is_fingerprint(material)
        ):
            raise ValueError("runtime_journal_invalid")
        body = {
            "sequence": len(self._records) + 1,
            "boundary": boundary,
            "fact": fact,
            "material_fingerprint": material,
            "previous_record_hash": self.head,
        }
        record_hash = fingerprint("runtime-journal-record-v1", body)
        payload = canonical({**body, "record_hash": record_hash}) + b"\n"
        _write(self._handle, payload)
        os.fsync(self._handle)
        self._records.append(
            RuntimeJournalRecordV1(**body, record_hash=record_hash)
        )

    def close(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None


def _write(handle: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(handle, payload[offset:])
        if written <= 0:
            raise OSError("runtime_journal_write_failed")
        offset += written
