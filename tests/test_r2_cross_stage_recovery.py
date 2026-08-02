"""Cross-stage restart and recovery state machine for Issue #82."""

from __future__ import annotations

import unittest

from backend.r2_cross_stage_recovery import (
    CrossStageRecoveryMachine,
    CrossStageStatus,
    EffectClassification,
    EffectObservation,
    PendingIntentV1,
    ReceiptPredecessorLinkV1,
    RecoveryBoundary,
    RecoveryFaultSelectorV1,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.r2_cross_stage_recovery_fixture import (
    BOUNDARIES,
    HEAD,
    NOW,
    RecoveryAdapters,
    snapshot,
)


class R2CrossStageRecoveryTests(unittest.TestCase):
    def test_pending_intents_use_stable_double_read_without_mutation(self):
        intents = tuple(
            PendingIntentV1.create(
                direction="forward",
                boundary=boundary,
                intent_fingerprint=opaque_fingerprint(8300 + index),
            )
            for index, boundary in enumerate(BOUNDARIES[:3])
        )
        adapters = RecoveryAdapters()
        adapters.observations = {
            intents[0].intent_fingerprint: EffectObservation.ABSENT,
            intents[1].intent_fingerprint: EffectObservation.PRESENT,
            intents[2].intent_fingerprint: EffectObservation.AMBIGUOUS,
        }
        result = self._machine(adapters, snapshot(pending=intents)).inspect()

        self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
        self.assertEqual(
            result.classifications,
            (
                EffectClassification.EFFECT_ABSENT_EXACT,
                EffectClassification.EFFECT_PRESENT_EXACT,
                EffectClassification.EFFECT_AMBIGUOUS,
            ),
        )
        self.assertEqual(len(adapters.calls), 6)
        self.assertEqual(adapters.mutations, 0)

    def test_unstable_double_read_is_ambiguous_and_read_only(self):
        intent = PendingIntentV1.create(
            direction="reverse",
            boundary=RecoveryBoundary.RESTORE_DATABASE,
            intent_fingerprint=opaque_fingerprint(8310),
        )
        adapters = RecoveryAdapters()
        values = iter((EffectObservation.ABSENT, EffectObservation.PRESENT))
        adapters.bundle = lambda: _bundle_with_observer(adapters, lambda _value: next(values))
        result = self._machine(adapters, snapshot(pending=(intent,))).inspect()
        self.assertEqual(result.classifications, (EffectClassification.EFFECT_AMBIGUOUS,))
        self.assertEqual(adapters.mutations, 0)

    def test_recovery_preserves_first_and_refreshes_authority_each_boundary(self):
        adapters = RecoveryAdapters()
        result = self._machine(adapters, snapshot()).recover(adapters.authority)

        self.assertIs(result.status, CrossStageStatus.LEGACY_FLAT_LAYOUT_RESTORED)
        reverses = [item for item in adapters.calls if item.startswith("reverse:")]
        self.assertEqual(
            reverses,
            [f"reverse:{boundary.value}" for boundary in BOUNDARIES],
        )
        self.assertEqual(BOUNDARIES[0], RecoveryBoundary.PRESERVE_FAILED_CONTAINER)
        self.assertEqual(len(adapters.authorities), len(BOUNDARIES))
        self.assertEqual(
            len({item.crash_nonce for item in adapters.authorities}),
            len(BOUNDARIES),
        )
        self.assertEqual(result.retained_new_objects, 17)
        self.assertEqual(result.cleanup_operations, 0)

    def test_reverse_effect_already_present_is_not_repeated(self):
        intent = PendingIntentV1.create(
            direction="reverse",
            boundary=RecoveryBoundary.PRESERVE_FAILED_CONTAINER,
            intent_fingerprint=opaque_fingerprint(8320),
        )
        committed = tuple(
            PendingIntentV1.create(
                direction="committed",
                boundary=boundary,
                intent_fingerprint=opaque_fingerprint(8321 + index),
            )
            for index, boundary in enumerate(BOUNDARIES[1:])
        )
        adapters = RecoveryAdapters()
        result = self._machine(
            adapters,
            snapshot(pending=(intent, *committed), preserved=True),
        ).recover(adapters.authority)
        self.assertIs(result.status, CrossStageStatus.LEGACY_FLAT_LAYOUT_RESTORED)
        self.assertNotIn("reverse:preserve_failed_container", adapters.calls)
        self.assertEqual(adapters.mutations, len(BOUNDARIES) - 1)

    def test_committed_effect_absence_is_an_incident_before_mutation(self):
        value = snapshot()
        adapters = RecoveryAdapters()
        first = value.pending_intents[0]
        adapters.observations[first.intent_fingerprint] = EffectObservation.ABSENT
        result = self._machine(adapters, value).recover(adapters.authority)
        self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
        self.assertEqual(adapters.mutations, 0)

    def test_duplicate_boundary_intents_are_rejected_before_recovery(self):
        boundary = RecoveryBoundary.RESTORE_DATABASE
        first = PendingIntentV1.create(
            direction="forward",
            boundary=boundary,
            intent_fingerprint=opaque_fingerprint(8311),
        )
        duplicate = PendingIntentV1.create(
            direction="committed",
            boundary=boundary,
            intent_fingerprint=opaque_fingerprint(8312),
        )
        with self.assertRaisesRegex(ValueError, "R2_RESTART_SNAPSHOT_INVALID"):
            snapshot(
                pending=(first, duplicate),
                remaining=(boundary,),
            )

    def test_reverse_effect_must_advance_the_durable_head(self):
        adapters = RecoveryAdapters()
        original = adapters.reverse

        def stale_head(boundary, authority):
            value = original(boundary, authority)
            adapters.head = value.prior_head_fingerprint
            from backend.r2_cross_stage_recovery import ReverseEffectEvidenceV1
            return ReverseEffectEvidenceV1.create(
                boundary=boundary,
                prior_head_fingerprint=value.prior_head_fingerprint,
                journal_head_fingerprint=value.prior_head_fingerprint,
                effect_fingerprint=value.effect_fingerprint,
                retained_new_objects=value.retained_new_objects,
                cleanup_operations=0,
            )

        adapters.reverse = stale_head
        result = self._machine(adapters, snapshot()).recover(adapters.authority)
        self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
        reverses = [item for item in adapters.calls if item.startswith("reverse:")]
        self.assertEqual(reverses, ["reverse:preserve_failed_container"])

    def test_failed_legacy_recovery_is_an_incident_stop(self):
        adapters = RecoveryAdapters()
        original = adapters.reverse

        def fail_legacy(boundary, authority):
            if boundary is RecoveryBoundary.RECOVER_LEGACY_SERVICE:
                raise RuntimeError("synthetic legacy recovery failure")
            return original(boundary, authority)

        adapters.reverse = fail_legacy
        result = self._machine(adapters, snapshot()).recover(adapters.authority)
        self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
        self.assertEqual(result.cleanup_operations, 0)

    def test_expiry_replay_and_head_drift_are_incident_stops(self):
        for mode in ("expired", "replay", "head_drift"):
            adapters = RecoveryAdapters()
            factory = _FaultyAuthority(adapters, mode)
            with self.subTest(mode=mode):
                result = self._machine(adapters, snapshot()).recover(factory)
                self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)

    def test_every_reverse_boundary_crash_requires_restart_without_cleanup(self):
        for boundary in BOUNDARIES:
            adapters = RecoveryAdapters()
            with self.subTest(boundary=boundary):
                machine = self._machine(
                    adapters,
                    snapshot(),
                    RecoveryFaultSelectorV1.crash_after_effect(boundary),
                )
                result = machine.recover(adapters.authority)
                self.assertIs(
                    result.status, CrossStageStatus.RECOVERY_RESTART_REQUIRED
                )
                self.assertEqual(result.cleanup_operations, 0)

    def test_receipt_predecessor_or_head_drift_incident_stops_before_mutation(self):
        bad = ReceiptPredecessorLinkV1.create(
            record_type="PUBLICATION_RECEIPT",
            material_fingerprint=opaque_fingerprint(8330),
            predecessor_fingerprint="0" * 64,
            prior_head_fingerprint="0" * 64,
        )
        adapters = RecoveryAdapters()
        result = self._machine(adapters, snapshot(links=(bad,))).recover(
            adapters.authority
        )
        self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
        self.assertEqual(adapters.mutations, 0)

    def test_single_unanchored_or_tampered_link_is_not_vacuously_valid(self):
        unanchored = ReceiptPredecessorLinkV1.create(
            record_type="PUBLICATION_RECEIPT",
            material_fingerprint=opaque_fingerprint(8340),
            predecessor_fingerprint=opaque_fingerprint(8341),
            prior_head_fingerprint=opaque_fingerprint(8342),
        )
        valid = snapshot(remaining=()).receipt_links[0]
        tampered = object.__new__(ReceiptPredecessorLinkV1)
        for name in (
            "record_type",
            "material_fingerprint",
            "receipt_fingerprint",
            "predecessor_fingerprint",
            "prior_head_fingerprint",
            "journal_head_fingerprint",
        ):
            object.__setattr__(tampered, name, getattr(valid, name))
        object.__setattr__(
            tampered, "receipt_fingerprint", opaque_fingerprint(8343)
        )
        for link, head in (
            (unanchored, unanchored.journal_head_fingerprint),
            (tampered, valid.journal_head_fingerprint),
        ):
            with self.subTest(link=link):
                adapters = RecoveryAdapters()
                result = self._machine(
                    adapters,
                    snapshot(links=(link,), remaining=(), head=head),
                ).inspect()
                self.assertIs(result.status, CrossStageStatus.INCIDENT_STOP)
                self.assertEqual(adapters.mutations, 0)

    def _machine(self, adapters, value, fault=None):
        return CrossStageRecoveryMachine.create(
            snapshot=value,
            adapters=adapters.bundle(),
            now=lambda: NOW,
            fault=fault or RecoveryFaultSelectorV1.none(),
        )


