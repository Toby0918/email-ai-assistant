"""Canonical unsigned R2 binding and fourteen-body issuance package."""
from __future__ import annotations
import hashlib
from dataclasses import dataclass, field
from backend.r2_final_master_closure import ClosureGate, R2FrozenRemoteMasterV1, gate_evidence_registry
from backend.r2_final_master_closure._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from backend.r2_final_master_closure.global_gate_evidence import ZERO_GATE_FIELDS, producer_fingerprint_v1
from backend.r2_production_binding import ApprovedCutoverBindingV2
from .review_inputs import R2ExternalArtifactError
_BINDING_FILENAME = "reviewed-production-binding-v2.json"
_SOURCE_TYPES = {
    ClosureGate.FINAL_MASTER_BINDING: "R2FrozenRemoteMasterV1",
    ClosureGate.CLOSURE_SURFACE_COMPLETENESS: "R2GateSourceReviewV1",
    ClosureGate.PRODUCTION_COMPOSITION: "ApprovedCutoverBindingV2",
    ClosureGate.GIT_BYTES: "R2GitByteStateReceiptV1",
    ClosureGate.DEPENDENCY_ACTION_PROVENANCE: "R2CiProvenanceBundleV2",
    ClosureGate.WINDOWS_NATIVE: "R2GateSourceReviewV1",
    ClosureGate.PORTABLE_FULL_SUITE: "R2CiProvenanceReceiptV2",
    ClosureGate.RUNBOOK_SEMANTICS: "R2OperatorRunbookReceiptV2",
    ClosureGate.CRASH_RECOVERY: "R2GateSourceReviewV1",
    ClosureGate.RETENTION_NO_DELETION: "R2RetentionProofV2",
    ClosureGate.DOCUMENTATION: "R2GateSourceReviewV1",
    ClosureGate.MECHANICAL_ARCHITECTURE: "R2GateSourceReviewV1",
    ClosureGate.LEAKAGE: "R2GateSourceReviewV1",
    ClosureGate.MAINTENANCE_SCOPE: "R2GateSourceReviewV1",
}
@dataclass(frozen=True, slots=True, repr=False)
class R2UnsignedGateArtifactV1:
    gate: ClosureGate
    filename: str
    unsigned_body_json: bytes = field(repr=False)
    evidence_fingerprint: str = field(repr=False)
    body_sha256: str = field(repr=False)
    def to_mapping(self) -> dict[str, object]:
        return {
            "gate": self.gate.value,
            "filename": self.filename,
            "unsigned_body": strict_json_object(self.unsigned_body_json),
            "evidence_fingerprint": self.evidence_fingerprint,
            "body_sha256": self.body_sha256,
        }
@dataclass(frozen=True, slots=True, repr=False)
class R2GateDerivationProvenanceV1:
    gate: ClosureGate
    source_type: str
    source_json: bytes = field(repr=False)
    supporting_source_json: tuple[bytes, ...] = field(repr=False)
    evidence_fingerprint: str = field(repr=False)
    provenance_fingerprint: str = field(repr=False)
    @property
    def source_mapping(self) -> dict[str, object]:
        return strict_json_object(self.source_json)
    @property
    def supporting_source_mappings(self) -> tuple[dict[str, object], ...]:
        return tuple(strict_json_object(item) for item in self.supporting_source_json)
    def to_mapping(self) -> dict[str, object]:
        return {
            "provenance_type": "R2GateDerivationProvenanceV1",
            "gate": self.gate.value,
            "source_type": self.source_type,
            "source": self.source_mapping,
            "supporting_sources": list(self.supporting_source_mappings),
            "evidence_fingerprint": self.evidence_fingerprint,
            "provenance_fingerprint": self.provenance_fingerprint,
        }
