"""Shared fail-closed binding checks for stateful composition adapters."""

from dataclasses import dataclass, field

from backend.cutover_composition_contracts import CompositionBindingV1
from backend.cutover_composition_contracts.canonical import (
    fingerprint as composition_fingerprint,
)
from backend.r2_production_binding.binding import ApprovedCutoverBindingV3
from backend.r2_production_binding.execution_confirmation import (
    ExecutionConfirmationClaimV1,
)
from backend.r2_production_binding.claim import (
    _consume_execution_confirmation_attempt_v1,
)
from backend.r2_production_binding.errors import (
    ExecutionConfirmationError,
    ProductionBindingError,
)
from backend.r2_production_binding._adapter_identity import (
    _require_adapter_type_surface_v1,
    production_adapter_fingerprint_v1,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2BoundProductionAdapterV1:
    slot: object
    binding_fingerprint: str = field(repr=False)
    implementation_fingerprints: tuple = field(repr=False)
    _adapter: object = field(repr=False)
    _adapter_surface: tuple = field(repr=False)
    _invoke: object = field(repr=False)
    _synthetic_test_only: bool = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError(
            "R2BoundProductionAdapterV1 requires bind_production_adapter_v1()"
        )

    def invoke(self, **kwargs):
        if self._synthetic_test_only:
            return self._invoke(**kwargs)
        return self._invoke(self._adapter, **kwargs)


def bind_production_adapter_v1(*, binding, adapter):
    try:
        if type(binding) is not ApprovedCutoverBindingV3:
            raise ProductionBindingError()
        adapter_type = type(adapter)
        registrations = _registrations_for_adapter(adapter_type)
        if not registrations or getattr(adapter, "_binding", None) is not binding:
            raise ProductionBindingError()
        surface = _reviewed_surface_for_adapter(adapter_type)
        observed = tuple(
            (
                item.command,
                production_adapter_fingerprint_v1(
                    item.command,
                    item.adapter_type,
                ),
            )
            for item in registrations
        )
        _require_adapter_type_surface_v1(adapter_type, surface)
        expected = dict(binding.production_role_fingerprints)
        if any(
            expected[item.production_role] != value
            for item, (_command, value) in zip(
                registrations,
                observed,
                strict=True,
            )
        ):
            raise ProductionBindingError()
        return _allocate_bound_adapter(
            registrations[0].slot,
            binding,
            observed,
            adapter,
            surface,
            False,
        )
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def reverify_bound_production_adapter_v1(*, binding, slot, bound):
    try:
        _require_bound_adapter_shell(binding, slot, bound)
        if bound._synthetic_test_only:
            _require_synthetic_adapter_module(bound._adapter)
        else:
            _reverify_real_adapter(binding, slot, bound)
        return bound
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _require_bound_adapter_shell(binding, slot, bound):
    from .catalog import ProductionAdapterSlotV1

    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(slot) is not ProductionAdapterSlotV1
        or type(bound) is not R2BoundProductionAdapterV1
        or bound.slot is not slot
        or bound.binding_fingerprint != binding.binding_fingerprint
    ):
        raise ProductionBindingError()


def _require_synthetic_adapter_module(adapter):
    module = type(adapter).__module__
    if not (
        module.startswith("backend.r2_")
        and module.endswith("_process.testing")
    ):
        raise ProductionBindingError()


def _reverify_real_adapter(binding, slot, bound):
    adapter_type = type(bound._adapter)
    reviewed_surface = _reviewed_surface_for_adapter(adapter_type)
    if bound._invoke is not _invoke_from_surface(reviewed_surface):
        raise ProductionBindingError()
    _require_adapter_type_surface_v1(adapter_type, bound._adapter_surface)
    registrations = _registrations_for_adapter(adapter_type)
    if (
        not registrations
        or registrations[0].slot is not slot
        or getattr(bound._adapter, "_binding", None) is not binding
    ):
        raise ProductionBindingError()
    observed = tuple(
        (
            item.command,
            production_adapter_fingerprint_v1(item.command, item.adapter_type),
        )
        for item in registrations
    )
    _require_adapter_type_surface_v1(adapter_type, bound._adapter_surface)
    expected = dict(binding.production_role_fingerprints)
    if observed != bound.implementation_fingerprints or any(
        expected[item.production_role] != value
        for item, (_command, value) in zip(registrations, observed, strict=True)
    ):
        raise ProductionBindingError()


def require_reviewed_bound_production_adapter_v1(*, binding, slot, bound):
    value = reverify_bound_production_adapter_v1(
        binding=binding,
        slot=slot,
        bound=bound,
    )
    if value._synthetic_test_only:
        raise ProductionBindingError()
    return value


def _synthetic_bound_adapter_v1(slot, adapter, binding):
    from .catalog import ProductionAdapterSlotV1

    if (
        type(slot) is not ProductionAdapterSlotV1
        or type(binding) is not ApprovedCutoverBindingV3
        or not callable(getattr(adapter, "invoke", None))
    ):
        raise ProductionBindingError()
    return _allocate_bound_adapter(slot, binding, (), adapter, (), True)


def _allocate_bound_adapter(
    slot,
    binding,
    fingerprints,
    adapter,
    surface,
    synthetic,
):
    if synthetic:
        invoke = adapter.invoke
    else:
        invoke = _invoke_from_surface(surface)
    value = object.__new__(R2BoundProductionAdapterV1)
    object.__setattr__(value, "slot", slot)
    object.__setattr__(value, "binding_fingerprint", binding.binding_fingerprint)
    object.__setattr__(value, "implementation_fingerprints", fingerprints)
    object.__setattr__(value, "_adapter", adapter)
    object.__setattr__(value, "_adapter_surface", surface)
    object.__setattr__(value, "_invoke", invoke)
    object.__setattr__(value, "_synthetic_test_only", synthetic)
    return value


def _registrations_for_adapter(adapter_type):
    from .catalog import production_adapter_catalog_v1

    return tuple(
        item
        for item in production_adapter_catalog_v1()
        if item.adapter_type is adapter_type
    )


def _reviewed_surface_for_adapter(adapter_type):
    from .catalog import _reviewed_adapter_surface_v1

    return _reviewed_adapter_surface_v1(adapter_type)


def _invoke_from_surface(surface):
    targets = tuple(member for name, member in surface if name == "invoke")
    if len(targets) != 1 or not callable(targets[0]):
        raise ProductionBindingError()
    return targets[0]


def require_adapter_context_v1(binding, claim, composition_binding, commands):
    try:
        if (
            type(binding) is not ApprovedCutoverBindingV3
            or type(claim) is not ExecutionConfirmationClaimV1
            or claim.production_binding_fingerprint != binding.binding_fingerprint
            or claim.command not in commands
        ):
            raise ProductionBindingError()
        require_composition_binding_v1(binding, composition_binding)
        _consume_execution_confirmation_attempt_v1(claim)
    except ProductionBindingError:
        raise
    except ExecutionConfirmationError:
        raise ProductionBindingError() from None


def require_composition_binding_v1(binding, composition_binding):
    from .binding_candidate import _operator_subject_fingerprint

    expected_master = composition_fingerprint(
        "project-container-governing-master-v1",
        binding.final_commit_oid,
    )
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(composition_binding) is not CompositionBindingV1
        or composition_binding.operation_fingerprint
        != binding.operation_fingerprint
        or composition_binding.governing_master_fingerprint != expected_master
        or composition_binding.operator_fingerprint
        != _operator_subject_fingerprint(
            binding.final_master_binding_fingerprint
        )
    ):
        raise ProductionBindingError()
