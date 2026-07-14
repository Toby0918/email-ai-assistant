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

WRAPPER_ONLY_IMAP_METHODS = {
    "list",
    "login",
    "logout",
    "select",
    "uid",
}

DIRECT_NON_UID_METHODS = {
    "fetch",
    "search",
}

RAW_CLIENT_ATTRIBUTES_OUTSIDE_WRAPPER = {
    "_client",
    "_imap_client",
    "client",
}

WRAPPER_RAW_CLIENT_ATTRIBUTE = "_imap_client"

FIXED_FETCH_SELECTORS = {
    "(BODYSTRUCTURE)",
    "(RFC822.SIZE)",
    "(RFC822.SIZE INTERNALDATE)",
}

IMAP_CONSTRUCTORS = {
    "IMAP4",
    "IMAP4_SSL",
    "IMAP4_stream",
}

WRAPPER_IMAP_CONSTRUCTOR = "IMAP4_SSL"

SMTP_CONSTRUCTORS = {
    "SMTP",
    "SMTP_SSL",
}

STATIC_BODY_PEEK_SELECTOR = re.compile(
    r"^\(BODY\.PEEK\[(?:HEADER|[1-9][0-9]*(?:\.[1-9][0-9]*)*(?:\.MIME|\.TEXT)?)\]\)$",
    re.IGNORECASE,
)


def _call_name(value: ast.expr) -> str | None:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return None


def _module_root(module_name: str | None) -> str | None:
    if module_name is None:
        return None
    return module_name.split(".", 1)[0]


def _is_allowed_fetch_selector(selector: ast.expr) -> bool:
    if not isinstance(selector, ast.Constant) or not isinstance(selector.value, str):
        return False
    value = selector.value.strip().upper()
    return value in FIXED_FETCH_SELECTORS or bool(
        STATIC_BODY_PEEK_SELECTOR.fullmatch(value)
    )


def _is_canonical_wrapper_client(value: ast.expr) -> bool:
    return (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id == "self"
        and value.attr == WRAPPER_RAW_CLIENT_ATTRIBUTE
    )


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }


def _is_constructor_field_assignment(
    node: ast.Attribute,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    parent = parents.get(node)
    if isinstance(parent, ast.Assign):
        if len(parent.targets) != 1 or parent.targets[0] is not node:
            return False
    elif isinstance(parent, ast.AnnAssign):
        if parent.target is not node:
            return False
    else:
        return False

    current: ast.AST | None = parent
    enclosing_function: ast.AST | None = None
    enclosing_class: ast.ClassDef | None = None
    while current is not None:
        current = parents.get(current)
        if enclosing_function is None and isinstance(
            current,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda),
        ):
            enclosing_function = current
            continue
        if enclosing_function is not None and isinstance(current, ast.ClassDef):
            enclosing_class = current
            break
    return (
        isinstance(enclosing_function, ast.FunctionDef)
        and enclosing_function.name == "__init__"
        and enclosing_class is not None
        and enclosing_class.name == "ReadOnlyImapSession"
    )


def _is_direct_allowlisted_client_call(
    node: ast.Attribute,
    parents: dict[ast.AST, ast.AST],
) -> bool:
    method_access = parents.get(node)
    if (
        not isinstance(method_access, ast.Attribute)
        or method_access.value is not node
        or method_access.attr.lower() not in WRAPPER_ONLY_IMAP_METHODS
    ):
        return False
    call = parents.get(method_access)
    return isinstance(call, ast.Call) and call.func is method_access


def _canonical_client_access_violations(tree: ast.AST) -> list[str]:
    parents = _parent_map(tree)
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute) or not _is_canonical_wrapper_client(node):
            continue
        if _is_constructor_field_assignment(node, parents):
            continue
        if _is_direct_allowlisted_client_call(node, parents):
            continue
        violations.append(
            f"line {node.lineno}: raw IMAP client escapes its allowlisted call boundary"
        )
    return violations


def _is_literal_readonly_select(node: ast.Call) -> bool:
    if len(node.args) > 1:
        return False
    if any(keyword.arg not in {"mailbox", "readonly"} for keyword in node.keywords):
        return False
    readonly_keywords = [
        keyword for keyword in node.keywords if keyword.arg == "readonly"
    ]
    mailbox_keywords = [
        keyword for keyword in node.keywords if keyword.arg == "mailbox"
    ]
    if len(readonly_keywords) != 1 or len(mailbox_keywords) > 1:
        return False
    if node.args and mailbox_keywords:
        return False
    readonly = readonly_keywords[0].value
    return isinstance(readonly, ast.Constant) and readonly.value is True


