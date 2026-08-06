"""Closed reviewed-public-input contracts for R2 artifact issuance."""

from __future__ import annotations
from dataclasses import dataclass, field

from backend.r2_ci_provenance_v2 import R2CiProvenanceBundleV2, R2CiProvenanceReceiptV2
from backend.r2_final_master_closure import ClosureGate, FinalMasterBindingV1
from backend.r2_final_master_closure._canonical import canonical_json, fingerprint, is_fingerprint
from backend.r2_operator_runbook_v2.receipt import R2OperatorRunbookReceiptV2
from backend.r2_production_binding import ApprovedCutoverBindingV2
from backend.r2_repository_manifest.git_byte_receipt_v2 import R2GitByteStateReceiptV1
from backend.r2_retention_ledger_v2 import R2RetentionProofV2
class R2ExternalArtifactError(ValueError):
    """Fixed content-free failure for public issuance validation."""

    def __init__(self) -> None:
        super().__init__("R2_EXTERNAL_ARTIFACT_INVALID")
_SOURCE_NAMES = {
    ClosureGate.CLOSURE_SURFACE_COMPLETENESS: ("closure_map", "spec_coverage_review"),
    ClosureGate.WINDOWS_NATIVE: ("windows_independent_receipt", "windows_native_receipt"),
    ClosureGate.CRASH_RECOVERY: (
        "rollback_plan", "legacy_restoration_evidence", "crash_matrix",
        "fresh_process_suite",
    ),
    ClosureGate.DOCUMENTATION: ("documentation_review", "generated_status"),
    ClosureGate.MECHANICAL_ARCHITECTURE: (
        "standards_review", "architecture_guard_run", "mechanical_guard_run",
        "static_guard_run",
    ),
    ClosureGate.LEAKAGE: ("repository_leakage_scan", "ci_leakage_reconciliation"),
    ClosureGate.MAINTENANCE_SCOPE: ("maintenance_scan_output",),
}
_ASSERTIONS = {
    ClosureGate.CLOSURE_SURFACE_COMPLETENESS: (
        "issues_86_through_102_covered", "eight_gaps_covered", "fourteen_gates_covered",
        "dependencies_and_acceptance_covered",
    ),
    ClosureGate.WINDOWS_NATIVE: ("same_ci_bundle", "windows_independent_and_native_ordered"),
    ClosureGate.CRASH_RECOVERY: (
        "LEGACY_FLAT_LAYOUT_RESTORED", "offline_synthetic_only",
        "fixed_crash_and_fresh_process_matrix",
    ),
    ClosureGate.DOCUMENTATION: ("exact_source_package", "front_matter_and_generated_status_verified"),
    ClosureGate.MECHANICAL_ARCHITECTURE: (
        "architecture_mechanical_static_guards_verified",
        "forbidden_capabilities_and_imports_absent",
    ),
    ClosureGate.LEAKAGE: ("repository_findings_empty_total_zero", "ci_leakage_zero_reconciled"),
    ClosureGate.MAINTENANCE_SCOPE: ("high_and_unclassified_zero", "low_findings_individually_classified"),
}
_ZERO_REVIEW_FIELDS = (
    "open_finding_count",
    "contract_changing_finding_count",
    "decision_contradiction_finding_count",
    "security_incident_finding_count",
    "surface_completeness_defect_count",
    "evidence_defect_count",
    "required_skip_count",
    "unclassified_skip_count",
    "platform_divergence_count",
    "leakage_finding_count",
    "private_data_access_count",
    "real_host_operation_count",
    "provider_attempt_count",
    "issue39_code_change_count",
    "failure_count",
    "unreviewed_count",
    "high_finding_count",
    "unclassified_finding_count",
)
@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2GateSourceReviewV1:
    review_type: str
    gate: ClosureGate
    binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    closure_map_fingerprint: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    source_fingerprints: tuple[tuple[str, str], ...] = field(repr=False)
    review_assertions: tuple[str, ...]
    review_result: str
    classified_nonblocking_finding_fingerprints: tuple[str, ...] = field(repr=False)
    classified_nonblocking_finding_count: int
    open_finding_count: int
    contract_changing_finding_count: int
    decision_contradiction_finding_count: int
    security_incident_finding_count: int
    surface_completeness_defect_count: int
    evidence_defect_count: int
    required_skip_count: int
    unclassified_skip_count: int
    platform_divergence_count: int
    leakage_finding_count: int
    private_data_access_count: int
    real_host_operation_count: int
    provider_attempt_count: int
    issue39_code_change_count: int
    failure_count: int
    unreviewed_count: int
    high_finding_count: int
    unclassified_finding_count: int
    review_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2GateSourceReviewV1 requires create()")

    @classmethod
    def create(cls, *, gate: object, final_master_binding: object,
               source_fingerprints: object,
               classified_nonblocking_finding_fingerprints: object = ()) -> R2GateSourceReviewV1:
        try:
            body = _source_review_body(gate, final_master_binding, source_fingerprints,
                                       classified_nonblocking_finding_fingerprints)
            return _allocate_source_review(body)
        except R2ExternalArtifactError:
            raise
        except Exception:
            raise R2ExternalArtifactError() from None

    def to_mapping(self) -> dict[str, object]:
        result = {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name not in {
                "source_fingerprints",
                "review_assertions",
                "classified_nonblocking_finding_fingerprints",
                "review_fingerprint",
            }
        }
        result["gate"] = self.gate.value
        result["source_fingerprints"] = [
            {"source": name, "fingerprint": value} for name, value in self.source_fingerprints]
        result["review_assertions"] = list(self.review_assertions)
        result["classified_nonblocking_finding_fingerprints"] = list(self.classified_nonblocking_finding_fingerprints)
        result["review_fingerprint"] = self.review_fingerprint
        return result

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())
@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ExternalArtifactReviewInputsV1:
    production_binding: ApprovedCutoverBindingV2 = field(repr=False)
    closure_surface_review: R2GateSourceReviewV1 = field(repr=False)
    git_byte_receipt: R2GitByteStateReceiptV1 = field(repr=False)
    ci_provenance_bundle: R2CiProvenanceBundleV2 = field(repr=False)
    ci_provenance_receipts: tuple[R2CiProvenanceReceiptV2, ...] = field(repr=False)
    runbook_receipt: R2OperatorRunbookReceiptV2 = field(repr=False)
    crash_recovery_review: R2GateSourceReviewV1 = field(repr=False)
    retention_proof: R2RetentionProofV2 = field(repr=False)
    documentation_review: R2GateSourceReviewV1 = field(repr=False)
    mechanical_architecture_review: R2GateSourceReviewV1 = field(repr=False)
    leakage_review: R2GateSourceReviewV1 = field(repr=False)
    maintenance_review: R2GateSourceReviewV1 = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ExternalArtifactReviewInputsV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> R2ExternalArtifactReviewInputsV1:
        try:
            _require_review_input_types(values)
            result = object.__new__(cls)
            for name in cls.__dataclass_fields__:
                object.__setattr__(result, name, values[name])
            return result
        except R2ExternalArtifactError:
            raise
        except Exception:
            raise R2ExternalArtifactError() from None
