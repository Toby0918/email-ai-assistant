"""Create-only, fsynced synthetic receipt journal for the Issue #83 proof."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.r2_cross_stage_recovery import (
    CutoverSuccessAppendV1,
    INITIAL_JOURNAL_HEAD_FINGERPRINT,
    INITIAL_RECEIPT_FINGERPRINT,
    ReceiptPredecessorLinkV1,
)
from scripts.r2_publication_receipt_support import canonical_publication_receipt


class SyntheticDurableJournal:
    __slots__ = ("_path",)

    def __init__(self, path: Path) -> None:
        self._path = path
        with path.open("xb") as stream:
            stream.flush()
            os.fsync(stream.fileno())

    def append_publication(self, receipt) -> None:
        index = len(self.records())
        verified = canonical_publication_receipt(receipt, index)
        self._append(
            "PUBLICATION_RECEIPT",
            verified.material_fingerprint,
            publication=verified,
        )

    def append_success(self, record_type, prior, material):
        if record_type != "CUTOVER_SUCCESS" or prior != self.current_head():
            raise ValueError("R2_DURABLE_SUCCESS_BINDING_INVALID")
        record = self._append(record_type, material)
        return CutoverSuccessAppendV1.create(
            record_type=record_type,
            prior_head_fingerprint=prior,
            journal_head_fingerprint=record["head"],
            material_fingerprint=material,
        )

    def current_head(self) -> str:
        records = self.records()
        return (
            records[-1]["head"]
            if records
            else INITIAL_JOURNAL_HEAD_FINGERPRINT
        )

    def records(self):
        first = self._path.read_bytes()
        second = self._path.read_bytes()
        if first != second or first and not first.endswith(b"\n"):
            raise RuntimeError("R2_DURABLE_JOURNAL_UNSTABLE")
        return tuple(
            json.loads(line) for line in first.decode("ascii").splitlines()
        )

    def _append(self, record_type, material, publication=None):
        records = self.records()
        prior_head = (
            records[-1]["head"]
            if records
            else INITIAL_JOURNAL_HEAD_FINGERPRINT
        )
        predecessor = (
            records[-1]["receipt"]
            if records
            else INITIAL_RECEIPT_FINGERPRINT
        )
        link = ReceiptPredecessorLinkV1.create(
            record_type=record_type,
            material_fingerprint=material,
            predecessor_fingerprint=predecessor,
            prior_head_fingerprint=prior_head,
        )
        value = {
            "record_type": record_type,
            "receipt": link.receipt_fingerprint,
            "predecessor": link.predecessor_fingerprint,
            "prior_head": link.prior_head_fingerprint,
            "head": link.journal_head_fingerprint,
            "material": material,
        }
        if publication is not None:
            value.update(
                {
                    "publication_type": publication.publication_type,
                    "publication_schema_version": 1,
                    "receipt_fields": publication.mapping(),
                }
            )
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self._path.open("ab", buffering=0) as stream:
            stream.write(payload.encode("ascii") + b"\n")
            os.fsync(stream.fileno())
        if self.records()[-1] != value:
            raise RuntimeError("R2_DURABLE_JOURNAL_APPEND_UNOBSERVED")
        return value
