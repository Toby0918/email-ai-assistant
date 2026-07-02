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
