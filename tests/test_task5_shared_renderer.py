"""Task 5 contracts for the shared task-card analysis renderer."""

from __future__ import annotations

import ast
import json
import shutil
import subprocess
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from backend.email_agent import server as email_server


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"
LOCAL_DEBUG = ROOT / "frontend" / "local_debug_page"
RENDERER = EXTENSION / "shared" / "render_analysis.js"
COMPONENT_CSS = EXTENSION / "shared" / "analysis_components.css"
FALLBACK_BANNER = "未使用 DeepSeek：本次结果由本地规则生成。"


def _frontend_asset_for_path(path: str):
    resolver = getattr(email_server, "_frontend_asset_for_path", None)
    return None if resolver is None else resolver(path)


class TaskFiveSharedRendererTests(unittest.TestCase):
    def test_both_surfaces_load_the_same_renderer_and_component_css(self) -> None:
        popup = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        debug = (LOCAL_DEBUG / "index.html").read_text(encoding="utf-8")
        app = (LOCAL_DEBUG / "app.js").read_text(encoding="utf-8")

        self.assertIn('href="shared/analysis_components.css"', popup)
        self.assertIn('src="shared/render_analysis.js"', popup)
        self.assertIn('href="/shared/analysis_components.css"', debug)
        self.assertIn('src="/shared/render_analysis.js"', debug)
        self.assertLess(debug.index('/shared/render_analysis.js'), debug.index('/app.js'))
        self.assertIn("EmailAssistantRender.renderAnalysis", app)
        self.assertNotIn("function renderAnalysis(", app)
        self.assertNotIn("const PRIORITY_LABELS", app)

    def test_task_card_precedes_closed_native_details_on_both_surfaces(self) -> None:
        for path in (EXTENSION / "popup.html", LOCAL_DEBUG / "index.html"):
            with self.subTest(path=path.name):
                page = path.read_text(encoding="utf-8")
                markers = [
                    'id="work-conclusion"',
                    'id="work-current-request"',
                    'id="work-next-steps"',
                    'id="work-key-facts"',
                    'id="work-must-check"',
                ]
                missing = [marker for marker in markers if marker not in page]
                if missing:
                    self.fail(f"missing task-card markers: {missing}")
                positions = [
                    page.index(marker) for marker in markers
                ]
                self.assertEqual(positions, sorted(positions))
                self.assertLess(positions[-1], page.index("<details"))
                self.assertNotRegex(page, r"<details\b[^>]*\bopen(?:\s|=|>)")
                for label in ("会话历史", "附件", "风险依据", "更多建议动作", "分析与技术信息"):
                    self.assertIn(label, page)

    def test_popup_keeps_draft_after_core_in_one_reachable_scroll_flow(self) -> None:
        page = (EXTENSION / "popup.html").read_text(encoding="utf-8")
        css = (EXTENSION / "popup.css").read_text(encoding="utf-8")
        soup = BeautifulSoup(page, "html.parser")
        draft = soup.select_one(".draft-section")

        self.assertIsNotNone(draft)
        self.assertIsNotNone(draft.find_parent("section", class_="result-section"))
        self.assertLess(page.index('id="work-must-check"'), page.index('class="draft-section"'))
        self.assertNotIn("overflow: hidden", css)
        self.assertNotIn("overflow-y: auto", css)
        self.assertNotIn("flex: 0 0 auto", css)

    def test_shared_component_css_pins_narrow_accessible_layout(self) -> None:
        css = COMPONENT_CSS.read_text(encoding="utf-8") if COMPONENT_CSS.exists() else ""
        self.assertIn("min-width: 0", css)
        self.assertIn("overflow-wrap: anywhere", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn(":focus-visible", css)
        self.assertIn("details > summary", css)
        self.assertNotIn("overflow-x: scroll", css)

    def test_status_is_polite_and_debug_scope_is_explicit(self) -> None:
        for path in (EXTENSION / "popup.html", LOCAL_DEBUG / "index.html"):
            page = path.read_text(encoding="utf-8")
            status = page[page.index('id="status"') : page.index('id="status"') + 180]
            self.assertIn('aria-live="polite"', status)
        debug = (LOCAL_DEBUG / "index.html").read_text(encoding="utf-8")
        self.assertIn("仅验证请求与结果渲染，不验证腾讯邮箱页面提取。", debug)
        for script in (
            (EXTENSION / "popup.js").read_text(encoding="utf-8"),
            (LOCAL_DEBUG / "app.js").read_text(encoding="utf-8"),
        ):
            self.assertIn('fields.status.textContent = "分析完成";', script)
            self.assertNotIn("Saved #", script)

    def test_loopback_static_assets_use_an_exact_allowlist(self) -> None:
        expected = {
            "/": LOCAL_DEBUG / "index.html",
            "/index.html": LOCAL_DEBUG / "index.html",
            "/app.js": LOCAL_DEBUG / "app.js",
            "/styles.css": LOCAL_DEBUG / "styles.css",
            "/shared/render_analysis.js": RENDERER,
            "/shared/analysis_components.css": COMPONENT_CSS,
        }
        for route, path in expected.items():
            with self.subTest(route=route):
                self.assertEqual(_frontend_asset_for_path(route), path)
        for route in (
            "/../AGENTS.md",
            "/shared/../api_client.js",
            "/backend/email_agent/server.py",
            "/.env",
            "/shared/api_client.js",
            "/unknown.js?x=1",
        ):
            with self.subTest(route=route):
                self.assertIsNone(_frontend_asset_for_path(route))

    def test_loopback_asset_code_respects_mechanical_size_limits(self) -> None:
        for path in (
            ROOT / "backend" / "email_agent" / "server.py",
            ROOT / "backend" / "email_agent" / "frontend_assets.py",
        ):
            with self.subTest(path=path.name):
                source = path.read_text(encoding="utf-8")
                self.assertLessEqual(len(source.splitlines()), 300)
                tree = ast.parse(source)
                lengths = [
                    node.end_lineno - node.lineno + 1
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                self.assertTrue(all(length <= 50 for length in lengths))

    def test_manifest_patch_version_is_023(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.2.3")

    def test_renderer_task_card_fallback_context_owner_and_draft_contract(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node.js is required for shared renderer behavior tests")
        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const source = fs.readFileSync({str(RENDERER)!r}, "utf8");
        function field() {{ return {{ textContent: "", value: "", hidden: true }}; }}
        const context = {{ window: {{}} }};
        vm.runInNewContext(source, context, {{ filename: "render_analysis.js" }});
        const fields = {{
          fallbackBanner: field(), conclusion: field(), currentRequest: field(),
          nextSteps: field(), keyFacts: field(), mustCheck: field(),
          conversationTimeline: field(), attachmentInsights: field(), attachments: field(),
          risks: field(), actions: field(), technicalDetails: field(),
          draftSubject: field(), draftBody: field(), draftReviewStatus: field(),
          draftReviewReasons: field(),
        }};
        const analysis = {{
          priority: "high", category: "order_followup",
          analysis_engine: {{ source: "rule_fallback", label: "Rule fallback", context_scope: "current_only", context_limited: true }},
          decision_brief: {{
            one_line_conclusion: "需核查交期后回复。",
            requested_outcome: "客户请求确认交货日期。",
            next_steps: [
              {{ step: "核查订单。", owner_hint: "internal_sales", due_hint: "今天" }},
              {{ step: "复核文件。", owner_hint: "attacker_owned_role", due_hint: "" }},
            ],
            key_facts: [{{ label: "PO", value: "PO-2026-001" }}],
            must_check: ["交付状态"], missing_info: ["跟踪号"],
          }},
          conversation_timeline: {{ previous_context: "历史", current_status: "unresolved", status_reason: "待确认", latest_external_request: "确认交期", latest_internal_commitment: "", open_items: [], confidence: "low" }},
          attachment_insights: [], attachments: [], risk_flags: [], suggested_actions: [],
          reply_draft: {{
            subject: "Re: Delivery confirmation",
            body: "Hello,\\n\\nPlease confirm the delivery date.\\n\\nBest regards",
            needs_human_review: true,
            review_reasons: ["需人工核对交期。"],
          }},
        }};
        context.window.EmailAssistantRender.renderAnalysis(fields, analysis);
        if (fields.fallbackBanner.hidden) throw new Error("fallback banner hidden");
        if (fields.fallbackBanner.textContent !== {FALLBACK_BANNER!r}) throw new Error(fields.fallbackBanner.textContent);
        if (!fields.nextSteps.textContent.includes("销售负责人")) throw new Error(fields.nextSteps.textContent);
        if (!fields.nextSteps.textContent.includes("相关负责人")) throw new Error(fields.nextSteps.textContent);
        if (fields.nextSteps.textContent.includes("attacker_owned_role")) throw new Error("raw owner leaked");
        if (!fields.mustCheck.textContent.includes("跟踪号")) throw new Error(fields.mustCheck.textContent);
        if (!fields.technicalDetails.textContent.includes("仅当前邮件")) throw new Error(fields.technicalDetails.textContent);
        if (!fields.technicalDetails.textContent.includes("上下文受限")) throw new Error(fields.technicalDetails.textContent);
        if (!fields.technicalDetails.textContent.includes("本地规则")) throw new Error(fields.technicalDetails.textContent);
        if (fields.technicalDetails.textContent.includes("Rule fallback")) throw new Error("fallback label was not localized");
        if (fields.draftSubject.textContent !== analysis.reply_draft.subject) throw new Error("draft subject changed");
        if (fields.draftBody.value !== analysis.reply_draft.body) throw new Error("draft body changed");
        if (!fields.draftReviewReasons.textContent.includes("需人工核对")) throw new Error("review reasons missing");
        analysis.analysis_engine = {{ source: "ai_model", label: "DeepSeek V4 Flash" }};
        context.window.EmailAssistantRender.renderAnalysis(fields, analysis);
        if (!fields.fallbackBanner.hidden || fields.fallbackBanner.textContent) throw new Error("model result shows fallback banner");
        """
        completed = subprocess.run(
            [node, "-e", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr or completed.stdout)


if __name__ == "__main__":
    unittest.main()
