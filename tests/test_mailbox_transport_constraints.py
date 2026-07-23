"""Mechanical transport constraints for the isolated mailbox importer."""

from __future__ import annotations

import ast
import hashlib
import re
import tempfile
import unittest
from pathlib import Path

from scripts.repo_utils import read_text


ROOT = Path(__file__).resolve().parents[1]

STATUS_GENERATOR_AST_SHA256 = (
    "483457c1c214b763027d13de5ad803e77103f9e68496170cca19cc5375b9337b"
)

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

_DIRECT_SYNC_WORD = re.compile(r"^(?:auto|re)?sync(?:s|ed|ing|er|ers|able)?$")
_CONTEXTUAL_SYNC_WORD = re.compile(
    r"^(?:auto|re)?synchron(?:ize|izes|ized|izing|izer|izers|"
    r"ise|ises|ised|ising|iser|isers|ization|izations|isation|isations)$"
)
_CONTEXTUAL_INCREMENTAL_WORD = re.compile(
    r"^(?:delta|pull(?:ed|ing)?|refresh(?:ed|ing)?|update(?:d|ing)?)$"
)
_SYNC_CONTEXT_WORDS = {
    "account", "accounts", "corpus", "email", "emails", "folder", "folders",
    "imap", "inbox", "incremental", "mailbox", "mailboxes", "message",
    "messages", "vault",
}
_SYNC_STRONG_PATH_CONTEXT_WORDS = {
    "account", "accounts", "folder", "folders", "imap", "inbox", "mailbox",
    "mailboxes", "vault",
}
_SYNC_TEXT_SUFFIXES = {
    ".bat", ".cjs", ".cmd", ".css", ".html", ".js", ".json", ".jsx",
    ".mjs", ".ps1", ".ts", ".tsx", ".yaml", ".yml",
}
_MAX_LITERAL_VARIANTS = 64
_QUOTED_LITERAL = r'''(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)'''
_QUOTED_LITERAL_CHAIN = re.compile(
    rf"{_QUOTED_LITERAL}(?:\s*\+\s*{_QUOTED_LITERAL})+",
    re.DOTALL,
)
_QUOTED_LITERAL_PART = re.compile(_QUOTED_LITERAL, re.DOTALL)
_JS_ARRAY_LITERAL_JOIN = re.compile(
    rf"\[(?P<items>\s*{_QUOTED_LITERAL}(?:\s*,\s*{_QUOTED_LITERAL})*\s*)\]"
    rf"\s*\.join\(\s*(?P<separator>{_QUOTED_LITERAL})\s*\)",
    re.DOTALL,
)
_JS_TEMPLATE_LITERAL = re.compile(r"`(?:\\.|[^`\\])*`", re.DOTALL)
_JS_CONSTANT_INTERPOLATION = re.compile(
    rf"\$\{{\s*(?P<value>{_QUOTED_LITERAL})\s*\}}",
    re.DOTALL,
)


def _decode_javascript_literal(token: str) -> str | None:
    if len(token) < 2 or token[0] not in "'\"`" or token[-1] != token[0]:
        return None
    content = token[1:-1]
    decoded: list[str] = []
    index = 0
    simple = {
        "0": "\0", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
        "t": "\t", "v": "\v", "\\": "\\", "'": "'", '"': '"',
        "`": "`", "/": "/",
    }
    while index < len(content):
        character = content[index]
        if character != "\\":
            decoded.append(character)
            index += 1
            continue
        index += 1
        if index >= len(content):
            return None
        marker = content[index]
        if marker in "01234567" and (
            marker != "0"
            or (
                index + 1 < len(content)
                and content[index + 1].isdigit()
            )
        ):
            return None
        if marker in simple:
            decoded.append(simple[marker])
            index += 1
            continue
        if marker in "\r\n":
            if marker == "\r" and index + 1 < len(content) and content[index + 1] == "\n":
                index += 1
            index += 1
            continue
        if marker == "x":
            digits = content[index + 1:index + 3]
            if len(digits) != 2 or not re.fullmatch(r"[0-9A-Fa-f]{2}", digits):
                return None
            decoded.append(chr(int(digits, 16)))
            index += 3
            continue
        if marker == "u":
            if index + 1 < len(content) and content[index + 1] == "{":
                closing = content.find("}", index + 2)
                if closing < 0:
                    return None
                digits = content[index + 2:closing]
                index = closing + 1
            else:
                digits = content[index + 1:index + 5]
                index += 5
            if (
                not 1 <= len(digits) <= 6
                or not re.fullmatch(r"[0-9A-Fa-f]+", digits)
            ):
                return None
            codepoint = int(digits, 16)
            if codepoint > 0x10FFFF or 0xD800 <= codepoint <= 0xDFFF:
                return None
            decoded.append(chr(codepoint))
            continue
        decoded.append(marker)
        index += 1
    return "".join(decoded)


def _decoded_javascript_literal_or_failure(token: str) -> str:
    decoded = _decode_javascript_literal(token)
    return decoded if decoded is not None else "sync"


def _term_tokens(value: str) -> set[str]:
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", value)
    return {
        part.casefold()
        for part in re.split(r"[^A-Za-z0-9]+", separated)
        if part
    }


def _combine_literal_variants(
    parts: list[set[str]],
    *,
    separator: str = "",
) -> set[str]:
    combined = {""}
    for index, variants in enumerate(parts):
        candidate = {
            prefix + (separator if index else "") + suffix
            for prefix in combined
            for suffix in variants
        }
        if len(candidate) > _MAX_LITERAL_VARIANTS:
            return {"sync"}
        combined = candidate
    return combined


