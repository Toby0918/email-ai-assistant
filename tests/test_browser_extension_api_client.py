"""Focused browser API-client fail-closed tests."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
API_CLIENT = ROOT / "frontend" / "browser_extension" / "shared" / "api_client.js"


class BrowserExtensionApiClientTests(unittest.TestCase):
    def test_cc_is_forwarded_for_private_identity_context(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__API_CLIENT_PATH__, "utf8");
            let requestBody = null;
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
                subject: "Synthetic",
                from: "sender@example.test",
                to: ["buyer@example.test"],
                cc: ["reviewer@example.test"],
                body_text: "Please review the synthetic request.",
              });
              if (
                !requestBody ||
                requestBody.cc.length !== 1 ||
                requestBody.cc[0] !== "reviewer@example.test"
              ) {
                throw new Error(`cc identity context was lost: ${JSON.stringify(requestBody)}`);
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

    def test_empty_email_body_never_calls_fetch(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")

        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__API_CLIENT_PATH__, "utf8");
            let fetchCount = 0;
            const context = {
              AbortController,
              setTimeout,
              clearTimeout,
              fetch: async () => {
                fetchCount += 1;
                throw new Error("fetch must not run for an empty body");
              },
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "api_client.js" });

            (async () => {
              const result = await context.EmailAssistantApi.analyzeCurrentEmail({
                subject: "Synthetic",
                body_text: " \n\t ",
              });
              if (fetchCount !== 0) throw new Error(`unexpected fetch count: ${fetchCount}`);
              if (!result || result.ok !== false || result.error.code !== "CURRENT_EMAIL_BODY_EMPTY") {
                throw new Error(`unexpected empty-body result: ${JSON.stringify(result)}`);
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
