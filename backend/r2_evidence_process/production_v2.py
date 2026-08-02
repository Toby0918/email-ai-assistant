"""Single-verb V2 evidence publication and journal-genesis dispatcher."""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass, field
from enum import Enum

from backend.r2_operator_process import verify_production_authority_v2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)
from backend.r2_production_binding.catalog import (
    OperatorSurfaceV2,
    executable_verb_map_v2,
)
from backend.r2_transaction_journal_v2 import R2JournalGenesisV2

from .contracts import EVIDENCE_ACKNOWLEDGEMENT


EVIDENCE_PRODUCTION_VERBS_V2 = executable_verb_map_v2(OperatorSurfaceV2.EVIDENCE)


class EvidenceProductionStatusV2(str, Enum):
    PUBLISHED = "EVIDENCE_PUBLISHED"
    BLOCKED_COMMAND = "BLOCKED_COMMAND"
    BLOCKED_TTY = "BLOCKED_TTY"
    BLOCKED_ACKNOWLEDGEMENT = "BLOCKED_ACKNOWLEDGEMENT"
    BLOCKED_ENVELOPE = "BLOCKED_ENVELOPE"
    BLOCKED_AUTHORITY = "BLOCKED_AUTHORITY"
    BLOCKED_PUBLICATION = "BLOCKED_PUBLICATION"
    BLOCKED_GENESIS = "BLOCKED_GENESIS"
    DORMANT_NO_EXTERNAL_ISSUER = "DORMANT_NO_EXTERNAL_ISSUER"


@dataclass(frozen=True, slots=True)
class EvidenceProductionResultV2:
    status: EvidenceProductionStatusV2
    accepted: int
    rejected: int
    published: int
    evidence_identity_fingerprint: str = field(default="", repr=False)
    genesis_head_fingerprint: str = field(default="", repr=False)
    genesis: object = field(default=None, repr=False)

    def counts(self):
        return self.accepted, self.rejected, self.published

    def to_mapping(self):
        return {
            "status": self.status.value,
            "accepted": self.accepted,
            "rejected": self.rejected,
            "published": self.published,
            "evidence_identity_fingerprint": self.evidence_identity_fingerprint,
            "genesis_head_fingerprint": self.genesis_head_fingerprint,
        }


@dataclass(frozen=True, slots=True, repr=False)
class ReviewedEvidencePublicationV2:
    binding_fingerprint: str = field(repr=False)
    authority_claim_fingerprint: str = field(repr=False)
    reviewed_evidence_fingerprint: str = field(repr=False)
    evidence_identity_fingerprint: str = field(repr=False)
    package_fingerprint: str = field(repr=False)
    manifest_fingerprint: str = field(repr=False)
    publication_fingerprint: str = field(repr=False)
    created: int


@dataclass(frozen=True, slots=True, repr=False)
class EvidenceProductionRoleV2:
    publish_reviewed_evidence: object = field(repr=False)

    def __post_init__(self):
        if not callable(self.publish_reviewed_evidence):
            raise TypeError("R2_EVIDENCE_PRODUCTION_ROLE_INVALID")


def run_evidence_production_v2(
    *,
    argv,
    terminal,
    binding,
    role,
    reviewed_evidence_fingerprint,
    durable_claims,
    expected_prior_journal_head_fingerprint,
    observed_at_epoch,
    journal_owner_fingerprint,
    genesis_nonce,
):
    if not _valid_argv(argv):
        return _blocked(EvidenceProductionStatusV2.BLOCKED_COMMAND)
    ingress = _read_ingress(terminal)
    if type(ingress) is EvidenceProductionStatusV2:
        return _blocked(ingress)
    try:
        action = production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint=reviewed_evidence_fingerprint,
        )
        claim = verify_production_authority_v2(
            ingress,
            binding=binding,
            expected_command=ProductionCommandV2.EVIDENCE_PUBLICATION,
            durable_claims=durable_claims,
            expected_prior_journal_head_fingerprint=(
                expected_prior_journal_head_fingerprint
            ),
            observed_at_epoch=observed_at_epoch(),
            expected_action_fingerprint=action,
        )
    except Exception:
        return _blocked(EvidenceProductionStatusV2.BLOCKED_AUTHORITY)
    return _publish_and_bind_genesis(
        binding,
        role,
        claim,
        reviewed_evidence_fingerprint,
        journal_owner_fingerprint,
        genesis_nonce,
        expected_prior_journal_head_fingerprint,
    )


