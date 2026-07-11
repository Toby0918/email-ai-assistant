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


class BrowserExtensionCurrentMessageCollectorTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__COLLECTOR_PATH__, "utf8");

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
              constructor(body, baseURI = "https://exmail.qq.com/cgi-bin/readmail") {
                this.body = body;
                this.baseURI = baseURI;
                this.location = new URL(baseURI);
                this.defaultView = {
                  getComputedStyle: (element) => ({
                    display: element.style.display || "block",
                    visibility: element.style.visibility || "visible",
                  }),
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

            function messageDocument(children, background = []) {
              const current = new FakeElement({
                attrs: { "data-email-current-message": "true" },
                children,
              });
              return new FakeDocument(new FakeElement({ tag: "body", children: [current, ...background] }));
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
                "data-resource-url": url,
                ...(options.attrs || {}),
              };
              return new FakeElement({ tag: "a", attrs, ...options, attrs });
            }

            function response(bytes, ok = true) {
              const data = Uint8Array.from(bytes);
              return {
                ok,
                headers: { get: (name) => name.toLowerCase() === "content-length" ? String(data.byteLength) : null },
                arrayBuffer: async () => data.buffer.slice(0),
              };
            }

            function loadCollector(fetchImpl) {
              const context = {
                URL,
                Uint8Array,
                ArrayBuffer,
                fetch: fetchImpl,
                btoa: (binary) => Buffer.from(binary, "binary").toString("base64"),
              };
              context.window = context;
              vm.runInNewContext(source, context, { filename: "current_message_collector.js" });
              const api = context.EmailAssistantCurrentMessageCollector;
              if (!api) throw new Error("EmailAssistantCurrentMessageCollector is missing");
              return api;
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
                  children: [resource("parent-hidden.pdf", "pdf", "/parent-hidden")],
                });
                const background = resource("background.pdf", "pdf", "/background");
                const doc = messageDocument([
                  resource("visible.pdf", "pdf", "/visible"),
                  resource("hidden.pdf", "pdf", "/hidden", { hidden: true }),
                  resource("aria.pdf", "pdf", "/aria", { attrs: { "aria-hidden": "true" } }),
                  hiddenParent,
                ], [background]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response([1, 2]);
                });
                const result = await api.collectVisibleResources(doc);
                if (calls.length !== 1 || calls[0] !== "https://exmail.qq.com/visible") {
                  throw new Error(`unexpected fetches: ${JSON.stringify(calls)}`);
                }
                if (result.attachment_files.length !== 1) throw new Error("visible resource not collected");
                if (result.resource_limitations.length !== 0) throw new Error("hidden resource returned metadata");
              },

              supported_same_origin_bytes_use_exact_upload_allowlist: async () => {
                const calls = [];
                const doc = messageDocument([
                  resource("../../photo.png", "image/png", "/download/photo"),
                  resource("scope.pdf", "application/pdf", "https://exmail.qq.com/download/pdf"),
                  resource("cost.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "/download/xlsx"),
                  resource("notes.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "/download/docx"),
                ]);
                const payloads = [[0, 255], [1, 2, 3], [4], [5, 6]];
                const api = loadCollector(async (url, options) => {
                  calls.push({ url, options });
                  return response(payloads[calls.length - 1]);
                });
                const result = await api.collectVisibleResources(doc);
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
                const doc = messageDocument([
                  resource("outside.pdf", "pdf", "https://example.invalid/outside"),
                  resource("script.exe", "application/octet-stream", "/script"),
                  resource("unreadable.pdf", "pdf", "/unreadable"),
                  resource("large.pdf", "pdf", "/large", { attrs: { "data-size": "5" } }),
                ]);
                const api = loadCollector(async () => {
                  fetchCount += 1;
                  throw new Error("private download failure details");
                });
                const result = await api.collectVisibleResources(doc, {
                  limits: { maxFiles: 5, maxFileBytes: 4, maxTotalBytes: 8 },
                });
                if (result.attachment_files.length !== 0) throw new Error("unsafe bytes were emitted");
                if (result.resource_limitations.length !== 4) throw new Error(JSON.stringify(result));
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

              count_and_total_byte_bounds_stop_additional_transfer: async () => {
                const calls = [];
                const doc = messageDocument([
                  resource("first.pdf", "pdf", "/first", { attrs: { "data-size": "2" } }),
                  resource("second.pdf", "pdf", "/second", { attrs: { "data-size": "3" } }),
                  resource("total.pdf", "pdf", "/total", { attrs: { "data-size": "1" } }),
                  resource("count.pdf", "pdf", "/count", { attrs: { "data-size": "1" } }),
                ]);
                const api = loadCollector(async (url) => {
                  calls.push(url);
                  return response(calls.length === 1 ? [1, 2] : [3, 4, 5]);
                });
                const result = await api.collectVisibleResources(doc, {
                  limits: { maxFiles: 3, maxFileBytes: 4, maxTotalBytes: 5 },
                });
                if (calls.length !== 2) throw new Error(`limits allowed extra transfer: ${JSON.stringify(calls)}`);
                if (result.attachment_files.length !== 2) throw new Error(JSON.stringify(result));
                const messages = result.resource_limitations.map((item) => item.limitation).join(" | ");
                if (!messages.includes("total frontend")) throw new Error("total-byte limitation missing");
                if (!messages.includes("file frontend")) throw new Error("file-count limitation missing");
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
        script = script.replace("__CASE_NAME__", json.dumps(case_name))
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
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

    def test_supported_same_origin_bytes_use_exact_upload_allowlist(self) -> None:
        self.run_node_case("supported_same_origin_bytes_use_exact_upload_allowlist")

    def test_unsafe_unsupported_failed_and_oversized_resources_return_limitations(self) -> None:
        self.run_node_case("unsafe_unsupported_failed_and_oversized_resources_return_limitations")

    def test_count_and_total_byte_bounds_stop_additional_transfer(self) -> None:
        self.run_node_case("count_and_total_byte_bounds_stop_additional_transfer")


if __name__ == "__main__":
    unittest.main()
