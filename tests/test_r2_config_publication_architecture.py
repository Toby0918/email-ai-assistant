"""Static guards for the loader-compatible Issue #79 Config unit."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

import backend.r2_config_publication as contracts


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_config_publication"


class R2ConfigPublicationArchitectureTests(unittest.TestCase):
    def test_public_surface_is_closed_and_pathless(self) -> None:
        self.assertEqual(
            set(contracts.__all__),
            {
                "ConfigCrashGap",
                "ConfigFaultSelectorV1",
                "ConfigPendingState",
                "ConfigPublicationPrerequisiteV1",
                "ConfigPublicationReceiptV1",
                "ConfigPublicationStatus",
                "ManagedConfigSelectionV1",
            },
        )
        source = (PACKAGE / "__init__.py").read_text("utf-8")
        self.assertNotIn("testing", source)
        self.assertNotIn("Path", source)

    def test_no_ambient_secret_private_or_legacy_reader_exists(self) -> None:
        source = "\n".join(
            path.read_text("utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in (
            "os.environ",
            "getenv(",
            "winreg",
            "clipboard",
            "keyring",
            "getpass",
            "load_dotenv",
            "legacy_config",
            "openai_api_key=",
            "deepseek_api_key=",
            "subprocess",
            "shell=true",
            "unlink(",
            "remove(",
            "os.replace(",
            "rmtree",
            "def main(",
            "sys.argv",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_only_existing_managed_loader_and_fixed_handle_are_reused(self) -> None:
        observed = set()
        for path in PACKAGE.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text("utf-8"))):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("backend.")
                ):
                    observed.add(node.module)
        self.assertEqual(
            observed,
            {
                "backend.email_agent.config",
                "backend.email_agent.managed_runtime_validation",
                "backend.r2_database_publication.windows_handle",
            },
        )

    def test_files_and_functions_remain_bounded(self) -> None:
        for path in PACKAGE.glob("*.py"):
            source = path.read_text("utf-8")
            with self.subTest(path=path.name):
                self.assertLessEqual(len(source.splitlines()), 300)
            for node in ast.walk(ast.parse(source)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    with self.subTest(path=path.name, function=node.name):
                        self.assertLessEqual(node.end_lineno - node.lineno + 1, 50)


if __name__ == "__main__":
    unittest.main()
