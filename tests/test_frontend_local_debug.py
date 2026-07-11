"""Tests for the local debug assistant window."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "local_debug_page"


class FrontendLocalDebugTests(unittest.TestCase):
    def test_local_debug_page_has_thread_and_attachment_insight_sections(self) -> None:
        page = (FRONTEND / "index.html").read_text(encoding="utf-8")
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="conversation-timeline"', page)
        self.assertIn('id="attachment-insights"', page)
        self.assertIn("会话进度", page)
        self.assertIn("附件洞察", page)
        self.assertIn("renderConversationTimeline", script)
        self.assertIn("analysis.conversation_timeline", script)
        self.assertIn("renderAttachmentInsights", script)
        self.assertIn("analysis.attachment_insights", script)
        self.assertIn("document.createElement", script)
        self.assertNotIn("innerHTML", script)

    def test_local_debug_page_renders_thread_and_attachment_insights_as_safe_nodes(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for local debug renderer tests")

        app = FRONTEND / "app.js"
        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const source = fs.readFileSync({str(app)!r}, "utf8");

        class FakeElement {{
          constructor(tagName = "div") {{
            this.tagName = tagName.toUpperCase();
            this.children = [];
            this.className = "";
            this.textContent = "";
            this.value = "";
          }}
          set innerHTML(value) {{ throw new Error(`innerHTML must not be used: ${{value}}`); }}
          addEventListener() {{}}
          appendChild(child) {{
            this.children.push(child);
            this.textContent = this.children.map((item) => item.textContent || "").join("");
            return child;
          }}
          replaceChildren(...children) {{
            this.children = children;
            this.textContent = children.map((item) => item.textContent || "").join("\\n");
          }}
          querySelectorAll(tagName) {{
            const matches = [];
            const expected = tagName.toUpperCase();
            function walk(node) {{
              if (node.tagName === expected) matches.push(node);
              for (const child of node.children || []) walk(child);
            }}
            walk(this);
            return matches;
          }}
        }}

        const elements = new Map();
        const document = {{
          querySelector(selector) {{
            if (!elements.has(selector)) elements.set(selector, new FakeElement());
            return elements.get(selector);
          }},
          createElement(tagName) {{ return new FakeElement(tagName); }},
          createTextNode(text) {{ return {{ tagName: "#TEXT", textContent: String(text) }}; }},
        }};
        elements.set("#conversation-timeline", new FakeElement());
        elements.set("#attachment-insights", new FakeElement());
        const context = {{ document, navigator: {{ clipboard: {{ writeText: async () => {{}} }} }} }};
        vm.runInNewContext(source, context);
        const backslash = String.fromCharCode(92);
        const quote = String.fromCharCode(34);
        context.analysis = {{
          priority: "high",
          summary: "需要回复最新请求。",
          category: "customer_inquiry",
          analysis_engine: {{ label: "Rule fallback" }},
          decision_brief: {{
            one_line_conclusion: "先核查后回复。", requested_outcome: "获得确认。", next_steps: [], key_facts: [],
            must_check: [], missing_info: [], reply_recommendation: {{ reason: "需人工审核。" }}, confidence: "medium",
          }},
          conversation_timeline: {{
            previous_context: "客户此前询问报价。", current_status: "partially_resolved", status_reason: "数量已确认，价格待核查。",
            latest_external_request: "请确认最终价格。", latest_internal_commitment: "销售将复核价格。",
            open_items: [{{ item: "复核价格", owner_hint: "sales", due_hint: "today", source: "thread" }}], confidence: "high",
          }},
          attachment_insights: [
            {{
              filename: "quote<img>.xlsx", type: "xlsx", status: "parsed",
              summary: "debug quoted URL " + quote + "https://debug.example/private report.xlsx" + quote,
              key_facts: [
                "Total: 200",
                "debug Windows path=" + quote + "C:" + backslash + "Program Files" + backslash + "Private" + backslash + "debug.xlsx" + quote,
                "debug UNC path=" + quote + backslash + backslash + "debug-server" + backslash + "share name" + backslash + "quote.xlsx" + quote,
                "debug root path=/secret",
              ],
              limitations: [
                "debug parser path=/var/tmp/private.txt",
                "debug quoted POSIX path=" + quote + "/var/tmp/private report.txt" + quote,
              ],
              raw_text: "LOCAL DEBUG RAW TEXT MUST NOT RENDER", private_url: "file:///private/quote.xlsx",
            }},
            {{
              filename: "failed.pdf", type: "pdf", status: "failed", summary: "", key_facts: [],
              limitations: ["解析失败，详情见 https://debug.example/failure。"],
            }},
          ],
          risk_flags: [], suggested_actions: [],
          reply_draft: {{ body: "Hello,\\n\\nWe are reviewing the final price.\\n\\nBest regards" }},
        }};
        vm.runInContext("renderAnalysis(analysis)", context);

        const timeline = elements.get("#conversation-timeline");
        const insights = elements.get("#attachment-insights");
        if (timeline.children.length !== 6) throw new Error(`timeline nodes missing: ${{timeline.children.length}}`);
        if (!timeline.textContent.includes("部分解决") || !timeline.textContent.includes("复核价格")) {{
          throw new Error(`timeline content missing: ${{timeline.textContent}}`);
        }}
        if (insights.children.length !== 2) throw new Error(`insight nodes missing: ${{insights.children.length}}`);
        if (!insights.textContent.includes("quote<img>.xlsx") || !insights.textContent.includes("Total: 200") ||
            !insights.textContent.includes("failed.pdf") || !insights.textContent.includes("解析失败") ||
            !insights.textContent.includes("暂无可用摘要")) {{
          throw new Error(`insight content missing: ${{insights.textContent}}`);
        }}
        for (const forbidden of [
          "LOCAL DEBUG RAW TEXT", "file:///private", "https://debug.example",
          "debug quoted URL", "private report.xlsx", "debug Windows path", "Program Files",
          "debug UNC path", "share name", "debug root path=/secret",
          "debug parser path=/var/tmp/private.txt", "debug quoted POSIX path", "private report.txt",
        ]) {{
          if (insights.textContent.includes(forbidden)) {{
            throw new Error(`private/raw insight field leaked: ${{forbidden}} in ${{insights.textContent}}`);
          }}
        }}
        if (!insights.textContent.includes("[已隐藏链接或路径]")) {{
          throw new Error(`attachment redaction placeholder missing: ${{insights.textContent}}`);
        }}
        if (insights.querySelectorAll("a").length || insights.querySelectorAll("img").length) {{
          throw new Error("attachment insight content became active markup");
        }}
        if (!elements.get("#draft").value.startsWith("Hello,")) throw new Error("English draft was not preserved");

        context.analysis.conversation_timeline = "stale";
        vm.runInContext("renderAnalysis(analysis)", context);
        if (timeline.textContent !== "暂无会话进度") {{
          throw new Error(`missing timeline fallback parity failed: ${{timeline.textContent}}`);
        }}
        """

        result = subprocess.run(
            ["node", "-e", textwrap.dedent(script)],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_local_debug_aborts_stalled_backend_and_reenables_analyze(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for local debug behavior tests")

        app = FRONTEND / "app.js"
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__APP__, "utf8")
              .replace("const ANALYZE_TIMEOUT_MS = 15000;", "const ANALYZE_TIMEOUT_MS = 20;");
            const listeners = new Map();
            const elements = new Map();
            function element(selector) {
              if (!elements.has(selector)) {
                elements.set(selector, {
                  value: selector === "#subject" ? "Synthetic" :
                    selector === "#from" ? "sender@example.test" :
                    selector === "#body" ? "Synthetic body" : "",
                  textContent: "",
                  disabled: false,
                  children: [],
                  addEventListener: (type, callback) => listeners.set(`${selector}:${type}`, callback),
                  replaceChildren: (...children) => {},
                  appendChild: (child) => child,
                });
              }
              return elements.get(selector);
            }
            let requestSignal;
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              document: {
                querySelector: element,
                createElement: () => element(`#created-${Math.random()}`),
                createTextNode: (text) => ({ textContent: String(text), children: [] }),
              },
              navigator: { clipboard: { writeText: async () => {} } },
              fetch: async (_url, options) => new Promise((_resolve, reject) => {
                requestSignal = options.signal;
                options.signal.addEventListener("abort", () => {
                  const error = new Error("PRIVATE_LOCAL_DEBUG_TIMEOUT");
                  error.name = "AbortError";
                  reject(error);
                });
              }),
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "app.js" });

            (async () => {
              const analyze = listeners.get("#analyze-button:click");
              await Promise.race([
                analyze(),
                new Promise((_resolve, reject) => setTimeout(
                  () => reject(new Error("local debug request did not honor its deadline")),
                  250,
                )),
              ]);
              if (!requestSignal || requestSignal.aborted !== true) {
                throw new Error("local debug request was not aborted");
              }
              if (elements.get("#analyze-button").disabled !== false) {
                throw new Error("local debug Analyze remained disabled");
              }
              const status = elements.get("#status").textContent;
              if (!status.includes("timed out") || !status.includes("try again")) {
                throw new Error(`unsafe timeout status: ${status}`);
              }
              if (status.includes("PRIVATE_LOCAL_DEBUG_TIMEOUT")) {
                throw new Error("private timeout detail leaked");
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__APP__", repr(str(app)))
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_local_debug_ignores_out_of_order_older_response(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for local debug behavior tests")

        app = FRONTEND / "app.js"
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__APP__, "utf8");
            function deferred() {
              let resolve;
              const promise = new Promise((yes) => { resolve = yes; });
              return { promise, resolve };
            }
            async function waitFor(predicate) {
              for (let index = 0; index < 50; index += 1) {
                if (predicate()) return;
                await new Promise((resolve) => setTimeout(resolve, 0));
              }
              throw new Error("request did not start");
            }
            function analysis(marker) {
              return {
                priority: "normal", summary: marker, category: "unknown",
                analysis_engine: { label: "Rule fallback" },
                decision_brief: {}, conversation_timeline: {}, attachment_insights: [],
                risk_flags: [], suggested_actions: [], reply_draft: { body: `Draft ${marker}` },
              };
            }
            const listeners = new Map();
            const elements = new Map();
            function element(selector) {
              if (!elements.has(selector)) {
                elements.set(selector, {
                  value: selector === "#subject" ? "Synthetic" :
                    selector === "#from" ? "sender@example.test" :
                    selector === "#body" ? "Synthetic body" : "",
                  textContent: "", disabled: false, children: [], className: "",
                  addEventListener: (type, callback) => listeners.set(`${selector}:${type}`, callback),
                  replaceChildren(...children) {
                    this.children = children;
                    this.textContent = children.map((item) => item.textContent || "").join("\n");
                  },
                  appendChild(child) { this.children.push(child); return child; },
                });
              }
              return elements.get(selector);
            }
            const first = deferred();
            const second = deferred();
            const queue = [first, second];
            let fetchCalls = 0;
            const context = {
              AbortController, setTimeout, clearTimeout,
              document: {
                querySelector: element,
                createElement: () => element(`#created-${Math.random()}`),
                createTextNode: (text) => ({ textContent: String(text), children: [] }),
              },
              navigator: { clipboard: { writeText: async () => {} } },
              fetch: async () => {
                const gate = queue[fetchCalls++];
                const payload = await gate.promise;
                return { json: async () => payload };
              },
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "app.js" });

            (async () => {
              const analyze = listeners.get("#analyze-button:click");
              const older = analyze();
              await waitFor(() => fetchCalls === 1);
              const newer = analyze();
              await waitFor(() => fetchCalls === 2);
              second.resolve({ ok: true, saved_id: 2, analysis: analysis("newer") });
              await newer;
              first.resolve({ ok: true, saved_id: 1, analysis: analysis("older") });
              await older;
              if (elements.get("#summary").textContent !== "newer") {
                throw new Error(`older response overwrote summary: ${elements.get("#summary").textContent}`);
              }
              if (elements.get("#draft").value !== "Draft newer") {
                throw new Error(`older response overwrote draft: ${elements.get("#draft").value}`);
              }
              if (elements.get("#status").textContent !== "Saved #2") {
                throw new Error(`older response overwrote status: ${elements.get("#status").textContent}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__APP__", repr(str(app)))
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

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
        self.assertIn("if (!data.ok)", script)
        self.assertIn('fields.status.textContent = data.error?.message || "Analysis failed"', script)
        self.assertIn("finally", script)
        self.assertIn("fields.analyzeButton.disabled = false", script)
        self.assertIn('fields.priority.textContent = "-"', script)
        self.assertIn('fields.summary.textContent = "No analysis yet"', script)
        self.assertIn('fields.attachmentsPreview.textContent = "-"', script)
        self.assertIn('fields.draft.value = ""', script)

    def test_local_debug_page_handles_backend_unavailable(self) -> None:
        script = (FRONTEND / "app.js").read_text(encoding="utf-8")

        self.assertIn("try {", script)
        self.assertIn("catch (error)", script)
        self.assertIn("Local analysis service unavailable", script)
        self.assertIn("generation === analysisGeneration", script)
        self.assertIn('fields.status.textContent = "Local analysis service unavailable"', script)

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
        self.assertIn('id="decision-brief"', page)
        self.assertIn("analysis.analysis_engine", script)
        self.assertIn("fields.engine.textContent", script)
        self.assertIn("formatDecisionBrief", script)
        self.assertIn("analysis.decision_brief", script)

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