@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2UnsignedExternalArtifactPackageV1:
    package_type: str
    final_master_binding_fingerprint: str = field(repr=False)
    reviewed_production_binding_json: bytes = field(repr=False)
    unsigned_gate_artifacts: tuple[R2UnsignedGateArtifactV1, ...] = field(repr=False)
    supporting_provenance_records: tuple[R2GateDerivationProvenanceV1, ...] = field(repr=False)
    issuance_manifest_json: bytes = field(repr=False)
    issuance_manifest_fingerprint: str = field(repr=False)
    artifact_count: int
    unsigned_gate_count: int
    signature_count: int
    package_fingerprint: str = field(repr=False)
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2UnsignedExternalArtifactPackageV1 requires preparation")
    @classmethod
    def from_json(cls, payload: object, *, frozen_master: object) -> R2UnsignedExternalArtifactPackageV1:
        try:
            source = strict_json_object(payload)
            if payload != canonical_json(source) or set(source) != _PACKAGE_FIELDS:
                raise R2ExternalArtifactError()
            if type(frozen_master) is not R2FrozenRemoteMasterV1:
                raise R2ExternalArtifactError()
            binding_json = canonical_json(source["reviewed_production_binding"])
            binding = ApprovedCutoverBindingV2.from_json(binding_json, final_master_binding=frozen_master.binding)
            derivations = _parse_provenance(source["supporting_provenance_records"])
            result = _build_unsigned_package_v1(frozen_master=frozen_master, production_binding=binding, derivations=derivations)
            if result.to_canonical_json() != payload:
                raise R2ExternalArtifactError()
            from .derivation import _rederive_external_evidence_v1
            _rederive_external_evidence_v1(result, frozen_master.binding, binding)
            return result
        except R2ExternalArtifactError:
            raise
        except Exception:
            raise R2ExternalArtifactError() from None
    def to_mapping(self) -> dict[str, object]:
        return {
            "package_type": self.package_type,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "reviewed_production_binding": strict_json_object(self.reviewed_production_binding_json),
            "unsigned_gate_artifacts": [item.to_mapping() for item in self.unsigned_gate_artifacts],
            "supporting_provenance_records": [item.to_mapping() for item in self.supporting_provenance_records],
            "issuance_manifest": strict_json_object(self.issuance_manifest_json),
            "issuance_manifest_fingerprint": self.issuance_manifest_fingerprint,
            "artifact_count": self.artifact_count,
            "unsigned_gate_count": self.unsigned_gate_count,
            "signature_count": self.signature_count,
            "package_fingerprint": self.package_fingerprint,
        }
    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())
_PACKAGE_FIELDS = {
    "package_type", "final_master_binding_fingerprint", "reviewed_production_binding",
    "unsigned_gate_artifacts", "supporting_provenance_records", "issuance_manifest",
    "issuance_manifest_fingerprint", "artifact_count", "unsigned_gate_count",
    "signature_count", "package_fingerprint",
}
_ARTIFACT_FIELDS = {"gate", "filename", "unsigned_body", "evidence_fingerprint", "body_sha256"}
_PROVENANCE_FIELDS = {"provenance_type", "gate", "source_type", "source", "supporting_sources", "evidence_fingerprint", "provenance_fingerprint"}
_MANIFEST_FIELDS = {"manifest_type", "binding_fingerprint", "files", "provenance_records", "artifact_count", "unsigned_gate_count", "signature_count", "issuance_manifest_fingerprint"}
def _build_unsigned_package_v1(*, frozen_master, production_binding, derivations):
    _require_build_inputs(frozen_master, production_binding, derivations)
    artifacts, records = [], []
    for index, (registration, derivation) in enumerate(zip(gate_evidence_registry(), derivations, strict=True), start=1):
        gate, evidence_value, source_type, source, supporting_sources = derivation
        body_json = canonical_json(_unsigned_body(frozen_master, registration, evidence_value))
        filename = f"{index:02d}-{gate.value}.json"
        artifacts.append(R2UnsignedGateArtifactV1(gate, filename, body_json, evidence_value, _sha256(body_json)))
        records.append(_provenance_record(
            gate, source_type, source, supporting_sources, evidence_value))
    binding_json = production_binding.to_canonical_json()
    manifest_json, manifest_fingerprint = _manifest(frozen_master, binding_json, tuple(artifacts), tuple(records))
    body = _package_body(frozen_master, binding_json, tuple(artifacts), tuple(records), manifest_json, manifest_fingerprint)
    return _allocate_package(body)
