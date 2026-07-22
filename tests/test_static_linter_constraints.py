"""Custom static linter constraints for the email AI assistant project.

Run:
    python -m unittest discover -s tests -p "test_static_linter_constraints.py"
"""

from __future__ import annotations

import ast
import json
import re
import unittest
from pathlib import Path

from scripts import repo_utils
from scripts.repo_utils import (
    FORBIDDEN_REPO_FILE_NAMES,
    FORBIDDEN_REPO_SUFFIXES,
    has_required_front_matter,
    is_ignored_by_gitignore,
    is_text_file,
    iter_project_files,
    load_gitignore_patterns,
    parse_front_matter,
    read_text,
)
from tests.support import failure_message


ROOT = Path(__file__).resolve().parents[1]

ALLOWED_PRINT_FILES: set[str] = set()

FORBIDDEN_FRONTEND_PATTERNS = {
    "OpenAI API key in frontend": r"OPENAI_API_KEY",
    "DeepSeek API key in frontend": r"\bDEEPSEEK_API_KEY\b",
    "OpenAI secret key literal in frontend": r"\bsk-[A-Za-z0-9_-]{10,}",
    "OpenAI API host in frontend": r"api\.openai\.com",
    "DeepSeek API host in frontend": r"api\.deepseek\.com",
    "OpenAI responses endpoint in frontend": r"/v1/responses",
    "OpenAI chat endpoint in frontend": r"/v1/chat/completions",
    "OpenAI JS client in frontend": r"new\s+OpenAI\s*\(",
    "OpenAI package import in frontend": r"from\s+['\"]openai['\"]|require\(['\"]openai['\"]\)",
    "DeepSeek package import in frontend": r"from\s+['\"]deepseek['\"]|require\(['\"]deepseek['\"]\)",
    "Ollama host in frontend": r"127\.0\.0\.1:11434|localhost:11434",
    "Ollama generate endpoint in frontend": r"/api/generate",
    "Ollama chat endpoint in frontend": r"/api/chat",
    "Ollama marker in frontend": r"\bollama\b",
    "local Qwen model marker in frontend": r"\bqwen(?:3\.6)?\b",
    "local Gemma model marker in frontend": r"\bgemma(?:4)?\b",
    "browser OAuth flow in frontend": r"chrome\.identity|client_secret|refresh_token|access_token",
    "environment access in frontend": r"process\.env|\.env",
    "SQLite access in frontend": r"\bsqlite3?\b",
}

FORBIDDEN_ATTACHMENT_ACQUISITION_PATTERNS = {
    "downloads API": r"\bchrome\.downloads\b",
    "File System Access API": (
        r"\bshow(?:Open|Save)FilePicker\b|\bshowDirectoryPicker\b|"
        r"\bFileSystem(?:File|Directory)?Handle\b|"
        r"\bFileSystem(?:WritableFileStream|SyncAccessHandle)\b|"
        r"\bcreateWritable\b|\bwritable\s*\.\s*write\s*\("
    ),
    "Web Storage": r"\blocalStorage\b|\bsessionStorage\b",
    "IndexedDB": r"\bindexedDB\b",
    "extension storage": (
        r"\bchrome\.storage\b|\bchrome\s*\[\s*['\"]storage['\"]\s*\]"
    ),
    "local path field": (
        r"\b(?:local_path|file_path|webkitRelativePath)\b|"
        r"(?:['\"]path['\"]|\bpath)\s*:|"
        r"\{\s*path\s*(?=[,}])|"
        r"\{\s*(?:[A-Za-z_$][\w$]*\s*,\s*)+path\s*(?=[,}])|"
        r"(?:\.\s*path|\[\s*['\"]path['\"]\s*\])\s*="
    ),
}

FORBIDDEN_EMAIL_ACTION_PATTERNS = {
    "automatic send mail action": r"\bsendMail\b",
    "Gmail send action": r"gmail\.users\.messages\.send",
    "archive action": r"archiveMessage|archive\s*\(",
    "delete action": r"deleteMessage|trashMessage|messages\.trash",
    "modify or move action": r"gmail\.users\.messages\.modify|messages\.modify|moveMessage|move\s*\(",
    "forward action": r"forwardMessage|forward\s*\(",
}

