"""Approved 7-direct plus 7-wrapper R2 gate derivation map."""

from __future__ import annotations

from backend.r2_ci_provenance_v2 import (CiProvenanceKindV2, R2CiProvenanceBundleV2,
                                         R2CiProvenanceReceiptV2, fixed_suite_fingerprint_v2)
from backend.r2_final_master_closure import ClosureGate, R2FrozenRemoteMasterV1
from backend.r2_final_master_closure._canonical import fingerprint, is_fingerprint
from backend.r2_operator_runbook_v2.receipt import R2OperatorRunbookReceiptV2
from backend.r2_operator_runbook_v2.review_registry import (blocker_resolution_fingerprint_v2,
                                                             decision_registry_fingerprint_v2)
from backend.r2_operator_runbook_v2.state_machine import operator_package_semantics_fingerprint_v2
from backend.r2_production_binding import (ApprovedCutoverBindingV2,
                                           production_composition_evidence_fingerprint_v2,
                                           require_reviewed_production_binding_v2)
from backend.r2_production_composition import build_production_binding_candidate_v1
from backend.r2_repository_manifest.git_byte_receipt_v2 import R2GitByteStateReceiptV1
from backend.r2_retention_ledger_v2 import R2RetentionProofV2

from .review_inputs import (R2ExternalArtifactError, R2ExternalArtifactReviewInputsV1,
                            R2GateSourceReviewV1, _fingerprints_valid, _positive,
                            _require_source_master, _require_source_review_mapping_v1,
                            _scalar_schema, _self_fingerprint, _zero)
from .unsigned_package import _SOURCE_TYPES, _build_unsigned_package_v1

_DIRECT = {
    ClosureGate.FINAL_MASTER_BINDING: ("observation_fingerprint", "r2-frozen-remote-master-v1", R2FrozenRemoteMasterV1, {"binding"}),
    ClosureGate.GIT_BYTES: ("receipt_fingerprint", "r2-git-byte-state-receipt-v1", R2GitByteStateReceiptV1, set()),
    ClosureGate.DEPENDENCY_ACTION_PROVENANCE: ("bundle_fingerprint", "r2-ci-provenance-bundle-v2", R2CiProvenanceBundleV2, set()),
    ClosureGate.PORTABLE_FULL_SUITE: ("receipt_fingerprint", "r2-ci-provenance-receipt-v2", R2CiProvenanceReceiptV2, set()),
    ClosureGate.RUNBOOK_SEMANTICS: ("receipt_fingerprint", "r2-operator-runbook-receipt-v2", R2OperatorRunbookReceiptV2, set()),
    ClosureGate.RETENTION_NO_DELETION: ("proof_fingerprint", "r2-retention-proof-v2", R2RetentionProofV2, set()),
}
_STATES = {
    ClosureGate.FINAL_MASTER_BINDING: {"observation_type": "R2FrozenRemoteMasterV1", "status": "FROZEN_REMOTE_MASTER_VERIFIED"},
    ClosureGate.GIT_BYTES: {"receipt_type": "R2GitByteStateReceiptV1", "status": "GIT_BYTE_STATE_VERIFIED"},
    ClosureGate.DEPENDENCY_ACTION_PROVENANCE: {"bundle_type": "R2CiProvenanceBundleV2", "status": "CI_PROVENANCE_RECONCILED"},
    ClosureGate.PORTABLE_FULL_SUITE: {"receipt_type": "R2CiProvenanceReceiptV2", "status": "CI_PROVENANCE_VERIFIED"},
    ClosureGate.RUNBOOK_SEMANTICS: {"receipt_type": "R2OperatorRunbookReceiptV2", "status": "RUNBOOK_SEMANTICS_VERIFIED"},
    ClosureGate.RETENTION_NO_DELETION: {"proof_type": "R2RetentionProofV2"},
}
_CI_ZERO = ("historical_package_count", "required_skip_count", "platform_divergence_count",
            "leakage_finding_count", "failure_count", "private_content_reads",
            "worktree_content_reads")


