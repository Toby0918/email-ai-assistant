"""Capability guards for Issue #75 manifest/worktree transaction."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_repository_manifest"


class R2RepositoryManifestArchitectureTests(unittest.TestCase):
    def test_no_forbidden_git_or_filesystem_capability_exists(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in PACKAGE.glob("*.py")
        )
        for marker in (
            "clone",
            "copyfile",
            "copytree",
            "fetch",
            "reset",
            "stash",
            "prune",
            "repair",
            "rmtree",
            "unlink(",
            "replace(",
            "remove(",
            "shell=true",
            "subprocess",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, source)

    def test_no_real_entry_or_operator_process_import_exists(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in PACKAGE.glob("*.py")
        )
        self.assertNotIn("def main(", source)
        self.assertNotIn("sys.argv", source)
        for package in (
            "r2_preflight_process",
            "r2_evidence_process",
            "r2_transaction_process",
        ):
            self.assertNotIn(package, source)


if __name__ == "__main__":
    unittest.main()
