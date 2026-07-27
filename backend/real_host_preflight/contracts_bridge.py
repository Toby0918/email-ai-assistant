"""Exact Issue #51 contract bridge for the read-only composition."""

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverProfileV1,
    RealPreflightAuthorizationV1,
    ReceiptEnvelopeV1,
    TestSandboxAuthorizationV1,
    default_operator_entry,
    validate_real_host_authorization,
)

__all__ = [
    "AuthorizationValidationStatus",
    "CutoverProfileV1",
    "RealPreflightAuthorizationV1",
    "ReceiptEnvelopeV1",
    "TestSandboxAuthorizationV1",
    "default_operator_entry",
    "validate_real_host_authorization",
]
