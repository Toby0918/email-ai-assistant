"""Capability and dependency isolation for Issue #80."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_independent_audits"


class R2IndependentAuditsArchitectureTests(unittest.TestCase):
    def test_package_is_separate_from_transaction_and_process_packages(self):
        self.assertEqual(
            {item.name for item in PACKAGE.glob("*.py")},
            {"__init__.py", "contracts.py", "process.py", "sink.py", "testing.py"},
        )
        transaction_sources = "\n".join(
            item.read_text(encoding="utf-8")
            for root in (
                ROOT / "backend" / "r2_transaction_process",
                ROOT / "backend" / "r2_repository_manifest",
            )
            for item in root.glob("*.py")
        )
        self.assertNotIn("r2_independent_audits", transaction_sources)
        self.assertNotIn("IndependentStoppedLayoutAuditReceiptV1", transaction_sources)
        self.assertNotIn("IndependentFinalRunningHealthReceiptV1", transaction_sources)

    def test_sink_has_no_path_or_arbitrary_io_capability(self) -> None:
        source = (PACKAGE / "sink.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        methods = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertEqual(
            methods,
            {
                "__init__",
                "__reduce__",
                "bind",
                "attest",
                "_consume",
                "_matched",
                "_make_receipt",
                "_attestation",
            },
        )
        for forbidden in (
            "pathlib",
            "os.path",
            "open(",
            ".read(",
            "listdir",
            "mkdir",
            "truncate",
            "replace(",
            "unlink",
            "remove(",
            "serialize",
            "pickle",
            "reset",
        ):
            self.assertNotIn(forbidden, source.lower())

    def test_receipt_issuance_is_private_to_exact_sink(self) -> None:
        contracts = (PACKAGE / "contracts.py").read_text(encoding="utf-8")
        sink = (PACKAGE / "sink.py").read_text(encoding="utf-8")
        process = (PACKAGE / "process.py").read_text(encoding="utf-8")
        self.assertIn("init=False", contracts)
        self.assertIn("def __reduce__", contracts)
        self.assertIn("object.__new__(receipt_type)", sink)
        self.assertNotIn("object.__new__", process)
        self.assertNotIn("ReceiptV1(", process)

    def test_normal_runtime_and_frontend_have_no_consumer(self) -> None:
        needle = "backend.r2_independent_audits"
        approved_composition = ROOT / "backend" / "r2_validation_lifecycle"
        consumers = []
        for root_name in ("backend", "frontend", "scripts", ".github"):
            root = ROOT / root_name
            for item in root.rglob("*") if root.exists() else ():
                if (
                    item.is_file()
                    and item.suffix in {".py", ".js", ".yml", ".yaml"}
                    and PACKAGE not in item.parents
                    and approved_composition not in item.parents
                    and needle in item.read_text(encoding="utf-8")
                ):
                    consumers.append(item.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, [])


if __name__ == "__main__":
    unittest.main()