def _source_review_body(gate, final_master, sources, findings):
    if (type(gate) is not ClosureGate or gate not in _SOURCE_NAMES
            or type(final_master) is not FinalMasterBindingV1 or type(sources) is not dict
            or set(sources) != set(_SOURCE_NAMES[gate])):
        raise R2ExternalArtifactError()
    ordered_sources = tuple((name, sources[name]) for name in _SOURCE_NAMES[gate])
    if any(not is_fingerprint(value) for _name, value in ordered_sources):
        raise R2ExternalArtifactError()
    ordered_findings = _require_findings(gate, findings)
    return {
        "review_type": "R2GateSourceReviewV1",
        "gate": gate.value,
        "binding_fingerprint": final_master.binding_fingerprint,
        "final_commit_oid": final_master.final_commit_oid,
        "final_tree_oid": final_master.final_tree_oid,
        "closure_map_fingerprint": final_master.closure_map_fingerprint,
        "source_package_fingerprint": final_master.source_package_fingerprint,
        "source_fingerprints": [
            {"source": name, "fingerprint": value} for name, value in ordered_sources],
        "review_assertions": list(_ASSERTIONS[gate]),
        "review_result": "ACCEPTED",
        "classified_nonblocking_finding_fingerprints": list(ordered_findings),
        "classified_nonblocking_finding_count": len(ordered_findings),
        **{name: 0 for name in _ZERO_REVIEW_FIELDS},
    }
