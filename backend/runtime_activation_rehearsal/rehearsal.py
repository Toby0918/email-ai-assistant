"""Public composition seam for the synthetic activation rehearsal."""

from __future__ import annotations

from .adapters import (
    ManagedActivationAdapters,
    ManagedLayoutEvidence,
    RuntimeBuildEvidence,
    RuntimeBuildRequest,
    has_exact_adapter_bundle,
)
from .artifact_checks import rehearse_artifact_publication
from .contract import (
    COMPLETED_RESULT,
    FAILED_RESULT,
    ManagedActivationResult,
)
from .database_checks import (
    DatabaseActivationState,
    rehearse_database_publication,
)
from .filesystem_checks import stable_layout, valid_layout
from .lifecycle_checks import (
    pre_publication_stop_request,
    stopped_service_gate,
)
from .policy import (
    LOCKED_DEPENDENCIES,
    LOCK_SHA256,
    PINNED_PYTHON_VERSION,
    PINNED_SQLITE_VERSION,
)
from .runtime_checks import stable_runtime, valid_runtime_build
from .service_checks import rehearse_service_activation


def rehearse_managed_runtime_activation(
    *,
    adapters: ManagedActivationAdapters,
) -> ManagedActivationResult:
    """Run the injected synthetic rehearsal with fixed failure output."""
    if not has_exact_adapter_bundle(adapters):
        return FAILED_RESULT
    try:
        return _execute_rehearsal(adapters)
    except Exception:
        return FAILED_RESULT


def _execute_rehearsal(
    adapters: ManagedActivationAdapters,
) -> ManagedActivationResult:
    runtime_phase = _rehearse_runtime(adapters)
    if runtime_phase is None:
        return FAILED_RESULT
    layout, runtime = runtime_phase
    database = _rehearse_stopped_database(adapters, layout)
    if database is None:
        return FAILED_RESULT
    if not rehearse_artifact_publication(
        filesystem=adapters.filesystem,
        probe=adapters.probe,
        layout=layout,
    ):
        return FAILED_RESULT
    if not rehearse_service_activation(
        adapters=adapters,
        layout=layout,
        runtime=runtime,
        database=database,
    ):
        return FAILED_RESULT
    return COMPLETED_RESULT


def _rehearse_runtime(
    adapters: ManagedActivationAdapters,
) -> tuple[ManagedLayoutEvidence, RuntimeBuildEvidence] | None:
    request = RuntimeBuildRequest(
        python_version=PINNED_PYTHON_VERSION,
        sqlite_version=PINNED_SQLITE_VERSION,
        locked_dependencies=LOCKED_DEPENDENCIES,
        lock_sha256=LOCK_SHA256,
    )
    first_layout = adapters.filesystem.observe_layout()
    if not valid_layout(first_layout):
        return None
    build = adapters.runtime.activate(request)
    if not valid_runtime_build(build, first_layout):
        return None
    probe = adapters.probe.observe_runtime()
    observed = adapters.runtime.observe()
    if not stable_runtime(build, observed, probe, first_layout):
        return None
    second_layout = adapters.filesystem.observe_layout()
    if not stable_layout(first_layout, second_layout):
        return None
    return second_layout, build


def _rehearse_stopped_database(
    adapters: ManagedActivationAdapters,
    layout: ManagedLayoutEvidence,
) -> DatabaseActivationState | None:
    request = pre_publication_stop_request()
    lifecycle_stop = adapters.lifecycle.stop(request)
    stopped_probe = adapters.probe.prove_stopped(request)
    gate = stopped_service_gate(
        lifecycle_stop,
        stopped_probe,
        request,
    )
    if gate is None:
        return None
    return rehearse_database_publication(
        adapter=adapters.database,
        layout=layout,
        gate=gate,
    )
