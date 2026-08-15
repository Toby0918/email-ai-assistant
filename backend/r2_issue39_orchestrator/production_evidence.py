"""Content-free create-only evidence package for the fixed Issue #39 run."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from backend.cutover_managed_activation.canonical import (
    canonical_json as runtime_canonical_json,
)

from .durable_io import guard_directory, read_segment, write_segment
from .preparation import Issue39PrepareStatusV1, Issue39PreparedExecutionV1


_EVIDENCE_PARENT = Path(
    r"D:\IncidentArchives\email_ai_assistant\issue38\issue39-evidence-v1"
)
_FILE = "migration-evidence-manifest-v1.json"
_RUNTIME_FILE = "approved-cpython-source-v1.json"
_RUNNER_FILE = "issue39-cutover-runner-v1.pyz"


@dataclass(frozen=True, slots=True, repr=False)
class Issue39EvidencePackageV1:
    reviewed_evidence_fingerprint: str = field(repr=False)
    evidence_identity_fingerprint: str = field(repr=False)
    package_fingerprint: str = field(repr=False)
    manifest_fingerprint: str = field(repr=False)
    payload: bytes = field(repr=False)
    runtime_source_manifest: bytes = field(repr=False)
    restart_anchor: bytes = field(repr=False)


def prepare_fixed_issue39_evidence_v1(prepared, catalog, closure, preflight):
    from .production_preflight import Issue39PreflightReceiptV1
    from .closure_binding import _Issue39ClosureBindingV1

    if (
        type(prepared) is not Issue39PreparedExecutionV1
        or prepared.status is not Issue39PrepareStatusV1.VERIFIED
        or catalog.worktree_count != prepared.worktree_count
        or type(closure) is not _Issue39ClosureBindingV1
        or type(preflight) is not Issue39PreflightReceiptV1
        or len(preflight.observation_fingerprints) != 3
    ):
        raise TypeError("R2_ISSUE39_EVIDENCE_PREPARE_INVALID")
    body = _evidence_body(prepared, catalog, closure, preflight)
    runtime_manifest = _runtime_manifest(prepared)
    from .production_anchor_package import build_restart_anchor

    restart_anchor = build_restart_anchor()
    body["restart_anchor_sha256"] = hashlib.sha256(restart_anchor).hexdigest()
    payload = _canonical(body)
    combined = payload + b"\0" + runtime_manifest + b"\0" + restart_anchor
    reviewed = _fingerprint("r2-issue39-reviewed-evidence-v1", combined)
    identity = _fingerprint("r2-issue39-evidence-identity-v1", combined)
    package = _fingerprint("r2-issue39-evidence-package-v1", combined)
    manifest = _fingerprint("r2-issue39-evidence-manifest-v1", payload)
    return Issue39EvidencePackageV1(
        reviewed, identity, package, manifest, payload, runtime_manifest,
        restart_anchor,
    )


def _evidence_body(prepared, catalog, closure, preflight):
    from .production_repository import review_repository_manifest
    from .production_service import observe_legacy_service

    binding = closure.production
    return {
        "schema": "issue39-migration-evidence-v1",
        "production_binding_fingerprint": binding.binding_fingerprint,
        "prepare_fingerprint": prepared.prepare_fingerprint,
        "closure_fingerprint": prepared._closure.closure_fingerprint,
        "production_input_manifest_fingerprint": (
            prepared._inputs.manifest_sha256
        ),
        "roster_fingerprint": prepared._roster.roster_fingerprint,
        "catalog_fingerprint": catalog.catalog_fingerprint,
        "preflight_receipt_fingerprint": preflight.receipt_fingerprint,
        "preflight_observation_fingerprints": list(
            preflight.observation_fingerprints
        ),
        "action_count": catalog.action_count,
        "worktree_count": prepared.worktree_count,
        "provider_attempt_count": 0,
        "private_data_access_count": 0,
        "cleanup_count": 0,
        "deletion_count": 0,
        "closure_manifest": closure.manifest.to_mapping(),
        "attestation_receipt": closure.receipt.to_mapping(),
        "prepared": _prepared_mapping(prepared),
        "before_evidence_preflight": {
            "subject_fingerprint": preflight.subject_fingerprint,
            "ledger_head_fingerprint": preflight.ledger_head_fingerprint,
            "observation_fingerprints": list(
                preflight.observation_fingerprints
            ),
            "receipt_fingerprint": preflight.receipt_fingerprint,
        },
        "repository_manifest": review_repository_manifest(
            prepared._roster._root
        ).to_mapping(),
        "legacy_service": observe_legacy_service(prepared._roster._root),
    }


def _prepared_mapping(prepared):
    inputs = prepared._inputs
    roster = prepared._roster
    return {
        "status": prepared.status.value,
        "prepare_fingerprint": prepared.prepare_fingerprint,
        "counts": list(prepared.counts()),
        "closure": {
            "closure_eligible": prepared._closure.closure_eligible,
            "issue38_closed": prepared._closure.issue38_closed,
            "incident_archived": prepared._closure.incident_archived,
            "closure_fingerprint": prepared._closure.closure_fingerprint,
        },
        "inputs": {
            name: getattr(inputs, name).value
            if name == "status" else getattr(inputs, name)
            for name in inputs.__dataclass_fields__
        },
        "roster": {
            "status": roster.status.value,
            "roster_fingerprint": roster.roster_fingerprint,
            "root": str(roster._root),
            "worktrees": [
                {
                    "role": item.role,
                    "placement": item.placement,
                    "selection_fingerprint": item.selection_fingerprint,
                }
                for item in roster.worktrees
            ],
            "snapshot": [
                {
                    "path": str(item.path),
                    "placement": item.placement,
                    "identity_fingerprint": item.identity_fingerprint,
                    "admin_identity_fingerprint": item.admin_identity_fingerprint,
                    "admin_content_fingerprint": item.admin_content_fingerprint,
                    "head_oid": item.head_oid,
                    "branch_fingerprint": item.branch_fingerprint,
                    "common_fingerprint": item.common_fingerprint,
                    "status_fingerprint": item.status_fingerprint,
                    "clean": item.clean,
                    "admin_path": str(item.admin_path),
                    "common_path": str(item.common_path),
                }
                for item in roster._snapshot
            ],
        },
    }


def _runtime_manifest(prepared):
    return runtime_canonical_json(
        {
            "source_type": "approved-cpython-source/v1",
            "python_version": "3.12.13",
            "sqlite_version": "3.50.4",
            "source_tree_fingerprint": prepared._inputs.runtime_tree_fingerprint,
            "source_entry_count": prepared._inputs.runtime_entry_count,
            "source_total_bytes": prepared._inputs.runtime_total_bytes,
            "executable_name": "python.exe",
            "executable_sha256": prepared._inputs.runtime_fingerprint,
        },
        code="R2_ISSUE39_RUNTIME_MANIFEST_INVALID",
    )


def fixed_issue39_evidence_location_v1(package):
    if type(package) is not Issue39EvidencePackageV1:
        raise TypeError("R2_ISSUE39_EVIDENCE_LOCATION_INVALID")
    return _EVIDENCE_PARENT / f"evidence-{package.package_fingerprint}"


def publish_fixed_issue39_evidence_v1(package):
    location = fixed_issue39_evidence_location_v1(package)
    if os.path.lexists(location) or not location.parent.is_dir():
        raise TypeError("R2_ISSUE39_EVIDENCE_PUBLICATION_BLOCKED")
    from backend.cutover_host_mutation.roles import AclRole
    from backend.cutover_host_mutation.windows_acl_apply import exact_container_policy
    from backend.cutover_host_mutation.windows_security import WindowsSecurityApi
    from backend.r2_main_publication.windows_dacl import apply_exact_dacl
    from .production_acl import _fixed_dacls
    from .production_native import create_directory_no_replace

    identity = create_directory_no_replace(location.parent, location)
    principals, explicit, _inherited = _fixed_dacls()
    apply_exact_dacl(
        location, expected_identity=identity, dacl=explicit, protected=True
    )
    captured = WindowsSecurityApi().capture(location, role=AclRole.PROJECT_CONTAINER)
    if not exact_container_policy(captured, principals):
        raise ValueError("R2_ISSUE39_EVIDENCE_DACL_INVALID")
    with guard_directory(location, flush=True):
        write_segment(location / _FILE, package.payload)
        write_segment(location / _RUNTIME_FILE, package.runtime_source_manifest)
        write_segment(location / _RUNNER_FILE, package.restart_anchor)
        _verify(location, package)
    return location


def verify_fixed_issue39_evidence_v1(package):
    location = fixed_issue39_evidence_location_v1(package)
    with guard_directory(location, flush=False):
        _require_evidence_dacl(location)
        _verify(location, package)
    return True


def _require_evidence_dacl(location):
    from backend.cutover_host_mutation.roles import AclRole
    from backend.cutover_host_mutation.windows_acl_apply import exact_container_policy
    from backend.cutover_host_mutation.windows_security import WindowsSecurityApi
    from .production_acl import _fixed_dacls

    principals, _explicit, _inherited = _fixed_dacls()
    captured = WindowsSecurityApi().capture(
        location, role=AclRole.PROJECT_CONTAINER
    )
    if not exact_container_policy(captured, principals):
        raise ValueError("R2_ISSUE39_EVIDENCE_DACL_INVALID")


def _verify(location, package):
    if tuple(sorted(item.name for item in location.iterdir())) != tuple(
        sorted((_FILE, _RUNTIME_FILE, _RUNNER_FILE))
    ):
        raise ValueError
    payload = read_segment(location / _FILE)
    if payload != package.payload:
        raise ValueError
    runtime_manifest = read_segment(location / _RUNTIME_FILE)
    if runtime_manifest != package.runtime_source_manifest:
        raise ValueError
    source = json.loads(payload)
    if _canonical(source) != payload:
        raise ValueError
    restart_anchor = read_segment(location / _RUNNER_FILE)
    if restart_anchor != package.restart_anchor:
        raise ValueError
    combined = payload + b"\0" + runtime_manifest + b"\0" + restart_anchor
    expected = (
        _fingerprint("r2-issue39-reviewed-evidence-v1", combined),
        _fingerprint("r2-issue39-evidence-identity-v1", combined),
        _fingerprint("r2-issue39-evidence-package-v1", combined),
        _fingerprint("r2-issue39-evidence-manifest-v1", payload),
    )
    if expected != (
        package.reviewed_evidence_fingerprint,
        package.evidence_identity_fingerprint,
        package.package_fingerprint,
        package.manifest_fingerprint,
    ):
        raise ValueError


def _canonical(value):
    return (
        json.dumps(
            value, ensure_ascii=True, allow_nan=False, sort_keys=True,
            separators=(",", ":"),
        ) + "\n"
    ).encode("ascii")


def _fingerprint(domain, payload):
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()
