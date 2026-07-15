"""Content-safe orchestration for one-record-at-a-time candidate staging."""

from __future__ import annotations

import uuid
from typing import Callable

from .repository import DetachedCandidate
from .staging_contract import (
    CandidateBatchReceipt,
    StageKnowledgeResult,
    StageKnowledgeSelection,
)


def stage_knowledge(
    selection: object,
    *,
    read_one_record: Callable[[str], object],
    deidentify: Callable[[str, object], object],
    scan_residuals: Callable[[object], object],
    write_encrypted_candidate_batch: Callable[
        [tuple[DetachedCandidate, ...]], object
    ],
) -> StageKnowledgeResult:
    selected = StageKnowledgeSelection.from_value(selection)
    support_texts: list[str] = []
    try:
        for record_id in selected.record_ids:
            with read_one_record(record_id) as raw:
                text = getattr(raw, "text")
                context = getattr(raw, "context")
                if not isinstance(text, str):
                    raise ValueError
                with deidentify(text, context) as deidentified:
                    findings = scan_residuals(deidentified)
                    if not isinstance(findings, tuple):
                        raise ValueError
                    if findings:
                        return StageKnowledgeResult(
                            "stage_residual_blocked", 0,
                            len(selected.record_ids), (),
                        )
                    support_texts.append(deidentified.text)
        candidates = (
            DetachedCandidate(str(uuid.uuid4()), tuple(support_texts)),
        )
        candidate_ids = tuple(item.candidate_id for item in candidates)
        written = write_encrypted_candidate_batch(tuple(candidates))
        if (not isinstance(written, CandidateBatchReceipt)
                or written.candidate_ids != candidate_ids):
            raise ValueError
        return StageKnowledgeResult(
            "stage_complete", len(selected.record_ids), 0, candidate_ids,
            written.batch_id,
        )
    except Exception:
        return StageKnowledgeResult(
            "stage_callback_failed", 0, len(selected.record_ids), ()
        )
