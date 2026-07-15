"""Strict encrypted-only schema for deidentified private evaluation cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .errors import PrivateEvaluationError
from .schema_validation import (
    enum_tuple as _enum_tuple,
    enum_value as _enum,
    invalid as _invalid,
    list_value as _list,
    mapping as _mapping,
    positive_int as _positive_int,
    safe_text as _safe_text,
    safe_text_tuple as _safe_text_tuple,
    text_value as _text,
    uuid4_value as _uuid4,
)
from .schema_values import (
    ACTION_TYPES,
    ATTACHMENT_KINDS,
    CATEGORIES,
    DIRECTIONS,
    LANGUAGES,
    RISK_TYPES,
)

_CASE_FIELDS = frozenset({
    "schema_version", "case_id", "revision", "approvals", "stratum",
    "deidentified_email", "expected",
})
_APPROVAL_FIELDS = frozenset({"business", "privacy", "pro_pair"})
_APPROVAL_VALUE_FIELDS = frozenset({"actor_ref", "role", "approved_at", "case_revision"})
_STRATUM_FIELDS = frozenset({"category", "language", "direction", "primary_risk"})
_EMAIL_FIELDS = frozenset({
    "subject", "sender", "recipients", "cc", "sent_at", "thread_text", "attachments",
})
_ATTACHMENT_FIELDS = frozenset({"kind", "text"})
_EXPECTED_FIELDS = frozenset({"category", "mandatory_risk_types", "required_action_types"})
_DATASET_FIELDS = frozenset({"schema_version", "dataset_namespace", "cases"})
@dataclass(frozen=True, slots=True, repr=False)
class ApprovalV1:
    actor_ref: str
    role: str
    approved_at: str
    case_revision: int

    def to_mapping(self) -> dict[str, object]:
        return {
            "actor_ref": self.actor_ref, "role": self.role,
            "approved_at": self.approved_at, "case_revision": self.case_revision,
        }


@dataclass(frozen=True, slots=True, repr=False)
class CaseApprovalsV1:
    business: ApprovalV1
    privacy: ApprovalV1
    pro_pair: ApprovalV1 | None

    def to_mapping(self) -> dict[str, object]:
        return {
            "business": self.business.to_mapping(),
            "privacy": self.privacy.to_mapping(),
            "pro_pair": None if self.pro_pair is None else self.pro_pair.to_mapping(),
        }


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationStratumV1:
    category: str
    language: str
    direction: str
    primary_risk: str

    def to_mapping(self) -> dict[str, object]:
        return {
            "category": self.category, "language": self.language,
            "direction": self.direction, "primary_risk": self.primary_risk,
        }


@dataclass(frozen=True, slots=True, repr=False)
class DeidentifiedAttachmentV1:
    kind: str
    text: str

    def to_mapping(self) -> dict[str, str]:
        return {"kind": self.kind, "text": self.text}


@dataclass(frozen=True, slots=True, repr=False)
class DeidentifiedEmailV1:
    subject: str
    sender: str
    recipients: tuple[str, ...]
    cc: tuple[str, ...]
    sent_at: str
    thread_text: str
    attachments: tuple[DeidentifiedAttachmentV1, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "subject": self.subject, "sender": self.sender,
            "recipients": list(self.recipients), "cc": list(self.cc),
            "sent_at": self.sent_at, "thread_text": self.thread_text,
            "attachments": [item.to_mapping() for item in self.attachments],
        }


@dataclass(frozen=True, slots=True, repr=False)
class ExpectedResultV1:
    category: str
    mandatory_risk_types: tuple[str, ...]
    required_action_types: tuple[str, ...]

    def to_mapping(self) -> dict[str, object]:
        return {
            "category": self.category,
            "mandatory_risk_types": list(self.mandatory_risk_types),
            "required_action_types": list(self.required_action_types),
        }


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationCaseV1:
    schema_version: str
    case_id: str
    revision: int
    approvals: CaseApprovalsV1
    stratum: EvaluationStratumV1
    deidentified_email: DeidentifiedEmailV1
    expected: ExpectedResultV1

    @classmethod
    def from_mapping(cls, value: object) -> "EvaluationCaseV1":
        data = _mapping(value, _CASE_FIELDS)
        if data["schema_version"] != "PrivateEvaluationCaseV1":
            _invalid()
        revision = _positive_int(data["revision"])
        approvals = _approvals(data["approvals"], revision)
        stratum = _stratum(data["stratum"])
        expected = _expected(data["expected"], stratum)
        return cls(
            "PrivateEvaluationCaseV1", _uuid4(data["case_id"]), revision,
            approvals, stratum, _email(data["deidentified_email"]), expected,
        )

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "case_id": self.case_id,
            "revision": self.revision, "approvals": self.approvals.to_mapping(),
            "stratum": self.stratum.to_mapping(),
            "deidentified_email": self.deidentified_email.to_mapping(),
            "expected": self.expected.to_mapping(),
        }


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationDatasetV1:
    schema_version: str
    dataset_namespace: str
    cases: tuple[EvaluationCaseV1, ...]

    @classmethod
    def from_mapping(cls, value: object) -> "EvaluationDatasetV1":
        data = _mapping(value, _DATASET_FIELDS)
        if data["schema_version"] != "PrivateEvaluationDatasetV1":
            _invalid()
        raw_cases = data["cases"]
        if type(raw_cases) is not list or not 200 <= len(raw_cases) <= 1000:
            raise PrivateEvaluationError("dataset_case_count_invalid")
        cases = tuple(EvaluationCaseV1.from_mapping(item) for item in raw_cases)
        if len({case.case_id for case in cases}) != len(cases):
            _invalid()
        _validate_coverage(cases)
        return cls("PrivateEvaluationDatasetV1", _uuid4(data["dataset_namespace"]), cases)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "dataset_namespace": self.dataset_namespace,
            "cases": [case.to_mapping() for case in self.cases],
        }


def _approvals(value: object, revision: int) -> CaseApprovalsV1:
    data = _mapping(value, _APPROVAL_FIELDS)
    business = _approval(data["business"], "business", revision)
    privacy = _approval(data["privacy"], "privacy_security", revision)
    pair = None if data["pro_pair"] is None else _approval(data["pro_pair"], "pro_pair", revision)
    if business.actor_ref == privacy.actor_ref:
        _invalid()
    return CaseApprovalsV1(business, privacy, pair)


def _approval(value: object, role: str, revision: int) -> ApprovalV1:
    data = _mapping(value, _APPROVAL_VALUE_FIELDS)
    case_revision = _positive_int(data["case_revision"])
    if data["role"] != role or case_revision != revision:
        _invalid()
    approved_at = _text(data["approved_at"], 40)
    try:
        parsed = datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError:
        _invalid()
    if parsed.tzinfo is None:
        _invalid()
    return ApprovalV1(_uuid4(data["actor_ref"]), role, approved_at, case_revision)


def _stratum(value: object) -> EvaluationStratumV1:
    data = _mapping(value, _STRATUM_FIELDS)
    risk = _enum(data["primary_risk"], RISK_TYPES | {"none"})
    return EvaluationStratumV1(
        _enum(data["category"], CATEGORIES), _enum(data["language"], LANGUAGES),
        _enum(data["direction"], DIRECTIONS), risk,
    )


def _email(value: object) -> DeidentifiedEmailV1:
    data = _mapping(value, _EMAIL_FIELDS)
    attachments = _list(data["attachments"], 8)
    parsed_attachments = tuple(_attachment(item) for item in attachments)
    return DeidentifiedEmailV1(
        _safe_text(data["subject"], 2_000), _safe_text(data["sender"], 512),
        _safe_text_tuple(data["recipients"], 8, 512),
        _safe_text_tuple(data["cc"], 8, 512),
        _safe_text(data["sent_at"], 200), _safe_text(data["thread_text"], 20_000),
        parsed_attachments,
    )


def _attachment(value: object) -> DeidentifiedAttachmentV1:
    data = _mapping(value, _ATTACHMENT_FIELDS)
    return DeidentifiedAttachmentV1(
        _enum(data["kind"], ATTACHMENT_KINDS), _safe_text(data["text"], 6_000)
    )


def _expected(value: object, stratum: EvaluationStratumV1) -> ExpectedResultV1:
    data = _mapping(value, _EXPECTED_FIELDS)
    category = _enum(data["category"], CATEGORIES)
    risks = _enum_tuple(data["mandatory_risk_types"], RISK_TYPES, len(RISK_TYPES))
    actions = _enum_tuple(data["required_action_types"], ACTION_TYPES, len(ACTION_TYPES))
    if category != stratum.category or (
        stratum.primary_risk != "none" and stratum.primary_risk not in risks
    ):
        _invalid()
    return ExpectedResultV1(category, risks, actions)


def _validate_coverage(cases: tuple[EvaluationCaseV1, ...]) -> None:
    strata = tuple(case.stratum for case in cases)
    if (
        {item.category for item in strata} != CATEGORIES
        or {item.language for item in strata} != LANGUAGES
        or {item.direction for item in strata} != DIRECTIONS
        or {item.primary_risk for item in strata} != RISK_TYPES | {"none"}
        or not any(case.expected.mandatory_risk_types for case in cases)
        or not any(case.expected.required_action_types for case in cases)
    ):
        raise PrivateEvaluationError("dataset_strata_incomplete")
