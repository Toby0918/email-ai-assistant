"""Exact unchanged ContainerAudit composition bridge."""

from backend.container_audit import (
    ContainerAuditAdapters,
    ContainerAuditResult,
    TrustedAuditPolicy,
    run_container_audit,
)
from backend.container_audit.policy import is_valid_policy


def compose_audit_adapters(
    *,
    filesystem,
    acl,
    volume,
    git,
    worktree,
    runtime,
    sqlite,
) -> ContainerAuditAdapters:
    return ContainerAuditAdapters(
        filesystem=filesystem,
        acl=acl,
        volume=volume,
        git=git,
        worktree=worktree,
        runtime=runtime,
        sqlite=sqlite,
    )


def audit_policy_is_valid(policy: object) -> bool:
    return is_valid_policy(policy)


def run_final_container_audit(
    *,
    policy: TrustedAuditPolicy,
    adapters: ContainerAuditAdapters,
) -> ContainerAuditResult:
    return run_container_audit(policy=policy, adapters=adapters)


__all__ = [
    "ContainerAuditAdapters",
    "ContainerAuditResult",
    "TrustedAuditPolicy",
    "audit_policy_is_valid",
    "compose_audit_adapters",
    "run_final_container_audit",
]