def prepare_unsigned_external_artifacts_v1(*, frozen_master, authority_verification_public_keys, review_inputs):
    """Derive one unsigned package without any signing capability."""
    try:
        binding = _require_inputs(frozen_master, authority_verification_public_keys, review_inputs)
        return _build_unsigned_package_v1(
            frozen_master=frozen_master, production_binding=binding,
            derivations=_derivations(frozen_master, binding, review_inputs))
    except R2ExternalArtifactError:
        raise
    except Exception:
        raise R2ExternalArtifactError() from None
def _require_inputs(frozen, authority_keys, inputs):
    if type(frozen) is not R2FrozenRemoteMasterV1 or type(inputs) is not R2ExternalArtifactReviewInputsV1:
        raise R2ExternalArtifactError()
    expected = build_production_binding_candidate_v1(
        final_master_binding=frozen.binding, verification_public_keys=authority_keys)
    candidate = inputs.production_binding
    if (type(candidate) is not ApprovedCutoverBindingV2
            or expected.to_canonical_json() != candidate.to_canonical_json()
            or _serialized_direct_fingerprint(
                ClosureGate.FINAL_MASTER_BINDING, frozen.to_mapping(), frozen.binding,
                candidate) != frozen.observation_fingerprint):
        raise R2ExternalArtifactError()
    require_reviewed_production_binding_v2(frozen.binding, candidate)
    _require_direct_inputs(inputs, frozen.binding, candidate)
    _require_reviews(inputs, frozen.binding)
    return candidate
def _derivations(frozen, binding, inputs):
    receipts = tuple(sorted(inputs.ci_provenance_receipts,
                            key=lambda item: item.provenance_kind.value))
    portable, windows = receipts[0], receipts[1:]
    windows_review = R2GateSourceReviewV1.create(
        gate=ClosureGate.WINDOWS_NATIVE, final_master_binding=frozen.binding,
        source_fingerprints={"windows_independent_receipt": windows[0].receipt_fingerprint,
                             "windows_native_receipt": windows[1].receipt_fingerprint})
    values = {
        ClosureGate.FINAL_MASTER_BINDING: _direct(frozen, frozen.observation_fingerprint),
        ClosureGate.CLOSURE_SURFACE_COMPLETENESS: _review(inputs.closure_surface_review),
        ClosureGate.PRODUCTION_COMPOSITION: _direct(binding, production_composition_evidence_fingerprint_v2(frozen.binding, binding)),
        ClosureGate.GIT_BYTES: _direct(inputs.git_byte_receipt, inputs.git_byte_receipt.receipt_fingerprint),
        ClosureGate.DEPENDENCY_ACTION_PROVENANCE: _direct(inputs.ci_provenance_bundle, inputs.ci_provenance_bundle.bundle_fingerprint),
        ClosureGate.WINDOWS_NATIVE: _review(windows_review, tuple(item.to_mapping() for item in windows)),
        ClosureGate.PORTABLE_FULL_SUITE: _direct(portable, portable.receipt_fingerprint),
        ClosureGate.RUNBOOK_SEMANTICS: _direct(inputs.runbook_receipt, inputs.runbook_receipt.receipt_fingerprint),
        ClosureGate.CRASH_RECOVERY: _review(inputs.crash_recovery_review),
        ClosureGate.RETENTION_NO_DELETION: _direct(inputs.retention_proof, inputs.retention_proof.proof_fingerprint),
        ClosureGate.DOCUMENTATION: _review(inputs.documentation_review),
        ClosureGate.MECHANICAL_ARCHITECTURE: _review(inputs.mechanical_architecture_review),
        ClosureGate.LEAKAGE: _review(inputs.leakage_review),
        ClosureGate.MAINTENANCE_SCOPE: _review(inputs.maintenance_review),
    }
    return tuple((gate, *values[gate]) for gate in ClosureGate)
def _direct(value, evidence_fingerprint):
    mapping = value.to_mapping()
    source_type = next(mapping[name] for name in
                       ("observation_type", "binding_type", "receipt_type", "bundle_type", "proof_type")
                       if name in mapping)
    return evidence_fingerprint, source_type, mapping, ()
def _review(value, supporting_sources=()):
    return value.review_fingerprint, "R2GateSourceReviewV1", value.to_mapping(), supporting_sources
