"""Generated final R2 operator runbook semantics and verification."""

from backend.r2_production_binding.catalog import (
    OperatorCommandEffectV2,
    OperatorSurfaceV2,
    R2OperatorCommandV2,
    command_catalog_v2,
    executable_verb_map_v2,
    resolve_operator_command_v2,
)

from .errors import OperatorRunbookError
from .receipt import R2OperatorRunbookReceiptV2, RunbookVerificationStatusV2
from .render import render_r2_operator_runbook_v2, runbook_document_fingerprint_v2
from .state_machine import (
    OperatorPhaseV2,
    R2OperatorPhaseRuleV2,
    operator_package_semantics_fingerprint_v2,
    operator_state_machine_v2,
)
from .review_registry import (
    blocker_resolution_fingerprint_v2,
    decision_registry_fingerprint_v2,
    issue38_decision_registry_v2,
    r1_blocker_resolution_registry_v2,
)

__all__ = [
    "OperatorCommandEffectV2", "OperatorPhaseV2", "OperatorSurfaceV2",
    "R2OperatorCommandV2", "R2OperatorPhaseRuleV2",
    "R2OperatorRunbookReceiptV2", "RunbookVerificationStatusV2",
    "OperatorRunbookError", "command_catalog_v2", "executable_verb_map_v2",
    "operator_package_semantics_fingerprint_v2", "operator_state_machine_v2",
    "render_r2_operator_runbook_v2", "resolve_operator_command_v2",
    "runbook_document_fingerprint_v2",
    "blocker_resolution_fingerprint_v2",
    "decision_registry_fingerprint_v2",
    "issue38_decision_registry_v2",
    "r1_blocker_resolution_registry_v2",
]
