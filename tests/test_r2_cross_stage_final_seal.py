"""Final audit binding and mutation-free success seal for Issue #82."""

from __future__ import annotations

import unittest

from backend.r2_cross_stage_recovery import (
    CrossStageRecoveryMachine,
    CrossStageStatus,
    CutoverSuccessAppendV1,
    FinalFreshnessObservationV1,
    FinalSealRequestV1,
    PendingIntentV1,
    RecoveryBoundary,
    RecoveryFaultSelectorV1,
)
from backend.r2_independent_audits import AuditKind
from backend.r2_validation_lifecycle import (
    IndependentAuditCompletionV1,
    ValidationLifecycleResultV1,
    ValidationStatus,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.r2_cross_stage_recovery_fixture import (
    HEAD,
    IDENTITIES,
    NONCE_A,
    NONCE_B,
    NOW,
    RecoveryAdapters,
    snapshot,
)


STOPPED_IDENTITIES = opaque_fingerprint(8400)
FINAL_IDENTITIES = opaque_fingerprint(8401)
STOPPED_HEALTH = opaque_fingerprint(8402)
FINAL_HEALTH = opaque_fingerprint(8403)


class R2CrossStageFinalSealTests(unittest.TestCase):
    def test_final_seal_binds_both_audits_and_appends_only_cutover_success(self):
        adapters = RecoveryAdapters()
        self._enable_seal(adapters)
        machine = self._machine(adapters, snapshot(remaining=()))
        result = machine.seal(self._request())

        self.assertIs(result.status, CrossStageStatus.CUTOVER_SUCCESS)
        self.assertEqual(result.host_mutations, 0)
        self.assertEqual(result.journal_appends, 1)
        self.assertEqual(adapters.freshness_reads, 1)
        self.assertEqual(adapters.success_appends, 1)
        self.assertEqual(adapters.mutations, 0)
        self.assertEqual(adapters.calls[-2:], ["minimal_freshness", "CUTOVER_SUCCESS"])
        with self.assertRaises(ValueError):
            machine.seal(self._request())

    def test_audit_expiry_head_nonce_and_identity_drift_cannot_seal(self):
        for mode in ("audit_expiry", "head", "nonce", "identities"):
            adapters = RecoveryAdapters()
            self._enable_seal(adapters, mode=mode)
            request = self._request(
                expired=(mode == "audit_expiry")
            )
            with self.subTest(mode=mode):
                result = self._machine(
                    adapters, snapshot(remaining=())
                ).seal(request)
                self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
                self.assertEqual(adapters.success_appends, 0)
                self.assertEqual(adapters.mutations, 0)

    def test_pending_intent_or_remaining_plan_blocks_final_seal(self):
        intent = PendingIntentV1.create(
            direction="forward",
            boundary=RecoveryBoundary.RESTORE_ACL,
            intent_fingerprint=opaque_fingerprint(8410),
        )
        for value in (
            snapshot(pending=(intent,), remaining=()),
            snapshot(),
        ):
            adapters = RecoveryAdapters()
            self._enable_seal(adapters)
            result = self._machine(adapters, value).seal(self._request())
            self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
            self.assertEqual(adapters.freshness_reads, 0)

    def _enable_seal(self, adapters, mode="ok"):
        def freshness():
            adapters.calls.append("minimal_freshness")
            adapters.freshness_reads += 1
            return FinalFreshnessObservationV1.create(
                journal_head_fingerprint=(
                    opaque_fingerprint(8490) if mode == "head" else HEAD
                ),
                nonce_b=(NONCE_A if mode == "nonce" else NONCE_B),
                approved_identities_fingerprint=(
                    opaque_fingerprint(8491)
                    if mode == "identities"
                    else IDENTITIES
                ),
                observed_at_epoch=NOW,
            )

        def append(record_type, prior_head, material):
            adapters.calls.append(record_type)
            adapters.success_appends += 1
            return CutoverSuccessAppendV1.create(
                record_type=record_type,
                prior_head_fingerprint=prior_head,
                journal_head_fingerprint=opaque_fingerprint(8492),
                material_fingerprint=material,
            )

        adapters.freshness = freshness
        adapters.append_success = append
        original = adapters.bundle
        adapters.bundle = lambda: _seal_bundle(adapters, original())

    def _request(self, *, expired=False):
        expires = NOW if expired else NOW + 299
        stopped = IndependentAuditCompletionV1.create(
            audit_kind=AuditKind.STOPPED_LAYOUT,
            audit_process_id=5101,
            service_nonce=NONCE_A,
            service_process_id=4101,
            journal_head_fingerprint=HEAD,
            approved_identities_fingerprint=STOPPED_IDENTITIES,
            health_evidence_fingerprint=STOPPED_HEALTH,
            observed_at_epoch=NOW - 1,
            expires_at_epoch=expires,
            attested=True,
        )
        final = IndependentAuditCompletionV1.create(
            audit_kind=AuditKind.FINAL_RUNNING_HEALTH,
            audit_process_id=5201,
            service_nonce=NONCE_B,
            service_process_id=4201,
            journal_head_fingerprint=HEAD,
            approved_identities_fingerprint=FINAL_IDENTITIES,
            health_evidence_fingerprint=FINAL_HEALTH,
            observed_at_epoch=NOW - 1,
            expires_at_epoch=expires,
            attested=True,
        )
        validation = ValidationLifecycleResultV1(
            ValidationStatus.VALIDATED,
            11,
            1,
            1,
            0,
            opaque_fingerprint(8420),
        )
        return FinalSealRequestV1.create(
            validation=validation,
            stopped_audit=stopped,
            final_audit=final,
            current_journal_head=HEAD,
            nonce_b=NONCE_B,
            approved_identities_fingerprint=IDENTITIES,
            stopped_identities_fingerprint=STOPPED_IDENTITIES,
            final_identities_fingerprint=FINAL_IDENTITIES,
        )

    def _machine(self, adapters, value):
        return CrossStageRecoveryMachine.create(
            snapshot=value,
            adapters=adapters.bundle(),
            now=lambda: NOW,
            fault=RecoveryFaultSelectorV1.none(),
        )


def _seal_bundle(adapters, original):
    from backend.r2_cross_stage_recovery import CrossStageAdaptersV1
    return CrossStageAdaptersV1(
        observe_intent=original.observe_intent,
        current_journal_head=original.current_journal_head,
        reverse_boundary=original.reverse_boundary,
        minimal_final_freshness=adapters.freshness,
        append_cutover_success=adapters.append_success,
    )


if __name__ == "__main__":
    unittest.main()
