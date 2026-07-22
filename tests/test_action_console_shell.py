"""Public UI contracts for the issue #23 Action Console shell."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
EXTENSION_PAGE = ROOT / "frontend" / "browser_extension" / "popup.html"
LOCAL_DEBUG_PAGE = ROOT / "frontend" / "local_debug_page" / "index.html"
EXTENSION_CSS = ROOT / "frontend" / "browser_extension" / "popup.css"
LOCAL_DEBUG_CSS = ROOT / "frontend" / "local_debug_page" / "styles.css"
COMPONENT_CSS = (
    ROOT / "frontend" / "browser_extension" / "shared" / "analysis_components.css"
)


def _rule_body(css: str, selector: str) -> str:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>[^}}]*)\}}", css)
    return "" if match is None else match.group("body")


class ActionConsoleShellTests(unittest.TestCase):
    def test_both_surfaces_expose_one_named_action_console_flow(self) -> None:
        for path in (EXTENSION_PAGE, LOCAL_DEBUG_PAGE):
            with self.subTest(path=path.relative_to(ROOT)):
                soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
                consoles = soup.select(".action-console")

                self.assertEqual(len(consoles), 1)
                console = consoles[0]
                title_id = console.get("aria-labelledby")
                self.assertIsInstance(title_id, str)
                title = soup.find(id=title_id)
                self.assertIsNotNone(title)
                self.assertIn(title.name, ("h1", "h2"))
                self.assertEqual(title.get_text(" ", strip=True), "Email AI Assistant")

                notice = console.select_one("#remote-processing-notice")
                analyze = console.select_one("#analyze-button")
                status = console.select_one("#status")
                result = console.select_one(".analysis-surface")
                copy_draft = console.select_one("#copy-draft-button")
                self.assertTrue(all((notice, analyze, status, result, copy_draft)))

                descendants = list(console.descendants)
                positions = [
                    descendants.index(element)
                    for element in (notice, analyze, status, result, copy_draft)
                ]
                self.assertEqual(positions, sorted(positions))
                self.assertEqual(notice.get("role"), "note")
                self.assertEqual(analyze.get("type"), "button")
                self.assertEqual(status.get("aria-live"), "polite")

    def test_scroll_ownership_matches_each_formal_surface(self) -> None:
        component_css = COMPONENT_CSS.read_text(encoding="utf-8")
        popup_css = EXTENSION_CSS.read_text(encoding="utf-8")
        debug_css = LOCAL_DEBUG_CSS.read_text(encoding="utf-8")

        console_rule = _rule_body(component_css, ".action-console")
        self.assertIn("min-width: 0", console_rule)
        self.assertIn("overflow-wrap: anywhere", console_rule)
        self.assertIn("min-height: 44px", _rule_body(component_css, "input"))

        self.assertNotRegex(popup_css, r"overflow-y\s*:\s*(?:auto|scroll|hidden)")
        self.assertNotRegex(_rule_body(popup_css, ".popup-shell"), r"max-height\s*:")
        self.assertNotIn("overflow: hidden", debug_css)

        compose_rule = _rule_body(debug_css, ".compose-panel")
        self.assertNotRegex(compose_rule, r"max-height\s*:")
        self.assertNotRegex(compose_rule, r"overflow-y\s*:")

        result_rule = _rule_body(debug_css, ".result-panel")
        self.assertRegex(result_rule, r"max-height\s*:\s*calc\(100vh\s*-\s*48px\)")
        self.assertRegex(result_rule, r"overflow-y\s*:\s*auto")

        shell_rule = _rule_body(debug_css, ".shell")
        column_minimums = [
            int(value)
            for value in re.findall(r"minmax\((\d+)px\s*,", shell_rule)
        ]
        gap_match = re.search(r"gap\s*:\s*(\d+)px", shell_rule)
        padding_match = re.search(r"padding\s*:\s*(\d+)px", shell_rule)
        self.assertEqual(len(column_minimums), 2)
        self.assertIsNotNone(gap_match)
        self.assertIsNotNone(padding_match)
        minimum_wide_width = (
            sum(column_minimums)
            + int(gap_match.group(1))
            + 2 * int(padding_match.group(1))
        )
        self.assertLessEqual(minimum_wide_width, 761)

        narrow_match = re.search(
            r"@media\s*\(max-width:\s*760px\)\s*\{(?P<body>.*)\}\s*$",
            debug_css,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(narrow_match)
        narrow_result_rule = _rule_body(narrow_match.group("body"), ".result-panel")
        self.assertRegex(narrow_result_rule, r"max-height\s*:\s*none")
        self.assertRegex(narrow_result_rule, r"overflow-y\s*:\s*visible")


if __name__ == "__main__":
    unittest.main()
