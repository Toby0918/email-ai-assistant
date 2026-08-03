"""Reviewed bootstrap for the fixed preflight executable process root."""

from dataclasses import dataclass, field
from time import time as _current_epoch

from backend.r2_final_master_closure import R2ReviewedProductionBindingReceiptV1
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    ProductionCommandV2,
    require_reviewed_bound_production_callable_v2,
    require_reviewed_production_binding_receipt_v2,
)
from backend.r2_production_binding._canonical import is_fingerprint

from .production_v2 import (
    PREFLIGHT_PRODUCTION_VERBS_V2,
    PreflightProductionResultV2,
    PreflightProductionRolesV2,
    PreflightProductionStatusV2,
    dormant_preflight_production_v2,
    run_preflight_production_v2,
)
from .terminal import SystemTerminal


@dataclass(frozen=True, slots=True, init=False, repr=False)
class PreflightProductionBootstrapV2:
    binding: ApprovedCutoverBindingV2 = field(repr=False)
    reviewed_binding_receipt: R2ReviewedProductionBindingReceiptV1 = field(repr=False)
    roles: PreflightProductionRolesV2 = field(repr=False)
    durable_claims: tuple[DurableAuthorityClaimV2, ...] = field(repr=False)
    expected_prior_journal_head_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("PreflightProductionBootstrapV2 requires create()")

    @classmethod
    def create(
        cls, *, binding, reviewed_binding_receipt, roles, durable_claims,
        expected_prior_journal_head_fingerprint,
    ):
        values = locals()
        values = {name: values[name] for name in cls.__dataclass_fields__}
        try:
            _require(values)
        except Exception:
            raise TypeError("R2_PREFLIGHT_PRODUCTION_BOOTSTRAP_INVALID") from None
        result = object.__new__(cls)
        for name in cls.__dataclass_fields__:
            object.__setattr__(result, name, values[name])
        return result

    def run(self, *, argv):
        return run_preflight_production_v2(
            argv=argv,
            terminal=SystemTerminal(),
            binding=self.binding,
            roles=self.roles,
            durable_claims=self.durable_claims,
            expected_prior_journal_head_fingerprint=(
                self.expected_prior_journal_head_fingerprint
            ),
            observed_at_epoch=_current_epoch,
        )


def execute_preflight_main_v2(argv, bootstrap):
    if bootstrap is None:
        return dormant_preflight_production_v2(argv=argv)
    try:
        if type(bootstrap) is not PreflightProductionBootstrapV2:
            raise TypeError
        return bootstrap.run(argv=argv)
    except Exception:
        return PreflightProductionResultV2(
            PreflightProductionStatusV2.BLOCKED_COMPOSITION, 0, 1, 0
        )


def _require(values):
    expected = set(PreflightProductionBootstrapV2.__dataclass_fields__)
    if (
        type(values) is not dict
        or set(values) != expected
        or type(values["binding"]) is not ApprovedCutoverBindingV2
        or not _receipt_matches(
            values["binding"], values["reviewed_binding_receipt"]
        )
        or type(values["roles"]) is not PreflightProductionRolesV2
        or not _claims_match(values["durable_claims"], values["binding"])
        or not is_fingerprint(values["expected_prior_journal_head_fingerprint"])
    ):
        raise TypeError("R2_PREFLIGHT_PRODUCTION_BOOTSTRAP_INVALID")
    for command in PREFLIGHT_PRODUCTION_VERBS_V2.values():
        require_reviewed_bound_production_callable_v2(
            binding=values["binding"],
            command=command,
            bound=values["roles"].select(command),
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
