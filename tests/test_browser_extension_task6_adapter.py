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
VISIBLE_CONTEXT = ROOT / "frontend" / "browser_extension" / "content" / "exmail_visible_context.js"
COLLECTOR = (
    ROOT
    / "frontend"
    / "browser_extension"
    / "content"
    / "current_message_collector.js"
)
CLASSIFIER = (
    ROOT
    / "frontend"
    / "browser_extension"
    / "content"
    / "exmail_visible_resource_classifier.js"
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
            const classifierSource = fs.readFileSync(__CLASSIFIER_PATH__, "utf8");
            const visibleContextSource = fs.existsSync(__VISIBLE_CONTEXT_PATH__)
              ? fs.readFileSync(__VISIBLE_CONTEXT_PATH__, "utf8")
              : "";

            class FakeElement {
              constructor({ tag = "div", id = "", className = "", role = "", text = "",
                            children = [], attrs = {}, hidden = false, style = {}, rect = {} } = {}) {
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
                this.rect = {
                  left: 0,
                  top: 0,
                  right: 100,
                  bottom: 20,
                  width: 100,
                  height: 20,
                  ...rect,
                };
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
              getBoundingClientRect() {
                return { ...this.rect };
              }
            }

            class FakeDocument {
              constructor(body, title = "Tencent Exmail") {
                this.body = body;
                this.title = title;
                this.baseURI = "https://exmail.qq.com/cgi-bin/readmail";
                this.location = new URL(this.baseURI);
                this.defaultView = {
                  innerWidth: 1280,
                  innerHeight: 720,
                  getSelection: () => emptySelection(),
                  getComputedStyle: (element) => ({
                    display: element.style.display || "block",
                    visibility: element.style.visibility || "visible",
                    opacity: element.style.opacity === undefined ? "1" : String(element.style.opacity),
                  }),
                };
                assignOwnerDocument(body, this);
              }
              querySelector(selector) {
                return this.body.querySelector(selector);
              }
              querySelectorAll(selector) {
                return allElements(this.body).filter((element) => matches(element, selector));
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
                children: [
                  ...(options.bodyChildren || []),
                  ...(options.explicitCurrentBody ? [new FakeElement({
                    className: "mail-current-body",
                    text: bodyText,
                    children: options.currentBodyChildren || [],
                  })] : []),
                ],
              });
              const controls = new FakeElement({
                className: "resource-region",
                children: options.hostResources || [],
              });
              const additionalBodies = options.additionalBodies || [];
              const currentMessageContainer = new FakeElement({
                className: "read-envelope",
                children: [subject, header, currentRoot, ...additionalBodies, controls],
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
              if (visibleContextSource) {
                vm.runInNewContext(visibleContextSource, context, { filename: "exmail_visible_context.js" });
              }
              vm.runInNewContext(source, context, { filename: "exmail_adapter.js" });
              return listener;
            }

            function loadAdapterWithRealCollector(doc, fetchImpl, frames = []) {
              let listener;
              const rootWindow = {
                document: doc,
                frames,
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
              if (visibleContextSource) {
                vm.runInNewContext(visibleContextSource, context, { filename: "exmail_visible_context.js" });
              }
              vm.runInNewContext(classifierSource, context, {
                filename: "exmail_visible_resource_classifier.js",
              });
              vm.runInNewContext(collectorSource, context, { filename: "current_message_collector.js" });
              vm.runInNewContext(source, context, { filename: "exmail_adapter.js" });
              return listener;
            }

            function loadAdapterWithInjectedVerifiedContext(doc, fetchImpl, verifiedContext) {
              let listener;
              const rootWindow = {
                document: doc,
                frames: [],
                fetch: fetchImpl,
                AbortController,
                setTimeout,
                clearTimeout,
                btoa: (binary) => Buffer.from(binary, "binary").toString("base64"),
                EmailAssistantExmailVisibleContext: {
                  resolveVerifiedDocumentContext: () => verifiedContext,
                  revalidateVerifiedDocumentContext: (_root, context) => context === verifiedContext,
                },
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
              vm.runInNewContext(classifierSource, context, {
                filename: "exmail_visible_resource_classifier.js",
              });
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

            function pdfResponse() {
              const bytes = Uint8Array.from([0x25, 0x50, 0x44, 0x46, 0x2d, 0x31]);
              let delivered = false;
              const reader = {
                read: async () => {
                  if (delivered) return { done: true, value: undefined };
                  delivered = true;
                  return { done: false, value: bytes };
                },
                cancel: async () => {},
                releaseLock: () => {},
              };
              return {
                ok: true,
                redirected: false,
                headers: { get: (name) => {
                  if (name.toLowerCase() === "content-length") return String(bytes.length);
                  if (name.toLowerCase() === "content-type") return "application/pdf";
                  return null;
                } },
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
                      options.verifiedDocument !== doc ||
                      options.verifiedDocumentContext !== true ||
                      typeof options.revalidateContext !== "function" ||
                      options.revalidateContext() !== true ||
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
                const currentRoot = new FakeElement({
                  id: "mailContentContainer", text: bodyText,
                  children: [new FakeElement({ className: "mail-current-body", text: bodyText })],
                });
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

              unknown_intermediate_body_wrapper_fails_closed_with_real_collector: async () => {
                const subjectText = "Synthetic wrapped request";
                const headerText = "From: sender@example.test\nTo: recipient@example.test";
                const bodyText = "Please review the wrapped visible message.";
                const subject = new FakeElement({ tag: "h1", id: "subject", text: subjectText });
                const header = new FakeElement({ className: "read-header", text: headerText });
                const currentRoot = new FakeElement({
                  id: "mailContentContainer", text: bodyText,
                  children: [new FakeElement({ className: "mail-current-body", text: bodyText })],
                });
                const forgedLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const unknownBodyWrapper = new FakeElement({
                  className: "unknown-message-wrapper",
                  children: [currentRoot, forgedLink],
                });
                const structuralEnvelope = new FakeElement({
                  className: "read-envelope",
                  text: `${subjectText}\n${headerText}\n${bodyText}`,
                  children: [subject, header, unknownBodyWrapper],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: `${subjectText}\n${headerText}\n${bodyText}`,
                  children: [structuralEnvelope],
                }));
                let fetchCount = 0;
                const listener = loadAdapterWithRealCollector(doc, async () => {
                  fetchCount += 1;
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (!result.ok || !result.payload.body_text.includes("wrapped visible message")) {
                  throw new Error(`body analysis did not continue: ${JSON.stringify(result)}`);
                }
                if (fetchCount !== 0 || result.payload.attachment_files.length !== 0) {
                  throw new Error(
                    `unknown wrapper escaped trust boundary: fetch=${fetchCount} ` +
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

              legacy_data_filename_metadata_is_filtered_before_collection: async () => {
                const dispatchFor = async (attrs, text = "") => {
                  const control = new FakeElement({
                    tag: "a",
                    text,
                    attrs: {
                      href: "/cgi-bin/download?opaque=synthetic",
                      target: "_blank",
                      ...attrs,
                    },
                  });
                  const { doc } = openedMessage("", { hostResources: [control] });
                  let resourceCalls = 0;
                  let candidates = [];
                  const collector = {
                    extractVisibleThreadSegments: () => [],
                    collectVisibleResources: async (_receivedDoc, options) => {
                      resourceCalls += 1;
                      candidates = options.verifiedResourceCandidates;
                      return { attachment_files: [], resource_limitations: [] };
                    },
                  };
                  const result = await beginDispatch(loadAdapter(doc, collector)).responsePromise;
                  return { control, resourceCalls, candidates, result };
                };

                const supported = await dispatchFor({ "data-filename": "synthetic.pdf" });
                if (
                  supported.resourceCalls !== 1 ||
                  supported.candidates.length !== 1 ||
                  supported.candidates[0] !== supported.control
                ) {
                  throw new Error(`supported data-filename was not admitted: ${JSON.stringify(supported.result)}`);
                }

                const rejected = [
                  ["unsupported", { "data-filename": "synthetic.exe" }, ""],
                  ["declared conflict", {
                    "data-filename": "synthetic.pdf",
                    "data-type": "docx",
                  }, ""],
                  ["visible conflict", { "data-filename": "synthetic.xlsx" }, "synthetic.docx"],
                ];
                for (const [label, attrs, text] of rejected) {
                  const outcome = await dispatchFor(attrs, text);
                  if (outcome.resourceCalls !== 0 || outcome.result.payload.attachment_files.length !== 0) {
                    throw new Error(`adapter admitted ${label} data-filename: ${JSON.stringify(outcome.result)}`);
                  }
                }
              },

              exact_qmbox_two_wrapper_untyped_offviewport_control_is_bounded: async () => {
                const bodyText = "Please review the bounded legacy message.";
                const subject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic bounded request" });
                const header = new FakeElement({
                  className: "read-header",
                  text: "From: sender@example.test\nTo: recipient@example.test",
                });
                const currentBody = new FakeElement({ className: "mail-current-body", text: bodyText });
                const currentRoot = new FakeElement({
                  id: "mailContentContainer",
                  className: "qmbox",
                  text: bodyText,
                  children: [currentBody],
                });
                const intermediate = new FakeElement({
                  className: "legacy-current-message-wrapper",
                  children: [currentRoot],
                });
                let clickCount = 0;
                let scrollCount = 0;
                const attachment = new FakeElement({
                  tag: "a",
                  attrs: { href: "/cgi-bin/download?opaque=synthetic", target: "_blank" },
                  rect: { left: 0, top: 900, right: 160, bottom: 924, width: 160, height: 24 },
                });
                attachment.click = () => { clickCount += 1; };
                attachment.scrollIntoView = () => { scrollCount += 1; };
                const resourceContainer = new FakeElement({
                  className: "read-envelope",
                  children: [subject, header, intermediate, attachment],
                });
                const body = new FakeElement({
                  tag: "body",
                  text: `Synthetic bounded request\nFrom: sender@example.test\nTo: recipient@example.test\n${bodyText}`,
                  children: [resourceContainer],
                });
                const doc = new FakeDocument(body);
                const originalLocation = doc.location.href;
                let fetchCount = 0;
                const verifiedContext = {
                  document: doc,
                  currentMessageRoot: currentRoot,
                  currentBodyRoot: currentBody,
                  subjectRoot: subject,
                  headerRoot: header,
                  contextToken: Object.freeze({ synthetic: true }),
                };
                const listener = loadAdapterWithInjectedVerifiedContext(doc, async (_url, options) => {
                  fetchCount += 1;
                  if (options.credentials !== "include" || options.redirect !== "error") {
                    throw new Error(`unsafe fetch options: ${JSON.stringify(options)}`);
                  }
                  return pdfResponse();
                }, verifiedContext);

                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  fetchCount !== 1 ||
                  result.payload.attachment_files.length !== 1 ||
                  result.payload.attachment_files[0].filename !== "attachment-1.pdf" ||
                  result.payload.attachment_files[0].type !== "pdf"
                ) {
                  throw new Error(`bounded legacy shape failed: ${JSON.stringify({ fetchCount, result })}`);
                }
                if (clickCount !== 0 || scrollCount !== 0 || doc.location.href !== originalLocation) {
                  throw new Error(`control caused interaction: ${JSON.stringify({ clickCount, scrollCount })}`);
                }
              },

              exact_qmbox_with_two_intermediate_wrappers_has_zero_fetch_or_payload: async () => {
                const bodyText = "Please review the wrapper depth boundary.";
                const subject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic wrapper depth" });
                const header = new FakeElement({
                  className: "read-header",
                  text: "From: sender@example.test\nTo: recipient@example.test",
                });
                const currentBody = new FakeElement({ className: "mail-current-body", text: bodyText });
                const currentRoot = new FakeElement({
                  id: "mailContentContainer",
                  className: "qmbox",
                  text: bodyText,
                  children: [currentBody],
                });
                const firstIntermediate = new FakeElement({ children: [currentRoot] });
                const secondIntermediate = new FakeElement({ children: [firstIntermediate] });
                const attachment = new FakeElement({
                  tag: "a",
                  attrs: { href: "/cgi-bin/download?opaque=synthetic", target: "_blank" },
                });
                const resourceContainer = new FakeElement({
                  className: "read-envelope",
                  children: [subject, header, secondIntermediate, attachment],
                });
                const body = new FakeElement({
                  tag: "body",
                  text: `Synthetic wrapper depth\nFrom: sender@example.test\nTo: recipient@example.test\n${bodyText}`,
                  children: [resourceContainer],
                });
                const doc = new FakeDocument(body);
                const verifiedContext = {
                  document: doc,
                  currentMessageRoot: currentRoot,
                  currentBodyRoot: currentBody,
                  subjectRoot: subject,
                  headerRoot: header,
                  contextToken: Object.freeze({ synthetic: true }),
                };
                let fetchCount = 0;
                const listener = loadAdapterWithInjectedVerifiedContext(doc, async () => {
                  fetchCount += 1;
                  return pdfResponse();
                }, verifiedContext);

                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  fetchCount !== 0 ||
                  result.payload.attachment_files.length !== 0
                ) {
                  throw new Error(`two intermediate wrappers escaped: ${JSON.stringify({ fetchCount, result })}`);
                }
              },

              verified_visible_mainframe_resource_is_collected_with_real_collector: async () => {
                const topDoc = mailboxDocument();
                const forgedLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const productPhoto = new FakeElement({
                  tag: "img",
                  attrs: {
                    src: "/cgi-bin/viewfile?file=opaque-product-photo",
                    alt: "product packaging inspection photo",
                    "data-mime-type": "image/jpeg",
                  },
                  rect: { right: 1280, bottom: 960, width: 1280, height: 960 },
                });
                const { doc: frameDoc } = openedMessage("", {
                  hostResources: [forgedLink],
                  explicitCurrentBody: true,
                  currentBodyChildren: [productPhoto],
                });
                const frameElement = new FakeElement({
                  tag: "iframe",
                  attrs: {
                    name: "mainFrame",
                    src: "https://exmail.qq.com/cgi-bin/readmail",
                  },
                });
                frameElement.ownerDocument = topDoc;
                frameElement.parentElement = topDoc.body;
                frameElement.parentNode = topDoc.body;
                topDoc.body.children.push(frameElement);
                const frameWindow = { document: frameDoc, frames: [], frameElement };
                frameElement.contentWindow = frameWindow;
                let fetchCount = 0;
                const listener = loadAdapterWithRealCollector(topDoc, async () => {
                  fetchCount += 1;
                  return oneByteResponse();
                }, [frameWindow]);

                const result = await beginDispatch(listener).responsePromise;
                if (!result.ok || !result.payload.body_text.includes("visible message")) {
                  throw new Error(`frame body analysis did not continue: ${JSON.stringify(result)}`);
                }
                if (
                  fetchCount !== 2 ||
                  result.payload.attachment_files.length !== 2 ||
                  !result.payload.attachment_files.some((item) => item.filename === "forged.pdf") ||
                  !result.payload.attachment_files.some((item) => item.filename === "inline-image-1.jpg")
                ) {
                  throw new Error(
                    `verified frame resource was not collected: fetch=${fetchCount} ` +
                    `files=${result.payload.attachment_files.length}`,
                  );
                }
                if (result.payload.resource_limitations.length !== 0) {
                  throw new Error(`verified frame emitted a limitation: ${JSON.stringify(result)}`);
                }
              },

              fallback_current_body_root_keeps_business_image_discovery: async () => {
                const productPhoto = new FakeElement({
                  tag: "img",
                  attrs: {
                    src: "/cgi-bin/viewfile?file=fallback-product-photo",
                    alt: "product packaging inspection photo",
                    "data-mime-type": "image/jpeg",
                  },
                  rect: { right: 1280, bottom: 960, width: 1280, height: 960 },
                });
                const attachment = new FakeElement({
                  tag: "a",
                  text: "visible.pdf",
                  attrs: {
                    download: "visible.pdf",
                    href: "/cgi-bin/download?file=visible",
                  },
                });
                const { doc } = openedMessage("", {
                  bodyChildren: [productPhoto],
                  hostResources: [attachment],
                });
                const calls = [];
                const listener = loadAdapterWithRealCollector(doc, async (url) => {
                  calls.push(url);
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  calls.length !== 2 ||
                  result.payload.attachment_files.length !== 2 ||
                  !result.payload.attachment_files.some((item) => item.filename === "visible.pdf") ||
                  !result.payload.attachment_files.some((item) => item.filename === "inline-image-1.jpg")
                ) {
                  throw new Error(`fallback current body lost business media: ${JSON.stringify({ calls, result })}`);
                }
              },

              sibling_avatar_is_not_treated_as_an_attachment: async () => {
                const avatar = new FakeElement({
                  tag: "img",
                  attrs: {
                    src: "/cgi-bin/viewfile?file=sender-avatar",
                    alt: "sender-avatar.jpg",
                    "data-mime-type": "image/jpeg",
                  },
                  rect: { right: 64, bottom: 64, width: 64, height: 64 },
                });
                const attachment = new FakeElement({
                  tag: "a",
                  attrs: {
                    download: "visible.pdf",
                    href: "/cgi-bin/download?file=visible",
                  },
                });
                const { doc } = openedMessage("", { hostResources: [avatar, attachment] });
                const calls = [];
                const listener = loadAdapterWithRealCollector(doc, async (url) => {
                  calls.push(url);
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  calls.length !== 1 ||
                  !calls[0].includes("file=visible") ||
                  result.payload.attachment_files.length !== 1 ||
                  result.payload.attachment_files[0].filename !== "visible.pdf"
                ) {
                  throw new Error(`sibling avatar escaped: ${JSON.stringify({ calls, result })}`);
                }
              },

              approved_profile_link_is_not_treated_as_an_attachment_control: async () => {
                const profileLink = new FakeElement({
                  tag: "a",
                  className: "sender-profile avatar-link",
                  text: "Sender profile avatar",
                  attrs: {
                    href: "/cgi-bin/viewfile?file=sender-avatar",
                    "data-filename": "sender-avatar.jpg",
                    "data-type": "image/jpeg",
                    title: "View sender profile avatar",
                  },
                });
                const attachment = new FakeElement({
                  tag: "a",
                  text: "visible.pdf",
                  attrs: {
                    download: "visible.pdf",
                    href: "/cgi-bin/download?file=visible",
                  },
                });
                const { doc } = openedMessage("", {
                  hostResources: [profileLink, attachment],
                });
                const calls = [];
                const listener = loadAdapterWithRealCollector(doc, async (url) => {
                  calls.push(url);
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  calls.length !== 1 ||
                  !calls[0].includes("file=visible") ||
                  result.payload.attachment_files.length !== 1 ||
                  result.payload.attachment_files[0].filename !== "visible.pdf"
                ) {
                  throw new Error(`profile link escaped attachment ownership: ${JSON.stringify({ calls, result })}`);
                }
              },

              legacy_tencent_download_control_is_collected_once: async () => {
                const legacyControl = new FakeElement({
                  tag: "a",
                  text: "synthetic.pdf",
                  attrs: {
                    href: "/cgi-bin/download?opaque=synthetic",
                    target: "_blank",
                  },
                });
                const { doc } = openedMessage("", { hostResources: [legacyControl] });
                const requests = [];
                const listener = loadAdapterWithRealCollector(doc, async (url, options) => {
                  requests.push({ url, options });
                  return oneByteResponse();
                });
                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  requests.length !== 1 ||
                  requests[0].url !== "https://exmail.qq.com/cgi-bin/download?opaque=synthetic" ||
                  requests[0].options.credentials !== "include" ||
                  requests[0].options.redirect !== "error" ||
                  result.payload.attachment_files.length !== 1 ||
                  result.payload.attachment_files[0].filename !== "synthetic.pdf" ||
                  result.payload.resource_limitations.length !== 0
                ) {
                  throw new Error(`legacy Tencent control was not collected safely: ${JSON.stringify({ requests, result })}`);
                }
              },

              verified_context_resource_discovery_does_not_prescan_deep_document: async () => {
                const attachment = new FakeElement({
                  tag: "a",
                  attrs: {
                    download: "visible.pdf",
                    href: "/cgi-bin/download?file=visible",
                  },
                });
                const {
                  doc,
                  currentRoot,
                  currentMessageContainer,
                  header,
                  subject,
                } = openedMessage("", { hostResources: [attachment] });
                const verifiedContext = {
                  document: doc,
                  frameWindow: null,
                  frameElement: null,
                  subjectRoot: subject,
                  headerRoot: header,
                  currentMessageRoot: currentRoot,
                  currentBodyRoot: currentRoot,
                  currentBodyText: "Please review the visible message.",
                  threadRoot: currentRoot,
                  contextToken: {},
                };

                let deepRoot = new FakeElement();
                for (let depth = 0; depth < 12000; depth += 1) {
                  deepRoot = new FakeElement({ children: [deepRoot] });
                }
                deepRoot.parentElement = doc.body;
                deepRoot.parentNode = doc.body;
                doc.body.children.push(deepRoot);

                const knownElements = [subject, header, currentRoot, attachment];
                doc.querySelector = (selector) =>
                  knownElements.find((element) => matches(element, selector)) || null;
                doc.querySelectorAll = (selector) =>
                  knownElements.filter((element) => matches(element, selector));
                doc.body.querySelectorAll = (selector) =>
                  knownElements.filter((element) => matches(element, selector));

                const calls = [];
                const listener = loadAdapterWithInjectedVerifiedContext(
                  doc,
                  async (url) => {
                    calls.push(url);
                    return oneByteResponse();
                  },
                  verifiedContext,
                );
                const result = await beginDispatch(listener).responsePromise;
                if (
                  !result.ok ||
                  calls.length !== 1 ||
                  !calls[0].includes("file=visible") ||
                  result.payload.attachment_files.length !== 1 ||
                  result.payload.attachment_files[0].filename !== "visible.pdf"
                ) {
                  throw new Error(`deep pre-scan bypassed resource bounds: ${JSON.stringify({ calls, result })}`);
                }
              },

              whole_fake_envelope_below_unknown_wrapper_fails_closed: async () => {
                const subjectText = "Synthetic fake envelope";
                const headerText = "From: sender@example.test\nTo: recipient@example.test";
                const bodyText = "Please review the fake envelope message.";
                const forgedLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const fakeEnvelope = new FakeElement({
                  className: "author-envelope",
                  children: [
                    new FakeElement({ tag: "h1", id: "subject", text: subjectText }),
                    new FakeElement({ className: "read-header", text: headerText }),
                    new FakeElement({
                      id: "mailContentContainer", text: bodyText,
                      children: [new FakeElement({ className: "mail-current-body", text: bodyText })],
                    }),
                    forgedLink,
                  ],
                });
                const unknownRealBodyWrapper = new FakeElement({ children: [fakeEnvelope] });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: `${subjectText}\n${headerText}\n${bodyText}`,
                  children: [unknownRealBodyWrapper],
                }));
                let fetchCount = 0;
                const listener = loadAdapterWithRealCollector(doc, async () => {
                  fetchCount += 1;
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (!result.ok || !result.payload.body_text.includes("fake envelope message")) {
                  throw new Error(`body analysis did not continue: ${JSON.stringify(result)}`);
                }
                if (fetchCount !== 0 || result.payload.attachment_files.length !== 0) {
                  throw new Error(
                    `whole fake envelope escaped: fetch=${fetchCount} ` +
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

              additional_global_known_body_root_fails_closed: async () => {
                const forgedLink = new FakeElement({
                  tag: "a",
                  attrs: { download: "forged.pdf", href: "/cgi-bin/download?file=forged" },
                });
                const additionalBody = new FakeElement({
                  className: "mail-content",
                  text: "Second author-controlled visible message body.",
                });
                const { doc } = openedMessage("", {
                  hostResources: [forgedLink],
                  envelopeExternal: [additionalBody],
                });
                let fetchCount = 0;
                const listener = loadAdapterWithRealCollector(doc, async () => {
                  fetchCount += 1;
                  return oneByteResponse();
                });

                const result = await beginDispatch(listener).responsePromise;
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload") || fetchCount !== 0) {
                  throw new Error(`global body ambiguity escaped: fetch=${fetchCount} ${JSON.stringify(result)}`);
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

                const bodyLevelControls = new FakeElement({ children: [validControl()] });
                cases.push(openedMessage("", { envelopeExternal: [bodyLevelControls] }).doc);

                const duplicateBody = new FakeElement({
                  className: "mail-content", text: "Second ambiguous visible message body.",
                });
                const duplicateDoc = openedMessage("", {
                  additionalBodies: [duplicateBody], hostResources: [validControl()],
                }).doc;
                const duplicateResult = await beginDispatch(loadAdapter(duplicateDoc, collector)).responsePromise;
                if (
                  duplicateResult.ok ||
                  Object.prototype.hasOwnProperty.call(duplicateResult, "payload")
                ) {
                  throw new Error(`ambiguous duplicate body escaped: ${JSON.stringify(duplicateResult)}`);
                }
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

              full_scope_revalidation_detects_mutations: async () => {
                const dimensions = [
                  ["thread", (state) => { state.thread = "THREAD-MUTATED"; }],
                  ["attachment metadata", (state) => { state.metadata = "metadata-mutated.pdf"; }],
                  ["attachment content", (state) => { state.content = "Q09OVEVOVC1NVVRBVEVE"; }],
                  ["resource limitation", (state) => { state.limitation = "LIMITATION-MUTATED"; }],
                ];
                for (const [label, mutate] of dimensions) {
                  const state = {
                    thread: "THREAD-ORIGINAL",
                    metadata: "metadata-original.pdf",
                    content: "Q09OVEVOVC1PUklHSU5BTA==",
                    limitation: "LIMITATION-ORIGINAL",
                  };
                  const control = new FakeElement({
                    tag: "a",
                    attrs: { download: "scope.pdf", href: "/cgi-bin/download?file=scope" },
                  });
                  const { doc, currentRoot } = openedMessage("", { hostResources: [control] });
                  Object.defineProperty(currentRoot, "innerText", {
                    get: () => `Please review the visible message. ${state.metadata}`,
                  });
                  Object.defineProperty(currentRoot, "textContent", {
                    get: () => `Please review the visible message. ${state.metadata}`,
                  });
                  doc.defaultView.getSelection = () => ({
                    rangeCount: 1,
                    toString: () => "Please review the fixed selected message.",
                    getRangeAt: () => ({ commonAncestorContainer: currentRoot }),
                  });
                  const collector = {
                    extractVisibleThreadSegments: () => [{
                      position: 0, from: "sender@example.test", to: "recipient@example.test",
                      sent_at: "", timestamp_text: "Today", subject: "Scope",
                      body_text: state.thread,
                    }],
                    collectVisibleResources: async () => ({
                      attachment_files: [{
                        filename: "scope-resource.pdf", type: "pdf", size: 16,
                        content_base64: state.content,
                      }],
                      resource_limitations: [{
                        code: "resource_read_failed", filename: "limited.docx", type: "docx",
                        size: 0, limitation: state.limitation,
                      }],
                    }),
                  };
                  const listener = loadAdapter(doc, collector);
                  const initial = await beginDispatch(listener).responsePromise;
                  const unchanged = await beginDispatch(
                    listener, { type: "REVALIDATE_CURRENT_EMAIL" },
                  ).responsePromise;
                  if (unchanged.message_fingerprint !== initial.message_fingerprint) {
                    throw new Error(`${label} unchanged scope was not stable`);
                  }
                  mutate(state);
                  const changed = await beginDispatch(
                    listener, { type: "REVALIDATE_CURRENT_EMAIL" },
                  ).responsePromise;
                  assertExactKeys(changed, ["ok", "message_fingerprint"], `${label} revalidation`);
                  if (!changed.ok || changed.message_fingerprint === initial.message_fingerprint) {
                    throw new Error(`${label} mutation did not invalidate the fingerprint`);
                  }
                  const serialized = JSON.stringify(changed);
                  for (const forbidden of Object.values(state)) {
                    if (serialized.includes(forbidden)) {
                      throw new Error(`${label} raw analyzed scope leaked: ${forbidden}`);
                    }
                  }
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
        script = script.replace("__VISIBLE_CONTEXT_PATH__", json.dumps(str(VISIBLE_CONTEXT)))
        script = script.replace("__COLLECTOR_PATH__", json.dumps(str(COLLECTOR)))
        script = script.replace("__CLASSIFIER_PATH__", json.dumps(str(CLASSIFIER)))
        script = script.replace("__CASE_NAME__", json.dumps(case_name))
        result = subprocess.run(
            ["node", "-"],
            cwd=ROOT,
            input=script,
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

    def test_unknown_intermediate_body_wrapper_fails_closed_with_real_collector(self) -> None:
        self.run_node_case("unknown_intermediate_body_wrapper_fails_closed_with_real_collector")

    def test_legacy_data_filename_metadata_is_filtered_before_collection(self) -> None:
        self.run_node_case("legacy_data_filename_metadata_is_filtered_before_collection")

    def test_exact_qmbox_two_wrapper_untyped_offviewport_control_is_bounded(self) -> None:
        self.run_node_case(
            "exact_qmbox_two_wrapper_untyped_offviewport_control_is_bounded"
        )

    def test_exact_qmbox_with_two_intermediate_wrappers_has_zero_fetch_or_payload(
        self,
    ) -> None:
        self.run_node_case(
            "exact_qmbox_with_two_intermediate_wrappers_has_zero_fetch_or_payload"
        )

    def test_verified_visible_mainframe_resource_is_collected_with_real_collector(self) -> None:
        self.run_node_case("verified_visible_mainframe_resource_is_collected_with_real_collector")

    def test_fallback_current_body_root_keeps_business_image_discovery(self) -> None:
        self.run_node_case("fallback_current_body_root_keeps_business_image_discovery")

    def test_sibling_avatar_is_not_treated_as_an_attachment(self) -> None:
        self.run_node_case("sibling_avatar_is_not_treated_as_an_attachment")

    def test_approved_profile_link_is_not_treated_as_an_attachment_control(self) -> None:
        self.run_node_case("approved_profile_link_is_not_treated_as_an_attachment_control")

    def test_legacy_tencent_download_control_is_collected_once(self) -> None:
        self.run_node_case("legacy_tencent_download_control_is_collected_once")

    def test_verified_context_resource_discovery_does_not_prescan_deep_document(self) -> None:
        self.run_node_case("verified_context_resource_discovery_does_not_prescan_deep_document")

    def test_whole_fake_envelope_below_unknown_wrapper_fails_closed(self) -> None:
        self.run_node_case("whole_fake_envelope_below_unknown_wrapper_fails_closed")

    def test_additional_global_known_body_root_fails_closed(self) -> None:
        self.run_node_case("additional_global_known_body_root_fails_closed")

    def test_invalid_structural_envelopes_and_endpoints_fail_closed(self) -> None:
        self.run_node_case("invalid_structural_envelopes_and_endpoints_fail_closed")

    def test_full_scope_revalidation_detects_mutations_without_raw_content(self) -> None:
        self.run_node_case("full_scope_revalidation_detects_mutations")

    def test_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("hidden_frame_message_is_not_extracted")

    def test_stylesheet_hidden_frame_message_is_not_extracted(self) -> None:
        self.run_node_case("stylesheet_hidden_frame_message_is_not_extracted")

    def test_stylesheet_hidden_message_root_is_not_selected(self) -> None:
        self.run_node_case("stylesheet_hidden_message_root_is_not_selected")


if __name__ == "__main__":
    unittest.main()
