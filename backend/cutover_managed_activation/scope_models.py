"""Private path-bearing values for one test-owned publication sandbox."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)

from .runtime_policy import RuntimeInputReviewV1


@dataclass(frozen=True, slots=True, repr=False)
class _SyntheticActivationScenarioSnapshot:
    root: Path = field(repr=False)
    marker: Path = field(repr=False)
    python_source: Path = field(repr=False)
    python_source_manifest: Path = field(repr=False)
    wheelhouse: Path = field(repr=False)
    dependency_lock: Path = field(repr=False)
    runtime_target: Path = field(repr=False)
    database_source: Path = field(repr=False)
    database_target: Path = field(repr=False)
    crx_source: Path = field(repr=False)
    crx_target: Path = field(repr=False)
    config_target: Path = field(repr=False)
    config_domains: tuple[str, ...] = field(repr=False)
    config_log_level: str

    @property
    def config_values(self) -> dict[str, object]:
        return {
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": list(self.config_domains),
            "EMAIL_AGENT_LOG_LEVEL": self.config_log_level,
        }


@dataclass(frozen=True, slots=True, repr=False)
class _SyntheticActivationReview:
    scenario: _SyntheticActivationScenarioSnapshot = field(repr=False)
    runtime_inputs: RuntimeInputReviewV1 = field(repr=False)
    root_identity: str = field(repr=False)
    marker_identity: str = field(repr=False)
    runtime_parent_fingerprint: str = field(repr=False)
    database_parent_fingerprint: str = field(repr=False)
    database_source_fingerprint: str = field(repr=False)
    database_schema_fingerprint: str = field(repr=False)
    database_native_identity: str = field(repr=False)
    artifact_parent_fingerprint: str = field(repr=False)
    crx_artifact_fingerprint: str = field(repr=False)
    crx_native_identity: str = field(repr=False)
    crx_sha256: str = field(repr=False)
    crx_size_bytes: int
    crx_format_version: int
    config_parent_fingerprint: str = field(repr=False)
    config_fingerprint: str = field(repr=False)
    config_sha256: str = field(repr=False)
    config_size_bytes: int
    stopped_service_role_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)

    @property
    def python_runtime_fingerprint(self) -> str:
        return self.runtime_inputs.python_runtime_fingerprint

    @property
    def wheelhouse_fingerprint(self) -> str:
        return self.runtime_inputs.wheelhouse_fingerprint

    @property
    def dependency_lock_fingerprint(self) -> str:
        return self.runtime_inputs.dependency_lock_fingerprint


@dataclass(frozen=True, slots=True, repr=False)
class _SyntheticActivationScope:
    review: _SyntheticActivationReview = field(repr=False)
    profile: CutoverProfileV1 = field(repr=False)
    authorization: TestSandboxAuthorizationV1 = field(repr=False)
    authorization_fingerprint: str = field(repr=False)
