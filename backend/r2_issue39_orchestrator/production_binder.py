"""Sole fixed composition root for the Issue #39 production action graph."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV3

from .action_catalog import (
    Issue39ProductionActionCatalogV1,
    build_fixed_production_action_catalog_v1,
)
from .action_runner import (
    Issue39ActionRunResultV1,
    Issue39ActionRunStatusV1,
    _Issue39ActionRunnerPortsV1,
    _run_issue39_action_catalog_v1,
)
from .closure_binding import _Issue39ClosureBindingV1
from .preparation import (
    Issue39PrepareStatusV1,
    Issue39PreparedExecutionV1,
    reverify_fixed_issue39_execution_v1,
)


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39ProductionBinderPortsV1:
    reverify: object = field(repr=False)
    load_closure: object = field(repr=False)
    build_catalog: object = field(repr=False)
    run_preflight: object = field(repr=False)
    prepare_evidence: object = field(repr=False)
    bootstrap: object = field(repr=False)
    anchor: object = field(repr=False)
    bind_actions: object = field(repr=False)
    run_actions: object = field(repr=False)


def bind_and_run_fixed_issue39_execution_v1(prepared):
    """Bind every capability internally and run no caller-selected target."""

    return _bind_and_run_issue39_execution_v1(
        prepared=prepared, ports=_production_ports()
    )


def resume_fixed_issue39_anchor_v1():
    """Resume only the self-verifying active external evidence anchor."""

    from .anchor_context import load_current_anchor_context_v1
    from .production_actions import bind_fixed_windows_action_ports_v1
    from .production_bootstrap import bootstrap_fixed_issue39_journal_v1

    context = load_current_anchor_context_v1()
    location, journal = bootstrap_fixed_issue39_journal_v1(
        closure=context.closure, package=context.package
    )
    actions = bind_fixed_windows_action_ports_v1(
        prepared=context.prepared,
        closure=context.closure,
        catalog=context.catalog,
        package=context.package,
        journal=journal,
        preflight=context.preflight,
    )
    return _run_issue39_action_catalog_v1(
        catalog=context.catalog,
        binding=context.closure.production,
        location=location,
        ports=actions,
    )


def _bind_and_run_issue39_execution_v1(*, prepared, ports):
    _require_inputs(prepared, ports)
    verified = ports.reverify(prepared)
    if (
        type(verified) is not Issue39PreparedExecutionV1
        or verified.status is not Issue39PrepareStatusV1.VERIFIED
    ):
        raise TypeError("R2_ISSUE39_PRODUCTION_BINDING_DRIFT")
    closure = ports.load_closure()
    _require_closure(verified, closure)
    catalog = ports.build_catalog(verified)
    if type(catalog) is not Issue39ProductionActionCatalogV1:
        raise TypeError("R2_ISSUE39_PRODUCTION_CATALOG_INVALID")
    preflight = ports.run_preflight(
        verified, closure, catalog, None, "before_evidence"
    )
    package = ports.prepare_evidence(
        verified, catalog, closure, preflight
    )
    location, journal = ports.bootstrap(
        closure=closure, package=package
    )
    preflight = ports.run_preflight(
        verified, closure, catalog, package, "after_evidence", preflight
    )
    ports.anchor(package)
    actions = ports.bind_actions(
        prepared=verified,
        closure=closure,
        catalog=catalog,
        package=package,
        journal=journal,
        preflight=preflight,
    )
    if type(actions) is not _Issue39ActionRunnerPortsV1:
        raise TypeError("R2_ISSUE39_PRODUCTION_ACTIONS_INVALID")
    result = ports.run_actions(
        catalog=catalog,
        binding=closure.production,
        location=location,
        ports=actions,
    )
    if type(result) is not Issue39ActionRunResultV1:
        raise TypeError("R2_ISSUE39_PRODUCTION_EXECUTION_INCOMPLETE")
    return result


def _production_ports():
    from .closure_binding import load_fixed_issue39_closure_binding_v1
    from .production_actions import bind_fixed_windows_action_ports_v1
    from .production_bootstrap import bootstrap_fixed_issue39_journal_v1
    from .production_evidence import prepare_fixed_issue39_evidence_v1
    from .production_preflight import run_fixed_issue39_preflight_v1
    from .restart_anchor import ensure_fixed_issue39_restart_anchor_v1

    return _Issue39ProductionBinderPortsV1(
        reverify_fixed_issue39_execution_v1,
        load_fixed_issue39_closure_binding_v1,
        build_fixed_production_action_catalog_v1,
        run_fixed_issue39_preflight_v1,
        prepare_fixed_issue39_evidence_v1,
        bootstrap_fixed_issue39_journal_v1,
        ensure_fixed_issue39_restart_anchor_v1,
        bind_fixed_windows_action_ports_v1,
        _run_issue39_action_catalog_v1,
    )


def _require_closure(prepared, closure):
    if (
        type(closure) is not _Issue39ClosureBindingV1
        or type(closure.production) is not ApprovedCutoverBindingV3
    ):
        raise TypeError("R2_ISSUE39_PRODUCTION_BINDING_INVALID")
    expected = hashlib.sha256(
        b"r2-issue39-closure-readiness-v1\0"
        + bytes.fromhex(closure.manifest.manifest_fingerprint)
        + bytes.fromhex(closure.receipt.receipt_fingerprint)
    ).hexdigest()
    if prepared._closure.closure_fingerprint != expected:
        raise TypeError("R2_ISSUE39_PRODUCTION_BINDING_DRIFT")


def _require_inputs(prepared, ports):
    names = (
        "reverify", "load_closure", "build_catalog", "run_preflight",
        "prepare_evidence", "bootstrap", "anchor", "bind_actions",
        "run_actions",
    )
    if (
        type(prepared) is not Issue39PreparedExecutionV1
        or type(ports) is not _Issue39ProductionBinderPortsV1
        or any(not callable(getattr(ports, name)) for name in names)
    ):
        raise TypeError("R2_ISSUE39_PRODUCTION_BINDING_INVALID")
