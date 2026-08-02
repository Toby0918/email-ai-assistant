"""Durable, content-free hash-chain for the representative tracer."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import canonical, fingerprint, is_fingerprint
from .types import MainPublicationBoundary

_ZERO = "0" * 64
_FACTS = frozenset({"intent", "observed", "committed"})


@dataclass(frozen=True, slots=True, repr=False)
class MainPublicationJournalRecordV1:
    sequence: int
    boundary: MainPublicationBoundary
    fact: str
    material_fingerprint: str = field(repr=False)
    previous_record_hash: str = field(repr=False)
    record_hash: str = field(repr=False)


class MainPublicationJournal:
    """Create-only journal owned by one fresh synthetic sandbox."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._records: list[MainPublicationJournalRecordV1] = []
        self._handle = os.open(
            path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY,
            0o600,
        )

    @property
    def head(self) -> str:
        return self._records[-1].record_hash if self._records else _ZERO

    @property
    def records(self) -> tuple[MainPublicationJournalRecordV1, ...]:
        return tuple(self._records)

    def append(
        self,
        boundary: MainPublicationBoundary,
        fact: str,
        material_fingerprint: str,
    ) -> MainPublicationJournalRecordV1:
        body = self._body(boundary, fact, material_fingerprint)
        record_hash = fingerprint("main-publication-journal-record-v1", body)
        record_values = dict(body)
        record_values["boundary"] = boundary
        record = MainPublicationJournalRecordV1(
            **record_values,
            record_hash=record_hash,
        )
        payload = canonical({**body, "record_hash": record_hash}) + b"\n"
        _write_all(self._handle, payload)
        os.fsync(self._handle)
        self._records.append(record)
        return record

    def close(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None

    def verified_records(self) -> tuple[MainPublicationJournalRecordV1, ...]:
        os.fsync(self._handle)
        rows = self._path.read_bytes().splitlines()
        decoded = tuple(_decode(row) for row in rows)
        if decoded != tuple(self._records):
            raise ValueError("main_publication_journal_invalid")
        return decoded

    def _body(self, boundary, fact, material) -> dict[str, object]:
        if (
            type(boundary) is not MainPublicationBoundary
            or fact not in _FACTS
            or not is_fingerprint(material)
        ):
            raise ValueError("main_publication_journal_invalid")
        return {
            "sequence": len(self._records) + 1,
            "boundary": boundary.value,
            "fact": fact,
            "material_fingerprint": material,
            "previous_record_hash": self.head,
        }


def _decode(payload: bytes) -> MainPublicationJournalRecordV1:
    try:
        value = json.loads(payload.decode("ascii"))
        if type(value) is not dict or set(value) != _ROW_FIELDS:
            raise ValueError
        record_hash = value.pop("record_hash")
        boundary = MainPublicationBoundary(value["boundary"])
        body = dict(value)
        if (
            record_hash
            != fingerprint("main-publication-journal-record-v1", body)
        ):
            raise ValueError
        body["boundary"] = boundary
        return MainPublicationJournalRecordV1(**body, record_hash=record_hash)
    except Exception:
        raise ValueError("main_publication_journal_invalid") from None


def _write_all(handle: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(handle, payload[offset:])
        if written <= 0:
            raise OSError("main_publication_journal_write_failed")
        offset += written


_ROW_FIELDS = {
    "sequence",
    "boundary",
    "fact",
    "material_fingerprint",
    "previous_record_hash",
    "record_hash",
}
