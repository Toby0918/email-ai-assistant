"""Provider-disabled synthetic service activation validation."""

from __future__ import annotations

import hashlib
import uuid

from .adapters import (
    AnalysisProbeEvidence,
    AnalysisProbeRequest,
    HealthProbeRequest,
    LifecycleStopRequest,
    ManagedActivationAdapters,
    ManagedLayoutEvidence,
    RuntimeBuildEvidence,
    ServiceStartEvidence,
    ServiceStartRequest,
    SqliteSnapshot,
    StoppedServiceGate,
)
from .database_checks import DatabaseActivationState, valid_source
from .filesystem_checks import resource_identity, stable_layout
from .lifecycle_checks import (
    POST_ACTIVATION_PHASE,
    PRE_ACTIVATION_TOKEN,
    PRE_PUBLICATION_PHASE,
    stopped_service_gate,
)
from .policy import ManagedResourceRole
from .service_validation import (
    valid_analysis,
    valid_changed_destination,
    valid_health,
    valid_start,
)


def rehearse_service_activation(
    *,
    adapters: ManagedActivationAdapters,
    layout: ManagedLayoutEvidence,
    runtime: RuntimeBuildEvidence,
    database: DatabaseActivationState,
) -> bool:
    """Start, probe, analyze, stop and verify synthetic state."""
    request = _start_request(layout, runtime, database)
    start_invoked = False
    phase_ok = False
    start: ServiceStartEvidence | None = None
    analysis: AnalysisProbeEvidence | None = None
    try:
        start_invoked = True
        candidate = adapters.lifecycle.start(request)
        if valid_start(candidate, request):
            start = candidate
            analysis = _run_probes(adapters, start)
            phase_ok = analysis is not None
    except Exception:
        phase_ok = False
    if not start_invoked:
        return False
    final_gate = _final_stop(adapters, request.activation_token)
    if final_gate is None:
        return False
    if not _valid_final_gate_for_database(
        final_gate,
        database,
        request.activation_token,
    ):
        return False
    if start is None:
        _observe_source(adapters, database.source)
        return False
    if not _valid_final_gate(final_gate, start, database):
        return False
    if not phase_ok or analysis is None:
        _observe_source(adapters, database.source)
        return False
    return _valid_post_activation(
        adapters=adapters,
        layout=layout,
        database=database,
        analysis=analysis,
    )


def _start_request(
    layout: ManagedLayoutEvidence,
    runtime: RuntimeBuildEvidence,
    database: DatabaseActivationState,
) -> ServiceStartRequest:
    return ServiceStartRequest(
        schema_version=1,
        activation_token=_activation_token(database.stopped_gate),
        service_identity=database.stopped_gate.service_identity,
        runtime_identity=runtime.runtime_identity,
        venv_identity=runtime.venv_identity,
        executable_identity=runtime.executable_identity,
        database_identity=database.destination.identity,
        attachment_temp_identity=resource_identity(
            layout,
            ManagedResourceRole.ATTACHMENT_TEMP,
        ),
        log_identity=resource_identity(
            layout,
            ManagedResourceRole.SERVICE_LOG,
        ),
        pid_identity=resource_identity(
            layout,
            ManagedResourceRole.PID_STATE,
        ),
        config_identity=resource_identity(
            layout,
            ManagedResourceRole.NON_SECRET_CONFIG,
        ),
        llm_provider="disabled",
        text_fallback_provider="disabled",
        provider_keys_present=False,
        private_knowledge_enabled=False,
        loopback_host="127.0.0.1",
    )


def _run_probes(
    adapters: ManagedActivationAdapters,
    start: ServiceStartEvidence,
) -> AnalysisProbeEvidence | None:
    health_request = HealthProbeRequest(
        activation_token=start.activation_token,
        service_identity=start.service_identity,
        loopback_host="127.0.0.1",
    )
    health = adapters.probe.health(health_request)
    if not valid_health(health, health_request):
        return None
    analysis_request = AnalysisProbeRequest(
        activation_token=start.activation_token,
        service_identity=start.service_identity,
        database_identity=start.database_identity,
        user_confirmed=True,
        synthetic=True,
    )
    analysis = adapters.probe.analyze(analysis_request)
    if not valid_analysis(analysis, analysis_request):
        return None
    return analysis


def _final_stop(
    adapters: ManagedActivationAdapters,
    activation_token: str,
) -> object | None:
    try:
        request = LifecycleStopRequest(
            schema_version=1,
            phase=POST_ACTIVATION_PHASE,
            activation_token=activation_token,
        )
        lifecycle = adapters.lifecycle.stop(request)
        probe = adapters.probe.prove_stopped(request)
        return stopped_service_gate(lifecycle, probe, request)
    except Exception:
        return None


def _observe_source(
    adapters: ManagedActivationAdapters,
    source: SqliteSnapshot,
) -> bool:
    try:
        observed = adapters.database.observe_source()
        return valid_source(observed) and observed == source
    except Exception:
        return False


def _valid_post_activation(
    *,
    adapters: ManagedActivationAdapters,
    layout: ManagedLayoutEvidence,
    database: DatabaseActivationState,
    analysis: AnalysisProbeEvidence,
) -> bool:
    try:
        destination = adapters.database.observe_destination()
        source = adapters.database.observe_source()
        final_layout = adapters.filesystem.observe_layout()
    except Exception:
        return False
    return (
        valid_changed_destination(
            destination,
            database.destination,
        )
        and destination.aggregate_count
        == database.destination.aggregate_count + 1
        and analysis.saved_id > 0
        and valid_source(source)
        and source == database.source
        and stable_layout(layout, final_layout)
    )


def _valid_final_gate(
    final_gate: StoppedServiceGate,
    start: ServiceStartEvidence,
    database: DatabaseActivationState,
) -> bool:
    return (
        _valid_final_gate_for_database(
            final_gate,
            database,
            start.activation_token,
        )
        and final_gate.service_identity == start.service_identity
    )


def _valid_final_gate_for_database(
    final_gate: StoppedServiceGate,
    database: DatabaseActivationState,
    activation_token: str,
) -> bool:
    return (
        final_gate.service_identity
        == database.stopped_gate.service_identity
        and final_gate.phase == POST_ACTIVATION_PHASE
        and database.stopped_gate.phase == PRE_PUBLICATION_PHASE
        and final_gate.activation_token == activation_token
        and database.stopped_gate.activation_token
        == PRE_ACTIVATION_TOKEN
        and final_gate.stop_token != database.stopped_gate.stop_token
    )


def _activation_token(gate: StoppedServiceGate) -> str:
    payload = (
        "issue37-service-activation-v1\0"
        + gate.service_identity
        + "\0"
        + gate.stop_token
        + "\0"
        + uuid.uuid4().hex
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