def _require_build_inputs(frozen, binding, derivations):
    if (
        type(frozen) is not R2FrozenRemoteMasterV1
        or type(binding) is not ApprovedCutoverBindingV2
        or binding.final_master_binding_fingerprint
        != frozen.binding.binding_fingerprint
        or type(derivations) is not tuple
        or len(derivations) != len(ClosureGate)
    ):
        raise R2ExternalArtifactError()
    for expected, item in zip(ClosureGate, derivations, strict=True):
        if (
            type(item) is not tuple
            or len(item) != 5
            or item[0] is not expected
            or not is_fingerprint(item[1])
            or item[2] != _SOURCE_TYPES[expected]
            or type(item[3]) is not dict
            or type(item[4]) is not tuple
            or any(type(source) is not dict for source in item[4])
            or len(item[4]) != (2 if expected is ClosureGate.WINDOWS_NATIVE else 0)
        ):
            raise R2ExternalArtifactError()
    if (derivations[0][1] != frozen.observation_fingerprint
            or derivations[0][3] != frozen.to_mapping()):
        raise R2ExternalArtifactError()
def _unsigned_body(frozen, registration, evidence_value):
    return {
        "evidence_type": "R2SignedGlobalGateEvidenceV1",
        "binding_fingerprint": frozen.binding.binding_fingerprint,
        "gate": registration.gate.value,
        "producer": registration.producer.value,
        "review_domain": registration.review_domain.value,
        "evidence_fingerprint": evidence_value,
        "producer_fingerprint": producer_fingerprint_v1(registration),
        "verified": 1,
        "self_certified": 0,
        **{name: 0 for name in ZERO_GATE_FIELDS},
    }
def _provenance_record(gate, source_type, source, supporting_sources, evidence_value):
    body = {
        "provenance_type": "R2GateDerivationProvenanceV1",
        "gate": gate.value,
        "source_type": source_type,
        "source": source,
        "supporting_sources": list(supporting_sources),
        "evidence_fingerprint": evidence_value,
    }
    return R2GateDerivationProvenanceV1(
        gate, source_type, canonical_json(source),
        tuple(canonical_json(item) for item in supporting_sources), evidence_value,
        fingerprint("r2-gate-derivation-provenance-v1", body))
def _manifest(frozen, binding_json, artifacts, records):
    body = {
        "manifest_type": "R2ExternalArtifactIssuanceManifestV1",
        "binding_fingerprint": frozen.binding.binding_fingerprint,
        "files": [
            {"filename": _BINDING_FILENAME, "sha256": _sha256(binding_json)},
            *[{"filename": item.filename, "sha256": item.body_sha256} for item in artifacts],
        ],
        "provenance_records": [{"gate": item.gate.value, "fingerprint": item.provenance_fingerprint} for item in records],
        "artifact_count": 15,
        "unsigned_gate_count": 14,
        "signature_count": 0,
    }
    manifest_fingerprint = fingerprint("r2-external-artifact-issuance-manifest-v1", body)
    return canonical_json({**body, "issuance_manifest_fingerprint": manifest_fingerprint}), manifest_fingerprint
def _package_body(frozen, binding_json, artifacts, records, manifest_json, manifest_fp):
    return {
        "package_type": "R2UnsignedExternalArtifactPackageV1",
        "final_master_binding_fingerprint": frozen.binding.binding_fingerprint,
        "reviewed_production_binding": strict_json_object(binding_json),
        "unsigned_gate_artifacts": [item.to_mapping() for item in artifacts],
        "supporting_provenance_records": [item.to_mapping() for item in records],
        "issuance_manifest": strict_json_object(manifest_json),
        "issuance_manifest_fingerprint": manifest_fp,
        "artifact_count": 15,
        "unsigned_gate_count": 14,
        "signature_count": 0,
    }
def _allocate_package(body):
    value = object.__new__(R2UnsignedExternalArtifactPackageV1)
    object.__setattr__(value, "package_type", body["package_type"])
    object.__setattr__(value, "final_master_binding_fingerprint", body["final_master_binding_fingerprint"])
    object.__setattr__(value, "reviewed_production_binding_json", canonical_json(body["reviewed_production_binding"]))
    object.__setattr__(value, "unsigned_gate_artifacts", _parse_artifacts(body["unsigned_gate_artifacts"]))
    object.__setattr__(value, "supporting_provenance_records", _parse_provenance_records(body["supporting_provenance_records"]))
    object.__setattr__(value, "issuance_manifest_json", canonical_json(body["issuance_manifest"]))
    for name in ("issuance_manifest_fingerprint", "artifact_count", "unsigned_gate_count", "signature_count"):
        object.__setattr__(value, name, body[name])
    object.__setattr__(value, "package_fingerprint", fingerprint("r2-unsigned-external-artifact-package-v1", body))
    return value
