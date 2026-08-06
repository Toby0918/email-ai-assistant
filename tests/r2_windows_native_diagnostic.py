"""Temporary content-free error-code probe for semantic case 23."""

from __future__ import annotations

import tempfile
from pathlib import Path

from backend.r2_verification_evidence import semantic_gap_matrix
from scripts.r2_semantic_case_journal import SemanticCaseJournal
from scripts.r2_semantic_owning_effects import execute_owning_effect


_VALUE_CODES = {
    "config_transaction_invocation_invalid": 1,
    "config_document_drift": 2,
    "config_target_collision": 3,
    "config_target_drift": 4,
    "config_loader_mismatch": 5,
    "config_target_replacement_blocked": 6,
    "config_target_replaced": 7,
    "config_pending_generation": 8,
    "config_test_scope_invalid": 9,
    "config_journal_invalid": 10,
    "managed_config_invalid": 11,
    "config_selection_invalid": 12,
    "config_prerequisite_invalid": 13,
    "config_fault_selector_invalid": 14,
}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r2-durable-cases-") as raw:
        sandbox = Path(raw)
        for index, case in enumerate(semantic_gap_matrix()[:23]):
            try:
                root = sandbox / "semantic-gaps" / f"case-{index:02d}"
                root.mkdir(parents=True)
                journal = SemanticCaseJournal(
                    root / "case.journal",
                    case.semantic,
                    case.direction,
                    case.gap,
                )
                effect = lambda case=case, root=root: execute_owning_effect(
                    case.semantic,
                    root,
                    case.direction,
                    case.gap,
                )
                journal.execute(effect)
            except ValueError as error:
                print(201 + index if index < 22 else _VALUE_CODES.get(str(error), 20))
                return 0
            except RuntimeError:
                print(201 + index if index < 22 else 50)
                return 0
            except Exception:
                print(201 + index if index < 22 else 80)
                return 0
    print(0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
