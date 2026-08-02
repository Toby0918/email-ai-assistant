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
from backend.r2_validation_lifecycle import (
    ValidationFaultSelectorV1,
    ValidationLifecycle,
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
from tests.r2_validation_lifecycle_fixture import (
    SyntheticValidationAdapters,
    approved_slice,
)


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
        self.assertEqual(
            adapters.calls[-3:],
            ["minimal_freshness", "CUTOVER_SUCCESS", "head"],
        )
        with self.assertRaises(ValueError):
            machine.seal(self._request())

    def test_success_append_requires_a_new_durably_observed_head(self):
        adapters = RecoveryAdapters()
        self._enable_seal(adapters, advance_head=False)
        result = self._machine(adapters, snapshot(remaining=())).seal(
            self._request()
        )
        self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
        self.assertEqual(result.journal_appends, 0)
        self.assertEqual(adapters.success_appends, 1)

    def test_audit_expiry_head_nonce_and_identity_drift_cannot_seal(self):
        for mode in ("audit_expiry", "head", "nonce", "identities"):
            adapters = RecoveryAdapters()
            self._enable_seal(adapters, mode=mode)
            request = self._request()
            with self.subTest(mode=mode):
                result = self._machine(
                    adapters,
                    snapshot(remaining=()),
                    now_epoch=(NOW + 301 if mode == "audit_expiry" else NOW),
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

    def _enable_seal(self, adapters, mode="ok", advance_head=True):
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
                observed_at_epoch=(NOW + 301 if mode == "audit_expiry" else NOW),
            )

        def append(record_type, prior_head, material):
            adapters.calls.append(record_type)
            adapters.success_appends += 1
            new_head = opaque_fingerprint(8492)
            if advance_head:
                adapters.head = new_head
            return CutoverSuccessAppendV1.create(
                record_type=record_type,
                prior_head_fingerprint=prior_head,
                journal_head_fingerprint=new_head,
                material_fingerprint=material,
            )

        adapters.freshness = freshness
        adapters.append_success = append
        original = adapters.bundle
        adapters.bundle = lambda: _seal_bundle(adapters, original())

    def _request(self):
        validation = ValidationLifecycle.create(
            approved=approved_slice(),
            adapters=SyntheticValidationAdapters().bundle(),
            nonce_factory=iter((NONCE_A, NONCE_B)).__next__,
            now=lambda: NOW,
            fault=ValidationFaultSelectorV1.none(),
        ).run()
        stopped = validation.stopped_audit
        final = validation.final_audit
        return FinalSealRequestV1.create(
            validation=validation,
            current_journal_head=HEAD,
            nonce_b=NONCE_B,
            approved_identities_fingerprint=IDENTITIES,
            stopped_identities_fingerprint=stopped.approved_identities_fingerprint,
            final_identities_fingerprint=final.approved_identities_fingerprint,
        )

    def _machine(self, adapters, value, now_epoch=NOW):
        return CrossStageRecoveryMachine.create(
            snapshot=value,
            adapters=adapters.bundle(),
            now=lambda: now_epoch,
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