def _require_direct_inputs(inputs, final_master, binding):
    receipt = inputs.git_byte_receipt
    if (type(receipt) is not R2GitByteStateReceiptV1
            or _serialized_direct_fingerprint(
                ClosureGate.GIT_BYTES, receipt.to_mapping(), final_master,
                binding) != receipt.receipt_fingerprint):
        raise R2ExternalArtifactError()
    receipts = _require_ci_inputs(inputs, final_master)
    proof, runbook = inputs.retention_proof, inputs.runbook_receipt
    for gate, value, kind, name in (
        (ClosureGate.RETENTION_NO_DELETION, proof, R2RetentionProofV2, "proof_fingerprint"),
        (ClosureGate.RUNBOOK_SEMANTICS, runbook, R2OperatorRunbookReceiptV2, "receipt_fingerprint"),
    ):
        if (type(value) is not kind or _serialized_direct_fingerprint(
                gate, value.to_mapping(), final_master, binding) != getattr(value, name)):
            raise R2ExternalArtifactError()
    if runbook.retention_proof_fingerprint != proof.proof_fingerprint or inputs.ci_provenance_receipts != receipts:
        raise R2ExternalArtifactError()
def _require_ci_inputs(inputs, final_master):
    receipts = tuple(sorted(inputs.ci_provenance_receipts,
                            key=lambda item: item.provenance_kind.value))
    kinds = tuple(sorted(CiProvenanceKindV2, key=lambda item: item.value))
    if (len(receipts) != 3 or any(type(item) is not R2CiProvenanceReceiptV2 for item in receipts)
            or tuple(item.provenance_kind for item in receipts) != kinds):
        raise R2ExternalArtifactError()
    mappings = tuple(item.to_mapping() for item in receipts)
    if any(_require_ci_receipt(source, final_master, kind) != item.receipt_fingerprint
           for source, kind, item in zip(mappings, kinds, receipts, strict=True)):
        raise R2ExternalArtifactError()
    bundle = inputs.ci_provenance_bundle
    if (type(bundle) is not R2CiProvenanceBundleV2
            or _require_ci_bundle(bundle.to_mapping(), final_master, mappings)
            != bundle.bundle_fingerprint):
        raise R2ExternalArtifactError()
    return receipts
def _require_ci_receipt(source, final_master, kind):
    if (not _scalar_schema(R2CiProvenanceReceiptV2, source)
            or source["receipt_type"] != "R2CiProvenanceReceiptV2"
            or source["status"] != "CI_PROVENANCE_VERIFIED"
            or source["provenance_kind"] != kind.value
            or source["workflow_lock_fingerprint"] != final_master.workflow_fingerprint
            or source["runbook_fingerprint"] != final_master.runbook_fingerprint
            or source["suite_fingerprint"] != fixed_suite_fingerprint_v2(kind)
            or source["portable_full_suite"] != int(kind is CiProvenanceKindV2.PORTABLE)
            or not _positive(source, ("selected_entry_count", "selected_byte_count",
                                      "hash_locked_dependency_count", "wheel_hash_count"))
            or not _zero(source, _CI_ZERO) or not _fingerprints_valid(source)):
        raise R2ExternalArtifactError()
    _require_source_master(source, final_master)
    return _self_fingerprint(source, "receipt_fingerprint", "r2-ci-provenance-receipt-v2")
def _require_ci_bundle(source, final_master, receipts=()):
    zero = _CI_ZERO[:5]
    if (not _scalar_schema(R2CiProvenanceBundleV2, source)
            or (source["bundle_type"], source["status"])
            != ("R2CiProvenanceBundleV2", "CI_PROVENANCE_RECONCILED")
            or source["workflow_lock_fingerprint"] != final_master.workflow_fingerprint
            or source["runbook_fingerprint"] != final_master.runbook_fingerprint
            or (source["provenance_receipt_count"], source["runner_fingerprint_count"],
                source["portable_full_suite_receipt_count"]) != (3, 3, 1)
            or not _positive(source, ("hash_locked_dependency_count", "wheel_hash_count"))
            or not _zero(source, zero) or not _fingerprints_valid(source)):
        raise R2ExternalArtifactError()
    _require_source_master(source, final_master)
    if receipts:
        _require_ci_coherence(receipts)
        expected = fingerprint("r2-ci-provenance-receipt-set-v2",
                               [item["receipt_fingerprint"] for item in receipts])
        if (source["dependency_lock_fingerprint"] != receipts[0]["dependency_lock_fingerprint"]
                or source["hash_locked_dependency_count"] != receipts[0]["hash_locked_dependency_count"]
                or source["wheel_hash_count"] != receipts[0]["wheel_hash_count"] * 2
                or source["receipt_set_fingerprint"] != expected):
            raise R2ExternalArtifactError()
    return _self_fingerprint(source, "bundle_fingerprint", "r2-ci-provenance-bundle-v2")
