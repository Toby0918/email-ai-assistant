"""Shared, verification-only R2 operator authorization ingress."""

from .envelope import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeError,
    AuthorizationEnvelopeReplay,
    authorization_envelope_message,
    decode_authorization_envelope_context,
    verify_authorization_envelope,
)

__all__ = [
    "AuthorizationEnvelopeDomain",
    "AuthorizationEnvelopeError",
    "AuthorizationEnvelopeReplay",
    "authorization_envelope_message",
    "decode_authorization_envelope_context",
    "verify_authorization_envelope",
]