def _literal_variant_tuples(parts: list[set[str]]) -> set[tuple[str, ...]]:
    combined: set[tuple[str, ...]] = {()}
    for variants in parts:
        candidate = {
            (*prefix, suffix)
            for prefix in combined
            for suffix in variants
        }
        if len(candidate) > _MAX_LITERAL_VARIANTS:
            return {("sync",)}
        combined = candidate
    return combined


def _literal_strings(
    node: ast.AST,
    constants: dict[str, set[str]] | None = None,
) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
        try:
            return {node.value.decode("utf-8")}
        except UnicodeDecodeError:
            return set()
    if isinstance(node, ast.Name) and constants is not None:
        return constants.get(node.id, set())
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_strings(node.left, constants)
        right = _literal_strings(node.right, constants)
        if left and right:
            return _combine_literal_variants([left, right])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        templates = _literal_strings(node.left, constants)
        right_parts = (
            [_literal_strings(item, constants) for item in node.right.elts]
            if isinstance(node.right, ast.Tuple)
            else [_literal_strings(node.right, constants)]
        )
        if templates and right_parts and all(right_parts):
            formatted: set[str] = set()
            for template in templates:
                for values in _literal_variant_tuples(right_parts):
                    argument: object = values if len(right_parts) > 1 else values[0]
                    try:
                        formatted.add(template % argument)
                    except (TypeError, ValueError):
                        continue
            return formatted
    if isinstance(node, ast.JoinedStr):
        parts: list[set[str]] = []
        for part in node.values:
            selected = (
                _literal_strings(part.value, constants)
                if isinstance(part, ast.FormattedValue)
                else _literal_strings(part, constants)
            )
            if not selected:
                return set()
            parts.append(selected)
        return _combine_literal_variants(parts)
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "join"
        and len(node.args) == 1
        and not node.keywords
        and isinstance(node.args[0], (ast.List, ast.Tuple, ast.Set))
    ):
        separators = _literal_strings(node.func.value, constants)
        parts = [
            _literal_strings(item, constants)
            for item in node.args[0].elts
        ]
        if separators and parts and all(parts):
            joined: set[str] = set()
            for separator in separators:
                joined.update(
                    _combine_literal_variants(parts, separator=separator)
                )
                if len(joined) > _MAX_LITERAL_VARIANTS:
                    return {"sync"}
            return joined
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "format"
        and not node.keywords
    ):
        templates = _literal_strings(node.func.value, constants)
        parts = [_literal_strings(argument, constants) for argument in node.args]
        if templates and all(parts):
            formatted: set[str] = set()
            for template in templates:
                for values in _literal_variant_tuples(parts):
                    try:
                        formatted.add(template.format(*values))
                    except (IndexError, KeyError, ValueError):
                        continue
            return formatted
    return set()


def _python_literal_constants(tree: ast.AST) -> dict[str, set[str]]:
    constants: dict[str, set[str]] = {}
    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign, ast.NamedExpr))
    ]
    for _pass in range(len(assignments) + 1):
        updated = {name: set(values) for name, values in constants.items()}
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets.extend(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign):
                targets.append(node.target)
                value = node.value
            elif isinstance(node, ast.NamedExpr):
                targets.append(node.target)
                value = node.value
            if value is None:
                continue
            selected = _literal_strings(value, constants)
            if not selected:
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    merged = updated.setdefault(target.id, set()) | selected
                    updated[target.id] = (
                        merged
                        if len(merged) <= _MAX_LITERAL_VARIANTS
                        else {"sync"}
                    )
        if updated == constants:
            break
        constants = updated
    return constants


def _python_executable_fragments(
    path: Path,
) -> list[str]:
    tree = ast.parse(read_text(path))
    constants = _python_literal_constants(tree)
    generated_prose = _generated_status_prose_nodes(path, tree)
    fragments: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            fragments.append(node.name)
        elif isinstance(node, ast.arg):
            fragments.append(node.arg)
        elif isinstance(node, ast.Name):
            fragments.append(node.id)
        elif isinstance(node, ast.Attribute):
            fragments.append(node.attr)
        elif isinstance(node, ast.alias):
            fragments.extend((node.name, node.asname or ""))
        elif isinstance(node, ast.ImportFrom):
            fragments.append(node.module or "")
        literals = _literal_strings(node, constants)
        if id(node) not in generated_prose:
            fragments.extend(literals)
    return fragments


def _text_executable_fragments(value: str) -> list[str]:
    fragments = value.splitlines()
    fragments.extend(
        re.sub(r"[\s'\"`+]", "", line)
        for line in value.splitlines()
    )
    fragments.extend(
        decoded if decoded is not None else "sync"
        for part in _QUOTED_LITERAL_PART.finditer(value)
        for decoded in [_decode_javascript_literal(part.group(0))]
    )
    fragments.extend(
        "".join(
            _decoded_javascript_literal_or_failure(part.group(0))
            for part in _QUOTED_LITERAL_PART.finditer(chain.group(0))
        )
        for chain in _QUOTED_LITERAL_CHAIN.finditer(value)
    )
    for joined in _JS_ARRAY_LITERAL_JOIN.finditer(value):
        items = [
            _decoded_javascript_literal_or_failure(part.group(0))
            for part in _QUOTED_LITERAL_PART.finditer(joined.group("items"))
        ]
        separator = _decode_javascript_literal(joined.group("separator"))
        if separator is None:
            separator = "sync"
        fragments.append(separator.join(items))
    for template in _JS_TEMPLATE_LITERAL.finditer(value):
        content = template.group(0)[1:-1]
        if "${" not in content:
            continue
        expanded = _JS_CONSTANT_INTERPOLATION.sub(
            lambda match: (
                _decoded_javascript_literal_or_failure(match.group("value"))
            ),
            content,
        )
        if "${" not in expanded:
            decoded = _decode_javascript_literal(f"`{expanded}`")
            fragments.append(decoded if decoded is not None else "sync")
    return fragments


