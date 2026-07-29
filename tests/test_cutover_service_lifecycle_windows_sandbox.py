"""Windows sandbox lifecycle composition for Issue #58."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.cutover_managed_activation import (
    ConfigPublicationReceiptV1,
    CrxPublicationReceiptV1,
    ManagedActivationReceiptSetV1,
    ManagedRuntimeReceiptV1,
    StoppedDatabaseCopyReceiptV1,
)
from backend.cutover_repository_transaction import (
    ReverseBoundary,
    SyntheticCrashGap,
    SyntheticFailureSelectorV1,
    SyntheticTransactionDirection,
    run_forward_synthetic_transaction,
    run_reverse_synthetic_transaction,
)
from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)
from backend.cutover_repository_transaction.failed_evidence import (
    verify_failed_new_objects,
)
from backend.cutover_repository_transaction.git_inspection import (
    directory_identity,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.cutover_service_lifecycle import (
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
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
    ServiceStopEvidenceV1,
    SyntheticActivationEvidenceV1,
    SyntheticRowEvidenceV1,
)
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    build_synthetic_repository_scenario,
    profile_for_review,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class ServiceLifecycleWindowsSandboxTests(unittest.TestCase):
    def test_full_failed_activation_preserves_and_restores_exact_topology(
        self,
    ) -> None:
        scenario = build_synthetic_repository_scenario()
        try:
            review = _review_test_sandbox(scenario)
            original_root = directory_identity(scenario.source)
            original_physical = tuple(
                directory_identity(item.original)
                for item in scenario.worktrees
            )
            original_admin = tuple(
                item.admin_identity for item in review.observations
            )
            profile = profile_for_review(review)
            authorization = authorization_for(
                profile, review.operation_fingerprint
            )
            scope = _bind_test_sandbox_transaction(
                review=review,
                profile=profile,
                authorization=authorization,
                observed_at_epoch=OBSERVED_AT,
            )
            run_forward_synthetic_transaction(
                scope=scope,
                failure_selector=SyntheticFailureSelectorV1.none(),
                observed_at_epoch=OBSERVED_AT,
            )
            journal_head = _forward_journal_head(scenario)
            service = _SandboxService(
                scenario.root, profile.profile_fingerprint
            )
            legacy_database_before = _file_hash(service.legacy_database)
            lifecycle = ProviderDisabledLifecycleTransaction.create(
                operation_fingerprint=review.operation_fingerprint,
                profile_fingerprint=profile.profile_fingerprint,
                journal_head_fingerprint=journal_head,
                publications=_publication_receipts(
                    profile.profile_fingerprint
                ),
                controller=ProviderDisabledServiceController.create(
                    profile_fingerprint=profile.profile_fingerprint,
                    adapters=service.adapters(),
                ),
                rollback_adapter=_repository_rollback_adapter(
                    scenario,
                    scope,
                    review,
                    journal_head,
                    original_root,
                    original_physical,
                    original_admin,
                    service,
                ),
            )

            failed = lifecycle.activate_new_service()
            self.assertIs(failed.status, LifecycleStatus.ROLLBACK_REQUIRED)
            recovered = lifecycle.rollback_and_recover_legacy(
                authorization=TestSandboxAuthorizationV1.create(
                    profile_fingerprint=profile.profile_fingerprint,
                    operation_fingerprint=review.operation_fingerprint,
                    phase="rollback",
                    expires_at_epoch=OBSERVED_AT + 600,
                ),
                observed_at_epoch=OBSERVED_AT,
            )

            self.assertIs(
                recovered.status, LifecycleStatus.LEGACY_SERVICE_RECOVERED
            )
            self.assertEqual(recovered.restored_worktrees, 11)
            self.assertEqual(recovered.retained_external_worktrees, 3)
            self.assertEqual(recovered.retained_git_records, 11)
            self.assertEqual(
                recovered.failed_container_classification,
                "FAILED_CONTAINER_PRESERVED_WITH_LEGACY_MAIN_EXTRACTED",
            )
            self.assertEqual(_row_count(service.new_database), 1)
            self.assertEqual(_row_count(service.legacy_database), 0)
            self.assertEqual(
                _file_hash(service.legacy_database),
                legacy_database_before,
            )
            self.assertEqual(
                directory_identity(scenario.source), original_root
            )
            self.assertEqual(
                tuple(
                    directory_identity(item.original)
                    for item in scenario.worktrees
                ),
                original_physical,
            )
            self.assertEqual(
                tuple(
                    directory_identity(item.admin)
                    for item in review.observations
                ),
                original_admin,
            )
            self.assertTrue(scenario.failed_container.is_dir())
        finally:
            scenario.close()


class _SandboxService:
    def __init__(self, root, profile):
        self.profile = profile
        self.new_database = root / "issue58-new.sqlite3"
        self.legacy_database = root / "issue58-legacy.sqlite3"
        _create_database(self.new_database)
        _create_database(self.legacy_database)
        self.new_start = None

    def adapters(self):
        return ProviderDisabledServiceAdapters(
            new_service=NewServiceAdapter(
                start_provider_disabled=self.start_new,
                read_health=lambda start: (
                    ServiceHealthEvidenceV1.create_from_start(start)
                ),
                analyze_fixed_synthetic=self.analyze,
                observe_synthetic_row=self.observe_row_as_failure,
                stop_exact=self.stop,
            ),
            legacy_service=LegacyServiceAdapter(
                start_provider_disabled_recovery=self.start_legacy,
                read_health=lambda start: (
                    ServiceHealthEvidenceV1.create_from_start(start)
                ),
                stop_exact=self.stop,
            ),
        )

    def start_new(self, request):
        self.new_start = _start(ServiceRole.NEW, 5100, request)
        return self.new_start

    def analyze(self, request):
        with sqlite3.connect(self.new_database) as connection:
            connection.execute(
                "INSERT INTO activation_evidence "
                "(request_fingerprint) VALUES (?)",
                (request.request_fingerprint,),
            )
        return SyntheticActivationEvidenceV1.create(
            request_fingerprint=request.request_fingerprint,
            route="deterministic_rules",
            provider_attempts=0,
            result_fingerprint="a" * 64,
        )

    def observe_row_as_failure(self, request):
        return SyntheticRowEvidenceV1.create(
            request_fingerprint=request.request_fingerprint,
            data_role_fingerprint=_publication_receipts(
                self.profile
            ).receipts[1].receipt_fingerprint,
            matching_rows=0,
        )

    def stop(self, start):
        return ServiceStopEvidenceV1.create_from_start(start)

    def start_legacy(self, request):
        return _start(ServiceRole.LEGACY, 5200, request)


def _start(role, pid, request):
    return ServiceStartEvidenceV1.create(
        role=role,
        pid=pid,
        start_time_ns=1_900_000_000_000_000_000 + pid,
        executable_fingerprint=request.runtime_fingerprint,
        port=request.port,
        port_owner_pid=pid,
        profile_fingerprint=request.profile_fingerprint,
        runtime_fingerprint=request.runtime_fingerprint,
        config_fingerprint=request.config_fingerprint,
        data_role_fingerprint=request.data_role_fingerprint,
        nonce=request.nonce,
        primary_provider="disabled",
        fallback_provider="disabled",
    )


def _repository_rollback_adapter(
    scenario,
    scope,
    review,
    journal_head,
    original_root,
    original_physical,
    original_admin,
    service,
):
    def verify_stopped(stop):
        if stop != ServiceStopEvidenceV1.create_from_start(service.new_start):
            raise RuntimeError("synthetic stop mismatch")
        return RollbackStageEvidenceV1.create(
            stage=RollbackStage.NEW_SERVICE_STOPPED,
            journal_head_fingerprint=journal_head,
            observation_fingerprint="b" * 64,
            retained_external=0,
            retained_git_records=0,
        )

    def preserve():
        selector = SyntheticFailureSelectorV1.create(
            direction=SyntheticTransactionDirection.REVERSE,
            boundary=ReverseBoundary.NEW_STATE_PRESERVED,
            mutation_index=18,
            gap=SyntheticCrashGap.AFTER_COMMITTED,
        )
        with unittest.TestCase().assertRaises(RepositoryTransactionError):
            run_reverse_synthetic_transaction(
                scope=scope,
                failure_selector=selector,
                observed_at_epoch=OBSERVED_AT,
            )
        return RollbackStageEvidenceV1.create(
            stage=RollbackStage.NEW_EVIDENCE_PRESERVED,
            journal_head_fingerprint=journal_head,
            observation_fingerprint="c" * 64,
            retained_external=3,
            retained_git_records=11,
        )

    def publish_failed(preserved):
        verify_failed_new_objects(scope, main_extracted=False)
        return FailedContainerPublicationReceiptV1.create(
            journal_head_fingerprint=journal_head,
            failed_container_fingerprint="d" * 64,
            retained_external=3,
            retained_git_records=11,
        )

    def restore(failed):
        receipt = run_reverse_synthetic_transaction(
            scope=scope,
            failure_selector=SyntheticFailureSelectorV1.none(),
            observed_at_epoch=OBSERVED_AT,
        )
        if (
            receipt.worktree_count != 11
            or directory_identity(scenario.source) != original_root
            or tuple(
                directory_identity(item.original)
                for item in scenario.worktrees
            )
            != original_physical
            or tuple(
                directory_identity(item.admin)
                for item in review.observations
            )
            != original_admin
        ):
            raise RuntimeError("synthetic topology mismatch")
        return RollbackRestoreEvidenceV1.create(
            journal_head_fingerprint=journal_head,
            failed_container_receipt_fingerprint=(
                failed.receipt_fingerprint
            ),
            main_restored=1,
            git_records_restored=11,
            embedded_worktrees_restored=8,
            external_worktrees_restored=3,
        )

    def prerequisites(restored):
        return LegacyPrerequisiteEvidenceV1.create(
            journal_head_fingerprint=journal_head,
            rollback_observation_fingerprint=(
                restored.observation_fingerprint
            ),
            parent_descriptor_fingerprint="e" * 64,
            finance_descriptor_fingerprint="f" * 64,
            original_database_fingerprint="0" * 64,
            sidecar_state_fingerprint="1" * 64,
            legacy_runtime_fingerprint="2" * 64,
            repository_identity_fingerprint="3" * 64,
            git_records_verified=11,
            worktrees_verified=11,
        )

    return JournalDrivenRollbackAdapter(
        verify_new_service_stopped=verify_stopped,
        preserve_new_evidence=preserve,
        publish_failed_container=publish_failed,
        restore_original_topology=restore,
        verify_legacy_prerequisites=prerequisites,
    )


def _publication_receipts(profile):
    types = (
        ManagedRuntimeReceiptV1,
        StoppedDatabaseCopyReceiptV1,
        CrxPublicationReceiptV1,
        ConfigPublicationReceiptV1,
    )
    receipts = tuple(
        kind.create(
            operation_fingerprint="4" * 64,
            profile_fingerprint=profile,
            governing_master_commit="5" * 40,
            authorization_fingerprint="6" * 64,
            input_fingerprints=(str(index) * 64,),
            observation_fingerprint=str(index + 4) * 64,
            counts={"published": 1, "rejected": 0},
        )
        for index, kind in enumerate(types, start=1)
    )
    return ManagedActivationReceiptSetV1.create(receipts=receipts)


def _forward_journal_head(scenario):
    bodies = [
        json.loads(path.read_text("ascii"))
        for path in sorted(scenario.journal_root.glob("*.json"))
    ]
    return bodies[-1]["record_hash"]


def _create_database(path):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE activation_evidence "
            "(id INTEGER PRIMARY KEY, request_fingerprint TEXT NOT NULL)"
        )


def _row_count(path):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM activation_evidence"
        ).fetchone()[0]


def _file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
