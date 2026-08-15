"""Strict reconstruction of one active run from its external evidence anchor."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path

from backend.r2_production_binding import ApprovedCutoverBindingV3
from backend.r2_production_binding._canonical import canonical_json as binding_json
from backend.r2_production_binding.review import require_reviewed_production_binding_v3
from backend.r2_solo_maintainer_closure import (
    FinalMasterBindingV1,
    SoloMaintainerAttestationReceiptV1,
    SoloMaintainerClosureManifestV1,
)
from backend.r2_solo_maintainer_closure._canonical import canonical_json as closure_json

from .action_catalog import build_fixed_production_action_catalog_v1
from .closure_binding import _Issue39ClosureBindingV1
from .durable_io import guard_directory, read_segment
from .preflight_ledger import _open_preflight_ledger_v1
from .preflight_progress import receipt, subject_fingerprint, validated_progress
from .preparation import (
    Issue39PrepareStatusV1,
    _allocate_prepared_execution_v1,
    _prepare_fingerprint,
)
from .production_evidence import (
    Issue39EvidencePackageV1,
    _FILE,
    _RUNNER_FILE,
    _RUNTIME_FILE,
    _canonical,
    _fingerprint,
    fixed_issue39_evidence_location_v1,
    verify_fixed_issue39_evidence_v1,
)
from .production_inputs import Issue39ProductionInputStatusV1, Issue39ProductionInputsV1
from .readiness import _observation
from .roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    Issue39WorktreeV1,
    _DiscoveredWorktree,
)


@dataclass(frozen=True, slots=True, repr=False)
class Issue39AnchorContextV1:
    prepared: object = field(repr=False)
    closure: object = field(repr=False)
    catalog: object = field(repr=False)
    package: object = field(repr=False)
    preflight: object = field(repr=False)


def current_process_is_fixed_anchor_v1():
    try:
        runner = Path(sys.argv[0]).absolute()
        from .production_evidence import _EVIDENCE_PARENT

        metadata = runner.lstat()
        parent = runner.parent.lstat()
        return (
            runner.name == _RUNNER_FILE
            and runner.parent.parent == _EVIDENCE_PARENT
            and runner.parent.name.startswith("evidence-")
            and stat.S_ISREG(metadata.st_mode)
            and stat.S_ISDIR(parent.st_mode)
            and not getattr(metadata, "st_file_attributes", 0) & 0x400
            and not getattr(parent, "st_file_attributes", 0) & 0x400
            and not runner.is_symlink()
            and not runner.parent.is_symlink()
            and not runner.parent.is_junction()
        )
    except OSError:
        return False


def load_current_anchor_context_v1():
    if not current_process_is_fixed_anchor_v1():
        raise TypeError("R2_ISSUE39_ANCHOR_CONTEXT_INVALID")
    runner = Path(sys.argv[0]).absolute()
    location = runner.parent
    with guard_directory(location.parent, flush=False):
        with guard_directory(location, flush=False):
            names = tuple(sorted(item.name for item in location.iterdir()))
            if names != tuple(sorted((_FILE, _RUNTIME_FILE, _RUNNER_FILE))):
                raise ValueError
            payload = read_segment(location / _FILE)
            runtime = read_segment(location / _RUNTIME_FILE)
            archive = read_segment(runner)
    body = json.loads(payload)
    if _canonical(body) != payload or not _valid_body(
        body, hashlib.sha256(archive).hexdigest()
    ):
        raise ValueError
    package = _package(payload, runtime, archive)
    expected = fixed_issue39_evidence_location_v1(package)
    if location != expected or runner != expected / _RUNNER_FILE:
        raise ValueError
    closure = _closure(body)
    prepared = _prepared(body)
    catalog = build_fixed_production_action_catalog_v1(prepared)
    if (
        catalog.catalog_fingerprint != body["catalog_fingerprint"]
        or closure.production.binding_fingerprint
        != body["production_binding_fingerprint"]
        or verify_fixed_issue39_evidence_v1(package) is not True
    ):
        raise ValueError
    subject = subject_fingerprint(prepared, closure, catalog)
    ledger = _open_preflight_ledger_v1(
        binding=closure.production, package_fingerprint=subject
    )
    completed = validated_progress(ledger, subject)
    before = receipt(subject, ledger, completed, 3)
    after = receipt(subject, ledger, completed, 5)
    if _receipt_mapping(before) != body["before_evidence_preflight"]:
        raise ValueError
    return Issue39AnchorContextV1(prepared, closure, catalog, package, after)


def _package(payload, runtime, archive):
    combined = payload + b"\0" + runtime + b"\0" + archive
    return Issue39EvidencePackageV1(
        _fingerprint("r2-issue39-reviewed-evidence-v1", combined),
        _fingerprint("r2-issue39-evidence-identity-v1", combined),
        _fingerprint("r2-issue39-evidence-package-v1", combined),
        _fingerprint("r2-issue39-evidence-manifest-v1", payload),
        payload, runtime, archive,
    )


def _closure(body):
    manifest = SoloMaintainerClosureManifestV1.from_json(
        closure_json(body["closure_manifest"])
    )
    attestation = SoloMaintainerAttestationReceiptV1.from_json(
        closure_json(body["attestation_receipt"])
    )
    final = FinalMasterBindingV1.from_mapping(manifest.final_master_binding)
    production = ApprovedCutoverBindingV3.from_json(
        binding_json(manifest.production_binding), final_master_binding=final
    )
    require_reviewed_production_binding_v3(final, production)
    if (
        attestation.manifest_fingerprint != manifest.manifest_fingerprint
        or attestation.production_binding_fingerprint != production.binding_fingerprint
    ):
        raise ValueError
    return _Issue39ClosureBindingV1(manifest, attestation, final, production)


def _prepared(body):
    source = body["prepared"]
    inputs_body = source["inputs"]
    inputs = Issue39ProductionInputsV1(
        Issue39ProductionInputStatusV1(inputs_body["status"]),
        *(inputs_body[name] for name in tuple(Issue39ProductionInputsV1.__dataclass_fields__)[1:]),
    )
    roster_body = source["roster"]
    worktrees = tuple(Issue39WorktreeV1(**item) for item in roster_body["worktrees"])
    snapshot = tuple(
        _DiscoveredWorktree(
            path=Path(item["path"]), placement=item["placement"],
            identity_fingerprint=item["identity_fingerprint"],
            admin_identity_fingerprint=item["admin_identity_fingerprint"],
            admin_content_fingerprint=item["admin_content_fingerprint"],
            head_oid=item["head_oid"], branch_fingerprint=item["branch_fingerprint"],
            common_fingerprint=item["common_fingerprint"],
            status_fingerprint=item["status_fingerprint"], clean=item["clean"],
            admin_path=Path(item["admin_path"]),
            common_path=Path(item["common_path"]),
        )
        for item in roster_body["snapshot"]
    )
    roster = Issue39BoundRosterV1(
        Issue39RosterStatusV1(roster_body["status"]), worktrees,
        roster_body["roster_fingerprint"], Path(roster_body["root"]), snapshot,
    )
    closure_body = source["closure"]
    readiness = _observation(
        closure_body["closure_eligible"], closure_body["issue38_closed"],
        closure_body["incident_archived"], closure_body["closure_fingerprint"],
    )
    counts = tuple(source["counts"])
    result = _allocate_prepared_execution_v1(
        Issue39PrepareStatusV1.VERIFIED, source["prepare_fingerprint"],
        *counts, readiness, inputs, roster,
    )
    if (
        _prepare_fingerprint(readiness, inputs, roster) != result.prepare_fingerprint
        or result.prepare_fingerprint != body["prepare_fingerprint"]
    ):
        raise ValueError
    return result


def _receipt_mapping(value):
    return {
        "subject_fingerprint": value.subject_fingerprint,
        "ledger_head_fingerprint": value.ledger_head_fingerprint,
        "observation_fingerprints": list(value.observation_fingerprints),
        "receipt_fingerprint": value.receipt_fingerprint,
    }


def _valid_body(body, archive_sha256):
    required = {
        "schema", "production_binding_fingerprint", "prepare_fingerprint",
        "closure_fingerprint", "production_input_manifest_fingerprint",
        "roster_fingerprint", "catalog_fingerprint",
        "preflight_receipt_fingerprint", "preflight_observation_fingerprints",
        "action_count", "worktree_count", "provider_attempt_count",
        "private_data_access_count", "cleanup_count", "deletion_count",
        "closure_manifest", "attestation_receipt", "prepared",
        "before_evidence_preflight", "restart_anchor_sha256",
        "repository_manifest",
        "legacy_service",
    }
    return (
        type(body) is dict and set(body) == required
        and body["schema"] == "issue39-migration-evidence-v1"
        and body["restart_anchor_sha256"] == archive_sha256
        and all(body[name] == 0 for name in (
            "provider_attempt_count", "private_data_access_count",
            "cleanup_count", "deletion_count",
        ))
    )
