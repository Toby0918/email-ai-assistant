"""Content-free R2 verification bundle and fingerprint package."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from backend.cutover_composition_contracts.canonical import is_fingerprint

from .matrix import semantic_gap_matrix


_BUNDLE_FIELDS = {
    "schema_version",
    "windows_ntfs",
    "process_type_count",
    "authorization_domain_count",
    "real_tty_channel_count",
    "independent_audit_process_count",
    "project_container_zone_count",
    "repository_count",
    "worktree_count",
    "managed_unit_count",
    "semantic_gap_case_count",
    "rule_fallback_result_count",
    "persisted_row_count",
    "provider_attempt_count",
    "public_leakage_count",
    "real_host_operation_count",
    "terminal_status",
}


@dataclass(frozen=True, slots=True, repr=False, init=False)
class R2VerificationBundleV1:
    values: tuple[tuple[str, object], ...]
    bundle_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2VerificationBundleV1 requires create()")

    @classmethod
    def create(cls, mapping: object):
        if not _valid_bundle(mapping):
            raise ValueError("R2_VERIFICATION_BUNDLE_INVALID")
        canonical = tuple(sorted(mapping.items()))
        value = object.__new__(cls)
        object.__setattr__(value, "values", canonical)
        object.__setattr__(
            value,
            "bundle_fingerprint",
            _fingerprint("r2-verification-bundle-v1", dict(canonical)),
        )
        return value

    def to_mapping(self) -> dict[str, object]:
        return dict(self.values)


@dataclass(frozen=True, slots=True)
class R2VerificationEvidenceV1:
    criteria_fingerprint: str
    matrix_fingerprint: str
    script_fingerprint: str
    bundle_fingerprint: str
    r2_surface_fingerprint: str
    package_fingerprint: str


def build_verification_evidence(
    *, criteria_bytes, script_bytes, bundle, r2_surface_fingerprint
):
    if (
        type(criteria_bytes) is not bytes
        or not criteria_bytes
        or type(script_bytes) is not bytes
        or not script_bytes
        or type(bundle) is not R2VerificationBundleV1
        or not is_fingerprint(r2_surface_fingerprint)
    ):
        raise ValueError("R2_VERIFICATION_EVIDENCE_INVALID")
    values = {
        "criteria_fingerprint": _bytes_fingerprint(
            "r2-verification-criteria-v1", criteria_bytes
        ),
        "matrix_fingerprint": _fingerprint(
            "r2-verification-matrix-v1",
            [
                {
                    "semantic": item.semantic,
                    "direction": item.direction,
                    "gap": item.gap,
                }
                for item in semantic_gap_matrix()
            ],
        ),
        "script_fingerprint": _bytes_fingerprint(
            "r2-verification-script-v1", script_bytes
        ),
        "bundle_fingerprint": bundle.bundle_fingerprint,
        "r2_surface_fingerprint": r2_surface_fingerprint,
    }
    return R2VerificationEvidenceV1(
        **values,
        package_fingerprint=_fingerprint(
            "r2-verification-package-v1", values
        ),
    )


def _valid_bundle(value) -> bool:
    if type(value) is not dict or set(value) != _BUNDLE_FIELDS:
        return False
    expected = {
        "schema_version": 1,
        "windows_ntfs": True,
        "process_type_count": 3,
        "authorization_domain_count": 4,
        "real_tty_channel_count": 3,
        "independent_audit_process_count": 2,
        "project_container_zone_count": 9,
        "repository_count": 1,
        "worktree_count": 11,
        "managed_unit_count": 4,
        "semantic_gap_case_count": 70,
        "rule_fallback_result_count": 1,
        "persisted_row_count": 1,
        "provider_attempt_count": 0,
        "public_leakage_count": 0,
        "real_host_operation_count": 0,
        "terminal_status": "CUTOVER_SUCCESS",
    }
    return value == expected


def _fingerprint(domain: str, value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return _bytes_fingerprint(domain, payload)


def _bytes_fingerprint(domain: str, payload: bytes) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()
