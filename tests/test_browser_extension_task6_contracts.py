"""Focused manifest and transport contracts for Task 6 integration."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"
API_CLIENT = EXTENSION / "shared" / "api_client.js"
RESOURCE_COLLECTOR = EXTENSION / "content" / "current_message_collector.js"


class BrowserExtensionTask6ContractTests(unittest.TestCase):
    def test_analysis_post_wait_is_15_seconds_and_resource_collection_stays_20_seconds(self) -> None:
        api_source = API_CLIENT.read_text(encoding="utf-8")
        collector_source = RESOURCE_COLLECTOR.read_text(encoding="utf-8")

        self.assertIn("MAX_ANALYZE_TIMEOUT_MS = 15000", api_source)
        self.assertIn("MAX_OVERALL_RESOURCE_TIMEOUT_MS = 20000", collector_source)
        self.assertNotIn("RESOURCE_COLLECTION_TIMEOUT_MS", api_source)

    def test_oversized_resource_timeout_uses_active_20_second_cumulative_deadline(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__COLLECTOR_PATH__, "utf8");

            class FakeElement {
              constructor({ tag = "div", attrs = {}, children = [] } = {}) {
                this.tagName = tag.toUpperCase();
                this.attrs = { ...attrs };
                this.children = children;
                this.hidden = false;
                this.style = {};
                this.innerText = "";
                this.textContent = "";
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
              constructor(body) {
                this.body = body;
                this.baseURI = "https://exmail.qq.com/cgi-bin/readmail";
                this.location = new URL(this.baseURI);
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
              const attributeMatch = selector.match(/^(?:([a-z]+))?\[([^=\]]+)(?:=['"]?([^'"]+)['"]?)?\]$/i);
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

            function resource(index) {
              const filename = `bounded-${index}.pdf`;
              return new FakeElement({
                tag: "a",
                attrs: {
                  href: `/cgi-bin/download?file=${index}`,
                  download: filename,
                  "data-filename": filename,
                  "data-type": "pdf",
                },
              });
            }

            const resources = [1, 2, 3, 4].map(resource);
            const currentRoot = new FakeElement({ attrs: { class: "mail-content" } });
            const controls = new FakeElement({ children: resources });
            const currentMessageContainer = new FakeElement({ children: [currentRoot, controls] });
            const doc = new FakeDocument(new FakeElement({ tag: "body", children: [currentMessageContainer] }));

            let now = 0;
            let fetchCalls = 0;
            let nextTimerId = 1;
            const scheduledDelays = [];
            class FakeDate extends Date {
              static now() { return now; }
            }
            const context = {
              URL,
              Uint8Array,
              ArrayBuffer,
              AbortController,
              Date: FakeDate,
              setTimeout: (callback, delay) => {
                scheduledDelays.push(delay);
                now += delay;
                callback();
                return nextTimerId++;
              },
              clearTimeout: () => {},
              fetch: () => {
                fetchCalls += 1;
                return new Promise(() => {});
              },
              btoa: (binary) => Buffer.from(binary, "binary").toString("base64"),
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "current_message_collector.js" });

            (async () => {
              const result = await context.EmailAssistantCurrentMessageCollector.collectVisibleResources(doc, {
                topLevelDocument: doc,
                currentMessageRoot: currentRoot,
                currentMessageContainer,
                verifiedResourceCandidates: resources,
                resourceControlsVerified: true,
                limits: {
                  perResourceTimeoutMs: 999999,
                  overallTimeoutMs: 999999,
                },
              });
              const expectedDelays = [8000, 8000, 4000];
              if (JSON.stringify(scheduledDelays) !== JSON.stringify(expectedDelays)) {
                throw new Error(`unexpected cumulative deadline schedule: ${JSON.stringify(scheduledDelays)}`);
              }
              const scheduledTotal = scheduledDelays.reduce((total, delay) => total + delay, 0);
              if (scheduledTotal !== 20000 || now !== 20000) {
                throw new Error(`resource collection exceeded 20000ms: scheduled=${scheduledTotal}, clock=${now}`);
              }
              if (fetchCalls !== 3) {
                throw new Error(`overall deadline allowed ${fetchCalls} resource fetches`);
              }
              const timeoutCount = result.resource_limitations.filter(
                (item) => item.code === "collection_timeout",
              ).length;
              if (timeoutCount !== 3) {
                throw new Error(`timed-out resources were not recorded: ${JSON.stringify(result)}`);
              }
              if (!result.resource_limitations.some((item) => item.code === "candidate_omission")) {
                throw new Error(`post-deadline candidate was not omitted: ${JSON.stringify(result)}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__COLLECTOR_PATH__", json.dumps(str(RESOURCE_COLLECTOR)))

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

    def test_analysis_timeout_overrides_keep_small_values_and_cap_large_values(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__API_CLIENT_PATH__, "utf8");
            const requestedDelays = [];
            const context = {
              AbortController,
              setTimeout: (_callback, delay) => {
                requestedDelays.push(delay);
                return requestedDelays.length;
              },
              clearTimeout: () => {},
              fetch: async () => ({
                ok: true,
                status: 200,
                json: async () => ({ ok: true }),
              }),
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "api_client.js" });

            (async () => {
              const email = {
                subject: "Synthetic",
                from: "sender@example.test",
                body_text: "Synthetic body",
              };
              await context.EmailAssistantApi.analyzeCurrentEmail(email);
              await context.EmailAssistantApi.analyzeCurrentEmail(email, { timeoutMs: 40000 });
              await context.EmailAssistantApi.analyzeCurrentEmail(email, { timeoutMs: 17 });
              const expected = [15000, 15000, 17];
              if (JSON.stringify(requestedDelays) !== JSON.stringify(expected)) {
                throw new Error(`unexpected analysis waits: ${JSON.stringify(requestedDelays)}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__API_CLIENT_PATH__", json.dumps(str(API_CLIENT)))

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

    def test_manifest_loads_collector_before_adapter_with_bounded_permissions(self) -> None:
        manifest = json.loads((EXTENSION / "manifest.json").read_text(encoding="utf-8"))
        script = manifest["content_scripts"][0]

        self.assertEqual(
            script["js"],
            ["content/current_message_collector.js", "content/exmail_adapter.js"],
        )
        self.assertEqual(script["matches"], ["https://exmail.qq.com/*"])
        self.assertEqual(
            manifest["host_permissions"],
            ["https://exmail.qq.com/*", "http://127.0.0.1:8765/*"],
        )
        self.assertNotIn("<all_urls>", json.dumps(manifest))

    def test_api_client_deeply_allowlists_task6_payload(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__API_CLIENT_PATH__, "utf8");
            let requestBody;
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              fetch: async (_url, options) => {
                requestBody = JSON.parse(options.body);
                return { ok: true, status: 200, json: async () => ({ ok: true }) };
              },
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "api_client.js" });

            (async () => {
              await context.EmailAssistantApi.analyzeCurrentEmail({
                subject: "Synthetic subject",
                from: "sender@example.test",
                to: ["recipient@example.test"],
                sent_at: "2026-07-11 10:00",
                body_text: "Synthetic body",
                attachments: [{
                  filename: "visible.pdf", size: "3 B", type: "pdf", cookie: "PRIVATE_COOKIE",
                }],
                thread_segments: [{
                  position: 0, from: "sender@example.test", to: "recipient@example.test",
                  sent_at: "2026-07-11 10:00", timestamp_text: "Today", subject: "Re: Synthetic",
                  body_text: "Thread body", hidden_id: "PRIVATE_HIDDEN_ID",
                }],
                attachment_files: [{
                  filename: "visible.pdf", type: "pdf", size: 3, content_base64: "AQID",
                  authorization: "PRIVATE_AUTHORIZATION", download_url: "PRIVATE_DOWNLOAD_URL",
                }],
                resource_limitations: [{
                  code: "frontend_limit",
                  filename: "oversized.pdf", type: "pdf", size: 999,
                  limitation: "Resource exceeds the configured limit.",
                  private_url: "PRIVATE_LIMITATION_URL", token: "PRIVATE_LIMITATION_TOKEN",
                }, {
                  code: "not_allowlisted",
                  filename: "forged.pdf", type: "pdf", size: 1,
                  limitation: "PRIVATE_UNKNOWN_CODE",
                }, {
                  code: "operational_failure",
                  filename: "forged-operational.pdf", type: "pdf", size: 1,
                  limitation: "PRIVATE_FORGED_OPERATIONAL",
                }],
                token: "PRIVATE_TOKEN",
                arbitrary_extra: "PRIVATE_EXTRA",
              });

              const expectedTopLevel = [
                "attachment_files", "attachments", "body_text", "from", "resource_limitations",
                "sent_at", "subject", "thread_segments", "to", "user_confirmed",
              ];
              const keys = Object.keys(requestBody).sort();
              if (JSON.stringify(keys) !== JSON.stringify(expectedTopLevel)) {
                throw new Error(`unexpected top-level keys: ${JSON.stringify(keys)}`);
              }
              const exactKeys = (value, expected, label) => {
                const actual = Object.keys(value).sort();
                const wanted = [...expected].sort();
                if (JSON.stringify(actual) !== JSON.stringify(wanted)) {
                  throw new Error(`${label} leaked keys: ${JSON.stringify(actual)}`);
                }
              };
              exactKeys(requestBody.attachments[0], ["filename", "size", "type"], "attachment");
              exactKeys(
                requestBody.thread_segments[0],
                ["position", "from", "to", "sent_at", "timestamp_text", "subject", "body_text"],
                "thread segment",
              );
              exactKeys(
                requestBody.attachment_files[0],
                ["filename", "type", "size", "content_base64"],
                "attachment file",
              );
              exactKeys(
                requestBody.resource_limitations[0],
                ["code", "filename", "type", "size", "limitation"],
                "resource limitation",
              );
              if (requestBody.resource_limitations.length !== 1) {
                throw new Error(`non-frontend limitation code crossed boundary: ${JSON.stringify(requestBody.resource_limitations)}`);
              }
              const serialized = JSON.stringify(requestBody);
              for (const marker of [
                "PRIVATE_COOKIE", "PRIVATE_HIDDEN_ID", "PRIVATE_AUTHORIZATION",
                "PRIVATE_DOWNLOAD_URL", "PRIVATE_LIMITATION_URL", "PRIVATE_LIMITATION_TOKEN",
                "PRIVATE_UNKNOWN_CODE", "PRIVATE_FORGED_OPERATIONAL", "PRIVATE_TOKEN", "PRIVATE_EXTRA",
              ]) {
                if (serialized.includes(marker)) throw new Error(`private marker leaked: ${marker}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__API_CLIENT_PATH__", json.dumps(str(API_CLIENT)))

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

    def test_api_client_aborts_stalled_backend_with_retryable_safe_error(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__API_CLIENT_PATH__, "utf8");
            let requestSignal;
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              fetch: async (_url, options) => new Promise((_resolve, reject) => {
                requestSignal = options.signal;
                options.signal.addEventListener("abort", () => {
                  const error = new Error("PRIVATE_BACKEND_TIMEOUT_DETAIL");
                  error.name = "AbortError";
                  reject(error);
                });
              }),
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "api_client.js" });

            (async () => {
              const data = await Promise.race([
                context.EmailAssistantApi.analyzeCurrentEmail({
                  subject: "Synthetic", from: "sender@example.test", body_text: "Synthetic body",
                }, { timeoutMs: 20 }),
                new Promise((_resolve, reject) => setTimeout(
                  () => reject(new Error("backend request did not honor its deadline")),
                  250,
                )),
              ]);
              if (!requestSignal || requestSignal.aborted !== true) {
                throw new Error("stalled backend request was not aborted");
              }
              if (data.ok !== false || data.error.code !== "LOCAL_ANALYSIS_TIMEOUT") {
                throw new Error(`unexpected timeout response: ${JSON.stringify(data)}`);
              }
              if (data.error.retryable !== true || !data.error.message.includes("try again")) {
                throw new Error(`timeout was not safely retryable: ${JSON.stringify(data)}`);
              }
              if (JSON.stringify(data).includes("PRIVATE_BACKEND_TIMEOUT_DETAIL")) {
                throw new Error("private timeout detail leaked");
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__API_CLIENT_PATH__", json.dumps(str(API_CLIENT)))
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


if __name__ == "__main__":
    unittest.main()
