"""Code-identity binding for production process callables."""

from __future__ import annotations

from dataclasses import dataclass, field

from .binding import ApprovedCutoverBindingV2
from ._callable_identity import production_callable_fingerprint_v2
from .errors import ProductionBindingError
from .vocabulary import ProductionCommandV2, ProductionRoleV2


_COMMAND_ROLES = {
    ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT: ProductionRoleV2.LEGACY_SOURCE_ANCHOR,
    ProductionCommandV2.HOST_BASELINE: ProductionRoleV2.PROJECT_CONTAINER,
    ProductionCommandV2.EVIDENCE_REVIEW: ProductionRoleV2.REPOSITORY_ROOT,
    ProductionCommandV2.EVIDENCE_VERIFICATION: ProductionRoleV2.GIT_COMMON_STATE,
    ProductionCommandV2.FINAL_AUDIT_READINESS: ProductionRoleV2.FINAL_RUNNING_AUDIT,
    ProductionCommandV2.RECOVERY_INSPECTION: ProductionRoleV2.STOPPED_LAYOUT_AUDIT,
    ProductionCommandV2.EVIDENCE_PUBLICATION: ProductionRoleV2.EVIDENCE_PACKAGE,
    ProductionCommandV2.EXECUTE: ProductionRoleV2.MANAGED_MAIN,
    ProductionCommandV2.RESUME: ProductionRoleV2.TRANSACTION_JOURNAL,
    ProductionCommandV2.ROLLBACK: ProductionRoleV2.LEGACY_SERVICE,
}

@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2BoundProductionCallableV2:
    command: ProductionCommandV2
    production_role: ProductionRoleV2
    implementation_fingerprint: str = field(repr=False)
    _callback: object = field(repr=False)
    _synthetic_test_only: bool = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2BoundProductionCallableV2 requires bind_production_callable_v2()")

    def __call__(self, *args, **kwargs):
        if (
            not self._synthetic_test_only
            and production_callable_fingerprint_v2(self.command, self._callback)
                != self.implementation_fingerprint
        ):
            raise ProductionBindingError()
        return self._callback(*args, **kwargs)


def bind_production_callable_v2(*, binding, command, callback):
    """Bind a callable only when its code identity is in the reviewed role registry."""
    try:
        if type(binding) is not ApprovedCutoverBindingV2:
            raise ProductionBindingError()
        role = _COMMAND_ROLES[command]
        observed = production_callable_fingerprint_v2(command, callback)
        if dict(binding.production_role_fingerprints)[role] != observed:
            raise ProductionBindingError()
        value = object.__new__(R2BoundProductionCallableV2)
        object.__setattr__(value, "command", command)
        object.__setattr__(value, "production_role", role)
        object.__setattr__(value, "implementation_fingerprint", observed)
        object.__setattr__(value, "_callback", callback)
        object.__setattr__(value, "_synthetic_test_only", False)
        return value
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def command_production_role_v2(command):
    if type(command) is not ProductionCommandV2:
        raise ProductionBindingError()
    return _COMMAND_ROLES[command]


def reverify_bound_production_callable_v2(*, binding, command, bound):
    """Recompute behavior identity immediately before a production invocation."""
    try:
        if (
            type(binding) is not ApprovedCutoverBindingV2
            or type(command) is not ProductionCommandV2
            or type(bound) is not R2BoundProductionCallableV2
        ):
            raise ProductionBindingError()
        role = _COMMAND_ROLES[command]
        if bound._synthetic_test_only:
            if not bound._callback.__module__.startswith("backend.r2_") or not (
                bound._callback.__module__.endswith("_process.testing")
            ):
                raise ProductionBindingError()
            return bound
        observed = production_callable_fingerprint_v2(command, bound._callback)
        expected = dict(binding.production_role_fingerprints)[role]
        if (
            bound.command is not command
            or bound.production_role is not role
            or bound.implementation_fingerprint != expected
            or observed != expected
        ):
            raise ProductionBindingError()
        return bound
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def require_reviewed_bound_production_callable_v2(*, binding, command, bound):
    value = reverify_bound_production_callable_v2(
        binding=binding, command=command, bound=bound
    )
    if value._synthetic_test_only:
        raise ProductionBindingError()
    return value


def _synthetic_bound_callable_v2(command, callback, binding):
    """Testing-package-only construction; never exported by the package root."""
    value = object.__new__(R2BoundProductionCallableV2)
    object.__setattr__(value, "command", command)
    object.__setattr__(value, "production_role", _COMMAND_ROLES[command])
    object.__setattr__(
        value,
        "implementation_fingerprint",
        dict(binding.production_role_fingerprints)[_COMMAND_ROLES[command]],
    )
    object.__setattr__(value, "_callback", callback)
    object.__setattr__(value, "_synthetic_test_only", True)
    return value
