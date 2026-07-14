"""Executable architecture constraints for the email AI assistant project.

Run:
    python -m unittest discover -s tests -p "test_architecture_constraints.py"
"""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from scripts.repo_utils import (
    FORBIDDEN_REPO_FILE_NAMES,
    FORBIDDEN_REPO_SUFFIXES,
    has_required_front_matter,
    is_ignored_by_gitignore,
    is_text_file,
    iter_project_files,
    load_gitignore_patterns,
    read_text,
)

ROOT = Path(__file__).resolve().parents[1]

FRONTEND_FORBIDDEN_PATTERNS = {
    "openai_api_key": r"OPENAI_API_KEY",
    "deepseek_api_key": r"\bDEEPSEEK_API_KEY\b",
    "openai_secret_key": r"\bsk-[A-Za-z0-9_-]{10,}",
    "openai_base_url": r"api\.openai\.com",
    "deepseek_base_url": r"api\.deepseek\.com",
    "openai_responses_api": r"/v1/responses",
    "openai_chat_api": r"/v1/chat/completions",
    "new_openai_client": r"new\s+OpenAI\s*\(",
    "openai_import": r"from\s+['\"]openai['\"]|require\(['\"]openai['\"]\)",
    "deepseek_import": r"from\s+['\"]deepseek['\"]|require\(['\"]deepseek['\"]\)",
    "ollama_host": r"127\.0\.0\.1:11434|localhost:11434",
    "ollama_generate_api": r"/api/generate",
    "ollama_chat_api": r"/api/chat",
    "ollama_marker": r"\bollama\b",
    "local_qwen_marker": r"\bqwen(?:3\.6)?\b",
    "local_gemma_marker": r"\bgemma(?:4)?\b",
    "browser_oauth_flow": r"chrome\.identity|client_secret|refresh_token|access_token",
    "env_access": r"process\.env|\.env",
    "sqlite_access": r"sqlite|sqlite3",
}

FRONTEND_DANGEROUS_ACTIONS = {
    "graph_send_mail": r"sendMail\b",
    "gmail_send": r"gmail\.users\.messages\.send",
    "archive_action": r"archiveMessage|archive\(",
    "delete_action": r"deleteMessage|trashMessage|messages\.trash",
    "modify_or_move_action": r"gmail\.users\.messages\.modify|messages\.modify|moveMessage|move\(",
    "forward_action": r"forwardMessage|forward\(",
}

IMAP_CONSTRUCTORS = {"IMAP4", "IMAP4_SSL", "IMAP4_stream"}
WRAPPER_IMAP_CONSTRUCTOR = "IMAP4_SSL"
SMTP_CONSTRUCTORS = {"SMTP", "SMTP_SSL"}


GITIGNORE_PATTERNS = load_gitignore_patterns(ROOT)


