"""Executable architecture constraints for the email AI assistant project.

Run:
    python -m unittest discover -s tests -p "test_architecture_constraints.py"
"""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import re
import tempfile
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

_CURRENT_EVIDENCE_ALLOWED_SEARCH_TARGETS = {
    "PLACEHOLDER.search",
    "_SAFE_CREDENTIAL_POLICY_PROSE.search",
    "pattern.search",
}
_CURRENT_EVIDENCE_FORBIDDEN_LOAD_NAMES = {
    "__builtins__", "__import__", "breakpoint", "delattr", "eval", "exec",
    "getattr", "globals", "input", "locals", "open", "print", "setattr",
    "vars",
}
_CURRENT_EVIDENCE_FORBIDDEN_ATTRIBUTES = {
    "account", "authority", "candidate", "chmod", "chown", "commit",
    "connect", "cursor", "database", "delete", "environ", "environment",
    "execute", "fetch", "filesystem", "flush", "folder", "get", "getenv",
    "glob", "historical", "history", "imap", "inbox", "iterdir", "key",
    "key_store", "list", "load", "mailbox", "mkdir", "open", "patch",
    "path", "poll", "post", "provider", "put", "query", "raw", "raw_vault",
    "read", "reader", "recv", "reload", "remove", "rename", "repository",
    "request", "restoration", "rglob", "rmdir", "rmtree", "rollback",
    "schedule", "search", "send", "snapshot", "sqlite", "stat", "store",
    "touch", "truncate", "unlink", "update", "urlopen", "vault", "walk",
    "watch", "write",
}

_CONTAINER_AUDIT_FILES = {
    "__init__.py",
    "adapters.py",
    "audit.py",
    "contract.py",
    "filesystem_checks.py",
    "policy.py",
    "system_checks.py",
}
_CONTAINER_AUDIT_ALLOWED_IMPORTS = {
    "__future__",
    "dataclasses",
    "enum",
    "typing",
    "backend.container_audit.adapters",
    "backend.container_audit.audit",
    "backend.container_audit.contract",
    "backend.container_audit.filesystem_checks",
    "backend.container_audit.policy",
    "backend.container_audit.system_checks",
}
_CONTAINER_AUDIT_FORBIDDEN_CALLS = {
    "chmod",
    "chown",
    "connect",
    "cursor",
    "execute",
    "getenv",
    "glob",
    "iterdir",
    "lstat",
    "mkdir",
    "open",
    "popen",
    "read",
    "read_bytes",
    "read_text",
    "remove",
    "rename",
    "replace",
    "resolve",
    "rglob",
    "rmdir",
    "rmtree",
    "run",
    "stat",
    "touch",
    "unlink",
    "walk",
    "write",
    "write_bytes",
    "write_text",
}
_CONTAINER_AUDIT_FORBIDDEN_LOAD_NAMES = {
    "__builtins__",
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "eval",
    "exec",
    "getattr",
    "globals",
    "input",
    "locals",
    "open",
    "print",
    "setattr",
    "vars",
}

_MIGRATION_EVIDENCE_FILES = {
    "__init__.py",
    "bound_file.py",
    "checked_io.py",
    "contract.py",
    "errors.py",
    "git_discovery.py",
    "git_remote.py",
    "git_runner.py",
    "manifest.py",
    "package.py",
    "path_checks.py",
    "policy.py",
    "process_tree.py",
    "publication.py",
    "review.py",
    "snapshot.py",
    "verification.py",
    "verification_schema.py",
    "verification_snapshot.py",
    "verification_values.py",
}
_MIGRATION_EVIDENCE_ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "ctypes",
    "dataclasses",
    "enum",
    "hashlib",
    "io",
    "json",
    "msvcrt",
    "os",
    "pathlib",
    "signal",
    "stat",
    "subprocess",
    "tempfile",
    "threading",
    "typing",
    "urllib",
    "uuid",
    "zipfile",
}
_MIGRATION_EVIDENCE_FORBIDDEN_GIT_VERBS = {
    "add",
    "checkout",
    "clean",
    "commit",
    "fetch",
    "merge",
    "move",
    "prune",
    "pull",
    "push",
    "rebase",
    "remove",
    "repair",
    "reset",
    "restore",
    "stash",
}
_REPARENTING_REHEARSAL_FILES = {
    "__init__.py",
    "audit_bridge.py",
    "audit_metadata.py",
    "baseline.py",
    "contract.py",
    "errors.py",
    "evidence_bridge.py",
    "git_runner.py",
    "layout.py",
    "publication.py",
    "rehearsal.py",
    "synthetic_project.py",
    "synthetic_scope.py",
    "verification.py",
    "worktrees.py",
}
_REPARENTING_REHEARSAL_ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "backend",
    "dataclasses",
    "enum",
    "hashlib",
    "os",
    "pathlib",
    "stat",
    "subprocess",
    "tempfile",
}
_REPARENTING_REHEARSAL_FORBIDDEN_GIT_VERBS = {
    "checkout",
    "clean",
    "clone",
    "fetch",
    "merge",
    "move",
    "prune",
    "pull",
    "push",
    "rebase",
    "remove",
    "reset",
    "restore",
    "rm",
    "stash",
}
_CONTAINER_AUDIT_FORBIDDEN_ATTRIBUTES = (
    _CONTAINER_AUDIT_FORBIDDEN_CALLS
    | {
        "Popen",
        "__getattribute__",
        "__subclasses__",
        "call",
        "check_call",
        "check_output",
        "import_module",
        "load_module",
        "system",
    }
)


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


def container_audit_package_files(package: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            path
            for path in package.rglob("*")
            if path.is_file()
            and "__pycache__"
            not in path.relative_to(package).parts
        )
    )


def container_audit_python_paths(package: Path) -> tuple[Path, ...]:
    return tuple(
        path
        for path in container_audit_package_files(package)
        if path.suffix == ".py"
    )


def parse_forbidden_container_audit_references(
    path: Path,
) -> set[str]:
    tree = ast.parse(read_text(path))
    references: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in _CONTAINER_AUDIT_FORBIDDEN_LOAD_NAMES
        ):
            references.add(node.id)
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in _CONTAINER_AUDIT_FORBIDDEN_ATTRIBUTES
        ):
            references.add(_expression_target(node))
    return references


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


def parse_call_targets(path: Path) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(read_text(path))
    return {
        _call_target(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }


def parse_hard_link_references(
    path: Path,
) -> tuple[tuple[str, int, bool], ...]:
    if not path.exists():
        return ()
    tree = ast.parse(read_text(path))
    link_names, references = _hard_link_import_bindings(tree)
    direct_calls = {
        id(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            target = _expression_target(node)
            if node.attr in {"link", "hardlink_to", "link_to"}:
                references.append(
                    (target, node.lineno, id(node) in direct_calls)
                )
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in link_names
        ):
            references.append(
                (
                    f"{node.id}(os.link)",
                    node.lineno,
                    id(node) in direct_calls,
                )
            )
        elif isinstance(node, ast.Call) and _call_target(node.func) == "getattr":
            dynamic = _dynamic_hard_link_target(node)
            if dynamic is not None:
                references.append(
                    (dynamic, node.lineno, id(node) in direct_calls)
                )
    return tuple(sorted(references, key=lambda item: item[1]))


def _hard_link_import_bindings(
    tree: ast.AST,
) -> tuple[set[str], list[tuple[str, int, bool]]]:
    link_names: set[str] = set()
    references: list[tuple[str, int, bool]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module == "os"
        ):
            for alias in node.names:
                if alias.name != "link":
                    continue
                bound = alias.asname or alias.name
                link_names.add(bound)
                suffix = f" as {bound}" if alias.asname else ""
                references.append(
                    (f"from os import link{suffix}", node.lineno, False)
                )
    return link_names, references


def _dynamic_hard_link_target(
    node: ast.Call,
) -> str | None:
    if len(node.args) < 2:
        return None
    attribute = node.args[1]
    if not isinstance(attribute, ast.Constant) or not isinstance(
        attribute.value,
        str,
    ):
        return f"getattr({_expression_target(node.args[0])}, <dynamic>)"
    if attribute.value not in {"link", "hardlink_to", "link_to"}:
        return None
    return (
        f"getattr({_expression_target(node.args[0])}, "
        f"{attribute.value})"
    )


def _call_target(value: ast.expr) -> str:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return f"{_expression_target(value.value)}.{value.attr}"
    return f"<{type(value).__name__}>"


def _expression_target(value: ast.expr) -> str:
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return f"{_expression_target(value.value)}.{value.attr}"
    if isinstance(value, ast.Call):
        return f"{_call_target(value.func)}()"
    return f"<{type(value).__name__}>"


def parse_bound_names(path: Path) -> set[str]:
    return set(parse_name_bindings(path))


def _bound_target_names(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, ast.Starred):
        return _bound_target_names(target.value)
    if isinstance(target, (ast.List, ast.Tuple)):
        return {
            name
            for item in target.elts
            for name in _bound_target_names(item)
        }
    return set()


def parse_name_bindings(path: Path) -> dict[str, list[str]]:
    tree = ast.parse(read_text(path))
    bindings: dict[str, list[str]] = {}

    def add(name: str, kind: str) -> None:
        bindings.setdefault(name, []).append(kind)

    for node in ast.walk(tree):
        if isinstance(node, ast.arg):
            add(node.arg, "argument")
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            add(node.name, "function")
        elif isinstance(node, ast.ClassDef):
            add(node.name, "class")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                add(
                    alias.asname or alias.name.split(".", 1)[0],
                    f"import:{alias.name}:{alias.asname or ''}",
                )
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                add(
                    alias.asname or alias.name,
                    f"from:{node.level}:{node.module or ''}:{alias.name}:"
                    f"{alias.asname or ''}",
                )
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for name in _bound_target_names(target):
                    add(name, "assignment")
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)):
            for name in _bound_target_names(node.target):
                add(name, type(node).__name__)
        elif isinstance(node, ast.AugAssign):
            for name in _bound_target_names(node.target):
                add(name, "AugAssign")
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            for name in _bound_target_names(node.target):
                add(name, type(node).__name__)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if item.optional_vars is not None:
                    for name in _bound_target_names(item.optional_vars):
                        add(name, "with")
        elif isinstance(node, ast.ExceptHandler) and node.name:
            add(node.name, "exception")
        elif isinstance(node, (ast.MatchAs, ast.MatchStar)) and node.name:
            add(node.name, type(node).__name__)
        elif isinstance(node, ast.MatchMapping) and node.rest:
            add(node.rest, "MatchMapping")
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            for name in node.names:
                add(name, type(node).__name__)
        elif isinstance(node, ast.Delete):
            for target in node.targets:
                for name in _bound_target_names(target):
                    add(name, "Delete")
        elif isinstance(node, ast.TypeAlias):
            for name in _bound_target_names(node.name):
                add(name, "TypeAlias")
    return bindings