def _imap_call_violations(
    tree: ast.AST,
    *,
    is_wrapper: bool = True,
) -> list[str]:
    violations = _canonical_client_access_violations(tree) if is_wrapper else []
    if not is_wrapper:
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr in RAW_CLIENT_ATTRIBUTES_OUTSIDE_WRAPPER
            ):
                violations.append(
                    f"line {node.lineno}: raw IMAP client attribute outside wrapper"
                )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        method = node.func.attr.lower()
        if is_wrapper and _is_canonical_wrapper_client(node.func.value):
            if method not in WRAPPER_ONLY_IMAP_METHODS:
                violations.append(
                    f"line {node.lineno}: raw IMAP method {method} is not allowlisted"
                )
                continue
        if is_wrapper and method in FORBIDDEN_IMAP_METHODS:
            violations.append(f"line {node.lineno}: forbidden IMAP method {method}")
            continue
        if method == "_simple_command":
            violations.append(f"line {node.lineno}: raw IMAP command passthrough")
            continue
        if is_wrapper and method in DIRECT_NON_UID_METHODS:
            violations.append(f"line {node.lineno}: non-UID IMAP method {method}")
            continue
        if is_wrapper and method in WRAPPER_ONLY_IMAP_METHODS:
            if not _is_canonical_wrapper_client(node.func.value):
                violations.append(
                    f"line {node.lineno}: raw IMAP method {method} must use "
                    f"self.{WRAPPER_RAW_CLIENT_ATTRIBUTE}"
                )
                continue
            if method == "select" and not _is_literal_readonly_select(node):
                violations.append(
                    f"line {node.lineno}: select must use one literal readonly=True"
                )
                continue
        if not is_wrapper and method in WRAPPER_ONLY_IMAP_METHODS:
            violations.append(
                f"line {node.lineno}: raw IMAP method {method} outside wrapper"
            )
            continue
        if method != "uid":
            continue
        if (
            not node.args
            or not isinstance(node.args[0], ast.Constant)
            or not isinstance(node.args[0].value, str)
        ):
            violations.append(f"line {node.lineno}: dynamic UID command")
            continue
        command = node.args[0].value
        if command.upper() not in {"SEARCH", "FETCH"}:
            violations.append(f"line {node.lineno}: forbidden UID command")
            continue
        if command.upper() != "FETCH":
            continue
        if len(node.args) != 3 or node.keywords:
            violations.append(f"line {node.lineno}: invalid UID FETCH call shape")
            continue
        if not _is_allowed_fetch_selector(node.args[2]):
            violations.append(
                f"line {node.lineno}: dynamic or non-allowlisted FETCH selector"
            )
    return violations


def _transport_import_violations(
    tree: ast.AST,
    *,
    is_wrapper: bool,
) -> list[str]:
    violations: list[str] = []
    imap_constructor_aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if _module_root(node.module) != "imaplib":
            continue
        for alias in node.names:
            if alias.name in IMAP_CONSTRUCTORS:
                imap_constructor_aliases[alias.asname or alias.name] = alias.name

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {_module_root(alias.name) for alias in node.names}
            if "smtplib" in roots:
                violations.append(f"line {node.lineno}: SMTP import")
            if "imaplib" in roots and not is_wrapper:
                violations.append(f"line {node.lineno}: IMAP import outside wrapper")
            continue
        if isinstance(node, ast.ImportFrom):
            root = _module_root(node.module)
            if root == "smtplib":
                violations.append(f"line {node.lineno}: SMTP import")
            if root == "imaplib" and not is_wrapper:
                violations.append(f"line {node.lineno}: IMAP import outside wrapper")
            if root == "imaplib" and is_wrapper:
                for alias in node.names:
                    if (
                        alias.name == "*"
                        or (
                            alias.name in IMAP_CONSTRUCTORS
                            and alias.name != WRAPPER_IMAP_CONSTRUCTOR
                        )
                    ):
                        violations.append(
                            f"line {node.lineno}: non-TLS IMAP constructor import"
                        )
            continue
        if not isinstance(node, ast.Call):
            continue
        constructor = _call_name(node.func)
        constructor = imap_constructor_aliases.get(constructor or "", constructor)
        if constructor in SMTP_CONSTRUCTORS:
            violations.append(f"line {node.lineno}: SMTP construction")
        if constructor not in IMAP_CONSTRUCTORS:
            continue
        if not is_wrapper:
            violations.append(f"line {node.lineno}: IMAP construction outside wrapper")
        elif constructor != WRAPPER_IMAP_CONSTRUCTOR:
            violations.append(f"line {node.lineno}: non-TLS IMAP construction")
    return violations


