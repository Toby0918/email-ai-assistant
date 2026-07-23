"""Contracts for the offline-ready multimodal current-email documentation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCS = (
    "docs/api/backend_api_contract.md",
    "docs/api/frontend_backend_flow.md",
    "docs/prompts/analyzer_prompt.md",
    "docs/data/analysis_result_schema.md",
    "docs/security/api_key_rules.md",
    "docs/operations/testing_checklist.md",
    "docs/product/roadmap.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/product/feature_scope.md",
    "docs/security/privacy_rules.md",
    "docs/security/email_data_handling.md",
)

DISCLOSURE = (
    "After you click Analyze, configured remote AI providers may receive locally "
    "deidentified current visible email text and selected current-message images "
    "or files after local screening. Media pixels or document content may contain "
    "identifying information and are not guaranteed to be fully deidentified. "
    "Processing is not local-only, and no zero-retention guarantee is made."
)

OPENAI_LIVE_COMPATIBILITY = (
    "OpenAI omits `text.format`; the JSON-only prompt is enforced by strict "
    "local validation."
)

OPENAI_CONTRACT_DOCS = (
    "AGENTS.md",
    "docs/api/backend_api_contract.md",
    "docs/prompts/analyzer_prompt.md",
    "docs/operations/testing_checklist.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/decisions/0007-multimodal-current-email-analysis.md",
)

OPENAI_TOUCHED_ACTIVE_DOCS = frozenset(OPENAI_CONTRACT_DOCS[1:5])

ATTACHMENT_TOUCHED_ACTIVE_DOCS = frozenset(
    {
        "docs/api/backend_api_contract.md",
        "docs/api/frontend_backend_flow.md",
        "docs/operations/testing_checklist.md",
        "docs/operations/multimodal_current_email_analysis_task_brief.md",
        "docs/product/roadmap.md",
        "docs/security/email_data_handling.md",
    }
)

BOUNDED_HANDOFF_TOUCHED_ACTIVE_DOCS = frozenset(
    {
        "docs/api/backend_api_contract.md",
        "docs/security/email_data_handling.md",
    }
)

GOVERNED_CORPUS_TOUCHED_ACTIVE_DOCS = frozenset(
    {"docs/operations/testing_checklist.md"}
)

AUTOMATIC_ATTACHMENT_SMOKE_TOUCHED_DOCS = frozenset(
    {
        "docs/operations/testing_checklist.md",
        "docs/product/roadmap.md",
        "docs/operations/multimodal_current_email_analysis_task_brief.md",
    }
)

ATTACHMENT_STATUS_SURFACES = (
    "docs/operations/testing_checklist.md",
    "docs/product/roadmap.md",
    "docs/operations/multimodal_current_email_analysis_task_brief.md",
    "docs/operations/project_status_log.md",
    "scripts/generate_project_status.py",
)

ATTACHMENT_SMOKE_MARKERS = (
    "Attachment Task 5 bounded automatic current-message smoke is complete",
    "two automatic attachment insights reported `parsed`",
    "zero non-parsed attachment insights",
    "remote providers were disabled",
    "request temporary directory returned to zero files",
)

TASK9_REPAIR_MARKERS = (
    "Task 9 semantic accuracy repair is offline complete",
    "parsed attachment status does not prove semantic correctness",
    "Any new live operation still requires fresh explicit authorization",
)

STALE_ATTACHMENT_SMOKE_CLAIMS = (
    "Task 5 real current-message attachment smoke remains pending",
    "The new attachment acquisition path is not live-tested",
)

PRIOR_TASK9_STATUS_DOCS = {
    "docs/decisions/0007-multimodal-current-email-analysis.md": "2026-07-22",
    "docs/operations/task9_semantic_accuracy_repair_task_brief.md": "2026-07-21",
}


class MultimodalDocumentationContractTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_active_docs_use_the_option_c_provider_contract(self) -> None:
        combined = "\n".join(self._read(path) for path in ACTIVE_DOCS)
        for marker in (
            "https://api.openai.com/v1",
            "gpt-5.6-sol",
            "Responses API",
            "store=false",
            "max_retries=0",
            "no tools",
            "JSON-only prompt",
            "max_output_tokens=2400",
            "one OpenAI multimodal primary call",
            "one DeepSeek text-only fallback",
            "deterministic rules last",
            "all providers disabled by default",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_openai_contract_omits_live_rejected_legacy_format(self) -> None:
        for relative in OPENAI_CONTRACT_DOCS:
            text = self._read(relative)
            with self.subTest(path=relative):
                self.assertIn(OPENAI_LIVE_COMPATIBILITY, text)

    def test_openai_payload_tuning_matches_the_fixed_runtime_contract(self) -> None:
        combined = "\n".join(
            self._read(path)
            for path in (
                "docs/api/backend_api_contract.md",
                "docs/prompts/analyzer_prompt.md",
                "docs/operations/multimodal_current_email_analysis_task_brief.md",
            )
        )
        for marker in (
            "text.verbosity=low",
            "reasoning.effort=low",
            "detail=high",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_budget_contract_is_current_and_old_runtime_budget_is_absent(self) -> None:
        for relative in (
            "docs/api/backend_api_contract.md",
            "docs/api/frontend_backend_flow.md",
            "docs/prompts/analyzer_prompt.md",
            "docs/operations/testing_checklist.md",
            "scripts/generate_project_status.py",
        ):
            text = self._read(relative)
            with self.subTest(path=relative):
                for marker in (
                    "60-second",
                    "55-second",
                    "35-second",
                    "10-second",
                    "12-second",
                    "8-second",
                    "5-second",
                    "20-second resource collection",
                ):
                    self.assertIn(marker, text)
                self.assertNotIn("15/13/10/5", text)
                self.assertNotIn("13-second cooperative", text)

    def test_public_schema_and_engine_labels_remain_stable(self) -> None:
        combined = self._read("docs/data/analysis_result_schema.md") + self._read(
            "docs/api/backend_api_contract.md"
        )
        for marker in (
            "unchanged public analysis schema",
            "OpenAI GPT-5.6 Sol",
            "DeepSeek V4 Flash text fallback",
            "DeepSeek V4 Pro text fallback",
            "Rule fallback",
            "analysis_engine.context_scope",
            "analysis_engine.context_limited",
            "current_only | relevant_history",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_backend_compatibility_labels_are_not_the_option_c_ui_allowlist(self) -> None:
        backend_contract = self._read("docs/api/backend_api_contract.md")
        schema_contract = self._read("docs/data/analysis_result_schema.md")
        frontend_flow = self._read("docs/api/frontend_backend_flow.md")

        for marker in (
            "backend-compatible labels",
            "DeepSeek V4 Flash",
            "DeepSeek V4 Pro",
            "DeepSeek",
            "Local Qwen",
            "Local Gemma",
            "Local AI model",
            "OpenAI",
        ):
            with self.subTest(scope="backend", marker=marker):
                self.assertIn(marker, backend_contract + schema_contract)

        for marker in (
            "Option C UI allowlist",
            "OpenAI GPT-5.6 Sol",
            "DeepSeek V4 Flash text fallback",
            "DeepSeek V4 Pro text fallback",
            "Rule fallback",
            "unknown-engine",
        ):
            with self.subTest(scope="frontend", marker=marker):
                self.assertIn(marker, frontend_flow)

    def test_rule_fallback_follows_all_configured_and_eligible_model_routes(self) -> None:
        for relative in (
            "docs/api/backend_api_contract.md",
            "docs/data/analysis_result_schema.md",
        ):
            text = self._read(relative)
            with self.subTest(path=relative):
                for marker in (
                    "provider disabled with no usable route",
                    "all configured and eligible model routes",
                    "eligible OpenAI failure",
                    "DeepSeek text fallback",
                    "deterministic rules last",
                ):
                    self.assertIn(marker, text)

        self.assertNotIn(
            "provider 被禁用、超时、失败或输出无效时返回完整规则结果",
            self._read("docs/data/analysis_result_schema.md"),
        )
        self.assertNotIn(
            "未启用后端模型 provider，provider 失败/超时/被跳过",
            self._read("docs/api/backend_api_contract.md"),
        )

    def test_visual_grounding_and_cross_language_limits_are_explicit(self) -> None:
        combined = self._read("docs/prompts/analyzer_prompt.md") + self._read(
            "docs/data/analysis_result_schema.md"
        ) + self._read("docs/api/backend_api_contract.md")
        for marker in (
            "matching attachment insight",
            "global fields",
            "identity",
            "protected traits",
            "precise facts",
            "commands",
            "commitments",
            "outcomes",
            "body-only fixed cross-language bridge",
            "text/hybrid",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_disclosure_and_fixed_frontend_statuses_are_documented(self) -> None:
        combined = self._read("docs/api/frontend_backend_flow.md") + self._read(
            "docs/operations/testing_checklist.md"
        )
        for marker in (
            DISCLOSURE,
            "正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。",
            "OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。",
            "远程模型结果未采用，本次使用安全规则结果。",
            "分析引擎信息未确认，请人工核查本次结果。",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_openai_key_and_routing_controls_are_backend_only(self) -> None:
        text = self._read("docs/security/api_key_rules.md")
        for marker in (
            "OPENAI_API_KEY",
            "backend only",
            "https://api.openai.com/v1",
            "no configurable OpenAI base URL",
            "OPENAI_ORG_ID",
            "OPENAI_PROJECT_ID",
            "OPENAI_CUSTOM_HEADERS",
            "OPENAI_ADMIN_KEY",
            "fail closed",
            "HTTP response",
            "SQLite",
            "frontend",
            "tests",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_bounded_smokes_do_not_close_task9_semantic_gates(self) -> None:
        combined = self._read("docs/product/roadmap.md") + self._read(
            "docs/operations/multimodal_current_email_analysis_task_brief.md"
        )
        for marker in (
            "0.2.3",
            "multimodal_current_email_offline_ready_live_pending",
            "Tasks 1-7",
            "review-clean",
            *TASK9_REPAIR_MARKERS,
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

        module = load_script_module(
            ROOT / "scripts" / "generate_project_status.py",
            "generate_project_status_multimodal_docs",
        )
        report = module.build_project_status()
        self.assertIn(
            "| Current stage | multimodal_current_email_offline_ready_live_pending |",
            report,
        )
        self.assertIn("Tasks 1-7", report)
        for marker in TASK9_REPAIR_MARKERS:
            with self.subTest(marker=marker):
                self.assertIn(marker, " ".join(report.split()))
        self.assertNotIn("remaining Task 9 gate is final master integration", report)
        for stale_claim in STALE_ATTACHMENT_SMOKE_CLAIMS:
            with self.subTest(stale_claim=stale_claim):
                self.assertNotIn(stale_claim, report)
        self.assertNotIn("current-clicked Tencent smoke remains pending", report)

    def test_root_readme_tracks_the_current_multimodal_release(self) -> None:
        readme = self._read("README.md")
        manifest = json.loads(self._read("frontend/browser_extension/manifest.json"))
        env_values = {}
        for line in self._read(".env.example").splitlines():
            if line and not line.startswith("#") and "=" in line:
                name, value = line.split("=", 1)
                env_values[name] = value

        version = manifest["version"]
        self.assertEqual(version, "0.2.3")
        self.assertIn(f"Current unpacked extension version: `{version}`.", readme)
        for name, expected in (
            ("EMAIL_AGENT_LLM_PROVIDER", "disabled"),
            ("EMAIL_AGENT_OPENAI_MODEL", "gpt-5.6-sol"),
            ("EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS", "35"),
            ("EMAIL_AGENT_TEXT_FALLBACK_PROVIDER", "disabled"),
            ("EMAIL_AGENT_DEEPSEEK_MODEL", "deepseek-v4-flash"),
            ("EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS", "10"),
            ("EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE", "conservative"),
        ):
            with self.subTest(configuration=name):
                self.assertEqual(env_values[name], expected)
                self.assertIn(f"| `{name}` | `{expected}` |", readme)

        for marker in (
            DISCLOSURE,
            "all providers disabled by default",
            "Task 9 synthetic provider and current-clicked Tencent smokes are complete",
            "Task 9 semantic accuracy repair is offline complete",
            "parsed attachment status does not prove semantic correctness",
            "fresh explicit authorization",
            "用户点击按钮后分析当前打开的一封邮件。",
            "不自动扫描邮箱或批量分析所有邮件。",
            "符合条件时先尝试一次 DeepSeek 文本回退",
            "该回退被禁用、不合格、预算不足、失败或不安全时才返回规则结果",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, readme)
        self.assertNotIn("`0.2.2`", readme)
        self.assertNotIn("has **not** been run by this project task", readme)
        for stale_claim in STALE_ATTACHMENT_SMOKE_CLAIMS:
            with self.subTest(stale_claim=stale_claim):
                self.assertNotIn(stale_claim, readme)

    def test_all_attachment_status_surfaces_use_the_current_live_boundary(self) -> None:
        for relative in ATTACHMENT_STATUS_SURFACES:
            text = self._read(relative)
            with self.subTest(path=relative, marker="old pending status"):
                self.assertNotIn("current-clicked Tencent smoke remains pending", text)
            for marker in TASK9_REPAIR_MARKERS:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, " ".join(text.split()))
            self.assertNotIn("remaining Task 9 gate is final master integration", text)
            for stale_claim in STALE_ATTACHMENT_SMOKE_CLAIMS:
                with self.subTest(path=relative, stale_claim=stale_claim):
                    self.assertNotIn(stale_claim, text)

    def test_prior_task9_docs_distinguish_completed_smokes_from_new_task5(self) -> None:
        obsolete_markers = (
            "current-clicked Tencent smoke remains pending",
            "current-clicked Tencent validation remains pending",
        )
        current_markers = TASK9_REPAIR_MARKERS
        for relative, approved_date in PRIOR_TASK9_STATUS_DOCS.items():
            text = self._read(relative)
            normalized_text = " ".join(text.split())
            with self.subTest(path=relative, marker="approved date"):
                self.assertIn(f"\nlast_update: {approved_date}\n", text[:300])
            for marker in obsolete_markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertNotIn(marker, normalized_text)
            for marker in current_markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, normalized_text)

    def test_status_generator_tracks_task_2_through_7_handoff_files(self) -> None:
        source = self._read("scripts/generate_project_status.py")
        for path in (
            "frontend/browser_extension/content/exmail_visible_context.js",
            "frontend/browser_extension/content/exmail_visible_resource_classifier.js",
            "backend/email_agent/multimodal_media.py",
            "backend/email_agent/openai_multimodal_client.py",
            "backend/email_agent/analysis_model_routes.py",
            "backend/email_agent/model_grounding.py",
            "backend/email_agent/model_visual_grounding.py",
            "tests/test_openai_multimodal_client.py",
            "tests/test_analysis_model_routes.py",
        ):
            with self.subTest(path=path):
                self.assertIn(path, source)

    def test_touched_document_front_matter_uses_approved_date(self) -> None:
        for relative in ACTIVE_DOCS:
            text = self._read(relative)
            expected_date = (
                "2026-07-23"
                if relative == "docs/operations/testing_checklist.md"
                else "2026-07-22"
                if relative in (
                    BOUNDED_HANDOFF_TOUCHED_ACTIVE_DOCS
                    | GOVERNED_CORPUS_TOUCHED_ACTIVE_DOCS
                )
                else "2026-07-21"
                if relative
                == "docs/operations/multimodal_current_email_analysis_task_brief.md"
                else "2026-07-20"
                if relative in AUTOMATIC_ATTACHMENT_SMOKE_TOUCHED_DOCS
                else "2026-07-18"
                if relative in ATTACHMENT_TOUCHED_ACTIVE_DOCS
                else "2026-07-17"
                if relative in OPENAI_TOUCHED_ACTIVE_DOCS
                else "2026-07-16"
            )
            with self.subTest(path=relative):
                self.assertTrue(text.startswith("---\n"))
                self.assertIn(f"\nlast_update: {expected_date}\n", text[:300])

    def test_labeled_moq_grounding_release_contract_is_documented(self) -> None:
        brief = self._read(
            "docs/operations/current_email_grounding_and_attachment_repair_task_brief.md"
        )
        checklist = self._read("docs/operations/testing_checklist.md")

        release_markers = (
            "Accepted label: `MOQ`",
            "Accepted label: `minimum order qty`",
            "Accepted label: `minimum order quantity`",
            "Accepted label: `最低起订量`",
            "Accepted label: `最低订购量`",
            "Local unknown-unit rejection.",
            "Conflicting public field fallback.",
            "Unrelated grounded fields remain eligible.",
        )

        for marker in release_markers:
            with self.subTest(scope="brief-release-marker", marker=marker):
                self.assertIn(marker, brief)
            with self.subTest(scope="checklist-release-marker", marker=marker):
                self.assertIn(marker, checklist)

        for marker in (
            "Finite accepted labels",
            "one-to-four alternatives",
            "closed canonical unit set",
            "parser-owned source spans",
            "indivisible alternative set",
            "Local exact-fact authority",
        ):
            with self.subTest(scope="brief", marker=marker):
                self.assertIn(marker, brief)

        self.assertIn("final MOQ answer closes the quantity request only", brief)

        for marker in (
            "one-to-four alternatives",
            "closed canonical unit set",
            "parser-owned source spans",
            "cannot split or omit one member",
            "unknown-unit",
            "local extraction remains the authority",
            "final labeled MOQ closes only the quantity request",
            "provider claim that a locally known MOQ remains pending falls back only for the conflicting public field",
        ):
            with self.subTest(scope="checklist", marker=marker):
                self.assertIn(marker, checklist)

    def test_current_message_attachment_acquisition_release_contract_is_documented(self) -> None:
        documents = {
            "AGENTS.md": (
                "verified legacy current-message control",
                "explicit Analyze click",
                "browser memory only",
                "5 files, 10 MiB per file, and 25 MiB total",
            ),
            "docs/decisions/0007-multimodal-current-email-analysis.md": (
                "picker selection is inert until Analyze",
                "request `finally`",
                "24-hour mtime cleanup is crash recovery only",
            ),
            "docs/security/email_data_handling.md": (
                "No `chrome.downloads`, `showOpenFilePicker`, File System Access",
                "no `localStorage`, `sessionStorage`, `IndexedDB`, or `chrome.storage`",
                "not normal retention and is not scheduled",
            ),
            "docs/api/frontend_backend_flow.md": (
                "selected files are not read on picker selection",
                "read only inside the Analyze click lifecycle",
                "only `attachment_insights[].status == \"parsed\"` proves content parsing",
            ),
            "docs/api/backend_api_contract.md": (
                "5 files, 10 MiB per file, and 25 MiB total",
                "local path fields are forbidden",
                "request `finally`",
            ),
            "docs/operations/testing_checklist.md": (
                "Attachment Task 5 remains valid acquisition/cleanup evidence only",
                "parsed attachment status does not prove semantic correctness",
                "Any new live operation still requires fresh explicit authorization",
                "24-hour mtime cleanup is crash recovery only",
            ),
            "docs/operations/current_email_grounding_and_attachment_repair_task_brief.md": (
                "Automatic legacy control acquisition is current-message-only",
                "picker selection does not read bytes",
                "Only `attachment_insights[].status == \"parsed\"` proves content parsing",
            ),
        }
        for relative, markers in documents.items():
            text = self._read(relative)
            for marker in markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
