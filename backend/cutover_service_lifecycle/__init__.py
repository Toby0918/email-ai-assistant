"""Synthetic provider-disabled activation and legacy recovery contracts."""

from .activation_contracts import (
    NewServiceActivationReceiptV1,
    NewServiceStartRequestV1,
    SyntheticActivationEvidenceV1,
    SyntheticActivationRequestV1,
    SyntheticRowEvidenceV1,
)
from .adapters import (
    LegacyServiceAdapter,
    NewServiceAdapter,
    ProviderDisabledServiceAdapters,
)
from .contracts import (
    LegacyRecoveryConfigV1,
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
    ServiceStopEvidenceV1,
)
from .controller import ProviderDisabledServiceController
from .errors import ServiceLifecycleError
from .failures import ActivationFailureKind, ServiceBoundaryFailure
from .lifecycle import (
    LifecycleResultV1,
    LifecycleStatus,
    ProviderDisabledLifecycleTransaction,
)
from .rollback_adapters import JournalDrivenRollbackAdapter
from .rollback_contracts import (
    FailedContainerPublicationReceiptV1,
    LegacyPrerequisiteEvidenceV1,
    RollbackRestoreEvidenceV1,
    RollbackStage,
    RollbackStageEvidenceV1,
)
from .real_lock import (
    LifecycleConstructorResult,
    LifecycleConstructorStatus,
    locked_real_service_lifecycle_constructor,
)

__all__ = [
    "ActivationFailureKind",
    "FailedContainerPublicationReceiptV1",
    "JournalDrivenRollbackAdapter",
    "LegacyRecoveryConfigV1",
    "LegacyPrerequisiteEvidenceV1",
    "LegacyServiceAdapter",
    "LifecycleResultV1",
    "LifecycleStatus",
    "LifecycleConstructorResult",
    "LifecycleConstructorStatus",
    "NewServiceActivationReceiptV1",
    "NewServiceAdapter",
    "NewServiceStartRequestV1",
    "ProviderDisabledServiceAdapters",
    "ProviderDisabledServiceController",
    "ProviderDisabledLifecycleTransaction",
    "RollbackRestoreEvidenceV1",
    "RollbackStage",
    "RollbackStageEvidenceV1",
    "ServiceBoundaryFailure",
    "ServiceHealthEvidenceV1",
    "ServiceLifecycleError",
    "ServiceRole",
    "ServiceStartEvidenceV1",
    "ServiceStopEvidenceV1",
    "SyntheticActivationEvidenceV1",
    "SyntheticActivationRequestV1",
    "SyntheticRowEvidenceV1",
    "locked_real_service_lifecycle_constructor",
]
