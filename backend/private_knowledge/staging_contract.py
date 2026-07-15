"""Content-free value contract for the raw-vault staging boundary."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .atomic_ciphertext import read_ciphertext
from .errors import PrivateKnowledgeError


_FIELDS = {
    "schema_version", "vault_id", "scope_fingerprint", "window_start",
    "window_end", "expires_at", "record_ids", "business_review",
    "privacy_review",
}
_REVIEW_FIELDS = {"actor_ref", "role", "approved_at"}
_RECORD_ID = re.compile(r"^[0-9a-f]{32}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


class StageKnowledgeSelection:
    __slots__ = (
        "vault_id", "scope_fingerprint", "window_start", "window_end",
        "expires_at", "_record_ids", "business_actor", "privacy_actor",
        "_latest_review",
    )

    def __init__(self, value: object) -> None:
        if not isinstance(value, dict) or set(value) != _FIELDS:
            raise PrivateKnowledgeError("stage_selection_invalid")
        if value["schema_version"] != "StageKnowledgeSelectionV1":
            raise PrivateKnowledgeError("stage_selection_invalid")
        self.vault_id = _uuid4(value["vault_id"])
        self.scope_fingerprint = _fingerprint(value["scope_fingerprint"])
        self.window_start = _timestamp(value["window_start"])
        self.window_end = _timestamp(value["window_end"])
        if not timedelta(0) < self.window_end - self.window_start <= timedelta(days=732):
            raise PrivateKnowledgeError("stage_selection_invalid")
        self._record_ids = _record_ids(value["record_ids"])
        self.business_actor, business_at = _review(
            value["business_review"], "business"
        )
        self.privacy_actor, privacy_at = _review(
            value["privacy_review"], "privacy_security"
        )
        if self.business_actor == self.privacy_actor:
            raise PrivateKnowledgeError("stage_selection_invalid")
        self._latest_review = max(business_at, privacy_at)
        self.expires_at = _timestamp(value["expires_at"])
        if not self._latest_review < self.expires_at <= self._latest_review + timedelta(days=1):
            raise PrivateKnowledgeError("stage_selection_invalid")

    @classmethod
    def from_value(cls, value: object) -> StageKnowledgeSelection:
        return value if isinstance(value, cls) else cls(value)

    @property
    def record_ids(self) -> tuple[str, ...]:
        return self._record_ids

    def require_current(self, now: datetime) -> None:
        if (not isinstance(now, datetime) or now.utcoffset() != timedelta(0)
                or now.microsecond or now < self._latest_review
                or now >= self.expires_at):
            raise PrivateKnowledgeError("stage_selection_expired")

    def __repr__(self) -> str:
        return "StageKnowledgeSelection(<redacted>)"


def load_stage_selection_manifest(
    path: Path,
    *,
    now: datetime,
) -> StageKnowledgeSelection:
    try:
        payload = read_ciphertext(
            Path(path), maximum=128 * 1024, code="stage_selection_invalid"
        )
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        raise PrivateKnowledgeError("stage_selection_invalid") from None
    selected = StageKnowledgeSelection(value)
    selected.require_current(now)
    return selected


@dataclass(frozen=True, slots=True, repr=False)
class CandidateBatchReceipt:
    batch_id: str = field(repr=False)
    candidate_ids: tuple[str, ...] = field(repr=False)

    def __post_init__(self) -> None:
        if (not isinstance(self.candidate_ids, tuple)
                or not 1 <= len(self.candidate_ids) <= 200):
            raise PrivateKnowledgeError("stage_result_invalid")
        _uuid4(self.batch_id, "stage_result_invalid")
        for value in self.candidate_ids:
            _uuid4(value, "stage_result_invalid")

    def __repr__(self) -> str:
        return "CandidateBatchReceipt(<redacted>)"


@dataclass(frozen=True, slots=True)
class StageKnowledgeResult:
    code: str
    accepted_count: int
    rejected_count: int
    candidate_ids: tuple[str, ...] = field(repr=False)
    batch_id: str | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        allowed = {"stage_complete", "stage_residual_blocked", "stage_callback_failed"}
        if (self.code not in allowed or type(self.accepted_count) is not int
                or type(self.rejected_count) is not int
                or self.accepted_count < 0 or self.rejected_count < 0
                or not isinstance(self.candidate_ids, tuple)):
            raise PrivateKnowledgeError("stage_result_invalid")
        for value in self.candidate_ids:
            _uuid4(value, "stage_result_invalid")
        success = self.code == "stage_complete"
        if (success and (self.batch_id is None or not self.candidate_ids)):
            raise PrivateKnowledgeError("stage_result_invalid")
        if not success and (self.batch_id is not None or self.candidate_ids):
            raise PrivateKnowledgeError("stage_result_invalid")
        if self.batch_id is not None:
            _uuid4(self.batch_id, "stage_result_invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.code == "stage_complete", "code": self.code,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "candidate_ids": list(self.candidate_ids),
            "batch_id": self.batch_id,
        }


def _record_ids(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= 200:
        raise PrivateKnowledgeError("stage_selection_invalid")
    result = tuple(value)
    if (not all(isinstance(item, str) and _RECORD_ID.fullmatch(item) for item in result)
            or len(set(result)) != len(result)):
        raise PrivateKnowledgeError("stage_selection_invalid")
    return result


def _review(value: object, role: str) -> tuple[str, datetime]:
    if not isinstance(value, dict) or set(value) != _REVIEW_FIELDS or value["role"] != role:
        raise PrivateKnowledgeError("stage_selection_invalid")
    actor = value["actor_ref"]
    if not isinstance(actor, str) or re.fullmatch(r"actor-[a-z0-9-]{3,80}", actor) is None:
        raise PrivateKnowledgeError("stage_selection_invalid")
    return actor, _timestamp(value["approved_at"])


def _timestamp(value: object) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise PrivateKnowledgeError("stage_selection_invalid")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise PrivateKnowledgeError("stage_selection_invalid") from None
    if parsed.microsecond:
        raise PrivateKnowledgeError("stage_selection_invalid")
    return parsed


def _fingerprint(value: object) -> str:
    if not isinstance(value, str) or _FINGERPRINT.fullmatch(value) is None:
        raise PrivateKnowledgeError("stage_selection_invalid")
    return value


def _uuid4(value: object, code: str = "stage_selection_invalid") -> str:
    if not isinstance(value, str):
        raise PrivateKnowledgeError(code)
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise PrivateKnowledgeError(code) from None
    if str(parsed) != value or parsed.version != 4:
        raise PrivateKnowledgeError(code)
    return value
