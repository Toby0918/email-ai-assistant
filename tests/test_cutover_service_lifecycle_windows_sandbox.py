"""Windows sandbox lifecycle composition for Issue #58."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import unittest

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.cutover_host_mutation.roles import AclRole
from backend.cutover_host_mutation.windows_security import WindowsSecurityApi
from backend.cutover_host_mutation.windows_filesystem_common import (
    authorization_fingerprint,
)
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
    CommittedRollbackPlanV1,
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


def _prepare_sandbox_lifecycle():
    scenario = build_synthetic_repository_scenario()
    review = _review_test_sandbox(scenario)
    original_root = directory_identity(scenario.source)
    original_physical = tuple(
        directory_identity(item.original) for item in scenario.worktrees
    )
    original_admin = tuple(
        item.admin_identity for item in review.observations
    )
    profile = profile_for_review(review)
    authorization = authorization_for(
        profile, review.operation_fingerprint
    )
    forward_authorization_fingerprint = authorization_fingerprint(
        authorization
    )
    scope = _bind_test_sandbox_transaction(
        review=review,
        profile=profile,
        authorization=authorization,
        observed_at_epoch=OBSERVED_AT,
    )
    publications = _publication_receipts(
        profile.profile_fingerprint,
        review.operation_fingerprint,
        profile.governing_master_commit,
        forward_authorization_fingerprint,
    )
    run_forward_synthetic_transaction(
        scope=scope,
        failure_selector=SyntheticFailureSelectorV1.none(),
        observed_at_epoch=OBSERVED_AT,
    )
    journal_head = _forward_journal_head(scenario)
    service = _SandboxService(
        scenario.root,
        profile.profile_fingerprint,
        publications.receipts[1].receipt_fingerprint,
    )
    legacy_database_before = _file_hash(service.legacy_database)
    legacy_runtime = scenario.root / "legacy-runtime.bin"
    legacy_runtime.write_bytes(b"issue58-synthetic-legacy-runtime")
    rollback_plan = _rollback_plan(
        scenario,
        journal_head,
        original_root,
        original_physical,
        original_admin,
        service.legacy_database,
        legacy_runtime,
    )
    controller = ProviderDisabledServiceController.create(
        operation_fingerprint=review.operation_fingerprint,
        profile_fingerprint=profile.profile_fingerprint,
        governing_master_commit=profile.governing_master_commit,
        publication_authorization_fingerprint=(
            forward_authorization_fingerprint
        ),
        adapters=service.adapters(),
    )
    lifecycle = ProviderDisabledLifecycleTransaction.create(
        operation_fingerprint=review.operation_fingerprint,
        profile_fingerprint=profile.profile_fingerprint,
        governing_master_commit=profile.governing_master_commit,
        publication_authorization_fingerprint=(
            forward_authorization_fingerprint
        ),
        journal_head_fingerprint=journal_head,
        publications=publications,
        controller=controller,
        rollback_adapter=_repository_rollback_adapter(
            scenario,
            scope,
            review,
            journal_head,
            original_root,
            original_physical,
            original_admin,
            service,
            rollback_plan,
            legacy_runtime,
        ),
        rollback_plan=rollback_plan,
    )
    return (
        scenario,
        review,
        original_root,
        original_physical,
        original_admin,
        profile,
        service,
        legacy_database_before,
        lifecycle,
    )


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class ServiceLifecycleWindowsSandboxTests(unittest.TestCase):
    def test_full_failed_activation_preserves_and_restores_exact_topology(
        self,
    ) -> None:
        (
            scenario,
            review,
            original_root,
            original_physical,
            original_admin,
            profile,
            service,
            legacy_database_before,
            lifecycle,
        ) = _prepare_sandbox_lifecycle()
        try:
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

    def test_preexisting_failed_container_collision_incident_stops(
        self,
    ) -> None:
        (
            scenario,
            review,
            _original_root,
            _original_physical,
            _original_admin,
            profile,
            service,
            _legacy_database_before,
            lifecycle,
        ) = _prepare_sandbox_lifecycle()
        try:
            failed = lifecycle.activate_new_service()
            self.assertIs(failed.status, LifecycleStatus.ROLLBACK_REQUIRED)
            scenario.failed_container.mkdir()
            stopped = lifecycle.rollback_and_recover_legacy(
                authorization=TestSandboxAuthorizationV1.create(
                    profile_fingerprint=profile.profile_fingerprint,
                    operation_fingerprint=review.operation_fingerprint,
                    phase="rollback",
                    expires_at_epoch=OBSERVED_AT + 600,
                ),
                observed_at_epoch=OBSERVED_AT,
            )
            self.assertIs(stopped.status, LifecycleStatus.INCIDENT_STOP)
            self.assertEqual(service.legacy_starts, 0)
        finally:
            scenario.close()


class _SandboxService:
    def __init__(self, root, profile, data_role):
        self.profile = profile
        self.data_role = data_role
        self.new_database = root / "issue58-new.sqlite3"
        self.legacy_database = root / "issue58-legacy.sqlite3"
        _create_database(self.new_database)
        _create_database(self.legacy_database)
        self.new_start = None
        self.legacy_starts = 0

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
            data_role_fingerprint=self.data_role,
            matching_rows=0,
        )

    def stop(self, start):
        return ServiceStopEvidenceV1.create_from_start(start)

    def start_legacy(self, request):
        self.legacy_starts += 1
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
    plan,
    legacy_runtime,
):
    def verify_stopped(stop):
        if stop != ServiceStopEvidenceV1.create_from_start(service.new_start):
            raise RuntimeError("synthetic stop mismatch")
        return RollbackStageEvidenceV1.create(
            stage=RollbackStage.NEW_SERVICE_STOPPED,
            journal_head_fingerprint=journal_head,
            observation_fingerprint="b" * 64,
            rollback_plan_fingerprint=plan.plan_fingerprint,
            previous_observation_fingerprint=(
                plan.committed_records_fingerprint
            ),
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
            rollback_plan_fingerprint=plan.plan_fingerprint,
            previous_observation_fingerprint="b" * 64,
            retained_external=3,
            retained_git_records=11,
        )

    def publish_failed(preserved):
        verify_failed_new_objects(scope, main_extracted=False)
        return FailedContainerPublicationReceiptV1.create(
            journal_head_fingerprint=journal_head,
            failed_container_fingerprint="d" * 64,
            rollback_plan_fingerprint=plan.plan_fingerprint,
            preservation_observation_fingerprint="c" * 64,
            retained_external=3,
            retained_git_records=11,
        )

    def restore(failed):
        for boundary, mutation_index in (
            (ReverseBoundary.MAIN_EXTRACTED, 19),
            (ReverseBoundary.ADMIN_RECORDS_RESTORED, 30),
            (ReverseBoundary.PHYSICAL_WORKTREES_RESTORED, 41),
            (ReverseBoundary.ORIGINAL_REPOSITORY_VERIFIED, 42),
        ):
            selector = SyntheticFailureSelectorV1.create(
                direction=SyntheticTransactionDirection.REVERSE,
                boundary=boundary,
                mutation_index=mutation_index,
                gap=SyntheticCrashGap.AFTER_COMMITTED,
            )
            with unittest.TestCase().assertRaises(
                RepositoryTransactionError
            ):
                run_reverse_synthetic_transaction(
                    scope=scope,
                    failure_selector=selector,
                    observed_at_epoch=OBSERVED_AT,
                )
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
            rollback_plan_fingerprint=plan.plan_fingerprint,
            reverse_receipt_fingerprint=receipt.receipt_fingerprint,
            original_topology_fingerprint=(
                _topology_fingerprint(
                    scenario, review
                )
            ),
            main_restored=1,
            git_records_restored=11,
            embedded_worktrees_restored=8,
            external_worktrees_restored=3,
        )

    def prerequisites(restored):
        security = WindowsSecurityApi()
        return LegacyPrerequisiteEvidenceV1.create(
            journal_head_fingerprint=journal_head,
            rollback_observation_fingerprint=(
                restored.observation_fingerprint
            ),
            rollback_plan_fingerprint=plan.plan_fingerprint,
            original_topology_fingerprint=(
                _topology_fingerprint(scenario, review)
            ),
            parent_descriptor_fingerprint=_acl_fingerprint(
                security, scenario.root, AclRole.PARENT
            ),
            finance_descriptor_fingerprint=_acl_fingerprint(
                security,
                scenario.root / "finance-synthetic",
                AclRole.FINANCE,
            ),
            original_database_fingerprint=_file_hash(
                service.legacy_database
            ),
            sidecar_state_fingerprint=_sidecar_fingerprint(
                service.legacy_database
            ),
            legacy_runtime_fingerprint=_file_hash(legacy_runtime),
            repository_identity_fingerprint=directory_identity(
                scenario.source
            ),
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


def _publication_receipts(profile, operation, master, authorization):
    types = (
        ManagedRuntimeReceiptV1,
        StoppedDatabaseCopyReceiptV1,
        CrxPublicationReceiptV1,
        ConfigPublicationReceiptV1,
    )
    receipts = tuple(
        kind.create(
            operation_fingerprint=operation,
            profile_fingerprint=profile,
            governing_master_commit=master,
            authorization_fingerprint=authorization,
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


def _rollback_plan(
    scenario,
    journal_head,
    original_root,
    original_physical,
    original_admin,
    legacy_database,
    legacy_runtime,
):
    security = WindowsSecurityApi()
    records = [
        item["record_hash"]
        for item in _journal_bodies(scenario)
        if item["event"].casefold() == "committed"
    ]
    return CommittedRollbackPlanV1.create(
        journal_head_fingerprint=journal_head,
        committed_records_fingerprint=_opaque_fingerprint(records),
        original_topology_fingerprint=_opaque_fingerprint(
            [original_root, *original_physical, *original_admin]
        ),
        parent_descriptor_fingerprint=_acl_fingerprint(
            security, scenario.root, AclRole.PARENT
        ),
        finance_descriptor_fingerprint=_acl_fingerprint(
            security,
            scenario.root / "finance-synthetic",
            AclRole.FINANCE,
        ),
        original_database_fingerprint=_file_hash(legacy_database),
        sidecar_state_fingerprint=_sidecar_fingerprint(legacy_database),
        legacy_runtime_fingerprint=_file_hash(legacy_runtime),
        repository_identity_fingerprint=original_root,
    )


def _journal_bodies(scenario):
    return [
        json.loads(path.read_text("ascii"))
        for path in sorted(scenario.journal_root.glob("*.json"))
    ]


def _topology_fingerprint(scenario, review):
    return _opaque_fingerprint(
        [
            directory_identity(scenario.source),
            *(
                directory_identity(item.original)
                for item in scenario.worktrees
            ),
            *(
                directory_identity(item.admin)
                for item in review.observations
            ),
        ]
    )


def _acl_fingerprint(security, path, role):
    return security.capture(path, role=role).observation.observation_fingerprint


def _sidecar_fingerprint(database):
    return _opaque_fingerprint(
        [
            (database.parent / f"{database.name}{suffix}").exists()
            for suffix in ("-wal", "-shm", "-journal")
        ]
    )


def _opaque_fingerprint(values):
    return hashlib.sha256(
        json.dumps(
            values,
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).hexdigest()


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
