"""Latent fixed preflight vocabulary; it grants no production reachability."""


PREFLIGHT_ACKNOWLEDGEMENT = "ACKNOWLEDGE_R2_PREFLIGHT"
PREFLIGHT_VERBS = {
    "current-topology": "current_topology_preflight",
    "host-baseline": "host_baseline",
    "evidence-review": "evidence_review",
    "evidence-verification": "evidence_verification",
    "final-audit-readiness": "final_audit_readiness",
    "recovery-inspection": "recovery_inspection",
}
