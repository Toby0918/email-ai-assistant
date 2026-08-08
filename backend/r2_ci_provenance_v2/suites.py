"""Closed CI suite registry; portable claims never include native tests."""

from __future__ import annotations

from enum import Enum

from ._canonical import fingerprint
from .errors import R2CiProvenanceError


class CiProvenanceKindV2(str, Enum):
    PORTABLE = "portable"
    WINDOWS_NATIVE = "windows_native"
    WINDOWS_INDEPENDENT = "windows_independent"


def _r2(name):
    return "tests.test_" + "r2_" + name


def _full_topology(method):
    return (
        _r2("full_topology_windows")
        + ".R2FullTopologyWindowsTests."
        + method
    )


_SUITES = {
    CiProvenanceKindV2.PORTABLE: ("discover:tests:portable-full-suite",),
    CiProvenanceKindV2.WINDOWS_NATIVE: (
        _r2("main_publication_windows"),
        _r2("repository_manifest_windows"),
        _r2("runtime_publication_windows"),
        _r2("database_publication_windows"),
        _r2("crx_publication_windows"),
        _r2("config_publication_windows"),
        _r2("validation_lifecycle_windows"),
        _full_topology(
            "test_all_ten_fixed_verbs_ignore_terminal_environment_and_artifacts"
        ),
        _full_topology("test_poison_bootstrap_workers_remain_dormant"),
        (
            "tests.test_r2_ci_provenance_v2_adapter."
            "R2CiProvenanceWindowsNativeAdapterTests."
            "test_ci_budgeted_script_proves_complete_topology_without_public_leakage"
        ),
        _full_topology("test_portable_contract_makes_no_windows_process_claim"),
        _full_topology(
            "test_surface_closure_uses_new_dormant_roots_not_removed_ingress"
        ),
    ),
    CiProvenanceKindV2.WINDOWS_INDEPENDENT: (
        _r2("preflight_production_v2"),
        _r2("evidence_production_v2"),
        _r2("transaction_production_v2"),
        _r2("execution_confirmation"),
        "tests.test_close_r2_final_master",
    ),
}

_PORTABLE_NATIVE_SKIP_REASONS = (
    "Windows integration only",
    "Windows sandbox evidence",
    "Windows sandbox required",
    "Windows Job Object test",
    "physical Windows claim",
    "Windows NTFS sandbox required",
    "Windows real TTY proof",
    "Windows NTFS/TTY/process proof",
    "Windows junction contract",
    "Windows sandbox evidence only; no Linux NTFS or ACL claim",
)


def fixed_suite_v2(kind):
    if type(kind) is not CiProvenanceKindV2:
        raise R2CiProvenanceError()
    return _SUITES[kind]


def fixed_suite_fingerprint_v2(kind):
    return fingerprint("r2-fixed-ci-suite-v2", {
        "kind": kind.value,
        "modules": list(fixed_suite_v2(kind)),
        "portable_native_skip_reasons": (
            list(_PORTABLE_NATIVE_SKIP_REASONS)
            if kind is CiProvenanceKindV2.PORTABLE else []
        ),
        "portable_full_suite": int(kind is CiProvenanceKindV2.PORTABLE),
        "required_skip_count": 0,
    })


def portable_native_skip_reason_registry_v2():
    return _PORTABLE_NATIVE_SKIP_REASONS
