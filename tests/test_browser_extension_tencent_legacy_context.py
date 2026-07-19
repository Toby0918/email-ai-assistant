"""Tencent Exmail legacy-thread extraction behavior tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "frontend" / "browser_extension" / "content" / "exmail_adapter.js"
VISIBLE_CONTEXT = (
    ROOT
    / "frontend"
    / "browser_extension"
    / "content"
    / "exmail_visible_context.js"
)
COLLECTOR = (
    ROOT
    / "frontend"
    / "browser_extension"
    / "content"
    / "current_message_collector.js"
)


class TencentLegacyContextTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const adapterSource = fs.readFileSync(__ADAPTER_PATH__, "utf8");
            const collectorSource = fs.readFileSync(__COLLECTOR_PATH__, "utf8");
            const visibleContextSource = fs.existsSync(__VISIBLE_CONTEXT_PATH__)
              ? fs.readFileSync(__VISIBLE_CONTEXT_PATH__, "utf8")
              : "";

            class FakeElement {
              constructor({ tag = "div", id = "", className = "", text = "",
                            children = [], attrs = {}, hidden = false, style = {},
                            aggregateText = false, rect = null } = {}) {
                this.tagName = tag.toUpperCase();
                this.id = id;
                this.className = className;
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
                const textNode = text ? {
                  nodeType: 3,
                  nodeValue: text,
                  textContent: text,
                  parentElement: this,
                  parentNode: this,
                } : null;
                this.childNodes = [...(textNode ? [textNode] : []), ...children];
                const aggregate = () => this.childNodes
                  .map((node) => node.nodeType === 3 ? node.nodeValue : node.innerText)
                  .filter(Boolean)
                  .join("\n");
                if (aggregateText) {
                  Object.defineProperty(this, "innerText", { get: aggregate });
                  Object.defineProperty(this, "textContent", { get: aggregate });
                } else {
                  this.innerText = text;
                  this.textContent = text;
                }
                const resolvedRect = {
                  left: 0, top: 0, right: 100, bottom: 20, width: 100, height: 20,
                  ...(rect || {}),
                };
                this.getBoundingClientRect = () => ({ ...resolvedRect });
              }

              contains(node) {
                return node === this || this.children.some((child) => child.contains(node));
              }

              getAttribute(name) {
                if (name === "id") return this.id || null;
                if (name === "class") return this.className || null;
                return Object.prototype.hasOwnProperty.call(this.attrs, name)
                  ? String(this.attrs[name])
                  : null;
              }

              hasAttribute(name) {
                return (name === "hidden" && this.hidden) ||
                  Object.prototype.hasOwnProperty.call(this.attrs, name);
              }

              querySelector(selector) {
                return this.querySelectorAll(selector)[0] || null;
              }

              querySelectorAll(selector) {
                return descendants(this).filter((element) => matchesAny(element, selector));
              }
            }

            class FakeDocument {
              constructor(body) {
                this.body = body;
                this.title = "Tencent Exmail synthetic fixture";
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
                return [this.body, ...descendants(this.body)]
                  .find((element) => matchesAny(element, selector)) || null;
              }

              querySelectorAll(selector) {
                return [this.body, ...descendants(this.body)]
                  .filter((element) => matchesAny(element, selector));
              }
            }

            function descendants(root) {
              return root.children.flatMap((child) => [child, ...descendants(child)]);
            }

            function assignOwnerDocument(root, doc) {
              root.ownerDocument = doc;
              for (const child of root.children) assignOwnerDocument(child, doc);
            }

            function matchesAny(element, selectorList) {
              return selectorList.split(",").some((selector) => matches(element, selector.trim()));
            }

            function matches(element, selector) {
              const attributeMatch = selector.match(/^\[([^=\]]+)(?:=['\"]?([^'\"]+)['\"]?)?\]$/);
              if (attributeMatch) {
                const [, name, value] = attributeMatch;
                if (!element.hasAttribute(name)) return false;
                return value === undefined || element.getAttribute(name) === value;
              }
              if (selector.startsWith("#")) return element.id === selector.slice(1);
              if (selector.startsWith(".")) {
                return element.className.split(/\s+/).includes(selector.slice(1));
              }
              if (selector === "[role='heading']") {
                return element.getAttribute("role") === "heading";
              }
              return element.tagName.toLowerCase() === selector.toLowerCase();
            }

            function emptySelection() {
              return {
                rangeCount: 0,
                toString: () => "",
                getRangeAt: () => { throw new Error("No range"); },
              };
            }

            function block(text, options = {}) {
              return new FakeElement({ className: "readmail_item", text, ...options });
            }

            function structuredBlock(attrs, children = []) {
              return new FakeElement({
                attrs: { "data-email-thread-segment": "true", ...attrs },
                text: "not legacy inline headers",
                children,
              });
            }

            const oldestText = [
              "From: buyer@example.test",
              "Date: 2026-07-10 09:00",
              "To: sales@example.test",
              "Subject: Synthetic placement request",
              "",
              "Please confirm the initial placement.",
              "Use the right side of the carton.",
              "Email: buyer@example.test",
            ].join("\n");

            const newestText = [
              "From: sales@example.test",
              "Date: 2026-07-11 10:30",
              "To: buyer@example.test",
              "Subject: Re: Synthetic placement request",
              "",
              "Placement is confirmed.",
              "Keep the label on one side.",
              "",
              "Thank you",
              "Best regards",
              "Synthetic Team",
              "Phone: +1 555 0100",
              "-----Original Message-----",
              "From: buyer@example.test",
              "Date: 2026-07-10 09:00",
              "To: sales@example.test",
              "Subject: Synthetic placement request",
              "OLD QUOTED CONTENT MUST NOT SURVIVE",
            ].join("\n");

            function legacyDocument(order = "newest-first", extras = []) {
              const messages = order === "newest-first"
                ? [block(newestText), block(oldestText)]
                : [block(oldestText), block(newestText)];
              const rootText = messages.map((item) => item.innerText).join("\n\n");
              const root = new FakeElement({
                className: "mail-content",
                text: rootText,
                children: [...messages, ...extras],
              });
              const staleHeader = new FakeElement({
                className: "read-header",
                text: [
                  "From: buyer@example.test",
                  "Date: 2026-07-10 09:00",
                  "To: sales@example.test",
                ].join("\n"),
              });
              const staleSubject = new FakeElement({
                tag: "h1",
                id: "subject",
                text: "Synthetic placement request",
              });
              const envelope = new FakeElement({
                className: "read-envelope",
                children: [staleSubject, staleHeader, root],
              });
              const body = new FakeElement({
                tag: "body",
                text: [staleSubject.innerText, staleHeader.innerText, rootText].join("\n"),
                children: [envelope],
              });
              return { doc: new FakeDocument(body), root };
            }

            function loadCollector() {
              const context = {
                URL,
                Uint8Array,
                ArrayBuffer,
                AbortController,
                setTimeout,
                clearTimeout,
              };
              context.window = context;
              vm.runInNewContext(collectorSource, context, {
                filename: "current_message_collector.js",
              });
              return context.EmailAssistantCurrentMessageCollector;
            }

            function resolveVisibleContext(doc, frames = []) {
              const rootWindow = { document: doc, frames };
              const context = { URL, window: rootWindow };
              vm.runInNewContext(visibleContextSource, context, {
                filename: "exmail_visible_context.js",
              });
              return rootWindow.EmailAssistantExmailVisibleContext
                .resolveVerifiedDocumentContext(rootWindow);
            }

            function loadAdapter(doc, collectorOverride = null, frames = []) {
              let listener;
              const rootWindow = {
                document: doc,
                frames,
                AbortController,
                setTimeout,
                clearTimeout,
              };
              if (collectorOverride) {
                rootWindow.EmailAssistantCurrentMessageCollector = collectorOverride;
              }
              const context = {
                URL,
                Uint8Array,
                ArrayBuffer,
                AbortController,
                setTimeout,
                clearTimeout,
                window: rootWindow,
                document: doc,
                chrome: {
                  runtime: {
                    onMessage: {
                      addListener: (callback) => { listener = callback; },
                    },
                  },
                },
              };
              if (visibleContextSource) {
                vm.runInNewContext(visibleContextSource, context, {
                  filename: "exmail_visible_context.js",
                });
              }
              if (!collectorOverride) {
                vm.runInNewContext(collectorSource, context, {
                  filename: "current_message_collector.js",
                });
              }
              vm.runInNewContext(adapterSource, context, { filename: "exmail_adapter.js" });
              return listener;
            }

            function syntheticHeader() {
              return new FakeElement({
                className: "read-header",
                text: [
                  "From: current@example.test",
                  "Date: 2026-07-12 11:00",
                  "To: team@example.test",
                ].join("\n"),
              });
            }

            function semanticLineBreakBody(mode) {
              const lineBreak = new FakeElement({
                tag: "br",
                hidden: mode === "hidden",
                rect: {
                  left: 10,
                  top: 10,
                  right: 10,
                  bottom: 27,
                  width: 0,
                  height: 17,
                },
              });
              const middle = mode === "hidden-ancestor"
                ? new FakeElement({
                    tag: "span",
                    hidden: true,
                    children: [lineBreak],
                    aggregateText: true,
                  })
                : lineBreak;
              return new FakeElement({
                className: "qm_con_body",
                children: [
                  new FakeElement({ tag: "span", text: "Hello" }),
                  middle,
                  new FakeElement({ tag: "span", text: "World" }),
                ],
                aggregateText: true,
              });
            }

            function legacyFrameDocument(options = {}) {
              const embeddedBodyChildren = [];
              if (options.headerInsideBody) embeddedBodyChildren.push(syntheticHeader());
              if (options.bodyInjectedHistory) embeddedBodyChildren.push(block(oldestText));
              if (options.bodyInjectedUnparseableHistory) {
                embeddedBodyChildren.push(block(
                  "Authored nested history lookalike must not enter current body.",
                ));
              }
              if (options.bodyHeading) {
                embeddedBodyChildren.push(new FakeElement({ tag: "h1", text: "Authored heading" }));
              }
              if (options.legitimateNestedText) {
                embeddedBodyChildren.push(new FakeElement({
                  tag: "p",
                  text: "Legitimate nested paragraph.",
                }));
              }
              if (options.nestedKnownBody) {
                embeddedBodyChildren.push(new FakeElement({
                  className: "mail-content",
                  text: "Authored nested body must not replace the verified outer body.",
                }));
              }
              const currentBodies = options.semanticLineBreak
                ? [semanticLineBreakBody(options.semanticLineBreak)]
                : options.duplicateBodies
                ? [
                    new FakeElement({ className: "qm_con_body", text: "First ambiguous body." }),
                    new FakeElement({ className: "qm_con_body", text: "Second ambiguous body." }),
                  ]
                : [new FakeElement({
                    className: options.knownBody ? "mail-content" : "qm_con_body",
                    text: "Current automatic request.\nPlease review the visible placement.",
                    children: embeddedBodyChildren,
                    aggregateText: true,
                  })];
              const subject = new FakeElement({
                tag: "h1",
                id: "subject",
                text: "Re: Synthetic placement request",
              });
              const children = [];
              if (options.leadingMetadata) {
                children.push(new FakeElement({
                  className: "mailbox-navigation",
                  text: [
                    "From: forged@example.test",
                    "To: forged-recipient@example.test",
                    "Date: 1999-01-01 00:00",
                  ].join("\n"),
                }));
              }
              children.push(subject);
              if (!options.missingHeader && !options.headerInsideBody) children.push(syntheticHeader());
              children.push(...currentBodies);
              if (!options.omitHistory) children.push(block(oldestText), block(newestText));
              const bodyText = children.map((child) => child.innerText).join("\n\n");
              const envelope = new FakeElement({
                className: "read-envelope",
                text: bodyText,
                children,
              });
              const documentChildren = options.unwrapped ? children : [envelope];
              if (options.backgroundThread) {
                documentChildren.push(new FakeElement({
                  className: "mailbox-region",
                  children: [block(oldestText)],
                }));
              }
              const doc = new FakeDocument(new FakeElement({
                tag: "body",
                text: bodyText,
                children: documentChildren,
              }));
              return { doc, currentBody: currentBodies[0] };
            }

            function mainFrameFixture(options = {}) {
              const frameState = legacyFrameDocument(options);
              const frameElement = new FakeElement({
                tag: "iframe",
                attrs: {
                  name: "mainFrame",
                  src: options.crossOrigin
                    ? "https://remote.example/frame"
                    : "https://exmail.qq.com/cgi-bin/readmail",
                },
                hidden: Boolean(options.hidden),
                style: options.frameStyle || {},
                rect: options.frameRect || null,
              });
              const topDoc = new FakeDocument(new FakeElement({
                tag: "body",
                text: "Mailbox navigation only",
                children: [frameElement],
              }));
              const frameWindow = {
                frameElement,
                frames: [],
                AbortController,
                setTimeout,
                clearTimeout,
              };
              frameElement.contentWindow = frameWindow;
              if (options.crossOrigin) {
                Object.defineProperty(frameWindow, "document", {
                  get: () => { throw new Error("cross-origin"); },
                });
              } else {
                frameWindow.document = frameState.doc;
              }
              return { ...frameState, topDoc, frameElement, frameWindow };
            }

            function duplicateMainFrameFixture() {
              const first = mainFrameFixture();
              const secondState = legacyFrameDocument();
              const secondElement = new FakeElement({
                tag: "iframe",
                attrs: { name: "mainFrame", src: "https://exmail.qq.com/cgi-bin/readmail" },
              });
              const topDoc = new FakeDocument(new FakeElement({
                tag: "body",
                text: "Mailbox navigation only",
                children: [first.frameElement, secondElement],
              }));
              const secondWindow = { document: secondState.doc, frameElement: secondElement, frames: [] };
              secondElement.contentWindow = secondWindow;
              return {
                topDoc,
                frames: [first.frameWindow, secondWindow],
              };
            }

            async function dispatch(listener) {
              return new Promise((resolve) => {
                const keepAlive = listener(
                  { type: "EXTRACT_CURRENT_EMAIL" },
                  {},
                  resolve,
                );
                if (keepAlive !== true) throw new Error("adapter did not keep async response alive");
              });
            }

            function assertNormalizedResult(result) {
              if (!result.ok) throw new Error(JSON.stringify(result));
              const payload = result.payload;
              if (payload.thread_segments.length !== 2) {
                throw new Error(`expected two segments: ${JSON.stringify(payload)}`);
              }
              const [oldest, newest] = payload.thread_segments;
              if (oldest.position !== 0 || newest.position !== 1) {
                throw new Error("positions are not oldest-to-newest");
              }
              if (oldest.from !== "buyer@example.test" || newest.from !== "sales@example.test") {
                throw new Error(`chronology or sender mismatch: ${JSON.stringify(payload.thread_segments)}`);
              }
              if (payload.from !== "buyer@example.test") {
                throw new Error(`top-level sender was not taken from verified header: ${payload.from}`);
              }
              if (payload.subject !== "Synthetic placement request") {
                throw new Error(`top-level subject was not verified: ${payload.subject}`);
              }
              if (payload.sent_at !== "2026-07-10 09:00") {
                throw new Error(`top-level date was not taken from verified header: ${payload.sent_at}`);
              }
              if (JSON.stringify(payload.to) !== JSON.stringify(["sales@example.test"])) {
                throw new Error(`top-level recipient was not verified: ${JSON.stringify(payload.to)}`);
              }
              const expected = "Placement is confirmed.\nKeep the label on one side.\n\nThank you";
              if (payload.body_text !== expected || newest.body_text !== expected) {
                throw new Error(`meaningful lines were not preserved: ${JSON.stringify(payload.body_text)}`);
              }
              const serialized = JSON.stringify(payload.thread_segments);
              for (const forbidden of ["Phone:", "Email:", "Best regards", "OLD QUOTED CONTENT"]) {
                if (serialized.includes(forbidden)) {
                  throw new Error(`signature or quoted history survived: ${forbidden}`);
                }
              }
            }

            const cases = {
              legacy_main_frame_extracts_current_body_and_full_history: async () => {
                const fixture = mainFrameFixture();
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    "Current automatic request.\nPlease review the visible placement."
                ) {
                  throw new Error(`legacy current body was not automatic: ${JSON.stringify(result)}`);
                }
                if (
                  result.payload.thread_segments.length !== 2 ||
                  result.payload.thread_segments[0].from !== "buyer@example.test" ||
                  result.payload.thread_segments[1].from !== "sales@example.test"
                ) {
                  throw new Error(`legacy history was not oldest-first: ${JSON.stringify(result)}`);
                }
              },

              legacy_qmbox_sibling_download_control_reaches_verified_collector: async () => {
                const subject = new FakeElement({
                  tag: "span",
                  id: "subject",
                  text: "Synthetic legacy attachment",
                });
                const header = new FakeElement({
                  className: "readmailinfo",
                  children: [subject],
                  text: [
                    "From: sender@example.test",
                    "Date: 2026-07-12 11:00",
                    "To: recipient@example.test",
                  ].join("\n"),
                  aggregateText: true,
                });
                const currentBody = new FakeElement({
                  id: "mailContentContainer",
                  className: "qmbox",
                  text: "Current automatic attachment request.",
                });
                const legacyControl = new FakeElement({
                  tag: "a",
                  text: "synthetic.pdf",
                  attrs: {
                    href: "/cgi-bin/download?opaque=synthetic",
                    target: "_blank",
                  },
                });
                const mainmail = new FakeElement({
                  id: "mainmail",
                  children: [header, currentBody, legacyControl],
                  aggregateText: true,
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [mainmail],
                  aggregateText: true,
                }));
                let received = null;
                const collector = {
                  extractVisibleMessageContext: () => ({
                    current_message: { body_text: "Current automatic attachment request." },
                    thread_segments: [],
                  }),
                  collectVisibleResources: async (_doc, options) => {
                    received = options.verifiedResourceCandidates;
                    return { attachment_files: [], resource_limitations: [] };
                  },
                };
                const result = await dispatch(loadAdapter(doc, collector));
                if (
                  !result.ok ||
                  !Array.isArray(received) ||
                  received.length !== 1 ||
                  received[0] !== legacyControl
                ) {
                  throw new Error(`legacy qmbox sibling control was dropped: ${JSON.stringify({ result, count: received && received.length })}`);
                }
              },

              legacy_qmbox_sibling_invalid_controls_never_reach_collector: async () => {
                const buildDocument = (legacyControl) => {
                  const subject = new FakeElement({ tag: "span", id: "subject", text: "Synthetic" });
                  const header = new FakeElement({
                    className: "readmailinfo",
                    text: ["From: sender@example.test", "Date: 2026-07-12 11:00", "To: recipient@example.test"].join("\n"),
                    children: [subject],
                    aggregateText: true,
                  });
                  const currentBody = new FakeElement({
                    id: "mailContentContainer",
                    className: "qmbox",
                    text: "Current automatic attachment request.",
                  });
                  const mainmail = new FakeElement({
                    id: "mainmail",
                    children: [header, currentBody, legacyControl],
                    aggregateText: true,
                  });
                  return new FakeDocument(new FakeElement({
                    tag: "body",
                    children: [mainmail],
                    aggregateText: true,
                  }));
                };
                const invalid = [
                  ["hidden text", "", "/cgi-bin/download?opaque=synthetic", "synthetic.pdf"],
                  ["doc", "synthetic.doc", "/cgi-bin/download?opaque=synthetic", ""],
                  ["xls", "synthetic.xls", "/cgi-bin/download?opaque=synthetic", ""],
                  ["pptx", "synthetic.pptx", "/cgi-bin/download?opaque=synthetic", ""],
                  ["zip", "synthetic.zip", "/cgi-bin/download?opaque=synthetic", ""],
                  ["txt", "synthetic.txt", "/cgi-bin/download?opaque=synthetic", ""],
                  ["signature text", "signature synthetic.pdf", "/cgi-bin/download?opaque=synthetic", ""],
                  ["profile label", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["malformed declared image", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["declared visible mismatch", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["image canonical conflict", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["declared image conflict", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["visible label conflict", "synthetic.pdf", "/cgi-bin/download?opaque=synthetic", ""],
                  ["compound visible label conflict", "synthetic.pdf synthetic.docx", "/cgi-bin/download?opaque=synthetic", ""],
                  ["compound visible label unknown", "synthetic.pdf synthetic.exe", "/cgi-bin/download?opaque=synthetic", ""],
                  ["SVG image", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["HEIC image", "", "/cgi-bin/download?opaque=synthetic", ""],
                  ["credential URL", "synthetic.pdf", "https://user:pass" + "@exmail.qq.com/cgi-bin/download?opaque=synthetic", ""],
                  ["HTTP URL", "synthetic.pdf", "http://exmail.qq.com/cgi-bin/download?opaque=synthetic", ""],
                  ["HTTPS port", "synthetic.pdf", "https://exmail.qq.com:444/cgi-bin/download?opaque=synthetic", ""],
                ];
                for (const [label, text, href, hiddenText] of invalid) {
                  const legacyControl = new FakeElement({
                    tag: "a",
                    text,
                    attrs: {
                      href,
                      target: "_blank",
                      ...(label === "profile label" ? { "aria-label": "profile synthetic.pdf" } : {}),
                      ...(label === "malformed declared image" ? {
                        title: "synthetic.pdf",
                        "data-type": "image/jpeg trailing",
                      } : {}),
                      ...(label === "declared visible mismatch" ? {
                        title: "synthetic.pdf",
                        "data-type": "docx",
                      } : {}),
                      ...(label === "image canonical conflict" ? {
                        "aria-label": "image/png",
                        "data-type": "image/jpeg",
                      } : {}),
                      ...(label === "declared image conflict" ? {
                        "aria-label": "image/png",
                        "data-type": "image/png",
                        "data-mime-type": "image/jpeg",
                      } : {}),
                      ...(label === "visible label conflict" ? {
                        "aria-label": "synthetic.docx",
                        "data-type": "pdf",
                      } : {}),
                      ...(label === "SVG image" ? {
                        "aria-label": "image/svg+xml",
                        "data-type": "image/svg+xml",
                      } : {}),
                      ...(label === "HEIC image" ? {
                        "aria-label": "image/heic",
                        "data-type": "image/heic",
                      } : {}),
                    },
                  });
                  if (hiddenText) {
                    const hiddenChild = new FakeElement({ tag: "span", text: hiddenText, hidden: true });
                    legacyControl.children = [hiddenChild];
                    legacyControl.childNodes.push(hiddenChild);
                    hiddenChild.parentElement = legacyControl;
                    hiddenChild.parentNode = legacyControl;
                    legacyControl.textContent = hiddenText;
                  }
                  let collectionCalls = 0;
                  const collector = {
                    extractVisibleMessageContext: () => ({
                      current_message: { body_text: "Current automatic attachment request." },
                      thread_segments: [],
                    }),
                    collectVisibleResources: async () => {
                      collectionCalls += 1;
                      return { attachment_files: [], resource_limitations: [] };
                    },
                  };
                  const result = await dispatch(loadAdapter(buildDocument(legacyControl), collector));
                  if (!result.ok || collectionCalls !== 0) {
                    throw new Error(`invalid legacy control reached collector: ${label}`);
                  }
                }
              },

              real_readmailinfo_nested_quotes_extract_current_body_and_history: async () => {
                const oldestQuote = new FakeElement({
                  tag: "blockquote",
                  text: oldestText,
                  aggregateText: true,
                });
                const recentQuote = new FakeElement({
                  tag: "blockquote",
                  text: newestText,
                  children: [oldestQuote],
                  aggregateText: true,
                });
                const currentRoot = new FakeElement({
                  id: "mailContentContainer",
                  className: "qmbox",
                  children: [
                    new FakeElement({ tag: "div", text: "Current automatic request." }),
                    new FakeElement({ tag: "div", text: "Please review the visible placement." }),
                    new FakeElement({ tag: "div", text: "Best regards" }),
                    new FakeElement({ tag: "div", text: "Synthetic Team" }),
                    recentQuote,
                  ],
                  aggregateText: true,
                });
                const subject = new FakeElement({
                  tag: "span",
                  id: "subject",
                  className: "sub_title s0",
                  text: "Re: Synthetic placement request",
                });
                const header = new FakeElement({
                  className: "readmailinfo",
                  text: [
                    "\u53d1\u4ef6\u4eba\uff1a Synthetic Current <current@example.test>",
                    "\u65f6   \u95f4\uff1a",
                    "2026-07-12 11:00",
                    "\u6536\u4ef6\u4eba\uff1a",
                    "Synthetic Team <team@example.test>; Synthetic Buyer <buyer@example.test>",
                    "\u6284   \u9001\uff1a",
                    "Synthetic Copy <copy@example.test>",
                  ].join("\n"),
                  children: [subject],
                  aggregateText: true,
                });
                const mainMail = new FakeElement({
                  id: "mainmail",
                  children: [header, currentRoot],
                  aggregateText: true,
                });
                const realShapeDoc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [mainMail],
                  aggregateText: true,
                }));
                const fixture = mainFrameFixture();
                fixture.frameWindow.document = realShapeDoc;

                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                const expectedCurrent = [
                  "Current automatic request.",
                  "",
                  "Please review the visible placement.",
                ].join("\n");
                if (result.payload.body_text !== expectedCurrent) {
                  throw new Error(`real-shape current body mismatch: ${JSON.stringify(result)}`);
                }
                if (
                  result.payload.thread_segments.length !== 2 ||
                  result.payload.thread_segments[0].from !== "buyer@example.test" ||
                  result.payload.thread_segments[1].from !== "sales@example.test"
                ) {
                  throw new Error(`real-shape history mismatch: ${JSON.stringify(result)}`);
                }
                if (
                  result.payload.from !== "Synthetic Current <current@example.test>" ||
                  result.payload.sent_at !== "2026-07-12 11:00" ||
                  result.payload.to[0] !== "Synthetic Team <team@example.test>" ||
                  result.payload.to[1] !== "Synthetic Buyer <buyer@example.test>" ||
                  result.payload.cc[0] !== "Synthetic Copy <copy@example.test>"
                ) {
                  throw new Error(`real-shape header mismatch: ${JSON.stringify(result)}`);
                }
              },

              linked_signature_after_rule_is_excluded_with_leading_salutation: async () => {
                const oldestQuote = new FakeElement({
                  tag: "blockquote",
                  text: oldestText,
                  aggregateText: true,
                });
                const signature = new FakeElement({
                  tag: "div",
                  children: [
                    new FakeElement({ tag: "span", text: "Synthetic Sender" }),
                    new FakeElement({
                      tag: "a",
                      text: "Synthetic Company",
                      attrs: { href: "https://example.test" },
                    }),
                  ],
                  aggregateText: true,
                });
                const currentRoot = new FakeElement({
                  id: "mailContentContainer",
                  className: "qmbox",
                  children: [
                    new FakeElement({ tag: "div", text: "Hello Buyer," }),
                    new FakeElement({ tag: "div", text: "Please review the visible placement." }),
                    new FakeElement({ tag: "div", text: "" }),
                    new FakeElement({ tag: "hr" }),
                    signature,
                    oldestQuote,
                  ],
                  aggregateText: true,
                });
                const subject = new FakeElement({
                  tag: "span",
                  id: "subject",
                  className: "sub_title s0",
                  text: "Re: Synthetic placement request",
                });
                const header = new FakeElement({
                  className: "readmailinfo",
                  text: [
                    "From: Synthetic Sender <sender@example.test>",
                    "Date: 2026-07-12 11:00",
                    "To: Synthetic Buyer <buyer@example.test>",
                  ].join("\n"),
                  children: [subject],
                  aggregateText: true,
                });
                const mainMail = new FakeElement({
                  id: "mainmail",
                  children: [header, currentRoot],
                  aggregateText: true,
                });
                const realShapeDoc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [mainMail],
                  aggregateText: true,
                }));
                const fixture = mainFrameFixture();
                fixture.frameWindow.document = realShapeDoc;

                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok || result.payload.body_text !== "Please review the visible placement.") {
                  throw new Error(`linked signature or salutation survived: ${JSON.stringify(result)}`);
                }
                for (const forbidden of ["Hello Buyer", "Synthetic Sender", "Synthetic Company"]) {
                  if (result.payload.body_text.includes(forbidden)) {
                    throw new Error(`private signature content survived: ${forbidden}`);
                  }
                }
              },

              non_qm_body_with_sibling_history_keeps_current_body: async () => {
                const fixture = mainFrameFixture({ knownBody: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    "Current automatic request.\nPlease review the visible placement." ||
                  result.payload.thread_segments.length !== 2
                ) {
                  throw new Error(`sibling history replaced current body: ${JSON.stringify(result)}`);
                }
              },

              message_authored_header_inside_body_is_rejected: async () => {
                const fixture = mainFrameFixture({ headerInsideBody: true, omitHistory: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`message-authored header was trusted: ${JSON.stringify(result)}`);
                }
              },

              message_authored_history_inside_current_body_is_ignored: async () => {
                const fixture = mainFrameFixture({ bodyInjectedHistory: true, omitHistory: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    "Current automatic request.\nPlease review the visible placement." ||
                  result.payload.thread_segments.length !== 0
                ) {
                  throw new Error(`message-authored history was trusted: ${JSON.stringify(result)}`);
                }
              },

              message_authored_history_inside_non_qm_body_is_ignored: async () => {
                const fixture = mainFrameFixture({
                  knownBody: true,
                  bodyInjectedHistory: true,
                  omitHistory: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    "Current automatic request.\nPlease review the visible placement." ||
                  result.payload.thread_segments.length !== 0
                ) {
                  throw new Error(`non-qm authored history was trusted: ${JSON.stringify(result)}`);
                }
              },

              unparseable_authored_history_inside_body_is_ignored: async () => {
                const fixture = mainFrameFixture({
                  bodyInjectedUnparseableHistory: true,
                  omitHistory: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    "Current automatic request.\nPlease review the visible placement." ||
                  result.payload.thread_segments.length !== 0
                ) {
                  throw new Error(`unparseable authored history escaped: ${JSON.stringify(result)}`);
                }
              },

              verified_header_supplies_metadata_instead_of_page_lines: async () => {
                const fixture = mainFrameFixture({ leadingMetadata: true, omitHistory: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.from !== "current@example.test" ||
                  result.payload.to[0] !== "team@example.test" ||
                  result.payload.sent_at !== "2026-07-12 11:00"
                ) {
                  throw new Error(`unverified page metadata won: ${JSON.stringify(result)}`);
                }
              },

              authored_heading_does_not_ambiguate_verified_subject: async () => {
                const fixture = mainFrameFixture({ bodyHeading: true, omitHistory: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok || !result.payload.body_text.includes("Current automatic request.")) {
                  throw new Error(`authored heading blocked verified subject: ${JSON.stringify(result)}`);
                }
              },

              nested_authored_body_does_not_replace_verified_outer_body: async () => {
                const fixture = mainFrameFixture({
                  nestedKnownBody: true,
                  legitimateNestedText: true,
                  omitHistory: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    [
                      "Current automatic request.",
                      "Please review the visible placement.",
                      "Legitimate nested paragraph.",
                    ].join("\n")
                ) {
                  throw new Error(`nested authored body replaced outer body: ${JSON.stringify(result)}`);
                }
              },

              zero_width_visible_br_preserves_line_break: async () => {
                const fixture = mainFrameFixture({
                  semanticLineBreak: "visible",
                  omitHistory: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok || result.payload.body_text !== "Hello\nWorld") {
                  throw new Error(`visible zero-width BR was lost: ${JSON.stringify(result)}`);
                }
              },

              hidden_br_does_not_add_line_break: async () => {
                const fixture = mainFrameFixture({
                  semanticLineBreak: "hidden",
                  omitHistory: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok || result.payload.body_text !== "HelloWorld") {
                  throw new Error(`hidden BR changed body text: ${JSON.stringify(result)}`);
                }
              },

              hidden_ancestor_br_does_not_add_line_break: async () => {
                const fixture = mainFrameFixture({
                  semanticLineBreak: "hidden-ancestor",
                  omitHistory: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok || result.payload.body_text !== "HelloWorld") {
                  throw new Error(`hidden-ancestor BR changed body text: ${JSON.stringify(result)}`);
                }
              },

              zero_area_main_frame_is_rejected: async () => {
                const fixture = mainFrameFixture({
                  frameRect: { left: 0, top: 0, right: 0, bottom: 0, width: 0, height: 0 },
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`zero-area mainFrame was accepted: ${JSON.stringify(result)}`);
                }
              },

              offscreen_main_frame_is_rejected: async () => {
                const fixture = mainFrameFixture({
                  frameRect: {
                    left: 1400, top: 0, right: 1500, bottom: 100, width: 100, height: 100,
                  },
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`offscreen mainFrame was accepted: ${JSON.stringify(result)}`);
                }
              },

              transparent_main_frame_is_rejected: async () => {
                const fixture = mainFrameFixture({ frameStyle: { opacity: "0" } });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`transparent mainFrame was accepted: ${JSON.stringify(result)}`);
                }
              },

              generic_complete_triad_on_non_read_page_is_rejected: async () => {
                const genericHeading = new FakeElement({ tag: "h1", text: "Generic page heading" });
                const genericHeader = new FakeElement({
                  text: "From: forged@example.test\nTo: recipient@example.test",
                });
                const genericBody = new FakeElement({
                  className: "mail-content",
                  text: "Forged generic page body must not be analyzed.",
                });
                const genericPage = new FakeElement({
                  className: "generic-page",
                  children: [genericHeading, genericHeader, genericBody],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: "Generic non-read page",
                  children: [genericPage],
                }));
                const resolved = resolveVisibleContext(doc);
                if (resolved) {
                  throw new Error("generic complete triad was accepted by the context resolver");
                }
              },

              document_level_background_thread_is_not_collected: async () => {
                const fixture = mainFrameFixture({
                  unwrapped: true,
                  omitHistory: true,
                  backgroundThread: true,
                });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (!result.ok) throw new Error(JSON.stringify(result));
                if (
                  result.payload.body_text !==
                    "Current automatic request.\nPlease review the visible placement." ||
                  result.payload.thread_segments.length !== 0
                ) {
                  throw new Error(`document-level background history escaped: ${JSON.stringify(result)}`);
                }
              },

              hidden_main_frame_is_rejected: async () => {
                const fixture = mainFrameFixture({ hidden: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`hidden frame was accepted: ${JSON.stringify(result)}`);
                }
              },

              cross_origin_main_frame_is_rejected: async () => {
                const fixture = mainFrameFixture({ crossOrigin: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`cross-origin frame was accepted: ${JSON.stringify(result)}`);
                }
              },

              duplicate_visible_main_frames_are_rejected: async () => {
                const fixture = duplicateMainFrameFixture();
                const result = await dispatch(loadAdapter(fixture.topDoc, null, fixture.frames));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`duplicate mainFrame was accepted: ${JSON.stringify(result)}`);
                }
              },

              missing_header_main_frame_is_rejected: async () => {
                const fixture = mainFrameFixture({ missingHeader: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`header-free frame was accepted: ${JSON.stringify(result)}`);
                }
              },

              stale_main_frame_discards_collected_content: async () => {
                const fixture = mainFrameFixture({ knownBody: true });
                const collector = {
                  extractVisibleMessageContext: () => {
                    fixture.frameElement.contentWindow = {
                      document: legacyFrameDocument({ knownBody: true }).doc,
                      frameElement: fixture.frameElement,
                      frames: [],
                    };
                    return {
                      current_message: { body_text: "COLLECTED CONTENT MUST BE DISCARDED" },
                      thread_segments: [{
                        position: 0,
                        from: "unsafe@example.test",
                        to: "recipient@example.test",
                        sent_at: "",
                        timestamp_text: "",
                        subject: "Unsafe",
                        body_text: "STALE THREAD MUST BE DISCARDED",
                      }],
                    };
                  },
                  collectVisibleResources: async () => ({
                    attachment_files: [], resource_limitations: [],
                  }),
                };
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  collector,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`stale content survived: ${JSON.stringify(result)}`);
                }
              },

              ambiguous_visible_bodies_are_rejected: async () => {
                const fixture = mainFrameFixture({ duplicateBodies: true });
                const result = await dispatch(loadAdapter(
                  fixture.topDoc,
                  null,
                  [fixture.frameWindow],
                ));
                if (result.ok || Object.prototype.hasOwnProperty.call(result, "payload")) {
                  throw new Error(`ambiguous bodies were accepted: ${JSON.stringify(result)}`);
                }
              },

              newest_first_is_normalized_and_current_metadata_wins: async () => {
                const { doc } = legacyDocument("newest-first");
                assertNormalizedResult(await dispatch(loadAdapter(doc)));
              },

              oldest_first_is_normalized_and_current_metadata_wins: async () => {
                const { doc } = legacyDocument("oldest-first");
                assertNormalizedResult(await dispatch(loadAdapter(doc)));
              },

              chinese_headers_allow_a_leading_optional_header: () => {
                const text = [
                  "\u6284\u9001\uff1aobserver@example.test",
                  "\u53d1\u4ef6\u4eba\uff1abuyer@example.test",
                  "\u53d1\u9001\u65f6\u95f4\uff1a2026-07-12 08:30",
                  "\u6536\u4ef6\u4eba\uff1asales@example.test",
                  "\u4e3b\u9898\uff1a\u5408\u6210\u4ea4\u671f\u786e\u8ba4",
                  "\u8bf7\u786e\u8ba4\u4ea4\u671f\u3002",
                  "\u795d\u597d",
                  "\u5408\u6210\u56e2\u961f",
                ].join("\n");
                const root = new FakeElement({
                  className: "mail-content",
                  text,
                  children: [block(text)],
                });
                const doc = new FakeDocument(new FakeElement({ tag: "body", text, children: [root] }));
                const context = loadCollector().extractVisibleMessageContext(
                  doc,
                  { currentMessageRoot: root },
                );
                if (context.thread_segments.length !== 1) {
                  throw new Error(`Chinese headers were not parsed: ${JSON.stringify(context)}`);
                }
                const segment = context.thread_segments[0];
                if (
                  segment.from !== "buyer@example.test" ||
                  segment.subject !== "\u5408\u6210\u4ea4\u671f\u786e\u8ba4" ||
                  segment.body_text !== "\u8bf7\u786e\u8ba4\u4ea4\u671f\u3002"
                ) {
                  throw new Error(`Chinese context mismatch: ${JSON.stringify(context)}`);
                }
              },

              unreliable_blocks_fail_closed_to_explicit_current_body: async () => {
                const currentOnly = new FakeElement({
                  className: "mail-current-body",
                  text: [
                    "Current safe request line one.",
                    "Current safe request line two.",
                    "Best regards",
                    "Synthetic Team",
                    "Website: https://example.test",
                  ].join("\n"),
                });
                const ambiguous = block([
                  "From: first@example.test",
                  "From: duplicate@example.test",
                  "Date: 2026-07-11 10:30",
                  "To: buyer@example.test",
                  "Subject: Ambiguous synthetic request",
                  "UNSAFE WHOLE ROOT HISTORY",
                ].join("\n"), { children: [currentOnly] });
                const root = new FakeElement({
                  className: "mail-content",
                  text: `${ambiguous.innerText}\nUNSAFE WHOLE ROOT HISTORY`,
                  children: [ambiguous],
                });
                const subject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic" });
                const envelope = new FakeElement({
                  className: "read-envelope",
                  children: [subject, syntheticHeader(), root],
                });
                const body = new FakeElement({
                  tag: "body",
                  text: `${subject.innerText}\n${root.innerText}`,
                  children: [envelope],
                });
                const result = await dispatch(loadAdapter(new FakeDocument(body)));
                if (!result.ok || result.payload.thread_segments.length !== 0) {
                  throw new Error(`ambiguous segmentation did not fail closed: ${JSON.stringify(result)}`);
                }
                const expected = "Current safe request line one.\nCurrent safe request line two.";
                if (result.payload.body_text !== expected) {
                  throw new Error(`current-only fallback mismatch: ${JSON.stringify(result.payload.body_text)}`);
                }
                if (JSON.stringify(result.payload).includes("UNSAFE WHOLE ROOT HISTORY")) {
                  throw new Error("whole-root history leaked into current-only payload");
                }
              },

              partial_history_and_collector_errors_never_keep_whole_root: async () => {
                const partialHistory = [
                  "Current request must not be inferred from this mixed root.",
                  "Sender: history@example.test",
                  "Old history must not survive.",
                ].join("\n");
                const unsafeRoot = new FakeElement({ className: "mail-content", text: partialHistory });
                const unsafeSubject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic" });
                const unsafeBody = new FakeElement({
                  tag: "body",
                  text: `Synthetic\n${partialHistory}`,
                  children: [unsafeSubject, syntheticHeader(), unsafeRoot],
                });
                const unsafeDoc = new FakeDocument(unsafeBody);
                const context = loadCollector().extractVisibleMessageContext(
                  unsafeDoc,
                  { currentMessageRoot: unsafeRoot },
                );
                if (context.thread_segments.length || context.current_message.body_text) {
                  throw new Error(`partial history reached fallback: ${JSON.stringify(context)}`);
                }

                const plainRoot = new FakeElement({
                  className: "mail-content",
                  text: "Plain root text is not explicit current-body provenance.",
                });
                const plainDoc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: plainRoot.innerText,
                  children: [plainRoot],
                }));
                const plainContext = loadCollector().extractVisibleMessageContext(
                  plainDoc,
                  { currentMessageRoot: plainRoot },
                );
                if (plainContext.current_message.body_text) {
                  throw new Error(`plain root was treated as current-only: ${JSON.stringify(plainContext)}`);
                }

                const throwingCollector = {
                  extractVisibleMessageContext: () => { throw new Error("synthetic failure"); },
                  collectVisibleResources: async () => ({ attachment_files: [], resource_limitations: [] }),
                };
                const failed = await dispatch(loadAdapter(unsafeDoc, throwingCollector));
                if (failed.ok || Object.prototype.hasOwnProperty.call(failed, "payload")) {
                  throw new Error(`collector error returned empty success: ${JSON.stringify(failed)}`);
                }

                const emptyCollector = {
                  extractVisibleMessageContext: () => ({
                    current_message: { body_text: "" },
                    thread_segments: [],
                  }),
                  collectVisibleResources: async () => ({
                    attachment_files: [],
                    resource_limitations: [],
                  }),
                };
                const emptied = await dispatch(loadAdapter(unsafeDoc, emptyCollector));
                if (emptied.ok || Object.prototype.hasOwnProperty.call(emptied, "payload")) {
                  throw new Error(`empty collector body returned success: ${JSON.stringify(emptied)}`);
                }

                const explicit = new FakeElement({
                  className: "mail-current-body",
                  text: "Only this current request may survive.",
                });
                const mixedRoot = new FakeElement({
                  className: "mail-content",
                  text: partialHistory,
                  children: [explicit],
                });
                const mixedSubject = new FakeElement({ tag: "h1", id: "subject", text: "Synthetic" });
                const mixedBody = new FakeElement({
                  tag: "body",
                  text: `Synthetic\n${partialHistory}`,
                  children: [mixedSubject, syntheticHeader(), mixedRoot],
                });
                const explicitResult = await dispatch(
                  loadAdapter(new FakeDocument(mixedBody), throwingCollector),
                );
                if (explicitResult.payload.body_text !== "Only this current request may survive.") {
                  throw new Error(`explicit current body lost on error: ${JSON.stringify(explicitResult)}`);
                }

                const verifiedRoot = new FakeElement({
                  className: "mail-content",
                  text: "Verified current-only request.",
                });
                const verifiedSubject = new FakeElement({
                  tag: "h1",
                  id: "subject",
                  text: "Verified synthetic request",
                });
                const verifiedBody = new FakeElement({
                  tag: "body",
                  text: "Verified synthetic request\nVerified current-only request.",
                  children: [verifiedSubject, syntheticHeader(), verifiedRoot],
                });
                const verifiedResult = await dispatch(
                  loadAdapter(new FakeDocument(verifiedBody), throwingCollector),
                );
                if (
                  verifiedResult.ok ||
                  Object.prototype.hasOwnProperty.call(verifiedResult, "payload")
                ) {
                  throw new Error(`heuristic currentRoot returned empty success: ${JSON.stringify(verifiedResult)}`);
                }
              },

              historical_candidates_do_not_replace_explicit_current_body: async () => {
                const currentOnly = new FakeElement({
                  className: "mail-current-body",
                  text: "Current standalone request.\nSecond current line.",
                });
                const rootText = `${currentOnly.innerText}\n${newestText}\n${oldestText}`;
                const root = new FakeElement({
                  className: "mail-content",
                  text: rootText,
                  children: [currentOnly, block(newestText), block(oldestText)],
                });
                const subject = new FakeElement({ tag: "h1", id: "subject", text: "Current subject" });
                const header = new FakeElement({
                  className: "read-header",
                  text: [
                    "From: current@example.test",
                    "Date: 2026-07-12 09:00",
                    "To: team@example.test",
                  ].join("\n"),
                });
                const envelope = new FakeElement({
                  className: "read-envelope",
                  children: [subject, header, root],
                });
                const body = new FakeElement({
                  tag: "body",
                  text: `${subject.innerText}\n${header.innerText}\n${rootText}`,
                  children: [envelope],
                });
                const result = await dispatch(loadAdapter(new FakeDocument(body)));
                if (!result.ok || result.payload.thread_segments.length !== 2) {
                  throw new Error(`historical thread lost: ${JSON.stringify(result)}`);
                }
                if (result.payload.body_text !== "Current standalone request.\nSecond current line.") {
                  throw new Error(`history replaced current body: ${JSON.stringify(result.payload)}`);
                }
                if (
                  result.payload.from !== "current@example.test" ||
                  result.payload.subject !== "Current subject"
                ) {
                  throw new Error(`historical metadata replaced current metadata: ${JSON.stringify(result.payload)}`);
                }
              },

              common_signature_boundaries_are_removed_conservatively: () => {
                const clean = loadCollector().cleanVisibleMessageBody;
                const variants = [
                  "Action remains.\nThanks & Regards\nSynthetic Name\nSynthetic Title\nM: +1 555 0100\nwww.example.test",
                  "Action remains.\nThanks and regards\nSynthetic Name\nhttps://example.test/profile",
                  "Action remains.\nM: +1 555 0100\nMobile No: +1 555 0101\nhttps://example.test\nwww.example.test",
                ];
                for (const value of variants) {
                  const cleaned = clean(value);
                  if (cleaned !== "Action remains.") {
                    throw new Error(`signature residue: ${JSON.stringify(cleaned)}`);
                  }
                }
                const ordinary = [
                  "Please keep these technical notes.",
                  "M: material grade 304",
                  "Website: customer portal must remain active",
                ].join("\n");
                if (clean(ordinary) !== ordinary) {
                  throw new Error(`ordinary body line removed: ${JSON.stringify(clean(ordinary))}`);
                }
              },

              structured_segments_use_explicit_positions_and_known_fields: () => {
                const newest = structuredBlock({
                  "data-position": "1",
                  "data-from": "sales@example.test",
                  "data-to": "buyer@example.test",
                  "data-sent-at": "Today",
                  "data-timestamp-text": "Today",
                  "data-subject": "Re: Structured",
                  "data-body-text": "Structured answer\nSecond line",
                });
                const oldest = structuredBlock({
                  "data-position": "0",
                }, [
                  new FakeElement({ className: "mail-sender", text: "buyer@example.test" }),
                  new FakeElement({ className: "mail-recipient", text: "sales@example.test" }),
                  new FakeElement({ tag: "time", text: "Yesterday" }),
                  new FakeElement({ className: "mail-subject", text: "Structured" }),
                  new FakeElement({ className: "mail-body", text: "Structured request" }),
                ]);
                const root = new FakeElement({
                  className: "mail-content",
                  text: "unsafe aggregate root",
                  children: [newest, oldest],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: "unsafe aggregate root",
                  children: [root],
                }));
                const context = loadCollector().extractVisibleMessageContext(
                  doc,
                  { currentMessageRoot: root },
                );
                if (context.thread_segments.length !== 2) {
                  throw new Error(`structured path missing: ${JSON.stringify(context)}`);
                }
                const [first, second] = context.thread_segments;
                if (
                  first.position !== 0 || first.from !== "buyer@example.test" ||
                  first.body_text !== "Structured request" ||
                  second.position !== 1 || second.from !== "sales@example.test" ||
                  second.body_text !== "Structured answer\nSecond line" ||
                  context.current_message.body_text !== "Structured answer\nSecond line"
                ) {
                  throw new Error(`structured projection mismatch: ${JSON.stringify(context)}`);
                }
              },

              missing_duplicate_hidden_and_oversized_blocks_fail_safely: () => {
                const api = loadCollector();
                const invalidTexts = [
                  oldestText.replace("From: buyer@example.test\n", ""),
                  oldestText.replace("Date: 2026-07-10 09:00\n", ""),
                  oldestText.replace("To: sales@example.test\n", ""),
                  oldestText.replace("Subject: Synthetic placement request\n", ""),
                  oldestText.replace(
                    "From: buyer@example.test",
                    "From: buyer@example.test\nFrom: duplicate@example.test",
                  ),
                ];
                for (const text of invalidTexts) {
                  const root = new FakeElement({
                    className: "mail-content",
                    text,
                    children: [block(text)],
                  });
                  const doc = new FakeDocument(new FakeElement({ tag: "body", text, children: [root] }));
                  const context = api.extractVisibleMessageContext(doc, { currentMessageRoot: root });
                  if (context.thread_segments.length !== 0) {
                    throw new Error(`invalid headers produced a thread: ${JSON.stringify(context)}`);
                  }
                }

                const hidden = block([
                  "From: hidden@example.test",
                  "Date: 2026-07-12 12:00",
                  "To: hidden-recipient@example.test",
                  "Subject: Hidden synthetic message",
                  "Hidden body",
                ].join("\n"), { hidden: true });
                const { doc, root } = legacyDocument("newest-first", [hidden]);
                const context = api.extractVisibleMessageContext(doc, { currentMessageRoot: root });
                if (context.thread_segments.length !== 2 || context.current_message.from !== "sales@example.test") {
                  throw new Error(`hidden block changed visible chronology: ${JSON.stringify(context)}`);
                }

                const tooMany = Array.from({ length: 51 }, (_item, index) => block([
                  `From: sender${index}@example.test`,
                  `Date: 2026-06-${String((index % 28) + 1).padStart(2, "0")} 09:00`,
                  "To: recipient@example.test",
                  `Subject: Synthetic ${index}`,
                  `Body ${index}`,
                ].join("\n")));
                const rootText = tooMany.map((item) => item.innerText).join("\n");
                const boundedRoot = new FakeElement({
                  className: "mail-content",
                  text: rootText,
                  children: tooMany,
                });
                const boundedDoc = new FakeDocument(new FakeElement({
                  tag: "body",
                  text: rootText,
                  children: [boundedRoot],
                }));
                const bounded = api.extractVisibleMessageContext(
                  boundedDoc,
                  { currentMessageRoot: boundedRoot },
                );
                if (bounded.thread_segments.length !== 0) {
                  throw new Error("over-limit thread did not fail closed");
                }
              },
            };

            (async () => {
              const caseName = __CASE_NAME__;
              if (!Object.prototype.hasOwnProperty.call(cases, caseName)) {
                throw new Error(`Unknown case: ${caseName}`);
              }
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
        script = script.replace("__CASE_NAME__", json.dumps(case_name))
        result = subprocess.run(
            ["node", "-"],
            cwd=ROOT,
            input=script,
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_newest_first_is_normalized_and_current_metadata_wins(self) -> None:
        self.run_node_case("newest_first_is_normalized_and_current_metadata_wins")

    def test_oldest_first_is_normalized_and_current_metadata_wins(self) -> None:
        self.run_node_case("oldest_first_is_normalized_and_current_metadata_wins")

    def test_chinese_headers_allow_a_leading_optional_header(self) -> None:
        self.run_node_case("chinese_headers_allow_a_leading_optional_header")

    def test_unreliable_blocks_fail_closed_to_explicit_current_body(self) -> None:
        self.run_node_case("unreliable_blocks_fail_closed_to_explicit_current_body")

    def test_partial_history_and_collector_errors_never_keep_whole_root(self) -> None:
        self.run_node_case("partial_history_and_collector_errors_never_keep_whole_root")

    def test_historical_candidates_do_not_replace_explicit_current_body(self) -> None:
        self.run_node_case("historical_candidates_do_not_replace_explicit_current_body")

    def test_common_signature_boundaries_are_removed_conservatively(self) -> None:
        self.run_node_case("common_signature_boundaries_are_removed_conservatively")

    def test_structured_segments_use_explicit_positions_and_known_fields(self) -> None:
        self.run_node_case("structured_segments_use_explicit_positions_and_known_fields")

    def test_missing_duplicate_hidden_and_oversized_blocks_fail_safely(self) -> None:
        self.run_node_case("missing_duplicate_hidden_and_oversized_blocks_fail_safely")

    def test_legacy_main_frame_extracts_current_body_and_full_history(self) -> None:
        self.run_node_case("legacy_main_frame_extracts_current_body_and_full_history")

    def test_legacy_qmbox_sibling_download_control_reaches_verified_collector(self) -> None:
        self.run_node_case("legacy_qmbox_sibling_download_control_reaches_verified_collector")

    def test_legacy_qmbox_sibling_invalid_controls_never_reach_collector(self) -> None:
        self.run_node_case("legacy_qmbox_sibling_invalid_controls_never_reach_collector")

    def test_real_readmailinfo_nested_quotes_extract_current_body_and_history(self) -> None:
        self.run_node_case(
            "real_readmailinfo_nested_quotes_extract_current_body_and_history"
        )

    def test_linked_signature_after_rule_is_excluded_with_leading_salutation(self) -> None:
        self.run_node_case(
            "linked_signature_after_rule_is_excluded_with_leading_salutation"
        )

    def test_non_qm_body_with_sibling_history_keeps_current_body(self) -> None:
        self.run_node_case("non_qm_body_with_sibling_history_keeps_current_body")

    def test_message_authored_header_inside_body_is_rejected(self) -> None:
        self.run_node_case("message_authored_header_inside_body_is_rejected")

    def test_message_authored_history_inside_current_body_is_ignored(self) -> None:
        self.run_node_case("message_authored_history_inside_current_body_is_ignored")

    def test_message_authored_history_inside_non_qm_body_is_ignored(self) -> None:
        self.run_node_case("message_authored_history_inside_non_qm_body_is_ignored")

    def test_unparseable_authored_history_inside_body_is_ignored(self) -> None:
        self.run_node_case("unparseable_authored_history_inside_body_is_ignored")

    def test_verified_header_supplies_metadata_instead_of_page_lines(self) -> None:
        self.run_node_case("verified_header_supplies_metadata_instead_of_page_lines")

    def test_authored_heading_does_not_ambiguate_verified_subject(self) -> None:
        self.run_node_case("authored_heading_does_not_ambiguate_verified_subject")

    def test_nested_authored_body_does_not_replace_verified_outer_body(self) -> None:
        self.run_node_case("nested_authored_body_does_not_replace_verified_outer_body")

    def test_zero_width_visible_br_preserves_line_break(self) -> None:
        self.run_node_case("zero_width_visible_br_preserves_line_break")

    def test_hidden_br_does_not_add_line_break(self) -> None:
        self.run_node_case("hidden_br_does_not_add_line_break")

    def test_hidden_ancestor_br_does_not_add_line_break(self) -> None:
        self.run_node_case("hidden_ancestor_br_does_not_add_line_break")

    def test_zero_area_main_frame_is_rejected(self) -> None:
        self.run_node_case("zero_area_main_frame_is_rejected")

    def test_offscreen_main_frame_is_rejected(self) -> None:
        self.run_node_case("offscreen_main_frame_is_rejected")

    def test_transparent_main_frame_is_rejected(self) -> None:
        self.run_node_case("transparent_main_frame_is_rejected")

    def test_generic_complete_triad_on_non_read_page_is_rejected(self) -> None:
        self.run_node_case("generic_complete_triad_on_non_read_page_is_rejected")

    def test_document_level_background_thread_is_not_collected(self) -> None:
        self.run_node_case("document_level_background_thread_is_not_collected")

    def test_hidden_main_frame_is_rejected(self) -> None:
        self.run_node_case("hidden_main_frame_is_rejected")

    def test_cross_origin_main_frame_is_rejected(self) -> None:
        self.run_node_case("cross_origin_main_frame_is_rejected")

    def test_duplicate_visible_main_frames_are_rejected(self) -> None:
        self.run_node_case("duplicate_visible_main_frames_are_rejected")

    def test_missing_header_main_frame_is_rejected(self) -> None:
        self.run_node_case("missing_header_main_frame_is_rejected")

    def test_stale_main_frame_discards_collected_content(self) -> None:
        self.run_node_case("stale_main_frame_discards_collected_content")

    def test_ambiguous_visible_bodies_are_rejected(self) -> None:
        self.run_node_case("ambiguous_visible_bodies_are_rejected")


if __name__ == "__main__":
    unittest.main()
