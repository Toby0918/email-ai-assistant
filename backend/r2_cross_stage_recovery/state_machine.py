"""Read-only restart inspection, exact reverse recovery, and final seal."""

from __future__ import annotations

from backend.cutover_composition_contracts.canonical import fingerprint, is_fingerprint
from backend.r2_independent_audits import (
    IndependentFinalRunningHealthReceiptV1,
    IndependentStoppedLayoutAuditReceiptV1,
    is_issued_audit_receipt,
)

from .adapters import CrossStageAdaptersV1
from .contracts import CrossStageResultV1, CrossStageStatus, CutoverSuccessAppendV1, EffectClassification, EffectObservation, FinalFreshnessObservationV1, FinalSealRequestV1, RecoveryBoundary, RecoveryCrashGap, RecoveryFaultSelectorV1, RestartSnapshotV1, ReverseBoundaryAuthorityV1, ReverseEffectEvidenceV1, plan_fingerprint
from .receipt_links import INITIAL_JOURNAL_HEAD_FINGERPRINT, INITIAL_RECEIPT_FINGERPRINT, ReceiptPredecessorLinkV1, is_valid_receipt_link


class CrossStageRecoveryMachine:
    __slots__ = ("_snapshot", "_adapters", "_now", "_fault", "_state", "_classifications", "_head", "_nonces", "_completed", "_host_mutations", "_journal_appends")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("CrossStageRecoveryMachine requires create()")

    @classmethod
    def create(cls, *, snapshot, adapters, now, fault):
        if type(snapshot) is not RestartSnapshotV1 or type(adapters) is not CrossStageAdaptersV1 or not adapters.exact() or not callable(now) or type(fault) is not RecoveryFaultSelectorV1:
            raise ValueError("R2_CROSS_STAGE_BINDING_INVALID")
        value = object.__new__(cls)
        value._snapshot, value._adapters = snapshot, adapters
        value._now, value._fault, value._state = now, fault, "ready"
        value._classifications, value._head, value._nonces = (), snapshot.current_journal_head, set()
        value._completed = value._host_mutations = value._journal_appends = 0
        return value

    def inspect(self):
        self._begin()
        self._classifications = self._inspect_pending()
        status = CrossStageStatus.INSPECTED
        if not self._links_valid() or EffectClassification.EFFECT_AMBIGUOUS in self._classifications:
            status = CrossStageStatus.INCIDENT_STOP
        self._state = "complete"
        return self._result(status)

    def recover(self, authority_factory):
        self._begin()
        if not callable(authority_factory):
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        self._classifications = self._inspect_pending()
        if not self._links_valid() or EffectClassification.EFFECT_AMBIGUOUS in self._classifications:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if not self._recovery_observations_valid():
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        skipped_effects = self._skip_reverse_effects()
        remaining = list(self._snapshot.remaining_reverse_plan)
        for boundary in tuple(remaining):
            if boundary in skipped_effects or self._preserved(boundary):
                remaining.pop(0)
                self._completed += 1
                continue
            status = self._reverse_one(boundary, remaining, authority_factory)
            if status is not None:
                return self._finish(status)
            remaining.pop(0)
        if remaining or self._snapshot.remaining_reverse_plan and self._snapshot.remaining_reverse_plan[-1] is not RecoveryBoundary.RECOVER_LEGACY_SERVICE:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        return self._finish(CrossStageStatus.LEGACY_FLAT_LAYOUT_RESTORED)

    def seal(self, request):
        self._begin()
        if self._seal_cut(RecoveryCrashGap.BEFORE_INTENT):
            return self._finish(CrossStageStatus.RECOVERY_RESTART_REQUIRED)
        if type(request) is not FinalSealRequestV1 or self._snapshot.pending_intents or self._snapshot.remaining_reverse_plan or not self._links_valid():
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if self._seal_cut(RecoveryCrashGap.AFTER_INTENT):
            return self._finish(CrossStageStatus.RECOVERY_RESTART_REQUIRED)
        try:
            freshness = self._adapters.minimal_final_freshness()
        except Exception:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if not self._valid_freshness(request, freshness) or not self._valid_audits(request):
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        material = self._seal_material(request)
        try:
            appended = self._adapters.append_cutover_success("CUTOVER_SUCCESS", request.current_journal_head, material)
        except Exception:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if type(appended) is not CutoverSuccessAppendV1 or appended.record_type != "CUTOVER_SUCCESS" or appended.prior_head_fingerprint != request.current_journal_head or appended.material_fingerprint != material:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if appended.journal_head_fingerprint == request.current_journal_head:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if self._seal_cut(RecoveryCrashGap.AFTER_EFFECT):
            self._journal_appends = 1
            return self._finish(CrossStageStatus.RECOVERY_RESTART_REQUIRED)
        try:
            durable_head = self._adapters.current_journal_head()
        except Exception:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        if durable_head != appended.journal_head_fingerprint:
            return self._finish(CrossStageStatus.INCIDENT_STOP)
        self._journal_appends = 1
        if self._seal_cut(RecoveryCrashGap.AFTER_STABLE_OBSERVATION):
            return self._finish(CrossStageStatus.RECOVERY_RESTART_REQUIRED)
        self._head = durable_head
        if self._seal_cut(RecoveryCrashGap.AFTER_COMMIT):
            return self._finish(CrossStageStatus.RECOVERY_RESTART_REQUIRED)
        return self._finish(CrossStageStatus.CUTOVER_SUCCESS)

    def _inspect_pending(self):
        classifications = []
        for intent in self._snapshot.pending_intents:
            try:
                first = self._adapters.observe_intent(intent)
                second = self._adapters.observe_intent(intent)
            except Exception:
                first = second = EffectObservation.AMBIGUOUS
            classifications.append(self._classify(first, second))
        return tuple(classifications)

    def _reverse_one(self, boundary, remaining, authority_factory):
        if self._recovery_cut(boundary, RecoveryCrashGap.BEFORE_INTENT):
            return CrossStageStatus.RECOVERY_RESTART_REQUIRED
        try:
            if self._adapters.current_journal_head() != self._head:
                return CrossStageStatus.INCIDENT_STOP
            plan = plan_fingerprint(tuple(remaining))
            authority = authority_factory(boundary, self._head, plan)
            if not self._valid_authority(authority, boundary, plan):
                return CrossStageStatus.INCIDENT_STOP
            if self._recovery_cut(boundary, RecoveryCrashGap.AFTER_INTENT):
                return CrossStageStatus.RECOVERY_RESTART_REQUIRED
            effect = self._adapters.reverse_boundary(boundary, authority)
            if not self._valid_effect(effect, boundary):
                return CrossStageStatus.INCIDENT_STOP
            self._host_mutations += 1
            if self._recovery_cut(boundary, RecoveryCrashGap.AFTER_EFFECT):
                return CrossStageStatus.RECOVERY_RESTART_REQUIRED
            if self._adapters.current_journal_head() != effect.journal_head_fingerprint:
                return CrossStageStatus.INCIDENT_STOP
            if self._recovery_cut(boundary, RecoveryCrashGap.AFTER_STABLE_OBSERVATION):
                return CrossStageStatus.RECOVERY_RESTART_REQUIRED
        except Exception:
            return CrossStageStatus.INCIDENT_STOP
        self._head = effect.journal_head_fingerprint
        self._completed += 1
        if self._recovery_cut(boundary, RecoveryCrashGap.AFTER_COMMIT):
            return CrossStageStatus.RECOVERY_RESTART_REQUIRED
        return None

    def _recovery_cut(self, boundary, gap):
        return self._fault.kind == "recovery_crash" and self._fault.boundary is boundary and self._fault.gap is gap

    def _seal_cut(self, gap):
        return self._fault.kind == "seal_crash" and self._fault.gap is gap

    def _valid_authority(self, value, boundary, plan):
        now = self._now()
        if type(value) is not ReverseBoundaryAuthorityV1 or type(now) is not int:
            return False
        exact = value.boundary is boundary and value.journal_head_fingerprint == self._head and value.remaining_plan_fingerprint == plan and value.issued_at_epoch <= now < value.expires_at_epoch
        if not exact or value.crash_nonce in self._nonces:
            return False
        self._nonces.add(value.crash_nonce)
        return True

    def _valid_effect(self, value, boundary):
        return type(value) is ReverseEffectEvidenceV1 and value.boundary is boundary and value.prior_head_fingerprint == self._head and is_fingerprint(value.journal_head_fingerprint) and value.journal_head_fingerprint != self._head and value.retained_new_objects == self._snapshot.retained_new_object_count and value.cleanup_operations == 0

    def _valid_freshness(self, request, value):
        now = self._now()
        return type(value) is FinalFreshnessObservationV1 and type(now) is int and value.observed_at_epoch == now and value.journal_head_fingerprint == request.current_journal_head == self._snapshot.current_journal_head and value.nonce_b == request.nonce_b and value.approved_identities_fingerprint == request.approved_identities_fingerprint == self._snapshot.approved_identities_fingerprint

    def _valid_audits(self, request):
        stopped = request.validation.stopped_audit
        final = request.validation.final_audit
        now = self._now()
        if type(stopped) is not IndependentStoppedLayoutAuditReceiptV1 or type(final) is not IndependentFinalRunningHealthReceiptV1 or not is_issued_audit_receipt(stopped) or not is_issued_audit_receipt(final) or type(now) is not int:
            return False
        common = stopped.journal_head_fingerprint == final.journal_head_fingerprint == request.current_journal_head and stopped.approved_identities_fingerprint == request.stopped_identities_fingerprint and final.approved_identities_fingerprint == request.final_identities_fingerprint and stopped.process_id != final.process_id
        fresh = all(item.observed_at_epoch <= now < item.expires_at_epoch and item.expires_at_epoch - item.observed_at_epoch == 300 for item in (stopped, final))
        return common and fresh

    def _links_valid(self):
        links = self._snapshot.receipt_links
        if not links or any(not is_valid_receipt_link(item) for item in links):
            return False
        first = links[0]
        anchored = (
            first.record_type == "PUBLICATION_RECEIPT"
            and first.predecessor_fingerprint == INITIAL_RECEIPT_FINGERPRINT
            and first.prior_head_fingerprint
            == INITIAL_JOURNAL_HEAD_FINGERPRINT
        )
        if not anchored or links[-1].journal_head_fingerprint != self._snapshot.current_journal_head:
            return False
        if any(item.record_type != "PUBLICATION_RECEIPT" for item in links):
            return False
        return all(current.predecessor_fingerprint == prior.receipt_fingerprint and current.prior_head_fingerprint == prior.journal_head_fingerprint for prior, current in zip(links, links[1:]))

    def _recovery_observations_valid(self):
        observed = {item.boundary for item in self._snapshot.pending_intents}
        if any(item not in observed for item in self._snapshot.remaining_reverse_plan):
            return False
        return all(
            intent.direction != "committed"
            or classification is EffectClassification.EFFECT_PRESENT_EXACT
            for intent, classification in zip(
                self._snapshot.pending_intents, self._classifications
            )
        )

    def _skip_reverse_effects(self):
        skipped = set()
        for intent, classification in zip(
            self._snapshot.pending_intents, self._classifications
        ):
            if intent.direction == "reverse" and classification is EffectClassification.EFFECT_PRESENT_EXACT:
                skipped.add(intent.boundary)
            if intent.direction == "forward" and classification is EffectClassification.EFFECT_ABSENT_EXACT:
                skipped.add(intent.boundary)
        return skipped

    def _preserved(self, boundary):
        return boundary is RecoveryBoundary.PRESERVE_FAILED_CONTAINER and self._snapshot.failed_container_preserved

    def _seal_material(self, request):
        return fingerprint("r2-cutover-success-material-v1", {"validation": request.validation.receipt_fingerprint, "stopped_process": request.validation.stopped_audit.process_id, "final_process": request.validation.final_audit.process_id, "head": request.current_journal_head, "nonce_b": request.nonce_b, "identities": request.approved_identities_fingerprint})

    def _classify(self, first, second):
        if first is second is EffectObservation.ABSENT:
            return EffectClassification.EFFECT_ABSENT_EXACT
        if first is second is EffectObservation.PRESENT:
            return EffectClassification.EFFECT_PRESENT_EXACT
        return EffectClassification.EFFECT_AMBIGUOUS

    def _begin(self):
        if self._state != "ready":
            raise ValueError("R2_CROSS_STAGE_SINGLE_USE")
        self._state = "running"

    def _finish(self, status):
        self._state = "complete"
        return self._result(status)

    def _result(self, status):
        body = {"status": status.value, "classifications": [item.value for item in self._classifications], "completed": self._completed, "retained": self._snapshot.retained_new_object_count, "host_mutations": self._host_mutations, "journal_appends": self._journal_appends}
        return CrossStageResultV1(status, self._classifications, self._completed, self._snapshot.retained_new_object_count, 0, self._host_mutations, self._journal_appends, fingerprint("r2-cross-stage-result-v1", body))
