from __future__ import annotations

import ast
from pathlib import Path
import unittest

from backend.r2_evidence_process.production_v2 import (
    EvidenceProductionStatusV2,
    run_evidence_production_v2,
)
from backend.r2_preflight_process.production_v2 import (
    PreflightProductionStatusV2,
    run_preflight_production_v2,
)
from backend.r2_transaction_process.production_v2 import (
    TransactionProductionStatusV2,
    run_transaction_production_v2,
)


ROOT = Path(__file__).resolve().parents[1]
ORCHESTRATOR = ROOT / "backend" / "r2_issue39_orchestrator"
ENTRY = ROOT / "scripts" / "execute_project_container_cutover.py"
ALLOWLIST_STATEMENT = (
    "The approved Issue #39 code allowlist permits only the fixed "
    "`backend.r2_issue39_orchestrator` composition root, "
    "`scripts/execute_project_container_cutover.py`, and its package-owned "
    "retained restart runner."
)
NORMATIVE_DOCUMENTS = (
    ROOT / "AGENTS.md",
    ROOT / "docs" / "constraints" / "architecture_constraints.md",
    ROOT / "docs" / "constraints" / "linter_constraints.md",
    ROOT / "docs" / "constraints" / "mechanical_rule_translation.md",
    ROOT / "docs" / "constraints" / "tooling_constraints.md",
    ROOT / "docs" / "security" / "project_container_cutover_contracts.md",
)


class _Poison:
    def __getattribute__(self, _name):
        raise AssertionError("dormant root inspected a poison input")


class Issue39GovernedEnablementTest(unittest.TestCase):
    def test_only_fixed_script_imports_orchestrator_from_production(self) -> None:
        importers = set()
        candidates = tuple((ROOT / "backend").rglob("*.py")) + tuple(
            (ROOT / "scripts").rglob("*.py")
        )
        for path in candidates:
            if path.is_relative_to(ORCHESTRATOR):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if _imports_orchestrator(tree):
                importers.add(path.relative_to(ROOT).as_posix())

        self.assertEqual(
            importers,
            {"scripts/execute_project_container_cutover.py"},
        )

    def test_fixed_script_and_retained_runner_have_one_exact_entry(self) -> None:
        script = ast.parse(ENTRY.read_text(encoding="utf-8"), filename=str(ENTRY))
        imports = {
            (node.module, tuple(alias.name for alias in node.names))
            for node in ast.walk(script)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertIn(
            ("backend.r2_issue39_orchestrator.cli", ("main",)),
            imports,
        )

        anchor = ast.parse(
            (ORCHESTRATOR / "production_anchor_package.py").read_text(
                encoding="utf-8"
            )
        )
        runner_values = {
            node.value
            for node in ast.walk(anchor)
            if isinstance(node, ast.Constant) and isinstance(node.value, bytes)
            and b"r2_issue39_orchestrator.cli" in node.value
        }
        self.assertEqual(
            runner_values,
            {b"from backend.r2_issue39_orchestrator.cli import main\nmain()\n"},
        )

    def test_historical_standalone_roots_remain_unconditionally_dormant(self) -> None:
        poison = _Poison()
        preflight = run_preflight_production_v2(
            argv=poison,
            terminal=poison,
            binding=poison,
            adapter=poison,
            execution_confirmation_claims=poison,
            expected_prior_journal_head_fingerprint=poison,
            observed_at_epoch=poison,
        )
        evidence = run_evidence_production_v2(
            argv=poison,
            terminal=poison,
            binding=poison,
            adapter=poison,
            reviewed_evidence_fingerprint=poison,
            execution_confirmation_claims=poison,
            expected_prior_journal_head_fingerprint=poison,
            observed_at_epoch=poison,
            journal_owner_fingerprint=poison,
            genesis_nonce=poison,
        )
        transaction = run_transaction_production_v2(
            argv=poison,
            terminal=poison,
            binding=poison,
            adapter=poison,
            execution_confirmation_claims=poison,
            current_journal_head_fingerprint=poison,
            transition_instance_fingerprint=poison,
            remaining_reverse_plan_fingerprint=poison,
            observed_at_epoch=poison,
        )

        self.assertIs(
            preflight.status,
            PreflightProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        )
        self.assertEqual(preflight.counts(), (0, 0, 0))
        self.assertIs(
            evidence.status,
            EvidenceProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        )
        self.assertEqual(evidence.counts(), (0, 0, 0))
        self.assertIs(
            transaction.status,
            TransactionProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        )
        self.assertEqual(transaction.counts(), (0, 0, 0))

    def test_normative_documents_share_the_exact_allowlist_statement(self) -> None:
        for path in NORMATIVE_DOCUMENTS:
            with self.subTest(path=path.relative_to(ROOT).as_posix()):
                self.assertIn(
                    ALLOWLIST_STATEMENT,
                    path.read_text(encoding="utf-8"),
                )


def _imports_orchestrator(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(
                alias.name.startswith("backend.r2_issue39_orchestrator")
                for alias in node.names
            ):
                return True
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            "backend.r2_issue39_orchestrator"
        ):
            return True
    return False


if __name__ == "__main__":
    unittest.main()
