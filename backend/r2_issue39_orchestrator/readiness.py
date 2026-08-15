"""Exact closure, Issue #38, and incident readiness observation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39ReadinessObservationV1:
    closure_eligible: bool
    issue38_closed: bool
    incident_archived: bool
    closure_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("Issue39ReadinessObservationV1 is observer-owned")

    def ready(self) -> bool:
        return (
            self.closure_eligible
            and self.issue38_closed
            and self.incident_archived
        )


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39ReadinessPorts:
    read_artifacts: object = field(repr=False)
    parse_manifest: object = field(repr=False)
    parse_receipt: object = field(repr=False)
    derive_current_manifest: object = field(repr=False)
    issue38_state: object = field(repr=False)
    incident_archived: object = field(repr=False)


def observe_fixed_issue39_readiness_v1() -> Issue39ReadinessObservationV1:
    """Read the fixed, content-free readiness facts without mutating GitHub."""

    return _observe_issue39_readiness_v1(ports=_production_ports())


def _observe_issue39_readiness_v1(*, ports):
    closure = False
    issue38_closed = False
    incident_archived = False
    closure_fingerprint = "0" * 64
    try:
        _require_ports(ports)
        manifest_payload, receipt_payload = ports.read_artifacts()
        manifest = ports.parse_manifest(manifest_payload)
        receipt = ports.parse_receipt(receipt_payload)
        current = ports.derive_current_manifest()
        closure = _closure_matches(manifest, receipt, current)
        if closure:
            closure_fingerprint = hashlib.sha256(
                b"r2-issue39-closure-readiness-v1\0"
                + bytes.fromhex(manifest.manifest_fingerprint)
                + bytes.fromhex(receipt.receipt_fingerprint)
            ).hexdigest()
        issue38_closed = ports.issue38_state() == "CLOSED"
        incident_archived = ports.incident_archived() is True
    except Exception:
        pass
    return _observation(
        closure,
        issue38_closed,
        incident_archived,
        closure_fingerprint,
    )


def _closure_matches(manifest, receipt, current) -> bool:
    fingerprints = (
        manifest.manifest_fingerprint,
        manifest.final_master_binding_fingerprint,
        manifest.production_binding_fingerprint,
        receipt.receipt_fingerprint,
    )
    return (
        all(_is_fingerprint(value) for value in fingerprints)
        and type(current) is type(manifest)
        and current.to_mapping() == manifest.to_mapping()
        and receipt.status == "SOLO_MAINTAINER_ATTESTATION_RECORDED"
        and receipt.manifest_fingerprint == manifest.manifest_fingerprint
        and receipt.final_master_binding_fingerprint
        == manifest.final_master_binding_fingerprint
        and receipt.final_commit_oid == manifest.final_commit_oid
        and receipt.final_tree_oid == manifest.final_tree_oid
        and receipt.production_binding_fingerprint
        == manifest.production_binding_fingerprint
        and manifest.issue39_authority_count == 0
        and manifest.execution_authority_count == 0
        and manifest.failure_count == 0
        and receipt.issue39_authority_count == 0
        and receipt.execution_authority_count == 0
    )


def _production_ports() -> _Issue39ReadinessPorts:
    from backend.r2_solo_maintainer_closure import (
        SoloMaintainerAttestationReceiptV1,
        SoloMaintainerClosureManifestV1,
    )
    from backend.r2_solo_maintainer_closure.closure import _manifest
    from backend.r2_solo_maintainer_closure.repository import (
        FixedGitHubPort,
        FixedRepositoryPort,
    )
    from backend.r2_solo_maintainer_closure.storage import read_closure_artifacts

    from .incident_verify import verify_fixed_incident_archive_v1

    from .github_readiness import read_fixed_issue38_state_v1

    def current_manifest():
        repository = FixedRepositoryPort().collect()
        github = FixedGitHubPort().collect(repository)
        return _manifest(repository, github)

    return _Issue39ReadinessPorts(
        read_closure_artifacts,
        SoloMaintainerClosureManifestV1.from_json,
        SoloMaintainerAttestationReceiptV1.from_json,
        current_manifest,
        read_fixed_issue38_state_v1,
        verify_fixed_incident_archive_v1,
    )


def _require_ports(ports) -> None:
    if type(ports) is not _Issue39ReadinessPorts or not all(
        callable(getattr(ports, name))
        for name in (
            "read_artifacts",
            "parse_manifest",
            "parse_receipt",
            "derive_current_manifest",
            "issue38_state",
            "incident_archived",
        )
    ):
        raise TypeError


def _is_fingerprint(value) -> bool:
    return type(value) is str and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def _observation(closure, issue38, incident, fingerprint):
    value = object.__new__(Issue39ReadinessObservationV1)
    for name, item in (
        ("closure_eligible", closure),
        ("issue38_closed", issue38),
        ("incident_archived", incident),
        ("closure_fingerprint", fingerprint),
    ):
        object.__setattr__(value, name, item)
    return value
