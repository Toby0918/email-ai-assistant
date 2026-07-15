"""Encrypted authority repository and isolated candidate-batch store."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Callable

from .atomic_ciphertext import exclusive_lock, read_ciphertext, replace_ciphertext
from .candidate_batch import CANDIDATE_MAGIC, CandidateBatchStore, DetachedCandidate
from .crypto_frames import decrypt_frame, encrypt_frame, validate_uuid4
from .errors import PrivateKnowledgeError
from .schema import KnowledgeCardV1


AUTHORITY_MAGIC = b"PKAUTH01"
_AUTHORITY_PURPOSE = b"authority-state/v1"
_MAX_STATE = 8 * 1024 * 1024


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
def _absolute_root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("path_invalid")
    return path.resolve()
