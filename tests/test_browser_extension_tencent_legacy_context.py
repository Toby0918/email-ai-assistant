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

            class FakeElement {
              constructor({ tag = "div", id = "", className = "", text = "",
                            children = [], attrs = {}, hidden = false, style = {} } = {}) {
                this.tagName = tag.toUpperCase();
                this.id = id;
                this.className = className;
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
                  getSelection: () => emptySelection(),
                  getComputedStyle: (element) => ({
                    display: element.style.display || "block",
                    visibility: element.style.visibility || "visible",
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

            function loadAdapter(doc, collectorOverride = null) {
              let listener;
              const rootWindow = {
                document: doc,
                frames: [],
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
              if (!collectorOverride) {
                vm.runInNewContext(collectorSource, context, {
                  filename: "current_message_collector.js",
                });
              }
              vm.runInNewContext(adapterSource, context, { filename: "exmail_adapter.js" });
              return listener;
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
              if (payload.from !== "sales@example.test") {
                throw new Error(`top-level sender was not taken from newest block: ${payload.from}`);
              }
              if (payload.subject !== "Re: Synthetic placement request") {
                throw new Error(`top-level subject was not current: ${payload.subject}`);
              }
              if (payload.sent_at !== "2026-07-11 10:30") {
                throw new Error(`top-level date was not current: ${payload.sent_at}`);
              }
              if (JSON.stringify(payload.to) !== JSON.stringify(["buyer@example.test"])) {
                throw new Error(`top-level recipient was not current: ${JSON.stringify(payload.to)}`);
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
                const envelope = new FakeElement({ className: "read-envelope", children: [subject, root] });
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
                  children: [unsafeSubject, unsafeRoot],
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
                if (!failed.ok || failed.payload.thread_segments.length || failed.payload.body_text) {
                  throw new Error(`collector error retained root: ${JSON.stringify(failed)}`);
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
                  children: [mixedSubject, mixedRoot],
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
                  children: [verifiedSubject, verifiedRoot],
                });
                const verifiedResult = await dispatch(
                  loadAdapter(new FakeDocument(verifiedBody), throwingCollector),
                );
                if (verifiedResult.payload.body_text) {
                  throw new Error(`heuristic currentRoot survived collector error: ${JSON.stringify(verifiedResult)}`);
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


if __name__ == "__main__":
    unittest.main()
