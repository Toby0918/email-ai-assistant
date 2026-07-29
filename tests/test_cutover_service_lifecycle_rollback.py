"""Journal-driven rollback and legacy recovery tests for Issue #58."""

from __future__ import annotations

import unittest

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.cutover_service_lifecycle import (
    ActivationFailureKind,
    FailedContainerPublicationReceiptV1,
    JournalDrivenRollbackAdapter,
    LegacyPrerequisiteEvidenceV1,
    LegacyServiceAdapter,
    LifecycleStatus,
    NewServiceAdapter,
    ProviderDisabledLifecycleTransaction,
    ProviderDisabledServiceAdapters,
    ProviderDisabledServiceController,
    RollbackRestoreEvidenceV1,
    RollbackStage,
    RollbackStageEvidenceV1,
    ServiceBoundaryFailure,
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
    ServiceStopEvidenceV1,
    SyntheticActivationEvidenceV1,
    SyntheticRowEvidenceV1,
)
from tests.test_cutover_service_lifecycle_activation import (
    PROFILE,
    publication_receipts,
)


OPERATION = "6" * 64
JOURNAL_HEAD = "7" * 64
NOW = 1_900_000_000


class _LifecycleHarness:
    def __init__(self, *, activation_failure=None, legacy_failure=False):
        self.events: list[str] = []
        self.activation_failure = activation_failure
        self.legacy_failure = legacy_failure
        self.new_start = None
        self.legacy_starts = 0
        self.legacy_health = 0

    def service_adapters(self):
        new = NewServiceAdapter(
            start_provider_disabled=self.start_new,
            read_health=self.health_new,
            analyze_fixed_synthetic=self.analyze,
            observe_synthetic_row=self.row,
            stop_exact=self.stop_new,
        )
        legacy = LegacyServiceAdapter(
            start_provider_disabled_recovery=self.start_legacy,
            read_health=self.health_legacy,
            stop_exact=lambda start: ServiceStopEvidenceV1.create_from_start(
                start
            ),
        )
        return ProviderDisabledServiceAdapters(
            new_service=new, legacy_service=legacy
        )

    def rollback_adapter(self, fail_stage=None):
        def maybe(stage, value):
            self.events.append(stage)
            if fail_stage == stage:
                raise RuntimeError("private fixture detail")
            return value

        return JournalDrivenRollbackAdapter(
            verify_new_service_stopped=lambda stop: maybe(
                "stopped",
                RollbackStageEvidenceV1.create(
                    stage=RollbackStage.NEW_SERVICE_STOPPED,
                    journal_head_fingerprint=JOURNAL_HEAD,
                    observation_fingerprint="8" * 64,
                    retained_external=0,
                    retained_git_records=0,
                ),
            ),
            preserve_new_evidence=lambda: maybe(
                "preserved",
                RollbackStageEvidenceV1.create(
                    stage=RollbackStage.NEW_EVIDENCE_PRESERVED,
                    journal_head_fingerprint=JOURNAL_HEAD,
                    observation_fingerprint="9" * 64,
                    retained_external=3,
                    retained_git_records=11,
                ),
            ),
            publish_failed_container=lambda preserved: maybe(
                "failed_container",
                FailedContainerPublicationReceiptV1.create(
                    journal_head_fingerprint=JOURNAL_HEAD,
                    failed_container_fingerprint="a" * 64,
                    retained_external=3,
                    retained_git_records=11,
                ),
            ),
            restore_original_topology=lambda failed: maybe(
                "restored",
                RollbackRestoreEvidenceV1.create(
                    journal_head_fingerprint=JOURNAL_HEAD,
                    failed_container_receipt_fingerprint=(
                        failed.receipt_fingerprint
                    ),
                    main_restored=1,
                    git_records_restored=11,
                    embedded_worktrees_restored=8,
                    external_worktrees_restored=3,
                ),
            ),
            verify_legacy_prerequisites=lambda restored: maybe(
                "prerequisites",
                LegacyPrerequisiteEvidenceV1.create(
                    journal_head_fingerprint=JOURNAL_HEAD,
                    rollback_observation_fingerprint=(
                        restored.observation_fingerprint
                    ),
                    parent_descriptor_fingerprint="b" * 64,
                    finance_descriptor_fingerprint="c" * 64,
                    original_database_fingerprint="d" * 64,
                    sidecar_state_fingerprint="e" * 64,
                    legacy_runtime_fingerprint="f" * 64,
                    repository_identity_fingerprint="0" * 64,
                    git_records_verified=11,
                    worktrees_verified=11,
                ),
            ),
        )

    def start_new(self, request):
        self.events.append("start_new")
        if self.activation_failure in {
            ActivationFailureKind.START_REJECTED,
            ActivationFailureKind.JOURNAL_AMBIGUITY,
            ActivationFailureKind.REPARSE_AMBIGUITY,
            ActivationFailureKind.SAFETY_AMBIGUITY,
        }:
            raise ServiceBoundaryFailure(self.activation_failure)
        self.new_start = ServiceStartEvidenceV1.create(
            role=ServiceRole.NEW,
            pid=4100,
            start_time_ns=1_900_000_000_000_000_000,
            executable_fingerprint=request.runtime_fingerprint,
            port=request.port,
            port_owner_pid=4100,
            profile_fingerprint=request.profile_fingerprint,
            runtime_fingerprint=request.runtime_fingerprint,
            config_fingerprint=request.config_fingerprint,
            data_role_fingerprint=request.data_role_fingerprint,
            nonce=request.nonce,
            primary_provider="disabled",
            fallback_provider="disabled",
        )
        return self.new_start

    def health_new(self, start):
        self.events.append("health_new")
        if (
            self.activation_failure
            is ActivationFailureKind.HEALTH_REJECTED
        ):
            raise ServiceBoundaryFailure(self.activation_failure)
        return ServiceHealthEvidenceV1.create_from_start(start)

    def analyze(self, request):
        self.events.append("analyze")
        if (
            self.activation_failure
            is ActivationFailureKind.DETERMINISTIC_RESULT_REJECTED
        ):
            raise ServiceBoundaryFailure(self.activation_failure)
        attempts = (
            1
            if self.activation_failure
            is ActivationFailureKind.PROVIDER_BOUNDARY_AMBIGUITY
            else 0
        )
        return SyntheticActivationEvidenceV1.create(
            request_fingerprint=request.request_fingerprint,
            route="deterministic_rules",
            provider_attempts=attempts,
            result_fingerprint="1" * 64,
        )

    def row(self, request):
        self.events.append("row")
        matching = (
            0
            if self.activation_failure
            is ActivationFailureKind.PERSISTENCE_REJECTED
            else 1
        )
        return SyntheticRowEvidenceV1.create(
            request_fingerprint=request.request_fingerprint,
            data_role_fingerprint=publication_receipts().receipts[
                1
            ].receipt_fingerprint,
            matching_rows=matching,
        )

    def stop_new(self, start):
        self.events.append("stop_new")
        return ServiceStopEvidenceV1.create_from_start(start)

    def start_legacy(self, request):
        self.events.append("start_legacy")
        self.legacy_starts += 1
        if self.legacy_failure:
            raise RuntimeError("private legacy fixture detail")
        return ServiceStartEvidenceV1.create(
            role=ServiceRole.LEGACY,
            pid=4200,
            start_time_ns=1_900_000_100_000_000_000,
            executable_fingerprint=request.runtime_fingerprint,
            port=request.port,
            port_owner_pid=4200,
            profile_fingerprint=request.profile_fingerprint,
            runtime_fingerprint=request.runtime_fingerprint,
            config_fingerprint=request.config_fingerprint,
            data_role_fingerprint=request.data_role_fingerprint,
            nonce=request.nonce,
            primary_provider="disabled",
            fallback_provider="disabled",
        )

    def health_legacy(self, start):
        self.events.append("health_legacy")
        self.legacy_health += 1
        return ServiceHealthEvidenceV1.create_from_start(start)