def _require_ci_coherence(receipts):
    shared = lambda item: (item["selected_entry_count"], item["selected_byte_count"],
                           item["dependency_lock_fingerprint"], item["runbook_fingerprint"],
                           item["hash_locked_dependency_count"], item["wheel_hash_count"])
    if (len(receipts) != 3 or any(shared(item) != shared(receipts[0]) for item in receipts)
            or len({item["runner_fingerprint"] for item in receipts}) != 3
            or receipts[0]["platform_lock_fingerprint"] == receipts[1]["platform_lock_fingerprint"]
            or receipts[1]["platform_lock_fingerprint"] != receipts[2]["platform_lock_fingerprint"]):
        raise R2ExternalArtifactError()
def _require_reviews(inputs, final_master):
    expected = ((inputs.closure_surface_review, ClosureGate.CLOSURE_SURFACE_COMPLETENESS),
                (inputs.crash_recovery_review, ClosureGate.CRASH_RECOVERY),
                (inputs.documentation_review, ClosureGate.DOCUMENTATION),
                (inputs.mechanical_architecture_review, ClosureGate.MECHANICAL_ARCHITECTURE),
                (inputs.leakage_review, ClosureGate.LEAKAGE),
                (inputs.maintenance_review, ClosureGate.MAINTENANCE_SCOPE))
    for review, gate in expected:
        if (type(review) is not R2GateSourceReviewV1 or review.gate is not gate
                or _require_source_review_mapping_v1(
                    gate, review.to_mapping(), final_master) != review.review_fingerprint):
            raise R2ExternalArtifactError()
def _rederive_external_evidence_v1(package, final_master, binding):
    records, values = package.supporting_provenance_records, []
    if tuple(item.gate for item in records) != tuple(ClosureGate):
        raise R2ExternalArtifactError()
    for record in records:
        gate, source = record.gate, record.source_mapping
        if record.source_type != _SOURCE_TYPES[gate]:
            raise R2ExternalArtifactError()
        if gate is ClosureGate.PRODUCTION_COMPOSITION:
            value = production_composition_evidence_fingerprint_v2(final_master, binding)
            if source != binding.to_mapping():
                raise R2ExternalArtifactError()
        elif gate in _DIRECT:
            value = _serialized_direct_fingerprint(gate, source, final_master, binding)
        else:
            value = _require_source_review_mapping_v1(gate, source, final_master)
        if value != record.evidence_fingerprint:
            raise R2ExternalArtifactError()
        values.append(value)
    _require_cross_source_links(records, values, final_master)
    return tuple(values)
def _serialized_direct_fingerprint(gate, source, final_master, binding):
    name, domain, kind, omitted = _DIRECT[gate]
    if (not _scalar_schema(kind, source, omitted) or not _fingerprints_valid(source)
            or any(source.get(key) != item for key, item in _STATES[gate].items())):
        raise R2ExternalArtifactError()
    value = _self_fingerprint(source, name, domain)
    if gate is ClosureGate.FINAL_MASTER_BINDING:
        _require_frozen(source, final_master)
    elif gate is ClosureGate.GIT_BYTES:
        _require_git(source, final_master, binding)
    elif gate is ClosureGate.DEPENDENCY_ACTION_PROVENANCE:
        _require_ci_bundle(source, final_master)
    elif gate is ClosureGate.PORTABLE_FULL_SUITE:
        _require_ci_receipt(source, final_master, CiProvenanceKindV2.PORTABLE)
    elif gate is ClosureGate.RUNBOOK_SEMANTICS:
        _require_runbook(source, final_master, binding)
    elif gate is ClosureGate.RETENTION_NO_DELETION:
        _require_retention(source, binding)
    return value
