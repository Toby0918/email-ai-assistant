"""Static tests for the Tencent Exmail browser extension prototype."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"


class BrowserExtensionStaticTests(unittest.TestCase):
    def test_tencent_exmail_route_decision_is_documented(self) -> None:
        adr = (ROOT / "docs" / "decisions" / "adr_0002_frontend_route.md").read_text(encoding="utf-8")
        roadmap = (ROOT / "docs" / "product" / "roadmap.md").read_text(encoding="utf-8")
        scope = (ROOT / "docs" / "product" / "feature_scope.md").read_text(encoding="utf-8")

        self.assertIn("Tencent Exmail", adr)
        self.assertIn("Chrome / Edge browser extension", adr)
        self.assertIn("exmail.qq.com", adr)
        self.assertIn("current opened Tencent Exmail message", adr)
        self.assertIn("user-selected email content", adr)
        self.assertIn("not arbitrary webpage analysis", adr)
        self.assertIn("after the explicit analyze click", adr)
        self.assertIn("Tencent Exmail", roadmap)
        self.assertIn("Tencent Exmail", scope)

    def test_active_docs_keep_selected_text_fallback_email_scoped(self) -> None:
        docs = [
            ROOT / "docs" / "decisions" / "adr_0002_frontend_route.md",
            ROOT / "docs" / "superpowers" / "specs" / "2026-07-02-tencent-exmail-browser-extension-design.md",
            ROOT / "docs" / "superpowers" / "plans" / "2026-07-02-tencent-exmail-browser-extension.md",
        ]
        required = [
            "user-selected email content",
            "currently opened Tencent Exmail message",
            "not arbitrary webpage analysis",
            "not background page scraping",
            "Open a Tencent Exmail message or select email body text from that opened message first",
        ]
        forbidden = [
            "selected page text",
            "selected text on any web page",
            "fallback when no opened email is detected",
            "No opened email or selected text found",
            "Open one email or select visible email body content first",
        ]

        for path in docs:
            text = path.read_text(encoding="utf-8")
            for marker in required:
                with self.subTest(path=path.name, marker=marker):
                    self.assertIn(marker, text)
            for marker in forbidden:
                with self.subTest(path=path.name, marker=marker):
                    self.assertNotIn(marker, text)

    def test_implementation_plan_uses_narrow_fallback_wording(self) -> None:
        plan = (
            ROOT
            / "docs"
            / "superpowers"
            / "plans"
            / "2026-07-02-tencent-exmail-browser-extension.md"
        ).read_text(encoding="utf-8")

        self.assertNotIn("当前打开邮件或用户选中的文本", plan)
        self.assertNotIn("Open one email or select email text first", plan)
        self.assertIn(
            "Open a Tencent Exmail message or select email body text from that opened message first",
            plan,
        )

    def test_exmail_superpowers_docs_use_allowed_source_type(self) -> None:
        docs = [
            ROOT / "docs" / "superpowers" / "specs" / "2026-07-02-tencent-exmail-browser-extension-design.md",
            ROOT / "docs" / "superpowers" / "plans" / "2026-07-02-tencent-exmail-browser-extension.md",
        ]

        for path in docs:
            text = path.read_text(encoding="utf-8")
            front_matter = text.split("---", 2)[1]
            with self.subTest(path=path.name):
                self.assertIn("source_type: operation_guide", front_matter)
                self.assertNotIn("source_type: design_spec", front_matter)
                self.assertNotIn("source_type: implementation_plan", front_matter)

    def test_browser_extension_files_exist(self) -> None:
        expected = [
            "manifest.json",
            "popup.html",
            "popup.css",
            "popup.js",
            "content/exmail_adapter.js",
            "shared/api_client.js",
            "shared/render_analysis.js",
        ]

        for relative in expected:
            with self.subTest(relative=relative):
                self.assertTrue((EXTENSION / relative).exists())

    def test_api_client_calls_only_local_backend(self) -> None:
        script = (EXTENSION / "shared" / "api_client.js").read_text(encoding="utf-8")

        self.assertIn("http://127.0.0.1:8765/api/analyze-current-email", script)
        self.assertIn("fetch(", script)
        self.assertIn('"Content-Type": "application/json"', script)
        self.assertIn("user_confirmed: true", script)
        self.assertNotIn("api.openai.com", script)
        self.assertNotIn("OPENAI_API_KEY", script)
        self.assertNotIn("process.env", script)

    def test_renderer_displays_existing_analysis_schema(self) -> None:
        script = (EXTENSION / "shared" / "render_analysis.js").read_text(encoding="utf-8")

        self.assertIn("renderAnalysis", script)
        self.assertIn("clearAnalysis", script)
        self.assertIn("analysis.priority", script)
        self.assertIn("analysis.summary", script)
        self.assertIn("analysis.category", script)
        self.assertIn("analysis.risk_flags", script)
        self.assertIn("analysis.suggested_actions", script)
        self.assertIn("analysis.reply_draft.body", script)

    def test_exmail_adapter_extracts_only_after_popup_message(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("chrome.runtime.onMessage.addListener", script)
        self.assertIn('MESSAGE_TYPE = "EXTRACT_CURRENT_EMAIL"', script)
        self.assertIn("sendResponse(extractCurrentEmail())", script)
        self.assertNotIn("setInterval(", script)
        self.assertNotIn("MutationObserver", script)

    def test_exmail_adapter_scopes_selected_text_to_message_context(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertIn("hasMessageContext", script)
        self.assertIn("getSelectedEmailContent", script)
        self.assertIn("selectionBelongsToMessage", script)
        self.assertIn("findBodyElement", script)
        self.assertIn("view.getSelection", script)
        self.assertIn("selected_text", script)
        self.assertIn(
            "Open a Tencent Exmail message or select email body text from that opened message first",
            script,
        )
        self.assertIn("not arbitrary webpage analysis", script)
        self.assertNotIn("selected page text", script)
        self.assertNotIn("selected text on any web page", script)
        self.assertNotIn("[role='main']", script)

    def test_exmail_adapter_does_not_log_email_body(self) -> None:
        script = (EXTENSION / "content" / "exmail_adapter.js").read_text(encoding="utf-8")

        self.assertNotIn("console.log", script)

    def test_popup_requests_current_email_after_user_click(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector("#analyze-button").addEventListener("click"', script)
        self.assertIn("chrome.tabs.query", script)
        self.assertIn("chrome.tabs.sendMessage", script)
        self.assertIn("EXTRACT_CURRENT_EMAIL", script)
        self.assertIn("EmailAssistantApi.analyzeCurrentEmail", script)
        self.assertIn("EmailAssistantRender.renderAnalysis", script)

    def test_popup_handles_copy_draft(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn('document.querySelector("#copy-draft-button").addEventListener("click"', script)
        self.assertIn("navigator.clipboard.writeText", script)
        self.assertIn("No draft to copy", script)
        self.assertIn("Copy failed", script)

    def test_popup_has_user_facing_error_states(self) -> None:
        script = (EXTENSION / "popup.js").read_text(encoding="utf-8")

        self.assertIn("Open a Tencent Exmail tab first", script)
        self.assertIn("Open a Tencent Exmail message or select email body text from that opened message first", script)
        self.assertIn("Local analysis service unavailable", script)
        self.assertIn("Analysis failed", script)

    def test_browser_extension_has_no_secret_or_openai_markers(self) -> None:
        forbidden = [
            "OPENAI_API_KEY",
            "api.openai.com",
            "/v1/responses",
            "/v1/chat/completions",
            "new OpenAI",
            "process.env",
            ".env",
            "sk-",
        ]

        for path in EXTENSION.rglob("*"):
            if path.is_dir() or path.suffix not in {".js", ".html", ".json", ".css"}:
                continue
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.relative_to(ROOT), marker=marker):
                    self.assertNotIn(marker, text)

    def test_browser_extension_has_no_high_risk_mailbox_actions(self) -> None:
        forbidden = [
            "sendMail",
            "gmail.users.messages.send",
            "archiveMessage",
            "deleteMessage",
            "trashMessage",
            "messages.trash",
        ]

        for path in EXTENSION.rglob("*.js"):
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                with self.subTest(path=path.relative_to(ROOT), marker=marker):
                    self.assertNotIn(marker, text)

    def test_tencent_exmail_task_brief_exists(self) -> None:
        brief = ROOT / "docs" / "operations" / "tencent_exmail_browser_extension_task_brief.md"

        self.assertTrue(brief.exists())
        text = brief.read_text(encoding="utf-8")
        self.assertIn("Tencent Exmail", text)
        self.assertIn("https://exmail.qq.com/*", text)
        self.assertIn("No automatic send", text)
        self.assertIn("No mailbox account integration", text)


if __name__ == "__main__":
    unittest.main()
