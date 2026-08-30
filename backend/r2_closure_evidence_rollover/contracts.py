"""Canonical, content-free contracts for historical closure evidence rollover."""

from __future__ import annotations

from enum import Enum

from backend.r2_solo_maintainer_closure._canonical import (
    CanonicalValue,
    allocate_value,
    canonical_json,
    fingerprint,
    is_fingerprint,
    is_git_oid,
    is_nonnegative_int,
    strict_object,
)

ROLLOVER_WINDOW_SECONDS = 300
class RolloverErrorCode(str, Enum):
    INVALID = "R2_CLOSURE_EVIDENCE_ROLLOVER_INVALID"
    FINGERPRINT_REJECTED = "R2_CLOSURE_EVIDENCE_ROLLOVER_FINGERPRINT_REJECTED"
    STALE = "R2_CLOSURE_EVIDENCE_ROLLOVER_STALE"
    STATE_REJECTED = "R2_CLOSURE_EVIDENCE_ROLLOVER_STATE_REJECTED"
    PUBLICATION_REJECTED = "R2_CLOSURE_EVIDENCE_ROLLOVER_PUBLICATION_REJECTED"

class ClosureEvidenceRolloverError(ValueError):
    """One fixed error code without source-derived detail."""

    def __init__(self, code: RolloverErrorCode = RolloverErrorCode.INVALID) -> None:
        if type(code) is not RolloverErrorCode:
            code = RolloverErrorCode.INVALID
        self.code = code
        super().__init__(code.value)

_STATE_FIELDS = (
    "state_type", "current_commit_oid", "current_tree_oid",
    "historical_commit_oid", "historical_tree_oid", "manifest_fingerprint",
    "receipt_fingerprint", "manifest_sha256", "receipt_sha256",
    "evidence_identity_fingerprint", "historical_target_name",
    "parent_identity_fingerprint", "parent_dacl_sha256",
)

class ClosureEvidenceRolloverStateV1(CanonicalValue):
    @classmethod
    def create(cls, *, repository: object, evidence: object):
        body = {
            "state_type": "ClosureEvidenceRolloverStateV1",
            "current_commit_oid": getattr(repository, "current_commit_oid", None),
            "current_tree_oid": getattr(repository, "current_tree_oid", None),
            "historical_commit_oid": getattr(evidence, "historical_commit_oid", None),
            "historical_tree_oid": getattr(evidence, "historical_tree_oid", None),
            "manifest_fingerprint": getattr(evidence, "manifest_fingerprint", None),
            "receipt_fingerprint": getattr(evidence, "receipt_fingerprint", None),
            "manifest_sha256": getattr(evidence, "manifest_sha256", None),
            "receipt_sha256": getattr(evidence, "receipt_sha256", None),
            "evidence_identity_fingerprint": getattr(
                evidence, "evidence_identity_fingerprint", None
            ),
            "parent_identity_fingerprint": getattr(
                evidence, "parent_identity_fingerprint", None
            ),
            "parent_dacl_sha256": getattr(evidence, "parent_dacl_sha256", None),
            "historical_target_name": getattr(evidence, "historical_target_name", None),
        }
        _validate_state_body(body)
        if (
            body["historical_commit_oid"]
            != getattr(repository, "historical_commit_oid", None)
            or body["historical_tree_oid"]
            != getattr(repository, "historical_tree_oid", None)
        ):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
        return _with_fingerprint(
            cls, body, "state_fingerprint", "r2-closure-evidence-rollover-state-v1"
        )

    @classmethod
    def from_json(cls, payload: object):
        return _parse(
            cls,
            payload,
            _STATE_FIELDS,
            "state_fingerprint",
            "r2-closure-evidence-rollover-state-v1",
            _validate_state_body,
        )


_CANDIDATE_FIELDS = (
    "candidate_type", "status", "state", "state_fingerprint",
    "historical_target_name", "prepared_at_epoch", "expires_at_epoch",
    "confirmation_window_seconds", "approval_count", "execution_authority_count",
    "issue39_authority_count",
)


