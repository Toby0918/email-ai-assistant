from __future__ import annotations

import ast
import hashlib
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
ORCHESTRATOR_MODULE = "backend.r2_issue39_orchestrator"
ENTRY_MODULE = "scripts.execute_project_container_cutover"
RETAINED_INCIDENT_LEAF = (
    ".r2-solo-maintainer-closure-v1.incident-"
    "794aea72b0012d1de728f3b87f7f25c2f7c9ae3ac8f66777845010635fc69721"
)
EXPECTED_ENTRY_SHA256 = (
    "1b774a75f724a4ff5b98d3f8c13115ebd1e9e7d0ecc669619623779e0150f8a9"
)
EXPECTED_RUNNER_BYTES = (
    b"from backend.r2_issue39_orchestrator.cli import main\nmain()\n"
)
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
    def test_fixed_incident_binding_pins_exact_retained_leaf(self) -> None:
        binding_path = ORCHESTRATOR / "incident_binding.py"
        tree = ast.parse(
            binding_path.read_text(encoding="utf-8"),
            filename=str(binding_path),
        )
        leaf_assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_LEAF"
                for target in node.targets
            )
        ]

        self.assertEqual(len(leaf_assignments), 1)
        self.assertEqual(
            ast.literal_eval(leaf_assignments[0].value),
            RETAINED_INCIDENT_LEAF,
        )
        self.assertNotIn(
            ".r2-solo-maintainer-closure-v1.stage-",
            binding_path.read_text(encoding="utf-8"),
        )

    def test_governed_import_detection_covers_valid_python_spellings(self) -> None:
        cases = (
            (
                "from backend import r2_issue39_orchestrator",
                ROOT / "backend" / "consumer.py",
            ),
            (
                "from .r2_issue39_orchestrator import cli",
                ROOT / "backend" / "consumer.py",
            ),
            (
                "from scripts import execute_project_container_cutover",
                ROOT / "backend" / "consumer.py",
            ),
        )
        for source, path in cases:
            with self.subTest(source=source):
                self.assertTrue(
                    _imports_governed_surface(ast.parse(source), path)
                )

    def test_only_fixed_script_imports_orchestrator_from_production(self) -> None:
        orchestrator_importers = set()
        entry_importers = set()
        candidates = tuple((ROOT / "backend").rglob("*.py")) + tuple(
            (ROOT / "scripts").rglob("*.py")
        )
        for path in candidates:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            modules = _imported_modules(tree, path)
            relative = path.relative_to(ROOT).as_posix()
            if not path.is_relative_to(ORCHESTRATOR) and any(
                _is_module_or_child(module, ORCHESTRATOR_MODULE)
                for module in modules
            ):
                orchestrator_importers.add(relative)
            if any(
                _is_module_or_child(module, ENTRY_MODULE) for module in modules
            ):
                entry_importers.add(relative)

        self.assertEqual(
            orchestrator_importers,
            {"scripts/execute_project_container_cutover.py"},
        )
        self.assertEqual(entry_importers, set())

    def test_fixed_script_and_retained_runner_have_one_exact_entry(self) -> None:
        entry_source = ENTRY.read_text(encoding="utf-8")
        self.assertEqual(
            hashlib.sha256(entry_source.encode("utf-8")).hexdigest(),
            EXPECTED_ENTRY_SHA256,
        )
        self.assertIn(
            r"D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement",
            entry_source,
        )
        self.assertLess(
            entry_source.index("_initial_launch_anchor_matches"),
            entry_source.index("from backend.r2_issue39_orchestrator.cli"),
        )

        anchor = ast.parse(
            (ORCHESTRATOR / "production_anchor_package.py").read_text(
                encoding="utf-8"
            )
        )
        main_entries = [
            node
            for node in ast.walk(anchor)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_zip_entry"
            and len(node.args) == 3
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == "__main__.py"
        ]
        self.assertEqual(len(main_entries), 1)
        payload = main_entries[0].args[2]
        self.assertIsInstance(payload, ast.Constant)
        self.assertEqual(payload.value, EXPECTED_RUNNER_BYTES)

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


def _imports_governed_surface(tree: ast.AST, path: Path) -> bool:
    modules = _imported_modules(tree, path)
    return any(
        _is_module_or_child(module, governed)
        for module in modules
        for governed in (ORCHESTRATOR_MODULE, ENTRY_MODULE)
    )


def _imported_modules(tree: ast.AST, path: Path) -> set[str]:
    modules = set()
    relative_parts = path.relative_to(ROOT).with_suffix("").parts
    package_parts = relative_parts[:-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.level:
                parent_count = node.level - 1
                if parent_count > len(package_parts):
                    continue
                base_parts = package_parts[: len(package_parts) - parent_count]
            else:
                base_parts = ()
            module_parts = tuple(filter(None, (node.module or "").split(".")))
            imported_from = ".".join((*base_parts, *module_parts))
            if imported_from:
                modules.add(imported_from)
            for alias in node.names:
                if alias.name != "*":
                    modules.add(".".join(filter(None, (imported_from, alias.name))))
    return modules


def _is_module_or_child(module: str, expected: str) -> bool:
    return module == expected or module.startswith(expected + ".")


if __name__ == "__main__":
    unittest.main()
