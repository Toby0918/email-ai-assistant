"""Load the exact closure-owned V3 values for the fixed production binder."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV3
from backend.r2_production_binding._canonical import canonical_json
from backend.r2_production_binding.review import (
    require_reviewed_production_binding_v3,
)
from backend.r2_solo_maintainer_closure import (
    FinalMasterBindingV1,
    SoloMaintainerAttestationReceiptV1,
    SoloMaintainerClosureManifestV1,
)


@dataclass(frozen=True, slots=True, repr=False)
class _Issue39ClosureBindingV1:
    manifest: SoloMaintainerClosureManifestV1 = field(repr=False)
    receipt: SoloMaintainerAttestationReceiptV1 = field(repr=False)
    final_master: FinalMasterBindingV1 = field(repr=False)
    production: ApprovedCutoverBindingV3 = field(repr=False)


def load_fixed_issue39_closure_binding_v1():
    from backend.r2_solo_maintainer_closure.storage import read_closure_artifacts

    manifest_payload, receipt_payload = read_closure_artifacts()
    manifest = SoloMaintainerClosureManifestV1.from_json(manifest_payload)
    receipt = SoloMaintainerAttestationReceiptV1.from_json(receipt_payload)
    final_master = FinalMasterBindingV1.from_mapping(
        manifest.final_master_binding
    )
    production = ApprovedCutoverBindingV3.from_json(
        canonical_json(manifest.production_binding),
        final_master_binding=final_master,
    )
    require_reviewed_production_binding_v3(final_master, production)
    if (
        receipt.status != "SOLO_MAINTAINER_ATTESTATION_RECORDED"
        or receipt.manifest_fingerprint != manifest.manifest_fingerprint
        or manifest.final_master_binding_fingerprint
        != final_master.binding_fingerprint
        or manifest.production_binding_fingerprint
        != production.binding_fingerprint
        or receipt.production_binding_fingerprint
        != production.binding_fingerprint
    ):
        raise TypeError("R2_ISSUE39_CLOSURE_BINDING_INVALID")
    return _Issue39ClosureBindingV1(
        manifest, receipt, final_master, production
    )