def _require_frozen(source, final_master):
    expected = {"binding_fingerprint": final_master.binding_fingerprint,
                "final_commit_oid": final_master.final_commit_oid,
                "final_tree_oid": final_master.final_tree_oid,
                "source_package_fingerprint": final_master.source_package_fingerprint,
                "runbook_fingerprint": final_master.runbook_fingerprint,
                "workflow_fingerprint": final_master.workflow_fingerprint,
                "exact_match": 1, "historical_master_count": 0, "dirty_path_count": 0}
    if (not is_fingerprint(source["remote_ref_fingerprint"])
            or any(source.get(name) != value for name, value in expected.items())):
        raise R2ExternalArtifactError()
def _require_git(source, final_master, binding):
    if (source["binding_fingerprint"] != binding.binding_fingerprint
            or source["final_master_binding_fingerprint"] != final_master.binding_fingerprint
            or (source["local_ref_count"], source["stable_common_state_role_count"],
                source["original_worktree_count"], source["reconstructed_worktree_count"],
                source["worktree_count"], source["ignored_content_reads"],
                source["private_content_reads"]) != (14, 5, 11, 11, 11, 0, 0)
            or not _positive(source, ("selected_byte_count",))):
        raise R2ExternalArtifactError()
    _require_source_master(source, final_master)
def _require_runbook(source, final_master, binding):
    if (source["binding_fingerprint"] != binding.binding_fingerprint
            or source["runbook_fingerprint"] != binding.runbook_fingerprint
            or source["package_semantics_fingerprint"] != operator_package_semantics_fingerprint_v2()
            or source["decision_registry_fingerprint"] != decision_registry_fingerprint_v2()
            or source["blocker_resolution_fingerprint"] != blocker_resolution_fingerprint_v2()
            or (source["catalog_command_count"], source["state_phase_count"],
                source["decision_count"], source["r1_blocker_class_count"]) != (10, 8, 14, 4)
            or not _zero(source, ("historical_command_count", "deletion_capability_count",
                                  "mixed_binding_count"))):
        raise R2ExternalArtifactError()
    _require_source_master(source, final_master)
def _require_retention(source, binding):
    zero = ("untracked_artifact_count", "deletion_capability_count", "overwrite_capability_count",
            "prune_capability_count", "automatic_expiry_capability_count", "private_payload_field_count")
    if (source["binding_fingerprint"] != binding.binding_fingerprint
            or not _positive(source, ("reconciled_entry_count",)) or not _zero(source, zero)):
        raise R2ExternalArtifactError()
def _require_cross_source_links(records, values, final_master):
    by_gate = {item.gate: item for item in records}
    windows_record = by_gate[ClosureGate.WINDOWS_NATIVE]
    if any(item.supporting_source_mappings for item in records if item is not windows_record):
        raise R2ExternalArtifactError()
    windows = windows_record.supporting_source_mappings
    kinds = (CiProvenanceKindV2.WINDOWS_INDEPENDENT, CiProvenanceKindV2.WINDOWS_NATIVE)
    if len(windows) != 2:
        raise R2ExternalArtifactError()
    for source, kind in zip(windows, kinds, strict=True):
        _require_ci_receipt(source, final_master, kind)
    review_sources = windows_record.source_mapping["source_fingerprints"]
    if [item["fingerprint"] for item in review_sources] != [item["receipt_fingerprint"] for item in windows]:
        raise R2ExternalArtifactError()
    portable = by_gate[ClosureGate.PORTABLE_FULL_SUITE].source_mapping
    bundle = by_gate[ClosureGate.DEPENDENCY_ACTION_PROVENANCE].source_mapping
    _require_ci_bundle(bundle, final_master, (portable, *windows))
    retention = values[list(ClosureGate).index(ClosureGate.RETENTION_NO_DELETION)]
    if by_gate[ClosureGate.RUNBOOK_SEMANTICS].source_mapping["retention_proof_fingerprint"] != retention:
        raise R2ExternalArtifactError()
