"""Fourteen internally derived gate records and eight finite gap proofs."""

from __future__ import annotations

from ._canonical import (
    CanonicalValue, allocate_value, canonical_json, fingerprint,
    is_fingerprint, is_git_oid, is_nonnegative_int, strict_object,
)
from .contracts import ASSURANCE_MODEL, SoloMaintainerClosureError
from .local_evidence import (
    LOCAL_SOURCE_NAMES, LocalSourceProofV1, PROOF_KINDS, proof_kind_for_source,
)


GAP_ORDER = (
    "terminal_contract", "production_composition", "git_byte_reproducibility",
    "crash_recovery", "retention_no_deletion", "runbook_semantic_closure",
    "windows_ci_provenance", "global_gates",
)
GATE_ORDER = (
    "final_master_binding", "closure_surface_completeness", "production_composition",
    "git_bytes", "dependency_action_provenance", "windows_native",
    "portable_full_suite", "runbook_semantics", "crash_recovery",
    "retention_no_deletion", "documentation", "mechanical_architecture",
    "leakage", "maintenance_scope",
)
SOURCE_REGISTRY = {
    "final_master_binding": ("frozen_remote_master", "git_object_source_package"),
    "closure_surface_completeness": ("closure_map", "spec_coverage"),
    "production_composition": ("approved_cutover_binding_v3", "production_composition"),
    "git_bytes": ("git_byte_state_receipt",),
    "dependency_action_provenance": (
        "github_guardrail_snapshot", "portable-provenance", "windows-native-provenance",
        "windows-independent-provenance", "provenance-reconciliation",
    ),
    "windows_native": ("windows-native-provenance", "windows-independent-provenance"),
    "portable_full_suite": ("quality-gates", "portable-provenance", "fixed_portable_suite"),
    "runbook_semantics": (
        "operator_runbook_receipt", "decision_registry", "blocker_resolution",
        "operator_package_semantics",
    ),
    "crash_recovery": (
        "rollback_plan", "legacy_restoration_evidence", "crash_matrix",
        "fresh_process_suite",
    ),
    "retention_no_deletion": ("retention_proof",),
    "documentation": ("documentation_guard", "generated_status"),
    "mechanical_architecture": (
        "quality_gate_review", "architecture_guard_run", "mechanical_guard_run",
        "static_guard_run",
    ),
    "leakage": ("repository_leakage_scan", "ci_leakage_reconciliation"),
    "maintenance_scope": ("maintenance_scan_output",),
}
_HOSTED_SOURCE_NAMES = frozenset(name for name in SOURCE_REGISTRY["dependency_action_provenance"]
                                 if name != "github_guardrail_snapshot") | {"quality-gates"}
_ZERO_FIELDS = (
    "human_approval_count", "required_skip_count", "unclassified_skip_count",
    "platform_divergence_count", "open_finding_count", "leakage_finding_count",
    "failure_count", "private_data_access_count", "real_host_operation_count",
    "provider_attempt_count", "cleanup_operation_count", "issue39_authority_count",
)
_RECORD_BODY = (
    "record_type", "gate", "binding_fingerprint", "final_commit_oid",
    "final_tree_oid", "source_package_fingerprint", "source_fingerprints",
    "source_count", "verification_result", *_ZERO_FIELDS,
)
class SoloMaintainerClosureEvidenceV1(CanonicalValue):
    @classmethod
    def create(cls, *, gate: str, binding: object,
               source_fingerprints: tuple[tuple[str, str], ...]):
        body = _record_body(gate, binding, source_fingerprints)
        return allocate_value(cls, {**body, "evidence_fingerprint": fingerprint(
            "r2-solo-maintainer-closure-evidence-v1", body)})

    @classmethod
    def from_json(cls, payload: object):
        try:
            source = strict_object(payload)
            if set(source) != {*_RECORD_BODY, "evidence_fingerprint"}:
                raise SoloMaintainerClosureError()
            body = {name: source[name] for name in _RECORD_BODY}
            _validate_record_body(body)
            if source["evidence_fingerprint"] != fingerprint(
                    "r2-solo-maintainer-closure-evidence-v1", body):
                raise SoloMaintainerClosureError()
            return allocate_value(cls, source)
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError() from None

    @classmethod
    def from_mapping(cls, source: object):
        return cls.from_json(canonical_json(source))
