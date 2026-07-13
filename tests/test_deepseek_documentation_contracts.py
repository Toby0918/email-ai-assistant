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

    def test_api_contract_records_deadlines_persistence_and_no_chain(self) -> None:
        contract = self._read("docs/api/backend_api_contract.md")
        for marker in (
            "https://api.deepseek.com",
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "openai==2.45.0",
            "32-second cooperative",
            "8-second",
            "25-second",
            "5-second",
            "2-second",
            "0.5-second cumulative",
            "0.25-second response floor",
            "PERSISTENCE_FAILED",
            "rollback failure",
            "quarantined",
            "35-second POST wait",
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
        self.assertTrue(adr.startswith("---\nlast_update: 2026-07-13\nstatus: active\n"))
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


if __name__ == "__main__":
    unittest.main()
