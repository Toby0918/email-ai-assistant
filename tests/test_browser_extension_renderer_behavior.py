"""Behavior tests for browser extension analysis rendering."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "frontend" / "browser_extension" / "shared" / "render_analysis.js"
POPUP_HTML = ROOT / "frontend" / "browser_extension" / "popup.html"
POPUP_CSS = ROOT / "frontend" / "browser_extension" / "popup.css"
POPUP_SCRIPT = ROOT / "frontend" / "browser_extension" / "popup.js"


class BrowserExtensionRendererBehaviorTests(unittest.TestCase):
    def test_analysis_urls_are_inert_without_validated_url_objects(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");

        class FakeElement {{
          constructor(tagName = "div") {{
            this.tagName = tagName.toUpperCase();
            this.children = [];
            this.className = "";
            this.textContent = "";
            this.value = "";
            this.ownerDocument = fakeDocument;
          }}

          appendChild(child) {{
            this.children.push(child);
            this.textContent = this.children.map((item) => item.textContent || "").join("");
            return child;
          }}

          replaceChildren(...children) {{
            this.children = children;
            this.textContent = this.children.map((item) => item.textContent || "").join("\\n");
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

        const fakeDocument = {{
          createElement: (tagName) => new FakeElement(tagName),
          createTextNode: (text) => ({{ tagName: "#TEXT", textContent: String(text) }}),
        }};
        const context = {{ window: {{}}, document: fakeDocument }};
        vm.runInNewContext(renderer, context);
        const fields = {{
          priority: new FakeElement(), summary: new FakeElement(), category: new FakeElement(),
          engine: new FakeElement(), decisionBrief: new FakeElement(),
          conversationTimeline: new FakeElement(), attachmentInsights: new FakeElement(),
          attachments: new FakeElement(), risks: new FakeElement(), actions: new FakeElement(),
          draft: new FakeElement("textarea"),
        }};
        const urls = [
          "https://decision.example.test/rfq/42",
          "https://risk.example.test/rfq/42",
          "https://action.example.test/rfq/42",
        ];

        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          decision_brief: {{
            one_line_conclusion: `Review ${{urls[0]}}`,
            requested_outcome: "Review the request.", next_steps: [], key_facts: [],
            must_check: [], missing_info: [],
            reply_recommendation: {{ should_reply: true, reply_type: "provide_info", reason: "Review." }},
            confidence: "medium",
          }},
          risk_flags: [{{ type: "other", level: "medium", evidence: `Check ${{urls[1]}}`, recommendation: "Review." }}],
          suggested_actions: [{{ type: "other", description: `Check ${{urls[2]}}` }}],
          reply_draft: {{ body: "Draft" }},
        }});

        for (const [field, url] of [
          [fields.decisionBrief, urls[0]], [fields.risks, urls[1]], [fields.actions, urls[2]],
        ]) {{
          if (!field.textContent.includes(url)) throw new Error(`URL text missing: ${{url}}`);
          if (field.querySelectorAll("a").length !== 0) {{
            throw new Error(`unvalidated analysis URL became clickable: ${{url}}`);
          }}
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

    def test_renders_conversation_progress_and_attachment_insights_safely(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");

        class FakeElement {{
          constructor(tagName = "div") {{
            this.tagName = tagName.toUpperCase();
            this.children = [];
            this.className = "";
            this.textContent = "";
            this.value = "";
            this.href = "";
            this.target = "";
            this.rel = "";
            this.ownerDocument = fakeDocument;
          }}

          set innerHTML(value) {{
            throw new Error(`innerHTML must not be used: ${{value}}`);
          }}

          appendChild(child) {{
            this.children.push(child);
            this.textContent = this.children.map((item) => item.textContent || "").join("");
            return child;
          }}

          replaceChildren(...children) {{
            this.children = children;
            this.textContent = this.children.map((item) => item.textContent || "").join("\\n");
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

        const fakeDocument = {{
          createElement: (tagName) => new FakeElement(tagName),
          createTextNode: (text) => ({{ tagName: "#TEXT", textContent: String(text) }}),
        }};
        const context = {{ window: {{}}, document: fakeDocument }};
        vm.runInNewContext(renderer, context);
        const backslash = String.fromCharCode(92);
        const quote = String.fromCharCode(34);

        const fields = {{
          priority: new FakeElement(),
          summary: new FakeElement(),
          category: new FakeElement(),
          engine: new FakeElement(),
          decisionBrief: new FakeElement(),
          conversationTimeline: new FakeElement(),
          attachmentInsights: new FakeElement(),
          attachments: new FakeElement(),
          risks: new FakeElement(),
          actions: new FakeElement(),
          draft: new FakeElement("textarea"),
        }};

        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "high",
          summary: "客户仍在等待报价。",
          category: "customer_inquiry",
          analysis_engine: {{ label: "Rule fallback" }},
          decision_brief: {{
            one_line_conclusion: "需要核查成本后回复客户。",
            requested_outcome: "客户希望获得报价。",
            next_steps: [],
            key_facts: [],
            must_check: [],
            missing_info: [],
            reply_recommendation: {{ should_reply: true, reply_type: "escalate_first", reason: "先内部核查。" }},
            confidence: "medium",
          }},
          conversation_timeline: {{
            previous_context: "客户此前提交了 RFQ。",
            current_status: "unresolved",
            status_reason: "成本仍待内部核查。",
            latest_external_request: "客户要求明天前提供报价。",
            latest_internal_commitment: "销售已承诺核查成本。",
            open_items: [
              {{ item: "核对成本", owner_hint: "internal_sales", due_hint: "明天", source: "thread" }},
              {{ item: "复核附件数量", owner_hint: "engineering", due_hint: "今天", source: "attachment" }},
            ],
            confidence: "medium",
          }},
          attachment_insights: [
            {{
              filename: "quote<script>.pdf",
              type: "pdf",
              status: "parsed",
              summary: "quoted URL " + quote + "https://private.example/quoted report.pdf" + quote,
              key_facts: [
                "RFQ 42",
                "200 pcs",
                "Windows path=" + quote + "C:" + backslash + "Program Files" + backslash + "Private" + backslash + "quote.xlsx" + quote,
                "UNC path=" + quote + backslash + backslash + "server" + backslash + "share name" + backslash + "quote.xlsx" + quote,
                "root path=/secret",
              ],
              limitations: [
                "parser path=/var/tmp/private.txt",
                "quoted POSIX path=" + quote + "/var/tmp/private report.txt" + quote,
              ],
              raw_text: "RAW ATTACHMENT TEXT MUST NOT RENDER",
              private_url: "file:///private/quote.pdf",
            }},
            {{
              filename: "failed.docx",
              type: "docx",
              status: "failed",
              summary: "",
              key_facts: [],
              limitations: ["解析失败，需人工核查。", "javascript:alert(1) file:///private/path data:text/html,boom"],
              raw_text: "SECOND RAW ATTACHMENT TEXT MUST NOT RENDER",
            }},
          ],
          risk_flags: [{{
            type: "commitment_risk",
            level: "medium",
            evidence: "请查看https://portal.example/rfq/42， 并访问http://status.example/rfq/42； 拒绝 data:text/plain,内容https://data.example/private、 javascript:说明https://script.example/private、 file:///目录https://file.example/private、 ftp://host/目录https://ftp.example/private。",
            recommendation: "内部确认后回复。",
          }}],
          suggested_actions: [{{ type: "confirm", description: "核查成本。" }}],
          reply_draft: {{ body: "Hello,\\n\\nWe are reviewing the quotation.\\n\\nBest regards" }},
        }});

        const mixedSchemeLinks = fields.risks.querySelectorAll("a");
        if (mixedSchemeLinks.length !== 0) {{
          throw new Error(`analysis text produced anchors: ${{mixedSchemeLinks.map((item) => item.href)}}`);
        }}
        if (fields.conversationTimeline.children.length !== 7) {{
          throw new Error(`expected seven timeline entries, got ${{fields.conversationTimeline.children.length}}`);
        }}
        const timelineText = fields.conversationTimeline.textContent;
        for (const expected of [
          "前情", "客户此前提交了 RFQ", "当前状态", "未解决", "成本仍待内部核查",
          "最新外部请求", "客户要求明天前提供报价", "最新内部承诺", "销售已承诺核查成本",
          "置信度", "中", "待办 1", "核对成本", "待办 2", "复核附件数量",
        ]) {{
          if (!timelineText.includes(expected)) throw new Error(`timeline text missing ${{expected}}: ${{timelineText}}`);
        }}
        if (fields.attachmentInsights.children.length !== 2) {{
          throw new Error(`expected two attachment insight entries, got ${{fields.attachmentInsights.children.length}}`);
        }}
        const insightText = fields.attachmentInsights.textContent;
        for (const expected of [
          "quote<script>.pdf", "PDF", "已解析", "摘要", "RFQ 42", "200 pcs",
          "failed.docx", "DOCX", "解析失败", "解析失败，需人工核查", "暂无可用摘要",
        ]) {{
          if (!insightText.includes(expected)) throw new Error(`attachment insight missing ${{expected}}: ${{insightText}}`);
        }}
        for (const forbidden of [
          "RAW ATTACHMENT TEXT MUST NOT RENDER", "SECOND RAW ATTACHMENT TEXT MUST NOT RENDER", "file:///private/quote.pdf",
          "quoted URL", "quoted report.pdf", "Windows path", "Program Files",
          "UNC path", "share name", "root path=/secret",
          "parser path=/var/tmp/private.txt", "quoted POSIX path", "private report.txt",
        ]) {{
          if (insightText.includes(forbidden)) throw new Error(`private/raw attachment field leaked: ${{forbidden}}`);
        }}
        if (!insightText.includes("[已隐藏链接或路径]")) {{
          throw new Error(`attachment redaction placeholder missing: ${{insightText}}`);
        }}
        if (fields.attachmentInsights.querySelectorAll("a").length !== 0) {{
          throw new Error("attachment filenames and model summaries must never become links");
        }}
        if (fields.attachmentInsights.querySelectorAll("img").length !== 0) {{
          throw new Error("attachment model content became executable HTML");
        }}
        const riskLinks = fields.risks.querySelectorAll("a");
        if (riskLinks.length !== 0) {{
          throw new Error(`unvalidated risk text became clickable: ${{riskLinks.map((item) => item.href)}}`);
        }}
        for (const inertUrl of ["https://portal.example/rfq/42", "http://status.example/rfq/42"]) {{
          if (!fields.risks.textContent.includes(inertUrl)) {{
            throw new Error(`inert URL text missing: ${{inertUrl}}`);
          }}
        }}
        for (const mixedScheme of [
          "data:text/plain,内容https://data.example/private",
          "javascript:说明https://script.example/private",
          "file:///目录https://file.example/private",
          "ftp://host/目录https://ftp.example/private",
        ]) {{
          if (!fields.risks.textContent.includes(mixedScheme)) {{
            throw new Error(`non-http scheme should remain visible text: ${{mixedScheme}}`);
          }}
        }}
        if (!fields.draft.value.startsWith("Hello,")) {{
          throw new Error(`English draft was not preserved: ${{fields.draft.value}}`);
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

    def test_missing_thread_and_attachment_fields_keep_other_analysis_readable(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");
        const element = () => ({{ textContent: "", value: "" }});
        const fields = {{
          priority: element(), summary: element(), category: element(), engine: element(),
          decisionBrief: element(), conversationTimeline: element(), attachmentInsights: element(),
          attachments: element(), risks: element(), actions: element(), draft: element(),
        }};
        const context = {{ window: {{}} }};
        vm.runInNewContext(renderer, context);
        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "normal",
          summary: "正文分析仍然可用。",
          category: "internal",
          analysis_engine: {{ label: "Rule fallback" }},
          decision_brief: {{
            one_line_conclusion: "继续人工核查。", requested_outcome: "确认现状。", next_steps: [], key_facts: [],
            must_check: [], missing_info: [],
            reply_recommendation: {{ should_reply: true, reply_type: "ask_clarification", reason: "信息不足。" }},
            confidence: "low",
          }},
          conversation_timeline: "stale",
          attachment_insights: {{ stale: true }},
          risk_flags: [{{ type: "commitment_risk", level: "low", evidence: "仍需核查。" }}],
          suggested_actions: [{{ type: "confirm", description: "人工确认。" }}],
          reply_draft: {{ body: "Hello, please confirm the latest status." }},
        }});
        if (fields.conversationTimeline.textContent !== "暂无会话进度") {{
          throw new Error(`timeline fallback missing: ${{fields.conversationTimeline.textContent}}`);
        }}
        if (fields.attachmentInsights.textContent !== "暂无附件洞察") {{
          throw new Error(`attachment fallback missing: ${{fields.attachmentInsights.textContent}}`);
        }}
        if (!fields.decisionBrief.textContent.includes("继续人工核查")) throw new Error("decision brief broke");
        if (!fields.risks.textContent.includes("承诺风险")) throw new Error("risks broke");
        if (!fields.actions.textContent.includes("人工确认")) throw new Error("actions broke");
        if (!fields.draft.value.includes("please confirm")) throw new Error("draft broke");
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

    def test_side_panel_sections_scroll_without_hiding_copy_draft_control(self) -> None:
        page = POPUP_HTML.read_text(encoding="utf-8")
        styles = POPUP_CSS.read_text(encoding="utf-8")
        script = POPUP_SCRIPT.read_text(encoding="utf-8")

        self.assertIn('id="conversation-timeline"', page)
        self.assertIn('id="attachment-insights"', page)
        self.assertIn("会话进度", page)
        self.assertIn("附件洞察", page)
        self.assertIn('conversationTimeline: document.querySelector("#conversation-timeline")', script)
        self.assertIn('attachmentInsights: document.querySelector("#attachment-insights")', script)

        draft_start = page.index('<section class="draft-section"')
        header_start = page.index('<div class="draft-header">', draft_start)
        header_end = page.index("</div>", header_start)
        copy_button = page.index('id="copy-draft-button"')
        self.assertLess(page.index('id="work-must-check"'), draft_start)
        self.assertLess(header_start, copy_button)
        self.assertLess(copy_button, header_end)
        self.assertNotIn("overflow: hidden", styles)
        self.assertNotIn("overflow-y: auto", styles)
        self.assertNotRegex(styles, r"(?s)\.draft-section\s*\{[^}]*flex:\s*0\s+0\s+auto")

    def test_renders_long_sections_as_structured_lists(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");

        class FakeElement {{
          constructor(tagName = "div") {{
            this.tagName = tagName.toUpperCase();
            this.children = [];
            this.className = "";
            this.textContent = "";
            this.value = "";
            this.ownerDocument = fakeDocument;
          }}

          appendChild(child) {{
            this.children.push(child);
            this.textContent = this.children.map((item) => item.textContent || "").join("\\n");
            return child;
          }}

          replaceChildren(...children) {{
            this.children = children;
            this.textContent = this.children.map((item) => item.textContent || "").join("\\n");
          }}
        }}

        const fakeDocument = {{
          createElement: (tagName) => new FakeElement(tagName),
        }};
        const context = {{ window: {{}}, document: fakeDocument }};
        vm.runInNewContext(renderer, context);

        const fields = {{
          priority: new FakeElement(),
          summary: new FakeElement(),
          category: new FakeElement(),
          engine: new FakeElement(),
          decisionBrief: new FakeElement(),
          attachments: new FakeElement(),
          risks: new FakeElement(),
          actions: new FakeElement(),
          draft: new FakeElement("textarea"),
        }};

        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "high",
          summary: "RFQ requires quote review for two long part numbers and a supplier portal link.",
          category: "new_product_development",
          analysis_engine: {{ label: "Local Qwen" }},
          decision_brief: {{
            one_line_conclusion: "这是一封 RFQ 报价提醒，需要核查两个零件和供应商链接后准备报价。",
            requested_outcome: "对方希望获得两个选项的报价。",
            next_steps: [
              {{
                step: "核查两个 Part No. 并确认报价、交期和附件要求。",
                owner_hint: "采购/工程负责人",
                due_hint: "2026-07-06 06:00 Asia/Shanghai",
                source: "latest_message",
              }},
            ],
            key_facts: [
              {{ label: "RFQ", value: "11467", source: "latest_message" }},
              {{ label: "链接", value: "https://app11.jaggaer.example/rfq/index.php?rfq=11467", source: "latest_message" }},
            ],
            must_check: ["供应商平台链接", "附件说明"],
            missing_info: ["内部报价审批状态"],
            reply_recommendation: {{
              should_reply: true,
              reply_type: "escalate_first",
              reason: "涉及价格和交期承诺，需内部审核后回复。",
            }},
            confidence: "medium",
          }},
          attachments: [
            {{ filename: "Supplier_Instruction_with_a_very_long_name_for_quote_process.pdf", size: "1.64M", type: "pdf" }},
          ],
          risk_flags: [
            {{
              type: "commitment_risk",
              level: "high",
              evidence: "RFQ 11467 includes part numbers 1156653 and 1687433 plus a long supplier portal URL https://app11.jaggaer.example/rfq/index.php?controller=quote&type=rfq&id=1842236&cid=225221.",
            }},
            {{
              type: "delivery_risk",
              level: "medium",
              evidence: "Quote deadline is soon; confirm lead time before replying.",
            }},
          ],
          suggested_actions: [
            {{
              type: "prepare_quote",
              description: "Review both options, confirm cost and lead time internally, then prepare a checked quotation.",
            }},
            {{
              type: "confirm",
              description: "Ask the responsible owner whether attachment instructions are complete before sending any commitment.",
            }},
          ],
          reply_draft: {{ body: "Hello,\\n\\nWe will review and confirm.\\n\\nBest regards" }},
        }});

        if (fields.risks.children.length !== 2) {{
          throw new Error(`expected two risk list items, got ${{fields.risks.children.length}}`);
        }}
        if (fields.actions.children.length !== 2) {{
          throw new Error(`expected two action list items, got ${{fields.actions.children.length}}`);
        }}
        if (fields.attachments.children.length !== 1) {{
          throw new Error(`expected one attachment list item, got ${{fields.attachments.children.length}}`);
        }}
        if (!fields.risks.children[0].className.includes("analysis-list__item")) {{
          throw new Error(`risk item class missing: ${{fields.risks.children[0].className}}`);
        }}
        if (fields.risks.textContent.includes("[object Object]")) {{
          throw new Error(`risk object text leaked: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("https://app11.jaggaer.example")) {{
          throw new Error(`long URL evidence missing: ${{fields.risks.textContent}}`);
        }}
        if (!fields.actions.textContent.includes("prepare a checked quotation")) {{
          throw new Error(`action description missing: ${{fields.actions.textContent}}`);
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

    def test_renders_risk_action_details_with_inert_url_text(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");

        class FakeElement {{
          constructor(tagName = "div") {{
            this.tagName = tagName.toUpperCase();
            this.children = [];
            this.className = "";
            this.textContent = "";
            this.value = "";
            this.attributes = {{}};
            this.href = "";
            this.target = "";
            this.rel = "";
            this.ownerDocument = fakeDocument;
          }}

          appendChild(child) {{
            this.children.push(child);
            this.textContent = this.children.map((item) => item.textContent || "").join("");
            return child;
          }}

          replaceChildren(...children) {{
            this.children = children;
            this.textContent = this.children.map((item) => item.textContent || "").join("\\n");
          }}

          setAttribute(name, value) {{
            this.attributes[name] = value;
            this[name] = value;
          }}

          querySelectorAll(tagName) {{
            const matches = [];
            const expected = tagName.toUpperCase();
            function walk(node) {{
              if (node.tagName === expected) {{
                matches.push(node);
              }}
              for (const child of node.children || []) {{
                walk(child);
              }}
            }}
            walk(this);
            return matches;
          }}
        }}

        const fakeDocument = {{
          createElement: (tagName) => new FakeElement(tagName),
          createTextNode: (text) => ({{ textContent: text }}),
        }};
        const context = {{ window: {{}}, document: fakeDocument }};
        vm.runInNewContext(renderer, context);

        const fields = {{
          priority: new FakeElement(),
          summary: new FakeElement(),
          category: new FakeElement(),
          engine: new FakeElement(),
          decisionBrief: new FakeElement(),
          attachments: new FakeElement(),
          risks: new FakeElement(),
          actions: new FakeElement(),
          draft: new FakeElement("textarea"),
        }};

        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "high",
          summary: "RFQ reminder needs internal quote review.",
          category: "new_product_development",
          analysis_engine: {{ label: "Local Qwen" }},
          decision_brief: {{
            one_line_conclusion: "这是一封 RFQ 报价提醒，需要核查供应商链接后准备报价。",
            requested_outcome: "对方希望在供应商系统提交报价。",
            next_steps: [
              {{
                step: "核查 RFQ 11467 的两个 Part No.，确认报价信息后再在链接中处理。",
                owner_hint: "采购/工程负责人",
                due_hint: "2026-07-06 06:00 Asia/Shanghai",
                source: "latest_message",
              }},
            ],
            key_facts: [
              {{ label: "链接", value: "https://app11.jaggaer.example/rfq/index.php?rfq=11467", source: "latest_message" }},
            ],
            must_check: ["报价", "交期"],
            missing_info: ["内部审批"],
            reply_recommendation: {{
              should_reply: true,
              reply_type: "escalate_first",
              reason: "涉及报价承诺，需内部确认后回复。",
            }},
            confidence: "medium",
          }},
          risk_flags: [
            {{
              type: "commitment_risk",
              level: "medium",
              evidence: "对方要求在 https://app11.jaggaer.example/rfq/index.php?rfq=11467 内提交报价。",
              recommendation: "先确认价格、交期和附件要求，再回复客户。",
            }},
          ],
          suggested_actions: [
            {{
              type: "prepare_quote",
              description: "核查 RFQ 11467 的两个 Part No.，确认报价信息后再在链接中处理。",
              owner_hint: "采购/工程负责人",
              due_hint: "2026-07-06 06:00 Asia/Shanghai",
            }},
          ],
          reply_draft: {{ body: "Dear Ravi,\\n\\nWe are reviewing.\\n\\nBest regards" }},
        }});

        const riskItem = fields.risks.children[0];
        const actionItem = fields.actions.children[0];
        if (!riskItem.textContent.includes("承诺风险（中）")) {{
          throw new Error(`risk title missing: ${{riskItem.textContent}}`);
        }}
        if (!riskItem.textContent.includes("依据：对方要求在")) {{
          throw new Error(`risk evidence line missing: ${{riskItem.textContent}}`);
        }}
        if (!riskItem.textContent.includes("建议：先确认价格")) {{
          throw new Error(`risk recommendation line missing: ${{riskItem.textContent}}`);
        }}
        if (!actionItem.textContent.includes("准备报价")) {{
          throw new Error(`action title missing: ${{actionItem.textContent}}`);
        }}
        if (!actionItem.textContent.includes("事项：核查 RFQ 11467")) {{
          throw new Error(`action description line missing: ${{actionItem.textContent}}`);
        }}
        if (!actionItem.textContent.includes("负责人：采购/工程负责人")) {{
          throw new Error(`action owner line missing: ${{actionItem.textContent}}`);
        }}
        if (!actionItem.textContent.includes("期限：2026-07-06")) {{
          throw new Error(`action due line missing: ${{actionItem.textContent}}`);
        }}
        if (!fields.decisionBrief.textContent.includes("这是一封 RFQ 报价提醒")) {{
          throw new Error(`decision conclusion missing: ${{fields.decisionBrief.textContent}}`);
        }}
        if (!fields.decisionBrief.textContent.includes("当前动作")) {{
          throw new Error(`decision step label missing: ${{fields.decisionBrief.textContent}}`);
        }}
        if (fields.decisionBrief.textContent.includes("[object Object]")) {{
          throw new Error(`decision object leaked: ${{fields.decisionBrief.textContent}}`);
        }}

        const anchors = fields.risks.querySelectorAll("a");
        if (anchors.length !== 0) {{
          throw new Error(`unvalidated URL became clickable: ${{anchors.length}}`);
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

    def test_renders_object_lists_without_default_object_text(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension renderer tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const renderer = fs.readFileSync({str(RENDERER)!r}, "utf8");
        const context = {{ window: {{}} }};
        vm.runInNewContext(renderer, context);

        const fields = {{
          priority: {{ textContent: "" }},
          summary: {{ textContent: "" }},
          category: {{ textContent: "" }},
          engine: {{ textContent: "" }},
          decisionBrief: {{ textContent: "" }},
          attachments: {{ textContent: "" }},
          risks: {{ textContent: "" }},
          actions: {{ textContent: "" }},
          draft: {{ value: "" }},
        }};

        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "high",
          summary: "需要核对付款状态。",
          category: "payment",
          analysis_engine: {{ label: "Rule fallback" }},
          decision_brief: {{
            one_line_conclusion: "客户要求确认付款状态，需要先核查再回复。",
            requested_outcome: "对方希望获得汇款状态确认。",
            next_steps: [],
            key_facts: [],
            must_check: [],
            missing_info: [],
            reply_recommendation: {{
              should_reply: true,
              reply_type: "provide_info",
              reason: "客户等待付款状态。",
            }},
            confidence: "medium",
          }},
          risk_flags: [{{ type: "payment_risk", level: "high", evidence: "邮件提到付款或发票。" }}],
          suggested_actions: [
            {{ type: "confirm", description: "请先核对付款、发票或汇款状态，再回复。" }},
            {{ type: "check_inventory" }},
          ],
          reply_draft: {{ body: "Draft body" }},
        }});

        if (fields.priority.textContent !== "高") {{
          throw new Error(`priority label missing: ${{fields.priority.textContent}}`);
        }}
        if (fields.category.textContent !== "付款/发票") {{
          throw new Error(`category label missing: ${{fields.category.textContent}}`);
        }}
        if (fields.engine.textContent !== "Rule fallback") {{
          throw new Error(`engine label missing: ${{fields.engine.textContent}}`);
        }}
        if (fields.risks.textContent.includes("[object Object]")) {{
          throw new Error(`risk text is not readable: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("付款风险")) {{
          throw new Error(`risk label missing: ${{fields.risks.textContent}}`);
        }}
        if (!fields.risks.textContent.includes("高")) {{
          throw new Error(`risk level missing: ${{fields.risks.textContent}}`);
        }}
        if (fields.actions.textContent.includes("[object Object]")) {{
          throw new Error(`action text is not readable: ${{fields.actions.textContent}}`);
        }}
        if (!fields.actions.textContent.includes("请先核对付款、发票或汇款状态，再回复。")) {{
          throw new Error(`action description missing: ${{fields.actions.textContent}}`);
        }}
        if (!fields.actions.textContent.includes("核查库存")) {{
          throw new Error(`action fallback label missing: ${{fields.actions.textContent}}`);
        }}
        fields.category.textContent = context.window.EmailAssistantRender.formatAttachments([
          {{ filename: "Bottle trap Project_Imported.pdf", size: "3.94M", type: "pdf" }},
        ]);
        if (fields.category.textContent !== "Bottle trap Project_Imported.pdf (3.94M, pdf)") {{
          throw new Error(`attachment format missing: ${{fields.category.textContent}}`);
        }}
        context.window.EmailAssistantRender.renderAnalysis(fields, {{
          priority: "normal",
          summary: "这是一封新品开发邮件。",
          category: "new_product_development",
          analysis_engine: {{ label: "Rule fallback" }},
          decision_brief: {{
            one_line_conclusion: "这是一封新品开发邮件，需要先核查项目范围。",
            requested_outcome: "对方希望获得可行性反馈。",
            next_steps: [],
            key_facts: [],
            must_check: [],
            missing_info: [],
            reply_recommendation: {{
              should_reply: true,
              reply_type: "escalate_first",
              reason: "涉及内部评估。",
            }},
            confidence: "medium",
          }},
          risk_flags: [],
          suggested_actions: [],
          reply_draft: {{ body: "Draft body" }},
        }});
        if (fields.category.textContent !== "新品开发/成本优化") {{
          throw new Error(`new product category label missing: ${{fields.category.textContent}}`);
        }}
        """

        result = subprocess.run(
            ["node", "-e", textwrap.dedent(script)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)


if __name__ == "__main__":
    unittest.main()
