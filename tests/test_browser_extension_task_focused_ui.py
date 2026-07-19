"""Task 7 contracts for multimodal disclosure and safe UI diagnostics."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[1]
EXTENSION = ROOT / "frontend" / "browser_extension"
LOCAL_DEBUG = ROOT / "frontend" / "local_debug_page"
RENDERER = EXTENSION / "shared" / "render_analysis.js"
DISCLOSURE = (
    "After you click Analyze, configured remote AI providers may receive locally deidentified "
    "current visible email text and selected current-message images or files after local "
    "screening. Media pixels or document content may contain identifying information and are not "
    "guaranteed to be fully deidentified. Processing is not local-only, and no zero-retention "
    "guarantee is made."
)
LOADING_STATUS = "正在分析当前邮件及所选图片/文件，最长可能需要 60 秒。"
DEEPSEEK_REASON = "OpenAI 多模态结果未采用，本次使用 DeepSeek 文本回退。"
RULE_REASON = "远程模型结果未采用，本次使用安全规则结果。"
UNKNOWN_REASON = "分析引擎信息未确认，请人工核查本次结果。"


class BrowserExtensionTaskFocusedUiTests(unittest.TestCase):
    def test_manual_picker_is_optional_collapsed_and_truthful_about_local_origin(self) -> None:
        soup = BeautifulSoup((EXTENSION / "popup.html").read_text(encoding="utf-8"), "html.parser")
        picker = soup.select_one("details.manual-attachment-picker")
        self.assertIsNotNone(picker)
        self.assertFalse(picker.has_attr("open"))
        self.assertIn("可选", picker.get_text(" ", strip=True))
        self.assertIn("仅在点击 Analyze 后读取", picker.get_text(" ", strip=True))
        self.assertIn("无法验证本地文件是否来自当前邮件", picker.get_text(" ", strip=True))
        self.assertLess(
            str(soup).index('id="remote-processing-notice"'),
            str(soup).index('id="manual-attachment-files"'),
        )

    def test_both_surfaces_show_the_exact_same_persistent_disclosure(self) -> None:
        notices: list[str] = []
        for path in (EXTENSION / "popup.html", LOCAL_DEBUG / "index.html"):
            soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
            notice = soup.select_one("#remote-processing-notice")
            self.assertIsNotNone(notice)
            notices.append(notice.get_text(" ", strip=True))
            self.assertFalse(notice.has_attr("hidden"))
            self.assertNotEqual(notice.get("aria-hidden"), "true")
        self.assertEqual(notices, [DISCLOSURE, DISCLOSURE])

    def test_pending_post_status_and_narrow_task_order_are_shared(self) -> None:
        for path in (EXTENSION / "popup.js", LOCAL_DEBUG / "app.js"):
            script = path.read_text(encoding="utf-8")
            self.assertIn(LOADING_STATUS, script)

        for path in (EXTENSION / "popup.html", LOCAL_DEBUG / "index.html"):
            page = path.read_text(encoding="utf-8")
            positions = [
                page.index(f'id="{element_id}"')
                for element_id in (
                    "work-conclusion",
                    "work-current-request",
                    "work-next-steps",
                    "work-key-facts",
                    "work-must-check",
                )
            ]
            self.assertEqual(positions, sorted(positions))
            self.assertLess(positions[-1], page.index('<details class="analysis-details"'))
            self.assertNotRegex(page, r"<details\b[^>]*\bopen(?:\s|=|>)")

        css = (EXTENSION / "shared" / "analysis_components.css").read_text(encoding="utf-8")
        self.assertIn("@media (max-width: 360px)", css)
        self.assertIn("overflow-wrap: anywhere", css)

    def test_renderer_allowlists_engine_labels_and_fixed_fallback_reasons(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for shared renderer behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__RENDERER__, "utf8");
            const context = { window: {} };
            vm.runInNewContext(source, context, { filename: "render_analysis.js" });
            function field() { return { textContent: "", value: "", hidden: true }; }
            const fields = {
              engine: field(), fallbackBanner: field(), technicalDetails: field(),
              draftBody: field(), draftSubject: field(), draftReviewStatus: field(),
              draftReviewReasons: field(),
            };
            const base = {
              priority: "normal", category: "unknown", decision_brief: {},
              reply_draft: { body: "", needs_human_review: true },
            };
            function render(engine) {
              context.window.EmailAssistantRender.renderAnalysis(fields, {
                ...base,
                analysis_engine: engine,
              });
              return [
                fields.engine.textContent,
                fields.fallbackBanner.textContent,
                fields.technicalDetails.textContent,
              ].join("\n");
            }
            let output = render({ source: "ai_model", label: "OpenAI GPT-5.6 Sol" });
            if (fields.engine.textContent !== "OpenAI GPT-5.6 Sol") throw new Error(output);
            if (!fields.fallbackBanner.hidden || fields.fallbackBanner.textContent) throw new Error(output);

            for (const label of [
              "DeepSeek V4 Flash text fallback",
              "DeepSeek V4 Pro text fallback",
            ]) {
              output = render({ source: "ai_model", label });
              if (fields.engine.textContent !== "DeepSeek text fallback") throw new Error(output);
              if (fields.fallbackBanner.hidden || fields.fallbackBanner.textContent !== __DEEPSEEK_REASON__) {
                throw new Error(output);
              }
              if (!fields.technicalDetails.textContent.includes(__DEEPSEEK_REASON__)) throw new Error(output);
              if (output.includes(label)) throw new Error(`raw DeepSeek label leaked: ${output}`);
            }

            output = render({ source: "rule_fallback", label: "Rule fallback" });
            if (fields.engine.textContent !== "Rule fallback") throw new Error(output);
            if (fields.fallbackBanner.hidden || fields.fallbackBanner.textContent !== __RULE_REASON__) {
              throw new Error(output);
            }
            if (!fields.technicalDetails.textContent.includes(__RULE_REASON__)) throw new Error(output);

            const secrets = [
              "MALICIOUS_PROVIDER_LABEL", "PRIVATE_DIAGNOSTIC", "PRIVATE_REASON",
              "PRIVATE_PROVIDER_ERROR", "C:\\private\\payload.json", "source-id-123",
            ];
            output = render({
              source: "ai_model", label: secrets[0], detail: secrets[1],
              reason: secrets[2], provider_error: secrets[3], path: secrets[4], source_id: secrets[5],
            });
            if (fields.engine.textContent !== "未确认分析引擎") throw new Error(output);
            if (fields.fallbackBanner.hidden || fields.fallbackBanner.textContent !== __UNKNOWN_REASON__) {
              throw new Error(output);
            }
            if (!fields.technicalDetails.textContent.includes(__UNKNOWN_REASON__)) throw new Error(output);
            for (const secret of secrets) {
              if (output.includes(secret)) throw new Error(`private provider data leaked: ${secret}`);
            }

            output = render({ source: "rule_fallback", label: "MALICIOUS_RULE_LABEL" });
            if (fields.engine.textContent !== "未确认分析引擎") throw new Error(output);
            if (output.includes("MALICIOUS_RULE_LABEL")) throw new Error(output);
            """
        )
        script = (
            script.replace("__RENDERER__", json.dumps(str(RENDERER)))
            .replace("__DEEPSEEK_REASON__", json.dumps(DEEPSEEK_REASON, ensure_ascii=False))
            .replace("__RULE_REASON__", json.dumps(RULE_REASON, ensure_ascii=False))
            .replace("__UNKNOWN_REASON__", json.dumps(UNKNOWN_REASON, ensure_ascii=False))
        )
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, capture_output=True, encoding="utf-8",
            text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_renderer_rejects_inherited_and_accessor_engine_fields_consistently(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for shared renderer behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__RENDERER__, "utf8");
            const context = { window: {} };
            vm.runInNewContext(source, context, { filename: "render_analysis.js" });
            function field() { return { textContent: "", value: "", hidden: true }; }
            const fields = {
              engine: field(), fallbackBanner: field(), technicalDetails: field(),
              draftBody: field(), draftSubject: field(), draftReviewStatus: field(),
              draftReviewReasons: field(),
            };
            const base = {
              priority: "normal", category: "unknown", decision_brief: {},
              reply_draft: { body: "", needs_human_review: true },
            };
            function render(engine) {
              context.window.EmailAssistantRender.renderAnalysis(fields, {
                ...base, analysis_engine: engine,
              });
              const output = [
                fields.engine.textContent,
                fields.fallbackBanner.textContent,
                fields.technicalDetails.textContent,
              ].join("\n");
              if (fields.engine.textContent !== "未确认分析引擎") throw new Error(output);
              if (fields.fallbackBanner.hidden || fields.fallbackBanner.textContent !== __UNKNOWN_REASON__) {
                throw new Error(output);
              }
              if (!fields.technicalDetails.textContent.includes("分析引擎：未确认分析引擎") ||
                  !fields.technicalDetails.textContent.includes(__UNKNOWN_REASON__)) {
                throw new Error(`contradictory engine presentation: ${output}`);
              }
              return output;
            }

            const inherited = Object.create({
              source: "ai_model", label: "OpenAI GPT-5.6 Sol",
              context_scope: "relevant_history", context_limited: true,
            });
            let output = render(inherited);
            if (output.includes("OpenAI GPT-5.6 Sol") || output.includes("相关历史")) {
              throw new Error(`inherited engine fields accepted: ${output}`);
            }

            let getterReads = 0;
            const accessorEngine = {};
            for (const [key, value] of Object.entries({
              source: "ai_model", label: "OpenAI GPT-5.6 Sol",
              context_scope: "relevant_history", context_limited: true,
            })) {
              Object.defineProperty(accessorEngine, key, {
                enumerable: true,
                get() { getterReads += 1; return value; },
              });
            }
            output = render(accessorEngine);
            if (getterReads !== 0) throw new Error(`engine accessors executed ${getterReads} times`);
            if (output.includes("OpenAI GPT-5.6 Sol") || output.includes("相关历史")) {
              throw new Error(`accessor engine fields accepted: ${output}`);
            }
            """
        )
        script = (
            script.replace("__RENDERER__", json.dumps(str(RENDERER)))
            .replace("__UNKNOWN_REASON__", json.dumps(UNKNOWN_REASON, ensure_ascii=False))
        )
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, capture_output=True, encoding="utf-8",
            text=True, check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_error_status_allowlist_rejects_prototype_and_accessor_codes(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for frontend behavior tests")

        for name, source in (
            ("popup", EXTENSION / "popup.js"),
            ("local-debug", LOCAL_DEBUG / "app.js"),
        ):
            with self.subTest(surface=name):
                script = textwrap.dedent(
                    r"""
                    const fs = require("fs");
                    const vm = require("vm");
                    const source = fs.readFileSync(__APP__, "utf8");
                    const elements = new Map();
                    function element(selector) {
                      if (!elements.has(selector)) elements.set(selector, {
                        textContent: "", value: "", disabled: false,
                        addEventListener() {},
                      });
                      return elements.get(selector);
                    }
                    const context = {
                      AbortController, setTimeout, clearTimeout,
                      document: { querySelector: element },
                      navigator: { clipboard: { writeText: async () => {} } },
                      chrome: {}, EmailAssistantApi: {},
                      EmailAssistantRender: {}, fetch: async () => {},
                    };
                    context.window = context;
                    vm.runInNewContext(source, context, { filename: "frontend.js" });
                    const result = vm.runInContext(`(() => {
                      const generic = "分析未完成，请重试。";
                      const statuses = ["toString", "constructor", "__proto__"].map(
                        (code) => safeAnalysisErrorStatus({ code }),
                      );
                      const inherited = Object.create({ code: "LOCAL_ANALYSIS_TIMEOUT" });
                      statuses.push(safeAnalysisErrorStatus(inherited));
                      let reads = 0;
                      const accessor = {};
                      Object.defineProperty(accessor, "code", {
                        enumerable: true,
                        get() { reads += 1; return "LOCAL_ANALYSIS_TIMEOUT"; },
                      });
                      statuses.push(safeAnalysisErrorStatus(accessor));
                      return { generic, statuses, reads };
                    })()`, context);
                    if (result.reads !== 0) throw new Error(`error code accessor executed ${result.reads} times`);
                    for (const status of result.statuses) {
                      if (status !== result.generic) throw new Error(`unsafe status: ${String(status)}`);
                    }
                    """
                ).replace("__APP__", json.dumps(str(source)))
                result = subprocess.run(
                    ["node", "-e", script], cwd=ROOT, capture_output=True, encoding="utf-8",
                    text=True, check=False, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_both_surfaces_keep_pending_copy_and_reject_raw_backend_messages(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for frontend behavior tests")

        for name, source, harness in (
            ("popup", EXTENSION / "popup.js", self._popup_error_harness()),
            ("local-debug", LOCAL_DEBUG / "app.js", self._local_debug_error_harness()),
        ):
            with self.subTest(surface=name):
                script = (
                    harness.replace("__APP__", json.dumps(str(source)))
                    .replace("__LOADING__", json.dumps(LOADING_STATUS, ensure_ascii=False))
                )
                result = subprocess.run(
                    ["node", "-e", script], cwd=ROOT, capture_output=True, encoding="utf-8", text=True,
                    check=False, timeout=10,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    @staticmethod
    def _popup_error_harness() -> str:
        return textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__APP__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            function element(selector) {
              if (!elements.has(selector)) elements.set(selector, {
                textContent: "", value: "", disabled: false,
                addEventListener(type, callback) { listeners.set(`${selector}:${type}`, callback); },
              });
              return elements.get(selector);
            }
            let resolveResponse;
            let calls = 0;
            const context = {
              document: { querySelector: element },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: { tabs: {
                query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                sendMessage: async (_id, message) => message.type === "REVALIDATE_CURRENT_EMAIL"
                  ? { ok: true, message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa" }
                  : { ok: true, tab_id: 7, message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa", payload: {
                      subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                      body_text: "Synthetic body", attachments: [], thread_segments: [],
                      attachment_files: [], resource_limitations: [],
                    } },
              } },
              EmailAssistantApi: { analyzeCurrentEmail: async () => {
                calls += 1;
                return await new Promise((resolve) => { resolveResponse = resolve; });
              } },
              EmailAssistantRender: {
                clearAnalysis: () => {}, renderAttachments: () => {}, renderAnalysis: () => {},
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });
            (async () => {
              const analyze = listeners.get("#analyze-button:click");
              const first = analyze();
              for (let i = 0; i < 20 && calls === 0; i += 1) await Promise.resolve();
              if (elements.get("#status").textContent !== __LOADING__) {
                throw new Error(`pending status mismatch: ${elements.get("#status").textContent}`);
              }
              resolveResponse({ ok: false, error: {
                code: "LOCAL_ANALYSIS_TIMEOUT", message: "PRIVATE_POPUP_TIMEOUT_DETAIL",
              } });
              await first;
              const status = elements.get("#status").textContent;
              if (status !== "本地分析服务超时，请重试。" || status.includes("PRIVATE_POPUP")) {
                throw new Error(`unsafe timeout status: ${status}`);
              }

              const second = analyze();
              for (let i = 0; i < 20 && calls === 1; i += 1) await Promise.resolve();
              resolveResponse({ ok: false, error: {
                code: "UNRECOGNIZED_PRIVATE_CODE", message: "PRIVATE_POPUP_BACKEND_MESSAGE",
              } });
              await second;
              const unknown = elements.get("#status").textContent;
              if (unknown !== "分析未完成，请重试。" || unknown.includes("PRIVATE_POPUP")) {
                throw new Error(`unsafe generic status: ${unknown}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error); process.exitCode = 1;
            });
            """
        )

    @staticmethod
    def _local_debug_error_harness() -> str:
        return textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__APP__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            function element(selector) {
              if (!elements.has(selector)) elements.set(selector, {
                textContent: "", value: selector === "#body" ? "Synthetic body" : "",
                disabled: false, children: [],
                addEventListener(type, callback) { listeners.set(`${selector}:${type}`, callback); },
              });
              return elements.get(selector);
            }
            let resolvePayload;
            let calls = 0;
            const context = {
              AbortController, setTimeout, clearTimeout,
              document: { querySelector: element },
              navigator: { clipboard: { writeText: async () => {} } },
              fetch: async () => {
                calls += 1;
                const payload = await new Promise((resolve) => { resolvePayload = resolve; });
                return { json: async () => payload };
              },
              EmailAssistantRender: {
                clearAnalysis: () => {}, renderAttachments: () => {}, renderAnalysis: () => {},
              },
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "app.js" });
            (async () => {
              const analyze = listeners.get("#analyze-button:click");
              const first = analyze();
              for (let i = 0; i < 20 && calls === 0; i += 1) await Promise.resolve();
              const pendingStatus = elements.get("#status").textContent;
              resolvePayload({ ok: false, error: {
                code: "LOCAL_ANALYSIS_TIMEOUT", message: "PRIVATE_DEBUG_TIMEOUT_DETAIL",
              } });
              await first;
              if (pendingStatus !== __LOADING__) {
                throw new Error(`pending status mismatch: ${pendingStatus}`);
              }
              const status = elements.get("#status").textContent;
              if (status !== "本地分析服务超时，请重试。" || status.includes("PRIVATE_DEBUG")) {
                throw new Error(`unsafe timeout status: ${status}`);
              }

              const second = analyze();
              for (let i = 0; i < 20 && calls === 1; i += 1) await Promise.resolve();
              resolvePayload({ ok: false, error: {
                code: "UNRECOGNIZED_PRIVATE_CODE", message: "PRIVATE_DEBUG_BACKEND_MESSAGE",
              } });
              await second;
              const unknown = elements.get("#status").textContent;
              if (unknown !== "分析未完成，请重试。" || unknown.includes("PRIVATE_DEBUG")) {
                throw new Error(`unsafe generic status: ${unknown}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error); process.exitCode = 1;
            });
            """
        )


if __name__ == "__main__":
    unittest.main()
