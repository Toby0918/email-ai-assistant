"""Unit-specific read-only recovery proof over a unified inspection."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV2
from backend.r2_transaction_journal_v2 import R2ReadOnlyInspectionReceiptV2
from backend.r2_transaction_journal_v2._canonical import fingerprint, is_fingerprint

from .errors import ManagedUnitPublicationError
from .plan import R2ManagedUnitTransitionV2


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ManagedRecoveryInspectionV2:
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    inspection: R2ReadOnlyInspectionReceiptV2 = field(repr=False)
    acl_conformance_fingerprint: str = field(repr=False)
    semantic_conformance_fingerprint: str = field(repr=False)
    acl_exact: bool
    semantic_exact: bool
    read_only: bool
    proof_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2ManagedRecoveryInspectionV2 requires create()")

    @classmethod
    def create(cls, *, binding, transition, inspection, acl_conformance_fingerprint, semantic_conformance_fingerprint, acl_exact, semantic_exact):
        try:
            if type(binding) is not ApprovedCutoverBindingV2 or type(transition) is not R2ManagedUnitTransitionV2 or type(inspection) is not R2ReadOnlyInspectionReceiptV2 or inspection.binding_fingerprint != binding.binding_fingerprint or inspection.transition_instance_fingerprint != transition.transition_instance_fingerprint or not is_fingerprint(acl_conformance_fingerprint) or not is_fingerprint(semantic_conformance_fingerprint) or acl_exact is not True or semantic_exact is not True:
                raise ManagedUnitPublicationError()
            body = {
                "binding_fingerprint": binding.binding_fingerprint,
                "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
                "transition_instance_fingerprint": transition.transition_instance_fingerprint,
                "inspection_fingerprint": inspection.receipt_fingerprint,
                "acl_conformance_fingerprint": acl_conformance_fingerprint,
                "semantic_conformance_fingerprint": semantic_conformance_fingerprint,
                "acl_exact": True, "semantic_exact": True, "read_only": True,
            }
            value = object.__new__(cls)
            for name, item in body.items():
                if name != "inspection_fingerprint":
                    object.__setattr__(value, name, item)
            object.__setattr__(value, "inspection", inspection)
            object.__setattr__(value, "proof_fingerprint", fingerprint("r2-managed-recovery-inspection-v2", body))
            return value
        except ManagedUnitPublicationError:
            raise
        except Exception:
            raise ManagedUnitPublicationError() from None
