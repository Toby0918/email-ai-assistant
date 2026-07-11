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


class BrowserExtensionTask6ContractTests(unittest.TestCase):
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

        api_client = EXTENSION / "shared" / "api_client.js"
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__API_CLIENT_PATH__, "utf8");
            let requestBody;
            const context = {
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
                token: "PRIVATE_TOKEN",
                arbitrary_extra: "PRIVATE_EXTRA",
              });

              const expectedTopLevel = [
                "attachment_files", "attachments", "body_text", "from", "sent_at", "subject",
                "thread_segments", "to", "user_confirmed",
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
              const serialized = JSON.stringify(requestBody);
              for (const marker of [
                "PRIVATE_COOKIE", "PRIVATE_HIDDEN_ID", "PRIVATE_AUTHORIZATION",
                "PRIVATE_DOWNLOAD_URL", "PRIVATE_TOKEN", "PRIVATE_EXTRA",
              ]) {
                if (serialized.includes(marker)) throw new Error(`private marker leaked: ${marker}`);
              }
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        ).replace("__API_CLIENT_PATH__", json.dumps(str(api_client)))

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
