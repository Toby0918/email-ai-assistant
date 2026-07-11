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
COLLECTOR = (
    ROOT
    / "frontend"
    / "browser_extension"
    / "content"
    / "current_message_collector.js"
)


class BrowserExtensionTask6AdapterTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__ADAPTER_PATH__, "utf8");
            const collectorSource = fs.readFileSync(__COLLECTOR_PATH__, "utf8");

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
                return this.querySelectorAll(selector)[0] || null;
              }
              querySelectorAll(selector) {
                return this.children
                  .flatMap((child) => allElements(child))
                  .filter((element) => matches(element, selector));
              }
            }

            class FakeDocument {
              constructor(body, title = "Tencent Exmail") {
                this.body = body;
                this.title = title;
                this.baseURI = "https://exmail.qq.com/cgi-bin/readmail";
                this.location = new URL(this.baseURI);
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
              const headerText = [
                "From: sender@example.test", "To: recipient@example.test", "Date: 2026-07-11 10:00",
              ].join("\n");
              const bodyText = "Please review the visible message.";
              const messageText = ["Synthetic request", headerText, bodyText].join("\n");
              const header = new FakeElement({ className: "read-header", text: headerText });
              const currentRoot = new FakeElement({
                className: "mail-content",
                text: bodyText,
                children: options.bodyChildren || [],
              });
              const controls = new FakeElement({
                className: "resource-region",
                children: options.hostResources || [],
              });
              const additionalBodies = options.additionalBodies || [];
              const currentMessageContainer = new FakeElement({
                className: "read-envelope",
                children: options.verifiedControls === false
                  ? [subject, currentRoot, controls]
                  : [subject, header, currentRoot, ...additionalBodies, controls],
              });
              const body = new FakeElement({
                tag: "body", text: [messageText, backgroundText].filter(Boolean).join("\n"),
                children: [currentMessageContainer, ...(options.envelopeExternal || [])],
              });
              return { doc: new FakeDocument(body), currentRoot, currentMessageContainer, controls, header, subject };
            }
            function mailboxDocument() {
              return new FakeDocument(new FakeElement({ tag: "body", text: "Mailbox navigation" }));
            }

            function loadAdapter(doc, collector, frames = []) {
              let listener;
              const rootWindow = { document: doc, frames };
              if (collector) rootWindow.EmailAssistantCurrentMessageCollector = collector;
              const context = {
                URL,
                window: rootWindow,
                document: doc,
                chrome: { runtime: { onMessage: { addListener: (callback) => { listener = callback; } } } },
              };
              vm.runInNewContext(source, context, { filename: "exmail_adapter.js" });
              return listener;
            }

            function loadAdapterWithRealCollector(doc, fetchImpl) {
              let listener;
              const rootWindow = {
                document: doc,
                frames: [],
                fetch: fetchImpl,
                AbortController,
                setTimeout,
                clearTimeout,
                btoa: (binary) => Buffer.from(binary, "binary").toString("base64"),
              };
              const context = {
                URL,
                Uint8Array,
                ArrayBuffer,
                AbortController,
                setTimeout,
                clearTimeout,
                window: rootWindow,
                document: doc,
                chrome: { runtime: { onMessage: { addListener: (callback) => { listener = callback; } } } },
              };
              vm.runInNewContext(collectorSource, context, { filename: "current_message_collector.js" });
              vm.runInNewContext(source, context, { filename: "exmail_adapter.js" });
              return listener;
            }

            function oneByteResponse() {
              let delivered = false;
              const reader = {
                read: async () => {
                  if (delivered) return { done: true, value: undefined };
                  delivered = true;
                  return { done: false, value: Uint8Array.from([1]) };
                },
                cancel: async () => {},
                releaseLock: () => {},
              };
              return {
                ok: true,
                redirected: false,
                headers: { get: (name) => name.toLowerCase() === "content-length" ? "1" : null },
                body: { getReader: () => reader },
              };
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
                    download: "visible.pdf",
                    href: "/cgi-bin/download?file=visible",
                  },
                });
                const externalControl = new FakeElement({
                  tag: "a",
                  attrs: { download: "external.pdf", href: "/cgi-bin/download?file=external" },
                });
                const { doc, currentRoot, currentMessageContainer } = openedMessage(
                  "background-private.pdf (4 KB)",
                  {
                    bodyChildren: [forgedBodyLink],
                    hostResources: [trustedControl],
                    envelopeExternal: [externalControl],
                  },
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
                      resource_limitations: [{ code: "resource_read_failed", filename: "limited.docx", type: "docx", size: 0,
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
                assertExactKeys(result.payload.resource_limitations[0], ["code", "filename", "type", "size", "limitation"], "limitation");
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
                assertExactKeys(result.payload.resource_limitations[0], ["code", "filename", "type", "size", "limitation"], "limitation");
              },

              collector_failure_keeps_body_analysis_safe: async () => {
                const control = new FakeElement({
                  tag: "a",
                  attrs: { download: "visible.pdf", href: "/cgi-bin/download?file=visible" },
                });
                const { doc } = openedMessage("", { hostResources: [control] });
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

              nested_known_body_container_fails_closed_with_real_collector: async () => {
                const subjectText = "Synthetic nested request";
                const headerText = "From: sender@example.test\nTo: recipient@example.test";
                const bodyText = "Please review the nested visible message.";
                const subject = new FakeElement({ tag: "h1", id: "subject", text: subjectText });
                const header = new FakeElement({ className: "read-header", text: headerText });
                const currentRoot = new FakeElement({ id: "mailContentContainer", text: bodyText });
                const forgedLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const outerKnownBody = new FakeElement({
                  className: "mail-content",
                  text: `${subjectText}\n${headerText}\n${bodyText}`,
                  children: [subject, header, currentRoot, forgedLink],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: `${subjectText}\n${headerText}\n${bodyText}`,
                  children: [outerKnownBody],
                }));
                let fetchCount = 0;
                const listener = loadAdapterWithRealCollector(doc, async () => {
                  fetchCount += 1;
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (!result.ok || !result.payload.body_text.includes("nested visible message")) {
                  throw new Error(`body analysis did not continue: ${JSON.stringify(result)}`);
                }
                if (fetchCount !== 0 || result.payload.attachment_files.length !== 0) {
                  throw new Error(
                    `nested known-body link escaped trust boundary: fetch=${fetchCount} ` +
                    `files=${result.payload.attachment_files.length}`,
                  );
                }
                if (
                  result.payload.resource_limitations.length !== 1 ||
                  result.payload.resource_limitations[0].code !== "resource_unavailable"
                ) {
                  throw new Error(`single unavailable limitation missing: ${JSON.stringify(result)}`);
                }
              },

              invalid_structural_envelopes_and_endpoints_fail_closed: async () => {
                let resourceCalls = 0;
                const collector = {
                  extractVisibleThreadSegments: () => [],
                  collectVisibleResources: async () => {
                    resourceCalls += 1;
                    return { attachment_files: [], resource_limitations: [] };
                  },
                };
                const validControl = () => new FakeElement({
                  tag: "a",
                  attrs: { download: "visible.pdf", href: "/cgi-bin/download?file=visible" },
                });
                const cases = [];

                const bodyLevelSubject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic request" });
                const bodyLevelHeader = new FakeElement({
                  text: "From: sender@example.test\nTo: recipient@example.test",
                });
                const bodyLevelMessage = new FakeElement({
                  className: "mail-content", text: "Please review the visible message.",
                });
                const bodyLevelControls = new FakeElement({ children: [validControl()] });
                cases.push(new FakeDocument(new FakeElement({
                  tag: "body",
                  text: "Synthetic request\nFrom: sender@example.test\nTo: recipient@example.test\nPlease review the visible message.",
                  children: [bodyLevelSubject, bodyLevelHeader, bodyLevelMessage, bodyLevelControls],
                })));

                const duplicateBody = new FakeElement({
                  className: "mail-content", text: "Second ambiguous visible message body.",
                });
                cases.push(openedMessage("", {
                  additionalBodies: [duplicateBody], hostResources: [validControl()],
                }).doc);
                cases.push(openedMessage("", { hostResources: [new FakeElement({
                  tag: "a", hidden: true,
                  attrs: { download: "hidden.pdf", href: "/cgi-bin/download?file=hidden" },
                })] }).doc);
                cases.push(openedMessage("", { hostResources: [new FakeElement({
                  tag: "a",
                  attrs: { download: "remote.pdf", href: "https://remote.example/download?file=remote" },
                })] }).doc);
                cases.push(openedMessage("", { hostResources: [new FakeElement({
                  tag: "a", attrs: { download: "no-query.pdf", href: "/cgi-bin/download" },
                })] }).doc);

                for (const doc of cases) {
                  const result = await beginDispatch(loadAdapter(doc, collector)).responsePromise;
                  if (!result.ok || result.payload.attachment_files.length !== 0) {
                    throw new Error(`body analysis did not continue safely: ${JSON.stringify(result)}`);
                  }
                  if (
                    result.payload.resource_limitations.length !== 1 ||
                    !result.payload.resource_limitations[0].limitation.includes("verified current-message resource controls")
                  ) {
                    throw new Error(`single unavailable limitation missing: ${JSON.stringify(result)}`);
                  }
                }
                if (resourceCalls !== 0) {
                  throw new Error(`invalid structural mapping reached collection ${resourceCalls} times`);
                }
              },

              metadata_revalidation_never_collects_resources: async () => {
                const { doc } = openedMessage();
                let collectorCalls = 0;
                const collector = {
                  extractVisibleThreadSegments: () => { collectorCalls += 1; return []; },
                  collectVisibleResources: async () => {
                    collectorCalls += 1;
                    return { attachment_files: [], resource_limitations: [] };
                  },
                };
                const pending = beginDispatch(
                  loadAdapter(doc, collector),
                  { type: "REVALIDATE_CURRENT_EMAIL" },
                );
                if (pending.keepAlive !== true) {
                  throw new Error("metadata revalidation message was not handled asynchronously");
                }
                const result = await pending.responsePromise;
                if (collectorCalls !== 0) throw new Error("metadata revalidation collected resources");
                assertExactKeys(result, ["ok", "message_fingerprint"], "revalidation response");
                if (!result.ok || !/^msg-v1-[a-f0-9]{16}$/.test(result.message_fingerprint)) {
                  throw new Error(`unsafe fingerprint response: ${JSON.stringify(result)}`);
                }
                const serialized = JSON.stringify(result);
                for (const forbidden of ["Synthetic request", "sender@example.test", "visible message"]) {
                  if (serialized.includes(forbidden)) throw new Error(`raw message metadata leaked: ${forbidden}`);
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
        script = script.replace("__COLLECTOR_PATH__", json.dumps(str(COLLECTOR)))
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

    def test_nested_known_body_container_fails_closed_with_real_collector(self) -> None:
        self.run_node_case("nested_known_body_container_fails_closed_with_real_collector")

    def test_invalid_structural_envelopes_and_endpoints_fail_closed(self) -> None:
        self.run_node_case("invalid_structural_envelopes_and_endpoints_fail_closed")

    def test_metadata_revalidation_never_collects_resources(self) -> None:
        self.run_node_case("metadata_revalidation_never_collects_resources")

    def test_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("hidden_frame_message_is_not_extracted")

    def test_stylesheet_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("stylesheet_hidden_frame_message_is_not_extracted")

    def test_stylesheet_hidden_message_root_is_not_selected(self) -> None:
        self.run_node_case("stylesheet_hidden_message_root_is_not_selected")


if __name__ == "__main__":
    unittest.main()
