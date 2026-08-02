"""Closed CI suite registry; portable claims never include native tests."""

from __future__ import annotations

from enum import Enum

from ._canonical import fingerprint
from .errors import R2CiProvenanceError


class CiProvenanceKindV2(str, Enum):
    PORTABLE = "portable"
    WINDOWS_NATIVE = "windows_native"
    WINDOWS_INDEPENDENT = "windows_independent"


_SUITES = {
    CiProvenanceKindV2.PORTABLE: (
        "tests.test_r2_final_master_closure_contracts",
        "tests.test_r2_git_byte_state_v2",
        "tests.test_r2_main_publication_contracts",
        "tests.test_r2_repository_manifest_contracts",
        "tests.test_r2_runtime_publication_contracts",
        "tests.test_r2_database_publication_contracts",
        "tests.test_r2_crx_publication_contracts",
        "tests.test_r2_config_publication_contracts",
        "tests.test_r2_validation_lifecycle",
        "tests.test_r2_rollback_recovery_v2",
        "tests.test_r2_rollback_recovery_v2_crash_matrix",
        "tests.test_r2_retention_ledger_v2",
        "tests.test_r2_operator_runbook_v2",
        "tests.test_r2_ci_provenance_v2",
    ),
    CiProvenanceKindV2.WINDOWS_NATIVE: (
        "tests.test_r2_main_publication_windows",
        "tests.test_r2_repository_manifest_windows",
        "tests.test_r2_runtime_publication_windows",
        "tests.test_r2_database_publication_windows",
        "tests.test_r2_crx_publication_windows",
        "tests.test_r2_config_publication_windows",
        "tests.test_r2_validation_lifecycle_windows",
        "tests.test_r2_full_topology_windows",
    ),
    CiProvenanceKindV2.WINDOWS_INDEPENDENT: (
        "tests.test_r2_preflight_process",
        "tests.test_r2_evidence_process",
        "tests.test_r2_transaction_process",
    ),
}


def fixed_suite_v2(kind):
    if type(kind) is not CiProvenanceKindV2:
        raise R2CiProvenanceError()
    return _SUITES[kind]


def fixed_suite_fingerprint_v2(kind):
    return fingerprint("r2-fixed-ci-suite-v2", {
        "kind": kind.value,
        "modules": list(fixed_suite_v2(kind)),
        "required_skip_count": 0,
    })
