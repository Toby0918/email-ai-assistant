"""Closed commands, domains, operator roles, and production roles."""

from __future__ import annotations

from enum import Enum


class AuthorityDomainV2(str, Enum):
    PREFLIGHT = "preflight"
    EVIDENCE = "evidence"
    EXECUTION = "execution"
    RECOVERY = "recovery"


class ProductionCommandV2(str, Enum):
    CURRENT_TOPOLOGY_PREFLIGHT = "current_topology_preflight"
    HOST_BASELINE = "host_baseline"
    EVIDENCE_REVIEW = "evidence_review"
    EVIDENCE_VERIFICATION = "evidence_verification"
    FINAL_AUDIT_READINESS = "final_audit_readiness"
    RECOVERY_INSPECTION = "recovery_inspection"
    EVIDENCE_PUBLICATION = "evidence_publication"
    EXECUTE = "execute"
    RESUME = "resume"
    ROLLBACK = "rollback"


class OperatorRoleV2(str, Enum):
    PREFLIGHT_OPERATOR = "preflight_operator"
    EVIDENCE_OPERATOR = "evidence_operator"
    EXECUTION_OPERATOR = "execution_operator"
    RECOVERY_OPERATOR = "recovery_operator"


class ProductionRoleV2(str, Enum):
    LEGACY_SOURCE_ANCHOR = "legacy_source_anchor"
    PROJECT_CONTAINER = "project_container"
    MANAGED_MAIN = "managed_main"
    REPOSITORY_ROOT = "repository_root"
    GIT_COMMON_STATE = "git_common_state"
    WORKTREE_TOPOLOGY = "worktree_topology"
    RUNTIME = "runtime"
    DATABASE = "database"
    CRX = "crx"
    CONFIG = "config"
    TRANSACTION_JOURNAL = "transaction_journal"
    EVIDENCE_PACKAGE = "evidence_package"
    FAILED_CONTAINER = "failed_container"
    LEGACY_SERVICE = "legacy_service"
    MANAGED_SERVICE = "managed_service"
    STOPPED_LAYOUT_AUDIT = "stopped_layout_audit"
    FINAL_RUNNING_AUDIT = "final_running_audit"
    RETENTION_LEDGER = "retention_ledger"


_COMMAND_DOMAINS = {
    ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT: AuthorityDomainV2.PREFLIGHT,
    ProductionCommandV2.HOST_BASELINE: AuthorityDomainV2.PREFLIGHT,
    ProductionCommandV2.EVIDENCE_REVIEW: AuthorityDomainV2.PREFLIGHT,
    ProductionCommandV2.EVIDENCE_VERIFICATION: AuthorityDomainV2.PREFLIGHT,
    ProductionCommandV2.FINAL_AUDIT_READINESS: AuthorityDomainV2.PREFLIGHT,
    ProductionCommandV2.RECOVERY_INSPECTION: AuthorityDomainV2.PREFLIGHT,
    ProductionCommandV2.EVIDENCE_PUBLICATION: AuthorityDomainV2.EVIDENCE,
    ProductionCommandV2.EXECUTE: AuthorityDomainV2.EXECUTION,
    ProductionCommandV2.RESUME: AuthorityDomainV2.EXECUTION,
    ProductionCommandV2.ROLLBACK: AuthorityDomainV2.RECOVERY,
}


def authority_domain_for_command_v2(
    command: object,
) -> AuthorityDomainV2 | None:
    if type(command) is not ProductionCommandV2:
        return None
    return _COMMAND_DOMAINS[command]