def parse_forbidden_current_evidence_references(path: Path) -> set[str]:
    tree = ast.parse(read_text(path))
    references: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Load)
            and node.id in _CURRENT_EVIDENCE_FORBIDDEN_LOAD_NAMES
        ):
            references.add(node.id)
        elif (
            isinstance(node, ast.Attribute)
            and node.attr in _CURRENT_EVIDENCE_FORBIDDEN_ATTRIBUTES
        ):
            target = _expression_target(node)
            if target not in _CURRENT_EVIDENCE_ALLOWED_SEARCH_TARGETS:
                references.add(target)
    return references


def binding_inventory_fingerprint(path: Path) -> str:
    tree = ast.parse(read_text(path))
    bindings = "\n".join(
        "{}\0{}".format(name, "\0".join(kinds))
        for name, kinds in sorted(parse_name_bindings(path).items())
    )
    stores = "\n".join(
        f"{name}\0{count}"
        for name, count in sorted(
            {
                selected.id: sum(
                    1
                    for candidate in ast.walk(tree)
                    if isinstance(candidate, ast.Name)
                    and isinstance(candidate.ctx, ast.Store)
                    and candidate.id == selected.id
                )
                for selected in ast.walk(tree)
                if isinstance(selected, ast.Name)
                and isinstance(selected.ctx, ast.Store)
            }.items()
        )
    )
    mutations = "\n".join(parse_non_name_mutation_targets(path))
    canonical = f"[bindings]\n{bindings}\n[stores]\n{stores}\n[mutations]\n{mutations}"
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def parse_non_name_mutation_targets(path: Path) -> list[str]:
    tree = ast.parse(read_text(path))
    observed: list[str] = []
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets.extend(node.targets)
        elif isinstance(
            node,
            (ast.AnnAssign, ast.AugAssign, ast.NamedExpr, ast.For, ast.AsyncFor),
        ):
            targets.append(node.target)
        elif isinstance(node, ast.comprehension):
            targets.append(node.target)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            targets.extend(
                item.optional_vars
                for item in node.items
                if item.optional_vars is not None
            )
        elif isinstance(node, ast.Delete):
            targets.extend(node.targets)
        for target in targets:
            observed.extend(
                f"{type(node).__name__}:{_expression_target(candidate)}"
                for candidate in ast.walk(target)
                if isinstance(candidate, (ast.Attribute, ast.Subscript))
            )
    return sorted(observed)


