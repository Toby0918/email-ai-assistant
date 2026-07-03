"""Tests for the local debug assistant window."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "local_debug_page"


class FrontendLocalDebugTests(unittest.TestCase):
    def test_local_debug_page_files_exist(self) -> None:
        # This first-version frontend is intentionally local and mailbox-free.
        self.assertTrue((FRONTEND / "index.html").exists())
        self.assertTrue((FRONTEND / "app.js").exists())
        self.assertTrue((FRONTEND / "styles.css").exists())

    def test_local_debug_page_calls_only_backend_api(self) -> None:
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn("/api/analyze-current-email", script)
        self.assertNotIn("api.openai.com", script)
        self.assertNotIn("OPENAI_API_KEY", script)

    def test_local_debug_page_submits_recipient_and_time_metadata(self) -> None:
        page = (FRONTEND / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="to"', page)
        self.assertIn('id="sent-at"', page)
        self.assertIn('id="attachments-input"', page)
        self.assertIn('id="attachments-preview"', page)
        self.assertIn("to: splitAddressList(fields.to.value)", script)
        self.assertIn("sent_at: fields.sentAt.value", script)
        self.assertIn("attachments,", script)
        self.assertIn("parseAttachmentList", script)
        self.assertIn("formatAttachments", script)

    def test_local_debug_page_can_copy_reply_draft(self) -> None:
        page = (FRONTEND / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="copy-draft-button"', page)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn("fields.draft.value", script)

    def test_local_debug_page_clears_analysis_on_failed_response(self) -> None:
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn("function clearAnalysis()", script)
        self.assertIn("clearAnalysis();\n    fields.status.textContent = data.error?.message", script)
        self.assertIn('fields.priority.textContent = "-"', script)
        self.assertIn('fields.summary.textContent = "No analysis yet"', script)
        self.assertIn('fields.attachmentsPreview.textContent = "-"', script)
        self.assertIn('fields.draft.value = ""', script)

    def test_local_debug_page_handles_backend_unavailable(self) -> None:
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn("try {", script)
        self.assertIn("catch (error)", script)
        self.assertIn("Local analysis service unavailable", script)
        self.assertIn('clearAnalysis();\n    fields.status.textContent = "Local analysis service unavailable"', script)

    def test_local_debug_page_renders_chinese_feedback_labels(self) -> None:
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn("function formatPriority", script)
        self.assertIn("function formatCategory", script)
        self.assertIn("function formatRisk", script)
        self.assertIn("new_product_development", script)
        self.assertIn('payment: "付款/发票"', script)
        self.assertIn('payment_risk: "付款风险"', script)
        self.assertIn('check_inventory: "核查库存"', script)

    def test_local_debug_page_displays_backend_analysis_engine(self) -> None:
        page = (FRONTEND / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="engine"', page)
        self.assertIn("analysis.analysis_engine", script)
        self.assertIn("fields.engine.textContent", script)

    def test_readme_documents_local_debug_start_command(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("python scripts/run_local_debug.py", readme)
        self.assertIn("http://127.0.0.1:8765", readme)

    def test_readme_has_readable_github_project_overview(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("企业邮箱 AI 辅助窗口", readme)
        self.assertIn("第一阶段边界", readme)
        self.assertIn("不自动发送、删除或归档邮件", readme)
        self.assertNotIn("浼佷笟", readme)
        self.assertNotIn("鈥", readme)
        self.assertNotIn("涓嶃", readme)


if __name__ == "__main__":
    unittest.main()
