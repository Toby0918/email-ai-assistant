"""One-shot dedicated provider-disabled legacy recovery runner."""

from __future__ import annotations

import uuid

from .canonical import fail, fingerprint
from .contracts import ServiceHealthEvidenceV1, ServiceStartEvidenceV1
from .legacy_contracts import (
    LegacyServiceRecoveryReceiptV1,
    LegacyServiceStartRequestV1,
)
from .rollback_contracts import LegacyPrerequisiteEvidenceV1


def run_legacy_recovery(
    *,
    adapter: object,
    profile_fingerprint: str,
    prerequisites: object,
    activation_nonce: str | None,
) -> LegacyServiceRecoveryReceiptV1:
    if type(prerequisites) is not LegacyPrerequisiteEvidenceV1:
        fail("legacy_recovery_not_available")
    nonce = str(uuid.uuid4())
    if nonce == activation_nonce:
        fail("legacy_recovery_nonce_invalid")
    request = LegacyServiceStartRequestV1.create(
        profile_fingerprint=profile_fingerprint,
        prerequisites=prerequisites,
        nonce=nonce,
    )
    try:
        start = adapter.start_provider_disabled_recovery(request)
        _validate_start(request, start)
        health = adapter.read_health(start)
        _validate_health(start, health)
    except Exception:
        fail("legacy_service_recovery_failed")
    return LegacyServiceRecoveryReceiptV1.create(
        nonce=nonce,
        start_fingerprint=_evidence_fingerprint("start", start),
        health_fingerprint=_evidence_fingerprint("health", health),
    )


def _validate_start(request, start) -> None:
    if type(start) is not ServiceStartEvidenceV1:
        fail("legacy_service_recovery_failed")
    expected = {
        "role": request.role,
        "profile_fingerprint": request.profile_fingerprint,
        "runtime_fingerprint": request.runtime_fingerprint,
        "executable_fingerprint": request.runtime_fingerprint,
        "config_fingerprint": request.config_fingerprint,
        "data_role_fingerprint": request.data_role_fingerprint,
        "nonce": request.nonce,
        "port": request.port,
    }
    if any(getattr(start, name) != item for name, item in expected.items()):
        fail("legacy_service_recovery_failed")


def _validate_health(start, health) -> None:
    if (
        type(health) is not ServiceHealthEvidenceV1
        or health.to_mapping() != {**start.to_mapping(), "healthy": True}
    ):
        fail("legacy_service_recovery_failed")


def _evidence_fingerprint(kind: str, evidence: object) -> str:
    return fingerprint(
        f"issue58-legacy-{kind}-v1",
        evidence.to_mapping(),
        code="legacy_service_recovery_failed",
    )

