"""Shared fail-closed binding checks for stateful composition adapters."""

from dataclasses import dataclass, field

from backend.cutover_composition_contracts import CompositionBindingV1
from backend.cutover_composition_contracts.canonical import (
    fingerprint as composition_fingerprint,
)
from backend.r2_production_binding.binding import ApprovedCutoverBindingV2
from backend.r2_production_binding.claim import DurableAuthorityClaimV2
from backend.r2_production_binding.errors import ProductionBindingError
from backend.r2_production_binding.vocabulary import PublicKeyRoleV2
from backend.r2_production_binding._adapter_identity import (
    production_adapter_fingerprint_v1,
)
from backend.r2_production_binding._canonical import fingerprint


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2BoundProductionAdapterV1:
    slot: object
    binding_fingerprint: str = field(repr=False)
    implementation_fingerprints: tuple = field(repr=False)
    _adapter: object = field(repr=False)
    _synthetic_test_only: bool = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError(
            "R2BoundProductionAdapterV1 requires bind_production_adapter_v1()"
        )

    def invoke(self, **kwargs):
        return self._adapter.invoke(**kwargs)


def bind_production_adapter_v1(*, binding, adapter):
    try:
        if type(binding) is not ApprovedCutoverBindingV2:
            raise ProductionBindingError()
        registrations = _registrations_for_adapter(type(adapter))
        if not registrations or getattr(adapter, "_binding", None) is not binding:
            raise ProductionBindingError()
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
        type(binding) is not ApprovedCutoverBindingV2
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
    registrations = _registrations_for_adapter(type(bound._adapter))
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
        or type(binding) is not ApprovedCutoverBindingV2
        or not callable(getattr(adapter, "invoke", None))
    ):
        raise ProductionBindingError()
    return _allocate_bound_adapter(slot, binding, (), adapter, True)


def _allocate_bound_adapter(slot, binding, fingerprints, adapter, synthetic):
    value = object.__new__(R2BoundProductionAdapterV1)
    object.__setattr__(value, "slot", slot)
    object.__setattr__(value, "binding_fingerprint", binding.binding_fingerprint)
    object.__setattr__(value, "implementation_fingerprints", fingerprints)
    object.__setattr__(value, "_adapter", adapter)
    object.__setattr__(value, "_synthetic_test_only", synthetic)
    return value


def _registrations_for_adapter(adapter_type):
    from .catalog import production_adapter_catalog_v1

    return tuple(
        item
        for item in production_adapter_catalog_v1()
        if item.adapter_type is adapter_type
    )


def operator_subject_fingerprint_v1(verification_public_keys):
    if (
        type(verification_public_keys) is not dict
        or set(verification_public_keys) != set(PublicKeyRoleV2)
        or any(
            type(role) is not PublicKeyRoleV2
            for role in verification_public_keys
        )
        or any(
            type(key) is not bytes or len(key) != 32
            for key in verification_public_keys.values()
        )
        or len(set(verification_public_keys.values())) != len(PublicKeyRoleV2)
    ):
        raise ProductionBindingError()
    return fingerprint(
        "r2-operator-subject-v2",
        {
            "verification_public_key_set": sorted(
                key.hex() for key in verification_public_keys.values()
            )
        },
    )


def require_adapter_context_v1(binding, claim, composition_binding, commands):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(claim) is not DurableAuthorityClaimV2
        or claim.binding_fingerprint != binding.binding_fingerprint
        or claim.command not in commands
    ):
        raise ProductionBindingError()
    require_composition_binding_v1(binding, composition_binding)


def require_composition_binding_v1(binding, composition_binding):
    keys = dict(binding.verification_public_keys)
    expected_master = composition_fingerprint(
        "project-container-governing-master-v1",
        binding.final_commit_oid,
    )
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(composition_binding) is not CompositionBindingV1
        or composition_binding.operation_fingerprint
        != binding.operation_fingerprint
        or composition_binding.governing_master_fingerprint != expected_master
        or composition_binding.operator_fingerprint
        != operator_subject_fingerprint_v1(keys)
    ):
        raise ProductionBindingError()
