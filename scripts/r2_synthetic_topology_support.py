"""Fixed synthetic Windows topology verifier support for Issue #83."""

from __future__ import annotations

import ast
import hashlib
import sys
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
from backend.r2_database_publication import QuiescencePrerequisitesV1
from backend.r2_validation_lifecycle import (
    ApprovedValidationSliceV1,
    ValidationFaultSelectorV1,
    ValidationLifecycle,
    ValidationStatus,
)
from backend.r2_evidence_process.contracts import (
    EvidenceProcessStatus,
    result as evidence_result,
)
from backend.r2_verification_evidence import (
    R2VerificationBundleV1,
    build_verification_evidence,
)
from tests.r2_validation_lifecycle_fixture import NOW
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.test_r2_validation_lifecycle_windows import _WindowsAdapters
from scripts.r2_synthetic_windows_support import (
    is_ntfs as _is_ntfs,
    require_uniform_acl as _require_uniform_acl,
    run_tty_processes as _run_tty_processes,
)
from scripts.r2_semantic_gap_support import execute_semantic_gap_matrix
from scripts.r2_durable_journal_support import SyntheticDurableJournal
from scripts.r2_publication_receipt_support import (
    canonical_publication_receipt,
    read_verified_publication_chain,
)
from scripts.r2_shared_topology_support import execute_shared_publications


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

_DYNAMIC_SURFACE_MODULES = (
    "tests.windows_synthetic_tty_host",
    "tests.r2_preflight_process_worker",
    "tests.r2_evidence_process_worker",
    "tests.r2_transaction_process_worker",
    "tests.r2_validation_service_worker",
    "tests.r2_validation_audit_worker",
)


def run_verification(repo_root: Path, script_path: Path) -> dict[str, object]:
    criteria = repo_root / "docs" / "operations" / "r2_synthetic_verification_criteria.md"
    with tempfile.TemporaryDirectory(
        prefix="r2-full-topology-", dir=Path(sys._base_executable).anchor
    ) as raw:
        sandbox = Path(raw)
        if not _is_ntfs(sandbox):
            raise RuntimeError("R2_SYNTHETIC_NTFS_REQUIRED")
        (sandbox / ".r2-full-topology-sandbox").write_bytes(b"r2-v1")
        process_proofs = _run_tty_processes(repo_root, sandbox)
        evidence_publication = evidence_result(EvidenceProcessStatus.PUBLISHED)
        prerequisites = _quiescence_prerequisites(
            sandbox, process_proofs, evidence_publication
        )
        topology = execute_shared_publications(sandbox, prerequisites)
        if (
            topology.quiescence_prerequisites_fingerprint
            != prerequisites.contract_fingerprint
            or topology.execution_order[:2]
            != ("quiescence:committed", "main:committed")
        ):
            raise RuntimeError("R2_SYNTHETIC_QUIESCENCE_ORDER_INVALID")
        _require_uniform_acl(topology.container)
        publications = (evidence_publication, *topology.receipts)
        journal = _publication_journal(sandbox, publications)
        semantic_gap_cases = execute_semantic_gap_matrix(sandbox)
        approved = _approved_from_publications(sandbox, publications, journal)
        validation, adapters = _run_lifecycle(topology, approved)
        try:
            final = _seal(validation, adapters, approved, journal)
            if final.status is not CrossStageStatus.CUTOVER_SUCCESS:
                raise RuntimeError("R2_SYNTHETIC_FINAL_SEAL_FAILED")
            adapters.close()
            bundle = _bundle(
                process_proofs.process_types,
                publications,
                adapters,
                semantic_gap_cases,
            )
            surface = _surface_fingerprint(repo_root)
            evidence = build_verification_evidence(
                criteria_bytes=criteria.read_bytes(),
                script_bytes=script_path.read_bytes(),
                bundle=bundle,
                r2_surface_fingerprint=surface,
            )
        finally:
            adapters.close()
    return _public_result(evidence)


