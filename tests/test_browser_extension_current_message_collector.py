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
            const popupSource = fs.readFileSync(__POPUP_PATH__, "utf8");

            class FakeElement {
              constructor({
                tag = "div",
                attrs = {},
                text = "",
                children = [],
                hidden = false,
                style = {},
              } = {}) {
                this.tagName = tag.toUpperCase();
                this.attrs = { ...attrs };
                this.innerText = text;
                this.textContent = text;
                this.children = children;
                this.hidden = hidden;
                this.style = style;
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
            }

            class FakeDocument {
              constructor(body, baseURI = "https://exmail.qq.com/cgi-bin/readmail", computedStyle = null) {
                this.body = body;
                this.baseURI = baseURI;
                this.location = new URL(baseURI);
                this.defaultView = {
                  getComputedStyle: computedStyle || ((element) => ({
                    display: element.style.display || "block",
                    visibility: element.style.visibility || "visible",
                  })),
                };
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
              doc.currentMessageContainer = container;
              doc.verifiedResourceCandidates = hostResources;
              return doc;
            }

            function resourceDocument(resources, bodyChildren = [], background = []) {
              return messageDocument(bodyChildren, background, resources);
            }

            function trustedResourceOptions(doc, options = {}) {
              return {
                currentMessageRoot: doc.currentMessageRoot,
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
              return new FakeElement({ tag: "a", attrs, ...options, attrs });
            }

            function response(bytes, ok = true) {
              if (!ok) {
                return { ok: false, headers: { get: () => null } };
              }
              return streamingResponse([bytes], { contentLength: String(bytes.length) }).response;
            }

            function streamingResponse(chunks, { contentLength = null } = {}) {
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
                  headers: { get: (name) => name.toLowerCase() === "content-length" ? contentLength : null },
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
                if (api.MAX_RESOURCE_BYTES !== 10 * 1024 * 1024) throw new Error("per-file limit mismatch");
                if (api.MAX_TOTAL_RESOURCE_BYTES !== 25 * 1024 * 1024) throw new Error("total limit mismatch");
              },

              visible_thread_segments_are_normalized_in_page_order: () => {
                const hiddenParent = new FakeElement({
                  style: { visibility: "hidden" },
                  children: [thread("Hidden by parent")],
                });
                const doc = messageDocument([
                  thread("  First   request \n needs review  ", {
                    "data-from": "  buyer@example.test ",
                    "data-to": " sales@example.test ",
                    "data-sent-at": " 2026-07-10T09:00:00Z ",
                    "data-timestamp-text": " Yesterday 09:00 ",
                    "data-subject": " Re:  Quote ",
                    "data-private-url": "https://example.invalid/private",
                    "data-token": "not-exported",
                  }),
                  thread("Hidden property", {}, { hidden: true }),
                  thread("Aria hidden", { "aria-hidden": "true" }),
                  thread("Display hidden", {}, { style: { display: "none" } }),
                  hiddenParent,
                  thread(" Second   answer ", { "data-from": "sales@example.test" }),
                ]);
                const api = loadCollector(async () => response([]));
                const segments = api.extractVisibleThreadSegments(doc);
                if (segments.length !== 2) throw new Error(`unexpected segments: ${JSON.stringify(segments)}`);
                if (segments[0].position !== 0 || segments[1].position !== 1) throw new Error("page order lost");
                if (segments[0].body_text !== "First request needs review") throw new Error("body not normalized");
                if (segments[0].from !== "buyer@example.test") throw new Error("sender not normalized");
                if (segments[0].to !== "sales@example.test") throw new Error("recipient not normalized");
                if (segments[0].sent_at !== "2026-07-10T09:00:00Z") throw new Error("sent_at not normalized");
                if (segments[0].timestamp_text !== "Yesterday 09:00") throw new Error("timestamp not normalized");
                if (segments[0].subject !== "Re: Quote") throw new Error("subject not normalized");
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
                poison.getAttribute = () => { throw new Error("candidate scan exceeded cap"); };
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

    def test_visible_thread_segments_are_normalized_in_page_order(self) -> None:
        self.run_node_case("visible_thread_segments_are_normalized_in_page_order")

    def test_hidden_and_background_resources_are_excluded(self) -> None:
        self.run_node_case("hidden_and_background_resources_are_excluded")

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

    def test_unsafe_unsupported_failed_and_oversized_resources_return_limitations(self) -> None:
        self.run_node_case("unsafe_unsupported_failed_and_oversized_resources_return_limitations")

    def test_known_body_container_is_checked_before_candidate_fetch(self) -> None:
        self.run_node_case("known_body_container_is_checked_before_candidate_fetch")

    def test_non_direct_message_root_is_rejected_before_candidate_fetch(self) -> None:
        self.run_node_case("non_direct_message_root_is_rejected_before_candidate_fetch")

    def test_count_and_total_byte_bounds_stop_additional_transfer(self) -> None:
        self.run_node_case("count_and_total_byte_bounds_stop_additional_transfer")

    def test_missing_content_length_streams_within_budget(self) -> None:
        self.run_node_case("missing_content_length_streams_within_budget")

    def test_missing_length_without_stream_rejects_before_arraybuffer(self) -> None:
        self.run_node_case("missing_length_without_stream_rejects_before_arraybuffer")

    def test_false_small_length_without_stream_rejects_before_arraybuffer(self) -> None:
        self.run_node_case("false_small_length_without_stream_rejects_before_arraybuffer")

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