def build_evidence_records(binding: object, local_proofs: tuple[object, ...],
                           hosted_records: tuple[object, ...], guardrail: object):
    if (type(local_proofs) is not tuple
            or tuple(getattr(item, "source", None) for item in local_proofs)
            != LOCAL_SOURCE_NAMES
            or any(type(item) is not LocalSourceProofV1 for item in local_proofs)):
        raise SoloMaintainerClosureError()
    combined = {item.source: (item.proof_kind, item.proof_fingerprint)
                for item in local_proofs}
    combined["github_guardrail_snapshot"] = (
        "GITHUB_GUARDRAIL_SNAPSHOT", guardrail.snapshot_fingerprint)
    combined.update({item.job_name: ("HOSTED_CHECK_RECORD", item.record_fingerprint)
                     for item in hosted_records})
    records = []
    for gate in GATE_ORDER:
        sources = tuple((name, *combined.get(name, (None, None)))
                        for name in SOURCE_REGISTRY[gate])
        if any(kind not in PROOF_KINDS or not is_fingerprint(value)
               for _name, kind, value in sources):
            raise SoloMaintainerClosureError()
        records.append(SoloMaintainerClosureEvidenceV1.create(
            gate=gate, binding=binding, source_fingerprints=sources))
    return tuple(records)
def evidence_set_fingerprint(records: tuple[object, ...]) -> str:
    _require_record_sequence(records)
    return fingerprint("r2-solo-maintainer-closure-evidence-set-v1", {
        "set_type": "SoloMaintainerClosureEvidenceSetV1",
        "evidence_fingerprints": [item.evidence_fingerprint for item in records],
    })
def build_gap_proofs(binding: object, records: tuple[object, ...]):
    return _build_gap_proofs(binding.binding_fingerprint, records)
def _build_gap_proofs(binding_fingerprint: str, records: tuple[object, ...]):
    _require_record_sequence(records)
    by_gate = {item.gate: item.evidence_fingerprint for item in records}
    mapping = (
        ("final_master_binding", "closure_surface_completeness"),
        ("production_composition",), ("git_bytes",), ("crash_recovery",),
        ("retention_no_deletion",), ("runbook_semantics",),
        ("dependency_action_provenance", "windows_native", "portable_full_suite"),
        ("documentation", "mechanical_architecture", "leakage", "maintenance_scope"),
    )
    return tuple(_gap_mapping(gap, binding_fingerprint,
                              tuple(by_gate[gate] for gate in gates))
                 for gap, gates in zip(GAP_ORDER, mapping, strict=True))
def gap_proof_set_fingerprint(proofs: tuple[dict[str, object], ...]) -> str:
    _validate_gap_proofs(proofs)
    return fingerprint("r2-solo-maintainer-closure-evidence-set-v1", {
        "set_type": "SoloMaintainerClosureGapProofSetV1", "gap_proofs": list(proofs)})
def validate_evidence_manifest_parts(body: dict[str, object]) -> None:
    raw_records, raw_proofs = body.get("evidence_records"), body.get("gap_proofs")
    if type(raw_records) is not list or len(raw_records) != 14:
        raise SoloMaintainerClosureError()
    records = tuple(SoloMaintainerClosureEvidenceV1.from_mapping(item) for item in raw_records)
    _validate_record_links(records, body)
    if (evidence_set_fingerprint(records) != body.get("evidence_set_fingerprint")
            or body.get("evidence_record_count") != len(records)):
        raise SoloMaintainerClosureError()
    if type(raw_proofs) is not list or len(raw_proofs) != 8:
        raise SoloMaintainerClosureError()
    proofs = tuple(raw_proofs)
    if (gap_proof_set_fingerprint(proofs) != body.get("gap_proof_set_fingerprint")
            or body.get("gap_proof_count") != len(proofs)
            or canonical_json(proofs) != canonical_json(_build_gap_proofs(
                body.get("final_master_binding_fingerprint"), records))):
        raise SoloMaintainerClosureError()
