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
            let backendCount = 0;
            const context = {
              document: { querySelector: (selector) => elements.get(selector) || null },
              navigator: { clipboard: { writeText: async () => {} } },
              chrome: {
                tabs: {
                  query: async () => [{ id: 7, url: "https://exmail.qq.com/cgi-bin/readmail" }],
                  sendMessage: async (_tabId, message) => {
                    extractionCount += 1;
                    if (message.type !== "EXTRACT_CURRENT_EMAIL") throw new Error("wrong extraction message");
                    return {
                      ok: true,
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


if __name__ == "__main__":
    unittest.main()
