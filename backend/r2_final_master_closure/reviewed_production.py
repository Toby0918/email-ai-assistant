"""Pure receipt for one reviewed production binding tied to final master."""

from dataclasses import dataclass, field

from ._canonical import fingerprint, is_fingerprint
from .binding import FinalMasterBindingV1
from .errors import FinalMasterClosureError


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2ReviewedProductionBindingReceiptV1:
    receipt_type: str
    final_master_binding_fingerprint: str = field(repr=False)
    production_binding_fingerprint: str = field(repr=False)
    operator_role_registry_fingerprint: str = field(repr=False)
    command_domain_registry_fingerprint: str = field(repr=False)
    public_key_registry_fingerprint: str = field(repr=False)
    production_role_registry_fingerprint: str = field(repr=False)
    production_composition_evidence_fingerprint: str = field(repr=False)
    verified: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError(
            "R2ReviewedProductionBindingReceiptV1 requires verified adapter"
        )

    def to_mapping(self):
        return {
            name: getattr(self, name) for name in self.__dataclass_fields__
        }


def _allocate_reviewed_production_binding_receipt_v1(final_master, body):
    fingerprint_fields = {
        name for name in body if name.endswith("_fingerprint")
    }
    if (
        type(final_master) is not FinalMasterBindingV1
        or set(body)
        != {
            "receipt_type",
            "final_master_binding_fingerprint",
            "production_binding_fingerprint",
            "operator_role_registry_fingerprint",
            "command_domain_registry_fingerprint",
            "public_key_registry_fingerprint",
            "production_role_registry_fingerprint",
            "production_composition_evidence_fingerprint",
            "verified",
        }
        or body["receipt_type"] != "R2ReviewedProductionBindingReceiptV1"
        or body["final_master_binding_fingerprint"]
        != final_master.binding_fingerprint
        or body["verified"] != 1
        or not all(is_fingerprint(body[name]) for name in fingerprint_fields)
    ):
        raise FinalMasterClosureError()
    value = object.__new__(R2ReviewedProductionBindingReceiptV1)
    for name, item in body.items():
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "receipt_fingerprint",
        fingerprint("r2-reviewed-production-binding-receipt-v1", body),
    )
    return value
