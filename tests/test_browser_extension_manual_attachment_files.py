"""Behavior contracts for explicit, click-bound manual attachment files."""

from __future__ import annotations

import json
import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "frontend" / "browser_extension" / "shared" / "manual_attachment_files.js"


class BrowserExtensionManualAttachmentFilesTests(unittest.TestCase):
    def _run_node(self, body: str, *, timeout: int = 20) -> None:
        if shutil.which("node") is None:
            self.skipTest("Node.js is required for browser extension behavior tests")
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync(__MODULE__, "utf8");
            const context = {
              ArrayBuffer,
              Uint8Array,
              btoa: (binary) => Buffer.from(binary, "binary").toString("base64"),
            };
            context.window = context;
            vm.runInNewContext(source, context, { filename: "manual_attachment_files.js" });
            const api = context.EmailAssistantManualAttachmentFiles;
            if (!api || !Object.isFrozen(api)) throw new Error("manual module is not frozen");
            __BODY__
            """
        ).replace("__MODULE__", json.dumps(str(MODULE))).replace("__BODY__", body)
        result = subprocess.run(
            ["node", "-e", script],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
            timeout=timeout,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_supported_files_use_safe_basename_and_existing_payload_shape(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                function selected(name, type, values) {
                  const buffer = Uint8Array.from(values).buffer;
                  return {
                    name, type, size: values.length, webkitRelativePath: "PRIVATE_RELATIVE_PATH",
                    lastModified: 999999, token: "PRIVATE_TOKEN", buffer,
                    arrayBuffer: async () => buffer,
                  };
                }
                const files = [
                  selected("C:\\private\\pho\u0085to\u202e\u200b\ufeff.png", "image/png", [1, 2, 3]),
                  selected("/private/spec.pdf", "application/pdf", [4]),
                  selected("sheet.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", [5]),
                  selected("letter.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", [6]),
                ];
                (async () => {
                  const result = await api.readSelectedFiles(files);
                  const expected = [
                    ["photo.png", "image", 3, "AQID"],
                    ["spec.pdf", "pdf", 1, "BA=="],
                    ["sheet.xlsx", "xlsx", 1, "BQ=="],
                    ["letter.docx", "docx", 1, "Bg=="],
                  ];
                  const actual = result.attachment_files.map((item) => [
                    item.filename, item.type, item.size, item.content_base64,
                  ]);
                  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
                    throw new Error(`supported projection mismatch: ${JSON.stringify(result)}`);
                  }
                  for (const item of result.attachment_files) {
                    const keys = Object.keys(item).sort();
                    if (JSON.stringify(keys) !== JSON.stringify([
                      "content_base64", "filename", "size", "type",
                    ])) throw new Error(`private fields leaked: ${JSON.stringify(keys)}`);
                  }
                  for (const file of files) {
                    if (Array.from(new Uint8Array(file.buffer)).some((value) => value !== 0)) {
                      throw new Error("mutable selected-file buffer was not cleared");
                    }
                  }
                  const serialized = JSON.stringify(result);
                  for (const marker of ["private", "PRIVATE_RELATIVE_PATH", "PRIVATE_TOKEN", "lastModified"]) {
                    if (serialized.includes(marker)) throw new Error(`private marker leaked: ${marker}`);
                  }
                })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
                """
            )
        )

    def test_invalid_raw_sizes_are_rejected_before_array_buffer_read(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                let reads = 0;
                const read = async () => { reads += 1; return Uint8Array.from([1]).buffer; };
                const files = [
                  { name: "missing.pdf", type: "application/pdf", arrayBuffer: read },
                  { name: "nan.pdf", type: "application/pdf", size: NaN, arrayBuffer: read },
                  { name: "negative.pdf", type: "application/pdf", size: -1, arrayBuffer: read },
                  { name: "fraction.pdf", type: "application/pdf", size: 1.5, arrayBuffer: read },
                  { name: "unsafe.pdf", type: "application/pdf", size: Number.MAX_SAFE_INTEGER + 1, arrayBuffer: read },
                ];
                (async () => {
                  const result = await api.readSelectedFiles(files);
                  if (reads !== 0 || result.attachment_files.length !== 0) {
                    throw new Error(`invalid size reached bytes: ${reads}/${JSON.stringify(result)}`);
                  }
                  if (result.resource_limitations.length !== files.length ||
                      result.resource_limitations.some((item) => item.code !== "resource_read_failed")) {
                    throw new Error(`invalid sizes were not fixed failures: ${JSON.stringify(result)}`);
                  }
                })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
                """
            )
        )

    def test_merge_requires_canonical_base64_and_exact_decoded_size(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                const item = (filename, size, content) => ({
                  filename, type: "pdf", size, content_base64: content,
                });
                const valid = [
                  item("one.pdf", 1, "AQ=="),
                  item("two.pdf", 2, "AQI="),
                  item("three.pdf", 3, "AQID"),
                ];
                const validResult = api.mergeAttachmentFiles(valid, [], []);
                if (validResult.attachment_files.length !== 3) {
                  throw new Error(`canonical base64 rejected: ${JSON.stringify(validResult)}`);
                }
                const invalid = [
                  item("bad-padding.pdf", 1, "AQ="),
                  item("bad-alphabet.pdf", 1, "A*=="),
                  item("interior-padding.pdf", 2, "AQ=A"),
                  item("noncanonical-bits.pdf", 1, "AR=="),
                  item("wrong-short.pdf", 2, "AQID"),
                  item("wrong-long.pdf", 3, "AQI="),
                ];
                for (const candidate of invalid) {
                  const result = api.mergeAttachmentFiles([candidate], [], []);
                  if (result.attachment_files.length !== 0) {
                    throw new Error(`invalid base64 accepted: ${JSON.stringify(candidate)}`);
                  }
                }
                """
            )
        )

    def test_file_list_is_read_by_bounded_index_without_iterator_or_seventh_access(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                let iteratorCalls = 0;
                let seventhReads = 0;
                let byteReads = 0;
                const fileList = {
                  length: 100,
                  [Symbol.iterator]() { iteratorCalls += 1; throw new Error("PRIVATE_ITERATOR"); },
                };
                for (let index = 0; index < 6; index += 1) {
                  fileList[index] = {
                    name: `bounded-${index}.pdf`, type: "application/pdf", size: 1,
                    arrayBuffer: async () => { byteReads += 1; return Uint8Array.from([index]).buffer; },
                  };
                }
                Object.defineProperty(fileList, 6, {
                  get() { seventhReads += 1; throw new Error("PRIVATE_SEVENTH_ACCESS"); },
                });
                (async () => {
                  const result = await api.readSelectedFiles(fileList);
                  if (iteratorCalls !== 0 || seventhReads !== 0) {
                    throw new Error(`unbounded FileList access: ${iteratorCalls}/${seventhReads}`);
                  }
                  if (byteReads !== 5 || result.attachment_files.length !== 5 ||
                      !result.resource_limitations.some((item) => item.code === "frontend_limit")) {
                    throw new Error(`bounded indexed read mismatch: ${JSON.stringify(result)}`);
                  }

                  let partialReads = 0;
                  const throwingList = { length: 2, 0: fileList[0] };
                  Object.defineProperty(throwingList, 1, {
                    get() { throw new Error("PRIVATE_INDEX_ACCESS"); },
                  });
                  throwingList[0] = {
                    ...throwingList[0],
                    arrayBuffer: async () => { partialReads += 1; return Uint8Array.from([1]).buffer; },
                  };
                  const failed = await api.readSelectedFiles(throwingList);
                  if (partialReads !== 0 || failed.attachment_files.length !== 0) {
                    throw new Error("index access failure allowed a partial byte read");
                  }
                })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
                """
            )
        )

    def test_unsupported_conflicting_and_failed_reads_return_only_fixed_limitations(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                let forbiddenReads = 0;
                const files = [{
                  name: "C:\\private\\program.exe", type: "application/octet-stream", size: 1,
                  arrayBuffer: async () => { forbiddenReads += 1; return new ArrayBuffer(1); },
                }, {
                  name: "private.pdf", type: "text/plain", size: 1,
                  arrayBuffer: async () => { forbiddenReads += 1; return new ArrayBuffer(1); },
                }, {
                  name: "broken.pdf", type: "application/pdf", size: 1,
                  arrayBuffer: async () => { throw new Error("PRIVATE_READ_FAILURE"); },
                }, {
                  name: "short.pdf", type: "application/pdf", size: 2,
                  arrayBuffer: async () => new ArrayBuffer(1),
                }];
                (async () => {
                  const result = await api.readSelectedFiles(files);
                  if (forbiddenReads !== 0) throw new Error("unsupported files were read");
                  if (result.attachment_files.length !== 0) throw new Error(JSON.stringify(result));
                  const codes = result.resource_limitations.map((item) => item.code);
                  if (JSON.stringify(codes) !== JSON.stringify([
                    "unsupported_type", "unsupported_type", "resource_read_failed", "resource_read_failed",
                  ])) throw new Error(`unexpected limitations: ${JSON.stringify(result)}`);
                  for (const item of result.resource_limitations) {
                    const keys = Object.keys(item).sort();
                    if (JSON.stringify(keys) !== JSON.stringify([
                      "code", "filename", "limitation", "size", "type",
                    ])) throw new Error(`limitation leaked fields: ${JSON.stringify(keys)}`);
                  }
                  const serialized = JSON.stringify(result);
                  for (const marker of ["PRIVATE_READ_FAILURE", "C:\\\\private", "application/octet-stream"]) {
                    if (serialized.includes(marker)) throw new Error(`private detail leaked: ${marker}`);
                  }
                })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
                """
            )
        )

    def test_file_count_and_per_file_limits_are_enforced_before_reads(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                const calls = Array(7).fill(0);
                const tiny = Array.from({ length: 6 }, (_, index) => ({
                  name: `file-${index}.pdf`, type: "application/pdf", size: 1,
                  arrayBuffer: async () => { calls[index] += 1; return Uint8Array.from([index]).buffer; },
                }));
                const oversized = {
                  name: "large.pdf", type: "application/pdf", size: 10 * 1024 * 1024 + 1,
                  arrayBuffer: async () => { calls[6] += 1; return new ArrayBuffer(1); },
                };
                (async () => {
                  const countResult = await api.readSelectedFiles(tiny);
                  if (countResult.attachment_files.length !== 5) throw new Error(JSON.stringify(countResult));
                  if (calls[5] !== 0 || !countResult.resource_limitations.some(
                    (item) => item.code === "frontend_limit",
                  )) throw new Error(`sixth file was not rejected before read: ${JSON.stringify(calls)}`);
                  const sizeResult = await api.readSelectedFiles([oversized]);
                  if (calls[6] !== 0 || sizeResult.attachment_files.length !== 0 ||
                      sizeResult.resource_limitations[0].code !== "frontend_limit") {
                    throw new Error(`oversized file was read: ${JSON.stringify(sizeResult)}`);
                  }
                })().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
                """
            )
        )

    def test_manual_first_merge_deduplicates_and_shares_count_and_byte_limits(self) -> None:
        self._run_node(
            textwrap.dedent(
                r"""
                const MiB = 1024 * 1024;
                const item = (filename, type, size, content, extra = {}) => ({
                  filename, type, size, content_base64: content, ...extra,
                });
                const firstBytes = btoa("\x01".repeat(10 * MiB));
                const secondBytes = btoa("\x02".repeat(10 * MiB));
                const thirdBytes = btoa("\x03".repeat(6 * MiB));
                const manual = [
                  item("same.pdf", "pdf", 10 * MiB, firstBytes, { path: "PRIVATE_PATH" }),
                  item("second.pdf", "pdf", 10 * MiB, secondBytes),
                ];
                const automatic = [
                  item("same.pdf", "pdf", 10 * MiB, firstBytes, { url: "PRIVATE_URL" }),
                  item("third.pdf", "pdf", 6 * MiB, thirdBytes),
                ];
                const limitations = [{
                  code: "resource_read_failed", filename: "failed.pdf", type: "pdf", size: 1,
                  limitation: "fixed", exception: "PRIVATE_EXCEPTION",
                }];
                const result = api.mergeAttachmentFiles(manual, automatic, limitations);
                if (result.attachment_files.length !== 2) throw new Error(JSON.stringify(result));
                if (result.attachment_files[0].content_base64 !== firstBytes ||
                    result.attachment_files[1].content_base64 !== secondBytes) {
                  throw new Error(`manual priority failed: ${JSON.stringify(result)}`);
                }
                if (!result.resource_limitations.some((entry) => entry.code === "frontend_limit")) {
                  throw new Error(`shared aggregate limit missing: ${JSON.stringify(result)}`);
                }
                const serialized = JSON.stringify(result);
                for (const marker of ["PRIVATE_PATH", "PRIVATE_URL", "PRIVATE_EXCEPTION"]) {
                  if (serialized.includes(marker)) throw new Error(`private marker leaked: ${marker}`);
                }
                """
            )
        )


if __name__ == "__main__":
    unittest.main()