def validate_manifest_body(body: dict[str, object], fields: set[str], binding_type: type) -> None:
    if set(body) != fields or body.get("manifest_type") != "SoloMaintainerClosureManifestV1":
        raise SoloMaintainerClosureError()
    binding = binding_type.from_mapping(body.get("final_master_binding"))
    copied = ("final_commit_oid", "final_tree_oid", "closure_map_fingerprint",
              "source_package_fingerprint", "runbook_fingerprint", "workflow_fingerprint")
    if any(body.get(name) != getattr(binding, name) for name in copied):
        raise SoloMaintainerClosureError()
    if body.get("final_master_binding_fingerprint") != binding.binding_fingerprint:
        raise SoloMaintainerClosureError()
    _validate_manifest_production(body, binding)
    from .hosted_evidence import validate_hosted_manifest_parts
    validate_hosted_manifest_parts(body)
    validate_evidence_manifest_parts(body)
    _validate_manifest_counts(body)
def closure_map_fingerprint() -> str:
    issues = ((86,), (87, 88, 89, 90, 91, 94, 95, 96), (92,),
              (93, 94, 95, 96, 97), (98,), (99,), (100,), (101, 102))
    decisions = (("D-R2-CLOSURE-1", "D-R2-FINITE-MAP-1"), ("D-R2-COMPOSITION-1",),
                 ("D-R2-GIT-BYTES-1",), ("D-R2-CRASH-RECOVERY-1",),
                 ("D-R2-RETENTION-1",), ("D-R2-RUNBOOK-DRIFT-1",),
                 ("D-R2-CI-PROVENANCE-1",), ("D-R2-GLOBAL-GATES-1",))
    return fingerprint("r2-final-master-closure-map-v1", [
        {"gap": gap, "blocked_by": [] if index == 0 else [GAP_ORDER[index - 1]],
         "owning_issues": list(issues[index]), "decision_ids": list(decisions[index])}
        for index, gap in enumerate(GAP_ORDER)])
def _record_body(gate: str, binding: object, sources: tuple[tuple[str, str], ...]):
    body = {"record_type": "SoloMaintainerClosureEvidenceV1", "gate": gate,
            "binding_fingerprint": getattr(binding, "binding_fingerprint", None),
            "final_commit_oid": getattr(binding, "final_commit_oid", None),
            "final_tree_oid": getattr(binding, "final_tree_oid", None),
            "source_package_fingerprint": getattr(binding, "source_package_fingerprint", None),
            "source_fingerprints": [{"source": name, "proof_kind": kind,
                                     "fingerprint": value}
                                    for name, kind, value in sources],
            "source_count": len(sources), "verification_result": "VERIFIED",
            **{name: 0 for name in _ZERO_FIELDS}}
    _validate_record_body(body)
    return body
def _validate_record_body(body: dict[str, object]) -> None:
    sources = body.get("source_fingerprints")
    valid_sources = (type(sources) is list and all(type(item) is dict
                     and set(item) == {"source", "proof_kind", "fingerprint"}
                     and type(item["source"]) is str and is_fingerprint(item["fingerprint"])
                     and item["proof_kind"] in PROOF_KINDS
                     for item in sources))
    if (set(body) != set(_RECORD_BODY) or body.get("record_type") != "SoloMaintainerClosureEvidenceV1"
            or body.get("gate") not in GATE_ORDER or not is_fingerprint(body.get("binding_fingerprint"))
            or not is_git_oid(body.get("final_commit_oid")) or not is_git_oid(body.get("final_tree_oid"))
            or not is_fingerprint(body.get("source_package_fingerprint")) or not valid_sources
            or body.get("source_count") != len(sources) or body.get("verification_result") != "VERIFIED"
            or any(body.get(name) != 0 for name in _ZERO_FIELDS)):
        raise SoloMaintainerClosureError()
