"""Bounded logical-retention cleanup for encrypted candidate batches."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Callable

from .candidate_batch import CandidateBatchStore
from .errors import PrivateKnowledgeError


_BATCH_FILE = re.compile(
    r"^batch-([0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12})\.pkcand$"
)
_MAX_BATCH_FILES = 200


def purge_expired_candidate_batches(
    root: Path,
    master_key: bytes | bytearray,
    *,
    clock: Callable[[], datetime],
) -> int:
    candidate_root = Path(root).resolve()
    try:
        paths = tuple(
            path for path in sorted(candidate_root.glob("batch-*.pkcand"))
            if _BATCH_FILE.fullmatch(path.name)
        )
    except OSError:
        raise PrivateKnowledgeError("candidate_retention_failed") from None
    if len(paths) > _MAX_BATCH_FILES:
        raise PrivateKnowledgeError("candidate_retention_limit")
    removed = 0
    for path in paths:
        match = _BATCH_FILE.fullmatch(path.name)
        assert match is not None
        try:
            CandidateBatchStore(
                candidate_root, master_key, batch_id=match.group(1), clock=clock
            ).read()
        except PrivateKnowledgeError as error:
            if error.code != "candidate_batch_expired":
                raise
            removed += 1
    return removed
