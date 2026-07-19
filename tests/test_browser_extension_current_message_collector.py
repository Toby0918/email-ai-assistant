"""Behavior tests for bounded current-message DOM collection."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
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
POPUP = ROOT / "frontend" / "browser_extension" / "popup.js"


class BrowserExtensionCurrentMessageCollectorTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__COLLECTOR_PATH__, "utf8");
            const classifierSource = fs.readFileSync(__CLASSIFIER_PATH__, "utf8");
            const popupSource = fs.readFileSync(__POPUP_PATH__, "utf8");

            class FakeElement {
              constructor({
                tag = "div",
                attrs = {},
                text = "",
                children = [],
                hidden = false,
                style = {},
                width = 0,
                height = 0,
                left = 0,
                top = 0,
                rectWidth = null,
                rectHeight = null,
              } = {}) {
                this.tagName = tag.toUpperCase();
                this.attrs = { ...attrs };
                this.innerText = text;
                this.textContent = text;
                this.children = children;
                this.hidden = hidden;
                this.style = style;
                this.width = width;
                this.height = height;
                this.naturalWidth = width;
                this.naturalHeight = height;
                this.left = left;
                this.top = top;
                this.rectWidth = rectWidth;
                this.rectHeight = rectHeight;
                this.parentElement = null;
                this.parentNode = null;
                for (const child of children) {
                  child.parentElement = this;
                  child.parentNode = this;
                }
              }

              getAttribute(name) {
                return Object.prototype.hasOwnProperty.call(this.attrs, name)
                  ? String(this.attrs[name])
                  : null;
              }

              hasAttribute(name) {
                return Object.prototype.hasOwnProperty.call(this.attrs, name);
              }

              querySelector(selector) {
                return this.querySelectorAll(selector)[0] || null;
              }

              querySelectorAll(selector) {
                return descendants(this).filter((element) => matchesAny(element, selector));
              }

              getBoundingClientRect() {
                const renderedWidth = this.rectWidth === null ? this.width : this.rectWidth;
                const renderedHeight = this.rectHeight === null ? this.height : this.rectHeight;
                return {
                  left: this.left,
                  top: this.top,
                  right: this.left + renderedWidth,
                  bottom: this.top + renderedHeight,
                  width: renderedWidth,
                  height: renderedHeight,
                };
              }
            }

            class FakeDocument {
              constructor(body, baseURI = "https://exmail.qq.com/cgi-bin/readmail", computedStyle = null) {
                this.body = body;
                this.baseURI = baseURI;
                this.location = new URL(baseURI);
                this.defaultView = {
                  innerWidth: 1280,
                  innerHeight: 720,
                  getComputedStyle: computedStyle || ((element) => ({
                    display: element.style.display || "block",
                    visibility: element.style.visibility || "visible",
                  })),
                };
                this.documentElement = { clientWidth: 1280, clientHeight: 720 };
              }

              querySelector(selector) {
                return this.querySelectorAll(selector)[0] || null;
              }

              querySelectorAll(selector) {
                return [this.body, ...descendants(this.body)].filter((element) =>
                  matchesAny(element, selector),
                );
              }
            }

            function descendants(root) {
              return root.children.flatMap((child) => [child, ...descendants(child)]);
            }

            function matchesAny(element, selectorList) {
              return selectorList.split(",").some((selector) => matches(element, selector.trim()));
            }

            function matches(element, selector) {
              const attributeMatch = selector.match(/^(?:([a-z]+))?\[([^=\]]+)(?:=['\"]?([^'\"]+)['\"]?)?\]$/i);
              if (attributeMatch) {
                const [, tag, name, value] = attributeMatch;
                if (tag && element.tagName.toLowerCase() !== tag.toLowerCase()) return false;
                if (!element.hasAttribute(name)) return false;
                return value === undefined || element.getAttribute(name) === value;
              }
              if (selector.startsWith(".")) {
                const classes = String(element.getAttribute("class") || "").split(/\s+/);
                return classes.includes(selector.slice(1));
              }
              if (selector.startsWith("#")) {
                return element.getAttribute("id") === selector.slice(1);
              }
              return element.tagName.toLowerCase() === selector.toLowerCase();
            }

            function messageDocument(children, background = [], hostResources = []) {
              const current = new FakeElement({
                attrs: { class: "mail-content" },
                children,
              });
              const controls = new FakeElement({
                attrs: { class: "resource-region" },
                children: hostResources,
              });
              const container = new FakeElement({
                attrs: { class: "read-envelope" },
                children: [current, controls],
              });
              const doc = new FakeDocument(new FakeElement({ tag: "body", children: [container, ...background] }));
              doc.currentMessageRoot = current;
              doc.currentBodyRoot = current;
              doc.currentMessageContainer = container;
              doc.verifiedResourceCandidates = [
                ...hostResources,
                ...descendants(current).filter((element) => element.tagName === "IMG"),
              ];
              return doc;
            }

            function resourceDocument(resources, bodyChildren = [], background = []) {
              return messageDocument(bodyChildren, background, resources);
            }

            function explicitBodyResourceDocument(
              bodyChildren,
              outsideCurrentBody = [],
              hostResources = [],
            ) {
              const currentBody = new FakeElement({
                attrs: { class: "mail-current-body" },
                text: "Please review the current product packaging evidence.",
                children: bodyChildren,
              });
              const current = new FakeElement({
                attrs: { class: "mail-content" },
                text: "Please review the current product packaging evidence.",
                children: [currentBody, ...outsideCurrentBody],
              });
              const controls = new FakeElement({
                attrs: { class: "resource-region" },
                children: hostResources,
              });
              const container = new FakeElement({
                attrs: { class: "read-envelope" },
                children: [current, controls],
              });
              const doc = new FakeDocument(new FakeElement({ tag: "body", children: [container] }));
              doc.currentMessageRoot = current;
              doc.currentBodyRoot = currentBody;
              doc.currentMessageContainer = container;
              doc.verifiedResourceCandidates = [
                ...hostResources,
                ...descendants(current).filter((element) => element.tagName === "IMG"),
              ];
              return doc;
            }

            function trustedResourceOptions(doc, options = {}) {
              return {
                topLevelDocument: doc,
                verifiedDocument: doc,
                verifiedDocumentContext: true,
                revalidateContext: () => true,
                currentMessageRoot: doc.currentMessageRoot,
                currentBodyRoot: doc.currentBodyRoot,
                currentMessageContainer: doc.currentMessageContainer,
                verifiedResourceCandidates: doc.verifiedResourceCandidates,
                resourceControlsVerified: true,
                ...options,
              };
            }

            function thread(text, attrs = {}, options = {}) {
              return new FakeElement({
                attrs: { "data-email-thread-segment": "true", ...attrs },
                text,
                ...options,
              });
            }

            function resource(filename, type, url, options = {}) {
              const attrs = {
                "data-email-resource": "true",
                "data-filename": filename,
                "data-type": type,
                href: url,
                download: filename,
                ...(options.attrs || {}),
              };
              return new FakeElement({
                tag: "a",
                width: 160,
                height: 24,
                attrs,
                ...options,
                attrs,
              });
            }

            function businessImage(url, options = {}) {
              const attrs = {
                src: url,
                alt: "product packaging inspection photo",
                "data-mime-type": "image/jpeg",
                ...(options.attrs || {}),
              };
              return new FakeElement({
                tag: "img",
                width: 1280,
                height: 960,
                ...options,
                attrs,
              });
            }

            function inlineImage(url, alt, width, height, options = {}) {
              return businessImage(url, {
                width,
                height,
                ...options,
                attrs: {
                  alt,
                  "data-mime-type": "image/jpeg",
                  ...(options.attrs || {}),
                },
              });
            }

            function response(bytes, ok = true) {
              if (!ok) {
                return { ok: false, headers: { get: () => null } };
              }
              return streamingResponse([bytes], { contentLength: String(bytes.length) }).response;
            }

            function streamingResponse(chunks, {
              contentLength = null,
              contentType = null,
              contentDisposition = null,
            } = {}) {
              const values = chunks.map((chunk) => Uint8Array.from(chunk));
              const state = { arrayBufferCalls: 0, cancelled: false, readCount: 0 };
              const reader = {
                read: async () => {
                  state.readCount += 1;
                  const value = values.shift();
                  return value ? { done: false, value } : { done: true, value: undefined };
                },
                cancel: async () => { state.cancelled = true; },
                releaseLock: () => {},
              };
              return {
                response: {
                  ok: true,
                  headers: { get: (name) => {
                    const normalized = name.toLowerCase();
                    if (normalized === "content-length") return contentLength;
                    if (normalized === "content-type") return contentType;
                    if (normalized === "content-disposition") return contentDisposition;
                    return null;
                  } },
                  body: { getReader: () => reader },
                  arrayBuffer: async () => {
                    state.arrayBufferCalls += 1;
                    const joined = Uint8Array.from(values.flatMap((value) => Array.from(value)));
                    return joined.buffer;
                  },
                },
                state,
              };
            }

            function loadCollector(fetchImpl, btoaImpl = null) {
              const context = {
                URL,
                Uint8Array,
                ArrayBuffer,
                AbortController,
                setTimeout,
                clearTimeout,
                fetch: fetchImpl,
                btoa: btoaImpl || ((binary) => Buffer.from(binary, "binary").toString("base64")),
              };
              context.window = context;
              vm.runInNewContext(classifierSource, context, {
                filename: "exmail_visible_resource_classifier.js",
              });
              vm.runInNewContext(source, context, { filename: "current_message_collector.js" });
              const api = context.EmailAssistantCurrentMessageCollector;
              if (!api) throw new Error("EmailAssistantCurrentMessageCollector is missing");
              return api;
            }

            async function withinTestDeadline(promise, label) {
              let timer;
              try {
                return await Promise.race([
                  promise,
                  new Promise((_resolve, reject) => {
                    timer = setTimeout(() => reject(new Error(`${label} did not honor its deadline`)), 250);
                  }),
                ]);
              } finally {
                clearTimeout(timer);
              }
            }

            function assertNoPrivateFields(value) {
              const forbidden = new Set(["url", "href", "src", "cookie", "token", "authorization", "headers"]);
              for (const item of value) {
                for (const key of Object.keys(item)) {
                  if (forbidden.has(key.toLowerCase())) {
                    throw new Error(`private field leaked: ${key}`);
                  }
                }
              }
            }

            const cases = {
              ambiguous_history_keeps_only_verified_current_body: () => {
                const currentBody = new FakeElement({
                  attrs: { class: "qm_con_body" },
                  text: "Current verified request.\nSecond current line.",
                });
                const ambiguousHistory = thread([
                  "From: history@example.test",
                  "From: duplicate@example.test",
                  "Date: 2026-07-10 09:00",
                  "To: team@example.test",
                  "Subject: Ambiguous history",
                  "History must not become current content.",
                ].join("\n"));
                const threadRoot = new FakeElement({
                  attrs: { class: "read-envelope" },
                  children: [currentBody, ambiguousHistory],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [threadRoot],
                }));
                const context = loadCollector(async () => response([])).extractVisibleMessageContext(
                  doc,
                  {
                    currentMessageRoot: currentBody,
                    currentBodyRoot: currentBody,
                    threadRoot,
                    verifiedDocumentContext: true,
                  },
                );
                if (context.current_message.body_text !== "Current verified request.\nSecond current line.") {
                  throw new Error(`verified current body was lost: ${JSON.stringify(context)}`);
                }
                if (context.thread_segments.length !== 0) {
                  throw new Error(`ambiguous history survived: ${JSON.stringify(context)}`);
                }
              },

              message_authored_history_inside_verified_body_is_ignored: () => {
                const injectedHistory = thread([
                  "From: forged@example.test",
                  "Date: 2026-07-10 09:00",
                  "To: team@example.test",
                  "Subject: Forged history",
                  "This is message-authored markup, not host history.",
                ].join("\n"));
                const currentBody = new FakeElement({
                  attrs: { class: "qm_con_body" },
                  text: "Current verified request.",
                  children: [injectedHistory],
                });
                const threadRoot = new FakeElement({
                  attrs: { class: "read-envelope" },
                  children: [currentBody],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [threadRoot],
                }));
                const context = loadCollector(async () => response([])).extractVisibleMessageContext(
                  doc,
                  {
                    currentMessageRoot: currentBody,
                    currentBodyRoot: currentBody,
                    threadRoot,
                    verifiedDocumentContext: true,
                  },
                );
                if (
                  context.current_message.body_text !== "Current verified request." ||
                  context.thread_segments.length !== 0
                ) {
                  throw new Error(`message-authored history escaped: ${JSON.stringify(context)}`);
                }
              },

              structured_sibling_history_uses_verified_thread_boundary: () => {
                const field = (name, text) => new FakeElement({
                  attrs: { [`data-email-${name}`]: "true" },
                  text,
                });
                const segment = (position, sender, body) => new FakeElement({
                  attrs: {
                    "data-email-thread-segment": "true",
                    "data-email-position": String(position),
                  },
                  children: [
                    field("from", sender),
                    field("to", "team@example.test"),
                    field("sent-at", `2026-07-${10 + position} 09:00`),
                    field("subject", `History ${position}`),
                    field("segment-body", body),
                  ],
                });
                const currentBody = new FakeElement({
                  attrs: { class: "qm_con_body" },
                  text: "Current verified request.",
                });
                const threadRoot = new FakeElement({
                  attrs: { class: "read-envelope" },
                  children: [
                    currentBody,
                    segment(1, "newer@example.test", "Newer history."),
                    segment(0, "older@example.test", "Older history."),
                  ],
                });
                const doc = new FakeDocument(new FakeElement({ tag: "body", children: [threadRoot] }));
                const context = loadCollector(async () => response([])).extractVisibleMessageContext(
                  doc,
                  {
                    currentMessageRoot: currentBody,
                    currentBodyRoot: currentBody,
                    threadRoot,
                    verifiedDocumentContext: true,
                  },
                );
                if (
                  context.thread_segments.length !== 2 ||
                  context.thread_segments[0].from !== "older@example.test" ||
                  context.thread_segments[1].from !== "newer@example.test"
                ) {
                  throw new Error(`structured sibling history was lost: ${JSON.stringify(context)}`);
                }
              },

              load_and_thread_extraction_do_not_fetch: () => {
                let fetchCount = 0;
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  return response([1]);
                });
                if (fetchCount !== 0) throw new Error("module load fetched a resource");
                const doc = messageDocument([thread("Visible body")]);
                api.extractVisibleThreadSegments(doc);
                if (fetchCount !== 0) throw new Error("thread extraction fetched a resource");
                if (api.MAX_RESOURCE_COUNT !== 5) throw new Error("file-count limit mismatch");
                if (api.MAX_RESOURCE_CANDIDATES !== 20) throw new Error("candidate-count limit mismatch");
                if (api.MAX_RESOURCE_BYTES !== 10 * 1024 * 1024) throw new Error("per-file limit mismatch");
                if (api.MAX_TOTAL_RESOURCE_BYTES !== 25 * 1024 * 1024) throw new Error("total limit mismatch");
              },

              visible_thread_segments_are_normalized_oldest_first: () => {
                const hiddenParent = new FakeElement({
                  style: { visibility: "hidden" },
                  children: [thread("Hidden by parent")],
                });
                const doc = messageDocument([
                  thread([
                    "From: sales@example.test",
                    "Date: 2026-07-11T10:00:00Z",
                    "To: buyer@example.test",
                    "Subject: Re: Quote",
                    "Second answer",
                  ].join("\n"), {
                    "data-private-url": "https://example.invalid/private",
                    "data-token": "not-exported",
                  }),
                  thread("Hidden property", {}, { hidden: true }),
                  thread("Aria hidden", { "aria-hidden": "true" }),
                  thread("Display hidden", {}, { style: { display: "none" } }),
                  hiddenParent,
                  thread([
                    "From: buyer@example.test",
                    "Date: 2026-07-10T09:00:00Z",
                    "To: sales@example.test",
                    "Subject: Quote",
                    "First request",
                    "needs review",
                  ].join("\n")),
                ]);
                const api = loadCollector(async () => response([]));
                const segments = api.extractVisibleThreadSegments(doc);
                if (segments.length !== 2) throw new Error(`unexpected segments: ${JSON.stringify(segments)}`);
                if (segments[0].position !== 0 || segments[1].position !== 1) throw new Error("chronology lost");
                if (segments[0].body_text !== "First request\nneeds review") throw new Error("body lines not preserved");
                if (segments[0].from !== "buyer@example.test") throw new Error("sender not parsed");
                if (segments[0].to !== "sales@example.test") throw new Error("recipient not normalized");
                if (segments[0].sent_at !== "2026-07-10T09:00:00Z") throw new Error("sent_at not parsed");
                if (segments[0].timestamp_text !== "2026-07-10T09:00:00Z") throw new Error("timestamp not parsed");
                if (segments[0].subject !== "Quote") throw new Error("subject not parsed");
                if (segments[1].from !== "sales@example.test") throw new Error("latest sender misplaced");
                assertNoPrivateFields(segments);
              },

              hidden_and_background_resources_are_excluded: async () => {
                const calls = [];
                const hiddenParent = new FakeElement({
                  style: { visibility: "hidden" },
                  children: [resource("parent-hidden.pdf", "pdf", "/cgi-bin/download?file=parent-hidden")],
                });
                const background = resource("background.pdf", "pdf", "/cgi-bin/download?file=background");
                const doc = resourceDocument([
                  resource("visible.pdf", "pdf", "/cgi-bin/download?file=visible"),
                  resource("hidden.pdf", "pdf", "/cgi-bin/download?file=hidden", { hidden: true }),
                  resource("aria.pdf", "pdf", "/cgi-bin/download?file=aria", { attrs: { "aria-hidden": "true" } }),
                  hiddenParent,
                ], [background]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1, 2]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (calls.length !== 1 || calls[0] !== "https://exmail.qq.com/cgi-bin/download?file=visible") {
                  throw new Error(`unexpected fetches: ${JSON.stringify(calls)}`);
                }
                if (result.attachment_files.length !== 1) throw new Error("visible resource not collected");
                if (result.resource_limitations.length !== 0) throw new Error("hidden resource returned metadata");
              },

              legacy_tencent_download_control_requires_complete_positive_evidence: async () => {
                const requests = [];
                const legacyControl = (attrs = {}, text = "synthetic.pdf") => new FakeElement({
                  tag: "a",
                  text,
                  width: 160,
                  height: 24,
                  attrs: {
                    href: "/cgi-bin/download?opaque=synthetic",
                    target: "_blank",
                    ...attrs,
                  },
                });
                const collect = async (control, options = {}) => {
                  const doc = resourceDocument([control]);
                  return loadCollector(async (url, fetchOptions) => {
                    requests.push({ url, fetchOptions });
                    return response([1, 2]);
                  }).collectVisibleResources(doc, trustedResourceOptions(doc, options));
                };

                const positive = await collect(legacyControl());
                if (requests.length !== 1 || requests[0].url !== "https://exmail.qq.com/cgi-bin/download?opaque=synthetic") {
                  throw new Error(`legacy control did not fetch exactly once: ${JSON.stringify(requests)}`);
                }
                if (
                  requests[0].fetchOptions.credentials !== "include" ||
                  requests[0].fetchOptions.redirect !== "error" ||
                  positive.attachment_files.length !== 1 ||
                  positive.attachment_files[0].filename !== "synthetic.pdf" ||
                  positive.attachment_files[0].type !== "pdf" ||
                  positive.resource_limitations.length !== 0
                ) {
                  throw new Error(`legacy positive projection mismatch: ${JSON.stringify({ requests, positive })}`);
                }

                const negativeCases = [
                  ["missing target", legacyControl({ target: "" })],
                  ["viewfile", legacyControl({ href: "/cgi-bin/viewfile?opaque=synthetic" })],
                  ["external origin", legacyControl({ href: "https://example.invalid/cgi-bin/download?opaque=synthetic" })],
                  ["credential URL", legacyControl({ href: "https://user:pass" + "@exmail.qq.com/cgi-bin/download?opaque=synthetic" })],
                  ["HTTP URL", legacyControl({ href: "http://exmail.qq.com/cgi-bin/download?opaque=synthetic" })],
                  ["non-default HTTPS port", legacyControl({ href: "https://exmail.qq.com:444/cgi-bin/download?opaque=synthetic" })],
                  ["empty query", legacyControl({ href: "/cgi-bin/download" })],
                  ["unsupported visible type", legacyControl({}, "synthetic.exe")],
                  ["signature hint", legacyControl({ title: "signature synthetic.pdf" })],
                  ["signature text", legacyControl({}, "signature synthetic.pdf")],
                  ["profile accessibility label", legacyControl({ "aria-label": "profile synthetic.pdf" }, "")],
                  ["malformed declared image type", legacyControl({
                    "aria-label": "synthetic.pdf",
                    "data-type": "image/jpeg trailing",
                  }, "")],
                  ["declared visible type mismatch", legacyControl({
                    title: "synthetic.pdf",
                    "data-type": "docx",
                  }, "")],
                  ["image canonical conflict", legacyControl({
                    "aria-label": "image/png",
                    "data-type": "image/jpeg",
                  }, "")],
                  ["declared image conflict", legacyControl({
                    "aria-label": "image/png",
                    "data-type": "image/png",
                    "data-mime-type": "image/jpeg",
                  }, "")],
                  ["visible label conflict", legacyControl({
                    "aria-label": "synthetic.docx",
                    "data-type": "pdf",
                  }, "synthetic.pdf")],
                  ["compound visible label conflict", legacyControl({
                    "data-type": "pdf",
                  }, "synthetic.pdf synthetic.docx")],
                  ["compound visible label unknown", legacyControl({
                    "data-type": "pdf",
                  }, "synthetic.pdf synthetic.exe")],
                  ["unsupported SVG image type", legacyControl({
                    "aria-label": "image/svg+xml",
                    "data-type": "image/svg+xml",
                  }, "")],
                  ["unsupported HEIC image type", legacyControl({
                    "aria-label": "image/heic",
                    "data-type": "image/heic",
                  }, "")],
                ];
                for (const [label, control] of negativeCases) {
                  const before = requests.length;
                  const rejected = await collect(control);
                  if (requests.length !== before || rejected.attachment_files.length !== 0) {
                    throw new Error(`legacy ${label} control was collected: ${JSON.stringify(rejected)}`);
                  }
                }

                const hiddenPdf = legacyControl({}, "");
                const hiddenChild = new FakeElement({ tag: "span", text: "synthetic.pdf", hidden: true });
                hiddenPdf.children = [hiddenChild];
                hiddenChild.parentElement = hiddenPdf;
                hiddenChild.parentNode = hiddenPdf;
                hiddenPdf.textContent = "synthetic.pdf";
                const hiddenBefore = requests.length;
                const hidden = await collect(hiddenPdf);
                if (requests.length !== hiddenBefore || hidden.attachment_files.length !== 0) {
                  throw new Error(`hidden legacy filename was collected: ${JSON.stringify(hidden)}`);
                }

                for (const extension of ["doc", "xls", "pptx", "zip", "txt"]) {
                  const before = requests.length;
                  const rejected = await collect(legacyControl({}, `synthetic.${extension}`));
                  if (requests.length !== before || rejected.attachment_files.length !== 0) {
                    throw new Error(`unsupported legacy extension was collected: ${extension}`);
                  }
                }

                const exactTypeCases = [
                  ["image/jpeg", "image"],
                  ["pdf", "pdf"],
                  ["xlsx", "xlsx"],
                  ["docx", "docx"],
                ];
                for (const [declaredType, expectedType] of exactTypeCases) {
                  const before = requests.length;
                  const accepted = await collect(legacyControl({
                    "aria-label": declaredType,
                    "data-type": declaredType,
                  }, ""));
                  if (
                    requests.length !== before + 1 ||
                    accepted.attachment_files.length !== 1 ||
                    accepted.attachment_files[0].type !== expectedType
                  ) {
                    throw new Error(`exact legacy type was not collected: ${declaredType}`);
                  }
                }

                const insideQmbox = legacyControl();
                const insideDoc = resourceDocument([], [insideQmbox]);
                insideDoc.verifiedResourceCandidates = [insideQmbox];
                const insideApi = loadCollector(async () => {
                  throw new Error("inside-qmbox legacy control must not fetch");
                });
                const inside = await insideApi.collectVisibleResources(
                  insideDoc,
                  trustedResourceOptions(insideDoc),
                );
                if (inside.attachment_files.length !== 0) {
                  throw new Error(`inside-qmbox legacy control was collected: ${JSON.stringify(inside)}`);
                }

                const changedControl = legacyControl();
                const changedDoc = resourceDocument([changedControl]);
                const changedApi = loadCollector(async () => {
                  throw new Error("changed context must not fetch");
                });
                const changed = await changedApi.collectVisibleResources(changedDoc, trustedResourceOptions(changedDoc, {
                  revalidateContext: () => false,
                }));
                if (changed.attachment_files.length !== 0) {
                  throw new Error(`changed legacy context was collected: ${JSON.stringify(changed)}`);
                }

                const redirectControl = legacyControl();
                const redirectDoc = resourceDocument([redirectControl]);
                const redirectApi = loadCollector(async () => ({
                  ...response([1]),
                  redirected: true,
                }));
                const redirected = await redirectApi.collectVisibleResources(
                  redirectDoc,
                  trustedResourceOptions(redirectDoc),
                );
                if (redirected.attachment_files.length !== 0 || redirected.resource_limitations.length !== 1) {
                  throw new Error(`redirected legacy control retained bytes: ${JSON.stringify(redirected)}`);
                }
              },

              legacy_data_filename_metadata_is_typed_and_fail_closed_before_fetch: async () => {
                const legacyControl = (attrs = {}, text = "") => new FakeElement({
                  tag: "a",
                  text,
                  width: 160,
                  height: 24,
                  attrs: {
                    href: "/cgi-bin/download?opaque=synthetic",
                    target: "_blank",
                    ...attrs,
                  },
                });
                const collect = async (control) => {
                  const doc = resourceDocument([control]);
                  let fetchCount = 0;
                  const result = await loadCollector(async () => {
                    fetchCount += 1;
                    return response([1, 2]);
                  }).collectVisibleResources(doc, trustedResourceOptions(doc));
                  return { fetchCount, result };
                };

                const supported = await collect(legacyControl({
                  "data-filename": "synthetic.pdf",
                }));
                if (
                  supported.fetchCount !== 1 ||
                  supported.result.attachment_files.length !== 1 ||
                  supported.result.attachment_files[0].filename !== "synthetic.pdf" ||
                  supported.result.attachment_files[0].type !== "pdf"
                ) {
                  throw new Error(`supported data-filename was not typed: ${JSON.stringify(supported)}`);
                }

                const rejected = [
                  ["unsupported", legacyControl({ "data-filename": "synthetic.exe" })],
                  ["declared conflict", legacyControl({
                    "data-filename": "synthetic.pdf",
                    "data-type": "docx",
                  })],
                  ["visible conflict", legacyControl({
                    "data-filename": "synthetic.xlsx",
                  }, "synthetic.docx")],
                ];
                for (const [label, control] of rejected) {
                  const outcome = await collect(control);
                  if (outcome.fetchCount !== 0 || outcome.result.attachment_files.length !== 0) {
                    throw new Error(`legacy data-filename ${label} fetched: ${JSON.stringify(outcome)}`);
                  }
                }
              },

              untyped_legacy_responses_require_allowlisted_header_signature_evidence: async () => {
                const legacyControl = () => new FakeElement({
                  tag: "a",
                  width: 160,
                  height: 24,
                  top: 900,
                  attrs: {
                    href: "/cgi-bin/download?opaque=synthetic",
                    target: "_blank",
                  },
                });
                const collect = async ({ bytes, contentType = null, contentDisposition = null }) => {
                  const control = legacyControl();
                  const doc = resourceDocument([control]);
                  let fetchCount = 0;
                  const api = loadCollector(async () => {
                    fetchCount += 1;
                    return streamingResponse([bytes], {
                      contentLength: String(bytes.length),
                      contentType,
                      contentDisposition,
                    }).response;
                  });
                  const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                  return { fetchCount, result };
                };

                const accepted = [
                  {
                    bytes: [0x25, 0x50, 0x44, 0x46, 0x2d, 0x31],
                    contentType: "application/pdf; charset=binary",
                    type: "pdf",
                    filename: "attachment-1.pdf",
                  },
                  {
                    bytes: [0x25, 0x50, 0x44, 0x46, 0x2d, 0x32],
                    contentType: "",
                    type: "pdf",
                    filename: "attachment-1.pdf",
                  },
                  {
                    bytes: [0x25, 0x50, 0x44, 0x46, 0x2d, 0x33],
                    contentType: "application/octet-stream",
                    type: "pdf",
                    filename: "attachment-1.pdf",
                  },
                  {
                    bytes: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a],
                    contentType: "application/octet-stream",
                    type: "image",
                    filename: "attachment-1.png",
                  },
                  {
                    bytes: [0xff, 0xd8, 0xff, 0x01],
                    contentType: "image/jpeg",
                    type: "image",
                    filename: "attachment-1.jpg",
                  },
                  {
                    bytes: Array.from(Buffer.from("GIF89a", "ascii")),
                    contentType: "image/gif",
                    type: "image",
                    filename: "attachment-1.gif",
                  },
                  {
                    bytes: [0x42, 0x4d, 0x01],
                    contentType: "image/bmp",
                    type: "image",
                    filename: "attachment-1.bmp",
                  },
                  {
                    bytes: [0x49, 0x49, 0x2a, 0x00, 0x01],
                    contentType: "image/tiff",
                    type: "image",
                    filename: "attachment-1.tiff",
                  },
                  {
                    bytes: [0x52, 0x49, 0x46, 0x46, 0x01, 0x02, 0x03, 0x04, 0x57, 0x45, 0x42, 0x50],
                    contentType: "image/webp",
                    type: "image",
                    filename: "attachment-1.webp",
                  },
                  {
                    bytes: [0x50, 0x4b, 0x03, 0x04, 0x01],
                    contentType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    type: "docx",
                    filename: "attachment-1.docx",
                  },
                  {
                    bytes: [0x50, 0x4b, 0x03, 0x04, 0x01],
                    contentType: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    type: "xlsx",
                    filename: "attachment-1.xlsx",
                  },
                  {
                    bytes: [0x50, 0x4b, 0x03, 0x04, 0x01],
                    contentType: "",
                    contentDisposition: 'attachment; filename="private-response.docx"',
                    type: "docx",
                    filename: "attachment-1.docx",
                  },
                  {
                    bytes: [0x50, 0x4b, 0x03, 0x04, 0x01],
                    contentType: "application/octet-stream",
                    contentDisposition: 'attachment; filename="private-response.xlsx"',
                    type: "xlsx",
                    filename: "attachment-1.xlsx",
                  },
                  {
                    bytes: [0x50, 0x4b, 0x03, 0x04, 0x02],
                    contentType: "application/octet-stream",
                    contentDisposition: "attachment; filename=private-response.docx",
                    type: "docx",
                    filename: "attachment-1.docx",
                  },
                ];
                for (const item of accepted) {
                  const { fetchCount, result } = await collect(item);
                  const file = result.attachment_files[0];
                  const expectedBase64 = Buffer.from(item.bytes).toString("base64");
                  if (
                    fetchCount !== 1 ||
                    result.attachment_files.length !== 1 ||
                    file.type !== item.type ||
                    file.filename !== item.filename ||
                    file.size !== item.bytes.length ||
                    file.content_base64 !== expectedBase64 ||
                    result.resource_limitations.length !== 0
                  ) {
                    throw new Error(`deferred response was not accepted safely: ${JSON.stringify({ item, fetchCount, result })}`);
                  }
                  if (JSON.stringify(result).includes("private-response")) {
                    throw new Error(`response filename escaped: ${JSON.stringify(result)}`);
                  }
                }

                const rejected = [
                  {
                    label: "html",
                    bytes: [0x3c, 0x68, 0x74, 0x6d, 0x6c],
                    contentType: "text/html",
                    code: "unsupported_type",
                  },
                  {
                    label: "multiple mime",
                    bytes: [0x25, 0x50, 0x44, 0x46, 0x2d],
                    contentType: "application/pdf, text/html",
                    code: "unsupported_type",
                  },
                  {
                    label: "truncated pdf",
                    bytes: [0x25, 0x50, 0x44],
                    contentType: "application/pdf",
                    code: "resource_read_failed",
                  },
                  {
                    label: "mime signature mismatch",
                    bytes: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a],
                    contentType: "application/pdf",
                    code: "resource_read_failed",
                  },
                  {
                    label: "generic zip without suffix",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    code: "unsupported_type",
                  },
                  {
                    label: "generic zip ambiguous suffix",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    contentDisposition: 'attachment; filename="one.docx"; filename*=UTF-8\'\'two.xlsx',
                    code: "unsupported_type",
                  },
                  {
                    label: "generic zip unterminated quoted filename",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    contentDisposition: 'attachment; filename="private-response.docx',
                    code: "unsupported_type",
                  },
                  {
                    label: "generic zip malformed unquoted filename",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    contentDisposition: "attachment; filename==private-response.docx",
                    code: "unsupported_type",
                  },
                  {
                    label: "generic zip unquoted trailing junk",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    contentDisposition: "attachment; filename=private-response.docx trailing",
                    code: "unsupported_type",
                  },
                  {
                    label: "generic zip quoted trailing junk",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    contentDisposition: 'attachment; filename="private-response.docx" trailing',
                    code: "unsupported_type",
                  },
                  {
                    label: "generic zip duplicate filename",
                    bytes: [0x50, 0x4b, 0x03, 0x04],
                    contentType: "application/octet-stream",
                    contentDisposition: "attachment; filename=one.docx; filename=two.docx",
                    code: "unsupported_type",
                  },
                ];
                for (const item of rejected) {
                  const { fetchCount, result } = await collect(item);
                  if (
                    fetchCount !== 1 ||
                    result.attachment_files.length !== 0 ||
                    result.resource_limitations.length !== 1 ||
                    result.resource_limitations[0].code !== item.code
                  ) {
                    throw new Error(`deferred ${item.label} response did not fail closed: ${JSON.stringify({ fetchCount, result })}`);
                  }
                  if (Object.prototype.hasOwnProperty.call(result.resource_limitations[0], "content_base64")) {
                    throw new Error(`deferred ${item.label} response emitted payload bytes`);
                  }
                  if (JSON.stringify(result).includes("private-response")) {
                    throw new Error(`deferred ${item.label} response emitted raw header metadata`);
                  }
                }
              },

              stylesheet_hidden_root_and_resources_are_excluded: async () => {
                const calls = [];
                const current = new FakeElement({
                  attrs: { class: "mail-content" },
                  children: [thread("Hidden ancestor segment")],
                });
                const controls = new FakeElement({
                  attrs: { class: "resource-region" },
                  children: [resource("hidden-ancestor.pdf", "pdf", "/cgi-bin/download?file=hidden-ancestor")],
                });
                const container = new FakeElement({
                  attrs: { class: "read-envelope" },
                  children: [current, controls],
                });
                const hiddenAncestor = new FakeElement({ children: [container] });
                const body = new FakeElement({ tag: "body", children: [hiddenAncestor] });
                const doc = new FakeDocument(body, "https://exmail.qq.com/cgi-bin/readmail", (element) => ({
                  display: element === hiddenAncestor ? "none" : "block",
                  visibility: "visible",
                }));
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });
                const segments = api.extractVisibleThreadSegments(doc, { currentMessageRoot: current });
                const resources = await api.collectVisibleResources(doc, {
                  currentMessageRoot: current,
                  currentMessageContainer: container,
                  verifiedResourceCandidates: controls.children,
                  resourceControlsVerified: true,
                });
                if (segments.length !== 0) throw new Error("segment beneath hidden ancestor was extracted");
                if (calls.length !== 0) throw new Error("resource beneath hidden ancestor was fetched");
                if (resources.attachment_files.length || resources.resource_limitations.length) {
                  throw new Error("hidden root emitted resource output");
                }
              },

              email_authored_same_origin_links_are_never_fetched: async () => {
                const calls = [];
                const forgedBodyLink = resource(
                  "forged.pdf",
                  "pdf",
                  "/cgi-bin/download?file=forged",
                  { attrs: { download: "forged.pdf" } },
                );
                const trustedControl = resource(
                  "trusted.pdf",
                  "pdf",
                  "/cgi-bin/download?file=trusted",
                );
                const doc = resourceDocument([trustedControl], [forgedBodyLink]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1, 2, 3]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (calls.length !== 1 || !calls[0].includes("file=trusted")) {
                  throw new Error(`email-authored link was fetched: ${JSON.stringify(calls)}`);
                }
                if (result.attachment_files.length !== 1 || result.attachment_files[0].filename !== "trusted.pdf") {
                  throw new Error(`trusted control was not collected: ${JSON.stringify(result)}`);
                }
              },

              unverified_controls_fail_closed_without_fetching: async () => {
                const calls = [];
                const forgedBodyLink = resource(
                  "forged.pdf",
                  "pdf",
                  "/cgi-bin/download?file=forged",
                  { attrs: { download: "forged.pdf" } },
                );
                const doc = messageDocument([forgedBodyLink]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([9]);
                });
                const result = await api.collectVisibleResources(doc, {
                  currentMessageRoot: doc.currentMessageRoot,
                  resourceControlsVerified: false,
                  verifiedResourceCandidates: [],
                });
                if (calls.length !== 0) throw new Error(`unverified control was fetched: ${JSON.stringify(calls)}`);
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error(`missing unavailable limitation: ${JSON.stringify(result)}`);
                }
                if (!result.resource_limitations[0].limitation.includes("verified current-message resource controls")) {
                  throw new Error(`unsafe limitation: ${JSON.stringify(result.resource_limitations)}`);
                }
              },

              unapproved_same_origin_endpoints_are_never_fetched: async () => {
                const calls = [];
                const doc = resourceDocument([
                  resource("mail.html", "pdf", "/cgi-bin/readmail?download=mail.html"),
                ]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (calls.length !== 0) throw new Error(`unapproved endpoint was fetched: ${JSON.stringify(calls)}`);
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error(`endpoint limitation missing: ${JSON.stringify(result)}`);
                }
                if (!result.resource_limitations[0].limitation.includes("approved Tencent Exmail attachment endpoint")) {
                  throw new Error(`unexpected endpoint limitation: ${JSON.stringify(result.resource_limitations)}`);
                }
              },

              supported_same_origin_bytes_use_exact_upload_allowlist: async () => {
                const calls = [];
                const doc = resourceDocument([
                  resource("../../photo.png", "image/png", "/cgi-bin/viewfile?file=photo"),
                  resource("scope.pdf", "application/pdf", "https://exmail.qq.com/cgi-bin/download?file=pdf"),
                  resource("cost.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "/cgi-bin/download?file=xlsx"),
                  resource("notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "/cgi-bin/download?file=docx"),
                ]);
                const payloads = [[0, 255], [1, 2, 3], [4], [5, 6]];
                const api = loadCollector(async (url, options) => {
                  calls.push({ url, options });
                  return response(payloads[calls.length - 1]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (result.resource_limitations.length !== 0) throw new Error(JSON.stringify(result));
                if (result.attachment_files.length !== 4) throw new Error("not all supported types collected");
                const expectedTypes = ["image", "pdf", "xlsx", "docx"];
                for (let index = 0; index < result.attachment_files.length; index += 1) {
                  const file = result.attachment_files[index];
                  const keys = Object.keys(file).sort().join(",");
                  if (keys !== "content_base64,filename,size,type") throw new Error(`upload fields changed: ${keys}`);
                  if (file.type !== expectedTypes[index]) throw new Error(`unexpected type: ${file.type}`);
                  const expectedBase64 = Buffer.from(payloads[index]).toString("base64");
                  if (file.content_base64 !== expectedBase64) throw new Error("base64 mismatch");
                  if (file.size !== payloads[index].length) throw new Error("byte size mismatch");
                }
                if (result.attachment_files[0].filename !== "photo.png") throw new Error("filename was not made safe");
                if (calls.some((call) => call.options.credentials !== "include" || call.options.redirect !== "error")) {
                  throw new Error("current-session fetch options are missing");
                }
                assertNoPrivateFields(result.attachment_files);
              },

              visible_attachment_and_business_inline_image_share_existing_payload: async () => {
                const photo = businessImage("/cgi-bin/viewfile?file=opaque-photo", {
                  attrs: { "data-filename": "customer-original-product-photo.jpg" },
                });
                const attachment = resource(
                  "inspection.pdf",
                  "application/pdf",
                  "/cgi-bin/download?file=inspection",
                );
                const doc = resourceDocument([attachment], [photo]);
                const calls = [];
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response(url.includes("viewfile") ? [1, 2, 3] : [4, 5]);
                });

                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (calls.length !== 2 || result.attachment_files.length !== 2) {
                  throw new Error(`approved resources were not collected: ${JSON.stringify(result)}`);
                }
                const attachmentFile = result.attachment_files.find((item) => item.type === "pdf");
                const inlineFile = result.attachment_files.find((item) => item.type === "image");
                if (!attachmentFile || attachmentFile.filename !== "inspection.pdf") {
                  throw new Error("visible attachment control changed");
                }
                if (!inlineFile || inlineFile.filename !== "inline-image-1.jpg") {
                  throw new Error(`inline image name is not opaque: ${JSON.stringify(inlineFile)}`);
                }
                const serialized = JSON.stringify(result.attachment_files);
                for (const forbidden of [
                  "opaque-photo",
                  "customer-original-product-photo",
                  "product packaging",
                  "viewfile",
                  "src",
                  "role",
                ]) {
                  if (serialized.includes(forbidden)) throw new Error(`inline private field leaked: ${forbidden}`);
                }
                assertNoPrivateFields(result.attachment_files);
              },

              signature_history_repeated_ui_hidden_external_and_ambiguous_media_are_excluded: async () => {
                const portrait = inlineImage(
                  "/cgi-bin/viewfile?file=portrait",
                  "staff portrait avatar beside contact logo",
                  180,
                  180,
                );
                const portraitBlock = new FakeElement({
                  attrs: { class: "signature contact-card" },
                  text: "person@example.test Tel: 000 0000 Address: Example Road",
                  children: [portrait],
                });
                const wordmark = inlineImage(
                  "/cgi-bin/viewfile?file=wordmark",
                  "corporate wordmark logo",
                  720,
                  140,
                );
                const addressBanner = inlineImage(
                  "/cgi-bin/viewfile?file=address-banner",
                  "company contact address banner",
                  900,
                  150,
                );
                const addressBlock = new FakeElement({
                  attrs: { class: "contact-card" },
                  text: "team@example.test Phone: 000 0000 Address: Example Street www.example.test",
                  children: [addressBanner],
                });
                const logo = inlineImage("/cgi-bin/viewfile?file=logo", "supplier logo", 800, 600);
                const avatar = inlineImage("/cgi-bin/viewfile?file=avatar", "profile avatar", 256, 256);
                const icon = inlineImage("/cgi-bin/viewfile?file=icon", "social icon", 96, 96);
                const tracker = inlineImage("/cgi-bin/viewfile?file=tracker", "tracking pixel", 1, 1);
                const quoted = new FakeElement({
                  attrs: { class: "quoted-history" },
                  children: [inlineImage(
                    "/cgi-bin/viewfile?file=quoted",
                    "historical product photo",
                    1280,
                    960,
                  )],
                });
                const repeatedOne = inlineImage(
                  "/cgi-bin/viewfile?file=repeated-one",
                  "product photo",
                  1280,
                  960,
                  { attrs: { "data-cid": "repeated-signature-image" } },
                );
                const repeatedTwo = inlineImage(
                  "/cgi-bin/viewfile?file=repeated-two",
                  "product photo",
                  1280,
                  960,
                  { attrs: { "data-cid": "repeated-signature-image" } },
                );
                const hidden = inlineImage(
                  "/cgi-bin/viewfile?file=hidden",
                  "hidden product photo",
                  1280,
                  960,
                  { hidden: true },
                );
                const external = inlineImage(
                  "https://media.example.test/product.jpg",
                  "external product photo",
                  1280,
                  960,
                );
                const signoff = new FakeElement({ text: "Best regards" });
                const afterSignoff = inlineImage(
                  "/cgi-bin/viewfile?file=after-signoff",
                  "product photo after signoff",
                  1280,
                  960,
                );
                const ambiguous = inlineImage(
                  "/cgi-bin/viewfile?file=ambiguous",
                  "unowned product photo",
                  1280,
                  960,
                );
                const attachment = resource(
                  "visible.pdf",
                  "pdf",
                  "/cgi-bin/download?file=visible",
                );
                const doc = explicitBodyResourceDocument([
                  portraitBlock,
                  wordmark,
                  addressBlock,
                  logo,
                  avatar,
                  icon,
                  tracker,
                  quoted,
                  repeatedOne,
                  repeatedTwo,
                  hidden,
                  external,
                  signoff,
                  afterSignoff,
                ], [ambiguous], [attachment]);
                const calls = [];
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });

                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (
                  calls.length !== 1 ||
                  !calls[0].includes("file=visible") ||
                  result.attachment_files.length !== 1 ||
                  result.attachment_files[0].filename !== "visible.pdf"
                ) {
                  throw new Error(`excluded media reached fetch/payload: ${JSON.stringify({ calls, result })}`);
                }
                if (result.resource_limitations.length !== 0) {
                  throw new Error(`rejected inline media leaked metadata: ${JSON.stringify(result)}`);
                }
              },

              known_thread_selector_image_is_excluded: async () => {
                const quotedImage = inlineImage(
                  "/cgi-bin/viewfile?file=nested-thread-photo",
                  "historical product packaging photo",
                  1280,
                  960,
                );
                const historicalThread = new FakeElement({
                  attrs: {
                    class: "mail-thread-item",
                    "data-email-thread-segment": "true",
                  },
                  children: [quotedImage],
                });
                const attachment = resource(
                  "visible.pdf",
                  "pdf",
                  "/cgi-bin/download?file=visible",
                );
                const doc = resourceDocument([attachment], [historicalThread]);
                const calls = [];
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });

                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (
                  calls.length !== 1 ||
                  !calls[0].includes("file=visible") ||
                  result.attachment_files.length !== 1 ||
                  result.attachment_files[0].filename !== "visible.pdf"
                ) {
                  throw new Error(`known thread media escaped: ${JSON.stringify({ calls, result })}`);
                }
              },

              complete_header_blockquote_image_is_excluded_but_current_image_is_collected: async () => {
                const currentImage = inlineImage(
                  "/cgi-bin/viewfile?file=current-business-photo",
                  "current product packaging photo",
                  1280,
                  960,
                );
                const historicalImage = inlineImage(
                  "/cgi-bin/viewfile?file=historical-business-photo",
                  "historical product packaging photo",
                  1280,
                  960,
                );
                const historicalBlockquote = new FakeElement({
                  tag: "blockquote",
                  text: [
                    "From: history@example.test",
                    "Date: 2026-07-10 09:00",
                    "To: team@example.test",
                    "Subject: Historical request",
                    "Historical text.",
                  ].join("\n"),
                  children: [historicalImage],
                });
                const doc = explicitBodyResourceDocument([
                  currentImage,
                  historicalBlockquote,
                ]);
                const calls = [];
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });

                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (
                  calls.length !== 1 ||
                  !calls[0].includes("file=current-business-photo") ||
                  calls[0].includes("historical-business-photo") ||
                  result.attachment_files.length !== 1
                ) {
                  throw new Error(`legacy history image escaped: ${JSON.stringify({ calls, result })}`);
                }
              },

              ordinary_blockquote_current_image_is_not_blanket_rejected: async () => {
                const currentImage = inlineImage(
                  "/cgi-bin/viewfile?file=quoted-current-business-photo",
                  "current product packaging photo",
                  1280,
                  960,
                );
                const ordinaryBlockquote = new FakeElement({
                  tag: "blockquote",
                  text: "Current customer-provided evidence without a quoted-mail header.",
                  children: [currentImage],
                });
                const doc = explicitBodyResourceDocument([ordinaryBlockquote]);
                const calls = [];
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });

                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (
                  calls.length !== 1 ||
                  !calls[0].includes("file=quoted-current-business-photo") ||
                  result.attachment_files.length !== 1
                ) {
                  throw new Error(`ordinary blockquote image was lost: ${JSON.stringify({ calls, result })}`);
                }
              },

              attachment_layout_may_be_offscreen_but_inline_images_keep_viewport_gate: async () => {
                const zeroLayoutImage = inlineImage(
                  "/cgi-bin/viewfile?file=zero-layout",
                  "product packaging photo",
                  1280,
                  960,
                  { rectWidth: 0, rectHeight: 0 },
                );
                const offscreenImage = inlineImage(
                  "/cgi-bin/viewfile?file=offscreen-inline",
                  "offscreen product packaging photo",
                  1280,
                  960,
                  { left: 2000 },
                );
                const offscreenAttachment = resource(
                  "offscreen.pdf",
                  "pdf",
                  "/cgi-bin/download?file=offscreen",
                  { left: 2000 },
                );
                const zeroLayoutAttachment = resource(
                  "zero-layout.pdf",
                  "pdf",
                  "/cgi-bin/download?file=zero-layout-attachment",
                  { rectWidth: 0, rectHeight: 0 },
                );
                const hiddenAttachment = resource(
                  "hidden.pdf",
                  "pdf",
                  "/cgi-bin/download?file=hidden",
                  { hidden: true },
                );
                const visibleAttachment = resource(
                  "visible.pdf",
                  "pdf",
                  "/cgi-bin/download?file=visible",
                );
                const doc = resourceDocument(
                  [offscreenAttachment, zeroLayoutAttachment, hiddenAttachment, visibleAttachment],
                  [zeroLayoutImage, offscreenImage],
                );
                const calls = [];
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1]);
                });

                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (
                  calls.length !== 2 ||
                  !calls.some((url) => url.includes("file=offscreen")) ||
                  !calls.some((url) => url.includes("file=visible")) ||
                  result.attachment_files.length !== 2 ||
                  !result.attachment_files.some((item) => item.filename === "offscreen.pdf") ||
                  !result.attachment_files.some((item) => item.filename === "visible.pdf")
                ) {
                  throw new Error(`rendered attachment visibility changed: ${JSON.stringify({ calls, result })}`);
                }
              },

              stale_verified_context_after_fetch_discards_bytes: async () => {
                const attachment = resource(
                  "stale.pdf",
                  "pdf",
                  "/cgi-bin/download?file=stale",
                );
                const doc = resourceDocument([attachment]);
                let current = true;
                const api = loadCollector(async () => {
                  current = false;
                  return response([1, 2, 3]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  revalidateContext: () => current,
                }));
                if (result.attachment_files.length !== 0) {
                  throw new Error("stale verified context emitted fetched bytes");
                }
                if (!result.resource_limitations.some((item) => item.code === "resource_unavailable")) {
                  throw new Error(`stale context limitation missing: ${JSON.stringify(result)}`);
                }
              },

              changed_resource_identity_after_fetch_discards_bytes: async () => {
                const attachment = resource(
                  "identity.pdf",
                  "pdf",
                  "/cgi-bin/download?file=identity-before",
                );
                const doc = resourceDocument([attachment]);
                const api = loadCollector(async () => {
                  attachment.attrs.href = "/cgi-bin/download?file=identity-after";
                  return response([9, 8, 7]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (result.attachment_files.length !== 0) {
                  throw new Error("changed resource identity emitted fetched bytes");
                }
                if (!result.resource_limitations.some((item) => item.code === "resource_unavailable")) {
                  throw new Error(`identity limitation missing: ${JSON.stringify(result)}`);
                }
              },

              redirected_response_is_rejected: async () => {
                const attachment = resource(
                  "redirect.pdf",
                  "pdf",
                  "/cgi-bin/download?file=redirect",
                );
                const doc = resourceDocument([attachment]);
                const api = loadCollector(async () => ({
                  ...response([1]),
                  redirected: true,
                  url: "https://exmail.qq.com/cgi-bin/download?file=redirected",
                }));
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (result.attachment_files.length !== 0) {
                  throw new Error("redirected response emitted bytes");
                }
                if (!result.resource_limitations.some((item) => item.code === "resource_read_failed")) {
                  throw new Error(`redirect limitation missing: ${JSON.stringify(result)}`);
                }
              },

              unsafe_unsupported_failed_and_oversized_resources_return_limitations: async () => {
                let fetchCount = 0;
                const doc = resourceDocument([
                  resource("outside.pdf", "pdf", "https://example.invalid/outside"),
                  resource("script.exe", "application/octet-stream", "/cgi-bin/download?file=script"),
                  resource("unreadable.pdf", "pdf", "/cgi-bin/download?file=unreadable"),
                  resource("large.pdf", "pdf", "/cgi-bin/download?file=large", { attrs: { "data-size": "5" } }),
                ]);
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  throw new Error("private download failure details");
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  limits: { maxFiles: 5, maxFileBytes: 4, maxTotalBytes: 8 },
                }));
                if (result.attachment_files.length !== 0) throw new Error("unsafe bytes were emitted");
                if (result.resource_limitations.length !== 4) throw new Error(JSON.stringify(result));
                const codes = result.resource_limitations.map((item) => item.code).sort();
                const expectedCodes = ["frontend_limit", "resource_read_failed", "resource_unavailable", "unsupported_type"].sort();
                if (JSON.stringify(codes) !== JSON.stringify(expectedCodes)) {
                  throw new Error(`limitation code mapping changed: ${JSON.stringify(result)}`);
                }
                if (fetchCount !== 1) throw new Error(`unexpected fetch count: ${fetchCount}`);
                const messages = result.resource_limitations.map((item) => item.limitation).join(" | ");
                for (const expected of ["same-origin", "not supported", "could not be read", "per-file"]) {
                  if (!messages.includes(expected)) throw new Error(`missing ${expected} limitation: ${messages}`);
                }
                for (const item of result.resource_limitations) {
                  if (Object.prototype.hasOwnProperty.call(item, "content_base64")) throw new Error("limited resource has bytes");
                }
                assertNoPrivateFields(result.resource_limitations);
              },

              known_body_container_is_checked_before_candidate_fetch: async () => {
                let fetchCount = 0;
                const currentRoot = new FakeElement({
                  attrs: { id: "mailContentContainer" },
                  text: "Please review the nested visible message.",
                });
                const forgedLink = resource(
                  "forged.pdf",
                  "pdf",
                  "/cgi-bin/download?file=forged",
                );
                const knownBodyContainer = new FakeElement({
                  attrs: { class: "mail-content" },
                  children: [currentRoot, forgedLink],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [knownBodyContainer],
                }));
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  return response([1]);
                });
                const result = await api.collectVisibleResources(doc, {
                  currentMessageRoot: currentRoot,
                  currentMessageContainer: knownBodyContainer,
                  verifiedResourceCandidates: [forgedLink],
                  resourceControlsVerified: true,
                });

                if (fetchCount !== 0 || result.attachment_files.length !== 0) {
                  throw new Error(
                    `known body container was not checked: fetch=${fetchCount} ` +
                    `files=${result.attachment_files.length}`,
                  );
                }
              },

              non_direct_message_root_is_rejected_before_candidate_fetch: async () => {
                let fetchCount = 0;
                const currentRoot = new FakeElement({
                  attrs: { id: "mailContentContainer" },
                  text: "Please review the wrapped visible message.",
                });
                const forgedLink = resource(
                  "forged.pdf",
                  "pdf",
                  "/cgi-bin/download?file=forged",
                );
                const unknownWrapper = new FakeElement({ children: [currentRoot, forgedLink] });
                const structuralEnvelope = new FakeElement({
                  attrs: { class: "read-envelope" },
                  children: [unknownWrapper],
                });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [structuralEnvelope],
                }));
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  return response([1]);
                });
                const result = await api.collectVisibleResources(doc, {
                  currentMessageRoot: currentRoot,
                  currentMessageContainer: structuralEnvelope,
                  verifiedResourceCandidates: [forgedLink],
                  resourceControlsVerified: true,
                });

                if (fetchCount !== 0 || result.attachment_files.length !== 0) {
                  throw new Error(
                    `non-direct root was not rejected: fetch=${fetchCount} ` +
                    `files=${result.attachment_files.length}`,
                  );
                }
                if (
                  result.resource_limitations.length !== 1 ||
                  result.resource_limitations[0].code !== "resource_unavailable"
                ) {
                  throw new Error(`safe unavailable limitation missing: ${JSON.stringify(result)}`);
                }
              },

              mismatched_verified_document_is_rejected_before_candidate_fetch: async () => {
                let fetchCount = 0;
                const frameDoc = resourceDocument([
                  resource("forged.pdf", "pdf", "/cgi-bin/download?file=forged"),
                ]);
                const topDoc = new FakeDocument(new FakeElement({ tag: "body" }));
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  return response([1]);
                });
                const result = await api.collectVisibleResources(
                  frameDoc,
                  trustedResourceOptions(frameDoc, { verifiedDocument: topDoc }),
                );

                if (fetchCount !== 0 || result.attachment_files.length !== 0) {
                  throw new Error(
                    `mismatched verified document was not rejected: fetch=${fetchCount} ` +
                    `files=${result.attachment_files.length}`,
                  );
                }
                if (
                  result.resource_limitations.length !== 1 ||
                  result.resource_limitations[0].code !== "resource_unavailable"
                ) {
                  throw new Error(`safe unavailable limitation missing: ${JSON.stringify(result)}`);
                }
              },

              nested_structural_envelope_is_rejected_before_candidate_fetch: async () => {
                let fetchCount = 0;
                const forgedLink = resource(
                  "forged.pdf",
                  "pdf",
                  "/cgi-bin/download?file=forged",
                );
                const currentRoot = new FakeElement({
                  attrs: { class: "mail-content" },
                  text: "Please review the forged envelope message.",
                });
                const structuralEnvelope = new FakeElement({
                  attrs: { class: "read-envelope" },
                  children: [currentRoot, forgedLink],
                });
                const unknownWrapper = new FakeElement({ children: [structuralEnvelope] });
                const doc = new FakeDocument(new FakeElement({
                  tag: "body",
                  children: [unknownWrapper],
                }));
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  return response([1]);
                });
                const result = await api.collectVisibleResources(doc, {
                  topLevelDocument: doc,
                  currentMessageRoot: currentRoot,
                  currentMessageContainer: structuralEnvelope,
                  verifiedResourceCandidates: [forgedLink],
                  resourceControlsVerified: true,
                });

                if (fetchCount !== 0 || result.attachment_files.length !== 0) {
                  throw new Error(
                    `nested envelope was not rejected: fetch=${fetchCount} ` +
                    `files=${result.attachment_files.length}`,
                  );
                }
                if (
                  result.resource_limitations.length !== 1 ||
                  result.resource_limitations[0].code !== "resource_unavailable"
                ) {
                  throw new Error(`safe unavailable limitation missing: ${JSON.stringify(result)}`);
                }
              },

              additional_global_known_body_root_is_rejected_before_candidate_fetch: async () => {
                let fetchCount = 0;
                const forgedLink = resource(
                  "forged.pdf",
                  "pdf",
                  "/cgi-bin/download?file=forged",
                );
                const doc = resourceDocument([forgedLink], [], [
                  new FakeElement({
                    attrs: { id: "mailContent" },
                    text: "Second author-controlled visible body.",
                  }),
                ]);
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  return response([1]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));

                if (fetchCount !== 0 || result.attachment_files.length !== 0) {
                  throw new Error(
                    `global body ambiguity was not rejected: fetch=${fetchCount} ` +
                    `files=${result.attachment_files.length}`,
                  );
                }
                if (
                  result.resource_limitations.length !== 1 ||
                  result.resource_limitations[0].code !== "resource_unavailable"
                ) {
                  throw new Error(`safe unavailable limitation missing: ${JSON.stringify(result)}`);
                }
              },

              count_and_total_byte_bounds_stop_additional_transfer: async () => {
                const calls = [];
                const doc = resourceDocument([
                  resource("first.pdf", "pdf", "/cgi-bin/download?file=first", { attrs: { "data-size": "2" } }),
                  resource("second.pdf", "pdf", "/cgi-bin/download?file=second", { attrs: { "data-size": "3" } }),
                  resource("total.pdf", "pdf", "/cgi-bin/download?file=total", { attrs: { "data-size": "1" } }),
                  resource("count.pdf", "pdf", "/cgi-bin/download?file=count", { attrs: { "data-size": "1" } }),
                ]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response(calls.length === 1 ? [1, 2] : [3, 4, 5]);
                });
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  limits: { maxFiles: 3, maxFileBytes: 4, maxTotalBytes: 5 },
                }));
                if (calls.length !== 2) throw new Error(`limits allowed extra transfer: ${JSON.stringify(calls)}`);
                if (result.attachment_files.length !== 2) throw new Error(JSON.stringify(result));
                const messages = result.resource_limitations.map((item) => item.limitation).join(" | ");
                if (!messages.includes("total frontend")) throw new Error("total-byte limitation missing");
                if (!messages.includes("file frontend")) throw new Error("file-count limitation missing");
              },

              missing_content_length_streams_within_budget: async () => {
                const streamed = streamingResponse([[1, 2], [3]]);
                const doc = resourceDocument([resource("streamed.pdf", "pdf", "/cgi-bin/download?file=streamed")]);
                const api = loadCollector(async () => streamed.response);
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  limits: { maxFiles: 2, maxFileBytes: 4, maxTotalBytes: 6 },
                }));
                if (result.attachment_files.length !== 1 || result.resource_limitations.length !== 0) {
                  throw new Error(`bounded stream was rejected: ${JSON.stringify(result)}`);
                }
                if (result.attachment_files[0].content_base64 !== "AQID") throw new Error("stream base64 mismatch");
                if (streamed.state.arrayBufferCalls !== 0) throw new Error("stream fell back to arrayBuffer");
              },

              missing_length_without_stream_rejects_before_arraybuffer: async () => {
                let arrayBufferCalls = 0;
                const doc = resourceDocument([resource("unknown.pdf", "pdf", "/cgi-bin/download?file=unknown")]);
                const api = loadCollector(async () => ({
                  ok: true,
                  headers: { get: () => null },
                  arrayBuffer: async () => { arrayBufferCalls += 1; return Uint8Array.from([1, 2]).buffer; },
                }));
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  limits: { maxFiles: 2, maxFileBytes: 4, maxTotalBytes: 6 },
                }));
                if (arrayBufferCalls !== 0) throw new Error("unbounded arrayBuffer fallback was used");
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error("missing-length fallback did not fail safely");
                }
              },

              false_small_length_without_stream_rejects_before_arraybuffer: async () => {
                let arrayBufferCalls = 0;
                const doc = resourceDocument([resource("false-small.pdf", "pdf", "/cgi-bin/download?file=false-small")]);
                const api = loadCollector(async () => ({
                  ok: true,
                  headers: { get: (name) => name.toLowerCase() === "content-length" ? "1" : null },
                  arrayBuffer: async () => {
                    arrayBufferCalls += 1;
                    return Uint8Array.from([1, 2, 3, 4, 5]).buffer;
                  },
                }));
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  limits: { maxFiles: 2, maxFileBytes: 4, maxTotalBytes: 6 },
                }));
                if (arrayBufferCalls !== 0) throw new Error("non-stream arrayBuffer was invoked");
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error("false-small non-stream response did not fail safely");
                }
              },

              announced_oversize_never_settling_cancel_returns_immediately: async () => {
                let cancelCalled = false;
                const doc = resourceDocument([
                  resource("announced-large.pdf", "pdf", "/cgi-bin/download?file=announced-large"),
                ]);
                const api = loadCollector(async () => ({
                  ok: true,
                  redirected: false,
                  headers: {
                    get: (name) => name.toLowerCase() === "content-length" ? "5" : null,
                  },
                  body: {
                    cancel: () => {
                      cancelCalled = true;
                      return new Promise(() => {});
                    },
                  },
                }));

                const result = await withinTestDeadline(
                  api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                    limits: {
                      maxFiles: 1,
                      maxFileBytes: 4,
                      maxTotalBytes: 4,
                      perResourceTimeoutMs: 20,
                      overallTimeoutMs: 50,
                    },
                  })),
                  "announced oversize cancellation",
                );

                if (!cancelCalled) throw new Error("best-effort response cancellation was not triggered");
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error(`announced oversize response was not rejected: ${JSON.stringify(result)}`);
                }
                const limitation = result.resource_limitations[0];
                if (limitation.code !== "frontend_limit" || !limitation.limitation.includes("per-file")) {
                  throw new Error(`announced-size limitation changed: ${JSON.stringify(result)}`);
                }
              },

              oversized_stream_cancels_without_upload_and_continues: async () => {
                const oversized = streamingResponse([[1, 2, 3], [4, 5], [6]], { contentLength: "1" });
                const safe = streamingResponse([[9, 10]]);
                const responses = [oversized, safe];
                let fetchCount = 0;
                let base64Count = 0;
                const doc = resourceDocument([
                  resource("oversized.pdf", "pdf", "/cgi-bin/download?file=oversized"),
                  resource("safe.pdf", "pdf", "/cgi-bin/download?file=safe"),
                ]);
                const api = loadCollector(
                  async () => responses[fetchCount++].response,
                  (binary) => { base64Count += 1; return Buffer.from(binary, "binary").toString("base64"); },
                );
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                  limits: { maxFiles: 2, maxFileBytes: 4, maxTotalBytes: 6 },
                }));
                if (!oversized.state.cancelled) throw new Error("oversized reader was not cancelled");
                if (oversized.state.readCount !== 2) throw new Error("reader did not stop at the first oversized chunk");
                if (oversized.state.arrayBufferCalls !== 0 || safe.state.arrayBufferCalls !== 0) {
                  throw new Error("stream unexpectedly buffered the whole body");
                }
                if (fetchCount !== 2) throw new Error("later safe resource was not processed");
                if (base64Count !== 1) throw new Error("rejected content reached base64 encoding");
                if (result.attachment_files.length !== 1 || result.attachment_files[0].filename !== "safe.pdf") {
                  throw new Error(`unexpected uploads: ${JSON.stringify(result)}`);
                }
                if (result.resource_limitations.length !== 1) throw new Error("oversized limitation missing");
              },

              stalled_fetch_is_aborted_and_returns_a_safe_limitation: async () => {
                let aborted = false;
                const doc = resourceDocument([
                  resource("stalled.pdf", "pdf", "/cgi-bin/download?file=stalled"),
                ]);
                const api = loadCollector(async (_url, options) => new Promise((_resolve, reject) => {
                  options.signal.addEventListener("abort", () => {
                    aborted = true;
                    reject(new Error("private stalled fetch detail"));
                  });
                }));
                const result = await withinTestDeadline(
                  api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                    limits: { perResourceTimeoutMs: 20, overallTimeoutMs: 50 },
                  })),
                  "stalled fetch",
                );
                if (!aborted) throw new Error("stalled fetch signal was not aborted");
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error(`stalled fetch did not fail safely: ${JSON.stringify(result)}`);
                }
                if (!result.resource_limitations[0].limitation.includes("deadline")) {
                  throw new Error(`deadline limitation missing: ${JSON.stringify(result)}`);
                }
                if (result.resource_limitations[0].code !== "collection_timeout") {
                  throw new Error(`timeout code missing: ${JSON.stringify(result)}`);
                }
              },

              stalled_stream_read_is_cancelled_and_returns_a_safe_limitation: async () => {
                let cancelled = false;
                const reader = {
                  read: async () => new Promise(() => {}),
                  cancel: async () => { cancelled = true; },
                  releaseLock: () => {},
                };
                const doc = resourceDocument([
                  resource("stalled.pdf", "pdf", "/cgi-bin/download?file=stalled-read"),
                ]);
                const api = loadCollector(async () => ({
                  ok: true,
                  redirected: false,
                  headers: { get: () => null },
                  body: { getReader: () => reader },
                }));
                const result = await withinTestDeadline(
                  api.collectVisibleResources(doc, trustedResourceOptions(doc, {
                    limits: { perResourceTimeoutMs: 20, overallTimeoutMs: 50 },
                  })),
                  "stalled stream read",
                );
                if (!cancelled) throw new Error("stalled stream reader was not cancelled");
                if (result.attachment_files.length !== 0 || result.resource_limitations.length !== 1) {
                  throw new Error(`stalled stream did not fail safely: ${JSON.stringify(result)}`);
                }
                if (!result.resource_limitations[0].limitation.includes("deadline")) {
                  throw new Error(`deadline limitation missing: ${JSON.stringify(result)}`);
                }
                if (result.resource_limitations[0].code !== "collection_timeout") {
                  throw new Error(`timeout code missing: ${JSON.stringify(result)}`);
                }
              },

              never_settling_read_and_cancel_still_timeout_and_reenable_analyze: async () => {
                let cancelCalled = false;
                const reader = {
                  read: () => new Promise(() => {}),
                  cancel: () => {
                    cancelCalled = true;
                    return new Promise(() => {});
                  },
                  releaseLock: () => {},
                };
                const doc = resourceDocument([
                  resource("stalled.pdf", "pdf", "/cgi-bin/download?file=stalled-read-cancel"),
                ]);
                const api = loadCollector(async () => ({
                  ok: true,
                  redirected: false,
                  headers: { get: () => null },
                  body: { getReader: () => reader },
                }));

                const listeners = new Map();
                const elements = new Map();
                for (const id of [
                  "status", "priority", "summary", "category", "engine", "decision-brief",
                  "conversation-timeline", "attachment-insights", "attachments", "risks", "actions",
                  "draft", "analyze-button", "copy-draft-button",
                ]) {
                  elements.set(`#${id}`, {
                    textContent: "", value: "", disabled: false,
                    addEventListener: (type, callback) => listeners.set(`${id}:${type}`, callback),
                  });
                }
                let receivedPayload;
                const fingerprint = "msg-v1-aaaaaaaaaaaaaaaa";
                const popupContext = {
                  document: { querySelector: (selector) => elements.get(selector) || null },
                  navigator: { clipboard: { writeText: async () => {} } },
                  chrome: { tabs: {
                    query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                    sendMessage: async (_tabId, message) => {
                      if (message.type === "REVALIDATE_CURRENT_EMAIL") {
                        return { ok: true, message_fingerprint: fingerprint };
                      }
                      const resources = await api.collectVisibleResources(
                        doc,
                        trustedResourceOptions(doc, {
                          limits: { perResourceTimeoutMs: 20, overallTimeoutMs: 50 },
                        }),
                      );
                      return {
                        ok: true,
                        message_fingerprint: fingerprint,
                        payload: {
                          subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                          body_text: "Synthetic body", attachments: [], thread_segments: [],
                          attachment_files: resources.attachment_files,
                          resource_limitations: resources.resource_limitations,
                        },
                      };
                    },
                  } },
                  EmailAssistantApi: {
                    analyzeCurrentEmail: async (payload) => {
                      receivedPayload = payload;
                      return { ok: false, error: { message: "Synthetic stop after payload capture." } };
                    },
                  },
                  EmailAssistantRender: {
                    clearAnalysis: () => {}, renderAttachments: () => {}, renderAnalysis: () => {},
                  },
                };
                vm.runInNewContext(popupSource, popupContext, { filename: "popup.js" });
                const analyze = listeners.get("analyze-button:click");
                await withinTestDeadline(analyze(), "Analyze with stalled read and cancel");

                if (!cancelCalled) throw new Error("best-effort reader cancellation was not triggered");
                if (!receivedPayload || receivedPayload.resource_limitations.length !== 1) {
                  throw new Error(`Analyze did not receive timeout limitation: ${JSON.stringify(receivedPayload)}`);
                }
                if (!receivedPayload.resource_limitations[0].limitation.includes("deadline")) {
                  throw new Error(`timeout limitation missing: ${JSON.stringify(receivedPayload)}`);
                }
                if (receivedPayload.resource_limitations[0].code !== "collection_timeout") {
                  throw new Error(`timeout code missing: ${JSON.stringify(receivedPayload)}`);
                }
                if (elements.get("#analyze-button").disabled !== false) {
                  throw new Error("Analyze remained disabled after resource timeout");
                }
              },

              candidate_overflow_is_bounded_with_one_aggregate_limitation: async () => {
                const api = loadCollector(async () => { throw new Error("unsupported resources must not fetch"); });
                if (!Number.isInteger(api.MAX_RESOURCE_CANDIDATES) || api.MAX_RESOURCE_CANDIDATES < 5) {
                  throw new Error("candidate scan cap is missing");
                }
                if (!Number.isInteger(api.MAX_RESOURCE_LIMITATIONS) || api.MAX_RESOURCE_LIMITATIONS < 2) {
                  throw new Error("limitation report cap is missing");
                }
                const candidates = Array.from(
                  { length: api.MAX_RESOURCE_CANDIDATES },
                  (_value, index) => resource(
                    `unsupported-${index}.txt`,
                    "text/plain",
                    `/cgi-bin/download?file=unsupported-${index}`,
                  ),
                );
                const poison = resource("must-not-scan.pdf", "pdf", "/cgi-bin/download?file=poison");
                const poisonGetAttribute = poison.getAttribute.bind(poison);
                poison.getAttribute = (name) => {
                  if (["id", "class"].includes(name)) return poisonGetAttribute(name);
                  throw new Error("candidate scan exceeded cap");
                };
                const doc = resourceDocument([...candidates, poison]);
                const result = await api.collectVisibleResources(doc, trustedResourceOptions(doc));
                if (result.resource_limitations.length > api.MAX_RESOURCE_LIMITATIONS) {
                  throw new Error(`limitation report exceeded cap: ${JSON.stringify(result)}`);
                }
                const aggregate = result.resource_limitations.filter((item) =>
                  item.limitation.includes("additional current-message resource candidates were omitted"),
                );
                if (aggregate.length !== 1) {
                  throw new Error(`expected one aggregate omission: ${JSON.stringify(result)}`);
                }
                if (aggregate[0].code !== "candidate_omission") {
                  throw new Error(`aggregate code missing: ${JSON.stringify(result)}`);
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
        script = script.replace("__COLLECTOR_PATH__", json.dumps(str(COLLECTOR)))
        script = script.replace("__CLASSIFIER_PATH__", json.dumps(str(CLASSIFIER)))
        script = script.replace("__POPUP_PATH__", json.dumps(str(POPUP)))
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

    def test_load_and_thread_extraction_do_not_fetch(self) -> None:
        self.run_node_case("load_and_thread_extraction_do_not_fetch")

    def test_ambiguous_history_keeps_only_verified_current_body(self) -> None:
        self.run_node_case("ambiguous_history_keeps_only_verified_current_body")

    def test_message_authored_history_inside_verified_body_is_ignored(self) -> None:
        self.run_node_case("message_authored_history_inside_verified_body_is_ignored")

    def test_structured_sibling_history_uses_verified_thread_boundary(self) -> None:
        self.run_node_case("structured_sibling_history_uses_verified_thread_boundary")

    def test_visible_thread_segments_are_normalized_oldest_first(self) -> None:
        self.run_node_case("visible_thread_segments_are_normalized_oldest_first")

    def test_hidden_and_background_resources_are_excluded(self) -> None:
        self.run_node_case("hidden_and_background_resources_are_excluded")

    def test_legacy_tencent_download_control_requires_complete_positive_evidence(self) -> None:
        self.run_node_case("legacy_tencent_download_control_requires_complete_positive_evidence")

    def test_legacy_data_filename_metadata_is_typed_and_fail_closed_before_fetch(
        self,
    ) -> None:
        self.run_node_case(
            "legacy_data_filename_metadata_is_typed_and_fail_closed_before_fetch"
        )

    def test_untyped_legacy_responses_require_allowlisted_header_signature_evidence(self) -> None:
        self.run_node_case(
            "untyped_legacy_responses_require_allowlisted_header_signature_evidence"
        )

    def test_stylesheet_hidden_root_and_resources_are_excluded(self) -> None:
        self.run_node_case("stylesheet_hidden_root_and_resources_are_excluded")

    def test_email_authored_same_origin_links_are_never_fetched(self) -> None:
        self.run_node_case("email_authored_same_origin_links_are_never_fetched")

    def test_unverified_controls_fail_closed_without_fetching(self) -> None:
        self.run_node_case("unverified_controls_fail_closed_without_fetching")

    def test_unapproved_same_origin_endpoints_are_never_fetched(self) -> None:
        self.run_node_case("unapproved_same_origin_endpoints_are_never_fetched")

    def test_supported_same_origin_bytes_use_exact_upload_allowlist(self) -> None:
        self.run_node_case("supported_same_origin_bytes_use_exact_upload_allowlist")

    def test_visible_attachment_and_business_inline_image_share_existing_payload(self) -> None:
        self.run_node_case("visible_attachment_and_business_inline_image_share_existing_payload")

    def test_signature_history_repeated_ui_hidden_external_and_ambiguous_media_are_excluded(
        self,
    ) -> None:
        self.run_node_case(
            "signature_history_repeated_ui_hidden_external_and_ambiguous_media_are_excluded"
        )

    def test_known_thread_selector_image_is_excluded(self) -> None:
        self.run_node_case("known_thread_selector_image_is_excluded")

    def test_complete_header_blockquote_image_is_excluded_but_current_image_is_collected(
        self,
    ) -> None:
        self.run_node_case(
            "complete_header_blockquote_image_is_excluded_but_current_image_is_collected"
        )

    def test_ordinary_blockquote_current_image_is_not_blanket_rejected(self) -> None:
        self.run_node_case("ordinary_blockquote_current_image_is_not_blanket_rejected")

    def test_attachment_layout_may_be_offscreen_but_inline_images_keep_viewport_gate(self) -> None:
        self.run_node_case(
            "attachment_layout_may_be_offscreen_but_inline_images_keep_viewport_gate"
        )

    def test_stale_verified_context_after_fetch_discards_bytes(self) -> None:
        self.run_node_case("stale_verified_context_after_fetch_discards_bytes")

    def test_changed_resource_identity_after_fetch_discards_bytes(self) -> None:
        self.run_node_case("changed_resource_identity_after_fetch_discards_bytes")

    def test_redirected_response_is_rejected(self) -> None:
        self.run_node_case("redirected_response_is_rejected")

    def test_unsafe_unsupported_failed_and_oversized_resources_return_limitations(self) -> None:
        self.run_node_case("unsafe_unsupported_failed_and_oversized_resources_return_limitations")

    def test_known_body_container_is_checked_before_candidate_fetch(self) -> None:
        self.run_node_case("known_body_container_is_checked_before_candidate_fetch")

    def test_non_direct_message_root_is_rejected_before_candidate_fetch(self) -> None:
        self.run_node_case("non_direct_message_root_is_rejected_before_candidate_fetch")

    def test_mismatched_verified_document_is_rejected_before_candidate_fetch(self) -> None:
        self.run_node_case("mismatched_verified_document_is_rejected_before_candidate_fetch")

    def test_nested_structural_envelope_is_rejected_before_candidate_fetch(self) -> None:
        self.run_node_case("nested_structural_envelope_is_rejected_before_candidate_fetch")

    def test_additional_global_known_body_root_is_rejected_before_candidate_fetch(self) -> None:
        self.run_node_case("additional_global_known_body_root_is_rejected_before_candidate_fetch")

    def test_count_and_total_byte_bounds_stop_additional_transfer(self) -> None:
        self.run_node_case("count_and_total_byte_bounds_stop_additional_transfer")

    def test_missing_content_length_streams_within_budget(self) -> None:
        self.run_node_case("missing_content_length_streams_within_budget")

    def test_missing_length_without_stream_rejects_before_arraybuffer(self) -> None:
        self.run_node_case("missing_length_without_stream_rejects_before_arraybuffer")

    def test_false_small_length_without_stream_rejects_before_arraybuffer(self) -> None:
        self.run_node_case("false_small_length_without_stream_rejects_before_arraybuffer")

    def test_announced_oversize_never_settling_cancel_returns_immediately(self) -> None:
        self.run_node_case("announced_oversize_never_settling_cancel_returns_immediately")

    def test_oversized_stream_cancels_without_upload_and_continues(self) -> None:
        self.run_node_case("oversized_stream_cancels_without_upload_and_continues")

    def test_stalled_fetch_is_aborted_and_returns_a_safe_limitation(self) -> None:
        self.run_node_case("stalled_fetch_is_aborted_and_returns_a_safe_limitation")

    def test_stalled_stream_read_is_cancelled_and_returns_a_safe_limitation(self) -> None:
        self.run_node_case("stalled_stream_read_is_cancelled_and_returns_a_safe_limitation")

    def test_never_settling_read_and_cancel_still_timeout_and_reenable_analyze(self) -> None:
        self.run_node_case("never_settling_read_and_cancel_still_timeout_and_reenable_analyze")

    def test_candidate_overflow_is_bounded_with_one_aggregate_limitation(self) -> None:
        self.run_node_case("candidate_overflow_is_bounded_with_one_aggregate_limitation")


if __name__ == "__main__":
    unittest.main()
