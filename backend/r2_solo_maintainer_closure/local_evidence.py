"""Private typed derivation of exact-master local closure evidence."""
from __future__ import annotations

import hashlib
from pathlib import Path

from ._canonical import CanonicalValue, allocate_value, fingerprint, is_fingerprint, is_git_oid, strict_object
from .contracts import ClosureErrorCode, SoloMaintainerClosureError
PROOF_KINDS = (
    "CANONICAL_DERIVATION", "FROZEN_GIT_OBJECT_CONTRACT", "HOSTED_CHECK_RECORD",
    "GITHUB_GUARDRAIL_SNAPSHOT", "HOSTED_TYPED_TEST_EXECUTION", "FRESH_LOCAL_OBSERVATION")
LOCAL_SOURCE_NAMES = (
    "frozen_remote_master", "git_object_source_package", "closure_map",
    "spec_coverage", "approved_cutover_binding_v3", "production_composition",
    "git_byte_state_receipt", "operator_runbook_receipt", "decision_registry",
    "blocker_resolution", "operator_package_semantics", "rollback_plan",
    "legacy_restoration_evidence", "crash_matrix", "fresh_process_suite",
    "retention_proof", "fixed_portable_suite", "documentation_guard",
    "generated_status", "quality_gate_review", "architecture_guard_run",
    "mechanical_guard_run", "static_guard_run", "repository_leakage_scan",
    "ci_leakage_reconciliation", "maintenance_scan_output",
)
_PROOF_FIELDS = ("source", "proof_kind", "final_commit_oid", "final_tree_oid",
                 "source_package_fingerprint", "subject_fingerprints", "verification_result")
_SUBJECT_PREFIXES = ("canonical:", "blob:", "hosted:", "fresh:")
_CANONICAL_SOURCES = (
    "frozen_remote_master", "git_object_source_package", "closure_map",
    "approved_cutover_binding_v3", "decision_registry", "blocker_resolution",
    "operator_package_semantics", "fixed_portable_suite",
)
_FRESH_SOURCES = ("generated_status", "repository_leakage_scan", "maintenance_scan_output")
_TYPED_PATHS = {
    "generated_status": ("docs/operations/project_status_log.md",),
    "spec_coverage": ("backend/r2_solo_maintainer_closure/local_evidence.py", "docs/operations/r2_solo_maintainer_closure_task_brief.md", "tests/test_r2_solo_maintainer_closure.py", "tests/test_r2_solo_maintainer_closure_architecture.py"),
    "production_composition": ("backend/r2_production_composition/adapter_binding.py", "tests/test_r2_production_composition_v1.py"),
    "git_byte_state_receipt": ("backend/r2_repository_manifest/git_byte_receipt_v2.py", "tests/test_r2_git_byte_state_v2.py"),
    "operator_runbook_receipt": ("backend/r2_operator_runbook_v2/receipt.py", "tests/test_r2_operator_runbook_v2.py"),
    "rollback_plan": ("backend/r2_rollback_recovery_v2/plan.py", "tests/test_r2_rollback_recovery_v2.py"),
    "legacy_restoration_evidence": ("backend/r2_rollback_recovery_v2/evidence.py", "tests/test_r2_rollback_recovery_v2.py"),
    "crash_matrix": ("backend/r2_rollback_recovery_v2/progress.py", "tests/test_r2_rollback_recovery_v2_crash_matrix.py"),
    "fresh_process_suite": ("backend/r2_ci_provenance_v2/suites.py", "tests/test_r2_ci_provenance_v2.py", "tests/r2_rollback_recovery_v2_fixture.py", "tests/test_r2_rollback_recovery_v2.py"),
    "retention_proof": ("backend/r2_retention_ledger_v2/proof.py", "tests/test_r2_retention_ledger_v2.py"),
    "documentation_guard": ("scripts/generate_project_status.py", "tests/test_generate_project_status.py"),
    "quality_gate_review": (".github/workflows/agent_guardrails.yml", "tests/test_architecture_constraints.py", "tests/test_static_linter_constraints.py", "tests/test_mechanical_rule_constraints.py"),
    "architecture_guard_run": (".github/workflows/agent_guardrails.yml", "tests/test_architecture_constraints.py"),
    "mechanical_guard_run": (".github/workflows/agent_guardrails.yml", "tests/test_mechanical_rule_constraints.py"),
    "static_guard_run": (".github/workflows/agent_guardrails.yml", "tests/test_static_linter_constraints.py"),
    "ci_leakage_reconciliation": ("scripts/r2_ci_provenance_support.py", "scripts/repository_leakage_scan.py", "tests/test_r2_ci_provenance_v2.py"),
}
_QUALITY_STEPS = (
    "Run architecture guardrails", "Run static linter guardrails",
    "Run mechanical rule guardrails", "Run full test suite", "Run maintenance scan",
)
_CLASSIFIED_STALE_PATHS = (
    "docs/README.md", "docs/api/error_codes.md", "docs/data/data_dictionary.md", "docs/decisions/0009-project-container-and-repository-boundaries.md", "docs/decisions/adr_0001_project_shape.md", "docs/decisions/adr_0003_no_auto_send.md",
    "docs/knowledge_base/action_rules.md", "docs/knowledge_base/business_terms.md", "docs/knowledge_base/customer_context_template.md", "docs/knowledge_base/email_categories.md",
    "docs/knowledge_base/priority_rules.md", "docs/knowledge_base/reply_guidelines.md", "docs/knowledge_base/risk_flags.md", "docs/operations/documentation_rules.md", "docs/operations/project_container_migration_task_brief.md",
    "docs/operations/troubleshooting.md", "docs/product/feature_scope.md", "docs/product/product_overview.md", "docs/product/user_flow.md", "docs/prompts/prompt_version_log.md",
    "docs/prompts/reply_draft_prompt.md", "docs/prompts/risk_detection_prompt.md", "docs/security/privacy_rules.md", "docs/security/prompt_injection_rules.md")
