"""Sole-maintainer production binding and dormant confirmation contracts."""

from ._adapter_identity import production_adapter_fingerprint_v1
from .binding import ApprovedCutoverBindingV3, production_action_fingerprint_v2
from .claim import validate_new_execution_confirmation_claim
from .errors import ExecutionConfirmationError, ProductionBindingError
from .execution_confirmation import (
    ExecutionConfirmationCandidateV1,
    ExecutionConfirmationClaimV1,
    confirm_execution_confirmation_v1,
    prepare_execution_confirmation_v1,
)
from .review import (
    production_composition_evidence_fingerprint_v3,
    require_reviewed_production_binding_v3,
)
from .vocabulary import (
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    authority_domain_for_command_v2,
)


__all__ = [
    "ApprovedCutoverBindingV3",
    "AuthorityDomainV2",
    "ExecutionConfirmationCandidateV1",
    "ExecutionConfirmationClaimV1",
    "ExecutionConfirmationError",
    "OperatorRoleV2",
    "ProductionBindingError",
    "ProductionCommandV2",
    "ProductionRoleV2",
    "authority_domain_for_command_v2",
    "confirm_execution_confirmation_v1",
    "prepare_execution_confirmation_v1",
    "production_action_fingerprint_v2",
    "production_adapter_fingerprint_v1",
    "production_composition_evidence_fingerprint_v3",
    "require_reviewed_production_binding_v3",
    "validate_new_execution_confirmation_claim",
]
