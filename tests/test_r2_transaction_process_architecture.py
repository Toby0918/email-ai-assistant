"""Physical and capability isolation for Issue #73."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_transaction_process"


class R2TransactionProcessArchitectureTests(unittest.TestCase):
    def test_exact_third_process_package_is_disjoint(self) -> None:
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "__main__.py",
                "contracts.py",
                "entry.py",
                "terminal.py",
                "testing.py",
            },
        )
        imports = set()
        for item in PACKAGE.glob("*.py"):
            for node in ast.walk(
                ast.parse(item.read_text(encoding="utf-8"))
            ):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
        self.assertFalse(
            {
                "backend.r2_preflight_process",
                "backend.r2_evidence_process",
                "backend.migration_evidence_verifier",
            }
            & imports
        )

    def test_command_surface_is_only_execute_resume_rollback(self) -> None:
        contracts = (PACKAGE / "contracts.py").read_text(encoding="utf-8")
        entry = (PACKAGE / "entry.py").read_text(encoding="utf-8")
        source = "\n".join(
            item.read_text(encoding="utf-8")
            for item in PACKAGE.glob("*.py")
        )
        for verb in ("execute", "resume", "rollback"):
            self.assertIn(f'"{verb}": "{verb}"', contracts)
        self.assertIn("len(argv) != 1", entry)
        for forbidden in (
            "argparse",
            "--path",
            "--profile",
            "--journal",
            "--recovery-target",
            "--force",
            "powershell",
            "subprocess",
            "git ",
            "os.environ",
        ):
            self.assertNotIn(forbidden, source.lower())

    def test_context_and_domains_are_explicit_before_action(self) -> None:
        testing = (PACKAGE / "testing.py").read_text(encoding="utf-8")
        for required in (
            "approved_binding_fingerprint",
            "journal_owner_fingerprint",
            "journal_head_fingerprint",
            "remaining_plan_fingerprint",
            "boundary_epoch",
            "crash_nonce",
            "AuthorizationEnvelopeDomain.EXECUTION",
            "AuthorizationEnvelopeDomain.RECOVERY",
            "CutoverExecutionAuthorizationV1",
            "RecoveryAuthorizationV1",
        ):
            self.assertIn(required, testing)
        self.assertLess(
            testing.index("verify_authorization_envelope("),
            testing.index("self._perform(verb)"),
        )

    def test_no_normal_consumer_imports_transaction_test_binder(self) -> None:
        needle = "backend.r2_transaction_process.testing"
        consumers = []
        for root_name in ("backend", "frontend", "scripts", ".github"):
            root = ROOT / root_name
            if not root.exists():
                continue
            for item in root.rglob("*"):
                if item.is_file() and item.suffix in {
                    ".py",
                    ".js",
                    ".yml",
                    ".yaml",
                } and needle in item.read_text(encoding="utf-8"):
                    consumers.append(item.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
