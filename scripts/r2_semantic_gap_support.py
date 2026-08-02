"""Execute all 70 rows through their owning R2 fault seams."""

from __future__ import annotations

from pathlib import Path

from backend.r2_verification_evidence import semantic_gap_matrix
from scripts.r2_semantic_case_journal import SemanticCaseJournal
from scripts.r2_semantic_owning_effects import execute_owning_effect


def execute_semantic_gap_matrix(sandbox: Path) -> int:
    receipts = []
    for index, case in enumerate(semantic_gap_matrix()):
        root = sandbox / "semantic-gaps" / f"case-{index:02d}"
        root.mkdir(parents=True)
        journal = SemanticCaseJournal(
            root / "case.journal", case.semantic, case.direction, case.gap
        )
        effect = lambda case=case, root=root: execute_owning_effect(
            case.semantic, root, case.direction, case.gap
        )
        receipts.append(journal.execute(effect))
    if len(receipts) != 70 or len(set(receipts)) != 70:
        raise RuntimeError("R2_SEMANTIC_GAP_EXECUTION_INCOMPLETE")
    return len(receipts)
