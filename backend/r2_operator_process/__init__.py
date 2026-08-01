"""Shared, verification-only R2 operator authorization ingress."""

from .envelope import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeError,
    AuthorizationEnvelopeReplay,
    authorization_envelope_message,
    verify_authorization_envelope,
)

__all__ = [
    "AuthorizationEnvelopeDomain",
    "AuthorizationEnvelopeError",
    "AuthorizationEnvelopeReplay",
    "authorization_envelope_message",
    "verify_authorization_envelope",
]
