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

UID_BOUNDARY_DOCS = (
    ROOT / "docs" / "constraints" / "architecture_constraints.md",
    ROOT / "docs" / "operations" / "authorized_mailbox_ingest_task_brief.md",
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

RAW_IMAP_METHOD_ALLOWLIST = {
    "list",
    "login",
    "logout",
    "response",
    "select",
    "uid",
}

WRAPPER_RAW_CLIENT_ATTRIBUTE = "_imap_client"
MAX_IMAP_UID = 4_294_967_295
SINGLE_UID_LITERAL = re.compile(r"^[1-9][0-9]*$")

FIXED_FETCH_SELECTORS = {
    "(BODYSTRUCTURE)",
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
    r"^\(BODY\.PEEK\[(?:HEADER|[1-9][0-9]*(?:\.[1-9][0-9]*)*)\](?:<[0-9]+\.[1-9][0-9]*>)?\)$",
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


def _is_single_uid_literal(value: ast.expr) -> bool:
    if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
        return False
    if not SINGLE_UID_LITERAL.fullmatch(value.value):
        return False
    return int(value.value) <= MAX_IMAP_UID


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


def _imap_constructor_sources(tree: ast.AST) -> tuple[set[str], set[str]]:
    constructor_names: set[str] = set()
    module_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "imaplib":
                    module_names.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and _module_root(node.module) == "imaplib":
            for alias in node.names:
                if alias.name in IMAP_CONSTRUCTORS:
                    constructor_names.add(alias.asname or alias.name)

    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if value is None or not _is_imap_constructor_source(
                value,
                constructor_names=constructor_names,
                module_names=module_names,
            ):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in constructor_names:
                    constructor_names.add(target.id)
                    changed = True
    return constructor_names, module_names


def _is_imap_constructor_source(
    value: ast.expr,
    *,
    constructor_names: set[str],
    module_names: set[str],
) -> bool:
    if isinstance(value, ast.Name):
        return value.id in constructor_names
    return (
        isinstance(value, ast.Attribute)
        and isinstance(value.value, ast.Name)
        and value.value.id in module_names
        and value.attr in IMAP_CONSTRUCTORS
    )


def _is_raw_imap_expression(
    value: ast.expr | None,
    *,
    tainted_names: set[str],
    constructor_names: set[str],
    module_names: set[str],
) -> bool:
    if value is None:
        return False
    if isinstance(value, ast.Name):
        return value.id in tainted_names
    if isinstance(value, ast.Attribute):
        return (
            isinstance(value.ctx, ast.Load)
            and (
                value.attr == WRAPPER_RAW_CLIENT_ATTRIBUTE
                or _is_raw_imap_expression(
                    value.value,
                    tainted_names=tainted_names,
                    constructor_names=constructor_names,
                    module_names=module_names,
                )
            )
        )
    if not isinstance(value, ast.Call):
        return False
    if _is_imap_constructor_source(
        value.func,
        constructor_names=constructor_names,
        module_names=module_names,
    ):
        return True
    return (
        isinstance(value.func, ast.Name)
        and value.func.id == "getattr"
        and len(value.args) >= 2
        and isinstance(value.args[1], ast.Constant)
        and value.args[1].value == WRAPPER_RAW_CLIENT_ATTRIBUTE
    )


def _raw_imap_alias_names(
    tree: ast.AST,
    *,
    constructor_names: set[str],
    module_names: set[str],
) -> set[str]:
    tainted_names: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                value = node.value
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                value = node.value
                targets = [node.target]
            else:
                continue
            if not _is_raw_imap_expression(
                value,
                tainted_names=tainted_names,
                constructor_names=constructor_names,
                module_names=module_names,
            ):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in tainted_names:
                    tainted_names.add(target.id)
                    changed = True
    return tainted_names


def _raw_imap_escape_violations(
    tree: ast.AST,
    *,
    tainted_names: set[str],
    constructor_names: set[str],
    module_names: set[str],
) -> list[str]:
    parents = _parent_map(tree)
    violations: list[str] = []

    def is_raw(value: ast.expr | None) -> bool:
        return _is_raw_imap_expression(
            value,
            tainted_names=tainted_names,
            constructor_names=constructor_names,
            module_names=module_names,
        )

    def contains_raw(value: ast.AST | None) -> bool:
        if value is None:
            return False
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Attribute):
            if is_raw(value.func.value):
                arguments = [
                    *value.args,
                    *(keyword.value for keyword in value.keywords),
                ]
                return any(contains_raw(argument) for argument in arguments)
        if isinstance(value, ast.expr) and is_raw(value):
            return True
        return any(contains_raw(child) for child in ast.iter_child_nodes(value))

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = node.value
            targets = node.targets
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            targets = [node.target]
        else:
            value = None
            targets = []
        if targets:
            for target in targets:
                allowed_constructor_field = (
                    isinstance(target, ast.Attribute)
                    and _is_canonical_wrapper_client(target)
                    and _is_constructor_field_assignment(target, parents)
                )
                stores_raw_field = (
                    isinstance(target, ast.Attribute)
                    and target.attr == WRAPPER_RAW_CLIENT_ATTRIBUTE
                )
                if (stores_raw_field or contains_raw(value)) and not allowed_constructor_field:
                    violations.append(
                        f"line {node.lineno}: raw IMAP client assignment escape"
                    )

        if isinstance(node, ast.NamedExpr) and (
            contains_raw(node.value) or contains_raw(node.target)
        ):
            violations.append(f"line {node.lineno}: raw IMAP client walrus escape")

        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)) and contains_raw(
            node.value
        ):
            violations.append(f"line {node.lineno}: raw IMAP client return escape")
        if not isinstance(node, ast.Call):
            continue
        arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
        if any(contains_raw(argument) for argument in arguments):
            violations.append(f"line {node.lineno}: raw IMAP client argument escape")
    return violations