def _source_transport_violations(
    tree: ast.AST,
    *,
    is_wrapper: bool,
) -> list[str]:
    return [
        *_transport_import_violations(tree, is_wrapper=is_wrapper),
        *_imap_call_violations(tree, is_wrapper=is_wrapper),
    ]


class MailboxTransportConstraintTests(unittest.TestCase):
    def test_transport_guard_rejects_write_dynamic_and_nonpeek_calls(self) -> None:
        samples = {
            "write method": "self._imap_client.store('1', '+FLAGS', '(Seen)')",
            "dynamic UID command": "self._imap_client.uid(command, '1')",
            "UID write command": "self._imap_client.uid('STORE', '1', '+FLAGS')",
            "non-PEEK body": "self._imap_client.uid('FETCH', '1', 'BODY[]')",
            "RFC822 body": "self._imap_client.uid('FETCH', '1', 'RFC822')",
            "raw command": "self._imap_client._simple_command('EXPUNGE')",
            "RFC822 text body": (
                "self._imap_client.uid('FETCH', '1', '(RFC822.TEXT)')"
            ),
            "RFC822 header body": (
                "self._imap_client.uid('FETCH', '1', '(RFC822.HEADER)')"
            ),
        }

        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(_imap_call_violations(ast.parse(sample)))

    def test_transport_guard_rejects_receiver_independent_and_nonallowlisted_calls(
        self,
    ) -> None:
        samples = {
            "alternate receiver write": (
                "self._imap_client.store('1', '+FLAGS', '(Seen)')",
                True,
            ),
            "raw LIST outside wrapper": ("client.list()", False),
            "UID outside wrapper": ("client.uid('SEARCH', 'ALL')", False),
            "private raw client outside wrapper": (
                "session._client.store('1', '+FLAGS', '(Seen)')",
                False,
            ),
            "canonical raw client outside wrapper": (
                "session._imap_client.store('1', '+FLAGS', '(Seen)')",
                False,
            ),
            "public raw client outside wrapper": (
                "session.client.store('1', '+FLAGS', '(Seen)')",
                False,
            ),
            "noncanonical raw client inside wrapper": (
                "self._client.uid('SEARCH', None, 'ALL')",
                True,
            ),
            "SELECT defaults to writable": (
                "self._imap_client.select('INBOX')",
                True,
            ),
            "SELECT explicitly writable": (
                "self._imap_client.select('INBOX', readonly=False)",
                True,
            ),
            "SELECT dynamic readonly": (
                "self._imap_client.select('INBOX', readonly=readonly)",
                True,
            ),
            "SELECT positional readonly": (
                "self._imap_client.select('INBOX', True)",
                True,
            ),
            "SELECT duplicate readonly": (
                "self._imap_client.select('INBOX', True, readonly=True)",
                True,
            ),
            "canonical raw _command": (
                "self._imap_client._command('EXPUNGE')",
                True,
            ),
            "canonical raw xatom": (
                "self._imap_client.xatom('IDLE')",
                True,
            ),
            "canonical raw send": (
                "self._imap_client.send(b'NOOP\\r\\n')",
                True,
            ),
            "canonical raw capability": (
                "self._imap_client.capability()",
                True,
            ),
            "canonical direct FETCH": (
                "self._imap_client.fetch('1', '(RFC822.SIZE)')",
                True,
            ),
            "canonical direct SEARCH": (
                "self._imap_client.search(None, 'ALL')",
                True,
            ),
            "raw client assignment alias": (
                "client = self._imap_client\nclient.send(b'NOOP\\r\\n')",
                True,
            ),
            "raw client return": (
                "def expose(self):\n    return self._imap_client",
                True,
            ),
            "raw client argument": (
                "consume(self._imap_client)",
                True,
            ),
            "dynamic FETCH selector": (
                "self._imap_client.uid('FETCH', '1', selector)",
                True,
            ),
            "unimplemented named FETCH builder": (
                "self._imap_client.uid('FETCH', '1', "
                "build_validated_fetch_selector(section))",
                True,
            ),
            "qualified untrusted FETCH builder": (
                "self._imap_client.uid('FETCH', '1', "
                "evil.build_validated_fetch_selector(section))",
                True,
            ),
            "non-allowlisted FETCH selector": (
                "self._imap_client.uid('FETCH', '1', '(FLAGS)')",
                True,
            ),
        }

        for label, (sample, is_wrapper) in samples.items():
            with self.subTest(label=label):
                self.assertTrue(
                    _source_transport_violations(
                        ast.parse(sample),
                        is_wrapper=is_wrapper,
                    )
                )

    def test_transport_guard_allows_fixed_read_only_selectors(
        self,
    ) -> None:
        samples = (
            "self._imap_client.list()",
            "self._imap_client.select('INBOX', readonly=True)",
            "self._imap_client.select(mailbox='INBOX', readonly=True)",
            "self._imap_client.uid('SEARCH', None, 'ALL')",
            "self._imap_client.uid('FETCH', '1', '(RFC822.SIZE)')",
            "self._imap_client.uid('FETCH', '1', '(BODYSTRUCTURE)')",
            "self._imap_client.uid('FETCH', '1', '(BODY.PEEK[HEADER])')",
        )

        for sample in samples:
            with self.subTest(sample=sample):
                self.assertFalse(
                    _source_transport_violations(
                        ast.parse(sample),
                        is_wrapper=True,
                    )
                )

        constructor_assignment = (
            "class ReadOnlyImapSession:\n"
            "    def __init__(self, client):\n"
            "        self._imap_client = client"
        )
        self.assertFalse(
            _source_transport_violations(
                ast.parse(constructor_assignment),
                is_wrapper=True,
            )
        )

        non_wrapper_samples = (
            "connection.close()",
            "session._connection.close()",
            "records.append(record)",
            "record.copy()",
            "repository.delete(record_id)",
        )
        for sample in non_wrapper_samples:
            with self.subTest(sample=sample, scope="non-wrapper collision control"):
                self.assertFalse(
                    _source_transport_violations(
                        ast.parse(sample),
                        is_wrapper=False,
                    )
                )

    def test_transport_import_guard_enforces_wrapper_ownership(self) -> None:
        forbidden_samples = {
            "IMAP import outside wrapper": ("import imaplib", False),
            "IMAP from-import outside wrapper": (
                "from imaplib import IMAP4_SSL",
                False,
            ),
            "qualified IMAP construction outside wrapper": (
                "imaplib.IMAP4_SSL()",
                False,
            ),
            "bare IMAP construction outside wrapper": ("IMAP4_SSL()", False),
            "stream IMAP construction outside wrapper": ("IMAP4_stream()", False),
            "plaintext IMAP construction in wrapper": (
                "import imaplib\nimaplib.IMAP4()",
                True,
            ),
            "plaintext IMAP import in wrapper": (
                "from imaplib import IMAP4",
                True,
            ),
            "stream IMAP construction in wrapper": (
                "import imaplib\nimaplib.IMAP4_stream()",
                True,
            ),
            "aliased plaintext IMAP construction in wrapper": (
                "from imaplib import IMAP4 as IMAP4_SSL\nIMAP4_SSL()",
                True,
            ),
            "SMTP import in wrapper": ("import smtplib", True),
            "qualified SMTP construction": ("smtplib.SMTP_SSL()", False),
            "bare SMTP construction": ("SMTP()", False),
        }

        for label, (sample, is_wrapper) in forbidden_samples.items():
            with self.subTest(label=label):
                self.assertTrue(
                    _transport_import_violations(
                        ast.parse(sample),
                        is_wrapper=is_wrapper,
                    )
                )

        wrapper_sample = "import imaplib\nimaplib.IMAP4_SSL()"
        self.assertFalse(
            _transport_import_violations(
                ast.parse(wrapper_sample),
                is_wrapper=True,
            )
        )

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

        session_path = package / "imap_readonly.py"
        for path in source_paths:
            tree = ast.parse(read_text(path))
            with self.subTest(path=path, guard="transport AST"):
                self.assertFalse(
                    _source_transport_violations(
                        tree,
                        is_wrapper=path.resolve() == session_path.resolve(),
                    )
                )

        if not session_path.exists():
            return
        tree = ast.parse(read_text(session_path))
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
