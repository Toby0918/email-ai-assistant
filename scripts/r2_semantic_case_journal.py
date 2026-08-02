"""Durably bind one selected gap to its owning R2 execution result."""

from __future__ import annotations

import json
import os
from pathlib import Path

from backend.cutover_composition_contracts.canonical import fingerprint


class SemanticCaseJournal:
    __slots__ = ("_binding", "_path")

    def __init__(self, path: Path, semantic: str, direction: str, gap: str):
        self._path = path
        self._binding = fingerprint(
            "r2-semantic-case-binding-v1", [semantic, direction, gap]
        )
        with path.open("xb") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        self._append(
            {
                "record_type": "CASE_BINDING",
                "binding": self._binding,
                "semantic": semantic,
                "direction": direction,
                "gap": gap,
            }
        )

    def execute(self, effect):
        evidence = effect()
        evidence_fingerprint = fingerprint(
            "r2-owning-semantic-effect-v1", evidence
        )
        self._append(
            {
                "record_type": "OWNING_RESULT",
                "binding": self._binding,
                "evidence": evidence_fingerprint,
            }
        )
        receipt = fingerprint(
            "r2-executed-semantic-case-v1",
            {
                "binding": self._binding,
                "evidence": evidence_fingerprint,
                "records": self.records(),
            },
        )
        self._append(
            {
                "record_type": "EXECUTED_CASE_RECEIPT",
                "binding": self._binding,
                "receipt": receipt,
            }
        )
        records = self.records()
        if records[-1]["receipt"] != receipt or len(records) != 3:
            raise RuntimeError("R2_SEMANTIC_RECEIPT_NOT_DURABLE")
        return receipt

    def records(self):
        first = self._path.read_bytes()
        second = self._path.read_bytes()
        if first != second or not first.endswith(b"\n"):
            raise RuntimeError("R2_SEMANTIC_JOURNAL_UNSTABLE")
        records = tuple(
            json.loads(line) for line in first.decode("ascii").splitlines()
        )
        if not records or records[0].get("record_type") != "CASE_BINDING":
            raise RuntimeError("R2_SEMANTIC_BINDING_NOT_DURABLE")
        return records

    def _append(self, body):
        records = self.records() if self._path.stat().st_size else ()
        prior = records[-1]["head"] if records else "0" * 64
        value = {
            **body,
            "prior": prior,
            "head": fingerprint(
                "r2-semantic-case-head-v1", [prior, body]
            ),
        }
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with self._path.open("ab", buffering=0) as stream:
            stream.write(payload.encode("ascii") + b"\n")
            os.fsync(stream.fileno())
        if self.records()[-1] != value:
            raise RuntimeError("R2_SEMANTIC_RECORD_NOT_DURABLE")