_FETCH_VALIDATORS = {
    "validate_single_uid_fetch_target",
    "validate_fetch_selector",
}


def _is_direct_validator_call(
    value: ast.expr,
    *,
    function_name: str,
    argument_name: str,
) -> bool:
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Name)
        and value.func.id == function_name
        and len(value.args) == 1
        and not value.keywords
        and isinstance(value.args[0], ast.Name)
        and value.args[0].id == argument_name
    )


def _fetch_validator_binding_violations(tree: ast.AST) -> list[str]:
    parents = _parent_map(tree)
    violations: list[str] = []

    def contains_reference(value: ast.AST | None) -> bool:
        if value is None:
            return False
        for child in ast.walk(value):
            if not isinstance(child, ast.Name) or child.id not in _FETCH_VALIDATORS:
                continue
            parent = parents.get(child)
            if isinstance(parent, ast.Call) and parent.func is child:
                continue
            return True
        return False

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            aliases = node.names
            if any((alias.asname or alias.name) in _FETCH_VALIDATORS for alias in aliases):
                violations.append(f"line {node.lineno}: FETCH validator import escape")
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr)):
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
            )
            value = node.value
            for target in targets:
                names = {
                    child.id
                    for child in ast.walk(target)
                    if isinstance(child, ast.Name)
                }
                if names & _FETCH_VALIDATORS:
                    violations.append(
                        f"line {node.lineno}: FETCH validator reassignment escape"
                    )
            if contains_reference(value):
                violations.append(f"line {node.lineno}: FETCH validator alias escape")
        if isinstance(node, (ast.Return, ast.Yield, ast.YieldFrom)) and contains_reference(
            node.value
        ):
            violations.append(f"line {node.lineno}: FETCH validator return escape")
        if isinstance(node, ast.Call):
            arguments = [*node.args, *(keyword.value for keyword in node.keywords)]
            if any(contains_reference(argument) for argument in arguments):
                violations.append(f"line {node.lineno}: FETCH validator argument escape")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            arguments = {
                argument.arg
                for argument in (
                    *node.args.posonlyargs,
                    *node.args.args,
                    *node.args.kwonlyargs,
                )
            }
            if node.args.vararg:
                arguments.add(node.args.vararg.arg)
            if node.args.kwarg:
                arguments.add(node.args.kwarg.arg)
            if arguments & _FETCH_VALIDATORS:
                violations.append(f"line {node.lineno}: FETCH validator shadow escape")
            defaults = [*node.args.defaults, *node.args.kw_defaults]
            if any(contains_reference(default) for default in defaults):
                violations.append(f"line {node.lineno}: FETCH validator default escape")
            if (
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name in _FETCH_VALIDATORS
                and not isinstance(parents.get(node), ast.Module)
            ):
                violations.append(f"line {node.lineno}: nested FETCH validator")
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


