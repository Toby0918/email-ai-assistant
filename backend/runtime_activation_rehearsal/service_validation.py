"""Strict validation for provider-disabled service evidence."""

from __future__ import annotations

import re

from .adapters import SqliteSnapshot
from .service_evidence import (
    AnalysisProbeEvidence,
    AnalysisProbeRequest,
    HealthProbeEvidence,
    HealthProbeRequest,
    ServiceStartEvidence,
    ServiceStartRequest,
)

_SHA256 = re.compile(r"[0-9a-f]{64}", re.ASCII)


def valid_start(
    value: object,
    request: ServiceStartRequest,
) -> bool:
    """Require exact Managed routing and provider-disabled state."""
    if type(value) is not ServiceStartEvidence:
        return False
    return (
        type(value.schema_version) is int
        and value.schema_version == 1
        and type(request.schema_version) is int
        and request.schema_version == 1
        and value.started is True
        and _valid_start_strings(value)
        and _digest(value.activation_token)
        and value.activation_token == request.activation_token
        and value.service_identity == request.service_identity
        and _start_echoes(value, request)
        and value.llm_provider == request.llm_provider == "disabled"
        and value.text_fallback_provider
        == request.text_fallback_provider
        == "disabled"
        and value.provider_keys_present is False
        and value.private_knowledge_enabled is False
        and value.provider_client_created is False
        and value.external_network_used is False
        and value.loopback_host == request.loopback_host == "127.0.0.1"
    )


def valid_health(
    value: object,
    request: HealthProbeRequest,
) -> bool:
    """Require one healthy literal-loopback provider-disabled probe."""
    return (
        type(value) is HealthProbeEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and _digest(value.activation_token)
        and value.activation_token == request.activation_token
        and _identity(value.service_identity)
        and value.service_identity == request.service_identity
        and type(value.loopback_host) is str
        and value.loopback_host == request.loopback_host == "127.0.0.1"
        and value.healthy is True
        and value.loopback_only is True
        and type(value.llm_provider) is str
        and value.llm_provider == "disabled"
        and type(value.text_fallback_provider) is str
        and value.text_fallback_provider == "disabled"
        and type(value.provider_calls) is int
        and value.provider_calls == 0
        and value.external_network_used is False
    )


def valid_analysis(
    value: object,
    request: AnalysisProbeRequest,
) -> bool:
    """Require one persisted synthetic rule-fallback analysis."""
    return (
        type(value) is AnalysisProbeEvidence
        and type(value.schema_version) is int
        and value.schema_version == 1
        and _digest(value.activation_token)
        and value.activation_token == request.activation_token
        and _identity(value.service_identity)
        and value.service_identity == request.service_identity
        and _identity(value.database_identity)
        and value.database_identity == request.database_identity
        and value.user_confirmed is request.user_confirmed is True
        and value.synthetic is request.synthetic is True
        and type(value.analysis_calls) is int
        and value.analysis_calls == 1
        and type(value.route) is str
        and value.route == "rule_fallback"
        and type(value.saved_id) is int
        and value.saved_id > 0
        and value.persisted is True
        and type(value.primary_provider_calls) is int
        and value.primary_provider_calls == 0
        and type(value.fallback_provider_calls) is int
        and value.fallback_provider_calls == 0
        and value.mailbox_accessed is False
        and value.vault_accessed is False
        and value.private_store_accessed is False
        and value.credentials_accessed is False
        and value.external_network_used is False
    )


def valid_changed_destination(
    value: object,
    before: SqliteSnapshot,
) -> bool:
    """Validate the one-row post-analysis destination change."""
    return (
        type(value) is SqliteSnapshot
        and type(value.schema_version) is int
        and value.schema_version == 1
        and value.present is True
        and _identity(value.identity)
        and value.identity == before.identity
        and _identity(value.parent_identity)
        and value.parent_identity == before.parent_identity
        and type(value.size_bytes) is int
        and value.size_bytes > 0
        and _digest(value.sha256)
        and value.canonical is True
        and value.has_reparse_component is False
        and type(value.sidecars) is tuple
        and all(type(sidecar) is str for sidecar in value.sidecars)
        and value.sidecars == ()
        and value.integrity_ok is True
        and value.schema_complete is True
        and value.query_only is True
        and value.sha256 != before.sha256
        and type(value.aggregate_count) is int
    )


def _valid_start_strings(value: ServiceStartEvidence) -> bool:
    identities = (
        value.service_identity,
        value.runtime_identity,
        value.venv_identity,
        value.executable_identity,
        value.database_identity,
        value.attachment_temp_identity,
        value.log_identity,
        value.pid_identity,
        value.config_identity,
    )
    return (
        all(_identity(item) for item in identities)
        and type(value.llm_provider) is str
        and type(value.text_fallback_provider) is str
        and type(value.loopback_host) is str
    )


def _start_echoes(
    value: ServiceStartEvidence,
    request: ServiceStartRequest,
) -> bool:
    return (
        value.activation_token == request.activation_token
        and value.runtime_identity == request.runtime_identity
        and value.venv_identity == request.venv_identity
        and value.executable_identity == request.executable_identity
        and value.database_identity == request.database_identity
        and value.attachment_temp_identity
        == request.attachment_temp_identity
        and value.log_identity == request.log_identity
        and value.pid_identity == request.pid_identity
        and value.config_identity == request.config_identity
    )


def _identity(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and value.strip() == value
    )


def _digest(value: object) -> bool:
    return type(value) is str and _SHA256.fullmatch(value) is not None
