"""Bind one caller-owned synthetic Windows managed-publication sandbox."""

from __future__ import annotations

import hashlib

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)

from .canonical import fail, fingerprint
from .config_contract import ManagedConfigV1
from .errors import ManagedActivationError
from .runtime_policy import review_runtime_inputs
from .scope_models import (
    _SyntheticActivationReview,
    _SyntheticActivationScenarioSnapshot,
    _SyntheticActivationScope,
)
from .scope_paths import (
    crx_format_version,
    identity,
    native_file_identity,
    scenario_paths,
    sqlite_schema_fingerprint,
    validate_owned_paths,
)
from .scope_profile import (
    authorization_fingerprint,
    authorization_matches,
    require_profile_matches,
)

_ERROR = "managed_activation_scope_invalid"


def _review_test_sandbox_activation(
    scenario: object,
) -> _SyntheticActivationReview:
    try:
        return _review_sandbox_activation(scenario)
    except ManagedActivationError:
        raise
    except Exception:
        fail(_ERROR)


def _review_sandbox_activation(scenario) -> _SyntheticActivationReview:
    supplied_paths = scenario_paths(scenario)
    validate_owned_paths(supplied_paths)
    snapshot = _snapshot_scenario(supplied_paths)
    paths = scenario_paths(snapshot)
    runtime = review_runtime_inputs(
        source=paths["python_source"],
        source_manifest=paths["python_source_manifest"],
        wheelhouse=paths["wheelhouse"],
        dependency_lock=paths["dependency_lock"],
    )
    root_marker = _review_root_and_marker(paths)
    database = _review_database(paths)
    crx = _review_crx(paths)
    config = _review_config(paths)
    roles = _review_roles(paths, root_marker)
    operation = _operation_fingerprint(
        paths, runtime, database, crx, config, roles
    )
    return _build_review(
        snapshot, runtime, root_marker, database, crx, config, roles, operation
    )


def _snapshot_scenario(paths) -> _SyntheticActivationScenarioSnapshot:
    config = ManagedConfigV1.from_mapping(paths["config_values"])
    return _SyntheticActivationScenarioSnapshot(
        root=paths["root"],
        marker=paths["marker"],
        python_source=paths["python_source"],
        python_source_manifest=paths["python_source_manifest"],
        wheelhouse=paths["wheelhouse"],
        dependency_lock=paths["dependency_lock"],
        runtime_target=paths["runtime_target"],
        database_source=paths["database_source"],
        database_target=paths["database_target"],
        crx_source=paths["crx_source"],
        crx_target=paths["crx_target"],
        config_target=paths["config_target"],
        config_domains=config.internal_email_domains,
        config_log_level=config.log_level,
    )


def _review_root_and_marker(paths) -> dict[str, str]:
    return {
        "root": identity(paths["root"]),
        "marker": identity(paths["marker"]),
    }


def _review_database(paths) -> dict[str, str]:
    payload = paths["database_source"].read_bytes()
    return {
        "sha256": hashlib.sha256(payload).hexdigest(),
        "schema": sqlite_schema_fingerprint(payload),
        "native": native_file_identity(paths["database_source"]),
    }


def _review_crx(paths) -> dict[str, object]:
    payload = paths["crx_source"].read_bytes()
    sha256 = hashlib.sha256(payload).hexdigest()
    size = len(payload)
    version = crx_format_version(payload)
    native = native_file_identity(paths["crx_source"])
    artifact = fingerprint(
        "issue57-reviewed-crx-v1",
        {
            "source_identity": native,
            "sha256": sha256,
            "size_bytes": size,
            "format_version": version,
        },
        code=_ERROR,
    )
    return {
        "sha256": sha256,
        "size": size,
        "version": version,
        "native": native,
        "artifact": artifact,
    }


def _review_config(paths) -> dict[str, object]:
    config = ManagedConfigV1.from_mapping(paths["config_values"])
    payload = config.to_canonical_bytes()
    sha256 = hashlib.sha256(payload).hexdigest()
    size = len(payload)
    selection = fingerprint(
        "issue57-managed-config-selection-v1",
        {
            "sha256": sha256,
            "size_bytes": size,
            "schema": "managed-non-secret-config/v1",
        },
        code=_ERROR,
    )
    return {"sha256": sha256, "size": size, "selection": selection}


