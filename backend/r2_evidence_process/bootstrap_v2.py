"""Reviewed bootstrap for the fixed evidence executable process root."""

from dataclasses import dataclass, field
from time import time as _current_epoch

from backend.r2_final_master_closure import R2ReviewedProductionBindingReceiptV1
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    require_reviewed_production_binding_receipt_v2,
)
from backend.r2_production_composition import (
    ProductionAdapterSlotV1,
    R2BoundProductionAdapterV1,
    require_reviewed_bound_production_adapter_v1,
)
from backend.r2_production_binding._canonical import is_fingerprint

from .production_v2 import (
    EvidenceProductionResultV2,
    EvidenceProductionStatusV2,
    dormant_evidence_production_v2,
    run_evidence_production_v2,
)
from .terminal import SystemTerminal


@dataclass(frozen=True, slots=True, init=False, repr=False)
class EvidenceProductionBootstrapV2:
    binding: ApprovedCutoverBindingV2 = field(repr=False)
    reviewed_binding_receipt: R2ReviewedProductionBindingReceiptV1 = field(repr=False)
    adapter: R2BoundProductionAdapterV1 = field(repr=False)
    reviewed_evidence_fingerprint: str = field(repr=False)
    durable_claims: tuple[DurableAuthorityClaimV2, ...] = field(repr=False)
    expected_prior_journal_head_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    genesis_nonce: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("EvidenceProductionBootstrapV2 requires create()")

    @classmethod
    def create(
        cls, *, binding, reviewed_binding_receipt, adapter,
        reviewed_evidence_fingerprint, durable_claims,
        expected_prior_journal_head_fingerprint, journal_owner_fingerprint,
        genesis_nonce,
    ):
        values = locals()
        values = {name: values[name] for name in cls.__dataclass_fields__}
        try:
            _require(values)
        except Exception:
            raise TypeError("R2_EVIDENCE_PRODUCTION_BOOTSTRAP_INVALID") from None
        result = object.__new__(cls)
        for name in cls.__dataclass_fields__:
            object.__setattr__(result, name, values[name])
        return result

    def run(self, *, argv):
        return run_evidence_production_v2(
            argv=argv,
            terminal=SystemTerminal(),
            binding=self.binding,
            adapter=self.adapter,
            reviewed_evidence_fingerprint=self.reviewed_evidence_fingerprint,
            durable_claims=self.durable_claims,
            expected_prior_journal_head_fingerprint=(
                self.expected_prior_journal_head_fingerprint
            ),
            observed_at_epoch=_current_epoch,
            journal_owner_fingerprint=self.journal_owner_fingerprint,
            genesis_nonce=self.genesis_nonce,
        )


def execute_evidence_main_v2(argv, bootstrap):
    if bootstrap is None:
        return dormant_evidence_production_v2(argv=argv)
    try:
        if type(bootstrap) is not EvidenceProductionBootstrapV2:
            raise TypeError
        return bootstrap.run(argv=argv)
    except Exception:
        return EvidenceProductionResultV2(
            EvidenceProductionStatusV2.BLOCKED_PUBLICATION, 0, 1, 0
        )


def _require(values):
    expected = set(EvidenceProductionBootstrapV2.__dataclass_fields__)
    fingerprints = (
        "reviewed_evidence_fingerprint",
        "expected_prior_journal_head_fingerprint",
        "journal_owner_fingerprint",
        "genesis_nonce",
    )
    if (
        type(values) is not dict
        or set(values) != expected
        or type(values["binding"]) is not ApprovedCutoverBindingV2
        or not _receipt_matches(
            values["binding"], values["reviewed_binding_receipt"]
        )
        or type(values["adapter"]) is not R2BoundProductionAdapterV1
        or not _claims_match(values["durable_claims"], values["binding"])
        or not all(is_fingerprint(values[name]) for name in fingerprints)
    ):
        raise TypeError("R2_EVIDENCE_PRODUCTION_BOOTSTRAP_INVALID")
    require_reviewed_bound_production_adapter_v1(
        binding=values["binding"],
        slot=ProductionAdapterSlotV1.EVIDENCE,
        bound=values["adapter"],
    )


def _claims_match(claims, binding):
    return type(claims) is tuple and all(
        type(item) is DurableAuthorityClaimV2
        and item.binding_fingerprint == binding.binding_fingerprint
        for item in claims
    )


def _receipt_matches(binding, receipt):
    try:
        return require_reviewed_production_binding_receipt_v2(binding, receipt) is receipt
    except Exception:
        return False
