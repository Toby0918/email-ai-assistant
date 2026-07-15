"""Synchronized DeepSeek documentation contract tests."""

from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ALLOWED_DEEPSEEK_SOURCES = {
    "https://api.deepseek.com",
    "https://api-docs.deepseek.com/quick_start/pricing/",
    "https://api-docs.deepseek.com/api/create-chat-completion",
    "https://api-docs.deepseek.com/guides/thinking_mode",
    "https://api-docs.deepseek.com/guides/kv_cache/",
    "https://cdn.deepseek.com/policies/en-US/deepseek-privacy-policy.html",
}
TARGET_DOCS = (
    "docs/prompts/analyzer_prompt.md",
    "docs/data/analysis_result_schema.md",
    "docs/api/backend_api_contract.md",
    "docs/security/email_data_handling.md",
    "docs/decisions/0005-deepseek-led-analysis.md",
    "docs/operations/deepseek_api_analysis_task_brief.md",
    "docs/superpowers/specs/2026-07-12-deepseek-led-email-analysis-design.md",
)
BUDGET_ORDER_DOCS = (
    "docs/api/backend_api_contract.md",
    "docs/decisions/0005-deepseek-led-analysis.md",
    "docs/operations/deepseek_api_analysis_task_brief.md",
    "docs/superpowers/specs/2026-07-12-deepseek-led-email-analysis-design.md",
)
FALLBACK_DIAGNOSTIC_CONTRACTS = {
    "docs/conventions/logging.md": (
        "analysis_fallback",
        "provider_auth",
        "provider_permission_or_balance",
        "provider_timeout",
        "envelope_invalid",
        "evidence_invalid",
        "provider_output_placeholder_echo",
        "safety_rejected_all",
        "local_debug_service.log",
        "public API",
        "raw exception",
        "Rule fallback remains a successful public analysis response.",
        "exactly one terminal allowlisted event",
        "1 MB",
        "two backups",
        "SQLite",
        "frontend",
        "Automated verification does not call DeepSeek.",
        "Logs must not contain API keys, prompts, email or thread content, "
        "attachment names or content, provider output, raw exception text, "
        "tracebacks, URLs, paths, or customer identifiers.",
        "dedicated diagnostic sink", "never attached to the root logger", "`propagate=False`", "fixed `WARNING` threshold", "exact fallback-event template", "exact built-in allowlisted arguments", "OpenAI, HTTPX, HTTP core", "DEBUG, INFO, WARNING, ERROR, CRITICAL, or an invalid level",
    ),
    "docs/operations/troubleshooting.md": (
        "analysis_fallback",
        "provider_auth",
        "provider_permission_or_balance",
        "provider_timeout",
        "envelope_invalid",
        "evidence_invalid",
        "provider_output_placeholder_echo",
        "safety_rejected_all",
        "local_debug_service.log",
        "public API",
        "SQLite",
        "frontend",
        "恰好一条终态 allowlisted `event=analysis_fallback`",
        "Get-Content outputs\\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'",
        "专用 diagnostic sink", "不挂到 root logger", "`propagate=False`", "固定 `WARNING` 门槛", "OpenAI、HTTPX、HTTP core", "DEBUG、INFO、WARNING、ERROR、CRITICAL 或无效 level",
    ),
    "docs/operations/deployment_notes.md": (
        "analysis_fallback",
        "provider_output_placeholder_echo",
        "local_debug_service.log",
        "public API",
        "raw exception",
        "exactly one terminal allowlisted event",
        "1 MB",
        "two backups",
        "SQLite",
        "frontend",
        "Automated verification does not call DeepSeek.",
        "Get-Content outputs\\local_debug_service.log -Tail 30 | Select-String 'event=analysis_'",
    ),
    "docs/api/backend_api_contract.md": (
        "analysis_fallback",
        "provider_auth",
        "provider_permission_or_balance",
        "provider_timeout",
        "envelope_invalid",
        "evidence_invalid",
        "provider_output_placeholder_echo",
        "safety_rejected_all",
        "public API",
        "raw exception",
        "Rule fallback remains a successful public analysis response.",
        "exactly one terminal allowlisted event",
        "SQLite",
        "frontend",
    ),
    "docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md": ("dedicated diagnostic sink", "never attached to the root logger", "`propagate=False`", "fixed `WARNING` threshold", "exact fallback-event template", "exact built-in allowlisted arguments", "DEBUG, INFO, WARNING, ERROR, CRITICAL, or an invalid level"),
    "docs/superpowers/plans/2026-07-13-deepseek-fallback-diagnostics.md": ("dedicated diagnostic sink", "never attached to the root logger", "`propagate=False`", "fixed `WARNING` threshold", "exact fallback-event template", "exact built-in allowlisted arguments", "PRIVATE_OPENAI_BODY", "DEBUG, INFO, WARNING, ERROR, CRITICAL, and an invalid level", "or record.exc_info is not None", "or record.exc_text is not None", "or record.stack_info is not None"),
}
ENVELOPE_SUBDIAGNOSTIC_DOCS = (
    "docs/conventions/logging.md",
    "docs/operations/troubleshooting.md",
    "docs/operations/deployment_notes.md",
    "docs/api/backend_api_contract.md",
    "docs/operations/deepseek_envelope_subdiagnostics_task_brief.md",
    "docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md",
    "docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md",
)
ENGLISH_ENVELOPE_SUBDIAGNOSTIC_DOCS = (
    "docs/operations/deepseek_envelope_subdiagnostics_task_brief.md",
    "docs/superpowers/specs/2026-07-13-deepseek-envelope-subdiagnostics-design.md",
    "docs/superpowers/plans/2026-07-14-deepseek-envelope-subdiagnostics.md",
)


class DeepSeekDocumentationContractTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_prompt_and_schema_separate_private_envelope_from_public_result(self) -> None:
        prompt = self._read("docs/prompts/analyzer_prompt.md")
        schema = self._read("docs/data/analysis_result_schema.md")
        for marker in (
            "deepseek_analysis_v1",
            "field_evidence",
            "extra_body",
            '"type": "json_object"',
            "one provider call",
            "field-level fallback",
            "universal provider-text safety",
            "passive consequential commitment",
        ):
            self.assertIn(marker, prompt)
        for marker in (
            "unchanged public analysis schema",
            "deepseek_analysis_v1",
            "never returned",
            "DeepSeek V4 Flash",
            "rule_fallback",
            "production provider path",
            "actual `analysis_engine.source`",
        ):
            self.assertIn(marker, schema)

    def test_placeholder_echo_and_local_exact_fact_authority_are_documented(self) -> None:
        required_markers = {
            "docs/prompts/analyzer_prompt.md": (
                "must never emit deidentification placeholder tokens",
                "generic references for exact identifiers and dates",
                "backend-verified exact facts remain authoritative",
                "model-authored exact identifiers and dates fall back to backend rule fields",
                "internal deidentification tokens stay local",
                "post-conversion residual scan",
                "unknown token fails closed",
            ),
            "docs/api/backend_api_contract.md": (
                "must never emit deidentification placeholder tokens",
                "generic references for exact identifiers and dates",
                "backend-verified exact facts remain authoritative",
                "model-authored exact identifiers and dates fall back to backend rule fields",
                "internal deidentification tokens stay local",
                "post-conversion residual scan",
                "unknown token fails closed",
            ),
            "docs/security/email_data_handling.md": (
                "must never emit deidentification placeholder tokens",
                "generic references for exact identifiers and dates",
                "backend-verified exact facts remain authoritative",
                "model-authored exact identifiers and dates fall back to backend rule fields",
                "internal deidentification tokens stay local",
                "post-conversion residual scan",
                "unknown token fails closed",
            ),
            "docs/security/privacy_rules.md": (
                "must never emit deidentification placeholder tokens",
                "generic references for exact identifiers and dates",
                "backend-verified exact facts remain authoritative",
                "model-authored exact identifiers and dates fall back to backend rule fields",
                "internal deidentification tokens stay local",
                "post-conversion residual scan",
                "unknown token fails closed",
            ),
        }
        for relative, markers in required_markers.items():
            text = self._read(relative)
            for marker in markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, text)

    def test_api_contract_records_deadlines_persistence_and_no_chain(self) -> None:
        contract = self._read("docs/api/backend_api_contract.md")
        for marker in (
            "https://api.deepseek.com",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "openai==2.45.0",
            "13-second cooperative",
            "8-second",
            "10-second",
            "5-second",
            "2-second",
            "0.5-second cumulative",
            "0.25-second response floor",
            "PERSISTENCE_FAILED",
            "rollback failure",
            "quarantined",
            "15-second POST wait",
            "20-second resource collection",
            "does not try Ollama",
            "absolute wall-clock deadline",
            "late-start quarantine",
            "commit, rollback, and close",
            "poisoned/detached",
        ):
            self.assertIn(marker, contract)

    def test_analysis_budget_starts_before_request_body_read(self) -> None:
        false_order_phrases = (
            "after the validated request body is read",
            "after the validated request body read",
            "after request-body read",
            "完成已校验的 request body 读取后调用",
        )
        for relative in BUDGET_ORDER_DOCS:
            text = self._read(relative)
            with self.subTest(path=relative):
                self.assertIn("`start -> read -> api`", text)
                for phrase in false_order_phrases:
                    self.assertNotIn(phrase, text.casefold())

    def test_security_contract_discloses_remote_processing_without_retention_guarantee(self) -> None:
        policy = self._read("docs/security/email_data_handling.md")
        for marker in (
            "persistent pre-click disclosure",
            "After you click Analyze, a configured remote AI provider receives locally deidentified current visible content and, when available, bounded approved knowledge cards. Processing is not local-only, and no zero-retention guarantee is made.",
            "current visible thread",
            "ephemeral sanitized attachment context",
            "excluded from API responses, SQLite, and logs",
            "enabled by default",
            "best-effort",
            "few hours to a few days",
            "Prompts or Inputs",
            "People's Republic of China",
            "no zero-retention guarantee",
            "copula or whitespace-only separators",
            "canonical complete analyzed scope",
            "production-route offline replay",
        ):
            self.assertIn(marker, policy)

    def test_adr_and_review_records_close_the_final_review_fix_wave(self) -> None:
        adr = self._read("docs/decisions/0005-deepseek-led-analysis.md")
        self.assertTrue(adr.startswith("---\nlast_update: 2026-07-14\nstatus: active\n"))
        for marker in (
            "https://api.deepseek.com",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "openai==2.45.0",
            "EMAIL_AGENT_LLM_PROVIDER=disabled",
            "EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative",
            "EMAIL_AGENT_LLM_PROVIDER=deepseek",
            "EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=model_led",
            "PERSISTENCE_FAILED",
            "production-route offline replay",
        ):
            self.assertIn(marker, adr)

        brief = self._read("docs/operations/deepseek_api_analysis_task_brief.md")
        design = self._read(
            "docs/superpowers/specs/2026-07-12-deepseek-led-email-analysis-design.md"
        )
        self.assertRegex(brief, r"(?s)## 3\. Current Status\s+```text\s+active\s+```")
        self.assertIn("Written design review: complete", brief)
        self.assertIn("Final review fix wave: complete", brief)
        self.assertIn("Written review: complete", design)
        self.assertIn("Final review fix wave: complete", design)

    def test_dynamic_provider_claims_use_only_rechecked_official_sources(self) -> None:
        for relative in TARGET_DOCS:
            text = self._read(relative)
            urls = {
                match.rstrip(".,;")
                for match in re.findall(r'https://[^\s`)>"\]]+', text)
                if "deepseek.com" in match
            }
            with self.subTest(path=relative):
                self.assertTrue(urls.issubset(ALLOWED_DEEPSEEK_SOURCES), urls)

    def test_active_provider_constraints_include_backend_only_deepseek(self) -> None:
        expected_markers = {
            "AGENTS.md": (
                "AI 调用可以是后端 DeepSeek 专用 provider",
                "不允许直接调用 DeepSeek API",
                "OpenAI/DeepSeek API key",
                "EMAIL_AGENT_LLM_PROVIDER=disabled",
                "EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative",
                "persistent pre-click disclosure",
            ),
            "docs/constraints/architecture_constraints.md": (
                "后端 DeepSeek 专用 provider",
                "frontend -> DeepSeek",
                "前端禁止直接调用 DeepSeek API",
                "允许的 provider 是规则兜底、DeepSeek 专用 provider",
                "DeepSeek API key",
            ),
            "docs/constraints/linter_constraints.md": (
                "前端禁止云端/本地模型 provider 直接调用",
                "DEEPSEEK_API_KEY",
                "api.deepseek.com",
                "DeepSeek SDK",
                "DeepSeek API key",
            ),
            "docs/security/api_key_rules.md": (
                "DeepSeek API key 只能存放在 Python 后端",
                "DEEPSEEK_API_KEY",
                "api.deepseek.com",
                "固定后端端点",
                "前端不得直接调用 DeepSeek API",
            ),
            "docs/security/privacy_rules.md": (
                "DeepSeek 外部处理",
                "persistent pre-click disclosure",
                "no zero-retention guarantee",
                "email_data_handling.md",
            ),
        }
        for relative, markers in expected_markers.items():
            text = self._read(relative)
            for marker in markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, text)

    def test_fallback_diagnostic_operations_contract_is_explicit(self) -> None:
        for relative, markers in FALLBACK_DIAGNOSTIC_CONTRACTS.items():
            text = self._read(relative)
            for marker in markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, text)

        troubleshooting = self._read("docs/operations/troubleshooting.md")
        for weakened in (
            "最多产生一个终态",
            "最多一条终态",
            "at most one terminal",
        ):
            with self.subTest(path="docs/operations/troubleshooting.md", weakened=weakened):
                self.assertNotIn(weakened, troubleshooting)

        plan = self._read("docs/superpowers/plans/2026-07-13-deepseek-fallback-diagnostics.md")
        for insecure_recipe in ("logging.getLogger('synthetic').warning", "logging.basicConfig(", "handlers=handlers"):
            self.assertNotIn(insecure_recipe, plan)

    def test_envelope_subdiagnostic_contract_is_explicit(self) -> None:
        markers = (
            "detail=",
            "not_applicable",
            "json_syntax",
            "top_level_shape",
            "schema_version",
            "analysis_shape",
            "attachment_shape",
            "field_evidence_shape",
            "provider output",
            "JSON keys",
            "paths",
            "values",
        )
        for relative in ENVELOPE_SUBDIAGNOSTIC_DOCS:
            text = self._read(relative)
            normalized_text = " ".join(text.split())
            for marker in markers:
                with self.subTest(path=relative, marker=marker):
                    self.assertIn(marker, text)

            non_envelope_contract = (
                "Every non-envelope fallback uses not_applicable."
                if relative in ENGLISH_ENVELOPE_SUBDIAGNOSTIC_DOCS
                else "每个非 envelope fallback 都使用 `not_applicable`。"
            )
            reconstruction_contract = (
                "it must never contain or be used to reconstruct provider output, "
                "JSON keys, paths, values, or exception text."
                if relative in ENGLISH_ENVELOPE_SUBDIAGNOSTIC_DOCS
                else "不得包含 provider output、JSON keys、paths、values 或 exception text，"
                "也不得用于重建这些内容。"
            )
            with self.subTest(path=relative, contract="non-envelope fallback"):
                self.assertIn(non_envelope_contract, normalized_text)
            with self.subTest(path=relative, contract="content reconstruction"):
                self.assertIn(reconstruction_contract, normalized_text)

        canonical_event = (
            "event=analysis_fallback code=<allowlisted code> "
            "stage=<allowlisted stage> provider=<allowlisted provider> "
            "model=<allowlisted model> output_mode=<allowlisted mode> "
            "detail=<allowlisted detail> elapsed_ms=<non-negative integer>"
        )
        for relative in ENVELOPE_SUBDIAGNOSTIC_DOCS:
            with self.subTest(path=relative, contract="canonical event"):
                self.assertIn(canonical_event, self._read(relative))

        troubleshooting = self._read("docs/operations/troubleshooting.md")
        for mapping in (
            "json_syntax -> JSON decoding or duplicate-key rejection",
            "top_level_shape -> exact top-level object/key-set validation",
            "schema_version -> fixed private-envelope version validation",
            "analysis_shape -> nested analysis field/type/enum validation",
            "attachment_shape -> attachment augmentation validation",
            "field_evidence_shape -> field-evidence map/list validation",
        ):
            with self.subTest(path="docs/operations/troubleshooting.md", mapping=mapping):
                self.assertIn(mapping, troubleshooting)

        api_contract = self._read("docs/api/backend_api_contract.md")
        self.assertIn("operator-only 日志变更", api_contract)
        self.assertIn("不是 public response field", api_contract)

    def test_fallback_route_stage_mapping_is_explicit(self) -> None:
        design = self._read(
            "docs/superpowers/specs/2026-07-13-deepseek-fallback-diagnostics-design.md"
        )
        plan = self._read(
            "docs/superpowers/plans/2026-07-13-deepseek-fallback-diagnostics.md"
        )
        task_three = plan.split("### Task 3:", 1)[1].split("### Task 4:", 1)[0]
        markers = (
            "`response_incomplete` and `response_empty`",
            "`stage=response`",
            "every other `LlmClientError` reason",
            "`stage=provider`",
            "`parse_legacy_result` performs JSON parsing, repair, and public schema validation only",
            "`validate_conservative_language`",
            "separate route `_run_stage`",
            "`public_schema_invalid` / `schema`",
            "`public_language_invalid` / `language`",
        )
        for relative, text in (
            ("active design", design),
            ("execution plan Task 3", task_three),
        ):
            for marker in markers:
                with self.subTest(document=relative, marker=marker):
                    self.assertIn(marker, text)
        self.assertNotIn(
            'code=exc.reason_code, stage="provider"', task_three
        )


if __name__ == "__main__":
    unittest.main()