class ClosureEvidenceRolloverCandidateV1(CanonicalValue):
    @classmethod
    def create(cls, state: ClosureEvidenceRolloverStateV1, prepared_at_epoch: int):
        if type(state) is not ClosureEvidenceRolloverStateV1:
            raise ClosureEvidenceRolloverError()
        body = {
            "candidate_type": "ClosureEvidenceRolloverCandidateV1",
            "status": "AWAITING_CLOSURE_EVIDENCE_ROLLOVER",
            "state": state.to_mapping(),
            "state_fingerprint": state.state_fingerprint,
            "historical_target_name": state.historical_target_name,
            "prepared_at_epoch": prepared_at_epoch,
            "expires_at_epoch": prepared_at_epoch + ROLLOVER_WINDOW_SECONDS,
            "confirmation_window_seconds": ROLLOVER_WINDOW_SECONDS,
            "approval_count": 0,
            "execution_authority_count": 0,
            "issue39_authority_count": 0,
        }
        _validate_candidate_body(body)
        return _with_fingerprint(
            cls,
            body,
            "candidate_fingerprint",
            "r2-closure-evidence-rollover-candidate-v1",
        )

    @classmethod
    def from_json(cls, payload: object):
        return _parse(
            cls,
            payload,
            _CANDIDATE_FIELDS,
            "candidate_fingerprint",
            "r2-closure-evidence-rollover-candidate-v1",
            _validate_candidate_body,
        )

    @property
    def state_value(self) -> ClosureEvidenceRolloverStateV1:
        return ClosureEvidenceRolloverStateV1.from_json(canonical_json(self.state))


_RECEIPT_FIELDS = (
    "receipt_type", "status", "candidate_fingerprint", "state_fingerprint",
    "current_commit_oid", "historical_commit_oid", "manifest_fingerprint",
    "receipt_fingerprint", "historical_target_name", "completed_at_epoch",
    "retained_count", "rename_count", "copy_count", "deletion_count",
    "overwrite_count", "cleanup_count", "approval_count",
    "execution_authority_count", "issue39_authority_count",
)


class ClosureEvidenceRolloverReceiptV1(CanonicalValue):
    @classmethod
    def create(cls, candidate: ClosureEvidenceRolloverCandidateV1, completed: int):
        if type(candidate) is not ClosureEvidenceRolloverCandidateV1:
            raise ClosureEvidenceRolloverError()
        state = candidate.state_value
        body = {
            "receipt_type": "ClosureEvidenceRolloverReceiptV1",
            "status": "HISTORICAL_CLOSURE_EVIDENCE_RETAINED",
            "candidate_fingerprint": candidate.candidate_fingerprint,
            "state_fingerprint": state.state_fingerprint,
            "current_commit_oid": state.current_commit_oid,
            "historical_commit_oid": state.historical_commit_oid,
            "manifest_fingerprint": state.manifest_fingerprint,
            "receipt_fingerprint": state.receipt_fingerprint,
            "historical_target_name": state.historical_target_name,
            "completed_at_epoch": completed,
            "retained_count": 1,
            "rename_count": 1,
            "copy_count": 0,
            "deletion_count": 0,
            "overwrite_count": 0,
            "cleanup_count": 0,
            "approval_count": 0,
            "execution_authority_count": 0,
            "issue39_authority_count": 0,
        }
        _validate_receipt_body(body)
        return _with_fingerprint(
            cls, body, "rollover_fingerprint", "r2-closure-evidence-rollover-receipt-v1"
        )

    @classmethod
    def from_json(cls, payload: object):
        return _parse(
            cls,
            payload,
            _RECEIPT_FIELDS,
            "rollover_fingerprint",
            "r2-closure-evidence-rollover-receipt-v1",
            _validate_receipt_body,
        )


