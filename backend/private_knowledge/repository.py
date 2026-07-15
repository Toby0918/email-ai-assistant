"""Encrypted authority repository and isolated candidate-batch store."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .atomic_ciphertext import exclusive_lock, read_ciphertext, replace_ciphertext
from .crypto_frames import decrypt_frame, encrypt_frame, validate_uuid4
from .errors import PrivateKnowledgeError
from .residual_scanner import scan_residuals
from .schema import (
    CONVERSATION_BUCKETS,
    COUNTERPARTY_BUCKETS,
    KnowledgeCardV1,
)


AUTHORITY_MAGIC = b"PKAUTH01"
CANDIDATE_MAGIC = b"PKCAND01"
_AUTHORITY_PURPOSE = b"authority-state/v1"
_CANDIDATE_PURPOSE = b"candidate-batch/v1"
_MAX_STATE = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class DetachedCandidate:
    candidate_id: str
    text: str

    def __post_init__(self) -> None:
        validate_uuid4(self.candidate_id, "candidate_invalid")
        if not isinstance(self.text, str) or not 1 <= len(self.text) <= 2_000_000:
            raise PrivateKnowledgeError("candidate_invalid")
        if scan_residuals(self.text):
            raise PrivateKnowledgeError("candidate_residual")

    def __repr__(self) -> str:
        return f"DetachedCandidate(candidate_id={self.candidate_id!r}, text=<redacted>)"


class AuthorityRepository:
    def __init__(
        self,
        root: Path,
        master_key: bytes | bytearray,
        *,
        authority_id: str,
        rng: Callable[[int], bytes] = os.urandom,
        crash_hook: Callable[[str], None] | None = None,
    ) -> None:
        self._root = _absolute_root(root)
        self._key = bytes(master_key)
        if len(self._key) != 32:
            raise PrivateKnowledgeError("private_key_invalid")
        self.authority_id = validate_uuid4(authority_id, "authority_invalid")
        self._rng = rng
        self._crash_hook = crash_hook
        self._path = self._root / "authority.pkauth"

    def initialize(self) -> None:
        with exclusive_lock(self._root, ".authority.lock", error_code="repository_locked"):
            if self._path.exists():
                raise PrivateKnowledgeError("repository_exists")
            self._write({"format_version": 1, "authority_id": self.authority_id, "cards": []})

    def insert(self, card: KnowledgeCardV1) -> None:
        if not isinstance(card, KnowledgeCardV1):
            raise PrivateKnowledgeError("repository_input_invalid")
        def mutation(cards: dict[str, KnowledgeCardV1]) -> None:
            if card.card_id in cards:
                raise PrivateKnowledgeError("card_exists")
            cards[card.card_id] = card
        self._mutate(mutation)

    def replace(self, card: KnowledgeCardV1) -> None:
        if not isinstance(card, KnowledgeCardV1):
            raise PrivateKnowledgeError("repository_input_invalid")
        def mutation(cards: dict[str, KnowledgeCardV1]) -> None:
            if card.card_id not in cards:
                raise PrivateKnowledgeError("card_missing")
            cards[card.card_id] = card
        self._mutate(mutation)

    def delete(self, card_id: str) -> None:
        validate_uuid4(card_id, "card_id_invalid")
        def mutation(cards: dict[str, KnowledgeCardV1]) -> None:
            if cards.pop(card_id, None) is None:
                raise PrivateKnowledgeError("card_missing")
        self._mutate(mutation)

    def get(self, card_id: str) -> KnowledgeCardV1 | None:
        validate_uuid4(card_id, "card_id_invalid")
        return self._load_cards().get(card_id)

    def list_cards(self) -> tuple[KnowledgeCardV1, ...]:
        cards = self._load_cards()
        return tuple(cards[key] for key in sorted(cards))

    def _mutate(self, callback: Callable[[dict[str, KnowledgeCardV1]], None]) -> None:
        with exclusive_lock(self._root, ".authority.lock", error_code="repository_locked"):
            cards = self._load_cards()
            callback(cards)
            if len(cards) > 10_000:
                raise PrivateKnowledgeError("repository_limit_exceeded")
            self._write({"format_version": 1, "authority_id": self.authority_id,
                         "cards": [cards[key].to_mapping() for key in sorted(cards)]})

    def _load_cards(self) -> dict[str, KnowledgeCardV1]:
        state = self._read()
        if set(state) != {"format_version", "authority_id", "cards"}:
            raise PrivateKnowledgeError("repository_schema_invalid")
        if state["format_version"] != 1 or state["authority_id"] != self.authority_id:
            raise PrivateKnowledgeError("repository_schema_invalid")
        values = state["cards"]
        if not isinstance(values, list) or len(values) > 10_000:
            raise PrivateKnowledgeError("repository_schema_invalid")
        cards = [KnowledgeCardV1.from_mapping(value) for value in values]
        if len({card.card_id for card in cards}) != len(cards):
            raise PrivateKnowledgeError("repository_schema_invalid")
        return {card.card_id: card for card in cards}

    def _read(self) -> dict[str, object]:
        frame = read_ciphertext(
            self._path, maximum=_MAX_STATE, code="repository_read_failed"
        )
        plaintext = decrypt_frame(
            frame, magic=AUTHORITY_MAGIC, purpose=_AUTHORITY_PURPOSE,
            namespace_id=self.authority_id, master_key=self._key,
            error_code="repository_authentication_failed",
        )
        try:
            value = json.loads(plaintext.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PrivateKnowledgeError("repository_schema_invalid") from None
        if not isinstance(value, dict):
            raise PrivateKnowledgeError("repository_schema_invalid")
        return value

    def _write(self, state: dict[str, object]) -> None:
        payload = json.dumps(
            state, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        frame = encrypt_frame(
            payload, magic=AUTHORITY_MAGIC, purpose=_AUTHORITY_PURPOSE,
            namespace_id=self.authority_id, master_key=self._key, rng=self._rng,
        )
        replace_ciphertext(
            self._path, frame, error_code="repository_write_failed",
            crash_hook=self._crash_hook,
        )


class CandidateBatchStore:
    def __init__(self, root: Path, master_key: bytes | bytearray, *, batch_id: str,
                 evidence: tuple[str, str] = ("1", "1"),
                 rng: Callable[[int], bytes] = os.urandom) -> None:
        self._root = _absolute_root(root)
        self._key = bytes(master_key)
        if len(self._key) != 32:
            raise PrivateKnowledgeError("private_key_invalid")
        self.batch_id = validate_uuid4(batch_id, "batch_invalid")
        if (not isinstance(evidence, tuple) or len(evidence) != 2
                or evidence[0] not in CONVERSATION_BUCKETS
                or evidence[1] not in COUNTERPARTY_BUCKETS):
            raise PrivateKnowledgeError("candidate_batch_invalid")
        self.evidence = evidence
        self._rng = rng
        self.path = self._root / f"batch-{self.batch_id}.pkcand"

    def write(self, candidates: tuple[DetachedCandidate, ...]) -> tuple[str, ...]:
        if not isinstance(candidates, tuple) or not 1 <= len(candidates) <= 200:
            raise PrivateKnowledgeError("candidate_batch_invalid")
        if not all(isinstance(item, DetachedCandidate) for item in candidates):
            raise PrivateKnowledgeError("candidate_batch_invalid")
        if len({item.candidate_id for item in candidates}) != len(candidates):
            raise PrivateKnowledgeError("candidate_batch_invalid")
        payload = json.dumps(
            {"format_version": 1, "batch_id": self.batch_id,
             "evidence": {"conversation_bucket": self.evidence[0],
                          "counterparty_bucket": self.evidence[1]},
             "candidates": [{"candidate_id": item.candidate_id, "text": item.text}
                            for item in candidates]},
            sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        frame = encrypt_frame(
            payload, magic=CANDIDATE_MAGIC, purpose=_CANDIDATE_PURPOSE,
            namespace_id=self.batch_id, master_key=self._key, rng=self._rng,
        )
        replace_ciphertext(self.path, frame, error_code="candidate_write_failed")
        return tuple(item.candidate_id for item in candidates)

    def read(self) -> tuple[DetachedCandidate, ...]:
        return self.read_with_evidence()[1]

    def read_with_evidence(
        self,
    ) -> tuple[tuple[str, str], tuple[DetachedCandidate, ...]]:
        frame = read_ciphertext(
            self.path, maximum=_MAX_STATE, code="candidate_read_failed"
        )
        plaintext = decrypt_frame(
            frame, magic=CANDIDATE_MAGIC, purpose=_CANDIDATE_PURPOSE,
            namespace_id=self.batch_id, master_key=self._key,
            error_code="candidate_authentication_failed",
        )
        try:
            state = json.loads(plaintext.decode("utf-8"))
            if (not isinstance(state, dict)
                    or set(state) != {"format_version", "batch_id", "evidence", "candidates"}
                    or state["format_version"] != 1 or state["batch_id"] != self.batch_id
                    or not isinstance(state["candidates"], list)
                    or not isinstance(state["evidence"], dict)
                    or set(state["evidence"]) != {
                        "conversation_bucket", "counterparty_bucket"
                    }):
                raise ValueError
            evidence = (
                state["evidence"]["conversation_bucket"],
                state["evidence"]["counterparty_bucket"],
            )
            if (evidence[0] not in CONVERSATION_BUCKETS
                    or evidence[1] not in COUNTERPARTY_BUCKETS):
                raise ValueError
            result = tuple(DetachedCandidate(**item) for item in state["candidates"])
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise PrivateKnowledgeError("candidate_schema_invalid") from None
        if not 1 <= len(result) <= 200:
            raise PrivateKnowledgeError("candidate_schema_invalid")
        return evidence, result


def _absolute_root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("path_invalid")
    return path.resolve()
