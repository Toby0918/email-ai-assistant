"""Synthetic provider-disabled validation slice for Issue #81."""

from __future__ import annotations

from types import SimpleNamespace

from backend.cutover_service_lifecycle import (
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
    ServiceStopEvidenceV1,
)
from backend.r2_config_publication.contracts import (
    ConfigPendingState,
    ConfigPublicationStatus,
    ManagedConfigSelectionV1,
    build_receipt as config_receipt,
)
from backend.r2_crx_publication.contracts import (
    CrxPendingState,
    CrxPublicationStatus,
    build_receipt as crx_receipt,
)
from backend.r2_database_publication import (
    DatabaseTransactionResultV1,
    DatabaseTransactionStatus,
)
from backend.r2_evidence_process.contracts import (
    EvidenceProcessStatus,
    result as evidence_result,
)
from backend.r2_repository_manifest.contracts import build_receipt as repository_receipt
from backend.r2_runtime_publication.contracts import (
    RuntimePendingClassification,
    RuntimePublicationStatus,
    build_receipt as runtime_receipt,
)
from backend.r2_validation_lifecycle import (
    ApprovedValidationSliceV1,
    FinalDatabaseProofV1,
    OperatorPublicConfirmationV1,
    PersistedPublicRowEvidenceV1,
    PublicRuleFallbackResultV1,
    ValidationAdaptersV1,
)
from backend.r2_cross_stage_recovery import (
    INITIAL_JOURNAL_HEAD_FINGERPRINT,
    INITIAL_RECEIPT_FINGERPRINT,
    ReceiptPredecessorLinkV1,
)
from backend.r2_independent_audits.testing import issue_verified_test_receipt
from tests.cutover_contract_fixtures import opaque_fingerprint


NOW = 1_900_000_000
OPERATION = opaque_fingerprint(8100)
PROFILE = opaque_fingerprint(8101)
AUTHORIZATION = opaque_fingerprint(8102)
PUBLICATION_MATERIAL = opaque_fingerprint(8103)
_PUBLICATION_LINK = ReceiptPredecessorLinkV1.create(
    record_type="PUBLICATION_RECEIPT",
    material_fingerprint=PUBLICATION_MATERIAL,
    predecessor_fingerprint=INITIAL_RECEIPT_FINGERPRINT,
    prior_head_fingerprint=INITIAL_JOURNAL_HEAD_FINGERPRINT,
)
HEAD = _PUBLICATION_LINK.journal_head_fingerprint
IDENTITIES = opaque_fingerprint(8104)
EVIDENCE = opaque_fingerprint(8105)
DATABASE_ROLE = opaque_fingerprint(8106)


def approved_slice() -> ApprovedValidationSliceV1:
    runtime = runtime_receipt(
        status=RuntimePublicationStatus.PUBLISHED,
        dependency_count=12,
        retained=0,
        tree=opaque_fingerprint(8110),
        verification=opaque_fingerprint(8111),
        classification=RuntimePendingClassification.PUBLISHED_EXACT,
    )
    crx = crx_receipt(
        status=CrxPublicationStatus.PUBLISHED,
        state=CrxPendingState.EFFECT_PRESENT_EXACT,
        review=SimpleNamespace(
            format_version=3,
            size_bytes=128,
            source_identity_fingerprint=opaque_fingerprint(8112),
            artifact_hash=opaque_fingerprint(8113),
        ),
        target_identity=opaque_fingerprint(8114),
        retained=0,
    )
    selection = ManagedConfigSelectionV1.create(
        {
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": ["example.test"],
            "EMAIL_AGENT_LOG_LEVEL": "WARNING",
        }
    )
    config = config_receipt(
        status=ConfigPublicationStatus.PUBLISHED,
        state=ConfigPendingState.EFFECT_PRESENT_EXACT,
        selection=selection,
        document=opaque_fingerprint(8115),
        target=opaque_fingerprint(8116),
        retained=0,
    )
    database = DatabaseTransactionResultV1(
        DatabaseTransactionStatus.PUBLISHED,
        DATABASE_ROLE,
        opaque_fingerprint(8118),
        2,
        0,
        0,
    )
    repository = repository_receipt(
        status="REPOSITORY_TOPOLOGY_PUBLISHED",
        manifest_fingerprint=opaque_fingerprint(8117),
        journal_head_fingerprint=opaque_fingerprint(8109),
        retained_residue_count=2,
    )
    return ApprovedValidationSliceV1.create(
        operation_fingerprint=OPERATION,
        profile_fingerprint=PROFILE,
        authorization_fingerprint=AUTHORIZATION,
        evidence=evidence_result(EvidenceProcessStatus.PUBLISHED),
        evidence_fingerprint=EVIDENCE,
        journal_head_fingerprint=HEAD,
        repository=repository,
        runtime=runtime,
        crx=crx,
        config=config,
        database=database,
        approved_identities_fingerprint=IDENTITIES,
    )


