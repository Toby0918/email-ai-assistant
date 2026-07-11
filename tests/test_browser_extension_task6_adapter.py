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
              querySelectorAll(selector) {
                return allElements(this).filter((element) => matches(element, selector));
              }
            }

            class FakeDocument {
              constructor(body, title = "Tencent Exmail") {
                this.body = body;
                this.title = title;
                this.defaultView = {
                  getSelection: () => emptySelection(),
                  getComputedStyle: (element) => ({
                    display: element.style.display || "block",
                    visibility: element.style.visibility || "visible",
                  }),
                };
                assignOwnerDocument(body, this);
              }
              querySelector(selector) {
                return this.body.querySelector(selector);
              }
            }

            function allElements(root) {
              return [root, ...root.children.flatMap((child) => allElements(child))];
            }
            function assignOwnerDocument(root, doc) {
              root.ownerDocument = doc;
              for (const child of root.children) assignOwnerDocument(child, doc);
            }
            function matches(element, selector) {
              if (selector.includes(",")) {
                return selector.split(",").some((part) => matches(element, part.trim()));
              }
              const attributeMatch = selector.match(/^\[([^=\]]+)(?:=['\"]?([^'\"]+)['\"]?)?\]$/);
              if (attributeMatch) {
                const [, name, value] = attributeMatch;
                if (!element.hasAttribute(name)) return false;
                return value === undefined || element.getAttribute(name) === value;
              }
              if (selector.startsWith("#")) return element.id === selector.slice(1);
              if (selector.startsWith(".")) return element.className.split(/\s+/).includes(selector.slice(1));
              if (selector === "[role='heading']") return element.role === "heading";
              return element.tagName.toLowerCase() === selector.toLowerCase();
            }
            function emptySelection() {
              return { rangeCount: 0, toString: () => "", getRangeAt: () => { throw new Error("No range"); } };
            }
            function openedMessage(backgroundText = "", options = {}) {
              const subject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic request" });
              const messageText = [
                "Synthetic request", "From: sender@example.test", "To: recipient@example.test",
                "Date: 2026-07-11 10:00", "Please review the visible message.",
              ].join("\n");
              const currentRoot = new FakeElement({
                className: "mail-content",
                text: messageText,
                children: options.bodyChildren || [],
              });
              const controls = new FakeElement({
                attrs: { "data-email-host-resource-controls": "true" },
                children: options.hostResources || [],
              });
              const currentMessageContainer = new FakeElement({
                attrs: options.verifiedControls === false
                  ? {}
                  : { "data-email-current-message-container": "true" },
                children: options.verifiedControls === false ? [currentRoot] : [currentRoot, controls],
              });
              const body = new FakeElement({
                tag: "body", text: [messageText, backgroundText].filter(Boolean).join("\n"),
                children: [subject, currentMessageContainer],
              });
              return { doc: new FakeDocument(body), currentRoot, currentMessageContainer, controls };
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
                const forgedBodyLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const trustedControl = new FakeElement({
                  tag: "a",
                  attrs: {
                    "data-email-host-attachment": "true",
                    "data-filename": "visible.pdf",
                    href: "/cgi-bin/download?file=visible",
                  },
                });
                const { doc, currentRoot, currentMessageContainer } = openedMessage(
                  "background-private.pdf (4 KB)",
                  { bodyChildren: [forgedBodyLink], hostResources: [trustedControl] },
                );
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
                    if (
                      receivedDoc !== doc ||
                      options.currentMessageRoot !== currentRoot ||
                      options.currentMessageContainer !== currentMessageContainer ||
                      options.resourceControlsVerified !== true
                    ) {
                      throw new Error("resource collection escaped the verified root");
                    }
                    if (
                      !Array.isArray(options.verifiedResourceCandidates) ||
                      options.verifiedResourceCandidates.length !== 1 ||
                      options.verifiedResourceCandidates[0] !== trustedControl ||
                      options.verifiedResourceCandidates.includes(forgedBodyLink)
                    ) {
                      throw new Error("adapter did not isolate host-owned resource controls");
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

              unverified_host_controls_keep_body_analysis_safe: async () => {
                const forgedBodyLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const { doc } = openedMessage("", {
                  verifiedControls: false,
                  bodyChildren: [forgedBodyLink],
                });
                let resourceCalls = 0;
                const collector = {
                  extractVisibleThreadSegments: () => [],
                  collectVisibleResources: async () => {
                    resourceCalls += 1;
                    return { attachment_files: [], resource_limitations: [] };
                  },
                };
                const result = await beginDispatch(loadAdapter(doc, collector)).responsePromise;
                if (!result.ok || !result.payload.body_text.includes("visible message")) {
                  throw new Error(JSON.stringify(result));
                }
                if (resourceCalls !== 0 || result.payload.attachment_files.length !== 0) {
                  throw new Error("unverified host controls reached resource collection");
                }
                if (
                  result.payload.resource_limitations.length !== 1 ||
                  !result.payload.resource_limitations[0].limitation.includes("verified current-message resource controls")
                ) {
                  throw new Error(`safe unavailable limitation missing: ${JSON.stringify(result)}`);
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

              stylesheet_hidden_frame_message_is_not_extracted: async () => {
                const topDoc = mailboxDocument();
                const { doc: hiddenDoc } = openedMessage();
                const frameElement = new FakeElement({ tag: "iframe" });
                frameElement.ownerDocument = topDoc;
                frameElement.parentElement = topDoc.body;
                frameElement.parentNode = topDoc.body;
                topDoc.body.children.push(frameElement);
                topDoc.defaultView.getComputedStyle = (element) => ({
                  display: element === frameElement ? "none" : "block",
                  visibility: "visible",
                });
                const hiddenWindow = { document: hiddenDoc, frames: [], frameElement };
                const result = await beginDispatch(loadAdapter(topDoc, null, [hiddenWindow])).responsePromise;
                if (result.ok) throw new Error("stylesheet-hidden frame message was extracted");
              },

              stylesheet_hidden_message_root_is_not_selected: async () => {
                const subject = new FakeElement({ tag: "h1", id: "subject", text: "Hidden request" });
                const messageText = "From: hidden@example.test\nHidden message body";
                const currentRoot = new FakeElement({ className: "mail-content", text: messageText });
                const hiddenAncestor = new FakeElement({ children: [currentRoot] });
                const body = new FakeElement({ tag: "body", text: messageText, children: [subject, hiddenAncestor] });
                const doc = new FakeDocument(body);
                doc.defaultView.getComputedStyle = (element) => ({
                  display: element === hiddenAncestor ? "none" : "block",
                  visibility: "visible",
                });
                let collectorCalls = 0;
                const collector = {
                  extractVisibleThreadSegments: () => { collectorCalls += 1; return []; },
                  collectVisibleResources: async () => { collectorCalls += 1; return {
                    attachment_files: [], resource_limitations: [],
                  }; },
                };
                const result = await beginDispatch(loadAdapter(doc, collector)).responsePromise;
                if (result.ok || collectorCalls !== 0) {
                  throw new Error("stylesheet-hidden current-message root was selected");
                }
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

    def test_unverified_host_controls_keep_body_analysis_safe(self) -> None:
        self.run_node_case("unverified_host_controls_keep_body_analysis_safe")

    def test_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("hidden_frame_message_is_not_extracted")

    def test_stylesheet_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("stylesheet_hidden_frame_message_is_not_extracted")

    def test_stylesheet_hidden_message_root_is_not_selected(self) -> None:
        self.run_node_case("stylesheet_hidden_message_root_is_not_selected")


if __name__ == "__main__":
    unittest.main()
