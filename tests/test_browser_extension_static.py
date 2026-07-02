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
