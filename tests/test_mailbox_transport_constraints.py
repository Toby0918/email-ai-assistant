"""Mechanical transport constraints for the isolated mailbox importer."""

from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

from scripts.repo_utils import read_text


ROOT = Path(__file__).resolve().parents[1]

POLICY_DOCS = (
    ROOT / "docs" / "constraints" / "tooling_constraints.md",
    ROOT / "docs" / "constraints" / "architecture_constraints.md",
    ROOT / "docs" / "constraints" / "linter_constraints.md",
)

ALLOWED_IMAP_OPERATIONS = (
    "`LIST`",
    "`EXAMINE`",
    "`UID SEARCH`",
    "`UID FETCH`",
    "`BODY.PEEK`",
)

FORBIDDEN_TRANSPORT_OPERATIONS = (
    "`STORE`",
    "`APPEND`",
    "`COPY`",
    "`MOVE`",
    "`EXPUNGE`",
    "`CREATE`",
    "`DELETE`",
    "`RENAME`",
    "`SUBSCRIBE`",
    "`UNSUBSCRIBE`",
    "`SMTP`",
    "`BODY[]`",
)

READ_ONLY_SESSION_METHODS = {
    "list_folders",
    "examine",
    "uid_search",
    "uid_fetch_size",
    "uid_fetch_bodystructure",
    "uid_fetch_peek",
}

FORBIDDEN_SOURCE_SNIPPETS = (
    "import smtplib",
    "from smtplib",
    "smtplib.",
    "SMTP(",
    "SMTP_SSL(",
    "BODY[]",
)

IMAP_RECEIVER_NAMES = {
    "client",
    "_client",
    "imap",
    "_imap",
    "connection",
    "_connection",
    "session",
    "_session",
}

FORBIDDEN_IMAP_METHODS = {
    "append",
    "close",
    "copy",
    "create",
    "delete",
    "expunge",
    "move",
    "rename",
    "store",
    "subscribe",
    "unsubscribe",
}


def _receiver_name(value: ast.expr) -> str | None:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def _imap_call_violations(tree: ast.AST) -> list[str]:
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        receiver = _receiver_name(node.func.value)
        if receiver not in IMAP_RECEIVER_NAMES:
            continue
        method = node.func.attr.lower()
        if method in FORBIDDEN_IMAP_METHODS or method in {"fetch", "_simple_command"}:
            violations.append(f"line {node.lineno}: forbidden IMAP method {method}")
            continue
        if method != "uid":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            violations.append(f"line {node.lineno}: dynamic UID command")
            continue
        command = node.args[0].value
        if not isinstance(command, str) or command.upper() not in {"SEARCH", "FETCH"}:
            violations.append(f"line {node.lineno}: forbidden UID command")
            continue
        if command.upper() != "FETCH":
            continue
        for argument in node.args[1:]:
            if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                continue
            selector = argument.value.upper()
            if "BODY[]" in selector or "RFC822" in selector:
                violations.append(f"line {node.lineno}: non-PEEK body selector")
            if re.search(r"\bBODY\[", selector) and "BODY.PEEK[" not in selector:
                violations.append(f"line {node.lineno}: non-PEEK body section")
    return violations


class MailboxTransportConstraintTests(unittest.TestCase):
    def test_transport_guard_rejects_write_dynamic_and_nonpeek_calls(self) -> None:
        samples = {
            "write method": "self._client.store('1', '+FLAGS', '(Seen)')",
            "dynamic UID command": "self._client.uid(command, '1')",
            "UID write command": "self._client.uid('STORE', '1', '+FLAGS')",
            "non-PEEK body": "self._client.uid('FETCH', '1', 'BODY[]')",
            "RFC822 body": "self._client.uid('FETCH', '1', 'RFC822')",
            "raw command": "self._client._simple_command('EXPUNGE')",
        }

        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(_imap_call_violations(ast.parse(sample)))

    def test_constraint_docs_define_fixed_read_only_transport_policy(self) -> None:
        for path in POLICY_DOCS:
            text = read_text(path)
            with self.subTest(path=path, marker="policy heading"):
                self.assertIn("Authorized mailbox transport policy", text)
            with self.subTest(path=path, marker="fixed endpoint"):
                self.assertIn("imap.exmail.qq.com:993", text)
            with self.subTest(path=path, marker="no arbitrary passthrough"):
                self.assertIn("no arbitrary IMAP command passthrough", text)
            for operation in ALLOWED_IMAP_OPERATIONS:
                with self.subTest(path=path, allowed=operation):
                    self.assertIn(operation, text)
            for operation in FORBIDDEN_TRANSPORT_OPERATIONS:
                with self.subTest(path=path, forbidden=operation):
                    self.assertIn(operation, text)

    def test_importer_sources_expose_only_read_only_imap_and_no_smtp(self) -> None:
        source_paths: list[Path] = []
        package = ROOT / "backend" / "mailbox_ingest"
        if package.exists():
            source_paths.extend(package.rglob("*.py"))
        cli = ROOT / "scripts" / "manage_mailbox_vault.py"
        if cli.exists():
            source_paths.append(cli)

        for path in source_paths:
            text = read_text(path)
            for snippet in FORBIDDEN_SOURCE_SNIPPETS:
                with self.subTest(path=path, forbidden=snippet):
                    self.assertNotIn(snippet, text)

        session_path = package / "imap_readonly.py"
        if not session_path.exists():
            return
        tree = ast.parse(read_text(session_path))
        self.assertFalse(_imap_call_violations(tree))
        session_classes = [
            node
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "ReadOnlyImapSession"
        ]
        self.assertEqual(len(session_classes), 1)
        public_methods = {
            node.name
            for node in session_classes[0].body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not node.name.startswith("_")
        }
        self.assertEqual(public_methods, READ_ONLY_SESSION_METHODS)


if __name__ == "__main__":
    unittest.main()
