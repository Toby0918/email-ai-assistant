"""Behavior tests for the Tencent Exmail content adapter."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "frontend" / "browser_extension" / "content" / "exmail_adapter.js"


class BrowserExtensionBehaviorTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = f"""
        const fs = require("fs");
        const vm = require("vm");
        const adapter = fs.readFileSync({str(ADAPTER)!r}, "utf8");

        class FakeElement {{
          constructor({{ tag = "div", id = "", className = "", role = "", text = "", children = [] }} = {{}}) {{
            this.tagName = tag.toUpperCase();
            this.id = id;
            this.className = className;
            this.role = role;
            this.innerText = text;
            this.textContent = text;
            this.children = children;
            this.parentElement = null;
            this.parentNode = null;
            this.nodeType = 1;
            for (const child of children) {{
              child.parentElement = this;
              child.parentNode = this;
            }}
          }}

          contains(node) {{
            if (node === this) {{
              return true;
            }}
            return this.children.some((child) => child.contains(node));
          }}

          querySelector(selector) {{
            return find(this, selector);
          }}
        }}

        class FakeDocument {{
          constructor({{ title = "", body, selection = null }} = {{}}) {{
            this.title = title;
            this.body = body;
            this.defaultView = {{
              getSelection: () => selection || emptySelection(),
            }};
          }}

          querySelector(selector) {{
            return this.body.querySelector(selector);
          }}
        }}

        function allElements(root) {{
          return [root, ...root.children.flatMap((child) => allElements(child))];
        }}

        function find(root, selector) {{
          return allElements(root).find((element) => matches(element, selector)) || null;
        }}

        function matches(element, selector) {{
          if (selector.startsWith("#")) {{
            return element.id === selector.slice(1);
          }}
          if (selector.startsWith(".")) {{
            return element.className.split(/\\s+/).includes(selector.slice(1));
          }}
          if (selector === "[role='heading']") {{
            return element.role === "heading";
          }}
          return element.tagName.toLowerCase() === selector.toLowerCase();
        }}

        function emptySelection() {{
          return {{
            rangeCount: 0,
            toString: () => "",
            getRangeAt: () => {{
              throw new Error("No range");
            }},
          }};
        }}

        function selection(text, node) {{
          return {{
            rangeCount: 1,
            toString: () => text,
            getRangeAt: () => ({{ commonAncestorContainer: node }}),
          }};
        }}

        function dispatch(doc) {{
          let listener;
          const context = {{
            window: {{ document: doc, frames: [] }},
            document: doc,
            chrome: {{
              runtime: {{
                onMessage: {{
                  addListener: (callback) => {{
                    listener = callback;
                  }},
                }},
              }},
            }},
          }};
          vm.runInNewContext(adapter, context);
          let response;
          listener({{ type: "EXTRACT_CURRENT_EMAIL" }}, {{}}, (value) => {{
            response = value;
          }});
          return response;
        }}

        function legacyReadDocument({{ selected = false, knownBody = false }} = {{}}) {{
          const subject = new FakeElement({{
            tag: "h1",
            id: "subject",
            text: "Re: Urgent Notification",
          }});
          const bodyText = [
            "Re: Urgent Notification",
            "From: customer@example.test",
            "To: quality@example.test",
            "Date: 2026-07-02 09:30",
            "Hi Edward,",
            "Received below complaint.",
            "Please respond within 24 hours of receipt.",
          ].join("\\n");
          const messageBody = new FakeElement({{
            tag: "div",
            className: knownBody ? "mail-content" : "",
            text: bodyText,
          }});
          const body = new FakeElement({{ tag: "body", text: bodyText, children: [subject, messageBody] }});
          return new FakeDocument({{
            title: "Tencent Exmail",
            body,
            selection: selected ? selection("Received below complaint.", messageBody) : null,
          }});
        }}

        function bodySelectorOnlyDocument() {{
          const messageBody = new FakeElement({{
            tag: "div",
            className: "mail-content",
            text: "This should not be accepted without read-message headers.",
          }});
          const body = new FakeElement({{
            tag: "body",
            text: "This should not be accepted without read-message headers.",
            children: [messageBody],
          }});
          return new FakeDocument({{ title: "Tencent Exmail", body }});
        }}

        function attachmentDocument() {{
          const subject = new FakeElement({{
            tag: "h1",
            id: "subject",
            text: "Bottle trap Cost optimisation project-Delifu",
          }});
          const bodyText = [
            "Bottle trap Cost optimisation project-Delifu",
            "From: engineer@example.test",
            "Hi Diana,",
            "Please review the attached project scope.",
            "Attachments (1)",
            "Bottle trap Project_Imported.pdf (3.94M)",
          ].join("\\n");
          const messageBody = new FakeElement({{
            tag: "div",
            className: "mail-content",
            text: bodyText,
          }});
          const body = new FakeElement({{ tag: "body", text: bodyText, children: [subject, messageBody] }});
          return new FakeDocument({{ title: "Tencent Exmail", body }});
        }}

        const cases = {{
          legacy_opened_message_extracts_body: () => {{
            const result = dispatch(legacyReadDocument());
            if (!result.ok) throw new Error(JSON.stringify(result));
            if (!result.payload.body_text.includes("Received below complaint.")) {{
              throw new Error("missing body text");
            }}
          }},
          legacy_selected_text_fallback_extracts_selection: () => {{
            const result = dispatch(legacyReadDocument({{ selected: true }}));
            if (!result.ok) throw new Error(JSON.stringify(result));
            if (result.source !== "selected_text") {{
              throw new Error(`expected selected_text, got ${{result.source}}`);
            }}
            if (result.payload.body_text !== "Received below complaint.") {{
              throw new Error(`unexpected selected text: ${{result.payload.body_text}}`);
            }}
          }},
          selected_text_wins_over_known_dom_body: () => {{
            const result = dispatch(legacyReadDocument({{ selected: true, knownBody: true }}));
            if (!result.ok) throw new Error(JSON.stringify(result));
            if (result.source !== "selected_text") {{
              throw new Error(`expected selected_text, got ${{result.source}}`);
            }}
            if (result.payload.body_text !== "Received below complaint.") {{
              throw new Error(`expected selected text only, got ${{result.payload.body_text}}`);
            }}
          }},
          selected_text_keeps_opened_message_metadata: () => {{
            const result = dispatch(legacyReadDocument({{ selected: true, knownBody: true }}));
            if (!result.ok) throw new Error(JSON.stringify(result));
            if (result.payload.subject !== "Re: Urgent Notification") {{
              throw new Error(`unexpected subject: ${{result.payload.subject}}`);
            }}
            if (result.payload.from !== "customer@example.test") {{
              throw new Error(`unexpected from: ${{result.payload.from}}`);
            }}
            if (result.payload.to[0] !== "quality@example.test") {{
              throw new Error(`unexpected to: ${{result.payload.to}}`);
            }}
            if (result.payload.sent_at !== "2026-07-02 09:30") {{
              throw new Error(`unexpected date: ${{result.payload.sent_at}}`);
            }}
            if (result.payload.body_text !== "Received below complaint.") {{
              throw new Error(`expected selected body only, got ${{result.payload.body_text}}`);
            }}
          }},
          body_selector_alone_is_not_message_context: () => {{
            const result = dispatch(bodySelectorOnlyDocument());
            if (result.ok) throw new Error("body selector alone should not extract");
          }},
          opened_message_extracts_attachment_metadata: () => {{
            const result = dispatch(attachmentDocument());
            if (!result.ok) throw new Error(JSON.stringify(result));
            if (!Array.isArray(result.payload.attachments) || result.payload.attachments.length !== 1) {{
              throw new Error(`expected one attachment, got ${{JSON.stringify(result.payload.attachments)}}`);
            }}
            const attachment = result.payload.attachments[0];
            if (attachment.filename !== "Bottle trap Project_Imported.pdf") {{
              throw new Error(`unexpected filename: ${{attachment.filename}}`);
            }}
            if (attachment.size !== "3.94M") {{
              throw new Error(`unexpected size: ${{attachment.size}}`);
            }}
            if (attachment.type !== "pdf") {{
              throw new Error(`unexpected type: ${{attachment.type}}`);
            }}
          }},
        }};

        cases[{case_name!r}]();
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

    def test_legacy_opened_message_extracts_body(self) -> None:
        self.run_node_case("legacy_opened_message_extracts_body")

    def test_legacy_selected_text_fallback_extracts_selection(self) -> None:
        self.run_node_case("legacy_selected_text_fallback_extracts_selection")

    def test_selected_text_wins_over_known_dom_body(self) -> None:
        self.run_node_case("selected_text_wins_over_known_dom_body")

    def test_selected_text_keeps_opened_message_metadata(self) -> None:
        self.run_node_case("selected_text_keeps_opened_message_metadata")

    def test_body_selector_alone_is_not_message_context(self) -> None:
        self.run_node_case("body_selector_alone_is_not_message_context")

    def test_opened_message_extracts_attachment_metadata(self) -> None:
        self.run_node_case("opened_message_extracts_attachment_metadata")


if __name__ == "__main__":
    unittest.main()
