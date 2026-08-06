"""Temporary content-free case probe for the durable semantic matrix."""

from __future__ import annotations

import tempfile
from pathlib import Path

from backend.r2_verification_evidence import semantic_gap_matrix
from scripts.r2_semantic_case_journal import SemanticCaseJournal
from scripts.r2_semantic_owning_effects import execute_owning_effect


def main() -> int:
    receipts = []
    with tempfile.TemporaryDirectory(prefix="r2-durable-cases-") as raw:
        sandbox = Path(raw)
        for index, case in enumerate(semantic_gap_matrix()):
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
                receipts.append(journal.execute(effect))
            except RuntimeError:
                print(index + 1)
                return 0
            except ValueError:
                print(index + 81)
                return 0
            except Exception:
                print(index + 161)
                return 0
    print(0 if len(receipts) == 70 and len(set(receipts)) == 70 else 240)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