SECRET_PATTERNS = {
    "OpenAI-like secret key": r"\bsk-[A-Za-z0-9_-]{10,}",
    "Google OAuth-like token": r"ya29\.[A-Za-z0-9_-]+",
    "hardcoded password assignment": r"password\s*=\s*['\"][^'\"]+['\"]",
}

GITIGNORE_PATTERNS = load_gitignore_patterns(ROOT)
ALLOWED_DOC_STATUSES = {"draft", "active", "deprecated"}
PERSISTENT_MULTIMODAL_DISCLOSURE = (
    "After you click Analyze, configured remote AI providers may receive locally deidentified "
    "current visible email text and selected current-message images or files after local "
    "screening. Media pixels or document content may contain identifying information and are "
    "not guaranteed to be fully deidentified. Processing is not local-only, and no "
    "zero-retention guarantee is made."
)


class PrintCallVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        # Record line numbers so failures point to the exact mechanical violation.
        self.print_lines: list[int] = []
        self.traceback_print_exc_lines: list[int] = []
        self.bare_except_lines: list[int] = []

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            self.print_lines.append(node.lineno)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "print_exc"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "traceback"
        ):
            self.traceback_print_exc_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.type is None:
            self.bare_except_lines.append(node.lineno)
        self.generic_visit(node)


