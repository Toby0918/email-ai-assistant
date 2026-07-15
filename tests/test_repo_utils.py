"""Tests for shared repository utility helpers."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts import repo_utils
from scripts.repo_utils import (
    has_required_front_matter,
    is_ignored_by_gitignore,
    is_text_file,
    iter_project_files,
    iter_python_files,
    load_gitignore_patterns,
    parse_front_matter,
    parse_front_matter_field,
    read_text,
)


class RepoUtilsTests(unittest.TestCase):
    def test_mailbox_vault_cryptography_pin_is_exact(self) -> None:
        requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
            encoding="utf-8"
        )

        versions = repo_utils.parse_pinned_dependency_versions(requirements)

        self.assertEqual(versions.get("cryptography"), "49.0.0")

    def test_dependency_pin_parser_rejects_conflicting_duplicates(self) -> None:
        requirements = "openai==2.45.0\nOpenAI==2.46.0\nPillow==12.3.0\n"

        with self.assertRaisesRegex(ValueError, r"openai.*2\.45\.0.*2\.46\.0"):
            repo_utils.parse_pinned_dependency_versions(requirements)

    def test_load_gitignore_patterns_skips_comments_blanks_and_negations(self) -> None:
        # Negated patterns are intentionally ignored by this simple scanner.
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".gitignore").write_text(
                "\n# comment\n.env\noutputs/\n!important.txt\n*.sqlite3\n",
                encoding="utf-8",
            )

            self.assertEqual(load_gitignore_patterns(root), [".env", "outputs/", "*.sqlite3"])

    def test_is_ignored_by_gitignore_matches_name_directory_and_glob(self) -> None:
        root = Path("repo")
        patterns = [".env", "outputs/", "*.sqlite3", "docs/generated/*.md"]

        self.assertTrue(is_ignored_by_gitignore(root / ".env", root, patterns))
        self.assertTrue(is_ignored_by_gitignore(root / "outputs" / "report.md", root, patterns))
        self.assertTrue(is_ignored_by_gitignore(root / "data" / "cache.sqlite3", root, patterns))
        self.assertTrue(is_ignored_by_gitignore(root / "docs" / "generated" / "x.md", root, patterns))
        self.assertFalse(is_ignored_by_gitignore(root / "docs" / "manual.md", root, patterns))

    def test_iter_project_files_skips_default_ignored_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "backend").mkdir()
            (root / ".venv").mkdir()
            (root / "backend" / "app.py").write_text("print('sample')\n", encoding="utf-8")
            (root / ".venv" / "ignored.py").write_text("print('ignored')\n", encoding="utf-8")

            files = {path.relative_to(root).as_posix() for path in iter_project_files(root)}

        self.assertEqual(files, {"backend/app.py"})

    def test_iter_project_files_skips_nested_git_worktree_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            kept = root / "backend" / "app.py"
            kept.parent.mkdir()
            kept.write_text("", encoding="utf-8")
            for directory in (".worktrees", "worktrees"):
                nested = root / directory / "feature" / "private_fixture.py"
                nested.parent.mkdir(parents=True)
                nested.write_text("", encoding="utf-8")

            files = {path.relative_to(root).as_posix() for path in iter_project_files(root)}

        self.assertEqual(files, {"backend/app.py"})

    def test_iter_python_files_skips_default_ignored_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "module").mkdir()
            (root / "module" / "__pycache__").mkdir()
            (root / "module" / "app.py").write_text("", encoding="utf-8")
            (root / "module" / "__pycache__" / "app.py").write_text("", encoding="utf-8")

            files = {path.relative_to(root).as_posix() for path in iter_python_files(root)}

        self.assertEqual(files, {"module/app.py"})

    def test_read_text_and_text_file_detection_are_shared(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            path = root / "docs" / "sample.md"
            path.parent.mkdir()
            path.write_text("\ufeffhello", encoding="utf-8")

            self.assertTrue(is_text_file(path))
            self.assertEqual(read_text(path), "\ufeffhello")

    def test_front_matter_helpers_parse_required_fields(self) -> None:
        text = """\ufeff---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Example
"""

        self.assertTrue(has_required_front_matter(text))
        self.assertEqual(parse_front_matter(text)["status"], "active")
        self.assertEqual(parse_front_matter_field(text, "source_type"), "operation_guide")


if __name__ == "__main__":
    unittest.main()