_MAINTENANCE_CLASSIFICATIONS = frozenset(
    ("low", "stale_doc", path, "docs/operations/cleanup_agent.md")
    for path in _CLASSIFIED_STALE_PATHS)
class LocalSourceProofV1(CanonicalValue):
    """Private closed proof; never accepted by the public closure seam."""
    @classmethod
    def create(cls, *, source: object, proof_kind: object,
               final_commit_oid: object, final_tree_oid: object,
               source_package_fingerprint: object,
               subject_fingerprints: object):
        subjects = _subject_mappings(subject_fingerprints)
        body = {
            "source": source, "proof_kind": proof_kind,
            "final_commit_oid": final_commit_oid, "final_tree_oid": final_tree_oid,
            "source_package_fingerprint": source_package_fingerprint,
            "subject_fingerprints": subjects, "verification_result": "VERIFIED",
        }
        _validate_proof_body(body)
        return allocate_value(cls, {**body, "proof_fingerprint": fingerprint(
            "r2-local-source-proof-v1", body)})
    @classmethod
    def from_json(cls, payload: object):
        try:
            source = strict_object(payload)
            if set(source) != {*_PROOF_FIELDS, "proof_fingerprint"}:
                raise SoloMaintainerClosureError()
            body = {name: source[name] for name in _PROOF_FIELDS}
            _validate_proof_body(body)
            if source["proof_fingerprint"] != fingerprint(
                    "r2-local-source-proof-v1", body):
                raise SoloMaintainerClosureError()
            return allocate_value(cls, source)
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError() from None
def _subject_mappings(value: object) -> list[dict[str, str]]:
    if type(value) is not tuple or any(type(item) is not tuple or len(item) != 2 for item in value):
        raise SoloMaintainerClosureError()
    return [{"subject": subject, "fingerprint": value} for subject, value in value]
def _validate_proof_body(body: dict[str, object]) -> None:
    subjects = body.get("subject_fingerprints")
    valid = (type(subjects) is list and len(subjects) > 0
             and all(type(item) is dict
                     and set(item) == {"subject", "fingerprint"}
                     and type(item["subject"]) is str
                     and item["subject"].startswith(_SUBJECT_PREFIXES)
                     and is_fingerprint(item["fingerprint"]) for item in subjects))
    if (set(body) != set(_PROOF_FIELDS) or body.get("source") not in LOCAL_SOURCE_NAMES
            or body.get("proof_kind") not in PROOF_KINDS
            or body.get("proof_kind") != proof_kind_for_source(body.get("source"))
            or not is_git_oid(body.get("final_commit_oid"))
            or not is_git_oid(body.get("final_tree_oid"))
            or not is_fingerprint(body.get("source_package_fingerprint"))
            or body.get("verification_result") != "VERIFIED" or not valid
            or tuple(item["subject"] for item in subjects)
            != _subject_names(body.get("source"))):
        raise SoloMaintainerClosureError()
