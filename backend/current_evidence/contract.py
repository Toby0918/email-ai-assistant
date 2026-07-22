"""Strict immutable value contract for deidentified current-click evidence."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.private_knowledge.entity_patterns import PLACEHOLDER
from backend.private_knowledge.residual_scanner import scan_residuals

from .artifact_policy import has_forbidden_artifact


_FIELDS = {
    "schema_version",
    "submission_id",
    "created_at",
    "thread_segments",
    "attachment_evidence",
}
_THREAD_FIELDS = {"source_id", "message_role", "text"}
_ATTACHMENT_FIELDS = {
    "source_id",
    "parse_status",
    "semantic_status",
    "text",
}
_THREAD_ID = re.compile(r"thread:(0|[1-9][0-9]?)\Z")
_ATTACHMENT_ID = re.compile(r"attachment:([0-4])\Z")
_MAX_THREAD_ITEMS = 50
_MAX_THREAD_ITEM_CHARACTERS = 2_000
_MAX_THREAD_CHARACTERS = 20_000
_MAX_ATTACHMENT_ITEMS = 5
_MAX_ATTACHMENT_ITEM_CHARACTERS = 8_000
_MAX_ATTACHMENT_CHARACTERS = 25_000


class CurrentEvidenceError(ValueError):
    """Content-free contract failure."""

    def __init__(self, code: str = "evidence_contract_invalid") -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True, repr=False)
class ThreadEvidence:
    source_id: str
    message_role: str
    text: str = field(repr=False)

    def to_mapping(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "message_role": self.message_role,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True, repr=False)
class AttachmentEvidence:
    source_id: str
    parse_status: str
    semantic_status: str
    text: str = field(repr=False)

    def to_mapping(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "parse_status": self.parse_status,
            "semantic_status": self.semantic_status,
            "text": self.text,
        }


@dataclass(frozen=True, slots=True, repr=False, init=False)
class CurrentClickEvidenceV1:
    submission_id: str
    created_at: str
    thread_segments: tuple[ThreadEvidence, ...] = field(repr=False)
    attachment_evidence: tuple[AttachmentEvidence, ...] = field(repr=False)
    schema_version: str = "CurrentClickEvidenceV1"

    @classmethod
    def from_mapping(cls, value: object) -> CurrentClickEvidenceV1:
        mapping = _exact_mapping(value, _FIELDS)
        if mapping["schema_version"] != "CurrentClickEvidenceV1":
            raise CurrentEvidenceError()
        threads = _thread_segments(mapping["thread_segments"])
        attachments = _attachment_evidence(mapping["attachment_evidence"])
        instance = object.__new__(cls)
        object.__setattr__(instance, "submission_id", _uuid4(mapping["submission_id"]))
        object.__setattr__(instance, "created_at", _timestamp(mapping["created_at"]))
        object.__setattr__(instance, "thread_segments", threads)
        object.__setattr__(instance, "attachment_evidence", attachments)
        object.__setattr__(instance, "schema_version", "CurrentClickEvidenceV1")
        return instance

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "submission_id": self.submission_id,
            "created_at": self.created_at,
            "thread_segments": [item.to_mapping() for item in self.thread_segments],
            "attachment_evidence": [
                item.to_mapping() for item in self.attachment_evidence
            ],
        }

    def __repr__(self) -> str:
        return "CurrentClickEvidenceV1(<redacted>)"


def _thread_segments(value: object) -> tuple[ThreadEvidence, ...]:
    if not isinstance(value, list) or not 1 <= len(value) <= _MAX_THREAD_ITEMS:
        raise CurrentEvidenceError()
    items: list[ThreadEvidence] = []
    total = 0
    for index, raw in enumerate(value):
        mapping = _exact_mapping(raw, _THREAD_FIELDS)
        source_id = _source_id(mapping["source_id"], _THREAD_ID, index)
        role = mapping["message_role"]
        if role not in {"history", "current"}:
            raise CurrentEvidenceError()
        text = _safe_text(mapping["text"], _MAX_THREAD_ITEM_CHARACTERS)
        total += len(text)
        items.append(ThreadEvidence(source_id, role, text))
    if total > _MAX_THREAD_CHARACTERS:
        raise CurrentEvidenceError()
    if items[-1].message_role != "current" or any(
        item.message_role != "history" for item in items[:-1]
    ):
        raise CurrentEvidenceError()
    return tuple(items)


def _attachment_evidence(value: object) -> tuple[AttachmentEvidence, ...]:
    if not isinstance(value, list) or len(value) > _MAX_ATTACHMENT_ITEMS:
        raise CurrentEvidenceError()
    items: list[AttachmentEvidence] = []
    total = 0
    for index, raw in enumerate(value):
        mapping = _exact_mapping(raw, _ATTACHMENT_FIELDS)
        source_id = _source_id(mapping["source_id"], _ATTACHMENT_ID, index)
        if mapping["parse_status"] != "parsed":
            raise CurrentEvidenceError()
        semantic_status = mapping["semantic_status"]
        if semantic_status not in {"unreviewed", "reviewed"}:
            raise CurrentEvidenceError()
        text = _safe_text(mapping["text"], _MAX_ATTACHMENT_ITEM_CHARACTERS)
        total += len(text)
        items.append(AttachmentEvidence(source_id, "parsed", semantic_status, text))
    if total > _MAX_ATTACHMENT_CHARACTERS:
        raise CurrentEvidenceError()
    return tuple(items)


def _exact_mapping(value: object, fields: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != fields:
        raise CurrentEvidenceError()
    return value


def _source_id(value: object, pattern: re.Pattern[str], index: int) -> str:
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise CurrentEvidenceError()
    if int(value.rsplit(":", 1)[1]) != index:
        raise CurrentEvidenceError()
    return value


def _safe_text(value: object, maximum: int) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= maximum:
        raise CurrentEvidenceError()
    if (
        value != value.strip()
        or PLACEHOLDER.search(value)
        or has_forbidden_artifact(value)
        or scan_residuals(value)
    ):
        raise CurrentEvidenceError()
    return value


def _uuid4(value: object) -> str:
    if not isinstance(value, str):
        raise CurrentEvidenceError()
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise CurrentEvidenceError() from None
    if str(parsed) != value or parsed.version != 4:
        raise CurrentEvidenceError()
    return value


def _timestamp(value: object) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise CurrentEvidenceError()
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        raise CurrentEvidenceError() from None
    if parsed.utcoffset() != timedelta(0) or parsed.microsecond:
        raise CurrentEvidenceError()
    if parsed.isoformat().replace("+00:00", "Z") != value:
        raise CurrentEvidenceError()
    return value


__all__ = ["CurrentClickEvidenceV1"]
