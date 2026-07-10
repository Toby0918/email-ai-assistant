"""Tests for bounded, de-identified attachment parsing."""

from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from docx import Document
from openpyxl import Workbook
from PIL import Image

from backend.email_agent import attachment_parser
from backend.email_agent.attachment_parser import parse_attachments
from backend.email_agent.attachment_storage import StoredAttachment


EXPECTED_KEYS = {"filename", "type", "status", "summary", "key_facts", "limitations"}


class _ObservedParagraph:
    def __init__(self, text: str) -> None:
        self._text = text
        self.read_count = 0

    @property
    def text(self) -> str:
        self.read_count += 1
        return self._text


class _ObservedCell:
    def __init__(self, text: str) -> None:
        self.text = text
        self.read_count = 0

    def __str__(self) -> str:
        self.read_count += 1
        return self.text


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

    def test_pdf_stops_collecting_when_character_budget_is_exhausted(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "dense.pdf", "pdf", b"synthetic")
            pages = [MagicMock(), MagicMock(), MagicMock()]
            pages[0].extract_text.return_value = "A" * 5_000
            pages[1].extract_text.return_value = "B" * 5_000
            pages[2].extract_text.return_value = "UNREACHED"
            reader = MagicMock()
            reader.pages = pages

            with patch.object(attachment_parser, "PdfReader", return_value=reader):
                with patch.object(
                    attachment_parser,
                    "_text_insight",
                    wraps=attachment_parser._text_insight,
                ) as text_insight:
                    result = parse_attachments([stored])

            collected = text_insight.call_args.args[1]
            self.assertLessEqual(len(collected), attachment_parser.MAX_EXTRACTED_CHARACTERS)
            pages[1].extract_text.assert_called_once()
            pages[2].extract_text.assert_not_called()
            self.assertIn("Character limit", " ".join(result[0]["limitations"]))

    def test_xlsx_stops_collecting_cells_and_sheets_at_character_budget(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "dense.xlsx", "xlsx", b"synthetic")
            unread_cell = _ObservedCell("UNREACHED")
            first_sheet = MagicMock()
            first_sheet.title = "Dense"
            first_sheet.iter_rows.return_value = iter(
                [("A" * 5_000,), ("B" * 5_000,), (unread_cell,)]
            )
            second_sheet = MagicMock()
            second_sheet.title = "Unreached"
            second_sheet.iter_rows.return_value = iter([("UNREACHED",)])
            workbook = MagicMock()
            workbook.worksheets = [first_sheet, second_sheet]

            with patch.object(attachment_parser, "load_workbook", return_value=workbook):
                with patch.object(
                    attachment_parser,
                    "_text_insight",
                    wraps=attachment_parser._text_insight,
                ) as text_insight:
                    result = parse_attachments([stored])

            collected = text_insight.call_args.args[1]
            self.assertLessEqual(len(collected), attachment_parser.MAX_EXTRACTED_CHARACTERS)
            self.assertEqual(unread_cell.read_count, 0)
            second_sheet.iter_rows.assert_not_called()
            self.assertIn("Character limit", " ".join(result[0]["limitations"]))

    def test_docx_stops_reading_paragraphs_at_character_budget(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "dense.docx", "docx", b"synthetic")
            paragraphs = [
                _ObservedParagraph("A" * 5_000),
                _ObservedParagraph("B" * 5_000),
                _ObservedParagraph("UNREACHED"),
            ]
            document = MagicMock()
            document.paragraphs = paragraphs

            with patch.object(attachment_parser, "Document", return_value=document):
                with patch.object(
                    attachment_parser,
                    "_text_insight",
                    wraps=attachment_parser._text_insight,
                ) as text_insight:
                    result = parse_attachments([stored])

            collected = text_insight.call_args.args[1]
            self.assertLessEqual(len(collected), attachment_parser.MAX_EXTRACTED_CHARACTERS)
            self.assertEqual(paragraphs[2].read_count, 0)
            self.assertIn("Character limit", " ".join(result[0]["limitations"]))

    def test_ocr_text_is_bounded_before_summary_processing(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "dense.png", "image", self._image_bytes())
            ocr = MagicMock()
            ocr.image_to_string.return_value = "O" * 10_000

            with patch.object(attachment_parser, "pytesseract", ocr):
                with patch.object(
                    attachment_parser,
                    "_text_insight",
                    wraps=attachment_parser._text_insight,
                ) as text_insight:
                    result = parse_attachments([stored])

            collected = text_insight.call_args.args[1]
            self.assertLessEqual(len(collected), attachment_parser.MAX_EXTRACTED_CHARACTERS)
            self.assertIn("Character limit", " ".join(result[0]["limitations"]))

    def test_image_pixel_guard_prevents_oversized_ocr_input(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "oversized.png", "image", b"synthetic")
            image = MagicMock()
            image.__enter__.return_value = image
            image.size = (100_000, 100_000)
            ocr = MagicMock()
            ocr.image_to_string.return_value = "should not be read"

            with patch.object(attachment_parser.Image, "open", return_value=image):
                with patch.object(attachment_parser, "pytesseract", ocr):
                    result = parse_attachments([stored])

            self.assertEqual(result[0]["status"], "metadata_only")
            self.assertIn("pixel", result[0]["limitations"][0].lower())
            ocr.image_to_string.assert_not_called()

    def test_all_displayable_url_schemes_are_replaced(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "links.png", "image", self._image_bytes())
            source_urls = [
                "http://web.example.test/a",
                "https://secure.example.test/b",
                "www.public.example.test/c",
                "mailto:buyer@example.test",
                "ftp://files.example.test/quote",
                "file:///C:/private/quote.xlsx",
                "sftp://host.example.test/root",
                "data:text/plain,private",
            ]
            ocr = MagicMock()
            ocr.image_to_string.return_value = " ".join(source_urls)

            with patch.object(attachment_parser, "pytesseract", ocr):
                result = parse_attachments([stored])

            visible_text = self._visible_text(result[0])
            for source_url in source_urls:
                self.assertNotIn(source_url, visible_text)
            self.assertIn("[link removed]", visible_text)

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
