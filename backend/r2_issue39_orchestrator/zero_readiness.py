"""Zero-mutation readiness before the optional incident disposition."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from .production_inputs import (
    Issue39ProductionInputStatusV1,
    verify_fixed_production_inputs_v1,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39ZeroMutationReadinessV1:
    baseline_eligible: bool
    incident_state: str
    readiness_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39ZeroMutationReadinessV1 is observer-owned")

    def ready(self):
        return self.baseline_eligible and self.incident_state in {
            "SOURCE_VERIFIED", "ARCHIVED"
        }


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39ZeroReadinessPortsV1:
    current: object = field(repr=False)
    artifacts: object = field(repr=False)
    parse_manifest: object = field(repr=False)
    parse_receipt: object = field(repr=False)
    inputs: object = field(repr=False)
    incident: object = field(repr=False)
    issue38: object = field(repr=False)


def observe_fixed_issue39_zero_mutation_readiness_v1():
    return _observe_zero_mutation_readiness_v1(_production_ports())


def _observe_zero_mutation_readiness_v1(ports):
    try:
        from .readiness import _closure_matches

        if type(ports) is not _Issue39ZeroReadinessPortsV1:
            raise TypeError
        current = ports.current()
        manifest_payload, receipt_payload = ports.artifacts()
        manifest = ports.parse_manifest(manifest_payload)
        receipt = ports.parse_receipt(receipt_payload)
        inputs = ports.inputs()
        incident = ports.incident()
        eligible = (
            _closure_matches(manifest, receipt, current)
            and ports.issue38() == "CLOSED"
            and current.failure_count == 0
            and current.issue39_authority_count == 0
            and current.execution_authority_count == 0
            and inputs.status is Issue39ProductionInputStatusV1.READY
        )
        fingerprint = hashlib.sha256(
            b"r2-issue39-zero-mutation-readiness-v1\0"
            + bytes.fromhex(current.manifest_fingerprint)
            + bytes.fromhex(receipt.receipt_fingerprint)
            + bytes.fromhex(inputs.manifest_sha256)
            + incident.encode("ascii")
        ).hexdigest()
        return _allocate(eligible, incident, fingerprint)
    except Exception:
        return _allocate(False, "BLOCKED", "0" * 64)


def _production_ports():
    from backend.r2_solo_maintainer_closure import (
        SoloMaintainerAttestationReceiptV1,
        SoloMaintainerClosureManifestV1,
    )
    from backend.r2_solo_maintainer_closure.closure import _manifest
    from backend.r2_solo_maintainer_closure.repository import (
        FixedGitHubPort, FixedRepositoryPort,
    )
    from backend.r2_solo_maintainer_closure.storage import read_closure_artifacts
    from .github_readiness import read_fixed_issue38_state_v1
    from .incident_verify import observe_fixed_incident_state_v1

    def current():
        repository = FixedRepositoryPort().collect()
        return _manifest(repository, FixedGitHubPort().collect(repository))

    return _Issue39ZeroReadinessPortsV1(
        current, read_closure_artifacts,
        SoloMaintainerClosureManifestV1.from_json,
        SoloMaintainerAttestationReceiptV1.from_json,
        verify_fixed_production_inputs_v1, observe_fixed_incident_state_v1,
        read_fixed_issue38_state_v1,
    )


def _allocate(eligible, incident, fingerprint):
    value = object.__new__(Issue39ZeroMutationReadinessV1)
    for name, item in (
        ("baseline_eligible", eligible),
        ("incident_state", incident),
        ("readiness_fingerprint", fingerprint),
    ):
        object.__setattr__(value, name, item)
    return value
