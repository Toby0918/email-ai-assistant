"""Behavior tests for persistent-panel stale result protection."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POPUP = ROOT / "frontend" / "browser_extension" / "popup.js"


class BrowserExtensionStaleStateTests(unittest.TestCase):
    def run_node_case(self, case_name: str) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for stale-state behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__POPUP__, "utf8");

            function deferred() {
              let resolve;
              let reject;
              const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
              return { promise, resolve, reject };
            }
            async function waitFor(predicate, label) {
              for (let index = 0; index < 50; index += 1) {
                if (predicate()) return;
                await new Promise((resolve) => setTimeout(resolve, 0));
              }
              throw new Error(`timed out waiting for ${label}`);
            }
            function success(marker, id) {
              return {
                ok: true,
                saved_id: id,
                analysis: {
                  marker,
                  reply_draft: { body: `Draft ${marker}` },
                },
              };
            }

            const listeners = new Map();
            const elements = new Map();
            for (const id of [
              "status", "priority", "summary", "category", "engine", "decision-brief",
              "conversation-timeline", "attachment-insights", "attachments", "risks", "actions",
              "draft", "analyze-button", "copy-draft-button",
            ]) {
              elements.set(`#${id}`, {
                textContent: "",
                value: "",
                disabled: false,
                addEventListener: (type, callback) => listeners.set(`${id}:${type}`, callback),
              });
            }

            let activeTab = { id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" };
            let fingerprint = "msg-v1-aaaaaaaaaaaaaaaa";
            let backendCalls = 0;
            let clipboardWrites = 0;
            let clearCount = 0;
            const messages = [];
            const renderMarkers = [];
            const backendQueue = [];
            const context = {
              setTimeout,
              clearTimeout,
              document: { querySelector: (selector) => elements.get(selector) || null },
              navigator: {
                clipboard: {
                  writeText: async () => { clipboardWrites += 1; },
                },
              },
              chrome: {
                tabs: {
                  query: async () => [activeTab],
                  sendMessage: async (tabId, message) => {
                    messages.push({ tabId, type: message.type });
                    if (message.type === "EXTRACT_CURRENT_EMAIL") {
                      return {
                        ok: true,
                        message_fingerprint: fingerprint,
                        payload: {
                          subject: "Synthetic", from: "sender@example.test", to: [], sent_at: "",
                          body_text: "Synthetic body", attachments: [], thread_segments: [],
                          attachment_files: [], resource_limitations: [],
                        },
                      };
                    }
                    if (message.type === "REVALIDATE_CURRENT_EMAIL") {
                      return { ok: true, message_fingerprint: fingerprint };
                    }
                    throw new Error(`unexpected message ${message.type}`);
                  },
                },
              },
              EmailAssistantApi: {
                analyzeCurrentEmail: async () => {
                  const queued = backendQueue[backendCalls++];
                  return queued ? queued.promise : success("immediate", 1);
                },
              },
              EmailAssistantRender: {
                clearAnalysis: () => {
                  clearCount += 1;
                  elements.get("#draft").value = "";
                },
                renderAttachments: () => {},
                renderAnalysis: (_fields, analysis) => {
                  renderMarkers.push(analysis.marker);
                  elements.get("#draft").value = analysis.reply_draft.body;
                },
              },
            };
            vm.runInNewContext(source, context, { filename: "popup.js" });
            const analyze = listeners.get("analyze-button:click");
            const copy = listeners.get("copy-draft-button:click");

            const cases = {
              delayed_response_after_tab_navigation_is_discarded: async () => {
                const first = deferred();
                backendQueue.push(first);
                const pending = analyze();
                await waitFor(() => backendCalls === 1, "first backend request");
                activeTab = { id: 8, url: "https://exmail.qq.com/cgi-bin/readmail" };
                first.resolve(success("stale", 11));
                await pending;
                if (renderMarkers.length !== 0) {
                  throw new Error(`stale navigation result rendered: ${JSON.stringify(renderMarkers)}`);
                }
                if (elements.get("#draft").value !== "") throw new Error("stale draft was retained");
                if (elements.get("#status").textContent !== "Email changed; analyze again") {
                  throw new Error(`stale state missing: ${elements.get("#status").textContent}`);
                }
              },

              out_of_order_older_response_cannot_overwrite_newer_result: async () => {
                const first = deferred();
                const second = deferred();
                backendQueue.push(first, second);
                const older = analyze();
                await waitFor(() => backendCalls === 1, "older backend request");
                const newer = analyze();
                await waitFor(() => backendCalls === 2, "newer backend request");
                second.resolve(success("newer", 22));
                await newer;
                first.resolve(success("older", 21));
                await older;
                if (JSON.stringify(renderMarkers) !== JSON.stringify(["newer"])) {
                  throw new Error(`out-of-order render: ${JSON.stringify(renderMarkers)}`);
                }
                if (elements.get("#draft").value !== "Draft newer") {
                  throw new Error(`older response replaced draft: ${elements.get("#draft").value}`);
                }
                if (elements.get("#status").textContent !== "Saved #22") {
                  throw new Error(`older response replaced status: ${elements.get("#status").textContent}`);
                }
              },

              copy_revalidates_fingerprint_before_clipboard_write: async () => {
                await analyze();
                if (renderMarkers.length !== 1) throw new Error("initial result did not render");
                fingerprint = "msg-v1-bbbbbbbbbbbbbbbb";
                await copy();
                if (clipboardWrites !== 0) throw new Error("stale draft reached clipboard");
                if (elements.get("#draft").value !== "") throw new Error("stale draft was not cleared");
                if (elements.get("#status").textContent !== "Email changed; analyze again") {
                  throw new Error(`copy stale state missing: ${elements.get("#status").textContent}`);
                }
                const revalidations = messages.filter((item) => item.type === "REVALIDATE_CURRENT_EMAIL");
                if (revalidations.length < 2) {
                  throw new Error(`copy/render revalidation missing: ${JSON.stringify(messages)}`);
                }
              },
            };

            (async () => {
              await cases[__CASE__]();
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        )
        script = script.replace("__POPUP__", json.dumps(str(POPUP)))
        script = script.replace("__CASE__", json.dumps(case_name))
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            encoding="utf-8",
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)

    def test_delayed_response_after_tab_navigation_is_discarded(self) -> None:
        self.run_node_case("delayed_response_after_tab_navigation_is_discarded")

    def test_out_of_order_older_response_cannot_overwrite_newer_result(self) -> None:
        self.run_node_case("out_of_order_older_response_cannot_overwrite_newer_result")

    def test_copy_revalidates_fingerprint_before_clipboard_write(self) -> None:
        self.run_node_case("copy_revalidates_fingerprint_before_clipboard_write")


if __name__ == "__main__":
    unittest.main()
