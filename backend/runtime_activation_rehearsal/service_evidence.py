"""Content-free provider-disabled service activation evidence."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True, repr=False)
class ServiceStartRequest:
    """Code-fixed Managed resources and disabled provider state."""

    schema_version: int
    activation_token: str
    service_identity: str
    runtime_identity: str
    venv_identity: str
    executable_identity: str
    database_identity: str
    attachment_temp_identity: str
    log_identity: str
    pid_identity: str
    config_identity: str
    llm_provider: str
    text_fallback_provider: str
    provider_keys_present: bool
    private_knowledge_enabled: bool
    loopback_host: str


@dataclass(frozen=True, slots=True, repr=False)
class ServiceStartEvidence:
    """Lifecycle-manager observation of the synthetic service."""

    schema_version: int
    started: bool
    activation_token: str
    service_identity: str
    runtime_identity: str
    venv_identity: str
    executable_identity: str
    database_identity: str
    attachment_temp_identity: str
    log_identity: str
    pid_identity: str
    config_identity: str
    llm_provider: str
    text_fallback_provider: str
    provider_keys_present: bool
    private_knowledge_enabled: bool
    provider_client_created: bool
    external_network_used: bool
    loopback_host: str


@dataclass(frozen=True, slots=True, repr=False)
class HealthProbeRequest:
    """Bound literal-loopback health request."""

    activation_token: str
    service_identity: str
    loopback_host: str


@dataclass(frozen=True, slots=True, repr=False)
class HealthProbeEvidence:
    """Independent loopback health and provider-state observation."""

    schema_version: int
    activation_token: str
    service_identity: str
    loopback_host: str
    healthy: bool
    loopback_only: bool
    llm_provider: str
    text_fallback_provider: str
    provider_calls: int
    external_network_used: bool


@dataclass(frozen=True, slots=True, repr=False)
class AnalysisProbeRequest:
    """One fixed synthetic user-click analysis request."""

    activation_token: str
    service_identity: str
    database_identity: str
    user_confirmed: bool
    synthetic: bool


@dataclass(frozen=True, slots=True, repr=False)
class AnalysisProbeEvidence:
    """Aggregate proof of one persisted rule-fallback analysis."""

    schema_version: int
    activation_token: str
    service_identity: str
    database_identity: str
    user_confirmed: bool
    synthetic: bool
    analysis_calls: int
    route: str
    saved_id: int
    persisted: bool
    primary_provider_calls: int
    fallback_provider_calls: int
    mailbox_accessed: bool
    vault_accessed: bool
    private_store_accessed: bool
    credentials_accessed: bool
    external_network_used: bool
