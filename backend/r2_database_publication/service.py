"""Module-owned legacy-service controller role and stopped receipt."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .canonical import fingerprint

_ISSUED_RECEIPTS: list[StoppedServiceReceiptV1] = []
_BOUND_CONTROLLERS: list[LegacyServiceControllerRole] = []


@dataclass(frozen=True, slots=True, init=False, repr=False)
class StoppedServiceReceiptV1:
    status: str
    service_identity_fingerprint: str = field(repr=False)
    observation_fingerprint: str = field(repr=False)
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("stopped receipt requires validated construction")


class LegacyServiceControllerRole:
    """Exact controller role; test binding stays in the testing module."""

    __slots__ = ("_state", "_identity", "_used")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("service controller requires validated binding")

    def quiesce(self) -> StoppedServiceReceiptV1:
        if not _contains_identity(_BOUND_CONTROLLERS, self) or self._used:
            raise ValueError("legacy_service_controller_invalid")
        self._used = True
        if self._state.read_text("ascii") != "running":
            raise ValueError("legacy_service_state_invalid")
        self._state.write_text("stopped", encoding="ascii")
        first = self._state.read_text("ascii")
        second = self._state.read_text("ascii")
        if first != "stopped" or second != first:
            raise ValueError("legacy_service_stop_unstable")
        return _issue_receipt(self._identity, first)


def _bind_test_controller(state: Path) -> LegacyServiceControllerRole:
    if not state.is_file() or state.read_text("ascii") != "running":
        raise ValueError("legacy_service_binding_invalid")
    controller = object.__new__(LegacyServiceControllerRole)
    controller._state = state
    controller._identity = fingerprint(
        "synthetic-legacy-service-v1", [state.name, state.stat().st_size]
    )
    controller._used = False
    _BOUND_CONTROLLERS.append(controller)
    return controller


def _issue_receipt(identity: str, state: str) -> StoppedServiceReceiptV1:
    body = {
        "status": "STOPPED",
        "service_identity_fingerprint": identity,
        "observation_fingerprint": fingerprint("stopped-observation-v1", state),
    }
    receipt = object.__new__(StoppedServiceReceiptV1)
    for name, value in body.items():
        object.__setattr__(receipt, name, value)
    object.__setattr__(receipt, "receipt_fingerprint", fingerprint("stopped-service-receipt-v1", body))
    _ISSUED_RECEIPTS.append(receipt)
    return receipt


def require_issued_receipt(value: object) -> StoppedServiceReceiptV1:
    if (
        type(value) is not StoppedServiceReceiptV1
        or not _contains_identity(_ISSUED_RECEIPTS, value)
    ):
        raise ValueError("stopped_service_receipt_invalid")
    return value


def _contains_identity(values: list[object], target: object) -> bool:
    return any(value is target for value in values)