def _review_roles(paths, root_marker) -> dict[str, str]:
    stopped = fingerprint(
        "issue57-stopped-service-role-v1",
        root_marker,
        code=_ERROR,
    )
    return {
        "runtime_parent": identity(paths["runtime_target"].parent),
        "database_parent": identity(paths["database_target"].parent),
        "artifact_parent": identity(paths["crx_target"].parent),
        "config_parent": identity(paths["config_target"].parent),
        "stopped_service": stopped,
    }


def _operation_fingerprint(paths, runtime, database, crx, config, roles) -> str:
    target_names = {
        role: hashlib.sha256(
            paths[field].name.casefold().encode("utf-8")
        ).hexdigest()
        for role, field in (
            ("runtime", "runtime_target"),
            ("database", "database_target"),
            ("artifact", "crx_target"),
            ("config", "config_target"),
        )
    }
    return fingerprint(
        "issue57-managed-publication-operation-v1",
        {
            "root": identity(paths["root"]),
            "marker": identity(paths["marker"]),
            "runtime_parent": roles["runtime_parent"],
            "runtime_target": target_names["runtime"],
            "python": runtime.python_runtime_fingerprint,
            "wheelhouse": runtime.wheelhouse_fingerprint,
            "lock": runtime.dependency_lock_fingerprint,
            "database_source": database["sha256"],
            "database_schema": database["schema"],
            "database_parent": roles["database_parent"],
            "database_target": target_names["database"],
            "crx": crx["artifact"],
            "artifact_parent": roles["artifact_parent"],
            "artifact_target": target_names["artifact"],
            "config": config["selection"],
            "config_parent": roles["config_parent"],
            "config_target": target_names["config"],
            "stopped_service_role": roles["stopped_service"],
        },
        code=_ERROR,
    )


def _build_review(
    scenario, runtime, root_marker, database, crx, config, roles, operation
):
    return _SyntheticActivationReview(
        scenario=scenario,
        runtime_inputs=runtime,
        root_identity=root_marker["root"],
        marker_identity=root_marker["marker"],
        runtime_parent_fingerprint=roles["runtime_parent"],
        database_parent_fingerprint=roles["database_parent"],
        database_source_fingerprint=database["sha256"],
        database_schema_fingerprint=database["schema"],
        database_native_identity=database["native"],
        artifact_parent_fingerprint=roles["artifact_parent"],
        crx_artifact_fingerprint=crx["artifact"],
        crx_native_identity=crx["native"],
        crx_sha256=crx["sha256"],
        crx_size_bytes=crx["size"],
        crx_format_version=crx["version"],
        config_parent_fingerprint=roles["config_parent"],
        config_fingerprint=config["selection"],
        config_sha256=config["sha256"],
        config_size_bytes=config["size"],
        stopped_service_role_fingerprint=roles["stopped_service"],
        operation_fingerprint=operation,
    )


def _bind_test_sandbox_activation(
    *,
    review: object,
    profile: object,
    authorization: object,
    observed_at_epoch: object,
) -> _SyntheticActivationScope:
    try:
        return _bind_review(
            review, profile, authorization, observed_at_epoch
        )
    except ManagedActivationError:
        raise
    except Exception:
        fail(_ERROR)


def _bind_review(review, profile, authorization, observed_at_epoch):
    if not _binding_types_are_exact(
        review, profile, authorization, observed_at_epoch
    ):
        fail(_ERROR)
    if not authorization_matches(
        review, profile, authorization, observed_at_epoch
    ):
        fail("managed_activation_authorization_invalid")
    current = _review_test_sandbox_activation(review.scenario)
    if current != review:
        fail("managed_activation_scope_drift")
    require_profile_matches(profile, current)
    return _SyntheticActivationScope(
        review=current,
        profile=profile,
        authorization=authorization,
        authorization_fingerprint=authorization_fingerprint(authorization),
    )


def _binding_types_are_exact(review, profile, authorization, observed) -> bool:
    return (
        type(review) is _SyntheticActivationReview
        and type(profile) is CutoverProfileV1
        and type(authorization) is TestSandboxAuthorizationV1
        and type(observed) is int
    )


__all__ = [
    "_bind_test_sandbox_activation",
    "_review_test_sandbox_activation",
]
