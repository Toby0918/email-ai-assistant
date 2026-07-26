"""Closed, pathless schema for the immutable Cutover Profile."""

from __future__ import annotations

from .errors import CutoverContractError

PROFILE_ERROR = "CUTOVER_PROFILE_INVALID"
PROFILE_TYPE = "CutoverProfileV1"
PROFILE_BODY_KEYS = (
    "profile_type",
    "governing_master_commit",
    "operator_fingerprint",
    "role_selections",
    "evidence_roles",
    "reviewed_git_selections",
    "worktree_roster",
    "runtime_inputs",
    "sqlite_source",
    "crx",
    "config",
    "acl_policy",
    "maintenance_rules",
    "rollback_roles",
)
ROLE_NAMES = (
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
EVIDENCE_ROLE_NAMES = (
    "review_root",
    "package_target",
    "journal_root",
    "git_records_preservation",
    "worktree_preservation",
    "rollback_publication",
)
GIT_SELECTION_NAMES = (
    "repository_identity",
    "common_directory_identity",
    "git_executable",
    "remote_configuration",
    "local_refs",
    "dirty_layers",
    "worktree_topology",
)
ROLLBACK_ROLE_NAMES = (
    "failed_container",
    "legacy_main",
    "legacy_git_records",
    "legacy_worktrees",
    "legacy_runtime",
    "legacy_database",
)
RUNTIME_KEYS = (
    "python_version",
    "sqlite_version",
    "python_runtime_fingerprint",
    "wheelhouse_fingerprint",
    "dependency_lock_fingerprint",
    "network_allowed",
    "legacy_reuse_allowed",
)
SQLITE_KEYS = (
    "role",
    "source_fingerprint",
    "schema_fingerprint",
    "publication",
    "requires_stopped_service",
    "requires_absent_sidecars",
)
CRX_KEYS = (
    "role",
    "artifact_fingerprint",
    "size_bytes",
    "publication",
    "signing_allowed",
)
CONFIG_KEYS = (
    "role",
    "config_fingerprint",
    "allowed_keys",
    "provider_mode",
    "reads_environment",
)
ACL_KEYS = (
    "policy_fingerprint",
    "container_principal_roles",
    "container_dacl_protected",
    "parent_mode",
    "finance_mode",
    "recursive_rewrite",
)
MAINTENANCE_KEYS = (
    "window_fingerprint",
    "two_identical_preflight_observations",
    "fresh_pre_mutation_gate",
    "cleanup_authorized",
)

def validate_profile_body(value: object) -> dict[str, object]:
    source = _exact_dict(value, PROFILE_BODY_KEYS)
    if (
        source["profile_type"] != PROFILE_TYPE
        or not _is_commit(source["governing_master_commit"])
        or not _is_fingerprint(source["operator_fingerprint"])
    ):
        _invalid()
    return {
        "profile_type": PROFILE_TYPE,
        "governing_master_commit": source["governing_master_commit"],
        "operator_fingerprint": source["operator_fingerprint"],
        "role_selections": _fingerprint_map(
            source["role_selections"], ROLE_NAMES
        ),
        "evidence_roles": _fingerprint_map(
            source["evidence_roles"], EVIDENCE_ROLE_NAMES
        ),
        "reviewed_git_selections": _fingerprint_map(
            source["reviewed_git_selections"], GIT_SELECTION_NAMES
        ),
        "worktree_roster": _worktree_roster(source["worktree_roster"]),
        "runtime_inputs": _runtime_inputs(source["runtime_inputs"]),
        "sqlite_source": _sqlite_source(source["sqlite_source"]),
        "crx": _crx(source["crx"]),
        "config": _config(source["config"]),
        "acl_policy": _acl_policy(source["acl_policy"]),
        "maintenance_rules": _maintenance(source["maintenance_rules"]),
        "rollback_roles": _fingerprint_map(
            source["rollback_roles"], ROLLBACK_ROLE_NAMES
        ),
    }

def _runtime_inputs(value: object) -> dict[str, object]:
    source = _exact_dict(value, RUNTIME_KEYS)
    if (
        source["python_version"] != "3.12.13"
        or source["sqlite_version"] != "3.50.4"
        or not _is_fingerprint(source["python_runtime_fingerprint"])
        or not _is_fingerprint(source["wheelhouse_fingerprint"])
        or not _is_fingerprint(source["dependency_lock_fingerprint"])
        or source["network_allowed"] is not False
        or source["legacy_reuse_allowed"] is not False
    ):
        _invalid()
    return {key: source[key] for key in RUNTIME_KEYS}

def _sqlite_source(value: object) -> dict[str, object]:
    source = _exact_dict(value, SQLITE_KEYS)
    if (
        source["role"] != "legacy_analysis_database"
        or not _is_fingerprint(source["source_fingerprint"])
        or not _is_fingerprint(source["schema_fingerprint"])
        or source["publication"] != "create_only"
        or source["requires_stopped_service"] is not True
        or source["requires_absent_sidecars"] is not True
    ):
        _invalid()
    return {key: source[key] for key in SQLITE_KEYS}

def _crx(value: object) -> dict[str, object]:
    source = _exact_dict(value, CRX_KEYS)
    if (
        source["role"] != "reviewed_browser_extension"
        or not _is_fingerprint(source["artifact_fingerprint"])
        or type(source["size_bytes"]) is not int
        or not 1 <= source["size_bytes"] <= 1024 * 1024 * 1024
        or source["publication"] != "create_only"
        or source["signing_allowed"] is not False
    ):
        _invalid()
    return {key: source[key] for key in CRX_KEYS}

def _config(value: object) -> dict[str, object]:
    source = _exact_dict(value, CONFIG_KEYS)
    allowed_keys = [
        "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
        "EMAIL_AGENT_LOG_LEVEL",
    ]
    if (
        source["role"] != "managed_non_secret_config"
        or not _is_fingerprint(source["config_fingerprint"])
        or source["allowed_keys"] != allowed_keys
        or type(source["allowed_keys"]) is not list
        or source["provider_mode"] != "disabled"
        or source["reads_environment"] is not False
    ):
        _invalid()
    return {
        **{key: source[key] for key in CONFIG_KEYS if key != "allowed_keys"},
        "allowed_keys": list(allowed_keys),
    }

def _acl_policy(value: object) -> dict[str, object]:
    source = _exact_dict(value, ACL_KEYS)
    principal_roles = ["builtin_administrators", "operator", "system"]
    if (
        not _is_fingerprint(source["policy_fingerprint"])
        or source["container_principal_roles"] != principal_roles
        or type(source["container_principal_roles"]) is not list
        or source["container_dacl_protected"] is not True
        or source["parent_mode"] != "capture_compare_only"
        or source["finance_mode"] != "capture_compare_only"
        or source["recursive_rewrite"] is not False
    ):
        _invalid()
    return {
        **{
            key: source[key]
            for key in ACL_KEYS
            if key != "container_principal_roles"
        },
        "container_principal_roles": list(principal_roles),
    }

def _maintenance(value: object) -> dict[str, object]:
    source = _exact_dict(value, MAINTENANCE_KEYS)
    if (
        not _is_fingerprint(source["window_fingerprint"])
        or source["two_identical_preflight_observations"] is not True
        or source["fresh_pre_mutation_gate"] is not True
        or source["cleanup_authorized"] is not False
    ):
        _invalid()
    return {key: source[key] for key in MAINTENANCE_KEYS}

def _worktree_roster(value: object) -> list[dict[str, str]]:
    if type(value) is not list or len(value) != 11:
        _invalid()
    result: list[dict[str, str]] = []
    fingerprints: set[str] = set()
    for index, item in enumerate(value, start=1):
        source = _exact_dict(
            item, ("role", "placement", "selection_fingerprint")
        )
        expected_role = f"worktree_{index:02d}"
        expected_placement = "embedded" if index <= 8 else "external"
        fingerprint = source["selection_fingerprint"]
        if (
            source["role"] != expected_role
            or source["placement"] != expected_placement
            or not _is_fingerprint(fingerprint)
            or fingerprint in fingerprints
        ):
            _invalid()
        fingerprints.add(fingerprint)
        result.append(
            {
                "role": expected_role,
                "placement": expected_placement,
                "selection_fingerprint": fingerprint,
            }
        )
    return result

def _fingerprint_map(value: object, names: tuple[str, ...]) -> dict[str, str]:
    source = _exact_dict(value, names)
    result = {name: source[name] for name in names}
    if (
        any(not _is_fingerprint(item) for item in result.values())
        or len(set(result.values())) != len(result)
    ):
        _invalid()
    return result

def _exact_dict(
    value: object, expected_keys: tuple[str, ...]
) -> dict[str, object]:
    if type(value) is not dict or set(value) != set(expected_keys):
        _invalid()
    return value

def _is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )

def _is_commit(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )

def _invalid() -> None:
    raise CutoverContractError(PROFILE_ERROR)