class SyntheticValidationAdapters:
    def __init__(self) -> None:
        self.calls = []
        self.analysis_calls = 0
        self.row_writes = 0
        self.starts = []
        self.mode = "ok"
        self.audit_pids = iter((5101, 5201))

    def bundle(self) -> ValidationAdaptersV1:
        return ValidationAdaptersV1(
            start_provider_disabled=self.start,
            read_health=self.health,
            analyze_public_rule_fallback=self.analysis,
            confirm_public_result=self.confirm,
            observe_persisted_row=self.row,
            stop_exact=self.stop,
            final_database_proof=self.database,
            run_independent_audit=self.audit,
        )

    def start(self, request):
        self.calls.append(f"start_{request.phase}")
        index = len(self.starts)
        pid = 4101 + index * 100
        nonce = request.nonce
        runtime = request.runtime_fingerprint
        if self.mode == "start_b_identity_drift" and index == 1:
            runtime = opaque_fingerprint(8190)
        start = ServiceStartEvidenceV1.create(
            role=ServiceRole.NEW,
            pid=pid,
            start_time_ns=8_100_000 + index,
            executable_fingerprint=runtime,
            port=request.port,
            port_owner_pid=pid,
            profile_fingerprint=request.profile_fingerprint,
            runtime_fingerprint=runtime,
            config_fingerprint=request.config_fingerprint,
            data_role_fingerprint=request.database_role_fingerprint,
            nonce=nonce,
            primary_provider="disabled",
            fallback_provider="disabled",
        )
        self.starts.append(start)
        return start

    def health(self, start):
        self.calls.append("health")
        return ServiceHealthEvidenceV1.create_from_start(start)

    def analysis(self, request):
        self.calls.append("analysis")
        self.analysis_calls += 1
        source = "remote" if self.mode == "wrong_source" else "rule_fallback"
        attempts = 1 if self.mode == "provider_attempt" else 0
        return PublicRuleFallbackResultV1.create(
            request_fingerprint=request.request_fingerprint,
            result_fingerprint=opaque_fingerprint(8120),
            analysis_engine_source=source,
            provider_attempts=attempts,
            safe=self.mode != "unsafe",
        )

    def confirm(self, result):
        self.calls.append("confirm")
        fingerprint = result.result_fingerprint
        if self.mode == "confirmation_drift":
            fingerprint = opaque_fingerprint(8121)
        return OperatorPublicConfirmationV1.create(
            result_fingerprint=fingerprint,
            confirmation_fingerprint=opaque_fingerprint(8122),
            confirmed=True,
        )

    def row(self, result, database_role):
        self.calls.append("row")
        self.row_writes += 1
        rows = 2 if self.mode == "duplicate_row" else 1
        return PersistedPublicRowEvidenceV1.create(
            result_fingerprint=result.result_fingerprint,
            database_role_fingerprint=database_role,
            matching_rows=rows,
            write_count=1,
        )

    def stop(self, start):
        self.calls.append("stop")
        return ServiceStopEvidenceV1.create_from_start(start)

    def database(self, database_role, row):
        self.calls.append("database_proof")
        return FinalDatabaseProofV1.create(
            database_role_fingerprint=database_role,
            matching_rows=row.matching_rows,
            sidecar_count=0,
            source_unchanged=True,
        )

    def audit(self, request):
        self.calls.append(f"audit_{request.audit_kind.value}")
        return issue_verified_test_receipt(
            kind=request.audit_kind,
            process_id=next(self.audit_pids),
            journal_head_fingerprint=request.journal_head_fingerprint,
            approved_identities_fingerprint=request.approved_identities_fingerprint,
            health_evidence_fingerprint=request.health_evidence_fingerprint,
            observed_at_epoch=NOW,
        )