def parse_import_roots(path: Path) -> set[str]:
    # Import roots are enough to enforce the project's layer boundaries.
    if not path.exists():
        return set()
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return set()

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def parse_called_names(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        tree = ast.parse(read_text(path))
    except SyntaxError:
        return set()

    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            names.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
    return names


class ArchitectureConstraintTests(unittest.TestCase):
    def test_mailbox_ingest_import_boundary_is_administrator_cli_only(self) -> None:
        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        required_contract = (
            "Only `scripts/manage_mailbox_vault.py` may import "
            "`backend.mailbox_ingest`."
        )

        self.assertIn(required_contract, architecture)
        self.assertIn(
            "scripts/manage_mailbox_vault.py -> backend.mailbox_ingest",
            architecture,
        )
        self.assertIn("frontend -> backend.mailbox_ingest", architecture)
        self.assertIn("backend.email_agent -> backend.mailbox_ingest", architecture)

        allowed_importer = ROOT / "scripts" / "manage_mailbox_vault.py"
        mailbox_package = ROOT / "backend" / "mailbox_ingest"
        runtime_paths = [
            path
            for path in (ROOT / "backend").rglob("*.py")
            if mailbox_package not in path.parents
        ]
        runtime_paths.extend(
            path
            for path in (ROOT / "scripts").glob("*.py")
            if path != allowed_importer
        )
        frontend = ROOT / "frontend"
        runtime_paths.extend(
            path
            for path in frontend.rglob("*")
            if path.is_file() and is_text_file(path)
        )
        workflows = ROOT / ".github" / "workflows"
        if workflows.exists():
            runtime_paths.extend(
                path
                for path in workflows.rglob("*")
                if path.is_file() and is_text_file(path)
            )

        importer_reference = re.compile(
            r"\b(?:backend[./])?mailbox_ingest\b",
            re.IGNORECASE,
        )
        for path in runtime_paths:
            with self.subTest(path=path):
                self.assertIsNone(
                    importer_reference.search(read_text(path)),
                    f"{path} must not reference the isolated mailbox importer",
                )

    def test_mail_transport_imports_and_constructors_are_wrapper_owned(self) -> None:
        wrapper = ROOT / "backend" / "mailbox_ingest" / "imap_readonly.py"
        runtime_paths = list((ROOT / "backend").rglob("*.py"))
        runtime_paths.extend((ROOT / "scripts").rglob("*.py"))

        for path in runtime_paths:
            imports = parse_import_roots(path)
            calls = parse_called_names(path)
            with self.subTest(path=path, rule="no SMTP"):
                self.assertNotIn("smtplib", imports)
                self.assertTrue(
                    calls.isdisjoint(SMTP_CONSTRUCTORS),
                    f"{path} must not construct an SMTP client",
                )
            if path.resolve() == wrapper.resolve():
                with self.subTest(path=path, rule="TLS IMAP only"):
                    self.assertTrue(
                        calls.isdisjoint(
                            IMAP_CONSTRUCTORS - {WRAPPER_IMAP_CONSTRUCTOR}
                        ),
                        f"{path} must construct only an IMAP4_SSL client",
                    )
                continue
            with self.subTest(path=path, rule="wrapper owns IMAP"):
                self.assertNotIn("imaplib", imports)
                self.assertTrue(
                    calls.isdisjoint(IMAP_CONSTRUCTORS),
                    f"{path} must not construct an IMAP client",
                )

    def test_frontend_provider_guard_covers_deepseek_direct_access(self) -> None:
        samples = {
            "DeepSeek API key": "const key = DEEPSEEK_API_KEY;",
            "DeepSeek API host": "https://api.deepseek.com/chat/completions",
            "DeepSeek SDK import": 'import client from "deepseek";',
        }
        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(
                    any(
                        re.search(pattern, sample, re.IGNORECASE)
                        for pattern in FRONTEND_FORBIDDEN_PATTERNS.values()
                    ),
                    f"Architecture guard does not reject {label}.",
                )

    def test_forbidden_repository_files_are_not_unignored(self) -> None:
        for path in iter_project_files(ROOT):
            name = path.name.lower()
            suffix = path.suffix.lower()
            if name in FORBIDDEN_REPO_FILE_NAMES or suffix in FORBIDDEN_REPO_SUFFIXES:
                with self.subTest(path=path):
                    self.assertTrue(
                        is_ignored_by_gitignore(path, ROOT, GITIGNORE_PATTERNS),
                        f"{path} is not ignored",
                    )
            with self.subTest(path=path):
                self.assertFalse(name.endswith(".token"))
                self.assertFalse(name.endswith(".secret"))

    def test_frontend_does_not_call_openai_or_read_secrets(self) -> None:
        # Frontend code may call only the backend, never OpenAI or local secrets.
        frontend = ROOT / "frontend"
        if not frontend.exists():
            self.skipTest("frontend/ does not exist yet")

        for path in frontend.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FRONTEND_FORBIDDEN_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(re.search(pattern, text, re.IGNORECASE))

    def test_frontend_does_not_perform_dangerous_email_actions(self) -> None:
        frontend = ROOT / "frontend"
        if not frontend.exists():
            self.skipTest("frontend/ does not exist yet")

        for path in frontend.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FRONTEND_DANGEROUS_ACTIONS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(re.search(pattern, text, re.IGNORECASE))

    def test_backend_never_imports_frontend(self) -> None:
        backend = ROOT / "backend"
        if not backend.exists():
            self.skipTest("backend/ does not exist yet")

        for path in backend.rglob("*.py"):
            imports = parse_import_roots(path)
            with self.subTest(path=path):
                self.assertNotIn("frontend", imports)

    def test_email_cleaner_has_no_ai_database_or_api_dependency(self) -> None:
        path = ROOT / "backend" / "email_agent" / "email_cleaner.py"
        if not path.exists():
            self.skipTest("email_cleaner.py does not exist yet")

        imports = parse_import_roots(path)
        forbidden = {"openai", "llm_client", "database", "exporter", "api"}
        self.assertTrue(imports.isdisjoint(forbidden), imports)

    def test_database_has_no_ai_or_frontend_dependency(self) -> None:
        path = ROOT / "backend" / "email_agent" / "database.py"
        if not path.exists():
            self.skipTest("database.py does not exist yet")

        imports = parse_import_roots(path)
        forbidden = {"openai", "llm_client", "frontend"}
        self.assertTrue(imports.isdisjoint(forbidden), imports)

    def test_exporter_has_no_ai_or_frontend_dependency(self) -> None:
        path = ROOT / "backend" / "email_agent" / "exporter.py"
        if not path.exists():
            self.skipTest("exporter.py does not exist yet")

        imports = parse_import_roots(path)
        forbidden = {"openai", "llm_client", "frontend"}
        self.assertTrue(imports.isdisjoint(forbidden), imports)

    def test_llm_client_has_no_storage_export_or_frontend_dependency(self) -> None:
        path = ROOT / "backend" / "email_agent" / "llm_client.py"
        if not path.exists():
            self.skipTest("llm_client.py does not exist yet")

        imports = parse_import_roots(path)
        forbidden = {"database", "exporter", "frontend"}
        self.assertTrue(imports.isdisjoint(forbidden), imports)

    def test_python_modules_do_not_contain_raw_secret_literals(self) -> None:
        secret_patterns = {
            "openai_key": r"\bsk-[A-Za-z0-9_-]{10,}",
            "oauth_token": r"ya29\.[A-Za-z0-9_-]+",
            "password_assignment": r"password\s*=\s*['\"][^'\"]+['\"]",
        }
        documented_pattern_files = {
            "linter_constraints.md",
            "test_static_linter_constraints.py",
            "test_architecture_constraints.py",
            "api_key_rules.md",
        }

        for path in iter_project_files(ROOT):
            if path.suffix.lower() not in {".py", ".js", ".ts", ".html", ".json", ".md"}:
                continue
            if path.name in documented_pattern_files:
                continue
            text = read_text(path)
            for name, pattern in secret_patterns.items():
                with self.subTest(rule=name, path=path):
                    matches = list(re.finditer(pattern, text, re.IGNORECASE))
                    if name == "openai_key":
                        matches = [
                            match for match in matches
                            if not match.group(0).lower().startswith("sk-your-")
                        ]
                    self.assertFalse(matches, f"{path} contains possible secret literal")

    def test_docs_markdown_files_have_required_front_matter(self) -> None:
        docs = ROOT / "docs"
        if not docs.exists():
            self.skipTest("docs/ does not exist yet")

        for path in docs.rglob("*.md"):
            text = read_text(path)
            with self.subTest(path=path):
                self.assertTrue(has_required_front_matter(text), f"{path} lacks required front matter")


if __name__ == "__main__":
    unittest.main()
