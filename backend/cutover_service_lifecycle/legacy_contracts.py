"""Dedicated provider-disabled legacy recovery request and receipt."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import fail, fingerprint, is_fingerprint, is_uuid4
from .contracts import LegacyRecoveryConfigV1
from .rollback_contracts import LegacyPrerequisiteEvidenceV1

_ERROR = "legacy_recovery_contract_invalid"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class LegacyServiceStartRequestV1:
    role: str
    profile_fingerprint: str = field(repr=False)
    runtime_fingerprint: str = field(repr=False)
    config_fingerprint: str = field(repr=False)
    data_role_fingerprint: str = field(repr=False)
    nonce: str = field(repr=False)
    port: int
    primary_provider: str
    fallback_provider: str
    reads_environment: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("LegacyServiceStartRequestV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        profile_fingerprint: object,
        prerequisites: object,
        nonce: object,
    ):
        if (
            not is_fingerprint(profile_fingerprint)
            or type(prerequisites) is not LegacyPrerequisiteEvidenceV1
            or not is_uuid4(nonce)
        ):
            fail(_ERROR)
        config = LegacyRecoveryConfigV1.create()
        config_fingerprint = fingerprint(
            "issue58-legacy-recovery-config-v1",
            config.to_mapping(),
            code=_ERROR,
        )
        value = object.__new__(cls)
        assignments = {
            "role": "reviewed_legacy_service",
            "profile_fingerprint": profile_fingerprint,
            "runtime_fingerprint": prerequisites.legacy_runtime_fingerprint,
            "config_fingerprint": config_fingerprint,
            "data_role_fingerprint": (
                prerequisites.original_database_fingerprint
            ),
            "nonce": nonce,
            "port": 8765,
            "primary_provider": config.primary_provider,
            "fallback_provider": config.fallback_provider,
            "reads_environment": config.reads_environment,
        }
        for name, item in assignments.items():
            object.__setattr__(value, name, item)
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class LegacyServiceRecoveryReceiptV1:
    status: str
    nonce: str = field(repr=False)
    start_fingerprint: str = field(repr=False)
    health_fingerprint: str = field(repr=False)
    attempts: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("LegacyServiceRecoveryReceiptV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        nonce: object,
        start_fingerprint: object,
        health_fingerprint: object,
    ):
        if (
            not is_uuid4(nonce)
            or not is_fingerprint(start_fingerprint)
            or not is_fingerprint(health_fingerprint)
        ):
            fail(_ERROR)
        body = {
            "receipt_type": "LegacyServiceRecoveryReceiptV1",
            "status": "LEGACY_SERVICE_RECOVERED",
            "nonce_fingerprint": fingerprint(
                "issue58-legacy-nonce-v1", nonce, code=_ERROR
            ),
            "start_fingerprint": start_fingerprint,
            "health_fingerprint": health_fingerprint,
            "attempts": 1,
        }
        value = object.__new__(cls)
        object.__setattr__(value, "status", body["status"])
        object.__setattr__(value, "nonce", nonce)
        object.__setattr__(value, "start_fingerprint", start_fingerprint)
        object.__setattr__(value, "health_fingerprint", health_fingerprint)
        object.__setattr__(value, "attempts", 1)
        object.__setattr__(
            value,
            "receipt_fingerprint",
            fingerprint("issue58-legacy-receipt-v1", body, code=_ERROR),
        )
        return value