def collect_repository_subjects(binding: object, production: object,
                                descriptors: object) -> dict[str, str]:
    """Bind canonical values and exact relevant frozen blob identities."""
    canonical = _canonical_subjects(binding, production)
    if type(descriptors) is not tuple:
        raise SoloMaintainerClosureError()
    by_path = {path: (mode, oid) for path, mode, oid, content in descriptors
               if type(path) is str and type(content) is bytes}
    required = {path for paths in _TYPED_PATHS.values() for path in paths}
    if any(path not in by_path for path in required):
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    for path in sorted(required):
        mode, oid = by_path[path]
        if mode not in {"100644", "100755"} or not is_git_oid(oid):
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        canonical["blob:" + path] = fingerprint("r2-local-source-proof-v1", {
            "subject_type": "FROZEN_GIT_BLOB", "source": path,
            "mode": mode, "blob_oid": oid})
    return canonical
def repository_subject_names() -> tuple[str, ...]:
    blobs = sorted({path for paths in _TYPED_PATHS.values() for path in paths})
    return tuple("canonical:" + name for name in _CANONICAL_SOURCES) + tuple(
        "blob:" + path for path in blobs)
def _canonical_subjects(binding: object, production: object) -> dict[str, str]:
    from backend.r2_ci_provenance_v2 import CiProvenanceKindV2, fixed_suite_fingerprint_v2
    from backend.r2_operator_runbook_v2.review_registry import (
        blocker_resolution_fingerprint_v2, decision_registry_fingerprint_v2,
    )
    from backend.r2_operator_runbook_v2.state_machine import (
        operator_package_semantics_fingerprint_v2,
    )
    values = {
        "frozen_remote_master": getattr(binding, "binding_fingerprint", None),
        "git_object_source_package": getattr(binding, "source_package_fingerprint", None),
        "closure_map": getattr(binding, "closure_map_fingerprint", None),
        "approved_cutover_binding_v3": getattr(production, "binding_fingerprint", None),
        "decision_registry": decision_registry_fingerprint_v2(),
        "blocker_resolution": blocker_resolution_fingerprint_v2(),
        "operator_package_semantics": operator_package_semantics_fingerprint_v2(),
        "fixed_portable_suite": fixed_suite_fingerprint_v2(CiProvenanceKindV2.PORTABLE),
    }
    if set(values) != set(_CANONICAL_SOURCES) or any(
            not is_fingerprint(value) for value in values.values()):
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    return {"canonical:" + name: value for name, value in values.items()}
def build_local_source_proofs(repository: object, github: object, root: Path):
    """Construct every proof only after the exact GitHub snapshot exists."""
    try:
        subjects = repository.source_mapping()
        records = {item.job_name: item for item in github.hosted_evidence}
        proofs = []
        for source in LOCAL_SOURCE_NAMES:
            kind, pairs = _proof_subjects(
                source, subjects, records, github, root, repository.tracked_paths)
            proofs.append(LocalSourceProofV1.create(
                source=source, proof_kind=kind,
                final_commit_oid=repository.final_master_binding.final_commit_oid,
                final_tree_oid=repository.final_master_binding.final_tree_oid,
                source_package_fingerprint=repository.final_master_binding.source_package_fingerprint,
                subject_fingerprints=pairs))
        return tuple(proofs)
    except SoloMaintainerClosureError:
        raise
    except Exception:
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED) from None
def proof_kind_for_source(source: str) -> str:
    if source in _CANONICAL_SOURCES:
        return "CANONICAL_DERIVATION"
    if source in _FRESH_SOURCES:
        return "FRESH_LOCAL_OBSERVATION"
    if source in _TYPED_PATHS:
        return "HOSTED_TYPED_TEST_EXECUTION"
    raise SoloMaintainerClosureError()
def _proof_subjects(source: str, subjects: dict[str, str], records: dict,
                    github: object, root: Path, tracked_paths: tuple[str, ...]):
    if source in _CANONICAL_SOURCES:
        name = "canonical:" + source
        return "CANONICAL_DERIVATION", ((name, subjects.get(name)),)
    if source in _FRESH_SOURCES:
        names = _subject_names(source)
        values = {"fresh:" + source: _fresh_subject(source, root, tracked_paths)[1]}
        return "FRESH_LOCAL_OBSERVATION", tuple(
            (name, values.get(name, subjects.get(name))) for name in names)
    paths = _TYPED_PATHS.get(source)
    if paths is None:
        raise SoloMaintainerClosureError()
    pairs = [("blob:" + path, subjects.get("blob:" + path)) for path in paths]
    for job, steps in _hosted_bindings(source):
        record = records.get(job)
        if record is None:
            raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
        pairs.append(("hosted:" + job, record.record_fingerprint))
        pairs.extend(("hosted:" + job + ":" + step,
                      github.step_fingerprint(job + ":" + step)) for step in steps)
    return "HOSTED_TYPED_TEST_EXECUTION", tuple(pairs)