class StaticLinterConstraintTests(unittest.TestCase):
    def test_private_knowledge_checked_reader_has_no_write_surface(self) -> None:
        package = ROOT / "backend" / "private_knowledge"
        checked = package / "checked_reader.py"
        reader_tree = ast.parse(read_text(checked))
        called = {
            node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
            for node in ast.walk(reader_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Attribute, ast.Name))
        }
        self.assertFalse({
            "write", "replace", "rename", "unlink", "remove", "rmdir", "mkdir",
        }.intersection(called))

        for name in ("read_only_file.py", "atomic_ciphertext.py"):
            tree = ast.parse(read_text(package / name))
            imports_checked_reader = any(
                isinstance(node, ast.ImportFrom)
                and node.level == 1
                and node.module == "checked_reader"
                for node in ast.walk(tree)
            )
            with self.subTest(name=name):
                self.assertTrue(imports_checked_reader)

        linter = " ".join(read_text(
            ROOT / "docs" / "constraints" / "linter_constraints.md"
        ).split())
        self.assertIn("pre-open and post-read parent/target identity", linter)
        self.assertIn("transient immutable bytes", linter)

    def test_private_knowledge_bootstrap_is_startup_only_and_request_free(self) -> None:
        bootstrap = ROOT / "backend" / "private_knowledge" / "runtime_bootstrap.py"
        startup = ROOT / "scripts" / "run_local_debug.py"
        server = ROOT / "backend" / "email_agent" / "server.py"
        api = ROOT / "backend" / "email_agent" / "api.py"

        bootstrap_text = read_text(bootstrap)
        bootstrap_tree = ast.parse(bootstrap_text)
        imported = {
            alias.name
            for node in ast.walk(bootstrap_tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            node.module
            for node in ast.walk(bootstrap_tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        for forbidden in (
            "backend.email_agent", "sqlite3", "imaplib", "smtplib", "logging",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertFalse(any(
                    module == forbidden or module.startswith(f"{forbidden}.")
                    for module in imported
                ))

        startup_text = read_text(startup)
        self.assertEqual(startup_text.count("load_configured_runtime_cards("), 1)
        self.assertLess(startup_text.index("configure_logging("), startup_text.index(
            "load_configured_runtime_cards("
        ))
        self.assertLess(startup_text.index("load_configured_runtime_cards("), startup_text.index(
            "run_server("
        ))

        request_text = read_text(server) + read_text(api)
        for forbidden in (
            "runtime_bootstrap", "load_runtime_knowledge", "open_authority_keys",
            "CurrentUserDpapiProtector", "EMAIL_AGENT_PRIVATE_KNOWLEDGE_",
        ):
            with self.subTest(request_forbidden=forbidden):
                self.assertNotIn(forbidden, request_text)

        linter = read_text(ROOT / "docs" / "constraints" / "linter_constraints.md")
        self.assertIn("only `scripts/run_local_debug.py` may import", linter)
        self.assertIn("runtime bootstrap occurs at most once before server start", linter)
        self.assertIn("untrusted request payload", linter)
        self.assertIn("prevalidated snapshot target", linter)

    def test_bounded_current_evidence_handoff_is_narrowly_documented(self) -> None:
        expected_markers = {
            ROOT / "AGENTS.md": (
                "`CurrentClickEvidenceV1`",
                "write-only deidentified current-click evidence",
                "future issue #17",
                "future issue #18",
            ),
            ROOT / "docs" / "constraints" / "tooling_constraints.md": (
                "`backend.current_evidence`",
                "opaque append capability",
                "no read, get, list, search, query, path, key, repository",
            ),
            ROOT / "docs" / "constraints" / "linter_constraints.md": (
                "`CurrentClickEvidenceV1`",
                "`submit_current_click_evidence`",
                "no reader, path, key, repository, raw-vault, or authority import",
            ),
            ROOT / "docs" / "security" / "email_data_handling.md": (
                "`CurrentClickEvidenceV1`",
                "same explicit Analyze click",
                "not raw thread, attachment bytes, filenames, URLs, or paths",
            ),
            ROOT / "docs" / "security" / "private_knowledge_handling.md": (
                "`CurrentClickEvidenceV1`",
                "separate evidence inbox",
                "write-only append capability",
            ),
            ROOT / "docs" / "api" / "backend_api_contract.md": (
                "`CurrentClickEvidenceV1`",
                "not an HTTP request or response field",
                "opaque append capability",
            ),
            ROOT / "docs" / "operations" /
            "authorized_mailbox_ingest_task_brief.md": (
                "future issue #17",
                "does not add a `sync` command",
                "exact current inventory fingerprint",
            ),
            ROOT / "docs" / "operations" / "project_structure.md": (
                "`backend/current_evidence/`",
                "contract-only",
                "`submit_current_click_evidence`",
            ),
            ROOT / "docs" / "templates" / "agent_task_brief_template.md": (
                "`CurrentClickEvidenceV1`",
                "manual incremental sync",
                "write-only append",
            ),
            ROOT / "docs" / "conventions" / "logging.md": (
                "`evidence_contract_invalid`",
                "`evidence_append_failed`",
                "must not log callback exceptions",
            ),
            ROOT / "docs" / "constraints" / "mechanical_rule_translation.md": (
                "`tests/test_current_evidence_handoff.py`",
                "`test_current_evidence_handoff_is_contract_only_and_write_only`",
                "write-only current-evidence boundary",
            ),
        }
        for path, markers in expected_markers.items():
            text = " ".join(read_text(path).split())
            for marker in markers:
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

    def test_raw_vault_to_knowledge_handoff_is_narrowly_documented(self) -> None:
        governance_paths = (
            ROOT / "docs" / "constraints" / "architecture_constraints.md",
            ROOT
            / "docs"
            / "operations"
            / "authorized_mailbox_ingest_task_brief.md",
        )
        common_markers = (
            "`stage-knowledge`",
            "approved random record IDs",
            "one record at a time",
            "local private-knowledge deidentifier and residual scanner in memory",
            "encrypted deidentified candidate batch",
            "separate knowledge namespace",
            "contain only candidate IDs, counts, and fixed codes",
            "`scripts/manage_private_knowledge.py`",
            "never import or read the raw vault",
            "eight core vault commands",
            "later Task 4 handoff command",
            "`tests/test_manage_mailbox_vault_stage_knowledge.py`",
            "stage_knowledge(",
            "read_one_record",
            "write_encrypted_candidate_batch",
            "synthetic",
            "releases raw plaintext and the ephemeral mapping before the next record",
        )

        for path in governance_paths:
            text = " ".join(read_text(path).split())
            for marker in common_markers:
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

        architecture = " ".join(read_text(governance_paths[0]).split())
        self.assertIn(
            "scripts/manage_mailbox_vault.py -> backend.private_knowledge",
            architecture,
        )

    def test_raw_vault_to_evaluation_stage_handoff_is_narrowly_documented(self) -> None:
        governance_paths = (
            ROOT / "AGENTS.md",
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "constraints" / "architecture_constraints.md",
            ROOT / "docs" / "constraints" / "linter_constraints.md",
            ROOT / "docs" / "operations" / "authorized_mailbox_ingest_task_brief.md",
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md",
            ROOT / "docs" / "operations" / "project_structure.md",
        )
        for path in governance_paths:
            text = " ".join(read_text(path).split())
            for marker in ("`stage-evaluation`", "`.pkevalstage`", "200"):
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

        combined = " ".join(
            " ".join(read_text(path).split()) for path in governance_paths
        )
        for marker in (
            "one record at a time",
            "hidden interactive base64",
            "`evaluation_stage_complete`",
            "only `scripts/manage_mailbox_vault.py` and "
            "`scripts/evaluate_private_deepseek.py`",
            "no mailbox app password",
            "distinct magic, purpose, and namespace",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

        operator_paths = (
            ROOT / "docs" / "operations" / "testing_checklist.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md",
        )
        command = (
            "python -B -m scripts.manage_mailbox_vault stage-evaluation"
        )
        for path in operator_paths:
            with self.subTest(path=path, marker=command):
                self.assertIn(command, " ".join(read_text(path).split()))

        hardened_paths = (
            ROOT / "AGENTS.md",
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "constraints" / "architecture_constraints.md",
            ROOT / "docs" / "constraints" / "linter_constraints.md",
            ROOT / "docs" / "operations" / "authorized_mailbox_ingest_task_brief.md",
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md",
            ROOT / "docs" / "operations" / "project_structure.md",
            ROOT / "docs" / "operations" / "testing_checklist.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
        )
        for path in hardened_paths:
            text = " ".join(read_text(path).split())
            for marker in (
                "`inventory_fingerprint`",
                "evaluation-only source",
                "no evidence accumulation",
            ):
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

    def test_stage_evaluation_template_and_logging_companions_are_explicit(self) -> None:
        template = " ".join(read_text(
            ROOT / "docs" / "templates" / "agent_task_brief_template.md"
        ).split())
        for marker in (
            "`StageEvaluationSelectionV1`",
            "`scope_fingerprint` and `inventory_fingerprint`",
            "exactly 200",
            "evaluation-only source",
            "no evidence accumulation",
            "before plaintext release",
            "hidden interactive base64",
            "`.pkevalstage`",
            "`evaluation_stage_complete`",
            "`argument_invalid`",
            "no network, provider, mailbox app password",
        ):
            with self.subTest(document="task-template", marker=marker):
                self.assertIn(marker, template)

        logging = " ".join(read_text(
            ROOT / "docs" / "conventions" / "logging.md"
        ).split())
        for marker in (
            "`stage-evaluation` writes zero log records",
            "one fixed content-free stdout JSON line",
            "`evaluation_stage_complete`",
            "`argument_invalid`",
            "record IDs, case IDs, paths, text, matched values, keys, or exception detail",
        ):
            with self.subTest(document="logging", marker=marker):
                self.assertIn(marker, logging)

    def test_final_dataset_build_and_interactive_judge_are_narrowly_documented(self) -> None:
        active_paths = (
            ROOT / "AGENTS.md",
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "constraints" / "architecture_constraints.md",
            ROOT / "docs" / "constraints" / "linter_constraints.md",
            ROOT / "docs" / "decisions" / "0006-authorized-mailbox-ingest-and-private-knowledge.md",
            ROOT / "docs" / "operations" / "private_evaluation_build_interactive_task_brief.md",
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md",
            ROOT / "docs" / "operations" / "testing_checklist.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
            ROOT / "docs" / "operations" / "project_structure.md",
            ROOT / "docs" / "templates" / "agent_task_brief_template.md",
            ROOT / "docs" / "conventions" / "logging.md",
        )
        combined = " ".join(
            " ".join(read_text(path).split()) for path in active_paths
        )
        for marker in (
            "`.pkevalstage`", "`.pkeval`", "fresh UUIDv4",
            "same operator-supplied 32-byte", "real local TTY",
            "`--interactive-judge`", "`UsefulnessJudgeView`",
            "no transcript", "20 Flash", "180 Flash", "40 Pro",
            "zero retry", "no automatic production model switch",
            "aggregate-only", "fixed exact-y readiness",
            "terminal control", "atomic no-clobber",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

        operator_paths = (
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md",
            ROOT / "docs" / "operations" / "testing_checklist.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
        )
        commands = (
            "python -B -m scripts.evaluate_private_deepseek build --staging",
            "python -B -m scripts.evaluate_private_deepseek verify --dataset",
            "python -B -m scripts.evaluate_private_deepseek run --dataset",
            "--interactive-judge",
        )
        for path in operator_paths:
            text = " ".join(read_text(path).split())
            for marker in commands:
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

        runbook = " ".join(read_text(operator_paths[0]).split())
        for marker in (
            "`build` reads only the reviewed `.pkevalstage`",
            "`verify` and `run` read only the final `.pkeval`",
            "never imports or reads the raw vault",
            "Create-only final publication performs all target validation before "
            "the atomic link and performs no target-identity check after the final "
            "commit point",
        ):
            with self.subTest(document="private-evaluation-runbook", marker=marker):
                self.assertIn(marker, runbook)

        publication_paths = (
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "constraints" / "architecture_constraints.md",
            ROOT / "docs" / "decisions" / "0006-authorized-mailbox-ingest-and-private-knowledge.md",
            ROOT / "docs" / "operations" / "private_evaluation_build_interactive_task_brief.md",
            ROOT / "docs" / "operations" / "private_deepseek_evaluation.md",
            ROOT / "docs" / "operations" / "deployment_notes.md",
            ROOT / "docs" / "operations" / "project_structure.md",
            ROOT / "docs" / "templates" / "agent_task_brief_template.md",
        )
        for path in publication_paths:
            text = " ".join(read_text(path).split())
            for marker in (
                "final commit point",
                "never rolls back or unlinks the target by pathname",
            ):
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

        constraints = " ".join(read_text(
            ROOT / "docs" / "constraints" / "architecture_constraints.md"
        ).split())
        self.assertIn(
            "parse -> interactive flag -> exact confirmation -> TTY -> readiness -> hidden key -> "
            "dataset -> provider configuration -> client construction -> calls",
            constraints,
        )

    def test_authorized_mailbox_exception_is_narrowly_documented(self) -> None:
        governance_markers = {
            ROOT / "AGENTS.md": (
                "administrator-only CLI",
                "one authorized account",
                "rolling 24-month window",
                "no scheduled job",
                "scripts/manage_mailbox_vault.py",
            ),
            ROOT / "docs" / "product" / "feature_scope.md": (
                "administrator-only CLI",
                "one authorized account",
                "rolling 24-month window",
                "browser extension remains click-only",
            ),
            ROOT / "docs" / "security" / "email_data_handling.md": (
                "inventory fingerprint",
                "external BitLocker",
                "DPAPI",
                "Codex and DeepSeek never read the raw vault",
            ),
            ROOT / "docs" / "security" / "privacy_rules.md": (
                "one authorized account",
                "no scheduled job",
                "no browser or normal-runtime integration",
                "administrator-only CLI",
            ),
        }

        for path, markers in governance_markers.items():
            text = read_text(path)
            for marker in markers:
                with self.subTest(path=path, marker=marker):
                    self.assertIn(marker, text)

    def test_browser_extension_permissions_remain_current_message_only(self) -> None:
        manifest = json.loads(
            read_text(ROOT / "frontend" / "browser_extension" / "manifest.json")
        )

        self.assertEqual(set(manifest["permissions"]), {"activeTab", "sidePanel"})
        self.assertEqual(
            set(manifest["host_permissions"]),
            {"https://exmail.qq.com/*", "http://127.0.0.1:8765/*"},
        )
        self.assertIn("currently opened Tencent Exmail message", manifest["description"])

    def test_attachment_acquisition_guard_covers_persistence_and_path_surfaces(self) -> None:
        samples = {
            "downloads API": ("chrome.downloads.download({url});",),
            "File System Access API": (
                "await showOpenFilePicker();",
                "await showSaveFilePicker();",
                "await showDirectoryPicker();",
                "const handle = new FileSystemHandle();",
                "const fileHandle = new FileSystemFileHandle();",
                "const directoryHandle = new FileSystemDirectoryHandle();",
                "const stream = new FileSystemWritableFileStream();",
                "const access = new FileSystemSyncAccessHandle();",
                "await handle.createWritable();",
                "await writable.write(bytes);",
            ),
            "Web Storage": ("localStorage.setItem('attachment', value);",),
            "IndexedDB": ("indexedDB.open('attachments');",),
            "extension storage": (
                "chrome.storage.local.set({attachment: value});",
                "chrome['storage'].local.set({attachment: value});",
            ),
            "local path field": (
                "const payload = {'local_path': selectedPath};",
                "const payload = {file_path: selectedPath};",
                "const payload = {path};",
                "const payload = {filename, path};",
                "payload.path = selectedPath;",
                "payload['path'] = selectedPath;",
                "payload.local_path = selectedPath;",
                "payload['file_path'] = selectedPath;",
                "const leaked = file.webkitRelativePath;",
            ),
        }
        for label, rule_samples in samples.items():
            pattern = FORBIDDEN_ATTACHMENT_ACQUISITION_PATTERNS[label]
            for sample in rule_samples:
                with self.subTest(label=label, sample=sample):
                    self.assertIsNotNone(
                        re.search(pattern, sample, re.IGNORECASE),
                        f"Attachment guard does not reject {label}: {sample}",
                    )

    def test_attachment_acquisition_guard_does_not_reject_safe_file_picker_code(self) -> None:
        safe_samples = (
            "const file = input.files[0];",
            "const reader = new FileReader();",
            "const payload = {attachment_files: files};",
            "const pathname = new URL(resourceUrl).pathname;",
            "const responseUrl = response.url;",
            "process(filename, path, options);",
            "await response.write(bytes);",
        )
        for sample in safe_samples:
            for label, pattern in FORBIDDEN_ATTACHMENT_ACQUISITION_PATTERNS.items():
                with self.subTest(label=label, sample=sample):
                    self.assertIsNone(re.search(pattern, sample, re.IGNORECASE))

    def test_browser_extension_has_no_persistent_attachment_acquisition_surface(self) -> None:
        extension = ROOT / "frontend" / "browser_extension"
        for path in extension.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FORBIDDEN_ATTACHMENT_ACQUISITION_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(
                        re.search(pattern, text, re.IGNORECASE),
                        failure_message(
                            f"{path} triggers forbidden attachment surface: {rule_name}.",
                            "Attachment acquisition must remain click-only, in-memory, and path-free.",
                            "docs/security/email_data_handling.md",
                        ),
                    )

    def test_analysis_diagnostic_calls_use_only_safe_keywords(self) -> None:
        path = ROOT / "backend" / "email_agent" / "analysis_model_routes.py"
        tree = ast.parse(read_text(path))
        calls = [
            node for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "log_analysis_fallback"
        ]
        self.assertEqual(len(calls), 1)
        self.assertEqual(
            {item.arg for item in calls[0].keywords},
            {
                "code",
                "stage",
                "provider",
                "model",
                "output_mode",
                "detail",
                "elapsed_ms",
            },
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
                        for pattern in FORBIDDEN_FRONTEND_PATTERNS.values()
                    ),
                    f"Frontend guard does not reject {label}.",
                )

    def test_deepseek_reuses_pinned_openai_sdk_without_remote_base_url_configuration(self) -> None:
        requirements = read_text(ROOT / "requirements.txt")
        tooling = read_text(ROOT / "docs" / "constraints" / "tooling_constraints.md")
        deployment = read_text(ROOT / "docs" / "operations" / "deployment_notes.md")

        self.assertIn("openai==2.45.0", requirements)
        self.assertNotRegex(requirements, r"(?im)^\s*deepseek(?:[-_.][A-Za-z0-9]+)*\s*[=<>~!]")
        for path, guidance in (
            ("docs/constraints/tooling_constraints.md", tooling),
            ("docs/operations/deployment_notes.md", deployment),
        ):
            with self.subTest(path=path):
                self.assertIn("OpenAI-compatible", guidance)
                self.assertIn("arbitrary remote base URL", guidance)
                self.assertIn("third-party DeepSeek SDK", guidance)

    def test_active_phase_two_brief_keeps_provider_disabled_by_default(self) -> None:
        brief = read_text(
            ROOT / "docs" / "operations" / "phase_two_attachment_thread_task_brief.md"
        )

        self.assertIn("The provider remains disabled by default", brief)
        self.assertIn(
            "`qwen3.6:latest` is the default configured model when Ollama is explicitly enabled",
            brief,
        )
        self.assertNotIn("defaults to `EMAIL_AGENT_LLM_PROVIDER=ollama`", brief)

    def test_multimodal_governance_pins_disclosure_provider_and_budget_boundaries(self) -> None:
        disclosure_paths = (
            ROOT / "AGENTS.md",
            ROOT / "docs" / "product" / "feature_scope.md",
            ROOT / "docs" / "security" / "email_data_handling.md",
            ROOT / "docs" / "security" / "privacy_rules.md",
        )
        for path in disclosure_paths:
            with self.subTest(path=path):
                self.assertIn(PERSISTENT_MULTIMODAL_DISCLOSURE, read_text(path))

        boundary_paths = (
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "constraints" / "architecture_constraints.md",
            ROOT / "docs" / "constraints" / "linter_constraints.md",
        )
        for path in boundary_paths:
            guidance = read_text(path)
            with self.subTest(path=path):
                self.assertIn("gpt-5.6-sol", guidance)
                self.assertIn("60 seconds", guidance)
                self.assertIn("55 seconds", guidance)
                self.assertIn("35 seconds", guidance)
                self.assertIn("12 seconds", guidance)
                self.assertIn("fixed official endpoint", guidance)

        template = read_text(ROOT / "docs" / "templates" / "agent_task_brief_template.md")
        self.assertIn("EMAIL_AGENT_OPENAI_MODEL", template)
        self.assertIn("EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS", template)
        self.assertIn("EMAIL_AGENT_TEXT_FALLBACK_PROVIDER", template)
        self.assertIn("exact persistent pre-click disclosure", template)

    def test_pinned_dependency_versions_are_consistent_across_active_guidance(self) -> None:
        expected_versions = {
            "cryptography": "49.0.0",
            "openai": "2.45.0",
            "pypdf": "6.14.2",
            "python-docx": "1.2.0",
            "Pillow": "12.3.0",
            "pytesseract": "0.3.13",
        }
        requirements = read_text(ROOT / "requirements.txt")
        repo_utils.parse_pinned_dependency_versions(requirements)
        guidance_files = [
            ROOT / "AGENTS.md",
            ROOT / "README.md",
            ROOT / "docs" / "constraints" / "tooling_constraints.md",
            ROOT / "docs" / "operations" / "phase_two_attachment_thread_task_brief.md",
        ]

        for package, version in expected_versions.items():
            pin = f"{package}=={version}"
            with self.subTest(package=package, path="requirements.txt"):
                self.assertIn(pin, requirements)
            package_guidance_files = guidance_files
            if package == "cryptography":
                package_guidance_files = [
                    ROOT / "AGENTS.md",
                    ROOT / "README.md",
                    ROOT / "docs" / "constraints" / "tooling_constraints.md",
                ]
            for path in package_guidance_files:
                with self.subTest(package=package, path=path):
                    marker = (
                        rf"{re.escape(package)}"
                        rf"(?:==|\s*\|\s*|\s+){re.escape(version)}"
                    )
                    self.assertRegex(read_text(path), marker)

    def test_no_forbidden_repository_files_are_unignored(self) -> None:
        for path in iter_project_files(ROOT):
            name = path.name.lower()
            suffix = path.suffix.lower()
            if name in FORBIDDEN_REPO_FILE_NAMES or suffix in FORBIDDEN_REPO_SUFFIXES:
                with self.subTest(path=path):
                    self.assertTrue(
                        is_ignored_by_gitignore(path, ROOT, GITIGNORE_PATTERNS),
                        failure_message(
                            f"{path} 是敏感或本地运行文件，且未被 .gitignore 忽略。",
                            "删除该文件或加入 .gitignore；示例配置只放 .env.example。",
                            "docs/security/api_key_rules.md",
                        ),
                    )
            with self.subTest(path=path):
                self.assertFalse(
                    name.endswith(".token") or name.endswith(".secret"),
                    failure_message(
                        f"{path} 看起来是 token 或 secret 文件。",
                        "移出版本库，并改用环境变量或本地受控配置。",
                        "docs/security/api_key_rules.md",
                    ),
                )

    def test_no_print_traceback_or_bare_except_in_backend_business_code(self) -> None:
        backend = ROOT / "backend"
        if not backend.exists():
            self.skipTest("backend/ does not exist yet")

        for path in backend.rglob("*.py"):
            if path.name in ALLOWED_PRINT_FILES:
                continue
            try:
                tree = ast.parse(read_text(path))
            except SyntaxError as exc:
                self.fail(
                    failure_message(
                        f"{path} 存在 Python 语法错误：{exc}",
                        "先修复语法错误，再运行静态约束测试。",
                        "docs/constraints/linter_constraints.md",
                    )
                )

            visitor = PrintCallVisitor()
            visitor.visit(tree)
            self.assertFalse(
                visitor.print_lines,
                failure_message(
                    f"{path} 在行 {visitor.print_lines} 使用了裸 print()。",
                    "改用 logging.getLogger(__name__)，并避免输出真实邮件正文或密钥。",
                    "docs/conventions/logging.md",
                ),
            )
            self.assertFalse(
                visitor.traceback_print_exc_lines,
                failure_message(
                    f"{path} 在行 {visitor.traceback_print_exc_lines} 使用了 traceback.print_exc()。",
                    "改用 logger.exception(...) 并保留必要上下文。",
                    "docs/conventions/logging.md",
                ),
            )
            self.assertFalse(
                visitor.bare_except_lines,
                failure_message(
                    f"{path} 在行 {visitor.bare_except_lines} 使用了裸 except。",
                    "捕获明确异常类型，例如 except ValueError as exc。",
                    "docs/conventions/logging.md",
                ),
            )

    def test_frontend_has_no_openai_secret_or_direct_api_call(self) -> None:
        frontend = ROOT / "frontend"
        if not frontend.exists():
            self.skipTest("frontend/ does not exist yet")

        for path in frontend.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FORBIDDEN_FRONTEND_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(
                        re.search(pattern, text, re.IGNORECASE),
                        failure_message(
                            f"{path} 触发前端禁用规则：{rule_name}。",
                            "前端只能调用本地后端 API；OpenAI key 和 OpenAI 调用必须留在后端 llm_client.py。",
                            "docs/constraints/linter_constraints.md",
                        ),
                    )

    def test_frontend_has_no_dangerous_email_action(self) -> None:
        frontend = ROOT / "frontend"
        if not frontend.exists():
            self.skipTest("frontend/ does not exist yet")

        for path in frontend.rglob("*"):
            if not path.is_file() or not is_text_file(path):
                continue
            text = read_text(path)
            for rule_name, pattern in FORBIDDEN_EMAIL_ACTION_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    self.assertIsNone(
                        re.search(pattern, text, re.IGNORECASE),
                        failure_message(
                            f"{path} 触发高风险邮箱动作规则：{rule_name}。",
                            "第一阶段禁止自动发送、删除、归档邮件；只允许用户点击后分析当前邮件。",
                            "docs/product/feature_scope.md",
                        ),
                    )

    def test_no_raw_secret_literals_in_text_files(self) -> None:
        documented_pattern_files = {
            "linter_constraints.md",
            "test_static_linter_constraints.py",
            "test_architecture_constraints.py",
            "api_key_rules.md",
        }
        for path in iter_project_files(ROOT):
            if not is_text_file(path):
                continue
            if path.name in documented_pattern_files:
                continue
            text = read_text(path)

            for rule_name, pattern in SECRET_PATTERNS.items():
                with self.subTest(rule=rule_name, path=path):
                    matches = list(re.finditer(pattern, text, re.IGNORECASE))
                    if rule_name == "OpenAI-like secret key":
                        matches = [
                            match for match in matches
                            if not match.group(0).lower().startswith("sk-your-")
                        ]
                    self.assertFalse(
                        matches,
                        failure_message(
                            f"{path} 出现疑似敏感值：{rule_name}。",
                            "删除真实密钥；测试中使用 your_api_key_here 这类明显假值。",
                            "docs/security/api_key_rules.md",
                        ),
                    )

    def test_docs_markdown_files_have_front_matter(self) -> None:
        docs = ROOT / "docs"
        if not docs.exists():
            self.skipTest("docs/ does not exist yet")

        for path in docs.rglob("*.md"):
            text = read_text(path)
            with self.subTest(path=path):
                self.assertTrue(
                    has_required_front_matter(text),
                    failure_message(
                        f"{path} 缺少标准 YAML front matter。",
                        "在文件顶部补充 last_update、status、owner、review_cycle、source_type。",
                        "docs/operations/documentation_rules.md",
                    ),
                )

    def test_docs_markdown_front_matter_status_uses_allowed_values(self) -> None:
        docs = ROOT / "docs"
        if not docs.exists():
            self.skipTest("docs/ does not exist yet")

        for path in docs.rglob("*.md"):
            text = read_text(path)
            if not has_required_front_matter(text):
                continue
            status = parse_front_matter(text).get("status")
            with self.subTest(path=path):
                self.assertIn(
                    status,
                    ALLOWED_DOC_STATUSES,
                    failure_message(
                        f"{path} 使用了非法 docs front matter status: {status}。",
                        "改用 draft、active 或 deprecated；任务执行状态应写在正文 Current Status 中。",
                        "docs/operations/documentation_rules.md",
                    ),
                )


if __name__ == "__main__":
    unittest.main()
