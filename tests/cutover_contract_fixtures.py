"""Synthetic content-free fixtures for Issue #51 contracts."""

from __future__ import annotations

import hashlib
import json


GOVERNING_MASTER = "0c99d89195162a766d58c06baf2af2a81fede796"


class HostileComparison:
    def __eq__(self, _other: object) -> bool:
        raise RuntimeError("hostile comparison must not run")

    def __ne__(self, _other: object) -> bool:
        raise RuntimeError("hostile comparison must not run")


class HostileKey(HostileComparison):
    def __init__(self, collision_target: str) -> None:
        self._collision_target = collision_target

    def __hash__(self) -> int:
        return hash(self._collision_target)


def opaque_fingerprint(index: int) -> str:
    return f"{index:064x}"


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def valid_profile_body() -> dict[str, object]:
    fingerprint_index = iter(range(1, 80))

    def fingerprint() -> str:
        return opaque_fingerprint(next(fingerprint_index))

    role_names = (
        "projects_parent",
        "finance_project",
        "project_container",
        "repository_root",
        "runtimes",
        "local_data",
        "runtime_temp",
        "logs",
        "artifacts",
        "worktrees",
        "config",
        "operator_private",
        "legacy_source",
        "failed_container",
    )
    evidence_role_names = (
        "review_root",
        "package_target",
        "journal_root",
        "git_records_preservation",
        "worktree_preservation",
        "rollback_publication",
    )
    git_selection_names = (
        "repository_identity",
        "common_directory_identity",
        "git_executable",
        "remote_configuration",
        "local_refs",
        "dirty_layers",
        "worktree_topology",
    )
    worktree_roster = [
        {
            "role": f"worktree_{index:02d}",
            "placement": "embedded" if index <= 8 else "external",
            "selection_fingerprint": fingerprint(),
        }
        for index in range(1, 12)
    ]
    return {
        "profile_type": "CutoverProfileV1",
        "governing_master_commit": GOVERNING_MASTER,
        "operator_fingerprint": fingerprint(),
        "role_selections": {name: fingerprint() for name in role_names},
        "evidence_roles": {
            name: fingerprint() for name in evidence_role_names
        },
        "reviewed_git_selections": {
            name: fingerprint() for name in git_selection_names
        },
        "worktree_roster": worktree_roster,
        "runtime_inputs": {
            "python_version": "3.12.13",
            "sqlite_version": "3.50.4",
            "python_runtime_fingerprint": fingerprint(),
            "wheelhouse_fingerprint": fingerprint(),
            "dependency_lock_fingerprint": fingerprint(),
            "network_allowed": False,
            "legacy_reuse_allowed": False,
        },
        "sqlite_source": {
            "role": "legacy_analysis_database",
            "source_fingerprint": fingerprint(),
            "schema_fingerprint": fingerprint(),
            "publication": "create_only",
            "requires_stopped_service": True,
            "requires_absent_sidecars": True,
        },
        "crx": {
            "role": "reviewed_browser_extension",
            "artifact_fingerprint": fingerprint(),
            "size_bytes": 4096,
            "publication": "create_only",
            "signing_allowed": False,
        },
        "config": {
            "role": "managed_non_secret_config",
            "config_fingerprint": fingerprint(),
            "allowed_keys": [
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
                "EMAIL_AGENT_LOG_LEVEL",
            ],
            "provider_mode": "disabled",
            "reads_environment": False,
        },
        "acl_policy": {
            "policy_fingerprint": fingerprint(),
            "container_principal_roles": [
                "builtin_administrators",
                "operator",
                "system",
            ],
            "container_dacl_protected": True,
            "parent_mode": "capture_compare_only",
            "finance_mode": "capture_compare_only",
            "recursive_rewrite": False,
        },
        "maintenance_rules": {
            "window_fingerprint": fingerprint(),
            "two_identical_preflight_observations": True,
            "fresh_pre_mutation_gate": True,
            "cleanup_authorized": False,
        },
        "rollback_roles": {
            name: fingerprint()
            for name in (
                "failed_container",
                "legacy_main",
                "legacy_git_records",
                "legacy_worktrees",
                "legacy_runtime",
                "legacy_database",
            )
        },
    }


def valid_authorization_mapping(
    authorization_type: str,
    *,
    profile_fingerprint: str,
    operator_fingerprint: str,
    operation: str,
    phase: str,
) -> dict[str, object]:
    body = {
        "authorization_type": authorization_type,
        "operation": operation,
        "operation_fingerprint": opaque_fingerprint(201),
        "profile_fingerprint": profile_fingerprint,
        "governing_master_commit": GOVERNING_MASTER,
        "operator_fingerprint": operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": 1_800_000_000,
        "not_before_epoch": 1_800_000_010,
        "expires_at_epoch": 1_800_000_610,
    }
    return {
        **body,
        "authorization_fingerprint": hashlib.sha256(
            canonical_json(body)
        ).hexdigest(),
    }
