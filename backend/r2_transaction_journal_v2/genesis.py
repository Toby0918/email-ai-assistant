"""Canonical final-master and evidence-bound journal genesis."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from .errors import JournalGenesisError


_TYPE = "R2JournalGenesisV2"
_FIELDS = (
    "genesis_type",
    "binding_fingerprint",
    "final_master_binding_fingerprint",
    "final_commit_oid",
    "final_tree_oid",
    "operation_fingerprint",
    "production_role_registry_fingerprint",
    "public_key_registry_fingerprint",
    "reviewed_evidence_fingerprint",
    "evidence_identity_fingerprint",
    "package_fingerprint",
    "manifest_fingerprint",
    "journal_owner_fingerprint",
    "genesis_nonce",
    "pre_genesis_head_fingerprint",
    "authority_claim",
    "record_sequence",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2JournalGenesisV2:
    genesis_type: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    production_role_registry_fingerprint: str = field(repr=False)
    public_key_registry_fingerprint: str = field(repr=False)
    reviewed_evidence_fingerprint: str = field(repr=False)
    evidence_identity_fingerprint: str = field(repr=False)
    package_fingerprint: str = field(repr=False)
    manifest_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    genesis_nonce: str = field(repr=False)
    pre_genesis_head_fingerprint: str = field(repr=False)
    authority_claim: DurableAuthorityClaimV2 = field(repr=False)
    record_sequence: int
    head_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2JournalGenesisV2 requires create()")

    @classmethod
    def create(cls, **values) -> R2JournalGenesisV2:
        body = _genesis_body(**values)
        return _construct(body, values["authority_claim"])

    @classmethod
    def from_json(cls, payload: object, *, binding: object) -> R2JournalGenesisV2:
        try:
            source = strict_json_object(payload)
            if (
                canonical_json(source) != payload
                or set(source) != {*_FIELDS, "head_fingerprint"}
            ):
                raise JournalGenesisError()
            claim = DurableAuthorityClaimV2.from_json(
                canonical_json(source["authority_claim"]),
                binding=binding,
            )
            body = _genesis_body(
                binding=binding,
                reviewed_evidence_fingerprint=source["reviewed_evidence_fingerprint"],
                evidence_identity_fingerprint=source["evidence_identity_fingerprint"],
                package_fingerprint=source["package_fingerprint"],
                manifest_fingerprint=source["manifest_fingerprint"],
                journal_owner_fingerprint=source["journal_owner_fingerprint"],
                genesis_nonce=source["genesis_nonce"],
                pre_genesis_head_fingerprint=source["pre_genesis_head_fingerprint"],
                authority_claim=claim,
            )
            if any(source[name] != body[name] for name in _FIELDS):
                raise JournalGenesisError()
            if source["head_fingerprint"] != fingerprint("r2-journal-genesis-v2", body):
                raise JournalGenesisError()
            return _construct(body, claim)
        except JournalGenesisError:
            raise
        except Exception:
            raise JournalGenesisError() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in _FIELDS}
        body["authority_claim"] = self.authority_claim.to_mapping()
        return {**body, "head_fingerprint": self.head_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _genesis_body(*, binding, authority_claim, **fingerprints):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(authority_claim) is not DurableAuthorityClaimV2
        or authority_claim.binding_fingerprint != binding.binding_fingerprint
        or authority_claim.command is not ProductionCommandV2.EVIDENCE_PUBLICATION
        or authority_claim.claim_sequence != 1
        or set(fingerprints) != {
            "reviewed_evidence_fingerprint",
            "evidence_identity_fingerprint",
            "package_fingerprint",
            "manifest_fingerprint",
            "journal_owner_fingerprint",
            "genesis_nonce",
            "pre_genesis_head_fingerprint",
        }
        or not all(is_fingerprint(value) for value in fingerprints.values())
        or authority_claim.journal_owner_fingerprint
        != fingerprints["journal_owner_fingerprint"]
        or authority_claim.prior_journal_head_fingerprint
        != fingerprints["pre_genesis_head_fingerprint"]
        or authority_claim.action_fingerprint
        != production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint=fingerprints["reviewed_evidence_fingerprint"],
        )
    ):
        raise JournalGenesisError()
    return {
        "genesis_type": _TYPE,
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "operation_fingerprint": binding.operation_fingerprint,
        "production_role_registry_fingerprint": binding.production_role_registry_fingerprint,
        "public_key_registry_fingerprint": binding.public_key_registry_fingerprint,
        **fingerprints,
        "authority_claim": authority_claim.to_mapping(),
        "record_sequence": 0,
    }


def _construct(body, claim):
    value = object.__new__(R2JournalGenesisV2)
    for name in _FIELDS:
        object.__setattr__(
            value,
            name,
            claim if name == "authority_claim" else body[name],
        )
    object.__setattr__(
        value,
        "head_fingerprint",
        fingerprint("r2-journal-genesis-v2", body),
    )
    return value
