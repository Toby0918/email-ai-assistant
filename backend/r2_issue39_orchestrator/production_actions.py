"""Sole fixed binding from the Issue #39 catalog to Windows host actions."""

from __future__ import annotations

from .action_catalog import Issue39ProductionActionCatalogV1
from .action_runner import _Issue39ActionRunnerPortsV1
from .closure_binding import _Issue39ClosureBindingV1
from .preparation import Issue39PrepareStatusV1, Issue39PreparedExecutionV1
from .production_confirmation import FixedIssue39ActionConfirmerV1
from .production_evidence import Issue39EvidencePackageV1
from .production_host import FixedIssue39WindowsHostV1
from .production_preflight import Issue39PreflightReceiptV1


def bind_fixed_windows_action_ports_v1(
    *, prepared, closure, catalog, package, journal, preflight
):
    if (
        type(prepared) is not Issue39PreparedExecutionV1
        or prepared.status is not Issue39PrepareStatusV1.VERIFIED
        or type(closure) is not _Issue39ClosureBindingV1
        or type(catalog) is not Issue39ProductionActionCatalogV1
        or type(package) is not Issue39EvidencePackageV1
        or type(preflight) is not Issue39PreflightReceiptV1
        or journal.binding_fingerprint
        != closure.production.binding_fingerprint
    ):
        raise TypeError("R2_ISSUE39_PRODUCTION_ACTIONS_INVALID")
    confirmer = FixedIssue39ActionConfirmerV1.create(
        closure=closure, catalog=catalog
    )
    host = FixedIssue39WindowsHostV1.create(
        prepared=prepared,
        closure=closure,
        catalog=catalog,
        package=package,
        preflight=preflight,
    )
    return _Issue39ActionRunnerPortsV1(
        confirmer.confirm,
        host.observe,
        host.apply,
        host.reverify,
        host.recovery_inspect,
        confirmer.clock,
        confirmer.confirm_terminal,
        host.terminal_audit,
        host.legacy_audit,
        host.partial,
        host.evidence,
    )
