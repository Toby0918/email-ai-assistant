"""Profile and authorization checks for synthetic managed publication."""

from __future__ import annotations

import hashlib

from .canonical import canonical_json, fail
from .scope_models import _SyntheticActivationReview

MASTER = "7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd"
_ERROR = "managed_activation_scope_invalid"


def require_profile_matches(
    profile: object,
    review: _SyntheticActivationReview,
) -> None:
    mapping = profile.to_mapping()
    selections = mapping["role_selections"]
    exact = (
        mapping["governing_master_commit"] == MASTER
        and mapping["runtime_inputs"] == _expected_runtime(review)
        and selections["runtimes"] == review.runtime_parent_fingerprint
        and selections["local_data"] == review.database_parent_fingerprint
        and mapping["sqlite_source"] == _expected_database(review)
        and selections["artifacts"] == review.artifact_parent_fingerprint
        and mapping["crx"] == _expected_crx(review)
        and selections["config"] == review.config_parent_fingerprint
        and mapping["config"] == _expected_config(review)
    )
    if not exact:
        fail("managed_activation_profile_mismatch")


def _expected_runtime(review) -> dict[str, object]:
    return {
        "python_version": "3.12.13",
        "sqlite_version": "3.50.4",
        "python_runtime_fingerprint": review.python_runtime_fingerprint,
        "wheelhouse_fingerprint": review.wheelhouse_fingerprint,
        "dependency_lock_fingerprint": review.dependency_lock_fingerprint,
        "network_allowed": False,
        "legacy_reuse_allowed": False,
    }


def _expected_database(review) -> dict[str, object]:
    return {
        "role": "legacy_analysis_database",
        "source_fingerprint": review.database_source_fingerprint,
        "schema_fingerprint": review.database_schema_fingerprint,
        "publication": "create_only",
        "requires_stopped_service": True,
        "requires_absent_sidecars": True,
    }


def _expected_crx(review) -> dict[str, object]:
    return {
        "role": "reviewed_browser_extension",
        "artifact_fingerprint": review.crx_artifact_fingerprint,
        "size_bytes": review.crx_size_bytes,
        "publication": "create_only",
        "signing_allowed": False,
    }


def _expected_config(review) -> dict[str, object]:
    return {
        "role": "managed_non_secret_config",
        "config_fingerprint": review.config_fingerprint,
        "allowed_keys": [
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
            "EMAIL_AGENT_LOG_LEVEL",
        ],
        "provider_mode": "disabled",
        "reads_environment": False,
    }


def authorization_matches(review, profile, authorization, observed) -> bool:
    return (
        authorization.profile_fingerprint == profile.profile_fingerprint
        and authorization.operation_fingerprint
        == review.operation_fingerprint
        and authorization.phase == "execute"
        and 0 <= observed < authorization.expires_at_epoch
    )


def authorization_fingerprint(authorization) -> str:
    return hashlib.sha256(
        b"issue57-test-authorization-v1\0"
        + canonical_json(
            {
                "profile": authorization.profile_fingerprint,
                "operation": authorization.operation_fingerprint,
                "phase": authorization.phase,
                "expires": authorization.expires_at_epoch,
            },
            code=_ERROR,
        )
    ).hexdigest()
