"""Executable architecture constraints for the email AI assistant project.

Run:
    python -m unittest discover -s tests -p "test_architecture_constraints.py"
"""

from __future__ import annotations

import ast
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
            artifact_policy.resolve(): {"__future__", "re"},
            contract.resolve(): {
                "__future__", "dataclasses", "datetime", "re", "uuid",
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
        for path in package.rglob("*.py"):
            imports = parse_import_modules(path)
            with self.subTest(path=path):
                self.assertEqual(imports, allowed_imports[path.resolve()])
                self.assertNotIn("backend.mailbox_ingest", read_text(path))

        self.assertTrue(
            parse_called_names(handoff).isdisjoint({
                "read", "get", "list", "search", "query", "find", "open",
                "load", "delete", "remove", "connect", "reload", "poll",
                "watch", "schedule",
            })
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
            parse_called_names(artifact_policy).issubset({"any", "compile", "search"})
        )
        capability_sources = (contract, handoff, package_init)
        for marker in (
            "mailbox_ingest", "raw_vault", "authority", "runtime_loader",
            "runtime_bootstrap", "repository", "sqlite", "pathlib", "getenv",
            "environ", "dpapi", "key_store", "snapshot", "provider",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, "\n".join(
                    read_text(path).lower() for path in capability_sources
                ))

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
        self.assertEqual(reserved, {
            "runtime_cards", "private_context", "knowledge_cards",
            "placeholder_mapping", "card_id", "snapshot_id", "vault_id",
            "private_knowledge_enabled", "private_knowledge_authority_root",
            "private_knowledge_snapshot_path",
        })
        self.assertTrue({
            "subject", "from", "to", "cc", "sent_at", "body_text",
            "thread_segments", "attachments", "attachment_files",
            "resource_limitations", "user_confirmed",
        }.isdisjoint(reserved))

        architecture = " ".join(read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        ).split())
        self.assertIn(
            "reserved private-knowledge payload fields before either analyzer branch",
            architecture,
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
