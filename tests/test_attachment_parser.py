"""Tests for bounded, de-identified attachment parsing."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from docx import Document
from openpyxl import Workbook
from PIL import Image

from backend.email_agent.attachment_parser import parse_attachments
from backend.email_agent.attachment_storage import StoredAttachment


EXPECTED_KEYS = {"filename", "type", "status", "summary", "key_facts", "limitations"}


class AttachmentParserTests(unittest.TestCase):
    def test_parse_pdf_returns_bounded_safe_text_facts(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "request.pdf", "pdf", self._pdf_bytes())

            result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "parsed")
            self.assertIn("RFQ", result[0]["summary"])
            self.assertNotIn("https://example.test/rfq", self._visible_text(result[0]))
            self.assertNotIn("\x00", self._visible_text(result[0]))
            self.assertLessEqual(len(self._visible_text(result[0])), 2_000)

    def test_parse_xlsx_returns_limited_sheet_facts(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "quote.xlsx", "xlsx", self._xlsx_bytes())

            result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "parsed")
            self.assertIn("Quote", result[0]["summary"])
            self.assertIn("Row limit", " ".join(result[0]["limitations"]))
            self.assertNotIn("https://example.test/quote", self._visible_text(result[0]))

    def test_parse_docx_returns_limited_paragraph_facts(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "summary.docx", "docx", self._docx_bytes())

            result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "parsed")
            self.assertIn("Purchase order", result[0]["summary"])
            self.assertIn("Paragraph limit", " ".join(result[0]["limitations"]))

    def test_parse_image_marks_ocr_unavailable_without_failing(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "label.png", "image", self._image_bytes())

            with patch("backend.email_agent.attachment_parser.pytesseract", None):
                result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "metadata_only")
            self.assertIn("OCR", result[0]["limitations"][0])

    def test_parse_errors_become_limitations(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "broken.pdf", "pdf", b"not a PDF")

            with self.assertNoLogs("pypdf", level="WARNING"):
                result = parse_attachments([stored])

            self.assertEqual(result[0]["status"], "metadata_only")
            self.assertTrue(result[0]["limitations"])

    def test_parse_does_not_open_macro_enabled_office_files(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "quote.xlsm", "xlsx", self._xlsx_bytes())

            result = parse_attachments([stored])

            self.assertEqual(result[0]["status"], "metadata_only")
            self.assertIn(".xlsx", result[0]["limitations"][0])

    @staticmethod
    def _visible_text(insight: dict[str, object]) -> str:
        return " ".join([str(insight["summary"]), *(str(fact) for fact in insight["key_facts"])])

    @staticmethod
    def _write(directory: str, filename: str, attachment_type: str, content: bytes) -> StoredAttachment:
        path = Path(directory) / filename
        path.write_bytes(content)
        return StoredAttachment(
            safe_filename=filename,
            type=attachment_type,
            path=path,
            byte_size=len(content),
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

    @staticmethod
    def _pdf_bytes() -> bytes:
        text = "RFQ quantity 12 https://example.test/rfq " + ("bounded text " * 300)
        stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode("ascii")
        objects = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /MediaBox [0 0 612 792] /Contents 4 0 R >>",
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        ]
        body = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for index, value in enumerate(objects, start=1):
            offsets.append(len(body))
            body.extend(f"{index} 0 obj\n".encode("ascii"))
            body.extend(value)
            body.extend(b"\nendobj\n")
        xref_offset = len(body)
        body.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
        body.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            body.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
        body.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii"))
        return bytes(body)

    @staticmethod
    def _xlsx_bytes() -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Quote"
        sheet.append(["Item", "Quantity", "Website"])
        sheet.append(["Widget", 12, "https://example.test/quote"])
        for row_number in range(2, 40):
            sheet.append([f"Part {row_number}", row_number, "pending"])
        content = BytesIO()
        workbook.save(content)
        return content.getvalue()

    @staticmethod
    def _docx_bytes() -> bytes:
        document = Document()
        document.add_paragraph("Purchase order review is required before confirmation.")
        for number in range(60):
            document.add_paragraph(f"Synthetic detail {number}")
        content = BytesIO()
        document.save(content)
        return content.getvalue()

    @staticmethod
    def _image_bytes() -> bytes:
        image = Image.new("RGB", (10, 20), color="white")
        content = BytesIO()
        image.save(content, format="PNG")
        return content.getvalue()


if __name__ == "__main__":
    unittest.main()
