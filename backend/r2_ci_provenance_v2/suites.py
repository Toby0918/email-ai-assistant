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
        _r2("full_topology_windows"),
    ),
    CiProvenanceKindV2.WINDOWS_INDEPENDENT: (
        _r2("preflight_process"),
        _r2("evidence_process"),
        _r2("transaction_process"),
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