def _validate_state_body(body: dict[str, object]) -> None:
    fingerprints = (
        "manifest_fingerprint", "receipt_fingerprint", "manifest_sha256",
        "receipt_sha256", "evidence_identity_fingerprint",
        "parent_identity_fingerprint", "parent_dacl_sha256",
    )
    expected_target = _historical_target(
        body.get("historical_commit_oid"), body.get("manifest_fingerprint")
    )
    if (
        set(body) != set(_STATE_FIELDS)
        or body.get("state_type") != "ClosureEvidenceRolloverStateV1"
        or not all(
            is_git_oid(body.get(name))
            for name in (
                "current_commit_oid", "current_tree_oid", "historical_commit_oid",
                "historical_tree_oid",
            )
        )
        or not all(is_fingerprint(body.get(name)) for name in fingerprints)
        or body.get("current_commit_oid") == body.get("historical_commit_oid")
        or body.get("historical_target_name") != expected_target
    ):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)


def _validate_candidate_body(body: dict[str, object]) -> None:
    if set(body) != set(_CANDIDATE_FIELDS):
        raise ClosureEvidenceRolloverError()
    state = ClosureEvidenceRolloverStateV1.from_json(canonical_json(body.get("state")))
    prepared = body.get("prepared_at_epoch")
    expected = (
        "ClosureEvidenceRolloverCandidateV1",
        "AWAITING_CLOSURE_EVIDENCE_ROLLOVER",
        state.state_fingerprint,
        state.historical_target_name,
        ROLLOVER_WINDOW_SECONDS,
        0,
        0,
        0,
    )
    observed = (
        body.get("candidate_type"), body.get("status"), body.get("state_fingerprint"),
        body.get("historical_target_name"), body.get("confirmation_window_seconds"),
        body.get("approval_count"), body.get("execution_authority_count"),
        body.get("issue39_authority_count"),
    )
    if (
        observed != expected
        or not is_nonnegative_int(prepared)
        or body.get("expires_at_epoch") != prepared + ROLLOVER_WINDOW_SECONDS
    ):
        raise ClosureEvidenceRolloverError()

def _validate_receipt_body(body: dict[str, object]) -> None:
    fingerprints = (
        "candidate_fingerprint", "state_fingerprint", "manifest_fingerprint",
        "receipt_fingerprint",
    )
    counts = (
        body.get("retained_count"), body.get("rename_count"), body.get("copy_count"),
        body.get("deletion_count"), body.get("overwrite_count"),
        body.get("cleanup_count"), body.get("approval_count"),
        body.get("execution_authority_count"), body.get("issue39_authority_count"),
    )
    if (
        set(body) != set(_RECEIPT_FIELDS)
        or body.get("receipt_type") != "ClosureEvidenceRolloverReceiptV1"
        or body.get("status") != "HISTORICAL_CLOSURE_EVIDENCE_RETAINED"
        or not all(is_fingerprint(body.get(name)) for name in fingerprints)
        or not is_git_oid(body.get("current_commit_oid"))
        or not is_git_oid(body.get("historical_commit_oid"))
        or body.get("historical_target_name")
        != _historical_target(
            body.get("historical_commit_oid"), body.get("manifest_fingerprint")
        )
        or not is_nonnegative_int(body.get("completed_at_epoch"))
        or counts != (1, 1, 0, 0, 0, 0, 0, 0, 0)
    ):
        raise ClosureEvidenceRolloverError()


def _historical_target(commit: object, manifest: object) -> str:
    if not is_git_oid(commit) or not is_fingerprint(manifest):
        return ""
    return f"r2-solo-maintainer-closure-v1.historical-{commit[:16]}-{manifest[:16]}"


def _with_fingerprint(kind, body, field: str, domain: str):
    mapping = dict(body)
    mapping[field] = fingerprint(domain, body)
    return allocate_value(kind, mapping)


def _parse(kind, payload, body_fields, field: str, domain: str, validator):
    try:
        mapping = strict_object(payload)
        if set(mapping) != set(body_fields) | {field}:
            raise ClosureEvidenceRolloverError()
        body = {name: mapping[name] for name in body_fields}
        validator(body)
        if mapping[field] != fingerprint(domain, body):
            raise ClosureEvidenceRolloverError()
        return allocate_value(kind, mapping)
    except ClosureEvidenceRolloverError:
        raise
    except Exception:
        raise ClosureEvidenceRolloverError() from None