def _gap_mapping(gap: str, binding: str, records: tuple[str, ...]) -> dict[str, object]:
    return {"proof_type": "SoloMaintainerClosureGapProofV1", "gap": gap,
            "binding_fingerprint": binding, "evidence_fingerprints": list(records),
            "evidence_count": len(records), "completed": 1, "open_finding_count": 0,
            "required_skip_count": 0, "unclassified_skip_count": 0,
            "leakage_finding_count": 0, "cleanup_operation_count": 0,
            "provider_attempt_count": 0, "real_host_operation_count": 0,
            "issue39_authority_count": 0}


def _validate_gap_proofs(proofs: tuple[dict[str, object], ...]) -> None:
    if tuple(item.get("gap") for item in proofs if type(item) is dict) != GAP_ORDER:
        raise SoloMaintainerClosureError()
    for item in proofs:
        values = item.get("evidence_fingerprints")
        if (set(item) != set(_gap_mapping(item["gap"], item.get("binding_fingerprint"),
                                         tuple(values) if type(values) is list else ()))
                or not is_fingerprint(item.get("binding_fingerprint"))
                or type(values) is not list or item.get("evidence_count") != len(values)
                or any(not is_fingerprint(value) for value in values)
                or any(item.get(name) != value for name, value in _gap_mapping(
                    item["gap"], item["binding_fingerprint"], tuple(values)).items()
                    if name not in {"evidence_fingerprints"})):
            raise SoloMaintainerClosureError()


def _require_record_sequence(records: tuple[object, ...]) -> None:
    if (type(records) is not tuple or len(records) != 14
            or tuple(getattr(item, "gate", None) for item in records) != GATE_ORDER
            or len({item.evidence_fingerprint for item in records}) != 14):
        raise SoloMaintainerClosureError()


def _validate_manifest_production(body: dict[str, object], binding: object) -> None:
    production = body.get("production_binding")
    try:
        from backend.r2_production_binding import ApprovedCutoverBindingV3
        parsed = ApprovedCutoverBindingV3.from_json(
            canonical_json(production), final_master_binding=binding)
    except Exception:
        raise SoloMaintainerClosureError() from None
    if parsed.binding_fingerprint != body.get("production_binding_fingerprint"):
        raise SoloMaintainerClosureError()


def _validate_record_links(records: tuple[object, ...], body: dict[str, object]) -> None:
    copied = ("binding_fingerprint", "final_commit_oid", "final_tree_oid",
              "source_package_fingerprint")
    expected = (body.get("final_master_binding_fingerprint"), body.get("final_commit_oid"),
                body.get("final_tree_oid"), body.get("source_package_fingerprint"))
    for item in records:
        names = tuple(source["source"] for source in item.source_fingerprints)
        kinds = tuple(source["proof_kind"] for source in item.source_fingerprints)
        expected_kinds = tuple(_expected_proof_kind(name) for name in names)
        if (names != SOURCE_REGISTRY[item.gate] or kinds != expected_kinds
                or tuple(getattr(item, name) for name in copied) != expected):
            raise SoloMaintainerClosureError()


def _expected_proof_kind(source: str) -> str:
    if source in _HOSTED_SOURCE_NAMES:
        return "HOSTED_CHECK_RECORD"
    if source == "github_guardrail_snapshot":
        return "GITHUB_GUARDRAIL_SNAPSHOT"
    return proof_kind_for_source(source)


def _validate_manifest_counts(body: dict[str, object]) -> None:
    exact = {"assurance_model": ASSURANCE_MODEL, "operator_count": 1,
             "hosted_evidence_count": 5, "evidence_record_count": 14, "gap_proof_count": 8}
    if any(body.get(name) != value for name, value in exact.items()):
        raise SoloMaintainerClosureError()
    positive = {"operator_count", "hosted_evidence_count", "evidence_record_count", "gap_proof_count"}
    for name, value in body.items():
        if name.endswith("_count") and (not is_nonnegative_int(value)
                                       or (name not in positive and value != 0)):
            raise SoloMaintainerClosureError()