def parse_import_modules(
    path: Path,
    *,
    package: str | None = None,
) -> set[str]:
    if not path.exists():
        return set()
    tree = ast.parse(read_text(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                selected = package or _package_for_import(path)
                relative = "." * node.level + (node.module or "")
                modules.add(
                    importlib.util.resolve_name(relative, selected)
                    if selected else f"unresolved:{relative}"
                )
            elif node.module:
                modules.add(node.module)
    return modules


def _package_for_import(path: Path) -> str | None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).with_suffix("")
    except (OSError, ValueError):
        return None
    parts = relative.parts[:-1]
    return ".".join(parts) if parts else None


def _mailbox_import_boundary_script_paths(
    root: Path,
    allowed_importer: Path,
) -> list[Path]:
    return [
        path
        for path in (root / "scripts").rglob("*.py")
        if path.resolve() != allowed_importer.resolve()
    ]


_PRIVATE_EVALUATION_ALLOWED_IMPORTS = frozenset({
    "__future__", "argparse", "base64", "binascii", "collections",
    "dataclasses", "datetime", "decimal", "getpass", "hashlib", "hmac",
    "json", "math", "os", "pathlib", "re", "stat", "struct", "tempfile",
    "time", "types", "typing", "unicodedata", "uuid",
    "cryptography.exceptions",
    "cryptography.hazmat.primitives",
    "cryptography.hazmat.primitives.ciphers.aead",
    "cryptography.hazmat.primitives.kdf.hkdf",
    "backend.email_agent.analysis_budget",
    "backend.email_agent.analysis_schema",
    "backend.email_agent.deepseek_analysis_schema",
    "backend.email_agent.model_grounding",
    "backend.email_agent.model_result_safety",
    "backend.email_agent.model_text_safety",
    "backend.email_agent.private_context_gate",
    "backend.email_agent.prompt_context",
    "backend.email_agent.rule_analyzer",
    "backend.email_agent.thread_timeline",
    "backend.project_layout",
    "backend.private_evaluation.case_context",
    "backend.private_evaluation.dataset_builder",
    "backend.private_evaluation.errors",
    "backend.private_evaluation.metrics",
    "backend.private_evaluation.reporting",
    "backend.private_evaluation.repository_io",
    "backend.private_evaluation.repository_path",
    "backend.private_evaluation.runner_values",
    "backend.private_evaluation.schema",
    "backend.private_evaluation.schema_validation",
    "backend.private_evaluation.schema_values",
    "backend.private_evaluation.selection",
    "backend.private_evaluation.staging_contract",
    "backend.private_evaluation.staging_repository",
    "backend.private_evaluation.staging_values",
    "backend.private_evaluation.terminal_judge",
    "backend.private_evaluation.terminal_text_safety",
    "backend.private_knowledge.deidentifier",
    "backend.private_knowledge.entity_patterns",
    "backend.private_knowledge.residual_scanner",
})


def _private_evaluation_imports_are_allowed(imports: set[str]) -> bool:
    return imports.issubset(_PRIVATE_EVALUATION_ALLOWED_IMPORTS)


def reparenting_consumer_candidates(
    root: Path,
    package: Path,
) -> tuple[Path, ...]:
    candidates = [
        path
        for path in (root / "backend").rglob("*.py")
        if not path.resolve().is_relative_to(package.resolve())
    ]
    candidates.extend((root / "scripts").rglob("*.py"))
    candidates.extend(root.glob("*.py"))
    candidates.extend(
        path
        for pattern in ("*.cmd", "*.bat", "*.ps1", "*.sh")
        for path in root.glob(pattern)
        if path.is_file()
    )
    candidates.extend(
        path
        for path in (root / "frontend").rglob("*")
        if path.is_file() and is_text_file(path)
    )
    workflows = root / ".github" / "workflows"
    if workflows.exists():
        candidates.extend(
            path
            for path in workflows.rglob("*")
            if path.is_file() and is_text_file(path)
        )
    return tuple(sorted(set(candidates)))


class ArchitectureConstraintTests(unittest.TestCase):
    def test_private_evaluation_builder_and_tty_judge_are_one_way_isolated(self) -> None:
        package = ROOT / "backend" / "private_evaluation"
        builder = package / "dataset_builder.py"
        stage_values = package / "staging_values.py"
        terminal = package / "terminal_judge.py"
        terminal_text = package / "terminal_text_safety.py"
        self.assertTrue(builder.is_file(), "dataset builder module is missing")
        self.assertTrue(stage_values.is_file(), "pure stage values module is missing")
        self.assertTrue(terminal.is_file(), "terminal judge module is missing")
        self.assertTrue(terminal_text.is_file(), "terminal text safety module is missing")

        builder_imports = parse_import_modules(builder)
        self.assertTrue(
            builder_imports.issubset({
                "__future__", "uuid", "backend.private_evaluation.errors",
                "backend.private_evaluation.schema",
                "backend.private_evaluation.staging_values",
            }),
            sorted(builder_imports),
        )
        self.assertNotIn("staging_repository", read_text(builder))
        self.assertTrue(
            parse_import_modules(stage_values).issubset({
                "__future__", "dataclasses", "uuid",
                "backend.private_evaluation.errors",
                "backend.private_evaluation.schema",
            })
        )
        terminal_imports = parse_import_modules(terminal)
        self.assertTrue(
            terminal_imports.issubset({
                "__future__", "typing", "backend.private_evaluation.errors",
                "backend.private_evaluation.runner_values",
                "backend.private_evaluation.terminal_text_safety",
            }),
            sorted(terminal_imports),
        )
        self.assertNotIn("EvaluationCaseV1", read_text(terminal))
        self.assertNotIn("pathlib", read_text(terminal))
        self.assertNotIn("json", read_text(terminal))
        self.assertNotIn("logging", read_text(terminal))
        self.assertTrue(
            parse_import_modules(terminal_text).issubset({
                "__future__", "unicodedata",
            })
        )

        evaluator = read_text(ROOT / "scripts" / "evaluate_private_deepseek.py")
        for marker in (
            'add_parser("build"', '"--staging"', '"--interactive-judge"',
            "terminal_streams_available", "make_interactive_judge",
            "write_new_encrypted_dataset",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, evaluator)
        for forbidden in (
            '"--transcript"', '"--export"', '"--save"', '"--output"',
            '"--force"', '"--overwrite"', '"--key"', '"--key-file"',
        ):
            self.assertNotIn(forbidden, evaluator)

    def test_private_evaluation_import_policy_canonicalizes_relative_imports(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            probe = Path(temporary) / "probe.py"
            probe.write_text(
                "from ..mailbox_ingest import vault_access\nimport ftplib\n",
                encoding="utf-8",
            )
            imports = parse_import_modules(
                probe, package="backend.private_evaluation"
            )

        self.assertEqual(
            imports, {"backend.mailbox_ingest", "ftplib"}
        )
        self.assertFalse(
            _private_evaluation_imports_are_allowed(imports)
        )

    def test_private_evaluation_backend_import_policy_rejects_new_runtime_and_store_bridges(self) -> None:
        self.assertTrue(_private_evaluation_imports_are_allowed({
            "backend.email_agent.analysis_schema",
            "backend.private_knowledge.residual_scanner",
        }))
        for forbidden in (
            "backend.email_agent.llm_client",
            "backend.mailbox_ingest.knowledge_stage_source",
            "backend.private_knowledge.atomic_ciphertext",
            "backend.private_knowledge.candidate_imports",
            "backend.private_knowledge.storage_policy",
            "backend.private_knowledge.staging",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(
                    _private_evaluation_imports_are_allowed({forbidden})
                )

    def test_private_evaluation_is_isolated_with_exactly_two_narrow_cli_bridges(self) -> None:
        package = ROOT / "backend" / "private_evaluation"
        for path in package.rglob("*.py"):
            imports = parse_import_modules(path)
            with self.subTest(path=path):
                self.assertTrue(
                    _private_evaluation_imports_are_allowed(imports),
                    sorted(imports - _PRIVATE_EVALUATION_ALLOWED_IMPORTS),
                )
                self.assertNotIn("backend.mailbox_ingest", read_text(path))

        evaluator = (ROOT / "scripts" / "evaluate_private_deepseek.py").resolve()
        staging_cli = (ROOT / "scripts" / "manage_mailbox_vault.py").resolve()
        allowed = {evaluator, staging_cli}
        paths = list((ROOT / "backend").rglob("*.py"))
        paths.extend((ROOT / "scripts").rglob("*.py"))
        paths.extend(path for path in (ROOT / "frontend").rglob("*") if path.is_file())
        for path in paths:
            if path.resolve() in allowed or package in path.parents:
                continue
            with self.subTest(path=path, direction="runtime-to-evaluation"):
                self.assertNotIn("backend.private_evaluation", read_text(path))

        script = read_text(evaluator)
        self.assertNotIn("from openai", script)
        self.assertIn("def _live_client_factory", script)
        stage_imports = {
            module
            for module in parse_import_modules(staging_cli)
            if module.startswith("backend.private_evaluation")
        }
        self.assertEqual(
            stage_imports,
            {
                "backend.private_evaluation.staging",
                "backend.private_evaluation.staging_contract",
                "backend.private_evaluation.staging_repository",
            },
        )
        architecture = read_text(ROOT / "docs" / "constraints" / "architecture_constraints.md")
        self.assertIn("private evaluation package is offline and aggregate-only", architecture)
        self.assertIn(
            "scripts/manage_mailbox_vault.py -> backend.private_evaluation staging only",
            architecture,
        )

    def test_private_knowledge_package_isolated_from_mailbox_and_normal_runtime(self) -> None:
        private_package = ROOT / "backend" / "private_knowledge"
        forbidden_imports = {"imaplib", "smtplib", "openai"}
        forbidden_references = ("backend.mailbox_ingest", "backend.email_agent")
        for path in private_package.rglob("*.py"):
            text = read_text(path)
            with self.subTest(path=path):
                self.assertTrue(parse_import_roots(path).isdisjoint(forbidden_imports))
                self.assertTrue(all(value not in text for value in forbidden_references))

        mailbox_package = ROOT / "backend" / "mailbox_ingest"
        for path in mailbox_package.rglob("*.py"):
            with self.subTest(path=path, direction="mailbox-to-private"):
                self.assertNotIn("private_knowledge", read_text(path))

    def test_only_mailbox_admin_cli_may_bridge_mailbox_and_private_knowledge(self) -> None:
        allowed = (ROOT / "scripts" / "manage_mailbox_vault.py").resolve()
        paths = list((ROOT / "backend").rglob("*.py"))
        paths.extend((ROOT / "scripts").rglob("*.py"))
        for path in paths:
            text = read_text(path)
            bridges = "mailbox_ingest" in text and "private_knowledge" in text
            with self.subTest(path=path):
                self.assertFalse(bridges and path.resolve() != allowed)

    def test_runtime_knowledge_loader_has_read_only_projection_dependencies(self) -> None:
        loader = ROOT / "backend" / "private_knowledge" / "runtime_loader.py"
        forbidden = {
            "repository", "review", "deidentifier", "candidate_imports",
            "key_store", "snapshot", "atomic_ciphertext", "cli_service",
        }
        imported_leaves = {
            module.rsplit(".", 1)[-1] for module in parse_import_modules(loader)
        }
        self.assertTrue(imported_leaves.isdisjoint(forbidden), imported_leaves)

        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        self.assertIn(
            "backend.private_knowledge must not import backend.mailbox_ingest",
            architecture,
        )
        self.assertIn("runtime loader is read-only", architecture)

    def test_email_agent_private_knowledge_bridge_is_exactly_allowlisted(self) -> None:
        email_agent = ROOT / "backend" / "email_agent"
        allowed = {
            (email_agent / "private_context_gate.py").resolve(): {
                "backend.private_knowledge.deidentifier",
                "backend.private_knowledge.entity_patterns",
                "backend.private_knowledge.residual_scanner",
            },
            (email_agent / "private_knowledge_context.py").resolve(): {
                "backend.private_knowledge.runtime_schema",
            },
        }
        observed: dict[Path, set[str]] = {}
        for path in email_agent.rglob("*.py"):
            private_imports = {
                module for module in parse_import_modules(path)
                if module.startswith("backend.private_knowledge")
            }
            if private_imports:
                observed[path.resolve()] = private_imports

        self.assertEqual(observed, allowed)

        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        self.assertIn(
            "No other `backend.email_agent` module may import `backend.private_knowledge`",
            architecture,
        )
        self.assertIn("runtime_cards=()", architecture)
        self.assertIn("public field set and diagnostic field shape remain frozen", architecture)
        self.assertIn(
            "provider_output_placeholder_echo` / `safety` / `not_applicable`",
            architecture,
        )
        linter = read_text(
            ROOT / "docs" / "constraints" / "linter_constraints.md"
        )
        self.assertIn("diagnostic field shape remains frozen", linter)
        self.assertIn(
            "provider_output_placeholder_echo` / `safety` / `not_applicable`",
            linter,
        )

    def test_runtime_bootstrap_is_the_only_normal_startup_key_bridge(self) -> None:
        bootstrap = ROOT / "backend" / "private_knowledge" / "runtime_bootstrap.py"
        self.assertTrue(bootstrap.is_file())
        text = read_text(bootstrap)
        self.assertNotIn("backend.email_agent", text)
        self.assertNotIn("logging", text)
        self.assertNotIn("print(", text)

        allowed = (ROOT / "scripts" / "run_local_debug.py").resolve()
        observed = []
        for path in [*(ROOT / "backend").rglob("*.py"), *(ROOT / "scripts").rglob("*.py")]:
            if "backend.private_knowledge.runtime_bootstrap" in parse_import_modules(path):
                observed.append(path.resolve())
        self.assertEqual(observed, [allowed])

        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        self.assertIn("startup-only runtime bootstrap", architecture)
        self.assertIn("no reload, polling, hot update, or status endpoint", architecture)

    def test_current_evidence_call_allowlist_rejects_alias_and_dynamic_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "sample.py"
            source.write_text(
                "def probe(repository):\n"
                "    PLACEHOLDER.search('safe')\n"
                "    repository.search('private')\n"
                "    open('private-store')\n"
                "    operation = open\n"
                "    reader = repository.read\n"
                "    operation('private-store')\n"
                "    reader()\n"
                "    getattr(repository, 'reload')()\n"
                "    tuple_reader, = (repository.read,)\n"
                "    tuple_reader()\n"
                "    (dynamic := open)('private-store')\n"
                "    [open][0]('private-store')\n"
                "    len = repository.read\n"
                "    len()\n"
                "    any = open\n"
                "    any(())\n"
                "    append = __builtins__['open']\n"
                "    append('private-store')\n"
                "    value = 'safe'\n"
                "    value.strip = repository.poll\n"
                "    value.strip()\n"
                "def shadow(PLACEHOLDER, operation=open):\n"
                "    PLACEHOLDER.search('private')\n"
                "    operation('private-store')\n",
                encoding="utf-8",
            )

            unexpected = parse_call_targets(source) - {"PLACEHOLDER.search"}
            bound_names = parse_bound_names(source)
            forbidden_references = parse_forbidden_current_evidence_references(
                source
            )
            non_name_mutations = parse_non_name_mutation_targets(source)

            binding_source = Path(directory) / "bindings.py"
            binding_source.write_text(
                "import safe_module as PLACEHOLDER\n"
                "def function_scope(manager, capability):\n"
                "    for PLACEHOLDER in (capability,):\n"
                "        PLACEHOLDER.search('private')\n"
                "    with manager as PLACEHOLDER:\n"
                "        pass\n"
                "    try:\n"
                "        pass\n"
                "    except Exception as PLACEHOLDER:\n"
                "        pass\n"
                "    return [PLACEHOLDER for PLACEHOLDER in (capability,)]\n"
                "def PLACEHOLDER():\n"
                "    pass\n"
                "class PLACEHOLDER:\n"
                "    pass\n",
                encoding="utf-8",
            )
            binding_kinds = parse_name_bindings(binding_source)["PLACEHOLDER"]

            uncommon_source = Path(directory) / "uncommon_bindings.py"
            uncommon_source.write_text(
                "def mutate(capability):\n"
                "    global receiver\n"
                "    receiver += capability\n"
                "    type alias_receiver = tuple[int]\n",
                encoding="utf-8",
            )
            uncommon_bindings = parse_name_bindings(uncommon_source)

            capability_source = Path(directory) / "capability_attributes.py"
            capability_source.write_text(
                "def inspect(append):\n"
                "    return (append.path, append.key, append.candidate, "
                "append.restoration, append.raw_vault, append.mailbox, "
                "append.authority, append.snapshot, append.repository)\n",
                encoding="utf-8",
            )
            capability_references = (
                parse_forbidden_current_evidence_references(capability_source)
            )

        self.assertEqual(
            unexpected,
            {
                "<Call>",
                "<NamedExpr>",
                "<Subscript>",
                "any",
                "append",
                "getattr",
                "len",
                "open",
                "operation",
                "reader",
                "repository.search",
                "tuple_reader",
                "value.strip",
            },
        )
        self.assertIn("PLACEHOLDER", bound_names)
        self.assertEqual(
            forbidden_references,
            {
                "__builtins__",
                "getattr",
                "open",
                "repository.poll",
                "repository.read",
                "repository.search",
            },
        )
        self.assertEqual(non_name_mutations, ["Assign:value.strip"])
        self.assertEqual(
            set(binding_kinds),
            {
                "For",
                "class",
                "comprehension",
                "exception",
                "function",
                "import:safe_module:PLACEHOLDER",
                "with",
            },
        )
        self.assertEqual(
            uncommon_bindings["receiver"],
            ["Global", "AugAssign"],
        )
        self.assertEqual(
            uncommon_bindings["alias_receiver"],
            ["TypeAlias"],
        )
        self.assertEqual(
            capability_references,
            {
                "append.authority",
                "append.candidate",
                "append.key",
                "append.mailbox",
                "append.path",
                "append.raw_vault",
                "append.repository",
                "append.restoration",
                "append.snapshot",
            },
        )

    def test_current_evidence_handoff_is_contract_only_and_write_only(self) -> None:
        package = ROOT / "backend" / "current_evidence"
        artifact_policy = package / "artifact_policy.py"
        contract = package / "contract.py"
        handoff = package / "handoff.py"
        package_init = package / "__init__.py"
        self.assertTrue(artifact_policy.is_file())
        self.assertTrue(contract.is_file())
        self.assertTrue(handoff.is_file())
        self.assertTrue(package_init.is_file())

        allowed_imports = {
            artifact_policy.resolve(): {"__future__", "re", "unicodedata"},
            contract.resolve(): {
                "__future__", "dataclasses", "datetime", "re", "unicodedata",
                "uuid",
                "backend.current_evidence.artifact_policy",
                "backend.private_knowledge.entity_patterns",
                "backend.private_knowledge.residual_scanner",
            },
            handoff.resolve(): {
                "__future__", "collections.abc", "dataclasses",
                "backend.current_evidence.contract",
            },
            package_init.resolve(): {
                "backend.current_evidence.contract",
                "backend.current_evidence.handoff",
            },
        }
        expected_import_bindings = {
            artifact_policy.resolve(): {
                "annotations": ["from:0:__future__:annotations:"],
                "re": ["import:re:"],
                "unicodedata": ["import:unicodedata:"],
            },
            contract.resolve(): {
                "PLACEHOLDER": [
                    "from:0:backend.private_knowledge.entity_patterns:"
                    "PLACEHOLDER:"
                ],
                "annotations": ["from:0:__future__:annotations:"],
                "dataclass": ["from:0:dataclasses:dataclass:"],
                "datetime": ["from:0:datetime:datetime:"],
                "field": ["from:0:dataclasses:field:"],
                "has_forbidden_artifact": [
                    "from:1:artifact_policy:has_forbidden_artifact:"
                ],
                "re": ["import:re:"],
                "scan_residuals": [
                    "from:0:backend.private_knowledge.residual_scanner:"
                    "scan_residuals:"
                ],
                "timedelta": ["from:0:datetime:timedelta:"],
                "unicodedata": ["import:unicodedata:"],
                "uuid": ["import:uuid:"],
            },
            handoff.resolve(): {
                "Callable": ["from:0:collections.abc:Callable:"],
                "CurrentClickEvidenceV1": [
                    "from:1:contract:CurrentClickEvidenceV1:"
                ],
                "CurrentEvidenceError": [
                    "from:1:contract:CurrentEvidenceError:"
                ],
                "annotations": ["from:0:__future__:annotations:"],
                "dataclass": ["from:0:dataclasses:dataclass:"],
            },
            package_init.resolve(): {
                "CurrentClickEvidenceV1": [
                    "from:1:contract:CurrentClickEvidenceV1:"
                ],
                "submit_current_click_evidence": [
                    "from:1:handoff:submit_current_click_evidence:"
                ],
            },
        }
        for path in package.rglob("*.py"):
            imports = parse_import_modules(path)
            import_bindings = {
                name: kinds
                for name, kinds in parse_name_bindings(path).items()
                if all(
                    kind.startswith(("from:", "import:"))
                    for kind in kinds
                )
            }
            with self.subTest(path=path):
                self.assertEqual(imports, allowed_imports[path.resolve()])
                self.assertEqual(
                    import_bindings,
                    expected_import_bindings[path.resolve()],
                )
                self.assertNotIn("backend.mailbox_ingest", read_text(path))

        expected_call_targets = {
            artifact_policy.resolve(): {
                "_SAFE_CREDENTIAL_POLICY_PROSE.search",
                "any",
                "pattern.search",
                "re.compile",
                "unicodedata.category",
                "unicodedata.normalize",
            },
            contract.resolve(): {
                "AttachmentEvidence", "CurrentEvidenceError", "PLACEHOLDER.search",
                "ThreadEvidence", "_attachment_evidence", "_exact_mapping",
                "_safe_text", "_source_id", "_thread_segments", "_timestamp",
                "_uuid4", "any", "dataclass", "datetime.fromisoformat",
                "enumerate", "field", "has_forbidden_artifact", "int",
                "isinstance", "item.to_mapping", "items.append", "len",
                "object.__new__", "object.__setattr__", "parsed.isoformat",
                "parsed.isoformat().replace", "parsed.utcoffset",
                "pattern.fullmatch", "re.compile", "scan_residuals", "set",
                "str", "super", "super().__init__", "timedelta", "tuple",
                "unicodedata.normalize", "uuid.UUID", "value.endswith",
                "value.rsplit", "value.strip",
            },
            handoff.resolve(): {
                "CurrentClickEvidenceV1.from_mapping", "CurrentEvidenceError",
                "_EvidenceSubmissionResult", "append", "dataclass",
            },
            package_init.resolve(): set(),
        }
        expected_binding_fingerprints = {
            artifact_policy.resolve(): (
                "3cfc02385d84418ea2595d043ab877acee481beb3960f65e645eda37ad1a60dc"
            ),
            contract.resolve(): (
                "2212fd36b03fc72caf8c8f907036b59a7ace4bacea4487e258a072edc4e6a839"
            ),
            handoff.resolve(): (
                "daf883b1bf7772119851627a6cde09d9c1dd90e9571c44cd595633fcd3d76d09"
            ),
            package_init.resolve(): (
                "812fdf2d6df5c9ba478de7e5b56a3c16aec361ab6c5e5225a74262b5a8b5435b"
            ),
        }
        for path in package.rglob("*.py"):
            with self.subTest(exact_call_targets=path):
                self.assertEqual(
                    parse_call_targets(path),
                    expected_call_targets[path.resolve()],
                )
                self.assertEqual(
                    parse_forbidden_current_evidence_references(path),
                    set(),
                )
                self.assertEqual(
                    binding_inventory_fingerprint(path),
                    expected_binding_fingerprints[path.resolve()],
                    parse_name_bindings(path),
                )
        builtins = {
            "any", "enumerate", "int", "isinstance", "len", "object", "set",
            "str", "super", "tuple",
        }
        for path in package.rglob("*.py"):
            self.assertEqual(
                builtins & parse_bound_names(path),
                set(),
                path,
            )
        self.assertEqual(
            parse_name_bindings(contract).get("PLACEHOLDER"),
            ["from:0:backend.private_knowledge.entity_patterns:PLACEHOLDER:"],
        )
        self.assertEqual(
            parse_name_bindings(artifact_policy).get(
                "_SAFE_CREDENTIAL_POLICY_PROSE"
            ),
            ["assignment"],
        )
        self.assertEqual(
            parse_name_bindings(artifact_policy).get("pattern"),
            ["comprehension"],
        )
        self.assertEqual(
            parse_name_bindings(artifact_policy).get("character"),
            ["comprehension"],
        )
        self.assertEqual(
            parse_name_bindings(contract).get("pattern"),
            ["argument"],
        )
        self.assertEqual(
            parse_name_bindings(handoff).get("append"),
            ["argument"],
        )
        handoff_tree = ast.parse(read_text(handoff))
        submit = next(
            node
            for node in handoff_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name == "submit_current_click_evidence"
        )
        self.assertEqual(
            [argument.arg for argument in submit.args.args],
            ["value"],
        )
        self.assertEqual(
            [argument.arg for argument in submit.args.kwonlyargs],
            ["append"],
        )
        self.assertEqual(submit.args.defaults, [])
        self.assertEqual(submit.args.kw_defaults, [None])
        self.assertEqual(
            [ast.unparse(statement) for statement in submit.body],
            [
                "evidence = CurrentClickEvidenceV1.from_mapping(value)",
                "try:\n    append(evidence)\nexcept Exception:\n    raise "
                "CurrentEvidenceError('evidence_append_failed') from None",
                "return _EvidenceSubmissionResult()",
            ],
        )
        artifact_tree = ast.parse(read_text(artifact_policy))
        self.assertEqual(
            [
                node.target.id
                for node in ast.walk(artifact_tree)
                if isinstance(node, ast.comprehension)
                and isinstance(node.target, ast.Name)
            ],
            ["character", "pattern"],
        )
        self.assertEqual(
            {
                node.name
                for node in ast.parse(read_text(handoff)).body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and not node.name.startswith("_")
            },
            {"submit_current_click_evidence"},
        )
        expected_exports = {
            artifact_policy: ["has_forbidden_artifact"],
            package_init: [
                "CurrentClickEvidenceV1", "submit_current_click_evidence",
            ],
            contract: ["CurrentClickEvidenceV1"],
            handoff: ["submit_current_click_evidence"],
        }
        for path, expected in expected_exports.items():
            tree = ast.parse(read_text(path))
            public_exports = next(
                ast.literal_eval(node.value)
                for node in tree.body
                if isinstance(node, ast.Assign)
                and any(
                    isinstance(target, ast.Name) and target.id == "__all__"
                    for target in node.targets
                )
            )
            with self.subTest(exports=path):
                self.assertEqual(public_exports, expected)
        self.assertTrue(
            parse_called_names(artifact_policy).issubset(
                {"any", "category", "compile", "normalize", "search"}
            )
        )
        capability_sources = (contract, handoff, package_init)
        for marker in (
            "mailbox_ingest", "raw_vault", "raw-vault", "authority", "runtime_loader",
            "runtime_bootstrap", "repository", "sqlite", "pathlib", "getenv",
            "environ", "dpapi", "key_store", "snapshot", "provider",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, "\n".join(
                    read_text(path).lower() for path in capability_sources
                ))
        package_source = "\n".join(
            read_text(path).lower() for path in package.rglob("*.py")
        )
        for marker in ("hot_update", "hotupdate", "hot-update"):
            with self.subTest(forbidden_hot_update_surface=marker):
                self.assertNotIn(marker, package_source)

        architecture = " ".join(read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        ).split())
        architecture_tree = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        ).split("## 1. 分层原则", 1)[0]
        for marker in (
            "current_evidence/", "artifact_policy.py", "contract.py", "handoff.py",
        ):
            with self.subTest(architecture_tree=marker):
                self.assertIn(marker, architecture_tree)
        self.assertIn(
            "normal runtime receives only an opaque append capability for "
            "CurrentClickEvidenceV1",
            architecture,
        )
        self.assertIn(
            "no read, get, list, search, query, path, key, repository, raw-vault, "
            "or authority capability",
            architecture,
        )

    def test_superseding_handoff_adr_names_only_the_changed_clauses(self) -> None:
        adr = read_text(
            ROOT / "docs" / "decisions" /
            "0008-bounded-corpus-to-runtime-handoffs.md"
        )
        for marker in (
            "ADR 0006 / Separate the administrator workflow",
            "ADR 0006 / Require two-phase authorization",
            "ADR 0006 / Schedule periodic import or evaluation",
            "ADR 0007 / Acquisition boundary",
            "ADR 0007 / Privacy and media boundary",
            "ADR 0007 / Consequences",
            "future issue #17",
            "future issue #18",
            "write-only",
            "exact current inventory fingerprint",
            "no hot reload",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, adr)
        self.assertIn("Provider route through Budgets remain unchanged", adr)
        self.assertIn("public API and public SQLite remain unchanged", adr)

    def test_private_knowledge_runtime_reads_are_descriptor_bound(self) -> None:
        package = ROOT / "backend" / "private_knowledge"
        checked = package / "checked_reader.py"
        snapshot_reader = package / "read_only_file.py"
        ciphertext = package / "atomic_ciphertext.py"

        self.assertTrue(checked.is_file())
        self.assertIn(
            "backend.private_knowledge.checked_reader",
            parse_import_modules(snapshot_reader),
        )
        self.assertIn(
            "backend.private_knowledge.checked_reader",
            parse_import_modules(ciphertext),
        )
        self.assertTrue({"open", "fstat", "read", "lstat", "close"}.issubset(
            parse_called_names(checked)
        ))
        self.assertFalse({
            "write", "replace", "rename", "unlink", "remove", "rmdir", "mkdir",
        }.intersection(parse_called_names(checked)))
        self.assertIn("O_NOFOLLOW", read_text(checked))

        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        self.assertIn(
            "pre-open and post-read descriptor identity checks",
            " ".join(architecture.split()),
        )
        security = read_text(
            ROOT / "docs" / "security" / "private_knowledge_handling.md"
        )
        self.assertIn("transient immutable plaintext bytes", " ".join(security.split()))
        for path in (
            package / "runtime_bootstrap.py",
            package / "runtime_loader.py",
            package / "read_only_file.py",
        ):
            with self.subTest(alias_binding=path.name):
                self.assertIn("prevalidated_target", read_text(path))
        self.assertIn(
            "original configured snapshot alias against the prevalidated target",
            " ".join(architecture.split()),
        )

    def test_private_payload_metadata_is_removed_before_analyzer_dispatch(self) -> None:
        api = ROOT / "backend" / "email_agent" / "api.py"
        tree = ast.parse(read_text(api))
        reserved = None
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if any(
                isinstance(target, ast.Name)
                and target.id == "_RESERVED_PRIVATE_PAYLOAD_FIELDS"
                for target in node.targets
            ):
                reserved = set(ast.literal_eval(node.value.args[0]))
                break
        expected_reserved = {
            "runtime_cards", "private_context", "knowledge_cards",
            "placeholder_mapping", "card_id", "snapshot_id", "vault_id",
            "private_knowledge_enabled", "private_knowledge_authority_root",
            "private_knowledge_snapshot_path", "protected_roots",
            "project_container",
        }
        self.assertEqual(reserved, expected_reserved)
        self.assertTrue({
            "subject", "from", "to", "cc", "sent_at", "body_text",
            "thread_segments", "attachments", "attachment_files",
            "resource_limitations", "user_confirmed",
        }.isdisjoint(reserved))

        architecture_source = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        architecture = " ".join(architecture_source.split())
        self.assertIn(
            "reserved private-knowledge payload fields before either analyzer branch",
            architecture,
        )
        documented_reserved = architecture_source.split(
            "The API copies only ordinary email-analysis input",
            maxsplit=1,
        )[1].split(
            "Legitimate current-email fields",
            maxsplit=1,
        )[0]
        self.assertEqual(
            set(re.findall(r"`([a-z_]+)`", documented_reserved)),
            expected_reserved,
        )

    def test_remote_exact_fact_boundaries_share_one_canonical_recognizer(self) -> None:
        consumers = (
            ROOT / "backend" / "private_knowledge" / "entity_patterns.py",
            ROOT / "backend" / "email_agent" / "model_exact_fact_safety.py",
            ROOT / "backend" / "email_agent" / "model_grounding.py",
        )
        for path in consumers:
            with self.subTest(path=path):
                self.assertIn(
                    "backend.exact_fact_patterns",
                    parse_import_modules(path),
                )

        required = "`backend.exact_fact_patterns` is the canonical exact-fact recognizer"
        for relative in (
            "docs/constraints/architecture_constraints.md",
            "docs/constraints/linter_constraints.md",
        ):
            with self.subTest(relative=relative):
                self.assertIn(required, read_text(ROOT / relative))

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
            _mailbox_import_boundary_script_paths(ROOT, allowed_importer)
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

    def test_mailbox_import_boundary_recurses_through_nested_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            allowed_importer = root / "scripts" / "manage_mailbox_vault.py"
            nested_script = root / "scripts" / "nested" / "tool.py"
            nested_script.parent.mkdir(parents=True)
            allowed_importer.write_text("", encoding="utf-8")
            nested_script.write_text("", encoding="utf-8")

            paths = _mailbox_import_boundary_script_paths(root, allowed_importer)

        self.assertIn(nested_script, paths)
        self.assertNotIn(allowed_importer, paths)

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

    def test_private_artifact_suffixes_are_ignored(self) -> None:
        required_suffixes = (
            ".sqlite3",
            ".pkevalstage",
            ".pkeval",
            ".pkauth",
            ".pkcand",
            ".pkimpt",
            ".pksnap",
            ".pkkey",
            ".pkstage",
            ".pkenv",
            ".pem",
            ".key",
            ".p12",
            ".pfx",
        )
        missing = [
            suffix
            for suffix in required_suffixes
            if not is_ignored_by_gitignore(
                ROOT / "security-probe" / f"private-artifact{suffix}",
                ROOT,
                GITIGNORE_PATTERNS,
            )
        ]

        self.assertEqual(
            [],
            missing,
            f"Private artifact suffixes missing from .gitignore: {missing}",
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

    def test_multimodal_provider_configuration_and_budgets_are_mechanical(self) -> None:
        config = read_text(ROOT / "backend" / "email_agent" / "config.py")
        budget = read_text(ROOT / "backend" / "email_agent" / "analysis_budget.py")
        extension = read_text(
            ROOT / "frontend" / "browser_extension" / "shared" / "api_client.js"
        )
        local_debug = read_text(ROOT / "frontend" / "local_debug_page" / "app.js")
        evaluation_runner = read_text(ROOT / "backend" / "private_evaluation" / "runner.py")

        self.assertIn('openai_model: str = "gpt-5.6-sol"', config)
        self.assertIn("openai_timeout_seconds: int = 35", config)
        self.assertIn('text_fallback_provider: str = "disabled"', config)
        self.assertNotIn("EMAIL_AGENT_OPENAI_BASE_URL", config)
        self.assertIn("BACKEND_TARGET_SECONDS = 55.0", budget)
        self.assertIn("PROVIDER_MAX_SECONDS = 35.0", budget)
        self.assertIn("DEEPSEEK_PROVIDER_MAX_SECONDS = 10.0", budget)
        self.assertIn("TEXT_FALLBACK_MIN_REMAINING_SECONDS = 12.0", budget)
        self.assertIn("RESPONSE_MARGIN_SECONDS = 5.0", budget)
        self.assertIn("MAX_ANALYZE_TIMEOUT_MS = 60000", extension)
        self.assertIn("ANALYZE_TIMEOUT_MS = 60000", local_debug)
        self.assertIn("deadline=started + 13.0", evaluation_runner)

    def test_project_layout_package_has_no_mutating_or_external_capability(
        self,
    ) -> None:
        package = ROOT / "backend" / "project_layout"
        allowed_import_roots = {
            "__future__",
            "dataclasses",
            "enum",
            "pathlib",
            "stat",
            "typing",
        }
        forbidden_calls = {
            "mkdir",
            "open",
            "remove",
            "rename",
            "replace",
            "rmdir",
            "unlink",
            "write_bytes",
            "write_text",
        }
        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = {
                alias.name.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imported.update(
                node.module.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
            )
            called_attributes = {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
            }
            with self.subTest(path=path.name):
                self.assertLessEqual(imported, allowed_import_roots)
                self.assertTrue(forbidden_calls.isdisjoint(called_attributes))

    def test_container_audit_has_only_pure_injected_metadata_capability(
        self,
    ) -> None:
        package = ROOT / "backend" / "container_audit"
        package_files = container_audit_package_files(package)
        paths = container_audit_python_paths(package)
        files = {
            path.relative_to(package).as_posix()
            for path in package_files
        }
        self.assertEqual(files, _CONTAINER_AUDIT_FILES)

        for path in paths:
            imports = parse_import_modules(path)
            calls = parse_called_names(path)
            references = parse_forbidden_container_audit_references(
                path
            )
            with self.subTest(path=path.name, boundary="imports"):
                self.assertLessEqual(
                    imports,
                    _CONTAINER_AUDIT_ALLOWED_IMPORTS,
                )
            with self.subTest(path=path.name, boundary="calls"):
                self.assertTrue(
                    calls.isdisjoint(
                        _CONTAINER_AUDIT_FORBIDDEN_CALLS
                    ),
                    sorted(
                        calls
                        & _CONTAINER_AUDIT_FORBIDDEN_CALLS
                    ),
                )
            with self.subTest(path=path.name, boundary="references"):
                self.assertFalse(references, sorted(references))

    def test_migration_evidence_is_offline_local_only_and_fixed_scope(
        self,
    ) -> None:
        package = ROOT / "backend" / "migration_evidence"
        paths = tuple(sorted(package.glob("*.py")))
        self.assertEqual(
            {path.name for path in paths},
            _MIGRATION_EVIDENCE_FILES,
        )
        for path in paths:
            imports = parse_import_modules(path)
            disallowed = {
                module
                for module in imports
                if not module.startswith("backend.migration_evidence")
                and module.split(".", 1)[0]
                not in _MIGRATION_EVIDENCE_ALLOWED_IMPORT_ROOTS
            }
            tree = ast.parse(read_text(path))
            string_values = {
                node.value.casefold()
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
            }
            with self.subTest(path=path.name, boundary="imports"):
                self.assertFalse(disallowed, sorted(disallowed))
            with self.subTest(path=path.name, boundary="git-verbs"):
                self.assertTrue(
                    string_values.isdisjoint(
                        _MIGRATION_EVIDENCE_FORBIDDEN_GIT_VERBS
                    )
                )
            with self.subTest(path=path.name, boundary="shell"):
                self.assertNotIn("shell=True", read_text(path))

    def test_migration_evidence_has_only_reviewed_rehearsal_bridge(
        self,
    ) -> None:
        package = (ROOT / "backend" / "migration_evidence").resolve()
        allowed_bridge = (
            ROOT
            / "backend"
            / "reparenting_rehearsal"
            / "evidence_bridge.py"
        ).resolve()
        candidates = [
            path
            for path in (ROOT / "backend").rglob("*.py")
            if not path.resolve().is_relative_to(package)
        ]
        candidates.extend((ROOT / "scripts").rglob("*.py"))
        candidates.extend(
            path
            for path in (ROOT / "frontend").rglob("*")
            if path.is_file() and is_text_file(path)
        )
        workflows = ROOT / ".github" / "workflows"
        if workflows.exists():
            candidates.extend(
                path
                for path in workflows.rglob("*")
                if path.is_file() and is_text_file(path)
            )
        text_reference = re.compile(
            r"\b(?:backend[./])?migration[_-]?evidence\b"
            r"|\b(?:prepare|create|verify)_migration_evidence",
            re.IGNORECASE,
        )
        public_calls = {
            "prepare_migration_evidence_review",
            "create_migration_evidence_package",
            "verify_migration_evidence_package",
        }
        for path in candidates:
            with self.subTest(path=path.relative_to(ROOT)):
                if path.suffix == ".py":
                    imports = parse_import_modules(path)
                    migration_imports = {
                        module
                        for module in imports
                        if module == "backend.migration_evidence"
                        or module.startswith("backend.migration_evidence.")
                    }
                    tree = ast.parse(read_text(path))
                    if any(
                        isinstance(node, ast.ImportFrom)
                        and node.module == "backend"
                        and any(
                            alias.name == "migration_evidence"
                            for alias in node.names
                        )
                        for node in ast.walk(tree)
                    ):
                        migration_imports.add("backend.migration_evidence")
                    called_seams = parse_called_names(path) & public_calls
                    if path.resolve() == allowed_bridge:
                        self.assertEqual(
                            migration_imports,
                            {"backend.migration_evidence"},
                        )
                        self.assertEqual(called_seams, public_calls)
                    else:
                        self.assertFalse(
                            migration_imports | called_seams,
                            f"{path} must not consume migration evidence",
                        )
                else:
                    self.assertIsNone(
                        text_reference.search(read_text(path)),
                        f"{path} must not consume migration evidence",
                    )

    def test_reparenting_rehearsal_has_exact_files_and_imports(
        self,
    ) -> None:
        package = ROOT / "backend" / "reparenting_rehearsal"
        paths = tuple(sorted(package.glob("*.py")))
        self.assertEqual(
            {path.name for path in paths},
            _REPARENTING_REHEARSAL_FILES,
        )
        bridge_imports = {
            "audit_bridge.py": {"backend.container_audit"},
            "evidence_bridge.py": {"backend.migration_evidence"},
            "layout.py": {"backend.project_layout"},
        }
        for path in paths:
            imports = parse_import_modules(path)
            roots = {module.split(".", 1)[0] for module in imports}
            external_backend = {
                module
                for module in imports
                if module.startswith("backend.")
                and not module.startswith(
                    "backend.reparenting_rehearsal"
                )
            }
            with self.subTest(path=path.name):
                self.assertLessEqual(
                    roots,
                    _REPARENTING_REHEARSAL_ALLOWED_IMPORT_ROOTS,
                )
                self.assertEqual(
                    external_backend,
                    bridge_imports.get(path.name, set()),
                )
                self.assertEqual(
                    "subprocess" in roots,
                    path.name == "git_runner.py",
                )

    def test_reparenting_rehearsal_mutations_are_no_clobber(
        self,
    ) -> None:
        package = ROOT / "backend" / "reparenting_rehearsal"
        mutation_files = {
            "publication.py",
            "synthetic_project.py",
            "synthetic_scope.py",
            "worktrees.py",
        }
        for path in sorted(package.glob("*.py")):
            mutating_calls = parse_called_names(path) & {
                "mkdir",
                "open",
                "rename",
                "write_bytes",
                "write_text",
            }
            destructive_calls = parse_called_names(path) & {
                "remove",
                "replace",
                "rmdir",
                "rmtree",
                "unlink",
            }
            tree = ast.parse(read_text(path))
            strings = {
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
            }
            with self.subTest(path=path.name):
                self.assertFalse(destructive_calls)
                if mutating_calls:
                    self.assertIn(path.name, mutation_files)
                self.assertTrue(
                    strings.isdisjoint(
                        _REPARENTING_REHEARSAL_FORBIDDEN_GIT_VERBS
                    )
                )
                self.assertNotIn("shell=True", read_text(path))

    def test_reparenting_hard_link_reference_parser_is_complete(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "candidate.py"
            path.write_text(
                "import os\n"
                "import os as filesystem\n"
                "from os import link as make_link\n"
                "from pathlib import Path\n"
                "os.link('source', 'target')\n"
                "alias = os.link\n"
                "filesystem.link('source', 'target')\n"
                "make_link('source', 'target')\n"
                "getattr(os, 'link')('source', 'target')\n"
                "assigned_os = os\n"
                "assigned_os.link('source', 'target')\n"
                "getattr(assigned_os, dynamic_name)('source', 'target')\n"
                "Path('target').hardlink_to('source')\n"
                "Path('target').link_to('source')\n",
                encoding="utf-8",
            )

            self.assertEqual(
                parse_hard_link_references(path),
                (
                    ("from os import link as make_link", 3, False),
                    ("os.link", 5, True),
                    ("os.link", 6, False),
                    ("filesystem.link", 7, True),
                    ("make_link(os.link)", 8, True),
                    ("getattr(os, link)", 9, True),
                    ("assigned_os.link", 11, True),
                    ("getattr(assigned_os, <dynamic>)", 12, True),
                    ("Path().hardlink_to", 13, True),
                    ("Path().link_to", 14, True),
                ),
            )

    def test_reparenting_hard_link_capability_is_anchor_only(
        self,
    ) -> None:
        package = ROOT / "backend" / "reparenting_rehearsal"
        references = tuple(
            (path.name, *reference)
            for path in sorted(package.glob("*.py"))
            for reference in parse_hard_link_references(path)
        )
        self.assertEqual(
            references,
            (("synthetic_scope.py", "os.link", 77, True),),
        )
        scope = package / "synthetic_scope.py"
        bindings = parse_name_bindings(scope)
        os_bindings = tuple(
            (name, kind)
            for name, kinds in sorted(bindings.items())
            for kind in kinds
            if kind.startswith(("import:os:", "from:0:os:"))
        )
        self.assertEqual(os_bindings, (("os", "import:os:"),))
        tree = ast.parse(read_text(scope))
        calls = tuple(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _call_target(node.func) == "os.link"
        )
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(calls[0].args), 2)
        self.assertEqual(
            tuple(keyword.arg for keyword in calls[0].keywords),
            ("follow_symlinks",),
        )
        self.assertIs(calls[0].keywords[0].value.value, False)

    def test_reparenting_rehearsal_public_seam_is_fixed(
        self,
    ) -> None:
        package = ROOT / "backend" / "reparenting_rehearsal"
        public_tree = ast.parse(read_text(package / "rehearsal.py"))
        public = tuple(
            node
            for node in public_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "rehearse_repository_reparenting"
        )
        self.assertEqual(len(public), 1)
        self.assertEqual(public[0].args.args, [])
        self.assertEqual(
            [item.arg for item in public[0].args.kwonlyargs],
            ["worktree_choices", "fail_at"],
        )
        self.assertEqual(public[0].args.kw_defaults, [None, None])

    def test_reparenting_rehearsal_has_no_host_consumers(
        self,
    ) -> None:
        package = (ROOT / "backend" / "reparenting_rehearsal").resolve()
        candidates = reparenting_consumer_candidates(ROOT, package)
        expected_wrappers = {
            (ROOT / name).resolve()
            for name in (
                "start_local_service.cmd",
                "status_local_service.cmd",
                "restart_local_service.cmd",
                "stop_local_service.cmd",
            )
        }
        self.assertLessEqual(
            expected_wrappers,
            {path.resolve() for path in candidates},
        )
        reference = re.compile(
            r"\b(?:backend[./])?reparenting[_-]?rehearsal\b"
            r"|\brehearse_repository_reparenting\b",
            re.IGNORECASE,
        )
        for path in candidates:
            with self.subTest(path=path.relative_to(ROOT)):
                if path.suffix == ".py":
                    imports = parse_import_modules(path)
                    tree = ast.parse(read_text(path))
                    from_backend = any(
                        isinstance(node, ast.ImportFrom)
                        and node.module == "backend"
                        and any(
                            alias.name == "reparenting_rehearsal"
                            for alias in node.names
                        )
                        for node in ast.walk(tree)
                    )
                    called = (
                        "rehearse_repository_reparenting"
                        in parse_called_names(path)
                    )
                    imported = any(
                        module == "backend.reparenting_rehearsal"
                        or module.startswith(
                            "backend.reparenting_rehearsal."
                        )
                        for module in imports
                    )
                    self.assertFalse(imported or from_backend or called)
                else:
                    self.assertIsNone(
                        reference.search(read_text(path)),
                        f"{path} must not consume the synthetic rehearsal",
                    )

    def test_reparenting_consumer_candidates_cover_every_host_surface(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "backend" / "reparenting_rehearsal"
            paths = (
                package / "__init__.py",
                root / "backend" / "service.py",
                root / "scripts" / "tool.py",
                root / "root_wrapper.py",
                root / "start.cmd",
                root / "frontend" / "extension.js",
                root / ".github" / "workflows" / "guard.yml",
            )
            for path in paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("", encoding="utf-8")

            candidates = reparenting_consumer_candidates(root, package)

        self.assertEqual(
            {path.relative_to(root).as_posix() for path in candidates},
            {
                ".github/workflows/guard.yml",
                "backend/service.py",
                "frontend/extension.js",
                "root_wrapper.py",
                "scripts/tool.py",
                "start.cmd",
            },
        )

    def test_container_audit_guard_rejects_nested_dynamic_capability(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = Path(temporary) / "container_audit"
            nested = package / "host" / "probe.py"
            nested.parent.mkdir(parents=True)
            nested.write_text(
                'reader = open\n'
                'module = __import__("os")\n'
                'runner = module.system\n'
                'getattr(module, "system")("whoami")\n',
                encoding="utf-8",
            )
            executable = package / "host" / "probe.sh"
            executable.write_text("#!/bin/sh\nwhoami\n", encoding="utf-8")

            package_files = container_audit_package_files(package)
            paths = container_audit_python_paths(package)
            references = parse_forbidden_container_audit_references(
                nested
            )

        self.assertIn(executable, package_files)
        self.assertIn(nested, paths)
        self.assertNotIn(executable, paths)
        self.assertLessEqual(
            {"open", "__import__", "getattr", "module.system"},
            references,
        )

    def test_container_audit_has_only_reviewed_rehearsal_bridge(
        self,
    ) -> None:
        package = (ROOT / "backend" / "container_audit").resolve()
        allowed_bridge = (
            ROOT
            / "backend"
            / "reparenting_rehearsal"
            / "audit_bridge.py"
        ).resolve()
        candidates = [
            path
            for path in (ROOT / "backend").rglob("*.py")
            if not path.resolve().is_relative_to(package)
        ]
        candidates.extend((ROOT / "scripts").rglob("*.py"))
        candidates.extend(ROOT.glob("*.py"))
        candidates.extend(
            path
            for pattern in ("*.cmd", "*.bat", "*.ps1", "*.sh")
            for path in ROOT.glob(pattern)
            if path.is_file()
        )
        candidates.extend(
            path
            for path in (ROOT / "frontend").rglob("*")
            if path.is_file() and is_text_file(path)
        )
        workflows = ROOT / ".github" / "workflows"
        if workflows.exists():
            candidates.extend(
                path
                for path in workflows.rglob("*")
                if path.is_file() and is_text_file(path)
            )
        expected_root_wrappers = {
            (ROOT / name).resolve()
            for name in (
                "start_local_service.cmd",
                "status_local_service.cmd",
                "restart_local_service.cmd",
                "stop_local_service.cmd",
            )
        }
        self.assertLessEqual(
            expected_root_wrappers,
            {path.resolve() for path in candidates},
        )

        reference = re.compile(
            r"\b(?:backend[./])?container[_-]?audit\b"
            r"|\brun_container_audit\b",
            re.IGNORECASE,
        )
        for path in candidates:
            with self.subTest(path=path.relative_to(ROOT)):
                if path.suffix == ".py":
                    imports = parse_import_modules(path)
                    audit_imports = {
                        module
                        for module in imports
                        if module == "backend.container_audit"
                        or module.startswith("backend.container_audit.")
                    }
                    called = parse_called_names(path) & {
                        "run_container_audit"
                    }
                    if path.resolve() == allowed_bridge:
                        self.assertEqual(
                            audit_imports,
                            {"backend.container_audit"},
                        )
                        self.assertEqual(
                            called,
                            {"run_container_audit"},
                        )
                    else:
                        self.assertFalse(
                            audit_imports | called,
                            f"{path} must not invoke the manual ContainerAudit",
                        )
                else:
                    self.assertIsNone(
                        reference.search(read_text(path)),
                        f"{path} must not invoke the manual ContainerAudit",
                    )

    def test_protected_location_policy_has_only_reviewed_internal_consumers(
        self,
    ) -> None:
        project_layout = (ROOT / "backend" / "project_layout").resolve()
        allowed_importers = {
            "backend/email_agent/managed_runtime.py",
            "backend/email_agent/standalone_verification.py",
            "backend/mailbox_ingest/protected_storage_path.py",
            "backend/mailbox_ingest/sales_policy_file.py",
            "backend/private_evaluation/repository_path.py",
            "backend/private_knowledge/snapshot_path.py",
            "backend/private_knowledge/storage_policy.py",
            "backend/reparenting_rehearsal/layout.py",
        }
        protected_policy_consumers = {
            "backend/mailbox_ingest/protected_storage_path.py",
            "backend/mailbox_ingest/sales_policy_file.py",
            "backend/private_evaluation/repository_path.py",
            "backend/private_knowledge/snapshot_path.py",
            "backend/private_knowledge/storage_policy.py",
        }
        importers: set[str] = set()
        consumers: set[str] = set()
        for path in (
            *(ROOT / "backend").rglob("*.py"),
            *(ROOT / "scripts").rglob("*.py"),
        ):
            if path.resolve().is_relative_to(project_layout):
                continue
            relative = path.relative_to(ROOT).as_posix()
            imports = parse_import_modules(path)
            if any(
                module == "backend.project_layout"
                or module.startswith("backend.project_layout.")
                for module in imports
            ):
                importers.add(relative)
            if "ProtectedLocationPolicy" in read_text(path):
                consumers.add(relative)
            self.assertNotIn(
                "ProtectedLocationPolicy._create(",
                read_text(path),
                relative,
            )

        self.assertEqual(importers, allowed_importers)
        self.assertEqual(consumers, protected_policy_consumers)

    def test_public_runtime_and_cli_cannot_supply_protected_roots(self) -> None:
        api = read_text(ROOT / "backend" / "email_agent" / "api.py")
        for reserved in ('"protected_roots"', '"project_container"'):
            self.assertIn(reserved, api)

        public_configuration = "\n".join(
            read_text(path)
            for path in (
                ROOT / ".env.example",
                ROOT / "backend" / "email_agent" / "config.py",
                ROOT / "scripts" / "manage_mailbox_vault.py",
                ROOT / "scripts" / "manage_private_knowledge.py",
                ROOT / "scripts" / "evaluate_private_deepseek.py",
                ROOT / "scripts" / "run_local_debug.py",
            )
        )
        for forbidden in (
            "--protected-roots",
            "--project-container",
            "EMAIL_AGENT_PROTECTED_ROOTS",
            "EMAIL_AGENT_PROJECT_CONTAINER",
        ):
            self.assertNotIn(forbidden, public_configuration)

    def test_project_layout_architecture_change_updates_task_template(
        self,
    ) -> None:
        template = read_text(
            ROOT / "docs" / "templates" / "agent_task_brief_template.md"
        )
        self.assertIn(
            "Repository placement and operational layout checklist",
            template,
        )
        self.assertIn("RepositoryPlacement", template)
        self.assertIn("OperationalLayout", template)
        self.assertIn("ProtectedLocationPolicy", template)

    def test_runtime_activation_rehearsal_architecture_is_documented(
        self,
    ) -> None:
        architecture = read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        )
        template = read_text(
            ROOT / "docs" / "templates" / "agent_task_brief_template.md"
        )

        self.assertIn("backend.runtime_activation_rehearsal", architecture)
        self.assertIn(
            "rehearse_managed_runtime_activation(*, adapters=...)",
            architecture,
        )
        self.assertIn("with no defaults", architecture)
        self.assertIn(
            "A runtime activation rehearsal accepts exactly five injected adapters",
            template,
        )
        self.assertIn("no path", template)
        self.assertIn("default host adapter", template)

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