def _binding_sites(tree: ast.AST, name: str) -> list[ast.AST]:
    sites: list[ast.AST] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and node.id == name
            and isinstance(node.ctx, (ast.Store, ast.Del))
        ):
            sites.append(node)
        elif isinstance(node, ast.arg) and node.arg == name:
            sites.append(node)
        elif isinstance(node, ast.alias):
            bound_name = node.asname or node.name.split(".", 1)[0]
            if bound_name == name:
                sites.append(node)
        elif isinstance(node, ast.ExceptHandler) and node.name == name:
            sites.append(node)
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and name in node.names:
            sites.append(node)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == name:
            sites.append(node)
        elif isinstance(node, ast.MatchMapping) and node.rest == name:
            sites.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == name:
                sites.append(node)
    return sites


def _generated_status_prose_nodes(path: Path, tree: ast.AST) -> set[int]:
    if path.resolve() != (ROOT / "scripts" / "generate_project_status.py").resolve():
        return set()
    status_ast_digest = hashlib.sha256(
        ast.dump(tree, include_attributes=False).encode("utf-8")
    ).hexdigest()
    if status_ast_digest != STATUS_GENERATOR_AST_SHA256:
        return set()
    reflective_names = {
        "__import__", "compile", "delattr", "eval", "exec", "getattr",
        "globals", "locals", "setattr", "vars",
    }
    reflective_attributes = {
        "__code__", "__dict__", "__getattribute__", "__globals__",
        "__setattr__", "__delattr__",
    }
    constants = _python_literal_constants(tree)
    if (
        any(
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in reflective_names
            for node in ast.walk(tree)
        )
        or any(
            isinstance(node, ast.Attribute)
            and node.attr in reflective_attributes
            for node in ast.walk(tree)
        )
        or any(
            "build_project_status" in _literal_strings(node, constants)
            for node in ast.walk(tree)
        )
    ):
        return set()
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    path_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.ImportFrom)
        and node.level == 0
        and node.module == "pathlib"
        and len(node.names) == 1
        and node.names[0].name == "Path"
        and node.names[0].asname is None
    ]
    if len(path_imports) != 1 or any(
        isinstance(node, ast.alias)
        and node not in path_imports[0].names
        and (
            node.asname == "Path"
            or (node.asname is None and node.name.split(".", 1)[0] == "Path")
        )
        for node in ast.walk(tree)
    ):
        return set()
    if _binding_sites(tree, "Path") != [path_imports[0].names[0]]:
        return set()
    argparse_imports = [
        node
        for node in tree.body
        if isinstance(node, ast.Import)
        and len(node.names) == 1
        and node.names[0].name == "argparse"
        and node.names[0].asname is None
    ]
    if (
        len(argparse_imports) != 1
        or _binding_sites(tree, "argparse") != [argparse_imports[0].names[0]]
    ):
        return set()
    root_assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "ROOT"
    ]
    if (
        len(root_assignments) != 1
        or ast.unparse(root_assignments[0].value)
        != "Path(__file__).resolve().parents[1]"
    ):
        return set()
    canonical_root_target = root_assignments[0].targets[0]
    if _binding_sites(tree, "ROOT") != [canonical_root_target]:
        return set()
    if any(
        isinstance(node, ast.Name)
        and node.id == "ROOT"
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and node is not canonical_root_target
        for node in ast.walk(tree)
    ) or any(
        (
            isinstance(node, ast.arg)
            and node.arg == "ROOT"
        )
        or (
            isinstance(node, ast.alias)
            and (
                node.asname == "ROOT"
                or (
                    node.asname is None
                    and node.name.split(".", 1)[0] == "ROOT"
                )
            )
        )
        or (
            isinstance(node, ast.ExceptHandler)
            and node.name == "ROOT"
        )
        or (
            isinstance(node, (ast.Global, ast.Nonlocal))
            and "ROOT" in node.names
        )
        or (
            isinstance(node, (ast.MatchAs, ast.MatchStar))
            and node.name == "ROOT"
        )
        or (
            isinstance(node, ast.MatchMapping)
            and node.rest == "ROOT"
        )
        or (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == "ROOT"
        )
        for node in ast.walk(tree)
    ):
        return set()
    canonical_path_loads = [
        node
        for node in ast.walk(root_assignments[0].value)
        if isinstance(node, ast.Name)
        and node.id == "Path"
        and isinstance(node.ctx, ast.Load)
    ]
    if len(canonical_path_loads) != 1:
        return set()
    canonical_path_load = canonical_path_loads[0]
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Name)
            and node.id == "Path"
            and isinstance(node.ctx, ast.Load)
        ):
            continue
        if node is canonical_path_load:
            continue
        keyword = parents.get(node)
        call = parents.get(keyword) if isinstance(keyword, ast.keyword) else None
        if not (
            isinstance(keyword, ast.keyword)
            and keyword.arg == "type"
            and keyword.value is node
            and isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "add_argument"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "parser"
            and any(
                isinstance(argument, ast.Constant)
                and argument.value == "--output"
                for argument in call.args
            )
        ):
            return set()
    if any(
        isinstance(node, ast.Name)
        and node.id == "Path"
        and isinstance(node.ctx, (ast.Store, ast.Del))
        for node in ast.walk(tree)
    ) or any(
        (
            isinstance(node, ast.arg)
            and node.arg == "Path"
        )
        or (
            isinstance(node, ast.ExceptHandler)
            and node.name == "Path"
        )
        or (
            isinstance(node, (ast.Global, ast.Nonlocal))
            and "Path" in node.names
        )
        or (
            isinstance(node, (ast.MatchAs, ast.MatchStar))
            and node.name == "Path"
        )
        or (
            isinstance(node, ast.MatchMapping)
            and node.rest == "Path"
        )
        or (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            and node.name == "Path"
        )
        for node in ast.walk(tree)
    ) or any(
        isinstance(node, ast.Attribute)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        for node in ast.walk(tree)
    ) or any(
        isinstance(node, ast.Subscript)
        and isinstance(node.ctx, (ast.Store, ast.Del))
        and isinstance(node.slice, ast.Constant)
        and node.slice.value in {"ROOT", "Path", "argparse", "write_text"}
        for node in ast.walk(tree)
    ) or any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.name == "write_text"
        for node in ast.walk(tree)
    ):
        return set()
    expected_parse_args = ast.parse(
        "def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.add_argument('--output', type=Path, "
        "default=ROOT / 'docs' / 'operations' / 'project_status_log.md')\n"
        "    return parser.parse_args(argv)\n"
    ).body[0]
    expected_main = ast.parse(
        "def main(argv: Sequence[str] | None = None) -> int:\n"
        "    args = parse_args(argv)\n"
        "    output = args.output if args.output.is_absolute() "
        "else ROOT / args.output\n"
        "    output.parent.mkdir(parents=True, exist_ok=True)\n"
        "    output.write_text(build_project_status(), encoding='utf-8')\n"
        "    return 0\n"
    ).body[0]
    parse_args_definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "parse_args"
    ]
    main_definitions = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "main"
    ]
    if (
        len(parse_args_definitions) != 1
        or len(main_definitions) != 1
        or _binding_sites(tree, "parse_args") != [parse_args_definitions[0]]
        or _binding_sites(tree, "main") != [main_definitions[0]]
        or ast.dump(parse_args_definitions[0], include_attributes=False)
        != ast.dump(expected_parse_args, include_attributes=False)
        or ast.dump(main_definitions[0], include_attributes=False)
        != ast.dump(expected_main, include_attributes=False)
    ):
        return set()
    status_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_project_status"
    ]
    if len(status_calls) != 1:
        return set()
    status_call = status_calls[0]
    status_definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "build_project_status"
    ]
    if (
        len(status_definitions) != 1
        or status_definitions[0] not in tree.body
        or status_definitions[0].decorator_list
        or any(
            isinstance(node, ast.Name)
            and node.id == "build_project_status"
            and isinstance(node.ctx, (ast.Store, ast.Del))
            for node in ast.walk(tree)
        )
        or any(
            isinstance(node, ast.alias)
            and (
                node.asname == "build_project_status"
                or (
                    node.asname is None
                    and node.name.split(".", 1)[0] == "build_project_status"
                )
            )
            for node in ast.walk(tree)
        )
    ):
        return set()
    status_loads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == "build_project_status"
    ]
    if len(status_loads) != 1 or status_loads[0] is not status_call.func:
        return set()
    if any(
        isinstance(node, ast.Attribute)
        and node.attr == "build_project_status"
        for node in ast.walk(tree)
    ):
        return set()
    sink = parents.get(status_call)
    if not (
        isinstance(sink, ast.Call)
        and isinstance(sink.func, ast.Attribute)
        and sink.func.attr == "write_text"
        and isinstance(sink.func.value, ast.Name)
        and sink.func.value.id == "output"
        and sink.args
        and sink.args[0] is status_call
    ):
        return set()
    output_assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "output"
            for target in node.targets
        )
    ]
    if len(output_assignments) != 1 or ast.unparse(output_assignments[0].value) != (
        "args.output if args.output.is_absolute() else ROOT / args.output"
    ):
        return set()
    owner = parents.get(sink)
    while owner is not None and not isinstance(
        owner,
        (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda),
    ):
        owner = parents.get(owner)
    if not isinstance(owner, ast.FunctionDef) or owner.name != "main":
        return set()
    output_bindings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "output" and isinstance(
            node.ctx,
            (ast.Store, ast.Del),
        ):
            output_bindings.append(type(node.ctx).__name__)
        elif isinstance(node, ast.arg) and node.arg == "output":
            output_bindings.append("argument")
        elif isinstance(node, ast.alias) and (
            node.asname == "output"
            or (node.asname is None and node.name.split(".", 1)[0] == "output")
        ):
            output_bindings.append("import")
        elif isinstance(node, ast.ExceptHandler) and node.name == "output":
            output_bindings.append("exception")
        elif isinstance(node, (ast.Global, ast.Nonlocal)) and "output" in node.names:
            output_bindings.append(type(node).__name__)
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name == "output":
            output_bindings.append(type(node).__name__)
        elif isinstance(node, ast.MatchMapping) and node.rest == "output":
            output_bindings.append("MatchMapping")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name == "output":
                output_bindings.append(type(node).__name__)
    if output_bindings != ["Store"]:
        return set()
    sink_statement = parents.get(sink)
    if not (
        isinstance(sink_statement, ast.Expr)
        and sink_statement.value is sink
        and output_assignments[0] in owner.body
        and sink_statement in owner.body
    ):
        return set()
    output_index = owner.body.index(output_assignments[0])
    if output_index + 2 >= len(owner.body):
        return set()
    mkdir_statement = owner.body[output_index + 1]
    if (
        ast.unparse(mkdir_statement)
        != "output.parent.mkdir(parents=True, exist_ok=True)"
        or owner.body[output_index + 2] is not sink_statement
    ):
        return set()
    generated_prose: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Return) or not isinstance(node.value, ast.JoinedStr):
            continue
        parent = parents.get(node)
        while parent is not None and not isinstance(
            parent,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda),
        ):
            parent = parents.get(parent)
        if not isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if parent.name != "build_project_status":
            continue
        generated_prose.update(
            id(part)
            for part in node.value.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return generated_prose


def _sync_exposure_terms(
    value: str,
    *,
    inherited_context: bool = False,
    inherited_semantic_context: bool = False,
) -> set[str]:
    terms = _term_tokens(value)
    direct = {term for term in terms if _DIRECT_SYNC_WORD.fullmatch(term)}
    contextual = {
        term
        for term in terms
        if _CONTEXTUAL_SYNC_WORD.fullmatch(term)
    }
    has_context = inherited_context or bool(terms.intersection(_SYNC_CONTEXT_WORDS))
    if not has_context:
        contextual.clear()
    semantic_aliases = (
        {
            term
            for term in terms
            if _CONTEXTUAL_INCREMENTAL_WORD.fullmatch(term)
        }
        if terms.intersection(_SYNC_CONTEXT_WORDS) or inherited_semantic_context
        else set()
    )
    compound: set[str] = set()
    for term in terms:
        for context in _SYNC_CONTEXT_WORDS:
            candidates = []
            if term.startswith(context):
                candidates.append(term.removeprefix(context))
            if term.endswith(context):
                candidates.append(term.removesuffix(context))
            compound.update(
                candidate
                for candidate in candidates
                if _DIRECT_SYNC_WORD.fullmatch(candidate)
                or _CONTEXTUAL_SYNC_WORD.fullmatch(candidate)
                or _CONTEXTUAL_INCREMENTAL_WORD.fullmatch(candidate)
            )
    return direct | contextual | semantic_aliases | compound


def _incremental_sync_exposures(
    path: Path,
    *,
    surface_root: Path,
) -> set[str]:
    relative_parts = path.resolve().relative_to(surface_root.resolve()).parts
    path_terms = {
        term
        for part in relative_parts
        for term in _term_tokens(part)
    }
    path_has_context = bool(path_terms.intersection(_SYNC_CONTEXT_WORDS))
    path_has_semantic_context = bool(
        path_terms.intersection(_SYNC_STRONG_PATH_CONTEXT_WORDS)
    )
    fragments = (
        _python_executable_fragments(path)
        if path.suffix.casefold() == ".py"
        else _text_executable_fragments(read_text(path))
    )
    fragments.extend(relative_parts)
    return {
        exposure
        for fragment in fragments
        for exposure in _sync_exposure_terms(
            fragment,
            inherited_context=path_has_context,
            inherited_semantic_context=path_has_semantic_context,
        )
    }


def _issue_ten_protected_surfaces() -> tuple[Path, ...]:
    paths = {
        *(path for path in (ROOT / "scripts").rglob("*")
          if path.is_file() and path.suffix.casefold() in {".bat", ".cmd", ".ps1", ".py"}),
        *(ROOT / "backend" / "email_agent").rglob("*.py"),
        *(path for path in (ROOT / "frontend").rglob("*")
          if path.is_file() and path.suffix.casefold() in _SYNC_TEXT_SUFFIXES),
        *(ROOT / ".github" / "workflows").glob("*.yml"),
        *(ROOT / ".github" / "workflows").glob("*.yaml"),
        *(path for path in ROOT.iterdir()
          if path.is_file() and path.suffix.casefold() in {".bat", ".cmd", ".ps1"}),
    }
    return tuple(sorted(paths, key=lambda path: path.as_posix().casefold()))


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
    def test_incremental_sync_guard_detects_executable_spelling_variants(self) -> None:
        samples = {
            "single_quote.py": "commands.add_parser('sync')\n",
            "double_quote.py": 'commands.add_parser("sync")\n',
            "snake_case.py": "incremental_sync = True\n",
            "camel_case.js": "syncMailbox();\n",
            "synchronize_inbox.js": "synchronizeInbox();\n",
            "synchronize_imap.py": "synchronizeImap()\n",
            "resync_mailbox.py": "resyncMailbox()\n",
            "resynchronize_mailbox.py": "resynchronizeMailbox()\n",
            "mailbox_syncer.py": "mailboxSyncer()\n",
            "mailbox_synchronizer.py": "mailboxSynchronizer()\n",
            "synchronizing_mailbox.py": "synchronizingMailbox()\n",
            "synchronized_mailbox.py": "synchronizedMailbox()\n",
            "resynchronizing_inbox.py": "resynchronizingInbox()\n",
            "synchronize_account.py": "synchronizeAccount()\n",
            "autosync_mailbox.py": "autosyncMailbox()\n",
            "autosynchronize_mailbox.py": "run_import()\n",
            "route.html": "/api/mailbox-sync\n",
            "compact_route.html": "/api/mailboxsync\n",
            "compact_call.js": "syncmailbox();\n",
            "refresh_mailbox.js": "refreshMailbox();\n",
            "compact_refresh_mailbox.js": "refreshmailbox();\n",
            "delta_mailbox.js": "deltaMailbox();\n",
            "pull_mailbox.js": "pullMailbox();\n",
            "mailbox_update_route.html": "/api/mailbox-update\n",
            "scheduled.yml": "steps:\n  - run: mailbox synchronize\n",
            "relative_import.py": "from .mailbox_sync import run as task\n",
            "absolute_import.py": "from backend.mailbox_sync import run as task\n",
            "constant_concat.py": "commands.add_parser('sy' + 'nc')\n",
            "bytes_literal.py": "commands.add_parser(b'mailbox sync')\n",
            "constant_fstring.py": (
                "commands.add_parser(f'{\"sy\"}nc')\n"
            ),
            "variable_fstring.py": (
                "part = 'sy'\ncommands.add_parser(f'{part}nc')\n"
            ),
            "reassigned_fstring.py": (
                "part = 'unused'\npart = 'sy'\n"
                "commands.add_parser(f'{part}nc')\n"
            ),
            "deep_constant_chain.py": (
                "a = 'sy'\nb = a\nc = b\nd = c\ne = d\nf = e\n"
                "commands.add_parser(f'{f}nc')\n"
            ),
            "literal_join.py": (
                "commands.add_parser(''.join(('sy', 'nc')))\n"
            ),
            "literal_format.py": (
                "commands.add_parser('s{}nc'.format('y'))\n"
            ),
            "literal_percent.py": (
                "commands.add_parser('%s%s' % ('sy', 'nc'))\n"
            ),
            "javascript_concat.js": '"mailbox-" + "sy" + "nc";\n',
            "javascript_multiline_concat.js": (
                '"mailbox-" +\n    "sy" +\n    "nc";\n'
            ),
            "javascript_array_join.js": "['sy', 'nc'].join('');\n",
            "javascript_template.js": "`mailbox-${'sy'}${'nc'}`;\n",
            "javascript_unicode_escape.js": '"\\u0073ync";\n',
            "javascript_hex_escape.js": '"\\x73ync";\n',
            "javascript_octal_escape.js": '"\\163ync";\n',
            "javascript_join_escape.js": (
                '["s\\u0079", "nc"].join("");\n'
            ),
            "javascript_template_escape.js": (
                '`mailbox-${"s\\u0079"}${"nc"}`;\n'
            ),
            "module_surface.mjs": "syncmailbox();\n",
            "executable_docstring.py": (
                "\"\"\"sync\"\"\"\ncommands.add_parser(__doc__)\n"
            ),
            "scripts/mailbox_sync/run.py": "run_import()\n",
            "scripts/manage_mailbox_vault.py": (
                "commands.add_parser('synchronize')\n"
            ),
            "scripts/mailbox_vault/resynchronize.py": (
                "commands.add_parser('resynchronize')\n"
            ),
            "scripts/mailbox/refresh.py": "run_import()\n",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, source in samples.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")
                with self.subTest(name=name):
                    self.assertTrue(
                        _incremental_sync_exposures(path, surface_root=root)
                    )

            benign = root / "benign.py"
            benign.write_text(
                "import os\n"
                "async def wait_for_io():\n"
                "    os.fsync(1)\n"
                "    return 'synchronous'\n"
                "def synchronize():\n"
                "    return 'synchronization complete'\n"
                "mailbox_label = 'current mailbox'\n"
                "def synchronize_clock():\n"
                "    return None\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _incremental_sync_exposures(benign, surface_root=root),
                set(),
            )

            checkout = root / "mailbox_sync" / "checkout"
            checkout.mkdir(parents=True)
            checkout_benign = checkout / "benign.py"
            checkout_benign.write_text(
                "def synchronize_clock():\n    return 'synchronous'\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _incremental_sync_exposures(
                    checkout_benign,
                    surface_root=checkout,
                ),
                set(),
            )

            status_generator = root / "generate_project_status.py"
            status_generator.write_text(
                "def build_project_status(count):\n"
                "    return f'Manual mailbox sync remains future scope: {count}'\n",
                encoding="utf-8",
            )
            self.assertTrue(
                _incremental_sync_exposures(
                    status_generator,
                    surface_root=root,
                )
            )

            canonical_status_path = ROOT / "scripts" / "generate_project_status.py"
            canonical_status_source = read_text(canonical_status_path)
            safe_status_tree = ast.parse(canonical_status_source)
            unsafe_path_sink_rebinding_tree = ast.parse(
                canonical_status_source.replace(
                    "ROOT = Path(__file__).resolve().parents[1]\n",
                    "ROOT = Path(__file__).resolve().parents[1]\n"
                    "Path.write_text = staticmethod(subprocess.run)\n",
                    1,
                )
            )
            unsafe_root_rebinding_tree = ast.parse(
                canonical_status_source.replace(
                    "ROOT = Path(__file__).resolve().parents[1]\n",
                    "ROOT = Path(__file__).resolve().parents[1]\n"
                    "ROOT = executor\n",
                    1,
                )
            )
            unsafe_module_path_rebinding_tree = ast.parse(
                canonical_status_source.replace(
                    "ROOT = Path(__file__).resolve().parents[1]\n",
                    "sys.modules[__name__].Path = EvilPath\n"
                    "ROOT = Path(__file__).resolve().parents[1]\n",
                    1,
                )
            )
            unsafe_module_root_rebinding_tree = ast.parse(
                canonical_status_source.replace(
                    "ROOT = Path(__file__).resolve().parents[1]\n",
                    "ROOT = Path(__file__).resolve().parents[1]\n"
                    "sys.modules[__name__].ROOT = executor\n",
                    1,
                )
            )
            unsafe_path_capability_mutation_tree = ast.parse(
                canonical_status_source.replace(
                    "ROOT = Path(__file__).resolve().parents[1]\n",
                    "ROOT = Path(__file__).resolve().parents[1]\n"
                    "type(ROOT).__truediv__ = replacement\n",
                    1,
                )
            )
            unsafe_evil_output_tree = ast.parse(
                canonical_status_source.replace(
                    "def build_project_status() -> str:\n",
                    "class EvilOutput:\n"
                    "    def write_text(self, value, **kwargs):\n"
                    "        return subprocess.run(value)\n"
                    "def build_project_status() -> str:\n",
                    1,
                ).replace(
                    "    args = parse_args(argv)\n",
                    "    args = parse_args(argv)\n"
                    "    args.output = EvilOutput()\n",
                    1,
                )
            )
            unsafe_status_decorator_tree = ast.parse(
                canonical_status_source.replace(
                    "def build_project_status() -> str:\n",
                    "@execute_result\n"
                    "def build_project_status() -> str:\n",
                    1,
                )
            )
            unsafe_status_tree = ast.parse(
                "def build_project_status(count):\n"
                "    return f'Manual mailbox sync remains future scope: {count}'\n"
                "def execute_status(subprocess):\n"
                "    subprocess.run(build_project_status())\n"
            )
            unsafe_receiver_tree = ast.parse(
                "def build_project_status(count):\n"
                "    return f'Manual mailbox sync remains future scope: {count}'\n"
                "def main(args, executor):\n"
                "    output = (args.output if args.output.is_absolute() "
                "else ROOT / args.output)\n"
                "    executor.write_text(build_project_status())\n"
            )
            unsafe_for_rebinding_tree = ast.parse(
                "def build_project_status(count):\n"
                "    return f'Manual mailbox sync remains future scope: {count}'\n"
                "def main(args, executor):\n"
                "    output = (args.output if args.output.is_absolute() "
                "else ROOT / args.output)\n"
                "    output.parent.mkdir(parents=True, exist_ok=True)\n"
                "    for output in (executor,):\n"
                "        output.write_text(build_project_status())\n"
            )
            unsafe_with_rebinding_tree = ast.parse(
                "def build_project_status(count):\n"
                "    return f'Manual mailbox sync remains future scope: {count}'\n"
                "def main(args, executor):\n"
                "    output = (args.output if args.output.is_absolute() "
                "else ROOT / args.output)\n"
                "    output.parent.mkdir(parents=True, exist_ok=True)\n"
                "    with executor as output:\n"
                "        output.write_text(build_project_status())\n"
            )
            unsafe_status_alias_tree = ast.parse(
                "def build_project_status():\n"
                "    return f'Manual mailbox sync remains future scope: {UNKNOWN}'\n"
                "def main(args, subprocess):\n"
                "    output = (args.output if args.output.is_absolute() "
                "else ROOT / args.output)\n"
                "    output.parent.mkdir(parents=True, exist_ok=True)\n"
                "    output.write_text(build_project_status())\n"
                "    runner = build_project_status\n"
                "    subprocess.run(runner())\n"
            )
            unsafe_status_reflection_tree = ast.parse(
                "def build_project_status():\n"
                "    return f'Manual mailbox sync remains future scope: {UNKNOWN}'\n"
                "def main(args, subprocess):\n"
                "    output = (args.output if args.output.is_absolute() "
                "else ROOT / args.output)\n"
                "    output.parent.mkdir(parents=True, exist_ok=True)\n"
                "    output.write_text(build_project_status())\n"
                "    runner = globals()['build_project_status']\n"
                "    subprocess.run(runner())\n"
            )
            self.assertTrue(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    safe_status_tree,
                )
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_path_sink_rebinding_tree,
                ),
                set(),
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_root_rebinding_tree,
                ),
                set(),
            )
            for unsafe_tree in (
                unsafe_module_path_rebinding_tree,
                unsafe_module_root_rebinding_tree,
                unsafe_path_capability_mutation_tree,
                unsafe_evil_output_tree,
                unsafe_status_decorator_tree,
            ):
                self.assertEqual(
                    _generated_status_prose_nodes(
                        canonical_status_path,
                        unsafe_tree,
                    ),
                    set(),
                )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_status_tree,
                ),
                set(),
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_receiver_tree,
                ),
                set(),
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_for_rebinding_tree,
                ),
                set(),
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_with_rebinding_tree,
                ),
                set(),
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_status_alias_tree,
                ),
                set(),
            )
            self.assertEqual(
                _generated_status_prose_nodes(
                    canonical_status_path,
                    unsafe_status_reflection_tree,
                ),
                set(),
            )

    def test_issue_ten_ratifies_future_manual_sync_without_adding_a_command(self) -> None:
        adr = read_text(
            ROOT / "docs" / "decisions" /
            "0008-bounded-corpus-to-runtime-handoffs.md"
        )
        cli_path = ROOT / "scripts" / "manage_mailbox_vault.py"
        cli = read_text(cli_path)
        cli_tree = ast.parse(cli)

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
        protected_surfaces = _issue_ten_protected_surfaces()
        self.assertTrue(
            {
                path
                for path in (ROOT / "scripts").rglob("*")
                if path.is_file()
                and path.suffix.casefold() in {".bat", ".cmd", ".ps1", ".py"}
            }.issubset(protected_surfaces)
        )
        self.assertTrue(
            {
                path
                for path in (ROOT / "frontend").rglob("*")
                if path.is_file()
                and path.suffix.casefold() in _SYNC_TEXT_SUFFIXES
            }.issubset(protected_surfaces)
        )
        self.assertTrue(
            {
                path
                for path in ROOT.iterdir()
                if path.is_file()
                and path.suffix.casefold() in {".bat", ".cmd", ".ps1"}
            }.issubset(protected_surfaces)
        )
        for path in protected_surfaces:
            with self.subTest(incremental_sync_surface=path):
                self.assertEqual(
                    _incremental_sync_exposures(path, surface_root=ROOT),
                    set(),
                )
        self.assertIn(
            'NETWORK_COMMANDS = frozenset({"inventory", "scan", "attachments"})',
            cli,
        )
        assignments = {
            target.id: node.value
            for node in cli_tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
        }
        self.assertEqual(
            ast.literal_eval(assignments["COMMANDS"]),
            (
                "init",
                "inventory",
                "scan",
                "attachments",
                "verify",
                "purge-expired",
                "revoke",
                "rewrap-recovery",
            ),
        )
        self.assertEqual(
            ast.literal_eval(assignments["STAGE_COMMAND"]),
            "stage-knowledge",
        )
        self.assertEqual(
            ast.literal_eval(assignments["STAGE_EVALUATION_COMMAND"]),
            "stage-evaluation",
        )
        network_value = assignments["NETWORK_COMMANDS"]
        self.assertIsInstance(network_value, ast.Call)
        self.assertIsInstance(network_value.func, ast.Name)
        self.assertEqual(network_value.func.id, "frozenset")
        self.assertEqual(
            frozenset(ast.literal_eval(network_value.args[0])),
            frozenset({"inventory", "scan", "attachments"}),
        )
        add_parser_attributes = [
            node
            for node in ast.walk(cli_tree)
            if isinstance(node, ast.Attribute)
            and node.attr == "add_parser"
        ]
        add_parser_calls = [
            node
            for node in ast.walk(cli_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
        ]
        self.assertEqual(len(add_parser_calls), 1)
        self.assertEqual(add_parser_attributes, [add_parser_calls[0].func])
        self.assertFalse(
            any(
                isinstance(node, ast.Constant)
                and node.value == "add_parser"
                for node in ast.walk(cli_tree)
            )
        )
        self.assertEqual(
            ast.unparse(add_parser_calls[0]),
            "commands.add_parser(command)",
        )
        command_loop = next(
            node
            for node in ast.walk(cli_tree)
            if isinstance(node, ast.For)
            and add_parser_calls[0] in set(ast.walk(node))
        )
        self.assertEqual(ast.unparse(command_loop.target), "command")
        self.assertEqual(
            ast.unparse(command_loop.iter),
            "(*COMMANDS, STAGE_COMMAND, STAGE_EVALUATION_COMMAND)",
        )
        build_parser_node = next(
            node
            for node in cli_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "build_parser"
        )
        self.assertEqual(
            hashlib.sha256(
                ast.dump(build_parser_node, include_attributes=False).encode(
                    "utf-8"
                )
            ).hexdigest(),
            "6f65b8f9cb62e6b1f5a8e283df05298ca3bd97aed775b0b2b44bf9a7cde1a8f1",
        )
        cli_constants = _python_literal_constants(cli_tree)
        protected_literal_names = {
            "COMMANDS",
            "NETWORK_COMMANDS",
            "STAGE_COMMAND",
            "STAGE_EVALUATION_COMMAND",
            "add_parser",
        }
        self.assertFalse(
            any(
                protected_literal_names.intersection(
                    _literal_strings(node, cli_constants)
                )
                for node in ast.walk(cli_tree)
            )
        )
        from scripts.manage_mailbox_vault import build_parser

        parser = build_parser()
        command_choices = next(
            action.choices
            for action in parser._actions
            if action.dest == "command"
        )
        self.assertEqual(
            set(command_choices),
            {
                "attachments",
                "init",
                "inventory",
                "purge-expired",
                "revoke",
                "rewrap-recovery",
                "scan",
                "stage-evaluation",
                "stage-knowledge",
                "verify",
            },
        )
        protected_constants = {
            "COMMANDS",
            "NETWORK_COMMANDS",
            "STAGE_COMMAND",
            "STAGE_EVALUATION_COMMAND",
        }
        initial_targets = {
            target.id: target
            for node in cli_tree.body
            if isinstance(node, ast.Assign)
            for target in node.targets
            if isinstance(target, ast.Name)
            and target.id in protected_constants
        }
        mutation_targets: list[ast.expr] = []
        for node in ast.walk(cli_tree):
            if isinstance(node, ast.Assign):
                mutation_targets.extend(node.targets)
            elif isinstance(
                node,
                (
                    ast.AnnAssign,
                    ast.AugAssign,
                    ast.NamedExpr,
                    ast.For,
                    ast.AsyncFor,
                    ast.comprehension,
                ),
            ):
                mutation_targets.append(node.target)
            elif isinstance(node, (ast.With, ast.AsyncWith)):
                mutation_targets.extend(
                    item.optional_vars
                    for item in node.items
                    if item.optional_vars is not None
                )
            elif isinstance(node, ast.Delete):
                mutation_targets.extend(node.targets)
            elif isinstance(node, ast.TypeAlias):
                mutation_targets.append(node.name)
        for name in protected_constants:
            stores = [
                node
                for node in ast.walk(cli_tree)
                if isinstance(node, ast.Name)
                and node.id == name
                and isinstance(node.ctx, ast.Store)
            ]
            self.assertEqual(stores, [initial_targets[name]], name)
            self.assertFalse(
                any(
                    target is not initial_targets[name]
                    and any(
                        (
                            isinstance(child, ast.Name)
                            and child.id == name
                        )
                        or (
                            isinstance(child, ast.Attribute)
                            and child.attr == name
                        )
                        for child in ast.walk(target)
                    )
                    for target in mutation_targets
                ),
                name,
            )
            self.assertFalse(
                any(
                    (
                        isinstance(node, ast.arg)
                        and node.arg == name
                    )
                    or (
                        isinstance(node, ast.alias)
                        and (node.asname or node.name.split(".", 1)[0]) == name
                    )
                    or (
                        isinstance(node, ast.ExceptHandler)
                        and node.name == name
                    )
                    or (
                        isinstance(node, (ast.Global, ast.Nonlocal))
                        and name in node.names
                    )
                    or (
                        isinstance(node, (ast.MatchAs, ast.MatchStar))
                        and node.name == name
                    )
                    or (
                        isinstance(node, ast.MatchMapping)
                        and node.rest == name
                    )
                    or (
                        isinstance(
                            node,
                            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
                        )
                        and node.name == name
                    )
                    for node in ast.walk(cli_tree)
                ),
                name,
            )
        for name, expected_parent in (
            ("commands", ast.Assign),
            ("command", ast.For),
        ):
            stores = [
                node
                for node in ast.walk(cli_tree)
                if isinstance(node, ast.Name)
                and node.id == name
                and isinstance(node.ctx, ast.Store)
            ]
            self.assertEqual(len(stores), 1, name)
            parents = {
                child: parent
                for parent in ast.walk(cli_tree)
                for child in ast.iter_child_nodes(parent)
            }
            self.assertIsInstance(parents[stores[0]], expected_parent, name)

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
