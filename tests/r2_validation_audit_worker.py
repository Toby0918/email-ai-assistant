"""Fresh-process independent audit worker for the Issue #81 sandbox."""

from __future__ import annotations

import json
import os
import sys

from backend.r2_independent_audits import (
    AuditDisposition,
    AuditKind,
    IndependentAuditObservationV1,
)
from backend.r2_independent_audits.testing import SyntheticIndependentAudit


def main() -> int:
    (
        kind_raw,
        operation,
        binding,
        head,
        identities,
        health,
        service_nonce,
        service_pid_raw,
    ) = sys.argv[1:]
    kind = AuditKind(kind_raw)
    now = 1_900_000_000
    entries = []
    audit = SyntheticIndependentAudit.create(
        kind=kind,
        operation_fingerprint=operation,
        approved_binding_fingerprint=binding,
        journal_head_fingerprint=head,
        approved_identities_fingerprint=identities,
        health_evidence_fingerprint=health,
        observed_at_epoch=now,
        now=lambda: now,
        append_attestation=entries.append,
    )
    result = audit.run(
        IndependentAuditObservationV1(
            audit_kind=kind,
            operation_fingerprint=operation,
            approved_binding_fingerprint=binding,
            journal_head_fingerprint=head,
            approved_identities_fingerprint=identities,
            health_evidence_fingerprint=health,
            observed_at_epoch=now,
            unambiguous=True,
        )
    )
    output = {
        "audit_kind": kind.value,
        "audit_process_id": os.getpid(),
        "service_nonce": service_nonce,
        "service_process_id": int(service_pid_raw),
        "journal_head_fingerprint": head,
        "approved_identities_fingerprint": identities,
        "health_evidence_fingerprint": health,
        "observed_at_epoch": now,
        "expires_at_epoch": now + 300,
        "attested": result.disposition is AuditDisposition.ATTESTED,
        "journal_entries": len(entries),
    }
    sys.stdout.write(json.dumps(output, sort_keys=True))
    return int(result.receipt is None or len(entries) != 1)


if __name__ == "__main__":
    raise SystemExit(main())
