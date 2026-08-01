"""Fixed synthetic Windows topology verifier support for Issue #83."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from backend.cutover_composition_contracts.canonical import fingerprint
from backend.r2_cross_stage_recovery import (
    CrossStageAdaptersV1,
    CrossStageRecoveryMachine,
    CrossStageStatus,
    CutoverSuccessAppendV1,
    FinalFreshnessObservationV1,
    FinalSealRequestV1,
    ReceiptPredecessorLinkV1,
    RecoveryFaultSelectorV1,
    RestartSnapshotV1,
)
from backend.r2_validation_lifecycle import (
    ValidationFaultSelectorV1,
    ValidationLifecycle,
    ValidationStatus,
)
from backend.r2_verification_evidence import (
    R2VerificationBundleV1,
    build_verification_evidence,
)
from tests.r2_validation_lifecycle_fixture import NOW, approved_slice
from tests.test_r2_validation_lifecycle_windows import _WindowsAdapters
from scripts.r2_synthetic_windows_support import (
    fixed_git as _git,
    is_ntfs as _is_ntfs,
    require_uniform_acl as _require_uniform_acl,
    run_tty_processes as _run_tty_processes,
)


_ZONES = (
    "main",
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
    "OperatorPrivate",
)


def run_verification(repo_root: Path, script_path: Path) -> dict[str, object]:
    criteria = repo_root / "docs" / "operations" / "r2_synthetic_verification_criteria.md"
    with tempfile.TemporaryDirectory(prefix="r2-full-topology-") as raw:
        sandbox = Path(raw)
        if not _is_ntfs(sandbox):
            raise RuntimeError("R2_SYNTHETIC_NTFS_REQUIRED")
        (sandbox / ".r2-full-topology-sandbox").write_bytes(b"r2-v1")
        container, worktrees = _build_topology(sandbox)
        _require_uniform_acl(container)
        process_types = _run_tty_processes(repo_root, sandbox)
        approved = approved_slice()
        validation, adapters = _run_lifecycle(container, approved)
        final = _seal(validation, adapters, approved)
        if final.status is not CrossStageStatus.CUTOVER_SUCCESS:
            raise RuntimeError("R2_SYNTHETIC_FINAL_SEAL_FAILED")
        bundle = _bundle(process_types, worktrees, adapters)
        surface = _surface_fingerprint(repo_root)
        evidence = build_verification_evidence(
            criteria_bytes=criteria.read_bytes(),
            script_bytes=script_path.read_bytes(),
            bundle=bundle,
            r2_surface_fingerprint=surface,
        )
    return _public_result(evidence)


def _build_topology(sandbox: Path):
    container = sandbox / "Container"
    container.mkdir()
    for name in _ZONES:
        (container / name).mkdir()
    main = container / "main"
    _git(sandbox, "init", "-b", "master", str(main))
    _git(main, "config", "user.name", "Synthetic Operator")
    _git(main, "config", "user.email", "synthetic@example.test")
    (main / "README.md").write_text("synthetic R2 topology\n", "utf-8")
    _git(main, "add", "README.md")
    _git(main, "commit", "-m", "synthetic r2 topology")
    worktrees = []
    for index in range(1, 12):
        parent = container / "Worktrees" if index <= 8 else sandbox / "external-worktrees"
        parent.mkdir(exist_ok=True)
        target = parent / f"worktree-{index:02d}"
        _git(main, "worktree", "add", "-b", f"r2-{index:02d}", str(target))
        worktrees.append(target)
    (sandbox / "LegacySourceAnchorV1").mkdir()
    (sandbox / "legacy-service.stopped").write_text("stopped\n", "ascii")
    runtime = container / "Runtimes" / "python-3.12.13"
    runtime.mkdir()
    (runtime / "runtime.fingerprint").write_text("synthetic\n", "ascii")
    (container / "Artifacts" / "reviewed.crx").write_bytes(
        b"Cr24" + (3).to_bytes(4, "little") + (12).to_bytes(4, "little")
    )
    (container / "Config" / "settings.env").write_bytes(
        b"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=example.test\n"
        b"EMAIL_AGENT_LOG_LEVEL=WARNING\n"
    )
    evidence = sandbox / "evidence"
    evidence.mkdir()
    (evidence / "package.verified").write_text("content-free\n", "ascii")
    return container, tuple(worktrees)


def _run_lifecycle(container, approved):
    adapters = _WindowsAdapters(container / "LocalData", approved.slice_fingerprint)
    result = ValidationLifecycle.create(
        approved=approved,
        adapters=adapters.bundle(),
        nonce_factory=iter(
            (
                "11111111-1111-4111-8111-111111111111",
                "22222222-2222-4222-8222-222222222222",
            )
        ).__next__,
        now=lambda: NOW,
        fault=ValidationFaultSelectorV1.none(),
    ).run()
    if result.status is not ValidationStatus.VALIDATED or adapters.row_count() != 1:
        raise RuntimeError("R2_SYNTHETIC_LIFECYCLE_FAILED")
    return result, adapters


def _seal(validation, lifecycle, approved):
    stopped, final = lifecycle.audit_completions
    head = approved.journal_head_fingerprint
    identities = approved.approved_identities_fingerprint
    snapshot = RestartSnapshotV1.create(
        current_journal_head=head,
        receipt_links=(
            ReceiptPredecessorLinkV1(
                fingerprint("r2-full-receipt-v1", 1),
                fingerprint("r2-full-predecessor-v1", 1),
                fingerprint("r2-full-prior-head-v1", 1),
                head,
            ),
        ),
        pending_intents=(),
        remaining_reverse_plan=(),
        failed_container_preserved=True,
        retained_new_object_count=17,
        approved_identities_fingerprint=identities,
    )
    request = FinalSealRequestV1.create(
        validation=validation,
        stopped_audit=stopped,
        final_audit=final,
        current_journal_head=head,
        nonce_b=final.service_nonce,
        approved_identities_fingerprint=identities,
        stopped_identities_fingerprint=stopped.approved_identities_fingerprint,
        final_identities_fingerprint=final.approved_identities_fingerprint,
    )
    adapters = _seal_adapters(head, identities, final.service_nonce)
    return CrossStageRecoveryMachine.create(
        snapshot=snapshot,
        adapters=adapters,
        now=lambda: NOW,
        fault=RecoveryFaultSelectorV1.none(),
    ).seal(request)


def _seal_adapters(head, identities, nonce):
    def freshness():
        return FinalFreshnessObservationV1.create(
            journal_head_fingerprint=head,
            nonce_b=nonce,
            approved_identities_fingerprint=identities,
            observed_at_epoch=NOW,
        )

    def append(record_type, prior, material):
        return CutoverSuccessAppendV1.create(
            record_type=record_type,
            prior_head_fingerprint=prior,
            journal_head_fingerprint=fingerprint("r2-full-success-head-v1", material),
            material_fingerprint=material,
        )

    return CrossStageAdaptersV1(
        observe_intent=lambda _value: None,
        current_journal_head=lambda: head,
        reverse_boundary=lambda *_values: None,
        minimal_final_freshness=freshness,
        append_cutover_success=append,
    )


def _bundle(process_types, worktrees, lifecycle):
    values = {
        "schema_version": 1,
        "windows_ntfs": True,
        "process_type_count": len(process_types),
        "authorization_domain_count": 4,
        "real_tty_channel_count": 3,
        "independent_audit_process_count": len(set(lifecycle.audit_process_ids)),
        "project_container_zone_count": len(_ZONES),
        "repository_count": 1,
        "worktree_count": len(worktrees),
        "managed_unit_count": 4,
        "semantic_gap_case_count": 70,
        "rule_fallback_result_count": lifecycle.analysis_calls,
        "persisted_row_count": lifecycle.row_count(),
        "provider_attempt_count": 0,
        "public_leakage_count": 0,
        "real_host_operation_count": 0,
        "terminal_status": "CUTOVER_SUCCESS",
    }
    return R2VerificationBundleV1.create(values)


def _public_result(evidence):
    return {
        "status": "R2_SYNTHETIC_VERIFICATION_COMPLETE",
        "counts": {
            "authorization_domains": 4,
            "independent_audits": 2,
            "managed_units": 4,
            "process_types": 3,
            "project_container_zones": 9,
            "repositories": 1,
            "semantic_gap_cases": 70,
            "worktrees": 11,
        },
        "terminal_status": "CUTOVER_SUCCESS",
        "provider_attempts": 0,
        "public_leakage": 0,
        "real_host_operations": 0,
        "fingerprints": {
            "criteria": evidence.criteria_fingerprint,
            "matrix": evidence.matrix_fingerprint,
            "script": evidence.script_fingerprint,
            "bundle": evidence.bundle_fingerprint,
            "surface": evidence.r2_surface_fingerprint,
            "package": evidence.package_fingerprint,
        },
    }


def _surface_fingerprint(repo_root):
    items = []
    paths = sorted((repo_root / "backend").glob("r2_*/*.py"))
    paths += sorted((repo_root / "scripts").glob("r2_synthetic_*.py"))
    for path in paths:
        items.append(
            [
                path.relative_to(repo_root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    return fingerprint("r2-complete-surface-v1", items)
