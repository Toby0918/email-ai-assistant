"""Strict content-free manifest and result contract for evaluation staging."""

from __future__ import annotations

import json
import re
import stat
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import PrivateEvaluationError
from .repository_io import read_bounded_checked
from .schema import EvaluationCaseV1


_SELECTION_FIELDS = frozenset({
    "schema_version", "vault_id", "scope_fingerprint", "window_start",
    "window_end", "expires_at", "cases",
})
_CASE_FIELDS = frozenset({
    "record_id", "case_id", "revision", "approvals", "stratum", "expected",
})
_RECORD_ID = re.compile(r"^[0-9a-f]{32}$")
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_MAX_MANIFEST_BYTES = 512 * 1024
_PUBLIC_ERROR_CODES = frozenset({
    "evaluation_stage_selection_invalid", "evaluation_stage_selection_expired",
    "evaluation_stage_unavailable", "evaluation_stage_decrypt_invalid",
    "evaluation_stage_schema_invalid", "evaluation_key_unavailable",
})
_GENERIC_EMAIL = {
    "subject": "Deidentified message",
    "sender": "Deidentified sender",
    "recipients": ["Deidentified recipient"],
    "cc": [],
    "sent_at": "Deidentified time",
    "thread_text": "Deidentified content pending",
    "attachments": [],
}


@dataclass(frozen=True, slots=True, repr=False)
class StageEvaluationCaseSelection:
    record_id: str = field(repr=False)
    _template: EvaluationCaseV1 = field(repr=False)

    @classmethod
    def from_mapping(cls, value: object) -> StageEvaluationCaseSelection:
        if type(value) is not dict or set(value) != _CASE_FIELDS:
            _invalid_selection()
        record_id = value["record_id"]
        if type(record_id) is not str or _RECORD_ID.fullmatch(record_id) is None:
            _invalid_selection()
        case_value = {
            "schema_version": "PrivateEvaluationCaseV1",
            "case_id": value["case_id"],
            "revision": value["revision"],
            "approvals": value["approvals"],
            "stratum": value["stratum"],
            "deidentified_email": dict(_GENERIC_EMAIL),
            "expected": value["expected"],
        }
        try:
            template = EvaluationCaseV1.from_mapping(case_value)
        except PrivateEvaluationError:
            _invalid_selection()
        return cls(record_id, template)

    @property
    def case_id(self) -> str:
        return self._template.case_id

    @property
    def approvals(self):
        return self._template.approvals

    def build_case(self, thread_text: str) -> EvaluationCaseV1:
        value = self._template.to_mapping()
        value["deidentified_email"]["thread_text"] = thread_text  # type: ignore[index]
        return EvaluationCaseV1.from_mapping(value)

    def approval_times(self) -> tuple[datetime, ...]:
        values = [self.approvals.business, self.approvals.privacy]
        if self.approvals.pro_pair is not None:
            values.append(self.approvals.pro_pair)
        return tuple(_approval_time(item.approved_at) for item in values)

    def __repr__(self) -> str:
        return "StageEvaluationCaseSelection(<redacted>)"


class StageEvaluationSelection:
    __slots__ = (
        "vault_id", "scope_fingerprint", "window_start", "window_end",
        "expires_at", "cases", "_latest_review",
    )

    def __init__(self, value: object) -> None:
        if type(value) is not dict or set(value) != _SELECTION_FIELDS:
            _invalid_selection()
        if value["schema_version"] != "StageEvaluationSelectionV1":
            _invalid_selection()
        self.vault_id = _uuid4(value["vault_id"])
        self.scope_fingerprint = _fingerprint(value["scope_fingerprint"])
        self.window_start = _timestamp(value["window_start"])
        self.window_end = _timestamp(value["window_end"])
        if not timedelta(0) < self.window_end - self.window_start <= timedelta(days=732):
            _invalid_selection()
        raw_cases = value["cases"]
        if type(raw_cases) is not list or len(raw_cases) != 200:
            _invalid_selection()
        self.cases = tuple(
            StageEvaluationCaseSelection.from_mapping(item) for item in raw_cases
        )
        record_ids = tuple(item.record_id for item in self.cases)
        case_ids = tuple(item.case_id for item in self.cases)
        if len(set(record_ids)) != 200 or len(set(case_ids)) != 200:
            _invalid_selection()
        self._latest_review = max(
            review for item in self.cases for review in item.approval_times()
        )
        self.expires_at = _timestamp(value["expires_at"])
        if not self._latest_review < self.expires_at <= self._latest_review + timedelta(days=1):
            _invalid_selection()

    @classmethod
    def from_value(cls, value: object) -> StageEvaluationSelection:
        return value if isinstance(value, cls) else cls(value)

    def require_current(self, now: datetime) -> None:
        if (
            not isinstance(now, datetime) or now.utcoffset() != timedelta(0)
            or now.microsecond or now < self._latest_review or now >= self.expires_at
        ):
            raise PrivateEvaluationError("evaluation_stage_selection_expired")

    def __repr__(self) -> str:
        return "StageEvaluationSelection(<redacted>)"