def dormant_evidence_production_v2(*, argv):
    if not _valid_argv(argv):
        return _blocked(EvidenceProductionStatusV2.BLOCKED_COMMAND)
    return EvidenceProductionResultV2(
        EvidenceProductionStatusV2.DORMANT_NO_EXTERNAL_ISSUER,
        0,
        0,
        0,
    )


def main(*, argv=None):
    arguments = tuple(sys.argv[1:]) if argv is None else argv
    result = dormant_evidence_production_v2(argv=arguments)
    sys.stdout.write(
        f"{result.status.value} accepted={result.accepted} "
        f"rejected={result.rejected} published={result.published}\n"
    )
    sys.stdout.flush()
    return 2 if result.status is EvidenceProductionStatusV2.BLOCKED_COMMAND else 0


def complete_reviewed_evidence_publication_v2(
    *,
    binding,
    claim,
    reviewed_evidence_fingerprint,
    evidence_identity_fingerprint,
    package_fingerprint,
    manifest_fingerprint,
):
    values = {
        "binding_fingerprint": binding.binding_fingerprint,
        "authority_claim_fingerprint": claim.claim_fingerprint,
        "reviewed_evidence_fingerprint": reviewed_evidence_fingerprint,
        "evidence_identity_fingerprint": evidence_identity_fingerprint,
        "package_fingerprint": package_fingerprint,
        "manifest_fingerprint": manifest_fingerprint,
        "created": 1,
    }
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(claim) is not DurableAuthorityClaimV2
        or claim.binding_fingerprint != binding.binding_fingerprint
        or claim.command is not ProductionCommandV2.EVIDENCE_PUBLICATION
        or any(not _is_fingerprint(value) for value in tuple(values.values())[:-1])
    ):
        raise TypeError("R2_REVIEWED_EVIDENCE_PUBLICATION_INVALID")
    publication = _fingerprint("r2-reviewed-evidence-publication-v2", values)
    return ReviewedEvidencePublicationV2(**values, publication_fingerprint=publication)


def _publish_and_bind_genesis(binding, role, claim, review, owner, nonce, prior_head):
    try:
        if type(role) is not EvidenceProductionRoleV2:
            raise TypeError
        publication = role.publish_reviewed_evidence(binding, claim)
        if (
            type(publication) is not ReviewedEvidencePublicationV2
            or publication.binding_fingerprint != binding.binding_fingerprint
            or publication.authority_claim_fingerprint != claim.claim_fingerprint
            or publication.reviewed_evidence_fingerprint != review
            or publication.created != 1
        ):
            raise TypeError
    except Exception:
        return _blocked(EvidenceProductionStatusV2.BLOCKED_PUBLICATION)
    try:
        genesis = R2JournalGenesisV2.create(
            binding=binding,
            reviewed_evidence_fingerprint=review,
            evidence_identity_fingerprint=publication.evidence_identity_fingerprint,
            package_fingerprint=publication.package_fingerprint,
            manifest_fingerprint=publication.manifest_fingerprint,
            journal_owner_fingerprint=owner,
            genesis_nonce=nonce,
            pre_genesis_head_fingerprint=prior_head,
            authority_claim=claim,
        )
    except Exception:
        return _blocked(EvidenceProductionStatusV2.BLOCKED_GENESIS)
    return EvidenceProductionResultV2(
        EvidenceProductionStatusV2.PUBLISHED,
        1,
        0,
        1,
        genesis.evidence_identity_fingerprint,
        genesis.head_fingerprint,
        genesis,
    )


def _read_ingress(terminal):
    try:
        if terminal.tty_state() != (True, True, True):
            return EvidenceProductionStatusV2.BLOCKED_TTY
        if terminal.read_acknowledgement() != EVIDENCE_ACKNOWLEDGEMENT:
            return EvidenceProductionStatusV2.BLOCKED_ACKNOWLEDGEMENT
        envelope = terminal.read_hidden_envelope(65_536)
        if type(envelope) is not str or not 1 <= len(envelope) <= 65_536:
            return EvidenceProductionStatusV2.BLOCKED_ENVELOPE
        return envelope
    except Exception:
        return EvidenceProductionStatusV2.BLOCKED_ENVELOPE


def _blocked(status):
    return EvidenceProductionResultV2(status, 0, 1, 0)


def _valid_argv(argv):
    return (
        type(argv) is tuple
        and len(argv) == 1
        and type(argv[0]) is str
        and argv[0] in EVIDENCE_PRODUCTION_VERBS_V2
    )


def _is_fingerprint(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _fingerprint(domain, value):
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()
