"""Encrypted deidentified candidate inbox inside the authority namespace."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from .atomic_ciphertext import exclusive_lock, read_ciphertext, replace_ciphertext
from .crypto_frames import decrypt_frame, encrypt_frame, validate_uuid4
from .errors import PrivateKnowledgeError
from .repository import DetachedCandidate
from .schema import CONVERSATION_BUCKETS, COUNTERPARTY_BUCKETS


_MAGIC = b"PKIMPRT1"
_PURPOSE = b"imported-candidates/v1"


@dataclass(frozen=True, slots=True, repr=False)
class ImportedCandidate:
    candidate_id: str
    support_texts: tuple[str, ...]
    evidence: tuple[str, str]
    expires_at: str

    def __post_init__(self) -> None:
        DetachedCandidate(self.candidate_id, self.support_texts, self.evidence)
        if (not isinstance(self.evidence, tuple) or len(self.evidence) != 2
                or self.evidence[0] not in CONVERSATION_BUCKETS
                or self.evidence[1] not in COUNTERPARTY_BUCKETS):
            raise PrivateKnowledgeError("candidate_import_invalid")
        _parse_expiry(self.expires_at)

    def __repr__(self) -> str:
        return (
            f"ImportedCandidate(candidate_id={self.candidate_id!r}, "
            "support_texts=<redacted>, evidence=<redacted>)"
        )

    def is_expired(self, now: datetime) -> bool:
        return now >= _parse_expiry(self.expires_at)


class ImportedCandidateStore:
    def __init__(self, root: Path, master_key: bytes | bytearray, *, authority_id: str,
                 rng: Callable[[int], bytes] = os.urandom) -> None:
        self._root = Path(root).resolve()
        self._key = bytes(master_key)
        self._authority_id = validate_uuid4(authority_id, "authority_invalid")
        self._rng = rng
        self._path = self._root / "candidate-imports.pkimpt"

    def initialize(self, *, resume_empty: bool = False) -> None:
        with exclusive_lock(self._root, ".candidate-imports.lock", error_code="candidate_import_locked"):
            if self._path.exists():
                if resume_empty and not self._load():
                    return
                raise PrivateKnowledgeError("candidate_import_exists")
            self._write({"format_version": 1, "authority_id": self._authority_id,
                         "candidates": []})

    def add(self, candidate: ImportedCandidate) -> None:
        if not isinstance(candidate, ImportedCandidate):
            raise PrivateKnowledgeError("candidate_import_invalid")
        def mutate(values: dict[str, ImportedCandidate]) -> None:
            existing = values.get(candidate.candidate_id)
            if existing == candidate:
                return
            if existing is not None:
                raise PrivateKnowledgeError("candidate_exists")
            values[candidate.candidate_id] = candidate
        self._mutate(mutate)

    def get(self, candidate_id: str) -> ImportedCandidate | None:
        validate_uuid4(candidate_id, "candidate_id_invalid")
        return self._load().get(candidate_id)

    def delete(self, candidate_id: str) -> None:
        def mutate(values: dict[str, ImportedCandidate]) -> None:
            if values.pop(candidate_id, None) is None:
                raise PrivateKnowledgeError("candidate_missing")
        self._mutate(mutate)

    def discard(self, candidate_id: str) -> None:
        validate_uuid4(candidate_id, "candidate_id_invalid")
        self._mutate(lambda values: values.pop(candidate_id, None))

    def _mutate(self, callback: Callable[[dict[str, ImportedCandidate]], None]) -> None:
        with exclusive_lock(self._root, ".candidate-imports.lock", error_code="candidate_import_locked"):
            values = self._load()
            callback(values)
            self._write({
                "format_version": 1, "authority_id": self._authority_id,
                "candidates": [
                    {"candidate_id": item.candidate_id,
                     "support_texts": list(item.support_texts),
                     "evidence": {"conversation_bucket": item.evidence[0],
                                  "counterparty_bucket": item.evidence[1]},
                     "expires_at": item.expires_at}
                    for item in (values[key] for key in sorted(values))
                ],
            })

    def _load(self) -> dict[str, ImportedCandidate]:
        frame = read_ciphertext(
            self._path, maximum=8 * 1024 * 1024, code="candidate_import_read_failed"
        )
        plaintext = decrypt_frame(
            frame, magic=_MAGIC, purpose=_PURPOSE,
            namespace_id=self._authority_id, master_key=self._key,
            error_code="candidate_import_authentication_failed",
        )
        try:
            state = json.loads(plaintext.decode("utf-8"))
            if (not isinstance(state, dict)
                    or set(state) != {"format_version", "authority_id", "candidates"}
                    or state["format_version"] != 1
                    or state["authority_id"] != self._authority_id
                    or not isinstance(state["candidates"], list)):
                raise ValueError
            items = tuple(_decode_item(item) for item in state["candidates"])
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise PrivateKnowledgeError("candidate_import_schema_invalid") from None
        if len(items) > 200 or len({item.candidate_id for item in items}) != len(items):
            raise PrivateKnowledgeError("candidate_import_schema_invalid")
        return {item.candidate_id: item for item in items}

    def _write(self, state: dict[str, object]) -> None:
        payload = json.dumps(
            state, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        frame = encrypt_frame(
            payload, magic=_MAGIC, purpose=_PURPOSE,
            namespace_id=self._authority_id, master_key=self._key, rng=self._rng,
        )
        replace_ciphertext(self._path, frame, error_code="candidate_import_write_failed")


def _decode_item(value: object) -> ImportedCandidate:
    if (not isinstance(value, dict)
            or set(value) != {
                "candidate_id", "support_texts", "evidence", "expires_at"
            }
            or not isinstance(value["support_texts"], list)
            or not isinstance(value["evidence"], dict)
            or set(value["evidence"]) != {
                "conversation_bucket", "counterparty_bucket"
            }):
        raise ValueError
    return ImportedCandidate(
        value["candidate_id"], tuple(value["support_texts"]),
        (value["evidence"]["conversation_bucket"],
         value["evidence"]["counterparty_bucket"]),
        value["expires_at"],
    )


def _parse_expiry(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PrivateKnowledgeError("candidate_import_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise PrivateKnowledgeError("candidate_import_invalid") from None
    if parsed.microsecond:
        raise PrivateKnowledgeError("candidate_import_invalid")
    return parsed
