"""Pure stopped-service gate validation."""

from __future__ import annotations

from .adapters import (
    LifecycleStopRequest,
    LifecycleStopEvidence,
    StoppedProbeEvidence,
    StoppedServiceGate,
)

PRE_PUBLICATION_PHASE = "pre_publication"
POST_ACTIVATION_PHASE = "post_activation"
PRE_ACTIVATION_TOKEN = "activation-not-started"


def pre_publication_stop_request() -> LifecycleStopRequest:
    """Return the fixed request for the pre-copy stopped proof."""
    return LifecycleStopRequest(
        schema_version=1,
        phase=PRE_PUBLICATION_PHASE,
        activation_token=PRE_ACTIVATION_TOKEN,
    )


def stopped_service_gate(
    lifecycle: object,
    probe: object,
    request: LifecycleStopRequest,
) -> StoppedServiceGate | None:
    """Bind lifecycle and independent stopped observations."""
    if (
        not _valid_request(request)
        or not _valid_stopped(lifecycle, LifecycleStopEvidence)
        or not _valid_stopped(probe, StoppedProbeEvidence)
    ):
        return None
    if (
        lifecycle.service_identity != probe.service_identity
        or lifecycle.stop_token != probe.stop_token
        or lifecycle.phase != request.phase
        or probe.phase != request.phase
        or lifecycle.activation_token != request.activation_token
        or probe.activation_token != request.activation_token
    ):
        return None
    return StoppedServiceGate(
        service_identity=lifecycle.service_identity,
        stop_token=lifecycle.stop_token,
        phase=lifecycle.phase,
        activation_token=lifecycle.activation_token,
    )


def _valid_stopped(value: object, evidence_type: type[object]) -> bool:
    return (
        type(value) is evidence_type
        and type(value.schema_version) is int
        and value.schema_version == 1
        and _identity(value.service_identity)
        and _identity(value.stop_token)
        and _phase(value.phase)
        and _identity(value.activation_token)
        and value.service_identity != value.stop_token
        and value.stopped is True
        and value.process_present is False
        and value.health_reachable is False
        and value.pid_present is False
    )


def _valid_request(value: object) -> bool:
    return (
        type(value) is LifecycleStopRequest
        and type(value.schema_version) is int
        and value.schema_version == 1
        and _phase(value.phase)
        and _identity(value.activation_token)
        and (
            (
                value.phase == PRE_PUBLICATION_PHASE
                and value.activation_token == PRE_ACTIVATION_TOKEN
            )
            or (
                value.phase == POST_ACTIVATION_PHASE
                and value.activation_token != PRE_ACTIVATION_TOKEN
            )
        )
    )


def _phase(value: object) -> bool:
    return (
        type(value) is str
        and value in {PRE_PUBLICATION_PHASE, POST_ACTIVATION_PHASE}
    )


def _identity(value: object) -> bool:
    return (
        type(value) is str
        and 1 <= len(value) <= 128
        and value.strip() == value
    )
