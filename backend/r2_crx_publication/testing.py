"""Validated binder for a fixed fresh synthetic CRX sandbox."""

from __future__ import annotations

from pathlib import Path

from .contracts import CrxPublicationPrerequisiteV1
from .review import review_source
from .transaction import SyntheticCrxPublicationTransaction


def bind_test_crx_transaction(
    *,
    source: Path,
    staging: Path,
    target: Path,
    journal: Path,
    quiescence_receipt_fingerprint: str,
):
    source, staging, target, journal = map(
        Path, (source, staging, target, journal)
    )
    if staging.exists() or staging.is_symlink():
        raise ValueError("crx_pending_generation")
    if (
        not source.is_file()
        or source.is_symlink()
        or journal.exists()
        or staging.parent != target.parent
        or staging.name != "email-ai-assistant.crx.prepare"
        or target.name != "email-ai-assistant.crx"
        or len({source.parent.resolve(), target.parent.resolve()}) != 2
    ):
        raise ValueError("crx_test_scope_invalid")
    prerequisite = CrxPublicationPrerequisiteV1.create(
        quiescence_receipt_fingerprint=quiescence_receipt_fingerprint
    )
    return SyntheticCrxPublicationTransaction(
        source=source,
        staging=staging,
        target=target,
        journal=journal,
        prerequisite=prerequisite,
        review=review_source(source),
    )
