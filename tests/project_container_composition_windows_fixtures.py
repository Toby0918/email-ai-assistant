"""Test-owned Windows adapters for the complete Issue #59 composition."""

from __future__ import annotations

import hashlib
import sqlite3
import tempfile
from pathlib import Path

from backend.cutover_composition_contracts import (
    CompositionStage,
    CompositionStageReceiptV1,
    ProjectContainerReceiptChainV1,
    UNBOUND_FINGERPRINT,
)
from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.cutover_host_mutation import AclRole
from backend.cutover_host_mutation.windows_filesystem_common import (
    authorization_fingerprint,
)
from backend.cutover_journal import DurabilityPlatform
from backend.cutover_managed_activation import (
    ArtifactPublicationAdapter,
    ArtifactPublisher,
    ConfigPublicationAdapter,
    ConfigPublisher,
    DatabasePublicationAdapter,
    LockedRuntimeBuilder,
    ManagedActivationAdapters,
    ManagedActivationPhase,
    ManagedConfigV1,
    RuntimePublicationAdapter,
    StoppedDatabaseCopier,
    StoppedServiceReceiptV1,
)
from backend.cutover_managed_activation.synthetic_scope import (
    _bind_test_sandbox_activation,
    _review_test_sandbox_activation,
)
from backend.cutover_service_lifecycle import LifecycleStatus
from backend.cutover_service_lifecycle import (
    ProviderDisabledLifecycleTransaction,
    ProviderDisabledServiceController,
)
from backend.cutover_repository_transaction import (
    SyntheticFailureSelectorV1,
    run_forward_synthetic_transaction,
)
from backend.cutover_repository_transaction.git_inspection import (
    directory_identity,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.migration_evidence_publication import (
    require_matching_migration_evidence_receipts,
    verify_published_migration_evidence,
)
from backend.real_host_preflight import PreMutationGate
from tests.cutover_composition_fixtures import JOURNAL_OWNER, OBSERVED_AT
from tests.cutover_host_mutation_fixtures import durable_intent
from tests.cutover_managed_activation_fixtures import (
    build_runtime_scenario,
    authorization_for as activation_authorization,
    profile_for_review as activation_profile,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.cutover_repository_transaction_fixtures import (
    authorization_for as repository_authorization,
    build_synthetic_repository_scenario,
    profile_for_review as repository_profile,
)
from tests.migration_evidence_publication_fixtures import (
    OBSERVED_AT as EVIDENCE_OBSERVED_AT,
    OPERATION_FINGERPRINT as EVIDENCE_OPERATION,
    PublicationReviewFixture,
)
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT as PREFLIGHT_OBSERVED_AT,
    sandbox_authorization,
)
from tests.test_cutover_host_mutation_windows_acl import (
    _bundle,
    _create_guarded_container,
)
from tests.test_cutover_managed_activation_contracts import MASTER
from tests.test_cutover_service_lifecycle_windows_sandbox import (
    _SandboxService,
    _forward_journal_head,
    _repository_rollback_adapter,
    _rollback_plan,
)
from tests.test_migration_evidence_publication_create_verify import (
    _authorization as evidence_authorization,
    _publish as publish_evidence,
    _review as review_evidence,
)
from tests.test_real_host_preflight_windows_composition import (
    _SandboxLayout,
    _run_preflight,
)
from backend.cutover_contracts import RealPreflightAuthorizationV1


_JOURNAL_STAGES = {
    item
    for item in CompositionStage
    if item
    not in {
        CompositionStage.CURRENT_TOPOLOGY,
        CompositionStage.HOST_BASELINE,
        CompositionStage.EVIDENCE_REVIEW,
        CompositionStage.EVIDENCE_PUBLICATION,
        CompositionStage.EVIDENCE_VERIFICATION,
        CompositionStage.FINAL_AUDIT_READINESS,
        CompositionStage.ACL_BASELINE,
        CompositionStage.PRE_MUTATION_GATE,
    }
}


class WindowsCompositionFixture:
    """One owner for every synthetic host capability used by the E2E test."""

    def __init__(self, binding, scope) -> None:
        self.binding = binding
        self.scope = scope
        self.owner = tempfile.TemporaryDirectory(
            prefix="issue59-windows-composition-"
        )
        self.scope.own_temporary_directory(self.owner)
        self.root = Path(self.owner.name)
        self.layout = _SandboxLayout.create(self.root / "preflight")
        self.evidence = PublicationReviewFixture()
        self.scope.own_temporary_directory(self.evidence.temporary)
        self.managed = None
        self.repository_scenario = None
        self.repository_review = None
        self.repository_scope = None
        self.repository_profile = None
        self.repository_original_root = None
        self.repository_original_physical = None
        self.repository_original_admin = None
        self.repository_journal_head = None
        self.managed_review = None
        self.managed_profile = None
        self.managed_authorization_fingerprint = None
        self.lifecycle = None
        self.service = None
        self.rollback_plan = None
        self.legacy_runtime = None
        self.consumed_publication_fingerprint = None
        self.acl_stores = []
        self.topology = None
        self.selection = None
        self.review = None
        self.created = None
        self.verified = None
        self.receipt_set = None
        self.failed = None
        self.recovered = None
        self.stage_receipts = {}

    def close(self) -> None:
        for store in reversed(self.acl_stores):
            store.close()
        if self.repository_scenario is not None:
            self.repository_scenario.close()
        if self.managed is not None:
            self.managed.close()
        self.evidence.close()
        self.owner.cleanup()

    def current_topology(self, prior):
        self.topology = _run_preflight(
            self.layout.callbacks(),
            self.layout.profile,
        )
        return self.emit(
            CompositionStage.CURRENT_TOPOLOGY,
            prior,
            self.topology,
        )

    def host_baseline(self, prior):
        parent = self.layout.observer.observe_volume(self.layout.parent)
        return self.emit(CompositionStage.HOST_BASELINE, prior, parent)

    def evidence_review(self, prior):
        self.selection, self.review = review_evidence(self.evidence)
        return self.emit(CompositionStage.EVIDENCE_REVIEW, prior, self.review)

    def evidence_publication(self, prior):
        self.created = publish_evidence(
            self.evidence,
            self.selection,
            self.review,
        )
        return self.emit(
            CompositionStage.EVIDENCE_PUBLICATION,
            prior,
            self.created,
        )

    def evidence_verification(self, prior):
        self.verified = verify_published_migration_evidence(
            profile=self.evidence.profile,
            authorization=evidence_authorization(
                self.evidence,
                RealPreflightAuthorizationV1,
                phase="evidence_verification",
            ),
            operation_fingerprint=EVIDENCE_OPERATION,
            observed_at_epoch=EVIDENCE_OBSERVED_AT,
            created_receipt=self.created,
        )
        require_matching_migration_evidence_receipts(
            review_receipt=self.review,
            created_receipt=self.created,
            verified_receipt=self.verified,
        )
        return self.emit(
            CompositionStage.EVIDENCE_VERIFICATION,
            prior,
            self.verified,
        )

    def final_audit_readiness(self, prior):
        gate = self._fresh_real_pre_mutation_gate()
        return self.emit(
            CompositionStage.FINAL_AUDIT_READINESS,
            prior,
            gate,
        )

    def failed_activation_chain(
        self,
        preflight_chain: ProjectContainerReceiptChainV1,
    ) -> ProjectContainerReceiptChainV1:
        stages = (
            CompositionStage.ACL_BASELINE,
            CompositionStage.PRE_MUTATION_GATE,
            CompositionStage.ACL_PUBLICATION,
            CompositionStage.REPOSITORY_TRANSACTION,
            CompositionStage.RUNTIME_PUBLICATION,
            CompositionStage.DATABASE_PUBLICATION,
            CompositionStage.ARTIFACT_PUBLICATION,
            CompositionStage.CONFIG_PUBLICATION,
            CompositionStage.ACTIVATION,
        )
        receipts = (
            *preflight_chain.receipts,
            *(self.stage_receipts[stage] for stage in stages),
        )
        return ProjectContainerReceiptChainV1.create(
            receipts=receipts,
            observed_at_epoch=OBSERVED_AT,
        )

    def acl_baseline(self, prior):
        acl_root = self.root / "acl"
        acl_root.mkdir()
        self.acl = _bundle(acl_root)
        parent = self.acl.adapter.capture(AclRole.PARENT)
        finance = self.acl.adapter.capture(AclRole.FINANCE)
        return self.emit(
            CompositionStage.ACL_BASELINE,
            prior,
            (parent, finance),
        )

    def pre_mutation_gate(self, prior):
        gate = self._fresh_real_pre_mutation_gate()
        return self.emit(
            CompositionStage.PRE_MUTATION_GATE,
            prior,
            gate,
            valid_until_epoch=OBSERVED_AT + 60,
        )

    def acl_publication(self, prior):
        created, create_store = _create_guarded_container(self.acl)
        intent, permit, apply_store = durable_intent(
            before_fingerprint=created.observation_fingerprint,
            expected_after_fingerprint=self.acl.policy.policy_fingerprint,
            platform=DurabilityPlatform.WINDOWS,
        )
        self.acl_applied = self.acl.adapter.apply_new_container_policy(
            created_container=created,
            intent=intent,
            durable_permit=permit,
        )
        self.acl_stores.extend((create_store, apply_store))
        return self.emit(
            CompositionStage.ACL_PUBLICATION,
            prior,
            self.acl_applied,
        )

    def repository_transaction(self, prior):
        scenario = build_synthetic_repository_scenario()
        self.scope.own_temporary_directory(scenario.owner)
        review = _review_test_sandbox(scenario)
        self.repository_scenario = scenario
        self.repository_review = review
        self.repository_original_root = directory_identity(scenario.source)
        self.repository_original_physical = tuple(
            directory_identity(item.original)
            for item in scenario.worktrees
        )
        self.repository_original_admin = tuple(
            item.admin_identity for item in review.observations
        )
        profile = repository_profile(
            review,
            acl_policy_fingerprint=self.acl_applied.policy_fingerprint,
        )
        if (
            profile.to_mapping()["acl_policy"]["policy_fingerprint"]
            != self.acl.policy.policy_fingerprint
        ):
            raise RuntimeError("synthetic ACL-to-repository binding drift")
        authorization = repository_authorization(
            profile,
            review.operation_fingerprint,
        )
        self.repository_profile = profile
        self.repository_scope = _bind_test_sandbox_transaction(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )
        forward = run_forward_synthetic_transaction(
            scope=self.repository_scope,
            failure_selector=SyntheticFailureSelectorV1.none(),
            observed_at_epoch=OBSERVED_AT,
        )
        self.repository_journal_head = _forward_journal_head(scenario)
        observation = (
            self.acl_applied.receipt_fingerprint,
            forward.receipt_fingerprint,
            review.operation_fingerprint,
            scenario.source.is_dir(),
            tuple(item.target.is_dir() for item in scenario.worktrees),
        )
        return self.emit(
            CompositionStage.REPOSITORY_TRANSACTION,
            prior,
            observation,
        )

    def runtime_publication(self, prior):
        self.receipt_set = self._publish_managed_phase()
        return self.emit(
            CompositionStage.RUNTIME_PUBLICATION,
            prior,
            self.receipt_set.receipts[0],
        )

    def database_publication(self, prior):
        if not self.managed.database_target.is_file():
            raise RuntimeError("synthetic database publication missing")
        return self.emit(
            CompositionStage.DATABASE_PUBLICATION,
            prior,
            self.receipt_set.receipts[1],
        )

    def artifact_publication(self, prior):
        if not self.managed.crx_target.is_file():
            raise RuntimeError("synthetic artifact publication missing")
        return self.emit(
            CompositionStage.ARTIFACT_PUBLICATION,
            prior,
            self.receipt_set.receipts[2],
        )

    def config_publication(self, prior):
        if not self.managed.config_target.is_file():
            raise RuntimeError("synthetic config publication missing")
        return self.emit(
            CompositionStage.CONFIG_PUBLICATION,
            prior,
            self.receipt_set.receipts[3],
        )

    def activation(self, prior):
        self._assemble_lifecycle()
        self.failed = self.lifecycle.activate_new_service()
        if self.failed.status is not LifecycleStatus.ROLLBACK_REQUIRED:
            raise RuntimeError("synthetic activation did not require rollback")
        return self.emit(CompositionStage.ACTIVATION, prior, self.failed)

    def final_audit(self, _prior):
        if self.failed.status is LifecycleStatus.ROLLBACK_REQUIRED:
            raise RuntimeError("synthetic final audit rejected activation")
        raise RuntimeError("synthetic activation result missing")

    def cutover_success(self, _prior):
        raise RuntimeError("synthetic failed activation cannot succeed")

    def recovery_inspection(self, prior):
        if self.failed.status is not LifecycleStatus.ROLLBACK_REQUIRED:
            raise RuntimeError("synthetic recovery inspection mismatch")
        return self.emit(
            CompositionStage.RECOVERY_INSPECTION,
            prior,
            self.failed,
        )

    def failed_container_preservation(self, prior):
        self.recovered = self.lifecycle.rollback_and_recover_legacy(
            authorization=TestSandboxAuthorizationV1.create(
                profile_fingerprint=self.managed_profile.profile_fingerprint,
                operation_fingerprint=(
                    self.managed_review.operation_fingerprint
                ),
                phase="rollback",
                expires_at_epoch=OBSERVED_AT + 600,
            ),
            observed_at_epoch=OBSERVED_AT,
        )
        if not self.repository_scenario.failed_container.is_dir():
            raise RuntimeError("synthetic failed container missing")
        return self.emit(
            CompositionStage.FAILED_CONTAINER_PRESERVATION,
            prior,
            self.recovered,
        )

    def rollback_restoration(self, prior):
        if self.recovered.restored_worktrees != 11:
            raise RuntimeError("synthetic worktree restoration mismatch")
        return self.emit(
            CompositionStage.ROLLBACK_RESTORATION,
            prior,
            self.recovered,
        )

    def legacy_health(self, prior):
        if (
            self.recovered.status
            is not LifecycleStatus.LEGACY_SERVICE_RECOVERED
            or self.service.legacy_starts != 1
        ):
            raise RuntimeError("synthetic legacy health mismatch")
        return self.emit(
            CompositionStage.LEGACY_HEALTH,
            prior,
            self.recovered,
        )

    def emit(self, stage, prior, component, *, valid_until_epoch=0):
        prior_fingerprint = (
            prior.receipt_fingerprint
            if type(prior) is CompositionStageReceiptV1
            else UNBOUND_FINGERPRINT
        )
        observation = _component_fingerprint(stage.value, component)
        journal_bound = stage in _JOURNAL_STAGES
        head = (
            _component_fingerprint(
                "journal",
                (prior_fingerprint, stage.value, observation),
            )
            if journal_bound
            else UNBOUND_FINGERPRINT
        )
        receipt = CompositionStageReceiptV1.create(
            binding=self.binding,
            stage=stage,
            prior_receipt_fingerprint=prior_fingerprint,
            observation_fingerprint=observation,
            journal_owner_fingerprint=(
                JOURNAL_OWNER if journal_bound else UNBOUND_FINGERPRINT
            ),
            prior_journal_head_fingerprint=(
                prior.journal_head_fingerprint
                if journal_bound
                and type(prior) is CompositionStageReceiptV1
                and prior.journal_owner_fingerprint
                != UNBOUND_FINGERPRINT
                else UNBOUND_FINGERPRINT
            ),
            journal_head_fingerprint=head,
            valid_until_epoch=valid_until_epoch,
            accepted=1,
            rejected=0,
            worktrees=(
                11
                if stage
                in {
                    CompositionStage.REPOSITORY_TRANSACTION,
                    CompositionStage.ROLLBACK_RESTORATION,
                    CompositionStage.LEGACY_HEALTH,
                }
                else 0
            ),
            provider_attempts=0,
        )
        self.stage_receipts[stage] = receipt
        return receipt

    def _fresh_real_pre_mutation_gate(self):
        topology = _run_preflight(
            self.layout.callbacks(),
            self.layout.profile,
        )
        operation = opaque_fingerprint(201)
        gate = PreMutationGate.bind(
            current_topology_receipt=topology,
            callbacks=self.layout.callbacks(),
            policy_fingerprint=opaque_fingerprint(407),
        )
        return gate.evaluate(
            profile=self.layout.profile,
            authorization=sandbox_authorization(
                self.layout.profile,
                operation_fingerprint=operation,
            ),
            operation_fingerprint=operation,
            nonce="123e4567-e89b-42d3-a456-426614174000",
            observed_at_epoch=PREFLIGHT_OBSERVED_AT + 1,
        )

    def _publish_managed_phase(self):
        self.managed = build_runtime_scenario()
        self.scope.own_temporary_directory(self.managed.owner)
        connection = sqlite3.connect(self.managed.database_source)
        try:
            connection.execute(
                "CREATE TABLE activation_evidence "
                "(id INTEGER PRIMARY KEY, "
                "request_fingerprint TEXT NOT NULL)"
            )
            connection.commit()
        finally:
            connection.close()
        review = _review_test_sandbox_activation(self.managed)
        profile = activation_profile(review)
        authorization = activation_authorization(
            profile,
            review.operation_fingerprint,
        )
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )
        self.managed_review = review
        self.managed_profile = profile
        self.managed_authorization_fingerprint = (
            scope.authorization_fingerprint
        )
        stopped = StoppedServiceReceiptV1.create(
            operation_fingerprint=review.operation_fingerprint,
            profile_fingerprint=profile.profile_fingerprint,
            governing_master_commit=MASTER,
            authorization_fingerprint=scope.authorization_fingerprint,
            service_role_fingerprint=review.stopped_service_role_fingerprint,
            database_source_fingerprint=review.database_source_fingerprint,
            observation_fingerprint="7" * 64,
        )
        config = ManagedConfigV1.from_mapping(self.managed.config_values)
        adapters = ManagedActivationAdapters(
            runtime=RuntimePublicationAdapter(
                lambda: LockedRuntimeBuilder.publish(scope=scope)
            ),
            database=DatabasePublicationAdapter(
                lambda: StoppedDatabaseCopier.copy(
                    scope=scope,
                    stopped_service_receipt=stopped,
                )
            ),
            artifact=ArtifactPublicationAdapter(
                lambda: ArtifactPublisher.publish(scope=scope)
            ),
            config=ConfigPublicationAdapter(
                lambda: ConfigPublisher.publish(scope=scope, config=config)
            ),
        )
        return ManagedActivationPhase.create(
            operation_fingerprint=review.operation_fingerprint,
            profile_fingerprint=profile.profile_fingerprint,
            governing_master_commit=MASTER,
            authorization_fingerprint=scope.authorization_fingerprint,
        ).publish(adapters)

    def _assemble_lifecycle(self):
        data_receipt = self.receipt_set.receipts[1]
        self.service = _SandboxService(
            self.repository_scenario.root,
            self.managed_profile.profile_fingerprint,
            data_receipt.receipt_fingerprint,
        )
        self.service.new_database = self.managed.database_target
        self.legacy_runtime = (
            self.repository_scenario.root / "legacy-runtime.bin"
        )
        self.legacy_runtime.write_bytes(
            b"issue59-synthetic-legacy-runtime"
        )
        self.rollback_plan = _rollback_plan(
            self.repository_scenario,
            self.repository_journal_head,
            self.repository_original_root,
            self.repository_original_physical,
            self.repository_original_admin,
            self.service.legacy_database,
            self.legacy_runtime,
        )
        controller = ProviderDisabledServiceController.create(
            operation_fingerprint=(
                self.managed_review.operation_fingerprint
            ),
            profile_fingerprint=self.managed_profile.profile_fingerprint,
            governing_master_commit=(
                self.managed_profile.governing_master_commit
            ),
            publication_authorization_fingerprint=(
                self.managed_authorization_fingerprint
            ),
            adapters=self.service.adapters(),
        )
        self.lifecycle = ProviderDisabledLifecycleTransaction.create(
            operation_fingerprint=(
                self.managed_review.operation_fingerprint
            ),
            profile_fingerprint=self.managed_profile.profile_fingerprint,
            governing_master_commit=(
                self.managed_profile.governing_master_commit
            ),
            publication_authorization_fingerprint=(
                self.managed_authorization_fingerprint
            ),
            journal_head_fingerprint=self.repository_journal_head,
            publications=self.receipt_set,
            controller=controller,
            rollback_adapter=_repository_rollback_adapter(
                self.repository_scenario,
                self.repository_scope,
                self.repository_review,
                self.repository_journal_head,
                self.repository_original_root,
                self.repository_original_physical,
                self.repository_original_admin,
                self.service,
                self.rollback_plan,
                self.legacy_runtime,
            ),
            rollback_plan=self.rollback_plan,
        )
        self.consumed_publication_fingerprint = (
            self.receipt_set.receipt_set_fingerprint
        )


def _component_fingerprint(label: str, value: object) -> str:
    fingerprints = []
    for item in value if type(value) is tuple else (value,):
        for name in (
            "receipt_fingerprint",
            "review_fingerprint",
            "receipt_set_fingerprint",
            "observation_fingerprint",
            "operation_fingerprint",
            "volume_fingerprint",
        ):
            candidate = getattr(item, name, None)
            if (
                type(candidate) is str
                and len(candidate) == 64
                and all(character in "0123456789abcdef" for character in candidate)
            ):
                fingerprints.append(candidate)
                break
        else:
            fingerprints.append(
                hashlib.sha256(
                    f"{type(item).__name__}:{item!r}".encode("utf-8")
                ).hexdigest()
            )
    payload = ":".join((label, *fingerprints)).encode("ascii")
    return hashlib.sha256(payload).hexdigest()
