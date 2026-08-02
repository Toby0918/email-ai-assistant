"""Shared, verification-only R2 operator authorization ingress."""

from .envelope import (
    AuthorizationEnvelopeDomain,
    AuthorizationEnvelopeError,
    AuthorizationEnvelopeReplay,
    authorization_envelope_message,
    decode_authorization_envelope_context,
    verify_authorization_envelope,
)
from .dormant_context import DormantProfileBindingV1
from .production_v2 import (
    ProductionAuthorityEnvelopeError,
    production_authority_message_v2,
    verify_production_authority_v2,
)

__all__ = [
    "AuthorizationEnvelopeDomain",
    "AuthorizationEnvelopeError",
    "AuthorizationEnvelopeReplay",
    "authorization_envelope_message",
    "decode_authorization_envelope_context",
    "verify_authorization_envelope",
    "DormantProfileBindingV1",
    "ProductionAuthorityEnvelopeError",
    "production_authority_message_v2",
    "verify_production_authority_v2",
]
