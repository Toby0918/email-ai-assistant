"""Create-only durable journal for database quiescence and publication."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import canonical, fingerprint, is_fingerprint


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseJournalRecordV1:
    sequence: int
    boundary: str
    fact: str
    material_fingerprint: str = field(repr=False)
    previous_record_hash: str = field(repr=False)
    record_hash: str = field(repr=False)


class DatabaseJournal:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._records: list[DatabaseJournalRecordV1] = []
        self._handle = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY, 0o600)

    @property
    def records(self) -> tuple[DatabaseJournalRecordV1, ...]:
        return tuple(self._records)

    @property
    def head(self) -> str:
        return self._records[-1].record_hash if self._records else "0" * 64

    def append(self, boundary: str, fact: str, material: str) -> None:
        if boundary not in {"legacy_service_quiescence", "database_prepare", "database_publish", "database_recovery"}:
            raise ValueError("database_journal_invalid")
        if fact not in {"intent", "effect_observed", "stable_verified", "committed", "classified"} or not is_fingerprint(material):
            raise ValueError("database_journal_invalid")
        body = {
            "sequence": len(self._records) + 1,
            "boundary": boundary,
            "fact": fact,
            "material_fingerprint": material,
            "previous_record_hash": self.head,
        }
        record_hash = fingerprint("database-journal-record-v1", body)
        record = DatabaseJournalRecordV1(**body, record_hash=record_hash)
        _write(self._handle, canonical({**body, "record_hash": record_hash}) + b"\n")
        os.fsync(self._handle)
        self._records.append(record)

    def verify(self) -> None:
        os.fsync(self._handle)
        rows = self._path.read_bytes().splitlines()
        if len(rows) != len(self._records):
            raise ValueError("database_journal_invalid")
        previous = "0" * 64
        for raw, record in zip(rows, self._records, strict=True):
            try:
                value = json.loads(raw.decode("ascii"))
                if type(value) is not dict or set(value) != _FIELDS:
                    raise ValueError
                supplied = value.pop("record_hash")
                if (
                    value["previous_record_hash"] != previous
                    or supplied != fingerprint("database-journal-record-v1", value)
                    or supplied != record.record_hash
                ):
                    raise ValueError
                previous = supplied
            except Exception:
                raise ValueError("database_journal_invalid") from None

    def close(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None


def _write(handle: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(handle, payload[offset:])
        if written <= 0:
            raise OSError("database_journal_write_failed")
        offset += written


_FIELDS = {
    "sequence",
    "boundary",
    "fact",
    "material_fingerprint",
    "previous_record_hash",
    "record_hash",
}
