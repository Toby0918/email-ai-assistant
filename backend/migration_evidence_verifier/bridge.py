"""The verifier worker's only Migration Evidence Package bridge."""

from __future__ import annotations


def verify_existing_payload(*, payload: bytes):
    from backend.migration_evidence.verification import (
        verify_migration_evidence_payload,
    )

    return verify_migration_evidence_payload(payload=payload)
