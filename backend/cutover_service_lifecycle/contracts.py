"""Closed provider-disabled service identity and Config contracts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .canonical import fail, is_fingerprint, is_uuid4

_ERROR = "service_lifecycle_contract_invalid"
_DISABLED = "disabled"


class ServiceRole(str, Enum):
    NEW = "reviewed_new_service"
    LEGACY = "reviewed_legacy_service"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class LegacyRecoveryConfigV1:
    primary_provider: str
    fallback_provider: str
    reads_environment: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("LegacyRecoveryConfigV1 requires create()")

    @classmethod
    def create(cls) -> LegacyRecoveryConfigV1:
        value = object.__new__(cls)
        object.__setattr__(value, "primary_provider", _DISABLED)
        object.__setattr__(value, "fallback_provider", _DISABLED)
        object.__setattr__(value, "reads_environment", False)
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            "config_type": "legacy-provider-disabled-recovery/v1",
            "primary_provider": self.primary_provider,
            "fallback_provider": self.fallback_provider,
            "reads_environment": self.reads_environment,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ServiceStartEvidenceV1:
    role: str
    pid: int = field(repr=False)
    start_time_ns: int = field(repr=False)
    executable_fingerprint: str = field(repr=False)
    port: int = field(repr=False)
    port_owner_pid: int = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    runtime_fingerprint: str = field(repr=False)
    config_fingerprint: str = field(repr=False)
    data_role_fingerprint: str = field(repr=False)
    nonce: str = field(repr=False)
    primary_provider: str
    fallback_provider: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ServiceStartEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> ServiceStartEvidenceV1:
        if not _valid_process_values(values):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in _normalized_process_values(values).items():
            object.__setattr__(value, name, item)
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            name: getattr(self, name)
            for name in _PROCESS_FIELDS
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ServiceHealthEvidenceV1:
    role: str
    pid: int = field(repr=False)
    start_time_ns: int = field(repr=False)
    executable_fingerprint: str = field(repr=False)
    port: int = field(repr=False)
    port_owner_pid: int = field(repr=False)
    profile_fingerprint: str = field(repr=False)
    runtime_fingerprint: str = field(repr=False)
    config_fingerprint: str = field(repr=False)
    data_role_fingerprint: str = field(repr=False)
    nonce: str = field(repr=False)
    primary_provider: str
    fallback_provider: str
    healthy: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ServiceHealthEvidenceV1 requires create_from_start()")

    @classmethod
    def create_from_start(
        cls, start: object
    ) -> ServiceHealthEvidenceV1:
        if type(start) is not ServiceStartEvidenceV1:
            fail(_ERROR)
        value = object.__new__(cls)
        for name in _PROCESS_FIELDS:
            object.__setattr__(value, name, getattr(start, name))
        object.__setattr__(value, "healthy", True)
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            **{name: getattr(self, name) for name in _PROCESS_FIELDS},
            "healthy": self.healthy,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ServiceStopEvidenceV1:
    role: str
    pid: int = field(repr=False)
    start_time_ns: int = field(repr=False)
    executable_fingerprint: str = field(repr=False)
    nonce: str = field(repr=False)
    stopped: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ServiceStopEvidenceV1 requires create_from_start()")

    @classmethod
    def create_from_start(
        cls, start: object
    ) -> ServiceStopEvidenceV1:
        if type(start) is not ServiceStartEvidenceV1:
            fail(_ERROR)
        value = object.__new__(cls)
        for name in (
            "role",
            "pid",
            "start_time_ns",
            "executable_fingerprint",
            "nonce",
        ):
            object.__setattr__(value, name, getattr(start, name))
        object.__setattr__(value, "stopped", True)
        return value

    def to_mapping(self) -> dict[str, object]:
        return {
            "role": self.role,
            "pid": self.pid,
            "start_time_ns": self.start_time_ns,
            "executable_fingerprint": self.executable_fingerprint,
            "nonce": self.nonce,
            "stopped": self.stopped,
        }


_PROCESS_FIELDS = (
    "role",
    "pid",
    "start_time_ns",
    "executable_fingerprint",
    "port",
    "port_owner_pid",
    "profile_fingerprint",
    "runtime_fingerprint",
    "config_fingerprint",
    "data_role_fingerprint",
    "nonce",
    "primary_provider",
    "fallback_provider",
)


def _valid_process_values(values: dict[str, object]) -> bool:
    fingerprints = (
        "executable_fingerprint",
        "profile_fingerprint",
        "runtime_fingerprint",
        "config_fingerprint",
        "data_role_fingerprint",
    )
    return (
        set(values) == set(_PROCESS_FIELDS)
        and type(values["role"]) is ServiceRole
        and type(values["pid"]) is int
        and 0 < values["pid"] < 2**31
        and type(values["start_time_ns"]) is int
        and 0 < values["start_time_ns"] < 2**63
        and type(values["port"]) is int
        and 0 < values["port"] <= 65_535
        and values["port_owner_pid"] == values["pid"]
        and all(is_fingerprint(values[name]) for name in fingerprints)
        and is_uuid4(values["nonce"])
        and values["primary_provider"] == _DISABLED
        and values["fallback_provider"] == _DISABLED
    )


def _normalized_process_values(
    values: dict[str, object],
) -> dict[str, object]:
    return {
        **values,
        "role": values["role"].value,
    }
