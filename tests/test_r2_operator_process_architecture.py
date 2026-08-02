"""Mechanical capability guards for the Issue #71 process roots."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT / "backend" / "r2_operator_process"
PREFLIGHT = ROOT / "backend" / "r2_preflight_process"


class R2OperatorProcessArchitectureTests(unittest.TestCase):
    def test_packages_have_only_the_reviewed_files(self) -> None:
        self.assertEqual(
            {item.name for item in OPERATOR.glob("*.py")},
            {"__init__.py", "envelope.py", "dormant_context.py", "production_v2.py"},
        )
        self.assertEqual(
            {item.name for item in PREFLIGHT.glob("*.py")},
            {
                "__init__.py",
                "__main__.py",
                "contracts.py",
                "entry.py",
                "terminal.py",
                "testing.py",
                "production_v2.py",
            },
        )

    def test_backend_contains_verification_but_no_signing_or_private_key(self) -> None:
        source = "\n".join(
            item.read_text(encoding="utf-8")
            for root in (OPERATOR, PREFLIGHT)
            for item in root.glob("*.py")
        )
        self.assertIn("Ed25519PublicKey", source)
        for forbidden in (
            "Ed25519PrivateKey",
            ".sign(",
            ".generate(",
            "private_bytes",
            "load_pem_private_key",
            "subprocess",
            "socket",
            "requests",
            "openai",
            "mailbox",
            "vault",
        ):
            self.assertNotIn(forbidden, source)

    def test_preflight_root_has_no_umbrella_or_stronger_root_import(self) -> None:
        imports = set()
        for item in PREFLIGHT.glob("*.py"):
            tree = ast.parse(item.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imports.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imports.add(node.module)
        for forbidden in (
            "backend.migration_evidence_publication_composition",
            "backend.cutover_transaction_composition",
            "backend.cutover_host_mutation",
            "backend.cutover_repository_transaction",
            "backend.cutover_managed_activation",
            "backend.cutover_service_lifecycle",
        ):
            self.assertNotIn(forbidden, imports)

    def test_command_and_terminal_surface_is_closed(self) -> None:
        contracts = (PREFLIGHT / "contracts.py").read_text(encoding="utf-8")
        entry = (PREFLIGHT / "entry.py").read_text(encoding="utf-8")
        terminal = (PREFLIGHT / "terminal.py").read_text(encoding="utf-8")
        self.assertEqual(contracts.count('": "'), 6)
        self.assertIn("tuple(sys.argv[1:])", entry)
        self.assertIn("len(argv) == 1", entry)
        self.assertNotIn("argparse", entry)
        self.assertNotIn("os.environ", entry + terminal)
        self.assertNotIn("Path(", entry + terminal)
        self.assertEqual(
            terminal.count("stream.isatty() is True"),
            1,
        )
        self.assertIn(
            "for stream in (sys.stdin, sys.stdout, sys.stderr)",
            terminal,
        )

    def test_only_tests_import_the_synthetic_binder(self) -> None:
        consumers = []
        needle = "backend.r2_preflight_process.testing"
        for root_name in ("backend", "frontend", "scripts", ".github"):
            root = ROOT / root_name
            if not root.exists():
                continue
            for item in root.rglob("*"):
                if item.is_file() and item.suffix in {".py", ".js", ".yml", ".yaml"}:
                    try:
                        source = item.read_text(encoding="utf-8")
                    except UnicodeDecodeError:
                        continue
                    if needle in source:
                        consumers.append(item.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