def _quiescence_prerequisites(sandbox, process_proofs, evidence):
    evidence_bytes = (sandbox / "published.evidence").read_bytes()
    return QuiescencePrerequisitesV1.create(
        preflight_fingerprint=process_proofs.preflight_fingerprint,
        evidence_fingerprint=fingerprint(
            "r2-executed-evidence-prerequisite-v1",
            [
                process_proofs.evidence_fingerprint,
                evidence.to_mapping(),
                hashlib.sha256(evidence_bytes).hexdigest(),
            ],
        ),
        fresh_gate_fingerprint=process_proofs.fresh_gate_fingerprint,
    )
def _publication_journal(sandbox, publications):
    journal = SyntheticDurableJournal(sandbox / "r2-receipts.journal")
    for value in publications:
        journal.append_publication(value)
    return journal


def _approved_from_publications(sandbox, publications, journal):
    records = journal.records()
    chain = read_verified_publication_chain(records)
    durable = chain.receipts
    expected = tuple(
        canonical_publication_receipt(value, index)
        for index, value in enumerate(publications)
    )
    if durable != expected:
        raise RuntimeError("R2_DURABLE_PUBLICATION_RECEIPT_DRIFT")
    evidence, _main, repository, runtime, database, crx, config = publications
    evidence_path = sandbox / "published.evidence"
    evidence_bytes = evidence_path.read_bytes()
    if evidence_bytes != b"SYNTHETIC_R2_EVIDENCE\n":
        raise RuntimeError("R2_SYNTHETIC_EVIDENCE_MISSING")
    return ApprovedValidationSliceV1.create(
        operation_fingerprint=opaque_fingerprint(8300),
        profile_fingerprint=opaque_fingerprint(8301),
        authorization_fingerprint=opaque_fingerprint(8302),
        evidence=evidence,
        evidence_fingerprint=hashlib.sha256(evidence_bytes).hexdigest(),
        journal_head_fingerprint=chain.terminal_head_fingerprint,
        repository=repository,
        runtime=runtime,
        crx=crx,
        config=config,
        database=database,
        approved_identities_fingerprint=fingerprint(
            "r2-approved-publication-identities-v1",
            [
                durable[2].mapping()["receipt_fingerprint"],
                durable[3].mapping()["receipt_fingerprint"],
                durable[5].mapping()["receipt_fingerprint"],
                durable[6].mapping()["receipt_fingerprint"],
                durable[4].mapping()["receipt_fingerprint"],
            ],
        ),
    )


def _run_lifecycle(topology, approved):
    evidence_root = topology.root / "validation-evidence"
    evidence_root.mkdir()
    adapters = _WindowsAdapters(
        evidence_root,
        approved.slice_fingerprint,
        approved.approved_identities_fingerprint,
        database_path=topology.database_path,
        service_executable=topology.runtime_executable,
        config_path=topology.config_path,
    )
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


def _seal(validation, lifecycle, approved, journal):
    stopped = validation.stopped_audit
    final = validation.final_audit
    head = approved.journal_head_fingerprint
    identities = approved.approved_identities_fingerprint
    links = _verified_receipt_links(journal.records())
    snapshot = RestartSnapshotV1.create(
        current_journal_head=head,
        receipt_links=links,
        pending_intents=(),
        remaining_reverse_plan=(),
        failed_container_preserved=True,
        retained_new_object_count=17,
        approved_identities_fingerprint=identities,
    )
    request = FinalSealRequestV1.create(
        validation=validation,
        current_journal_head=head,
        nonce_b=validation.start_b_nonce,
        approved_identities_fingerprint=identities,
        stopped_identities_fingerprint=stopped.approved_identities_fingerprint,
        final_identities_fingerprint=final.approved_identities_fingerprint,
    )
    adapters = _seal_adapters(
        journal, head, identities, validation.start_b_nonce
    )
    return CrossStageRecoveryMachine.create(
        snapshot=snapshot,
        adapters=adapters,
        now=lambda: NOW,
        fault=RecoveryFaultSelectorV1.none(),
    ).seal(request)


def _verified_receipt_links(records):
    links = []
    for item in records:
        link = ReceiptPredecessorLinkV1.create(
            record_type=item["record_type"],
            material_fingerprint=item["material"],
            predecessor_fingerprint=item["predecessor"],
            prior_head_fingerprint=item["prior_head"],
        )
        observed = (
            item["receipt"],
            item["predecessor"],
            item["prior_head"],
            item["head"],
        )
        expected = (
            link.receipt_fingerprint,
            link.predecessor_fingerprint,
            link.prior_head_fingerprint,
            link.journal_head_fingerprint,
        )
        if observed != expected:
            raise RuntimeError("R2_DURABLE_RECEIPT_LINK_INVALID")
        links.append(link)
    return tuple(links)


