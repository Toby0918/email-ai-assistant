"""Synthetic-only binder for the public preflight process seam."""

from __future__ import annotations

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.cutover_composition_contracts.canonical import fingerprint
from backend.cutover_contracts import CutoverProfileV1
from backend.r2_production_binding import ApprovedCutoverBindingV2, ProductionCommandV2
from .entry import run_authorization_gate
from .production_v2 import (
    _create_synthetic_roles_v2,
    complete_preflight_read_v2,
    run_preflight_production_v2,
)
from backend.r2_production_binding.role_binding import _synthetic_bound_callable_v2


class SyntheticPreflightProcess:
    __slots__ = (
        "_binding",
        "_claimed",
        "_key",
        "_now",
        "_operation",
        "_profile",
        "reader_acquisitions",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticPreflightProcess requires create()")

    @classmethod
    def create(
        cls,
        *,
        profile: CutoverProfileV1,
        binding: ApprovedCutoverBindingV1,
        operation_fingerprint: str,
        verification_public_key: bytes,
        observed_at_epoch,
    ) -> SyntheticPreflightProcess:
        _require_context(
            profile,
            binding,
            operation_fingerprint,
            verification_public_key,
            observed_at_epoch,
        )
        value = object.__new__(cls)
        value._profile = profile
        value._binding = binding
        value._operation = operation_fingerprint
        value._key = verification_public_key
        value._now = observed_at_epoch
        value._claimed = set()
        value.reader_acquisitions = 0
        return value

    def run(self, *, argv: object, terminal: object):
        return run_authorization_gate(
            argv=argv,
            terminal=terminal,
            profile=self._profile,
            operation_fingerprint=self._operation,
            verification_public_key=self._key,
            observed_at_epoch=self._now,
            claim_nonce=self._claim_nonce,
        )

    def _claim_nonce(self, nonce: str) -> bool:
        if nonce in self._claimed:
            return False
        self._claimed.add(nonce)
        return True


def _require_context(profile, binding, operation, key, now) -> None:
    master = fingerprint(
        "project-container-governing-master-v1",
        profile.governing_master_commit,
    )
    if (
        type(profile) is not CutoverProfileV1
        or type(binding) is not ApprovedCutoverBindingV1
        or binding.profile_fingerprint != profile.profile_fingerprint
        or binding.governing_master_fingerprint != master
        or binding.operator_fingerprint != profile.operator_fingerprint
        or binding.operation_fingerprint != operation
        or type(key) is not bytes
        or len(key) != 32
        or not callable(now)
    ):
        raise ValueError("R2_PREFLIGHT_SYNTHETIC_BINDING_INVALID")


class SyntheticPreflightProductionV2:
    __slots__ = ("_binding", "_counts", "_now", "_roles")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticPreflightProductionV2 requires create()")

    @classmethod
    def create(cls, *, binding, observed_at_epoch):
        if (
            type(binding) is not ApprovedCutoverBindingV2
            or not callable(observed_at_epoch)
        ):
            raise ValueError("R2_PREFLIGHT_SYNTHETIC_V2_BINDING_INVALID")
        value = object.__new__(cls)
        value._binding = binding
        value._now = observed_at_epoch
        value._counts = {command: 0 for command in ProductionCommandV2}
        callbacks = {
            command: _callback(value, command)
            for command in tuple(ProductionCommandV2)[:6]
        }
        value._roles = _create_synthetic_roles_v2(tuple(
            _synthetic_bound_callable_v2(command, callbacks[command], binding)
            for command in callbacks
        ))
        return value

    @property
    def total_role_invocations(self):
        return sum(self._counts.values())

    def role_invocations(self, command):
        return self._counts[command]

    def run(self, **values):
        return run_preflight_production_v2(
            binding=self._binding,
            roles=self._roles,
            observed_at_epoch=self._now,
            **values,
        )

    def _record(self, command, binding, claim):
        if claim.command is not command:
            raise ValueError("R2_PREFLIGHT_SYNTHETIC_V2_COMMAND_INVALID")
        self._counts[command] += 1
        return complete_preflight_read_v2(binding, claim)


def _callback(process, command):
    return lambda binding, claim: process._record(command, binding, claim)
