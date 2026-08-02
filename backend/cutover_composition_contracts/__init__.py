"""Content-free contracts shared by the three operator roots."""

from .binding import (
    CompositionBindingV1,
    OperatorEntryResult,
    OperatorEntryStatus,
)
from .authorization_sequence import AuthorizationSequenceV1
from .approved_binding import ApprovedCutoverBindingV1
from .canonical import UNBOUND_FINGERPRINT
from .chain import ProjectContainerReceiptChainV1, ReceiptChainState
from .errors import CompositionContractError
from .receipts import CompositionStage, CompositionStageReceiptV1
from .r2_receipt import R2CutoverReceiptV1
from .r2_types import (
    AuthorizationDomain,
    FinalCutoverOutcome,
    JournalFactKind,
    ManagedPublicationUnit,
    PendingEffectState,
    R2JournalBoundary,
    TwoStartLifecycleState,
    authorization_domain_for_phase,
    managed_publication_boundaries,
)

__all__ = [
    "AuthorizationSequenceV1",
    "ApprovedCutoverBindingV1",
    "AuthorizationDomain",
    "CompositionBindingV1",
    "CompositionContractError",
    "CompositionStage",
    "CompositionStageReceiptV1",
    "FinalCutoverOutcome",
    "JournalFactKind",
    "ManagedPublicationUnit",
    "OperatorEntryResult",
    "OperatorEntryStatus",
    "ProjectContainerReceiptChainV1",
    "PendingEffectState",
    "R2CutoverReceiptV1",
    "R2JournalBoundary",
    "ReceiptChainState",
    "UNBOUND_FINGERPRINT",
    "TwoStartLifecycleState",
    "authorization_domain_for_phase",
    "managed_publication_boundaries",
]
