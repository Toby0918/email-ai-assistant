"""Focused explicit-click behavior test for the Task 6 popup path."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POPUP = ROOT / "frontend" / "browser_extension" / "popup.js"


class BrowserExtensionTask6PopupTests(unittest.TestCase):
    def test_manual_files_are_idle_until_analyze_then_read_once_and_cleared(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__POPUP_PATH__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            for (const id of [
              "status", "priority", "summary", "category", "engine", "decision-brief",
              "conversation-timeline", "attachment-insights", "attachments", "risks", "actions",
              "draft", "analyze-button", "copy-draft-button", "manual-attachment-files",
            ]) {
              elements.set(`#${id}`, {
                textContent: "", value: "", disabled: false, files: [],
                addEventListener: (type, callback) => listeners.set(`${id}:${type}`, callback),
              });
            }
            const manualInput = elements.get("#manual-attachment-files");
            manualInput.files = [{ name: "selected.pdf" }];
            manualInput.value = "C:\\fakepath\\selected.pdf";
            let extractionCount = 0;
            let revalidationCount = 0;
            let readCount = 0;
            let backendCount = 0;
            let backendPayload;
            let renderedAttachments;
            const automatic = {
              filename: "automatic.pdf", type: "pdf", size: 1, content_base64: "QQ==",
            };
            const manual = {
              filename: "selected.pdf", type: "pdf", size: 1, content_base64: "Qg==",
            };
            const context = {
              document: { querySelector: (selector) => elements.get(selector) || null },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: { tabs: {
                query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                sendMessage: async (_tabId, message) => {
                  if (message.type === "REVALIDATE_CURRENT_EMAIL") {
                    revalidationCount += 1;
                    return { ok: true, message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa" };
                  }
                  extractionCount += 1;
                  return {
                    ok: true, tab_id: 7, message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa",
                    payload: {
                      subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                      body_text: "Synthetic body", attachments: [], thread_segments: [],
                      attachment_files: [automatic], resource_limitations: [],
                    },
                  };
                },
              } },
              EmailAssistantManualAttachmentFiles: {
                readSelectedFiles: async (files) => {
                  readCount += 1;
                  if (extractionCount !== 1) throw new Error("manual file read preceded extraction");
                  if (files !== manualInput.files) throw new Error("wrong FileList read");
                  if (manualInput.disabled !== true) throw new Error("picker remained enabled while reading");
                  return { attachment_files: [manual], resource_limitations: [] };
                },
                mergeAttachmentFiles: (manualFiles, automaticFiles, limitations) => ({
                  attachment_files: [...manualFiles, ...automaticFiles],
                  resource_limitations: limitations,
                }),
              },
              EmailAssistantApi: { analyzeCurrentEmail: async (payload) => {
                backendCount += 1;
                backendPayload = JSON.parse(JSON.stringify(payload));
                return { ok: true, analysis: {} };
              } },
              EmailAssistantRender: {
                clearAnalysis: () => {},
                renderAttachments: (_field, value) => {
                  renderedAttachments = JSON.parse(JSON.stringify(value));
                },
                renderAnalysis: () => {},
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });

            (async () => {
              if (readCount !== 0 || extractionCount !== 0 || backendCount !== 0) {
                throw new Error("popup load read a file or crossed a boundary");
              }
              const change = listeners.get("manual-attachment-files:change");
              if (change) await change();
              if (readCount !== 0) throw new Error("file input change read selected bytes");
              await listeners.get("analyze-button:click")();
              if (readCount !== 1 || extractionCount !== 1 || backendCount !== 1) {
                throw new Error(`unexpected counts: ${readCount}/${extractionCount}/${backendCount}`);
              }
              if (revalidationCount !== 2) {
                throw new Error(`expected pre/post API revalidation, got ${revalidationCount}`);
              }
              if (backendPayload.attachment_files[0].filename !== "selected.pdf" ||
                  backendPayload.attachment_files[1].filename !== "automatic.pdf") {
                throw new Error(`manual-first payload missing: ${JSON.stringify(backendPayload)}`);
              }
              const rendered = JSON.stringify(renderedAttachments);
              if (!rendered.includes("selected.pdf") || !rendered.includes("automatic.pdf") ||
                  rendered.includes("content_base64") || rendered.includes("Qg==") || rendered.includes("QQ==")) {
                throw new Error(`renderer received bytes instead of metadata: ${rendered}`);
              }
              if (manualInput.value !== "" || manualInput.disabled !== false ||
                  elements.get("#analyze-button").disabled !== false) {
                throw new Error("manual attachment controls were not cleared and re-enabled");
              }
            })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
            """
        ).replace("__POPUP_PATH__", json.dumps(str(POPUP)))
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_manual_read_stale_context_makes_zero_backend_calls_and_clears_input(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__POPUP_PATH__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            function element(selector) {
              if (!elements.has(selector)) elements.set(selector, {
                textContent: "", value: "", disabled: false, files: [],
                addEventListener(type, callback) { listeners.set(`${selector}:${type}`, callback); },
              });
              return elements.get(selector);
            }
            const manualInput = element("#manual-attachment-files");
            manualInput.files = [{ name: "selected.pdf" }];
            manualInput.value = "selected.pdf";
            let reads = 0;
            let backendCalls = 0;
            const context = {
              document: { querySelector: element },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: { tabs: {
                query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                sendMessage: async (_id, message) => message.type === "REVALIDATE_CURRENT_EMAIL"
                  ? { ok: true, message_fingerprint: "msg-v1-bbbbbbbbbbbbbbbb" }
                  : { ok: true, tab_id: 7, message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa", payload: {
                      subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                      body_text: "Synthetic body", attachments: [], thread_segments: [],
                      attachment_files: [], resource_limitations: [],
                    } },
              } },
              EmailAssistantManualAttachmentFiles: {
                readSelectedFiles: async () => {
                  reads += 1;
                  return { attachment_files: [{
                    filename: "selected.pdf", type: "pdf", size: 1, content_base64: "QQ==",
                  }], resource_limitations: [] };
                },
                mergeAttachmentFiles: (manual, automatic, limitations) => ({
                  attachment_files: [...manual, ...automatic], resource_limitations: limitations,
                }),
              },
              EmailAssistantApi: { analyzeCurrentEmail: async () => {
                backendCalls += 1;
                return { ok: true, analysis: {} };
              } },
              EmailAssistantRender: {
                clearAnalysis: () => {}, renderAttachments: () => {}, renderAnalysis: () => {},
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });
            (async () => {
              await listeners.get("#analyze-button:click")();
              if (reads !== 1 || backendCalls !== 0) {
                throw new Error(`stale manual read crossed backend: ${reads}/${backendCalls}`);
              }
              if (element("#status").textContent !== "Email changed; analyze again") {
                throw new Error(`missing stale status: ${element("#status").textContent}`);
              }
              if (manualInput.value !== "" || manualInput.disabled || element("#analyze-button").disabled) {
                throw new Error("stale exit did not clear and re-enable controls");
              }
            })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
            """
        ).replace("__POPUP_PATH__", json.dumps(str(POPUP)))
        result = subprocess.run(
            ["node", "-e", script], cwd=ROOT, capture_output=True, text=True,
            check=False, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_popup_rejects_empty_extracted_body_without_backend_call(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__POPUP_PATH__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            for (const id of [
              "status", "priority", "summary", "category", "engine", "decision-brief",
              "conversation-timeline", "attachment-insights", "attachments", "risks", "actions",
              "draft", "analyze-button", "copy-draft-button", "manual-attachment-files",
            ]) {
              elements.set(`#${id}`, {
                textContent: "", value: "", disabled: false, files: [],
                addEventListener: (type, callback) => listeners.set(`${id}:${type}`, callback),
              });
            }
            let backendCalls = 0;
            let manualReads = 0;
            let extractionCalls = 0;
            elements.get("#manual-attachment-files").files = [{ name: "selected.pdf" }];
            elements.get("#manual-attachment-files").value = "selected.pdf";
            const context = {
              document: { querySelector: (selector) => elements.get(selector) || null },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: {
                tabs: {
                  query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                  sendMessage: async () => {
                    extractionCalls += 1;
                    return {
                      ok: true,
                      message_fingerprint: extractionCalls === 1
                        ? "msg-v1-aaaaaaaaaaaaaaaa"
                        : "invalid-private-fingerprint",
                      payload: {
                        subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                        body_text: extractionCalls === 1 ? "   " : "Synthetic body",
                        attachments: [], thread_segments: [], attachment_files: [], resource_limitations: [],
                      },
                    };
                  },
                },
              },
              EmailAssistantApi: {
                analyzeCurrentEmail: async () => {
                  backendCalls += 1;
                  return { ok: true, analysis: {} };
                },
              },
              EmailAssistantManualAttachmentFiles: {
                readSelectedFiles: async () => {
                  manualReads += 1;
                  return { attachment_files: [], resource_limitations: [] };
                },
                mergeAttachmentFiles: () => ({ attachment_files: [], resource_limitations: [] }),
              },
              EmailAssistantRender: {
                clearAnalysis: () => {}, renderAttachments: () => {}, renderAnalysis: () => {},
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });

            (async () => {
              const analyze = listeners.get("analyze-button:click");
              await analyze();
              if (backendCalls !== 0) throw new Error("empty body reached backend");
              if (manualReads !== 0) throw new Error("empty body caused a selected-file read");
              if (elements.get("#manual-attachment-files").value !== "") {
                throw new Error("empty-body exit did not clear the selected file");
              }
              elements.get("#manual-attachment-files").files = [{ name: "selected.pdf" }];
              elements.get("#manual-attachment-files").value = "selected.pdf";
              await analyze();
              if (manualReads !== 0 || backendCalls !== 0) {
                throw new Error("invalid fingerprint caused a selected-file read or backend call");
              }
              if (elements.get("#manual-attachment-files").value !== "") {
                throw new Error("invalid-fingerprint exit did not clear the selected file");
              }
              if (elements.get("#analyze-button").disabled !== false) {
                throw new Error("Analyze remained disabled after empty-body rejection");
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__POPUP_PATH__", json.dumps(str(POPUP)))
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

    def test_popup_load_is_idle_and_one_click_requests_each_boundary_once(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__POPUP_PATH__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            const ids = [
              "status", "priority", "summary", "category", "engine", "decision-brief",
              "attachments", "risks", "actions", "draft", "analyze-button", "copy-draft-button",
            ];
            for (const id of ids) {
              elements.set(`#${id}`, {
                textContent: "",
                value: "",
                disabled: false,
                addEventListener: (type, callback) => listeners.set(`${id}:${type}`, callback),
              });
            }

            let extractionCount = 0;
            let revalidationCount = 0;
            let backendCount = 0;
            const context = {
              document: { querySelector: (selector) => elements.get(selector) || null },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: {
                tabs: {
                  query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                  sendMessage: async (_tabId, message) => {
                    if (message.type === "REVALIDATE_CURRENT_EMAIL") {
                      revalidationCount += 1;
                      return { ok: true, message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa" };
                    }
                    extractionCount += 1;
                    if (message.type !== "EXTRACT_CURRENT_EMAIL") throw new Error("wrong extraction message");
                    return {
                      ok: true,
                      message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa",
                      payload: {
                        subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                        body_text: "Synthetic body", attachments: [], thread_segments: [],
                        attachment_files: [], resource_limitations: [],
                      },
                    };
                  },
                },
              },
              EmailAssistantApi: {
                analyzeCurrentEmail: async () => {
                  backendCount += 1;
                  return { ok: true, saved_id: 1, analysis: {} };
                },
              },
              EmailAssistantRender: {
                clearAnalysis: () => {},
                formatAttachments: () => "",
                renderAttachments: () => {},
                renderAnalysis: () => {},
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });

            (async () => {
              if (extractionCount !== 0 || backendCount !== 0) {
                throw new Error("popup load performed extraction or analysis");
              }
              const analyze = listeners.get("analyze-button:click");
              if (typeof analyze !== "function") throw new Error("Analyze click handler missing");
              await analyze();
              if (extractionCount !== 1) throw new Error(`expected one extraction, got ${extractionCount}`);
              if (revalidationCount !== 2) throw new Error(`expected two revalidations, got ${revalidationCount}`);
              if (backendCount !== 1) throw new Error(`expected one backend request, got ${backendCount}`);
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__POPUP_PATH__", json.dumps(str(POPUP)))
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

    def test_popup_always_reenables_analyze_after_pre_request_failure(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__POPUP_PATH__, "utf8");
            const listeners = new Map();
            const elements = new Map();
            for (const id of [
              "status", "priority", "summary", "category", "engine", "decision-brief",
              "conversation-timeline", "attachment-insights", "attachments", "risks", "actions",
              "draft", "analyze-button", "copy-draft-button", "manual-attachment-files",
            ]) {
              elements.set(`#${id}`, {
                textContent: "", value: "", disabled: false,
                addEventListener: (type, callback) => listeners.set(`${id}:${type}`, callback),
              });
            }
            let backendCalls = 0;
            elements.get("#manual-attachment-files").files = [{ name: "synthetic.pdf" }];
            elements.get("#manual-attachment-files").value = "synthetic.pdf";
            const context = {
              document: { querySelector: (selector) => elements.get(selector) || null },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: {
                tabs: {
                  query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                  sendMessage: async () => ({
                    ok: true,
                    message_fingerprint: "msg-v1-aaaaaaaaaaaaaaaa",
                    payload: {
                      subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                      body_text: "Synthetic body", attachments: [], thread_segments: [],
                      attachment_files: [], resource_limitations: [],
                    },
                  }),
                },
              },
              EmailAssistantApi: {
                analyzeCurrentEmail: async () => {
                  backendCalls += 1;
                  return { ok: false, error: { message: "try again", retryable: true } };
                },
              },
              EmailAssistantManualAttachmentFiles: {
                readSelectedFiles: async () => { throw new Error("synthetic pre-request read failure"); },
                mergeAttachmentFiles: () => { throw new Error("merge must not run"); },
              },
              EmailAssistantRender: {
                clearAnalysis: () => {}, renderAttachments: () => {}, renderAnalysis: () => {},
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });

            (async () => {
              const analyze = listeners.get("analyze-button:click");
              try { await analyze(); } catch (_error) {}
              if (elements.get("#analyze-button").disabled !== false) {
                throw new Error("Analyze remained disabled after failure");
              }
              if (elements.get("#manual-attachment-files").disabled !== false ||
                  elements.get("#manual-attachment-files").value !== "") {
                throw new Error("manual input was not cleared and re-enabled after failure");
              }
              if (backendCalls !== 0) throw new Error("backend ran after pre-request failure");
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__POPUP_PATH__", json.dumps(str(POPUP)))
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
