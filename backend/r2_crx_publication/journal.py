"""Create-only durable CRX unit journal."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import canonical, fingerprint


@dataclass(frozen=True, slots=True, repr=False)
class CrxJournalRecordV1:
    sequence: int
    boundary: str
    fact: str
    material_fingerprint: str = field(repr=False)
    previous_record_hash: str = field(repr=False)
    record_hash: str = field(repr=False)


class CrxJournal:
    def __init__(self, path: Path) -> None:
        self._records: list[CrxJournalRecordV1] = []
        self._handle = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY,
            0o600,
        )

    @property
    def records(self):
        return tuple(self._records)

    @property
    def head(self):
        return self._records[-1].record_hash if self._records else "0" * 64

    def append(self, boundary: str, fact: str, material: str) -> None:
        if boundary not in {"crx_prepare", "crx_publish", "crx_recovery"}:
            raise ValueError("crx_journal_invalid")
        body = {
            "sequence": len(self._records) + 1,
            "boundary": boundary,
            "fact": fact,
            "material_fingerprint": material,
            "previous_record_hash": self.head,
        }
        record_hash = fingerprint("crx-journal-record-v1", body)
        payload = canonical({**body, "record_hash": record_hash}) + b"\n"
        offset = 0
        while offset < len(payload):
            written = os.write(self._handle, payload[offset:])
            if written <= 0:
                raise OSError("crx_journal_write_failed")
            offset += written
        os.fsync(self._handle)
        self._records.append(CrxJournalRecordV1(**body, record_hash=record_hash))

    def close(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None
