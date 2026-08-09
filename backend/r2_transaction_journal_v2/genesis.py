"""Canonical V3 and Execution Confirmation-bound journal genesis."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    ExecutionConfirmationClaimV1,
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
    "execution_confirmation_policy_fingerprint",
    "reviewed_evidence_fingerprint",
    "evidence_identity_fingerprint",
    "package_fingerprint",
    "manifest_fingerprint",
    "journal_owner_fingerprint",
    "genesis_nonce",
    "pre_genesis_head_fingerprint",
    "execution_confirmation_claim",
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
    execution_confirmation_policy_fingerprint: str = field(repr=False)
    reviewed_evidence_fingerprint: str = field(repr=False)
    evidence_identity_fingerprint: str = field(repr=False)
    package_fingerprint: str = field(repr=False)
    manifest_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    genesis_nonce: str = field(repr=False)
    pre_genesis_head_fingerprint: str = field(repr=False)
    execution_confirmation_claim: ExecutionConfirmationClaimV1 = field(repr=False)
    record_sequence: int
    head_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2JournalGenesisV2 requires create()")

    @classmethod
    def create(cls, **values) -> R2JournalGenesisV2:
        try:
            claim = values["execution_confirmation_claim"]
            return _construct(_genesis_body(**values), claim)
        except JournalGenesisError:
            raise
        except Exception:
            raise JournalGenesisError() from None

    @classmethod
    def from_json(cls, payload: object, *, binding: object) -> R2JournalGenesisV2:
        try:
            source = strict_json_object(payload)
            if (
                canonical_json(source) != payload
                or set(source) != {*_FIELDS, "head_fingerprint"}
            ):
                raise JournalGenesisError()
            claim = ExecutionConfirmationClaimV1.from_json(
                canonical_json(source["execution_confirmation_claim"]),
                binding=binding,
            )
            body = _genesis_body(
                binding=binding,
                execution_confirmation_claim=claim,
                **{
                    name: source[name]
                    for name in _FINGERPRINT_INPUTS
                },
            )
            if any(source[name] != body[name] for name in _FIELDS):
                raise JournalGenesisError()
            if source["head_fingerprint"] != _head_fingerprint(body):
                raise JournalGenesisError()
            return _construct(body, claim)
        except JournalGenesisError:
            raise
        except Exception:
            raise JournalGenesisError() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in _FIELDS}
        body["execution_confirmation_claim"] = (
            self.execution_confirmation_claim.to_mapping()
        )
        return {**body, "head_fingerprint": self.head_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


_FINGERPRINT_INPUTS = (
    "reviewed_evidence_fingerprint",
    "evidence_identity_fingerprint",
    "package_fingerprint",
    "manifest_fingerprint",
    "journal_owner_fingerprint",
    "genesis_nonce",
    "pre_genesis_head_fingerprint",
)


def _genesis_body(*, binding, execution_confirmation_claim, **fingerprints):
    if not _valid_inputs(binding, execution_confirmation_claim, fingerprints):
        raise JournalGenesisError()
    return {
        "genesis_type": _TYPE,
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "operation_fingerprint": binding.operation_fingerprint,
        "production_role_registry_fingerprint": (
            binding.production_role_registry_fingerprint
        ),
        "execution_confirmation_policy_fingerprint": (
            binding.execution_confirmation_policy_fingerprint
        ),
        **fingerprints,
        "execution_confirmation_claim": execution_confirmation_claim.to_mapping(),
        "record_sequence": 0,
    }


def _valid_inputs(binding, claim, values):
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(claim) is not ExecutionConfirmationClaimV1
        or set(values) != set(_FINGERPRINT_INPUTS)
        or not all(is_fingerprint(value) for value in values.values())
    ):
        return False
    expected_action = production_action_fingerprint_v2(
        binding,
        ProductionCommandV2.EVIDENCE_PUBLICATION,
        subject_fingerprint=values["reviewed_evidence_fingerprint"],
    )
    return (
        claim.production_binding_fingerprint == binding.binding_fingerprint
        and claim.command is ProductionCommandV2.EVIDENCE_PUBLICATION
        and claim.claim_sequence == 1
        and claim.journal_owner_fingerprint == values["journal_owner_fingerprint"]
        and claim.prior_journal_head_fingerprint
        == values["pre_genesis_head_fingerprint"]
        and claim.transition_instance_fingerprint
        == values["reviewed_evidence_fingerprint"]
        and claim.remaining_reverse_plan_fingerprint == "0" * 64
        and claim.closure_manifest_fingerprint == values["manifest_fingerprint"]
        and claim.action_fingerprint == expected_action
    )


def _construct(body, claim):
    value = object.__new__(R2JournalGenesisV2)
    for name in _FIELDS:
        item = claim if name == "execution_confirmation_claim" else body[name]
        object.__setattr__(value, name, item)
    object.__setattr__(value, "head_fingerprint", _head_fingerprint(body))
    return value


def _head_fingerprint(body):
    return fingerprint("r2-journal-genesis-v2", body)
