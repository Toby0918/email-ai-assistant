"""Validated path binder for fresh caller-owned Runtime sandboxes."""

from __future__ import annotations

from pathlib import Path

from .builder import RuntimeInputPaths, review_inputs
from .contracts import RuntimePublicationPrerequisiteV1
from .transaction import SyntheticRuntimePublicationTransaction


def bind_test_runtime_transaction(
    *,
    python_source: Path,
    source_manifest: Path,
    wheelhouse: Path,
    dependency_lock: Path,
    staging: Path,
    target: Path,
    journal: Path,
    quiescence_receipt_fingerprint: str,
):
    paths = RuntimeInputPaths(
        Path(python_source),
        Path(source_manifest),
        Path(wheelhouse),
        Path(dependency_lock),
    )
    staging = Path(staging)
    target = Path(target)
    journal = Path(journal)
    if (
        staging.exists()
        or target.exists()
        or journal.exists()
        or staging.parent != target.parent
        or staging.name != "managed-runtime.prepare"
        or target.name != "managed-runtime"
        or len({staging.parent.resolve(), journal.parent.resolve()}) != 2
    ):
        raise ValueError("runtime_test_scope_invalid")
    prerequisite = RuntimePublicationPrerequisiteV1.create(
        quiescence_receipt_fingerprint=quiescence_receipt_fingerprint
    )
    review = review_inputs(paths)
    return SyntheticRuntimePublicationTransaction(
        paths=paths,
        staging=staging,
        target=target,
        journal=journal,
        prerequisite=prerequisite,
        review=review,
    )