def _parse_artifacts(values):
    if type(values) is not list or len(values) != len(ClosureGate):
        raise R2ExternalArtifactError()
    result = []
    for index, (expected, value) in enumerate(zip(ClosureGate, values, strict=True), 1):
        if (type(value) is not dict or set(value) != _ARTIFACT_FIELDS
                or value["gate"] != expected.value or value["filename"] != f"{index:02d}-{expected.value}.json"
                or not is_fingerprint(value["evidence_fingerprint"])):
            raise R2ExternalArtifactError()
        body_json = canonical_json(value["unsigned_body"])
        if value["body_sha256"] != _sha256(body_json):
            raise R2ExternalArtifactError()
        result.append(R2UnsignedGateArtifactV1(expected, value["filename"], body_json, value["evidence_fingerprint"], value["body_sha256"]))
    return tuple(result)
def _parse_provenance(values):
    records = _parse_provenance_records(values)
    return tuple((item.gate, item.evidence_fingerprint, item.source_type,
                  item.source_mapping, item.supporting_source_mappings) for item in records)
def _parse_provenance_records(values):
    if type(values) is not list or len(values) != len(ClosureGate):
        raise R2ExternalArtifactError()
    result = []
    for expected, value in zip(ClosureGate, values, strict=True):
        if (type(value) is not dict or set(value) != _PROVENANCE_FIELDS
                or value["provenance_type"] != "R2GateDerivationProvenanceV1"
                or value["gate"] != expected.value or value["source_type"] != _SOURCE_TYPES[expected]
                or type(value["source"]) is not dict or type(value["supporting_sources"]) is not list
                or any(type(item) is not dict for item in value["supporting_sources"])
                or not is_fingerprint(value["evidence_fingerprint"])):
            raise R2ExternalArtifactError()
        body = {name: value[name] for name in value if name != "provenance_fingerprint"}
        if fingerprint("r2-gate-derivation-provenance-v1", body) != value.get("provenance_fingerprint"):
            raise R2ExternalArtifactError()
        result.append(R2GateDerivationProvenanceV1(
            expected, value["source_type"], canonical_json(value["source"]),
            tuple(canonical_json(item) for item in value["supporting_sources"]),
            value["evidence_fingerprint"], value["provenance_fingerprint"]))
    return tuple(result)
def _sha256(payload):
    return hashlib.sha256(payload).hexdigest()
def _require_package_integrity_v1(package):
    if (type(package) is not R2UnsignedExternalArtifactPackageV1
            or package.package_type != "R2UnsignedExternalArtifactPackageV1"
            or any(type(item) is not int for item in (
                package.artifact_count, package.unsigned_gate_count, package.signature_count))
            or (package.artifact_count, package.unsigned_gate_count, package.signature_count) != (15, 14, 0)
            or not is_fingerprint(package.final_master_binding_fingerprint)):
        raise R2ExternalArtifactError()
    mapping, stored = package.to_mapping(), package.package_fingerprint
    if mapping.pop("package_fingerprint", None) != stored or fingerprint("r2-unsigned-external-artifact-package-v1", mapping) != stored:
        raise R2ExternalArtifactError()
    manifest = strict_json_object(package.issuance_manifest_json)
    if set(manifest) != _MANIFEST_FIELDS:
        raise R2ExternalArtifactError()
    manifest_body, manifest_fp = dict(manifest), manifest["issuance_manifest_fingerprint"]
    manifest_body.pop("issuance_manifest_fingerprint")
    files = [{"filename": _BINDING_FILENAME, "sha256": _sha256(package.reviewed_production_binding_json)},
             *[{"filename": item.filename, "sha256": _sha256(item.unsigned_body_json)} for item in package.unsigned_gate_artifacts]]
    provenance = [{"gate": item.gate.value, "fingerprint": item.provenance_fingerprint}
                  for item in package.supporting_provenance_records]
    expected = {"manifest_type": "R2ExternalArtifactIssuanceManifestV1",
                "binding_fingerprint": package.final_master_binding_fingerprint,
                "files": files, "provenance_records": provenance,
                "artifact_count": 15, "unsigned_gate_count": 14, "signature_count": 0}
    if (canonical_json(manifest_body) != canonical_json(expected)
            or fingerprint("r2-external-artifact-issuance-manifest-v1", expected) != manifest_fp
            or manifest_fp != package.issuance_manifest_fingerprint):
        raise R2ExternalArtifactError()