def recovery_authorization():
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint=PROFILE,
        operation_fingerprint=OPERATION,
        phase="rollback",
        expires_at_epoch=NOW + 600,
    )


def transaction(harness, *, fail_stage=None):
    controller = ProviderDisabledServiceController.create(
        profile_fingerprint=PROFILE,
        adapters=harness.service_adapters(),
    )
    return ProviderDisabledLifecycleTransaction.create(
        operation_fingerprint=OPERATION,
        profile_fingerprint=PROFILE,
        journal_head_fingerprint=JOURNAL_HEAD,
        publications=publication_receipts(),
        controller=controller,
        rollback_adapter=harness.rollback_adapter(fail_stage),
    )


class LifecycleRollbackTests(unittest.TestCase):
    def test_known_pre_mutation_start_rejection_is_safe_abort(self):
        harness = _LifecycleHarness(
            activation_failure=ActivationFailureKind.START_REJECTED
        )
        lifecycle = transaction(harness)

        result = lifecycle.activate_new_service()

        self.assertIs(result.status, LifecycleStatus.SAFE_ABORT)
        self.assertEqual(
            (result.containment_attempted, result.contained), (0, 0)
        )
        self.assertNotIn("stop_new", harness.events)
        with self.assertRaisesRegex(
            Exception, "^lifecycle_rollback_not_allowed$"
        ):
            lifecycle.rollback_and_recover_legacy(
                authorization=recovery_authorization(),
                observed_at_epoch=NOW,
            )

    def test_success_is_terminal_and_never_enters_rollback(self):
        harness = _LifecycleHarness()
        lifecycle = transaction(harness)

        result = lifecycle.activate_new_service()

        self.assertIs(result.status, LifecycleStatus.CUTOVER_SUCCEEDED)
        self.assertEqual(result.provider_attempts, 0)
        self.assertEqual(harness.events.count("start_new"), 1)
        with self.assertRaisesRegex(
            Exception, "^lifecycle_rollback_not_allowed$"
        ):
            lifecycle.rollback_and_recover_legacy(
                authorization=recovery_authorization(),
                observed_at_epoch=NOW,
            )

    def test_all_known_post_mutation_failures_require_rollback(self):
        for failure in (
            ActivationFailureKind.HEALTH_REJECTED,
            ActivationFailureKind.DETERMINISTIC_RESULT_REJECTED,
            ActivationFailureKind.PERSISTENCE_REJECTED,
        ):
            with self.subTest(failure=failure.value):
                harness = _LifecycleHarness(activation_failure=failure)
                result = transaction(harness).activate_new_service()
                self.assertIs(
                    result.status, LifecycleStatus.ROLLBACK_REQUIRED
                )

    def test_all_ambiguity_classes_incident_stop_without_guessing(self):
        for failure in (
            ActivationFailureKind.JOURNAL_AMBIGUITY,
            ActivationFailureKind.REPARSE_AMBIGUITY,
            ActivationFailureKind.SAFETY_AMBIGUITY,
        ):
            with self.subTest(failure=failure.value):
                harness = _LifecycleHarness(activation_failure=failure)
                result = transaction(harness).activate_new_service()
                self.assertIs(result.status, LifecycleStatus.INCIDENT_STOP)
                self.assertEqual(
                    (result.containment_attempted, result.contained),
                    (0, 0),
                )
                self.assertNotIn("stop_new", harness.events)

    def test_known_failure_requires_authorized_journal_rollback(self):
        harness = _LifecycleHarness(
            activation_failure=ActivationFailureKind.PERSISTENCE_REJECTED
        )
        lifecycle = transaction(harness)

        failed = lifecycle.activate_new_service()
        self.assertIs(failed.status, LifecycleStatus.ROLLBACK_REQUIRED)
        before = tuple(harness.events)
        with self.assertRaisesRegex(
            Exception, "^lifecycle_recovery_authorization_invalid$"
        ):
            lifecycle.rollback_and_recover_legacy(
                authorization=None, observed_at_epoch=NOW
            )
        self.assertEqual(tuple(harness.events), before)

        recovered = lifecycle.rollback_and_recover_legacy(
            authorization=recovery_authorization(),
            observed_at_epoch=NOW,
        )

        self.assertIs(
            recovered.status, LifecycleStatus.LEGACY_SERVICE_RECOVERED
        )
        self.assertEqual(
            harness.events[-8:],
            [
                "stop_new",
                "stopped",
                "preserved",
                "failed_container",
                "restored",
                "prerequisites",
                "start_legacy",
                "health_legacy",
            ],
        )
        self.assertEqual((harness.legacy_starts, harness.legacy_health), (1, 1))

    def test_provider_ambiguity_contains_only_exact_new_identity(self):
        harness = _LifecycleHarness(
            activation_failure=(
                ActivationFailureKind.PROVIDER_BOUNDARY_AMBIGUITY
            )
        )
        lifecycle = transaction(harness)

        result = lifecycle.activate_new_service()

        self.assertIs(result.status, LifecycleStatus.INCIDENT_STOP)
        self.assertEqual(result.containment_attempted, 1)
        self.assertEqual(result.contained, 1)
        self.assertEqual(harness.events.count("stop_new"), 1)
        with self.assertRaisesRegex(
            Exception, "^lifecycle_rollback_not_allowed$"
        ):
            lifecycle.rollback_and_recover_legacy(
                authorization=recovery_authorization(),
                observed_at_epoch=NOW,
            )

    def test_every_reverse_boundary_failure_incident_stops(self):
        for stage in (
            "stopped",
            "preserved",
            "failed_container",
            "restored",
            "prerequisites",
        ):
            with self.subTest(stage=stage):
                harness = _LifecycleHarness(
                    activation_failure=(
                        ActivationFailureKind.PERSISTENCE_REJECTED
                    )
                )
                lifecycle = transaction(harness, fail_stage=stage)
                lifecycle.activate_new_service()

                result = lifecycle.rollback_and_recover_legacy(
                    authorization=recovery_authorization(),
                    observed_at_epoch=NOW,
                )

                self.assertIs(result.status, LifecycleStatus.INCIDENT_STOP)
                self.assertEqual(harness.legacy_starts, 0)

    def test_legacy_failure_has_fixed_terminal_status_and_no_retry(self):
        harness = _LifecycleHarness(
            activation_failure=ActivationFailureKind.PERSISTENCE_REJECTED,
            legacy_failure=True,
        )
        lifecycle = transaction(harness)
        lifecycle.activate_new_service()

        result = lifecycle.rollback_and_recover_legacy(
            authorization=recovery_authorization(),
            observed_at_epoch=NOW,
        )

        self.assertIs(
            result.status,
            LifecycleStatus.INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED,
        )
        self.assertEqual((harness.legacy_starts, harness.legacy_health), (1, 0))
        with self.assertRaisesRegex(
            Exception, "^lifecycle_recovery_not_repeatable$"
        ):
            lifecycle.rollback_and_recover_legacy(
                authorization=recovery_authorization(),
                observed_at_epoch=NOW,
            )


if __name__ == "__main__":
    unittest.main()