def _bundle_with_observer(adapters, observer):
    value = adapters.bundle.__wrapped__() if hasattr(adapters.bundle, "__wrapped__") else None
    from backend.r2_cross_stage_recovery import CrossStageAdaptersV1
    return CrossStageAdaptersV1(
        observe_intent=observer,
        current_journal_head=adapters.current_head,
        reverse_boundary=adapters.reverse,
        minimal_final_freshness=adapters.freshness,
        append_cutover_success=adapters.append_success,
    )


class _FaultyAuthority:
    def __init__(self, adapters, mode):
        self.adapters = adapters
        self.mode = mode
        self.first = None

    def __call__(self, boundary, head, plan):
        if self.mode == "head_drift":
            self.adapters.head = opaque_fingerprint(8390)
        value = self.adapters.authority(boundary, head, plan)
        if self.mode == "expired":
            from backend.r2_cross_stage_recovery import ReverseBoundaryAuthorityV1
            return ReverseBoundaryAuthorityV1.create(
                boundary=boundary,
                journal_head_fingerprint=head,
                remaining_plan_fingerprint=plan,
                crash_nonce=value.crash_nonce,
                issued_at_epoch=NOW - 10,
                expires_at_epoch=NOW,
            )
        if self.mode == "replay":
            if self.first is None:
                self.first = value
            elif boundary is not self.first.boundary:
                from backend.r2_cross_stage_recovery import ReverseBoundaryAuthorityV1
                return ReverseBoundaryAuthorityV1.create(
                    boundary=boundary,
                    journal_head_fingerprint=head,
                    remaining_plan_fingerprint=plan,
                    crash_nonce=self.first.crash_nonce,
                    issued_at_epoch=NOW - 1,
                    expires_at_epoch=NOW + 60,
                )
        return value


if __name__ == "__main__":
    unittest.main()
