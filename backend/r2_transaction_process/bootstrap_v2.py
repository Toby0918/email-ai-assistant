"""Reviewed bootstrap for the fixed transaction executable process root."""

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
    TransactionProductionResultV2,
    TransactionProductionStatusV2,
    dormant_transaction_production_v2,
    run_transaction_production_v2,
)
from .terminal import SystemTerminal


@dataclass(frozen=True, slots=True, init=False, repr=False)
class TransactionProductionBootstrapV2:
    binding: ApprovedCutoverBindingV2 = field(repr=False)
    reviewed_binding_receipt: R2ReviewedProductionBindingReceiptV1 = field(repr=False)
    adapter: R2BoundProductionAdapterV1 = field(repr=False)
    durable_claims: tuple[DurableAuthorityClaimV2, ...] = field(repr=False)
    current_journal_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    remaining_reverse_plan_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("TransactionProductionBootstrapV2 requires create()")

    @classmethod
    def create(
        cls, *, binding, reviewed_binding_receipt, adapter, durable_claims,
        current_journal_head_fingerprint, transition_instance_fingerprint,
        remaining_reverse_plan_fingerprint,
    ):
        values = locals()
        values = {name: values[name] for name in cls.__dataclass_fields__}
        try:
            _require(values)
        except Exception:
            raise TypeError("R2_TRANSACTION_PRODUCTION_BOOTSTRAP_INVALID") from None
        result = object.__new__(cls)
        for name in cls.__dataclass_fields__:
            object.__setattr__(result, name, values[name])
        return result

    def run(self, *, argv):
        return run_transaction_production_v2(
            argv=argv,
            terminal=SystemTerminal(),
            binding=self.binding,
            adapter=self.adapter,
            durable_claims=self.durable_claims,
            current_journal_head_fingerprint=(
                self.current_journal_head_fingerprint
            ),
            transition_instance_fingerprint=(
                self.transition_instance_fingerprint
            ),
            remaining_reverse_plan_fingerprint=(
                self.remaining_reverse_plan_fingerprint
            ),
            observed_at_epoch=_current_epoch,
        )


def execute_transaction_main_v2(argv, bootstrap):
    if bootstrap is None:
        return dormant_transaction_production_v2(argv=argv)
    try:
        if type(bootstrap) is not TransactionProductionBootstrapV2:
            raise TypeError
        return bootstrap.run(argv=argv)
    except Exception:
        return TransactionProductionResultV2(
            TransactionProductionStatusV2.BLOCKED_ACTION, 0, 1, 0
        )


def _require(values):
    expected = set(TransactionProductionBootstrapV2.__dataclass_fields__)
    fingerprints = (
        "current_journal_head_fingerprint",
        "transition_instance_fingerprint",
        "remaining_reverse_plan_fingerprint",
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
        raise TypeError("R2_TRANSACTION_PRODUCTION_BOOTSTRAP_INVALID")
    require_reviewed_bound_production_adapter_v1(
        binding=values["binding"],
        slot=ProductionAdapterSlotV1.TRANSACTION,
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
