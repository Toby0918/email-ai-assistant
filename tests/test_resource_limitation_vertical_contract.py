"""Synthetic collector-to-renderer contract for resource limitations."""

from __future__ import annotations

import io
import json
import os
import base64
import shutil
import sqlite3
import subprocess
import textwrap
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from openpyxl import Workbook

from backend.email_agent.api import handle_analyze_current_email
from backend.email_agent.attachment_storage import StoredAttachment
from backend.email_agent.config import load_config
from backend.email_agent.database import initialize_schema, save_analysis


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COLLECTOR = os.path.join(
    ROOT, "frontend", "browser_extension", "content", "current_message_collector.js"
)
API_CLIENT = os.path.join(
    ROOT, "frontend", "browser_extension", "shared", "api_client.js"
)
RENDERER = os.path.join(
    ROOT, "frontend", "browser_extension", "shared", "render_analysis.js"
)


class ResourceLimitationVerticalContractTests(unittest.TestCase):
    def test_maximum_cardinality_limitations_reach_analyzer_sqlite_and_renderer(self) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for the vertical browser contract")

        request_payload = self._collector_to_api_payload(self._synthetic_xlsx())
        self.assertEqual(len(request_payload["attachment_files"]), 5)
        self.assertEqual(len(request_payload["resource_limitations"]), 8)
        self.assertEqual(
            [item.get("code") for item in request_payload["resource_limitations"]],
            [
                "unsupported_type",
                "frontend_limit",
                "resource_unavailable",
                "frontend_limit",
                "frontend_limit",
                "unsupported_type",
                "unsupported_type",
                "candidate_omission",
            ],
        )
        for item in request_payload["resource_limitations"]:
            self.assertEqual(
                set(item),
                {"code", "filename", "type", "size", "limitation"},
            )

        with TemporaryDirectory() as directory:
            config = replace(load_config(dotenv_path=None), attachment_temp_dir=directory)
            content = self._synthetic_xlsx()
            stored_attachments = []
            for index in range(5):
                path = Path(directory) / f"quote-{index}.xlsx"
                path.write_bytes(content)
                stored_attachments.append(StoredAttachment(
                    safe_filename=path.name,
                    type="xlsx",
                    path=path,
                    byte_size=len(content),
                    expires_at=datetime.now(UTC) + timedelta(hours=1),
                ))
            operational = {
                "code": "operational_failure",
                "filename": "resource",
                "type": "unsupported",
                "size": 0,
                "limitation": "Attachment resources are temporarily unavailable; body analysis continued.",
            }
            with patch(
                "backend.email_agent.api._store_attachments_or_degrade",
                return_value=(stored_attachments, [operational]),
            ):
                with patch.dict(os.environ, {"EMAIL_AGENT_LLM_PROVIDER": "disabled"}):
                    response = handle_analyze_current_email(request_payload, config=config)

        self.assertTrue(response["ok"])
        analysis = response["analysis"]
        insights = analysis["attachment_insights"]
        self.assertEqual(
            len(insights),
            14,
            repr([(item["filename"], item["status"]) for item in insights]),
        )
        self.assertEqual(
            [(item["filename"], item["status"]) for item in insights],
            [
                *[(f"quote-{index}.xlsx", "parsed") for index in range(5)],
                ("unsupported-0.txt", "unavailable"),
                ("large.pdf", "unavailable"),
                ("unavailable.docx", "unavailable"),
                ("count-limited-0.pdf", "unavailable"),
                ("count-limited-1.pdf", "unavailable"),
                ("unsupported-1.txt", "unavailable"),
                ("unsupported-2.txt", "unavailable"),
                ("additional-resources", "unavailable"),
                ("resource", "failed"),
            ],
        )
        for insight in insights[5:]:
            self.assertEqual(insight["key_facts"], [])

        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)
        save_analysis(
            connection,
            subject=request_payload["subject"],
            sender=request_payload["from"],
            analysis=analysis,
        )
        stored_json = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        stored = json.loads(stored_json)
        self.assertEqual(len(stored["attachment_insights"]), 14)
        for forbidden in (
            "content_base64",
            "data-resource-url",
            "PRIVATE_TOKEN",
            "https://exmail.qq.com/cgi-bin",
            "C:/private",
        ):
            self.assertNotIn(forbidden, stored_json)

        rendered = self._render_insights(stored["attachment_insights"])
        self.assertEqual(rendered["count"], 14)
        for expected in (
            "quote-0.xlsx",
            "quote-4.xlsx",
            "unsupported-0.txt",
            "large.pdf",
            "unavailable.docx",
            "count-limited-0.pdf",
            "count-limited-1.pdf",
            "unsupported-2.txt",
            "additional-resources",
            "resource",
            "已解析",
            "不可用",
            "解析失败",
        ):
            self.assertIn(expected, rendered["text"])
        self.assertEqual(rendered["anchor_count"], 0)

    def _collector_to_api_payload(self, xlsx_bytes: bytes) -> dict[str, object]:
        max_file_bytes = len(xlsx_bytes) + 256
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const collectorSource = fs.readFileSync(__COLLECTOR__, "utf8");
            const apiSource = fs.readFileSync(__API_CLIENT__, "utf8");
            const xlsxBytes = Uint8Array.from(Buffer.from(__XLSX_BASE64__, "base64"));

            class Element {
              constructor(attrs = {}, children = [], text = "", tag = "div") {
                this.tagName = tag.toUpperCase();
                this.attrs = { ...attrs };
                this.children = children;
                this.innerText = text;
                this.textContent = text;
                this.style = {};
                this.hidden = false;
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
              querySelectorAll() { return []; }
            }

            function resource(filename, type, url, size = 0) {
              return new Element({
                "data-filename": filename,
                "data-type": type,
                href: url,
                download: filename,
                "data-size": String(size),
              }, [], filename, "a");
            }
            function streamResponse(bytes) {
              let delivered = false;
              const reader = {
                read: async () => {
                  if (delivered) return { done: true, value: undefined };
                  delivered = true;
                  return { done: false, value: bytes };
                },
                cancel: async () => {},
                releaseLock: () => {},
              };
              return {
                ok: true,
                redirected: false,
                headers: { get: (name) => name.toLowerCase() === "content-length" ? String(bytes.length) : null },
                body: { getReader: () => reader },
              };
            }

            const parsed = Array.from({ length: 5 }, (_value, index) =>
              resource(`quote-${index}.xlsx`, "xlsx", `/cgi-bin/download?file=quote-${index}`),
            );
            const unsupported = Array.from({ length: 12 }, (_value, index) =>
              resource(
                `unsupported-${index}.txt`,
                "text/plain",
                `/cgi-bin/download?file=unsupported-${index}`,
              ),
            );
            const candidates = [
              ...parsed,
              unsupported[0],
              resource("large.pdf", "pdf", "/cgi-bin/download?file=large", __OVERSIZED__),
              resource("unavailable.docx", "docx", "/cgi-bin/readmail?file=unavailable"),
              resource("count-limited-0.pdf", "pdf", "/cgi-bin/download?file=count-limited-0"),
              resource("count-limited-1.pdf", "pdf", "/cgi-bin/download?file=count-limited-1"),
              ...unsupported.slice(1),
            ];
            const currentRoot = new Element({ class: "mail-content" }, [], "Synthetic body");
            const controls = new Element({ class: "resource-region" }, candidates);
            const container = new Element({ class: "read-envelope" }, [currentRoot, controls]);
            const body = new Element({}, [container]);
            const doc = {
              body,
              baseURI: "https://exmail.qq.com/cgi-bin/readmail",
              defaultView: { getComputedStyle: () => ({ display: "block", visibility: "visible" }) },
            };
            const context = {
              URL,
              Uint8Array,
              ArrayBuffer,
              AbortController,
              setTimeout,
              clearTimeout,
              btoa: (binary) => Buffer.from(binary, "binary").toString("base64"),
            };
            context.window = context;
            vm.runInNewContext(collectorSource, context, { filename: "current_message_collector.js" });

            (async () => {
              const resources = await context.EmailAssistantCurrentMessageCollector.collectVisibleResources(doc, {
                currentMessageRoot: currentRoot,
                currentMessageContainer: container,
                verifiedResourceCandidates: candidates,
                resourceControlsVerified: true,
                limits: {
                  maxFiles: 5,
                  maxFileBytes: __MAX_FILE_BYTES__,
                  maxTotalBytes: __MAX_TOTAL_BYTES__,
                  perResourceTimeoutMs: 20,
                  overallTimeoutMs: 500,
                },
                fetchImpl: async (url) => {
                  if (url.includes("file=quote-")) return streamResponse(xlsxBytes);
                  throw new Error(`unexpected fetch ${url}`);
                },
              });

              let requestBody;
              context.fetch = async (_url, options) => {
                requestBody = JSON.parse(options.body);
                return { ok: true, status: 200, json: async () => ({ ok: true }) };
              };
              vm.runInNewContext(apiSource, context, { filename: "api_client.js" });
              await context.EmailAssistantApi.analyzeCurrentEmail({
                subject: "Synthetic RFQ 42",
                from: "customer@example.test",
                to: ["sales@cndlf.com"],
                sent_at: "2026-07-11 10:00 UTC",
                body_text: "Please review RFQ 42 and prepare a response.",
                attachments: [],
                thread_segments: [],
                attachment_files: resources.attachment_files,
                resource_limitations: resources.resource_limitations,
              });
              process.stdout.write(JSON.stringify(requestBody));
            })().catch((error) => {
              console.error(error && error.stack ? error.stack : error);
              process.exitCode = 1;
            });
            """
        )
        script = script.replace("__COLLECTOR__", json.dumps(COLLECTOR))
        script = script.replace("__API_CLIENT__", json.dumps(API_CLIENT))
        script = script.replace(
            "__XLSX_BASE64__",
            json.dumps(base64.b64encode(xlsx_bytes).decode("ascii")),
        )
        script = script.replace("__MAX_FILE_BYTES__", str(max_file_bytes))
        script = script.replace("__MAX_TOTAL_BYTES__", str(max_file_bytes * 6))
        script = script.replace("__OVERSIZED__", str(max_file_bytes + 1))
        result = subprocess.run(
            ["node", "-"],
            cwd=ROOT,
            input=script,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=20,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return json.loads(result.stdout)

    def _render_insights(self, insights: list[dict[str, object]]) -> dict[str, object]:
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__RENDERER__, "utf8");
            class FakeElement {
              constructor(tagName = "div") {
                this.tagName = tagName.toUpperCase();
                this.children = [];
                this.className = "";
                this.textContent = "";
                this.ownerDocument = fakeDocument;
              }
              set innerHTML(value) { throw new Error(`innerHTML used: ${value}`); }
              appendChild(child) {
                this.children.push(child);
                this.textContent = this.children.map((item) => item.textContent || "").join("");
                return child;
              }
              replaceChildren(...children) {
                this.children = children;
                this.textContent = children.map((item) => item.textContent || "").join("\n");
              }
              querySelectorAll(tagName) {
                const expected = tagName.toUpperCase();
                const matches = [];
                const walk = (node) => {
                  if (node.tagName === expected) matches.push(node);
                  for (const child of node.children || []) walk(child);
                };
                walk(this);
                return matches;
              }
            }
            const fakeDocument = {
              createElement: (tagName) => new FakeElement(tagName),
              createTextNode: (text) => ({ tagName: "#TEXT", textContent: String(text), children: [] }),
            };
            const context = { window: {}, document: fakeDocument };
            vm.runInNewContext(source, context, { filename: "render_analysis.js" });
            const field = new FakeElement();
            context.window.EmailAssistantRender.renderAttachmentInsights(field, __INSIGHTS__);
            process.stdout.write(JSON.stringify({
              count: field.children.length,
              text: field.textContent,
              anchor_count: field.querySelectorAll("a").length,
            }));
            """
        )
        script = script.replace("__RENDERER__", json.dumps(RENDERER))
        script = script.replace("__INSIGHTS__", json.dumps(insights, ensure_ascii=False))
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=10,
        )
        if result.returncode != 0:
            self.fail(result.stderr or result.stdout)
        return json.loads(result.stdout)

    @staticmethod
    def _synthetic_xlsx() -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Reference", "Quantity"])
        sheet.append(["RFQ 42", "200 pcs"])
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()


if __name__ == "__main__":
    unittest.main()