def _hosted_bindings(source: str):
    if source == "fresh_process_suite":
        return (("windows-native-provenance", ("Verify Windows native Git-object provenance",)),
                ("windows-independent-provenance", ("Verify independent Windows process provenance",)))
    if source == "quality_gate_review":
        return (("quality-gates", _QUALITY_STEPS),)
    step = {"architecture_guard_run": "Run architecture guardrails",
            "mechanical_guard_run": "Run mechanical rule guardrails",
            "static_guard_run": "Run static linter guardrails"}.get(source)
    if step:
        return (("quality-gates", (step,)),)
    if source == "ci_leakage_reconciliation":
        return (("provenance-reconciliation", ("Reconcile exact same-package receipts",)),)
    return (("quality-gates", ("Run full test suite",)),)
def _subject_names(source: str) -> tuple[str, ...]:
    if source in _CANONICAL_SOURCES:
        return ("canonical:" + source,)
    names = tuple("blob:" + path for path in _TYPED_PATHS.get(source, ()))
    if source in _FRESH_SOURCES:
        return names + ("fresh:" + source,)
    if source not in _TYPED_PATHS:
        raise SoloMaintainerClosureError()
    for job, steps in _hosted_bindings(source):
        names += ("hosted:" + job,) + tuple("hosted:" + job + ":" + step for step in steps)
    return names
def _fresh_subject(source: str, root: Path, tracked_paths: tuple[str, ...]) -> tuple[str, str]:
    if not isinstance(root, Path) or type(tracked_paths) is not tuple or not tracked_paths:
        raise SoloMaintainerClosureError()
    if source == "generated_status":
        from scripts import generate_project_status as status
        _require_module_root(status, root)
        try:
            generated = status._normalize_status_snapshot(status.build_project_status())
            frozen = status._normalize_status_snapshot((root / "docs/operations/project_status_log.md").read_bytes().decode("utf-8"))
        except (UnicodeError, ValueError):
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED) from None
        if generated != frozen:
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        value = fingerprint("r2-local-source-proof-v1", {
            "subject_type": "FRESH_GENERATED_STATUS", "source": source,
            "content_sha256": hashlib.sha256(frozen).hexdigest()})
    elif source == "repository_leakage_scan":
        from scripts import repository_leakage_scan as leakage
        _require_module_root(leakage, root)
        if leakage.scan_repository(root, tracked_files=tracked_paths) != ():
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        value = fingerprint("r2-local-source-proof-v1", {
            "subject_type": "FRESH_REPOSITORY_LEAKAGE", "source": source, "total": 0})
    else:
        value = _maintenance_observation(root, tracked_paths)
    return "fresh:" + source, value
def _maintenance_observation(root: Path, tracked_paths: tuple[str, ...]) -> str:
    from scripts import maintenance_scan as maintenance
    _require_module_root(maintenance, root)
    try:
        observation = maintenance._collect_materialized_stable_observation(
            root,
            tracked_paths,
        )
    except maintenance.MaintenanceObservationError:
        raise SoloMaintainerClosureError(
            ClosureErrorCode.EVIDENCE_REJECTED
        ) from None
    if type(observation) is not maintenance.MaintenanceObservationV1:
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    classifications = tuple(item.as_tuple() for item in observation.records)
    if (len(classifications) != len(_MAINTENANCE_CLASSIFICATIONS)
            or len(set(classifications)) != len(classifications)
            or set(classifications) != _MAINTENANCE_CLASSIFICATIONS):
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    fields = ("severity", "category", "path", "doc")
    values = [{name: getattr(item, name) for name in fields}
              for item in observation.records]
    return fingerprint("r2-local-source-proof-v1", {
        "subject_type": "FRESH_MAINTENANCE_SCAN", "source": "maintenance_scan_output",
        "high_finding_count": observation.high_count,
        "classification_registry": sorted(
            [list(item) for item in _MAINTENANCE_CLASSIFICATIONS]), "findings": values})
def _require_module_root(module: object, root: Path) -> None:
    try:
        if Path(module.ROOT).resolve() != root.resolve():
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    except SoloMaintainerClosureError:
        raise
    except Exception:
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED) from None
