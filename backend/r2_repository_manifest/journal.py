"""Create-only durable content-free journal for the Issue #75 slice."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from .canonical import canonical, fingerprint, is_fingerprint
from .types import ManifestBoundary

_ZERO = "0" * 64


@dataclass(frozen=True, slots=True, repr=False)
class ManifestJournalRecordV1:
    sequence: int
    boundary: ManifestBoundary
    item_index: int
    direction: str
    fact: str
    material_fingerprint: str = field(repr=False)
    previous_record_hash: str = field(repr=False)
    record_hash: str = field(repr=False)


class ManifestJournal:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._records: list[ManifestJournalRecordV1] = []
        self._handle = os.open(
            path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY, 0o600
        )

    @property
    def head(self) -> str:
        return self._records[-1].record_hash if self._records else _ZERO

    @property
    def records(self) -> tuple[ManifestJournalRecordV1, ...]:
        return tuple(self._records)

    def append(self, boundary, item_index, direction, fact, material):
        body = self._body(boundary, item_index, direction, fact, material)
        record_hash = fingerprint("manifest-journal-record-v1", body)
        values = {**body, "boundary": boundary}
        record = ManifestJournalRecordV1(**values, record_hash=record_hash)
        _write(self._handle, canonical({**body, "record_hash": record_hash}) + b"\n")
        os.fsync(self._handle)
        self._records.append(record)
        return record

    def verified_records(self) -> tuple[ManifestJournalRecordV1, ...]:
        os.fsync(self._handle)
        decoded = tuple(_decode(row) for row in self._path.read_bytes().splitlines())
        if decoded != tuple(self._records):
            raise ValueError("manifest_journal_invalid")
        return decoded

    def close(self) -> None:
        if self._handle is not None:
            os.close(self._handle)
            self._handle = None

    def _body(self, boundary, index, direction, fact, material):
        if (
            type(boundary) is not ManifestBoundary
            or type(index) is not int
            or not 1 <= index <= 100
            or direction not in {"forward", "reverse"}
            or fact not in {"intent", "observed", "committed"}
            or not is_fingerprint(material)
        ):
            raise ValueError("manifest_journal_invalid")
        return {
            "sequence": len(self._records) + 1,
            "boundary": boundary.value,
            "item_index": index,
            "direction": direction,
            "fact": fact,
            "material_fingerprint": material,
            "previous_record_hash": self.head,
        }


def _decode(payload: bytes) -> ManifestJournalRecordV1:
    try:
        value = json.loads(payload.decode("ascii"))
        if type(value) is not dict or set(value) != _FIELDS:
            raise ValueError
        record_hash = value.pop("record_hash")
        body = dict(value)
        if record_hash != fingerprint("manifest-journal-record-v1", body):
            raise ValueError
        body["boundary"] = ManifestBoundary(body["boundary"])
        return ManifestJournalRecordV1(**body, record_hash=record_hash)
    except Exception:
        raise ValueError("manifest_journal_invalid") from None


def _write(handle: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(handle, payload[offset:])
        if written <= 0:
            raise OSError("manifest_journal_write_failed")
        offset += written


_FIELDS = {
    "sequence",
    "boundary",
    "item_index",
    "direction",
    "fact",
    "material_fingerprint",
    "previous_record_hash",
    "record_hash",
}