def _is_exact_uid_search(node: ast.Call) -> bool:
    return (
        len(node.args) == 4
        and not node.keywords
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == "SEARCH"
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value is None
        and isinstance(node.args[2], ast.Constant)
        and node.args[2].value == "SINCE"
        and isinstance(node.args[3], ast.Name)
        and node.args[3].id == "date"
    )


def _imap_call_violations(
    tree: ast.AST,
    *,
    is_wrapper: bool = True,
) -> list[str]:
    constructor_names, module_names = _imap_constructor_sources(tree)
    tainted_names = _raw_imap_alias_names(
        tree,
        constructor_names=constructor_names,
        module_names=module_names,
    )
    violations = _raw_imap_escape_violations(
        tree,
        tainted_names=tainted_names,
        constructor_names=constructor_names,
        module_names=module_names,
    )
    violations.extend(_fetch_validator_binding_violations(tree))

    def is_raw(value: ast.expr | None) -> bool:
        return _is_raw_imap_expression(
            value,
            tainted_names=tainted_names,
            constructor_names=constructor_names,
            module_names=module_names,
        )

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if not is_raw(node.func.value):
            continue
        method = node.func.attr.lower()
        canonical_receiver = _is_canonical_wrapper_client(node.func.value)
        if not is_wrapper or not canonical_receiver:
            violations.append(
                f"line {node.lineno}: raw IMAP method {method} must use "
                f"self.{WRAPPER_RAW_CLIENT_ATTRIBUTE} inside the wrapper"
            )
        if method not in RAW_IMAP_METHOD_ALLOWLIST:
            violations.append(
                f"line {node.lineno}: raw IMAP method {method} is not allowlisted"
            )
            continue
        if method == "select" and not _is_literal_readonly_select(node):
            violations.append(
                f"line {node.lineno}: select must use one literal readonly=True"
            )
            continue
        if method == "response":
            if (
                len(node.args) != 1
                or node.keywords
                or not isinstance(node.args[0], ast.Constant)
                or node.args[0].value != "UIDVALIDITY"
            ):
                violations.append(
                    f"line {node.lineno}: response cache access must be UIDVALIDITY"
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
        if command.upper() == "SEARCH":
            if not _is_exact_uid_search(node):
                violations.append(f"line {node.lineno}: invalid UID SEARCH call shape")
            continue
        if command.upper() != "FETCH":
            continue
        if len(node.args) != 3 or node.keywords:
            violations.append(f"line {node.lineno}: invalid UID FETCH call shape")
            continue
        dynamic_uid = _is_direct_validator_call(
            node.args[1],
            function_name="validate_single_uid_fetch_target",
            argument_name="uid",
        )
        dynamic_selector = _is_direct_validator_call(
            node.args[2],
            function_name="validate_fetch_selector",
            argument_name="selector",
        )
        if dynamic_uid != dynamic_selector:
            violations.append(
                f"line {node.lineno}: UID and selector validators must be paired"
            )
            continue
        if not dynamic_uid and not _is_single_uid_literal(node.args[1]):
            violations.append(
                f"line {node.lineno}: UID FETCH target must be one finite literal UID"
            )
            continue
        if not dynamic_selector and not _is_allowed_fetch_selector(node.args[2]):
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
    def test_issue_ten_ratifies_future_manual_sync_without_adding_a_command(self) -> None:
        adr = read_text(
            ROOT / "docs" / "decisions" /
            "0008-bounded-corpus-to-runtime-handoffs.md"
        )
        cli = read_text(ROOT / "scripts" / "manage_mailbox_vault.py")

        for marker in (
            "administrator-triggered incremental synchronization",
            "manual",
            "read-only",
            "exact current inventory fingerprint",
            "fixed `imap.exmail.qq.com:993` endpoint",
            "no browser, normal API, scheduler, cleanup, polling, or background trigger",
            "not implemented by this decision",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, adr)
        self.assertNotIn('"sync"', cli)
        self.assertIn(
            'NETWORK_COMMANDS = frozenset({"inventory", "scan", "attachments"})',
            cli,
        )

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
            "canonical raw client outside wrapper": (
                "session._imap_client.store('1', '+FLAGS', '(Seen)')",
                False,
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
            "getattr raw client alias": (
                "raw = getattr(self, '_imap_client')\n"
                "raw.send(b'NOOP\\r\\n')",
                True,
            ),
            "constructor raw client alias": (
                "import imaplib\n"
                "raw = imaplib.IMAP4_SSL()\n"
                "raw.send(b'NOOP\\r\\n')",
                True,
            ),
            "aliased constructor raw client": (
                "import imaplib\n"
                "constructor = imaplib.IMAP4_SSL\n"
                "raw = constructor()\n"
                "raw.send(b'NOOP\\r\\n')",
                True,
            ),
            "constructor raw client return": (
                "import imaplib\n"
                "def expose():\n"
                "    return imaplib.IMAP4_SSL()",
                True,
            ),
            "constructor raw client argument": (
                "import imaplib\n"
                "consume(imaplib.IMAP4_SSL())",
                True,
            ),
            "raw socket chain": (
                "self._imap_client.sock.send(b'NOOP\\r\\n')",
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

    def test_transport_guard_applies_imap_method_names_only_to_raw_receivers(
        self,
    ) -> None:
        samples = (
            "repository.list()",
            "vault_index.select()",
            "protector.client.protect(data)",
            "folders.append(folder)",
            "metadata.copy()",
            "temp.close()",
            "client.uid('SEARCH', None, 'ALL')",
            "self._client.store('1', '+FLAGS', '(Seen)')",
            "factory.IMAP4_SSL().list()",
        )

        for sample in samples:
            with self.subTest(sample=sample):
                self.assertFalse(
                    _source_transport_violations(
                        ast.parse(sample),
                        is_wrapper=True,
                    )
                )

    def test_uid_fetch_requires_one_finite_literal_uid(self) -> None:
        rejected_targets = (
            "uid",
            "f'{uid}'",
            "'*'",
            "'1:*'",
            "'1:4'",
            "'1,4'",
            "'0'",
            "'-1'",
            "'4294967296'",
        )

        for target in rejected_targets:
            sample = (
                "self._imap_client.uid('FETCH', "
                f"{target}, '(BODYSTRUCTURE)')"
            )
            with self.subTest(target=target):
                self.assertTrue(_imap_call_violations(ast.parse(sample)))

        for target in ("'1'", "'4294967295'"):
            sample = (
                "self._imap_client.uid('FETCH', "
                f"{target}, '(BODYSTRUCTURE)')"
            )
            with self.subTest(target=target):
                self.assertFalse(_imap_call_violations(ast.parse(sample)))

        canonical_dynamic = (
            "self._imap_client.uid('FETCH', "
            "validate_single_uid_fetch_target(uid), "
            "validate_fetch_selector(selector))"
        )
        self.assertFalse(_imap_call_violations(ast.parse(canonical_dynamic)))

    def test_dynamic_fetch_validators_cannot_be_aliased_or_escaped(self) -> None:
        samples = {
            "qualified UID validator": (
                "self._imap_client.uid('FETCH', validators."
                "validate_single_uid_fetch_target(uid), "
                "validate_fetch_selector(selector))"
            ),
            "qualified selector validator": (
                "self._imap_client.uid('FETCH', "
                "validate_single_uid_fetch_target(uid), validators."
                "validate_fetch_selector(selector))"
            ),
            "UID validator alias": (
                "target = validate_single_uid_fetch_target\n"
                "self._imap_client.uid('FETCH', target(uid), "
                "validate_fetch_selector(selector))"
            ),
            "selector validator alias": (
                "builder = validate_fetch_selector\n"
                "self._imap_client.uid('FETCH', "
                "validate_single_uid_fetch_target(uid), builder(selector))"
            ),
            "validator reassignment": (
                "validate_fetch_selector = unsafe\n"
                "self._imap_client.uid('FETCH', "
                "validate_single_uid_fetch_target(uid), "
                "validate_fetch_selector(selector))"
            ),
            "validator import": (
                "from unsafe import validate_fetch_selector\n"
                "self._imap_client.uid('FETCH', "
                "validate_single_uid_fetch_target(uid), "
                "validate_fetch_selector(selector))"
            ),
            "validator parameter shadow": (
                "def run(validate_fetch_selector):\n"
                "    self._imap_client.uid('FETCH', "
                "validate_single_uid_fetch_target(uid), "
                "validate_fetch_selector(selector))"
            ),
            "validator nested definition": (
                "def run():\n"
                "    def validate_fetch_selector(value):\n"
                "        return value\n"
                "    self._imap_client.uid('FETCH', "
                "validate_single_uid_fetch_target(uid), "
                "validate_fetch_selector(selector))"
            ),
        }

        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(_imap_call_violations(ast.parse(sample)))

    def test_validator_references_cannot_escape_recursive_expression_shapes(self) -> None:
        samples = {
            "list storage": "box = [validate_fetch_selector]",
            "tuple storage": "box = (validate_single_uid_fetch_target,)",
            "dict storage": "box = {'v': validate_fetch_selector}",
            "set storage": "box = {validate_fetch_selector}",
            "subscript alias": "box = [validate_fetch_selector][0]",
            "return": "def expose():\n    return validate_single_uid_fetch_target",
            "yield": "def expose():\n    yield validate_fetch_selector",
            "argument": "consume(validate_fetch_selector)",
            "lambda": "callback = lambda: validate_fetch_selector",
            "comprehension": (
                "box = [validate_fetch_selector for _ in values]"
            ),
            "nested alias": (
                "box = {'v': [validate_fetch_selector]}\n"
                "alias = box['v'][0]"
            ),
        }
        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(_imap_call_violations(ast.parse(sample)))

    def test_uid_search_and_obsolete_size_selector_shapes_are_exact(self) -> None:
        rejected = (
            "self._imap_client.uid('SEARCH', None, 'ALL')",
            "self._imap_client.uid('search', None, 'SINCE', date)",
            "self._imap_client.uid('SEARCH', None, 'SINCE', date, 'UNSEEN')",
            "self._imap_client.uid('SEARCH', charset, 'SINCE', date)",
            "self._imap_client.uid('SEARCH', None, criterion, date)",
            "self._imap_client.uid('SEARCH', None, 'SINCE', other_date)",
            "self._imap_client.uid('SEARCH', None, 'SINCE', date, extra=True)",
            "self._imap_client.uid('FETCH', '1', '(RFC822.SIZE)')",
        )
        for sample in rejected:
            with self.subTest(sample=sample):
                self.assertTrue(_imap_call_violations(ast.parse(sample)))

    def test_raw_client_escape_guard_closes_container_and_expression_shapes(self) -> None:
        samples = {
            "walrus": "if (raw := self._imap_client):\n    pass",
            "destructuring": "raw, other = self._imap_client, None",
            "tuple": "value = (self._imap_client,)",
            "list": "value = [self._imap_client]",
            "dict": "value = {'raw': self._imap_client}",
            "set": "value = {self._imap_client}",
            "subscript": "value = [self._imap_client][0]",
            "lambda": "value = lambda: self._imap_client",
            "closure": (
                "def outer():\n"
                "    raw = self._imap_client\n"
                "    def inner():\n"
                "        return raw"
            ),
            "comprehension": "value = [self._imap_client for _ in items]",
            "attribute chain": "value = self._imap_client.sock",
            "yield": "def expose():\n    yield self._imap_client",
            "constructor in container": (
                "import imaplib\nvalue = [imaplib.IMAP4_SSL()]"
            ),
        }

        for label, sample in samples.items():
            with self.subTest(label=label):
                self.assertTrue(
                    _source_transport_violations(ast.parse(sample), is_wrapper=True)
                )

    def test_transport_guard_allows_fixed_read_only_selectors(
        self,
    ) -> None:
        samples = (
            "self._imap_client.list()",
            "self._imap_client.select('INBOX', readonly=True)",
            "self._imap_client.select(mailbox='INBOX', readonly=True)",
            "self._imap_client.uid('SEARCH', None, 'SINCE', date)",
            "self._imap_client.uid('FETCH', '1', '(RFC822.SIZE INTERNALDATE)')",
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

    def test_task_three_docs_keep_uid_fetch_literal_until_validator_tests_exist(
        self,
    ) -> None:
        for path in UID_BOUNDARY_DOCS:
            text = " ".join(read_text(path).split())
            with self.subTest(path=path, marker="single UID literal"):
                self.assertIn("finite single-UID decimal literal", text)
            with self.subTest(path=path, marker="future validator expression"):
                self.assertIn("validate_single_uid_fetch_target(uid)", text)
            with self.subTest(path=path, marker="same-change runtime tests"):
                self.assertIn("same change as its runtime tests", text)

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
