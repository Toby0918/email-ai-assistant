"""Focused behavior tests for the Task 6 content-adapter integration."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "frontend" / "browser_extension" / "content" / "exmail_adapter.js"


class BrowserExtensionTask6AdapterTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__ADAPTER_PATH__, "utf8");

            class FakeElement {
              constructor({ tag = "div", id = "", className = "", role = "", text = "",
                            children = [], attrs = {}, hidden = false, style = {} } = {}) {
                this.tagName = tag.toUpperCase();
                this.id = id;
                this.className = className;
                this.role = role;
                this.innerText = text;
                this.textContent = text;
                this.children = children;
                this.attrs = { ...attrs };
                this.hidden = hidden;
                this.style = style;
                this.nodeType = 1;
                this.parentElement = null;
                this.parentNode = null;
                for (const child of children) {
                  child.parentElement = this;
                  child.parentNode = this;
                }
              }
              contains(node) {
                return node === this || this.children.some((child) => child.contains(node));
              }
              getAttribute(name) {
                if (name === "id") return this.id || null;
                if (name === "class") return this.className || null;
                if (name === "role") return this.role || null;
                return Object.prototype.hasOwnProperty.call(this.attrs, name) ? String(this.attrs[name]) : null;
              }
              hasAttribute(name) {
                return (name === "hidden" && this.hidden) || Object.prototype.hasOwnProperty.call(this.attrs, name);
              }
              querySelector(selector) {
                return allElements(this).find((element) => matches(element, selector)) || null;
              }
            }

            class FakeDocument {
              constructor(body, title = "Tencent Exmail") {
                this.body = body;
                this.title = title;
                this.defaultView = { getSelection: () => emptySelection() };
              }
              querySelector(selector) {
                return this.body.querySelector(selector);
              }
            }

            function allElements(root) {
              return [root, ...root.children.flatMap((child) => allElements(child))];
            }
            function matches(element, selector) {
              if (selector.startsWith("#")) return element.id === selector.slice(1);
              if (selector.startsWith(".")) return element.className.split(/\s+/).includes(selector.slice(1));
              if (selector === "[role='heading']") return element.role === "heading";
              return element.tagName.toLowerCase() === selector.toLowerCase();
            }
            function emptySelection() {
              return { rangeCount: 0, toString: () => "", getRangeAt: () => { throw new Error("No range"); } };
            }
            function openedMessage(backgroundText = "") {
              const subject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic request" });
              const messageText = [
                "Synthetic request", "From: sender@example.test", "To: recipient@example.test",
                "Date: 2026-07-11 10:00", "Please review the visible message.",
              ].join("\n");
              const currentRoot = new FakeElement({ className: "mail-content", text: messageText });
              const body = new FakeElement({
                tag: "body", text: [messageText, backgroundText].filter(Boolean).join("\n"),
                children: [subject, currentRoot],
              });
              return { doc: new FakeDocument(body), currentRoot };
            }
            function mailboxDocument() {
              return new FakeDocument(new FakeElement({ tag: "body", text: "Mailbox navigation" }));
            }

            function loadAdapter(doc, collector, frames = []) {
              let listener;
              const rootWindow = { document: doc, frames };
              if (collector) rootWindow.EmailAssistantCurrentMessageCollector = collector;
              const context = {
                window: rootWindow,
                document: doc,
                chrome: { runtime: { onMessage: { addListener: (callback) => { listener = callback; } } } },
              };
              vm.runInNewContext(source, context, { filename: "exmail_adapter.js" });
              return listener;
            }

            function beginDispatch(listener, message = { type: "EXTRACT_CURRENT_EMAIL" }) {
              let response;
              let resolveResponse;
              const responsePromise = new Promise((resolve) => { resolveResponse = resolve; });
              const keepAlive = listener(message, {}, (value) => {
                response = value;
                resolveResponse(value);
              });
              return { keepAlive, response: () => response, responsePromise };
            }
            function assertExactKeys(value, expected, label) {
              const actual = Object.keys(value).sort();
              const wanted = [...expected].sort();
              if (JSON.stringify(actual) !== JSON.stringify(wanted)) {
                throw new Error(`${label} keys: ${JSON.stringify(actual)}`);
              }
            }

            const cases = {
              collection_is_async_bounded_and_message_dispatched: async () => {
                const { doc, currentRoot } = openedMessage("background-private.pdf (4 KB)");
                let extractCalls = 0;
                let collectCalls = 0;
                let releaseCollection;
                const gate = new Promise((resolve) => { releaseCollection = resolve; });
                const collector = {
                  extractVisibleThreadSegments: (receivedDoc, options) => {
                    extractCalls += 1;
                    if (receivedDoc !== doc || options.currentMessageRoot !== currentRoot) {
                      throw new Error("collector did not receive the verified current-message root");
                    }
                    return [
                      { position: 0, from: "a@example.test", to: "b@example.test", sent_at: "",
                        timestamp_text: "Yesterday", subject: "Synthetic", body_text: "First visible segment" },
                      { position: 1, from: "b@example.test", to: "a@example.test", sent_at: "",
                        timestamp_text: "Today", subject: "Re: Synthetic", body_text: "Second visible segment" },
                    ];
                  },
                  collectVisibleResources: async (receivedDoc, options) => {
                    collectCalls += 1;
                    if (receivedDoc !== doc || options.currentMessageRoot !== currentRoot) {
                      throw new Error("resource collection escaped the verified root");
                    }
                    await gate;
                    return {
                      attachment_files: [{ filename: "visible.pdf", type: "pdf", size: 3, content_base64: "AQID" }],
                      resource_limitations: [{ filename: "limited.docx", type: "docx", size: 0,
                        limitation: "Resource could not be read from the current Tencent Exmail session." }],
                    };
                  },
                };
                const listener = loadAdapter(doc, collector);
                if (extractCalls !== 0 || collectCalls !== 0) throw new Error("collection ran at module load");
                if (listener({ type: "IGNORED" }, {}, () => {}) !== false) throw new Error("ignored message was handled");
                if (extractCalls !== 0 || collectCalls !== 0) throw new Error("collection ran for another message type");

                const pending = beginDispatch(listener);
                if (pending.keepAlive !== true) throw new Error(`expected async listener return true, got ${pending.keepAlive}`);
                if (pending.response() !== undefined) throw new Error("adapter responded before resource bytes completed");
                if (extractCalls !== 1 || collectCalls !== 1) throw new Error("collector was not called exactly once");
                releaseCollection();
                const result = await pending.responsePromise;
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (result.payload.thread_segments.length !== 2) throw new Error("expected two visible thread segments");
                if (result.payload.attachment_files[0].content_base64 !== "AQID") throw new Error("attachment bytes missing");
                assertExactKeys(result.payload.attachment_files[0], ["filename", "type", "size", "content_base64"], "file");
                assertExactKeys(result.payload.resource_limitations[0], ["filename", "type", "size", "limitation"], "limitation");
                if (result.payload.attachments.some((item) => item.filename.includes("background-private"))) {
                  throw new Error("background attachment metadata escaped the current root");
                }
              },

              collector_absence_keeps_body_analysis_safe: async () => {
                const { doc } = openedMessage();
                const pending = beginDispatch(loadAdapter(doc, null));
                if (pending.keepAlive !== true) throw new Error("missing collector response was not asynchronous");
                const result = await pending.responsePromise;
                if (!result.ok || !result.payload.body_text.includes("visible message")) throw new Error(JSON.stringify(result));
                if (result.payload.thread_segments.length || result.payload.attachment_files.length) {
                  throw new Error("missing collector emitted collected data");
                }
                if (result.payload.resource_limitations.length !== 1) throw new Error("missing safe collector limitation");
                assertExactKeys(result.payload.resource_limitations[0], ["filename", "type", "size", "limitation"], "limitation");
              },

              collector_failure_keeps_body_analysis_safe: async () => {
                const { doc } = openedMessage();
                const collector = {
                  extractVisibleThreadSegments: () => [],
                  collectVisibleResources: async () => { throw new Error("private fetch detail"); },
                };
                const result = await beginDispatch(loadAdapter(doc, collector)).responsePromise;
                if (!result.ok || !result.payload.body_text.includes("visible message")) throw new Error(JSON.stringify(result));
                if (result.payload.attachment_files.length !== 0) throw new Error("failed collection emitted bytes");
                const serialized = JSON.stringify(result.payload.resource_limitations);
                if (!serialized.includes("could not be collected") || serialized.includes("private fetch detail")) {
                  throw new Error(`unsafe failure response: ${serialized}`);
                }
              },

              hidden_frame_message_is_not_extracted: async () => {
                const topDoc = mailboxDocument();
                const { doc: hiddenDoc } = openedMessage();
                const frameElement = new FakeElement({ tag: "iframe", attrs: { "aria-hidden": "true" } });
                const hiddenWindow = { document: hiddenDoc, frames: [], frameElement };
                const pending = beginDispatch(loadAdapter(topDoc, null, [hiddenWindow]));
                if (pending.keepAlive !== true) throw new Error("extraction response was not asynchronous");
                const result = await pending.responsePromise;
                if (result.ok) throw new Error("hidden frame message was extracted");
              },
            };

            (async () => {
              const caseName = __CASE_NAME__;
              await cases[caseName]();
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        )
        script = script.replace("__ADAPTER_PATH__", json.dumps(str(ADAPTER)))
        script = script.replace("__CASE_NAME__", json.dumps(case_name))
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_collection_is_async_bounded_and_message_dispatched(self) -> None:
        self.run_node_case("collection_is_async_bounded_and_message_dispatched")

    def test_collector_absence_keeps_body_analysis_safe(self) -> None:
        self.run_node_case("collector_absence_keeps_body_analysis_safe")

    def test_collector_failure_keeps_body_analysis_safe(self) -> None:
        self.run_node_case("collector_failure_keeps_body_analysis_safe")

    def test_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("hidden_frame_message_is_not_extracted")


if __name__ == "__main__":
    unittest.main()
