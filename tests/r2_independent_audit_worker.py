"""Synthetic fresh-process driver for Issue #80."""

from __future__ import annotations

import json
import os
import sys

from backend.r2_independent_audits import AuditKind, IndependentAuditObservationV1
from backend.r2_independent_audits.testing import SyntheticIndependentAudit
from tests.cutover_contract_fixtures import opaque_fingerprint


def main() -> int:
    kind = AuditKind(sys.argv[1])
    operation, binding, head = (opaque_fingerprint(index) for index in range(8000, 8003))
    identities, health = (opaque_fingerprint(index) for index in range(8003, 8005))
    entries = []
    audit = SyntheticIndependentAudit.create(
        kind=kind,
        operation_fingerprint=operation,
        approved_binding_fingerprint=binding,
        journal_head_fingerprint=head,
        approved_identities_fingerprint=identities,
        health_evidence_fingerprint=health,
        observed_at_epoch=1_900_000_000,
        now=lambda: 1_900_000_000,
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
            observed_at_epoch=1_900_000_000,
            unambiguous=True,
        )
    )
    sys.stdout.write(
        json.dumps(
            {
                "audit_kind": kind.value,
                "process_id": os.getpid(),
                "journal_entries": len(entries),
                "status": result.disposition.value,
            },
            sort_keys=True,
        )
    )
    return int(result.receipt is None)


if __name__ == "__main__":
    raise SystemExit(main())