@dataclass(frozen=True, slots=True)
class StageEvaluationResult:
    code: str
    accepted_count: int
    rejected_count: int

    def __post_init__(self) -> None:
        allowed = {
            "evaluation_stage_complete",
            "evaluation_stage_residual_blocked",
            "evaluation_stage_callback_failed",
        }
        if self.code not in allowed:
            raise PrivateEvaluationError("evaluation_stage_result_invalid")
        expected = (200, 0) if self.code == "evaluation_stage_complete" else (0, 200)
        if (
            type(self.accepted_count) is not int
            or type(self.rejected_count) is not int
            or (self.accepted_count, self.rejected_count) != expected
        ):
            raise PrivateEvaluationError("evaluation_stage_result_invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "ok": self.code == "evaluation_stage_complete",
            "code": self.code,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
        }


def load_stage_evaluation_manifest(
    path: Path,
    *,
    now: datetime,
) -> StageEvaluationSelection:
    try:
        payload = read_bounded_checked(
            Path(path), _MAX_MANIFEST_BYTES, _validate_manifest_path,
            lambda _stage, _path: None,
        )
        value = json.loads(payload.decode("utf-8"))
        selected = StageEvaluationSelection(value)
        selected.require_current(now)
        return selected
    except PrivateEvaluationError as exc:
        if exc.code == "evaluation_stage_selection_expired":
            raise
        _invalid_selection()
    except (UnicodeError, json.JSONDecodeError):
        _invalid_selection()


def public_stage_error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return code if code in _PUBLIC_ERROR_CODES else "internal_error"


def _validate_manifest_path(value: Path) -> Path:
    path = Path(value)
    try:
        if not path.is_absolute():
            _invalid_selection()
        resolved = path.resolve(strict=True)
        if resolved != path.resolve(strict=False):
            _invalid_selection()
        for component in (path, *path.parents):
            if not component.exists():
                continue
            metadata = component.lstat()
            reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
            if stat.S_ISLNK(metadata.st_mode) or getattr(
                metadata, "st_file_attributes", 0
            ) & reparse:
                _invalid_selection()
        if not stat.S_ISREG(path.lstat().st_mode):
            _invalid_selection()
        return resolved
    except PrivateEvaluationError:
        raise
    except (OSError, RuntimeError):
        _invalid_selection()


def _approval_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        _invalid_selection()
    if parsed.tzinfo is None:
        _invalid_selection()
    return parsed.astimezone(timezone.utc)


def _timestamp(value: object) -> datetime:
    if type(value) is not str or not value.endswith("Z"):
        _invalid_selection()
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        _invalid_selection()
    if parsed.microsecond:
        _invalid_selection()
    return parsed


def _fingerprint(value: object) -> str:
    if type(value) is not str or _FINGERPRINT.fullmatch(value) is None:
        _invalid_selection()
    return value


def _uuid4(value: object) -> str:
    from .schema_validation import uuid4_value

    try:
        return uuid4_value(value)
    except PrivateEvaluationError:
        _invalid_selection()


def _invalid_selection() -> None:
    raise PrivateEvaluationError("evaluation_stage_selection_invalid")
