"""Exact V2 production dispatcher for the six read-only preflight verbs."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from backend.r2_operator_process.production_v2 import verify_production_authority_v2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    ProductionCommandV2,
)

from .contracts import PREFLIGHT_ACKNOWLEDGEMENT


PREFLIGHT_PRODUCTION_VERBS_V2 = {
    "current-topology": ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
    "host-baseline": ProductionCommandV2.HOST_BASELINE,
    "evidence-review": ProductionCommandV2.EVIDENCE_REVIEW,
    "evidence-verification": ProductionCommandV2.EVIDENCE_VERIFICATION,
    "final-audit-readiness": ProductionCommandV2.FINAL_AUDIT_READINESS,
    "recovery-inspection": ProductionCommandV2.RECOVERY_INSPECTION,
}


class PreflightProductionStatusV2(str, Enum):
    COMPLETED = "PREFLIGHT_COMPLETE"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_ENVELOPE = "BLOCKED_ENVELOPE"
    BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
    BLOCKED_COMPOSITION = "BLOCKED_COMPOSITION"
    DORMANT_NO_EXTERNAL_ISSUER = "DORMANT_NO_EXTERNAL_ISSUER"


@dataclass(frozen=True, slots=True)
class PreflightProductionResultV2:
    status: PreflightProductionStatusV2
    accepted: int
    rejected: int
    read_operations: int

    def counts(self):
        return self.accepted, self.rejected, self.read_operations

    def to_mapping(self):
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "read_operations": self.read_operations,
        }


@dataclass(frozen=True, slots=True, repr=False)
class PreflightReadCompletionV2:
    binding_fingerprint: str = field(repr=False)
    command: ProductionCommandV2
    claim_fingerprint: str = field(repr=False)
    read_operations: int


@dataclass(frozen=True, slots=True, repr=False)
class PreflightProductionRolesV2:
    current_topology_preflight: object = field(repr=False)
    host_baseline: object = field(repr=False)
    evidence_review: object = field(repr=False)
    evidence_verification: object = field(repr=False)
    final_audit_readiness: object = field(repr=False)
    recovery_inspection: object = field(repr=False)

    def __post_init__(self):
        if not all(callable(value) for value in self._values()):
            raise TypeError("R2_PREFLIGHT_PRODUCTION_ROLES_INVALID")

    def select(self, command):
        if type(command) is not ProductionCommandV2:
            raise TypeError("R2_PREFLIGHT_PRODUCTION_ROLES_INVALID")
        return dict(zip(PREFLIGHT_PRODUCTION_VERBS_V2.values(), self._values()))[
            command
        ]

    def _values(self):
        return (
            self.current_topology_preflight,
            self.host_baseline,
            self.evidence_review,
            self.evidence_verification,
            self.final_audit_readiness,
            self.recovery_inspection,
        )


def run_preflight_production_v2(
    *,
    argv,
    terminal,
    binding,
    roles,
    durable_claims,
    expected_prior_journal_head_fingerprint,
    observed_at_epoch,
):
    if not _valid_argv(argv):
        return _blocked(PreflightProductionStatusV2.BLOCKED_COMMAND)
    ingress = _read_ingress(terminal)
    if type(ingress) is PreflightProductionStatusV2:
        return _blocked(ingress)
    command = PREFLIGHT_PRODUCTION_VERBS_V2[argv[0]]
    try:
        observed = observed_at_epoch()
        claim = verify_production_authority_v2(
            ingress,
            binding=binding,
            expected_command=command,
            durable_claims=durable_claims,
            expected_prior_journal_head_fingerprint=(
                expected_prior_journal_head_fingerprint
            ),
            observed_at_epoch=observed,
        )
    except Exception:
        return _blocked(PreflightProductionStatusV2.BLOCKED_AUTHORITY)
    return _invoke_role(binding, roles, command, claim)


def dormant_preflight_production_v2(*, argv):
    if not _valid_argv(argv):
        return _blocked(PreflightProductionStatusV2.BLOCKED_COMMAND)
    return PreflightProductionResultV2(
        PreflightProductionStatusV2.DORMANT_NO_EXTERNAL_ISSUER,
        0,
        0,
        0,
    )


def complete_preflight_read_v2(binding, claim):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(claim) is not DurableAuthorityClaimV2
        or claim.binding_fingerprint != binding.binding_fingerprint
    ):
        raise TypeError("R2_PREFLIGHT_READ_COMPLETION_INVALID")
    return PreflightReadCompletionV2(
        binding.binding_fingerprint,
        claim.command,
        claim.claim_fingerprint,
        1,
    )


def _invoke_role(binding, roles, command, claim):
    try:
        if type(roles) is not PreflightProductionRolesV2:
            raise TypeError
        completion = roles.select(command)(binding, claim)
        if (
            type(completion) is not PreflightReadCompletionV2
            or completion.binding_fingerprint != binding.binding_fingerprint
            or completion.command is not command
            or completion.claim_fingerprint != claim.claim_fingerprint
            or completion.read_operations != 1
        ):
            raise TypeError
    except Exception:
        return _blocked(PreflightProductionStatusV2.BLOCKED_COMPOSITION)
    return PreflightProductionResultV2(
        PreflightProductionStatusV2.COMPLETED,
        1,
        0,
        1,
    )


def _read_ingress(terminal):
    try:
        if terminal.tty_state() != (True, True, True):
            return PreflightProductionStatusV2.BLOCKED_TTY
        if terminal.read_acknowledgement() != PREFLIGHT_ACKNOWLEDGEMENT:
            return PreflightProductionStatusV2.BLOCKED_ACKNOWLEDGEMENT
        envelope = terminal.read_hidden_envelope(65_536)
        if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
            return PreflightProductionStatusV2.BLOCKED_ENVELOPE
        return envelope
    except Exception:
        return PreflightProductionStatusV2.BLOCKED_ENVELOPE


def _valid_argv(argv):
    return (
        type(argv) is tuple
        and len(argv) == 1
        and type(argv[0]) is str
        and argv[0] in PREFLIGHT_PRODUCTION_VERBS_V2
    )


def _blocked(status):
    return PreflightProductionResultV2(status, 0, 1, 0)