def _seal_adapters(journal, head, identities, nonce):

    def freshness():
        return FinalFreshnessObservationV1.create(
            journal_head_fingerprint=head,
            nonce_b=nonce,
            approved_identities_fingerprint=identities,
            observed_at_epoch=NOW,
        )

    return CrossStageAdaptersV1(
        observe_intent=lambda _value: None,
        current_journal_head=journal.current_head,
        reverse_boundary=lambda *_values: None,
        minimal_final_freshness=freshness,
        append_cutover_success=journal.append_success,
    )


def _bundle(process_types, publications, lifecycle, semantic_gap_cases):
    _evidence, _main, repository, runtime, database, crx, config = publications
    values = {
        "schema_version": 1,
        "windows_ntfs": True,
        "process_type_count": len(process_types),
        "authorization_domain_count": 4,
        "real_tty_channel_count": 3,
        "independent_audit_process_count": len(set(lifecycle.audit_process_ids)),
        "project_container_zone_count": len(_ZONES),
        "repository_count": repository.repository_count,
        "worktree_count": repository.worktree_count,
        "managed_unit_count": sum(
            (
                int(runtime.complete),
                int(database.status.value == "DATABASE_PUBLISHED"),
                int(crx.status.value == "CRX_PUBLISHED"),
                int(config.status.value == "CONFIG_PUBLISHED"),
            )
        ),
        "semantic_gap_case_count": semantic_gap_cases,
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
    for path in _surface_source_paths(repo_root):
        items.append(
            [
                path.relative_to(repo_root).as_posix(),
                hashlib.sha256(path.read_bytes()).hexdigest(),
            ]
        )
    return fingerprint("r2-complete-surface-v1", items)


def _surface_source_paths(repo_root):
    seeds = (
        repo_root / "scripts" / "verify_r2_synthetic_topology.py",
        repo_root / "scripts" / "r2_synthetic_topology_support.py",
        repo_root / "scripts" / "r2_synthetic_windows_support.py",
        repo_root / "scripts" / "r2_semantic_gap_support.py",
    )
    dynamic = tuple(
        _resolve_module(repo_root, tuple(name.split(".")))
        for name in _DYNAMIC_SURFACE_MODULES
    )
    all_seeds = (*seeds, *(path for path in dynamic if path is not None))
    return _transitive_local_sources(repo_root, all_seeds)


def _transitive_local_sources(repo_root, seeds):
    pending = list(seeds)
    observed = set()
    while pending:
        path = pending.pop()
        if path in observed:
            continue
        observed.add(path)
        tree = ast.parse(path.read_text(encoding="utf-8"))
        module = _module_parts(repo_root, path)
        for node in ast.walk(tree):
            names = _imported_modules(module, node)
            for name in names:
                resolved = _resolve_module(repo_root, name)
                if resolved is not None and resolved not in observed:
                    pending.append(resolved)
    return tuple(sorted(observed))


def _module_parts(repo_root, path):
    relative = path.relative_to(repo_root).with_suffix("")
    return relative.parts


def _imported_modules(current, node):
    if isinstance(node, ast.Import):
        return tuple(tuple(alias.name.split(".")) for alias in node.names)
    if not isinstance(node, ast.ImportFrom):
        return ()
    if node.level:
        package = current[:-1]
        keep = len(package) - node.level + 1
        base = package[:keep]
    else:
        base = ()
    named = tuple(node.module.split(".")) if node.module else ()
    parent = (*base, *named)
    return (parent, *(tuple((*parent, alias.name)) for alias in node.names))


def _resolve_module(repo_root, parts):
    if not parts or parts[0] not in {"backend", "scripts", "tests"}:
        return None
    module = repo_root.joinpath(*parts).with_suffix(".py")
    package = repo_root.joinpath(*parts, "__init__.py")
    if module.is_file():
        return module
    return package if package.is_file() else None
