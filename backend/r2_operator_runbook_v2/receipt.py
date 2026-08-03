"""Verification receipt for exact generated runbook semantics."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_production_binding import ApprovedCutoverBindingV2
from backend.r2_retention_ledger_v2 import R2RetentionProofV2
from backend.r2_transaction_journal_v2._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object

from .errors import OperatorRunbookError
from .render import render_r2_operator_runbook_v2, runbook_document_fingerprint_v2
from .state_machine import operator_package_semantics_fingerprint_v2
from .review_registry import (
    blocker_resolution_fingerprint_v2,
    decision_registry_fingerprint_v2,
    issue38_decision_registry_v2,
    r1_blocker_resolution_registry_v2,
)


class RunbookVerificationStatusV2(str, Enum):
    RUNBOOK_SEMANTICS_VERIFIED = "RUNBOOK_SEMANTICS_VERIFIED"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2OperatorRunbookReceiptV2:
    receipt_type: str
    status: RunbookVerificationStatusV2
    binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    package_semantics_fingerprint: str = field(repr=False)
    retention_proof_fingerprint: str = field(repr=False)
    decision_registry_fingerprint: str = field(repr=False)
    blocker_resolution_fingerprint: str = field(repr=False)
    catalog_command_count: int
    state_phase_count: int
    decision_count: int
    r1_blocker_class_count: int
    historical_command_count: int
    deletion_capability_count: int
    mixed_binding_count: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2OperatorRunbookReceiptV2 requires create()")

    @classmethod
    def create(cls, **values):
        try:
            _require(values)
            binding, retention = values["binding"], values["retention_proof"]
            body = {"receipt_type": "R2OperatorRunbookReceiptV2", "status": RunbookVerificationStatusV2.RUNBOOK_SEMANTICS_VERIFIED.value, "binding_fingerprint": binding.binding_fingerprint, "final_commit_oid": binding.final_commit_oid, "final_tree_oid": binding.final_tree_oid, "source_package_fingerprint": binding.source_package_fingerprint, "runbook_fingerprint": binding.runbook_fingerprint, "package_semantics_fingerprint": values["package_semantics_fingerprint"], "retention_proof_fingerprint": retention.proof_fingerprint, "decision_registry_fingerprint": decision_registry_fingerprint_v2(), "blocker_resolution_fingerprint": blocker_resolution_fingerprint_v2(), "catalog_command_count": 10, "state_phase_count": 8, "decision_count": len(issue38_decision_registry_v2()), "r1_blocker_class_count": len(r1_blocker_resolution_registry_v2()), "historical_command_count": 0, "deletion_capability_count": 0, "mixed_binding_count": 0}
            return _construct(body)
        except OperatorRunbookError:
            raise
        except Exception:
            raise OperatorRunbookError() from None

    @classmethod
    def from_json(cls, payload, **values):
        try:
            source = strict_json_object(payload)
            result = cls.create(**values)
            if canonical_json(source) != payload or source != result.to_mapping():
                raise OperatorRunbookError()
            return result
        except OperatorRunbookError:
            raise
        except Exception:
            raise OperatorRunbookError() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in self.__dataclass_fields__ if name != "receipt_fingerprint"}
        body["status"] = self.status.value
        return {**body, "receipt_fingerprint": self.receipt_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _require(values):
    required = {"binding", "retention_proof", "document", "source_package_fingerprint", "package_semantics_fingerprint"}
    if set(values) != required:
        raise OperatorRunbookError()
    binding, retention = values["binding"], values["retention_proof"]
    if type(binding) is not ApprovedCutoverBindingV2 or type(retention) is not R2RetentionProofV2 or retention.binding_fingerprint != binding.binding_fingerprint:
        raise OperatorRunbookError()
    if values["document"] != render_r2_operator_runbook_v2() or binding.runbook_fingerprint != runbook_document_fingerprint_v2() or values["source_package_fingerprint"] != binding.source_package_fingerprint or values["package_semantics_fingerprint"] != operator_package_semantics_fingerprint_v2() or not is_fingerprint(values["source_package_fingerprint"]):
        raise OperatorRunbookError()
    if any(getattr(retention, name) != 0 for name in ("untracked_artifact_count", "deletion_capability_count", "overwrite_capability_count", "prune_capability_count", "automatic_expiry_capability_count", "private_payload_field_count")):
        raise OperatorRunbookError()


def _construct(body):
    value = object.__new__(R2OperatorRunbookReceiptV2)
    for name, item in body.items():
        object.__setattr__(value, name, RunbookVerificationStatusV2(item) if name == "status" else item)
    object.__setattr__(value, "receipt_fingerprint", fingerprint("r2-operator-runbook-receipt-v2", body))
    return value
