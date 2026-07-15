"""Encrypted deidentified support bundles for reviewed knowledge candidates."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .atomic_ciphertext import exclusive_lock, read_ciphertext, replace_ciphertext
from .crypto_frames import decrypt_frame, encrypt_frame, validate_uuid4
from .errors import PrivateKnowledgeError
from .residual_scanner import scan_residuals
from .schema import CONVERSATION_BUCKETS, COUNTERPARTY_BUCKETS


CANDIDATE_MAGIC = b"PKCAND01"
_CANDIDATE_PURPOSE = b"candidate-batch/v1"
_MAX_STATE = 8 * 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class DetachedCandidate:
    candidate_id: str
    support_texts: tuple[str, ...] | str
    evidence: tuple[str, str] | None = None

    def __post_init__(self) -> None:
        validate_uuid4(self.candidate_id, "candidate_invalid")
        values = (
            (self.support_texts,)
            if isinstance(self.support_texts, str) else self.support_texts
        )
        if (not isinstance(values, tuple) or not 1 <= len(values) <= 200
                or not all(isinstance(item, str) and item for item in values)
                or sum(len(item) for item in values) > 2_000_000):
            raise PrivateKnowledgeError("candidate_invalid")
        if any(scan_residuals(item) for item in values):
            raise PrivateKnowledgeError("candidate_residual")
        if self.evidence is not None and not _valid_evidence(self.evidence):
            raise PrivateKnowledgeError("candidate_invalid")
        object.__setattr__(self, "support_texts", values)

    @property
    def text(self) -> str:
        return "\n\n".join(self.support_texts)

    def __repr__(self) -> str:
        return (
            f"DetachedCandidate(candidate_id={self.candidate_id!r}, "
            "support_texts=<redacted>, evidence=<redacted>)"
        )


class CandidateBatchStore:
    def __init__(
        self,
        root: Path,
        master_key: bytes | bytearray,
        *,
        batch_id: str,
        rng: Callable[[int], bytes] = os.urandom,
        clock: Callable[[], datetime] = (
            lambda: datetime.now(timezone.utc).replace(microsecond=0)
        ),
    ) -> None:
        self._root = _absolute_root(root)
        self._key = bytes(master_key)
        if len(self._key) != 32:
            raise PrivateKnowledgeError("private_key_invalid")
        self.batch_id = validate_uuid4(batch_id, "batch_invalid")
        self._rng = rng
        self._clock = clock
        self.path = self._root / f"batch-{self.batch_id}.pkcand"
        self._lock_name = f".candidate-{self.batch_id}.lock"

    def write(self, candidates: tuple[DetachedCandidate, ...]) -> tuple[str, ...]:
        if (not isinstance(candidates, tuple) or not 1 <= len(candidates) <= 200
                or not all(isinstance(item, DetachedCandidate) for item in candidates)
                or any(item.evidence is None for item in candidates)
                or len({item.candidate_id for item in candidates}) != len(candidates)):
            raise PrivateKnowledgeError("candidate_batch_invalid")
        created = self._now()
        state = _state(
            self.batch_id,
            created,
            created + timedelta(days=30),
            candidates,
        )
        with exclusive_lock(
            self._root, self._lock_name, error_code="candidate_batch_locked"
        ):
            self._write_state(state)
        return tuple(item.candidate_id for item in candidates)

    def read(self) -> tuple[DetachedCandidate, ...]:
        return self.read_with_expiry()[1]

    def read_with_expiry(self) -> tuple[str, tuple[DetachedCandidate, ...]]:
        with exclusive_lock(
            self._root, self._lock_name, error_code="candidate_batch_locked"
        ):
            state, expires, candidates = self._load()
            if self._now() >= expires:
                self._delete()
                raise PrivateKnowledgeError("candidate_batch_expired")
        return state["expires_at"], candidates

    def discard(self, candidate_id: str) -> None:
        validate_uuid4(candidate_id, "candidate_id_invalid")
        with exclusive_lock(
            self._root, self._lock_name, error_code="candidate_batch_locked"
        ):
            if not self.path.exists():
                return
            state, expires, candidates = self._load()
            if self._now() >= expires:
                self._delete()
                return
            remaining = tuple(
                item for item in candidates if item.candidate_id != candidate_id
            )
            if len(remaining) == len(candidates):
                return
            if not remaining:
                self._delete()
                return
            state["candidates"] = [_encode_candidate(item) for item in remaining]
            self._write_state(state)

    def _load(
        self,
    ) -> tuple[dict[str, object], datetime, tuple[DetachedCandidate, ...]]:
        frame = read_ciphertext(
            self.path, maximum=_MAX_STATE, code="candidate_read_failed"
        )
        plaintext = decrypt_frame(
            frame,
            magic=CANDIDATE_MAGIC,
            purpose=_CANDIDATE_PURPOSE,
            namespace_id=self.batch_id,
            master_key=self._key,
            error_code="candidate_authentication_failed",
        )
        try:
            state = json.loads(plaintext.decode("utf-8"))
            if (not isinstance(state, dict)
                    or set(state) != {
                        "format_version", "batch_id", "created_at", "expires_at",
                        "candidates",
                    }
                    or state["format_version"] != 3
                    or state["batch_id"] != self.batch_id
                    or not isinstance(state["candidates"], list)):
                raise ValueError
            result = tuple(_decode_candidate(item) for item in state["candidates"])
            created = _parse_time(state["created_at"])
            expires = _parse_time(state["expires_at"])
            if expires - created != timedelta(days=30):
                raise ValueError
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            raise PrivateKnowledgeError("candidate_schema_invalid") from None
        if (not 1 <= len(result) <= 200
                or len({item.candidate_id for item in result}) != len(result)):
            raise PrivateKnowledgeError("candidate_schema_invalid")
        return state, expires, result

    def _write_state(self, state: dict[str, object]) -> None:
        payload = json.dumps(
            state, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        frame = encrypt_frame(
            payload, magic=CANDIDATE_MAGIC, purpose=_CANDIDATE_PURPOSE,
            namespace_id=self.batch_id, master_key=self._key, rng=self._rng,
        )
        replace_ciphertext(self.path, frame, error_code="candidate_write_failed")

    def _delete(self) -> None:
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            raise PrivateKnowledgeError("candidate_delete_failed") from None

    def _now(self) -> datetime:
        try:
            value = self._clock()
        except Exception:
            raise PrivateKnowledgeError("clock_invalid") from None
        if (not isinstance(value, datetime) or value.utcoffset() != timedelta(0)
                or value.microsecond):
            raise PrivateKnowledgeError("clock_invalid")
        return value


def _state(
    batch_id: str,
    created: datetime,
    expires: datetime,
    candidates: tuple[DetachedCandidate, ...],
) -> dict[str, object]:
    return {
        "format_version": 3,
        "batch_id": batch_id,
        "created_at": _format_time(created),
        "expires_at": _format_time(expires),
        "candidates": [_encode_candidate(item) for item in candidates],
    }


def _encode_candidate(candidate: DetachedCandidate) -> dict[str, object]:
    assert candidate.evidence is not None
    return {
        "candidate_id": candidate.candidate_id,
        "support_texts": list(candidate.support_texts),
        "evidence": {
            "conversation_bucket": candidate.evidence[0],
            "counterparty_bucket": candidate.evidence[1],
        },
    }


def _decode_candidate(value: object) -> DetachedCandidate:
    if (not isinstance(value, dict)
            or set(value) != {"candidate_id", "support_texts", "evidence"}
            or not isinstance(value["support_texts"], list)
            or not isinstance(value["evidence"], dict)
            or set(value["evidence"]) != {
                "conversation_bucket", "counterparty_bucket"
            }):
        raise ValueError
    evidence = (
        value["evidence"]["conversation_bucket"],
        value["evidence"]["counterparty_bucket"],
    )
    return DetachedCandidate(
        value["candidate_id"], tuple(value["support_texts"]), evidence
    )


def _valid_evidence(value: object) -> bool:
    return (
        isinstance(value, tuple)
        and len(value) == 2
        and value[0] in CONVERSATION_BUCKETS
        and value[1] in COUNTERPARTY_BUCKETS
    )


def _absolute_root(value: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        raise PrivateKnowledgeError("path_invalid")
    return path.resolve()


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_time(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError
    parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    if parsed.microsecond:
        raise ValueError
    return parsed