def _require_source_review_mapping_v1(gate, source, final_master):
    fields = set(R2GateSourceReviewV1.__dataclass_fields__)
    if (type(source) is not dict or set(source) != fields or gate not in _SOURCE_NAMES
            or source["review_type"] != "R2GateSourceReviewV1" or source["gate"] != gate.value
            or source["binding_fingerprint"] != final_master.binding_fingerprint
            or source["final_commit_oid"] != final_master.final_commit_oid
            or source["final_tree_oid"] != final_master.final_tree_oid
            or source["closure_map_fingerprint"] != final_master.closure_map_fingerprint
            or source["source_package_fingerprint"] != final_master.source_package_fingerprint
            or source["review_result"] != "ACCEPTED" or source["review_assertions"] != list(_ASSERTIONS[gate])
            or any(type(source[name]) is not int for name in (*_ZERO_REVIEW_FIELDS,
                    "classified_nonblocking_finding_count"))
            or any(source[name] != 0 for name in _ZERO_REVIEW_FIELDS)):
        raise R2ExternalArtifactError()
    entries = source["source_fingerprints"]
    if (type(entries) is not list or [item.get("source") for item in entries] != list(_SOURCE_NAMES[gate])
            or any(type(item) is not dict or set(item) != {"source", "fingerprint"} or not is_fingerprint(item["fingerprint"]) for item in entries)
            or (gate is ClosureGate.CLOSURE_SURFACE_COMPLETENESS
                and entries[0]["fingerprint"] != final_master.closure_map_fingerprint)):
        raise R2ExternalArtifactError()
    findings = source["classified_nonblocking_finding_fingerprints"]
    if (type(findings) is not list or findings != sorted(set(findings))
            or any(not is_fingerprint(item) for item in findings)
            or source["classified_nonblocking_finding_count"] != len(findings)
            or (gate is not ClosureGate.MAINTENANCE_SCOPE and findings)):
        raise R2ExternalArtifactError()
    body = {key: value for key, value in source.items() if key != "review_fingerprint"}
    expected = fingerprint("r2-gate-source-review-v1", body)
    if source["review_fingerprint"] != expected:
        raise R2ExternalArtifactError()
    return expected
def _require_findings(gate, value):
    if type(value) is not tuple or any(not is_fingerprint(item) for item in value):
        raise R2ExternalArtifactError()
    ordered = tuple(sorted(value))
    if len(set(ordered)) != len(ordered):
        raise R2ExternalArtifactError()
    if gate is not ClosureGate.MAINTENANCE_SCOPE and ordered:
        raise R2ExternalArtifactError()
    return ordered
def _allocate_source_review(body):
    value = object.__new__(R2GateSourceReviewV1)
    for name, item in body.items():
        if name == "gate":
            item = ClosureGate(item)
        elif name == "source_fingerprints":
            item = tuple((entry["source"], entry["fingerprint"]) for entry in item)
        elif name in {
            "review_assertions",
            "classified_nonblocking_finding_fingerprints",
        }:
            item = tuple(item)
        object.__setattr__(value, name, item)
    object.__setattr__(value, "review_fingerprint", fingerprint("r2-gate-source-review-v1", body))
    return value
def _require_review_input_types(values):
    expected = set(R2ExternalArtifactReviewInputsV1.__dataclass_fields__)
    if set(values) != expected:
        raise R2ExternalArtifactError()
    exact = {
        "production_binding": ApprovedCutoverBindingV2,
        "git_byte_receipt": R2GitByteStateReceiptV1,
        "ci_provenance_bundle": R2CiProvenanceBundleV2,
        "runbook_receipt": R2OperatorRunbookReceiptV2,
        "retention_proof": R2RetentionProofV2,
    }
    if any(type(values[name]) is not kind for name, kind in exact.items()):
        raise R2ExternalArtifactError()
    receipts = values["ci_provenance_receipts"]
    if (type(receipts) is not tuple or len(receipts) != 3
            or any(type(item) is not R2CiProvenanceReceiptV2 for item in receipts)):
        raise R2ExternalArtifactError()
    for name in (
        "closure_surface_review",
        "crash_recovery_review",
        "documentation_review",
        "mechanical_architecture_review",
        "leakage_review",
        "maintenance_review",
    ):
        if type(values[name]) is not R2GateSourceReviewV1:
            raise R2ExternalArtifactError()
def _scalar_schema(kind, source, omitted=()):
    fields = {name: item for name, item in kind.__dataclass_fields__.items() if name not in omitted}
    return (type(source) is dict and set(source) == set(fields)
            and all(type(source[name]) is (int if item.type == "int" else str) for name, item in fields.items()))
def _self_fingerprint(source, name, domain):
    stored = source.get(name)
    body = {key: item for key, item in source.items() if key != name}
    if not is_fingerprint(stored) or fingerprint(domain, body) != stored:
        raise R2ExternalArtifactError()
    return stored
def _fingerprints_valid(source):
    return all(is_fingerprint(item) for name, item in source.items()
               if name.endswith("fingerprint"))
def _positive(source, names):
    return all(type(source[name]) is int and source[name] >= 1 for name in names)
def _zero(source, names):
    return all(type(source[name]) is int and source[name] == 0 for name in names)
def _require_source_master(source, final_master):
    observed = source.get("final_commit_oid"), source.get("final_tree_oid"), source.get("source_package_fingerprint")
    expected = final_master.final_commit_oid, final_master.final_tree_oid, final_master.source_package_fingerprint
    if observed != expected:
        raise R2ExternalArtifactError()
