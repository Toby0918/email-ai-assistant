"""Closed R2 phase, journal, lifecycle, and outcome vocabulary."""

from __future__ import annotations

from enum import Enum


class AuthorizationDomain(str, Enum):
    PREFLIGHT = "preflight"
    EVIDENCE = "evidence"
    EXECUTION = "execution"
    RECOVERY = "recovery"


_AUTHORIZATION_PHASE_DOMAINS = {
    "current_topology_preflight": AuthorizationDomain.PREFLIGHT,
    "host_baseline": AuthorizationDomain.PREFLIGHT,
    "evidence_review": AuthorizationDomain.PREFLIGHT,
    "evidence_verification": AuthorizationDomain.PREFLIGHT,
    "final_audit_readiness": AuthorizationDomain.PREFLIGHT,
    "recovery_inspection": AuthorizationDomain.PREFLIGHT,
    "independent_stopped_layout_audit": AuthorizationDomain.PREFLIGHT,
    "independent_final_running_audit": AuthorizationDomain.PREFLIGHT,
    "evidence_publication": AuthorizationDomain.EVIDENCE,
    "execute": AuthorizationDomain.EXECUTION,
    "resume": AuthorizationDomain.EXECUTION,
    "rollback": AuthorizationDomain.RECOVERY,
    "incident_containment": AuthorizationDomain.RECOVERY,
    "legacy_recovery": AuthorizationDomain.RECOVERY,
}


def authorization_domain_for_phase(
    phase: object,
) -> AuthorizationDomain | None:
    if type(phase) is not str:
        return None
    return _AUTHORIZATION_PHASE_DOMAINS.get(phase)


class ManagedPublicationUnit(str, Enum):
    RUNTIME = "runtime"
    DATABASE = "database"
    CRX = "crx"
    CONFIG = "config"


class R2JournalBoundary(str, Enum):
    CURRENT_TOPOLOGY_PREFLIGHT = "current_topology_preflight"
    HOST_BASELINE = "host_baseline"
    EVIDENCE_REVIEW = "evidence_review"
    EVIDENCE_PUBLICATION = "evidence_publication"
    EVIDENCE_VERIFICATION = "evidence_verification"
    PRE_MUTATION_GATE = "pre_mutation_gate"
    LEGACY_SERVICE_QUIESCENCE_INTENT = (
        "legacy_service_quiescence_intent"
    )
    LEGACY_SERVICE_QUIESCENCE_EFFECT = (
        "legacy_service_quiescence_effect"
    )
    LEGACY_SERVICE_QUIESCENCE_COMMITTED = (
        "legacy_service_quiescence_committed"
    )
    LEGACY_ANCHOR_RENAME = "legacy_anchor_rename"
    CONTAINER_PUBLICATION = "container_publication"
    MAIN_PUBLICATION = "main_publication"
    ACL_WHOLE_TREE_CONFORMANCE = "acl_whole_tree_conformance"
    REPOSITORY_RELOCATION = "repository_relocation"
    WORKTREE_RECONSTRUCTION = "worktree_reconstruction"
    RUNTIME_PREPARE = "runtime_prepare"
    RUNTIME_PUBLISH = "runtime_publish"
    DATABASE_PREPARE = "database_prepare"
    DATABASE_PUBLISH = "database_publish"
    CRX_PREPARE = "crx_prepare"
    CRX_PUBLISH = "crx_publish"
    CONFIG_PREPARE = "config_prepare"
    CONFIG_PUBLISH = "config_publish"
    VALIDATION_START_A = "validation_start_a"
    RULE_FALLBACK_ANALYSIS = "rule_fallback_analysis"
    VALIDATION_STOP_A = "validation_stop_a"
    STOPPED_LAYOUT_AUDIT = "stopped_layout_audit"
    FINAL_START_B = "final_start_b"
    FINAL_RUNNING_AUDIT = "final_running_audit"
    PENDING_EFFECT_CLASSIFICATION = "pending_effect_classification"
    RECOVERY_INSPECTION = "recovery_inspection"
    FAILED_CONTAINER_PRESERVATION = "failed_container_preservation"
    CONFIG_ROLLBACK = "config_rollback"
    CRX_ROLLBACK = "crx_rollback"
    DATABASE_ROLLBACK = "database_rollback"
    RUNTIME_ROLLBACK = "runtime_rollback"
    WORKTREE_ROLLBACK = "worktree_rollback"
    REPOSITORY_ROLLBACK = "repository_rollback"
    CONTAINER_ROLLBACK = "container_rollback"
    LEGACY_ANCHOR_RESTORATION = "legacy_anchor_restoration"
    LEGACY_SERVICE_RECOVERY = "legacy_service_recovery"
    LEGACY_FLAT_LAYOUT_RESTORED = "legacy_flat_layout_restored"
    INCIDENT_STOP = "incident_stop"
    CUTOVER_SUCCESS = "cutover_success"


_MANAGED_BOUNDARIES = {
    ManagedPublicationUnit.RUNTIME: (
        R2JournalBoundary.RUNTIME_PREPARE,
        R2JournalBoundary.RUNTIME_PUBLISH,
    ),
    ManagedPublicationUnit.DATABASE: (
        R2JournalBoundary.DATABASE_PREPARE,
        R2JournalBoundary.DATABASE_PUBLISH,
    ),
    ManagedPublicationUnit.CRX: (
        R2JournalBoundary.CRX_PREPARE,
        R2JournalBoundary.CRX_PUBLISH,
    ),
    ManagedPublicationUnit.CONFIG: (
        R2JournalBoundary.CONFIG_PREPARE,
        R2JournalBoundary.CONFIG_PUBLISH,
    ),
}


def managed_publication_boundaries(
) -> dict[ManagedPublicationUnit, tuple[R2JournalBoundary, ...]]:
    return dict(_MANAGED_BOUNDARIES)


class JournalFactKind(str, Enum):
    INTENT = "intent"
    EFFECT_OBSERVED = "effect_observed"
    COMMITTED = "committed"
    PENDING_CLASSIFIED = "pending_classified"
    AUDIT_ATTESTED = "audit_attested"
    FINAL_OUTCOME = "final_outcome"


class PendingEffectState(str, Enum):
    EFFECT_ABSENT_EXACT = "EFFECT_ABSENT_EXACT"
    EFFECT_PRESENT_EXACT = "EFFECT_PRESENT_EXACT"
    EFFECT_AMBIGUOUS = "EFFECT_AMBIGUOUS"


class FinalCutoverOutcome(str, Enum):
    CUTOVER_SUCCESS = "CUTOVER_SUCCESS"
    LEGACY_FLAT_LAYOUT_RESTORED = "LEGACY_FLAT_LAYOUT_RESTORED"
    INCIDENT_STOP = "INCIDENT_STOP"


class TwoStartLifecycleState(str, Enum):
    LEGACY_STOPPED = "LEGACY_STOPPED"
    VALIDATION_START_A_RUNNING = "VALIDATION_START_A_RUNNING"
    VALIDATION_START_A_STOPPED = "VALIDATION_START_A_STOPPED"
    STOPPED_LAYOUT_AUDITED = "STOPPED_LAYOUT_AUDITED"
    FINAL_START_B_RUNNING = "FINAL_START_B_RUNNING"
    FINAL_RUNNING_AUDITED = "FINAL_RUNNING_AUDITED"
    CUTOVER_SUCCESS = "CUTOVER_SUCCESS"
