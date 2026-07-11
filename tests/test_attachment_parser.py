"""Tests for bounded, de-identified attachment parsing."""

from __future__ import annotations

import json
import sqlite3
import struct
import unittest
from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch
from zipfile import ZIP_STORED, ZipFile

import pypdf.filters as pypdf_filters
from docx import Document
from openpyxl import Workbook
from PIL import Image

from backend.email_agent import attachment_parser
from backend.email_agent.analyzer import build_analysis_prompt
from backend.email_agent.attachment_fact_safety import sanitize_constructed_fact
from backend.email_agent.attachment_facts import extract_attachment_facts
from backend.email_agent.attachment_parser import parse_attachments
from backend.email_agent.attachment_storage import StoredAttachment
from backend.email_agent.attachment_text import sanitize_text
from backend.email_agent.database import initialize_schema, save_analysis


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


class _ObservedDocxCell:
    def __init__(self, text: str) -> None:
        self._text = text
        self.read_count = 0

    @property
    def text(self) -> str:
        self.read_count += 1
        return self._text


class AttachmentParserTests(unittest.TestCase):
    def test_business_identifier_is_protected_only_inside_strict_fact_extraction(self) -> None:
        raw = (
            "RFQ: 7654321 unlabeled 7654322 phone +1 (202) 555-0199 "
            "RFQ: 1234-5678-9012-3456 PO: 202-555-0199 "
            "Invoice: 1234567890123456 RFQ: RFQ-1234567890123456 "
            "PO: PO-1234567890123456 Quantity: 202-555-0199 "
            "Amount: USD 1234-5678-9012-3456 "
            "Amount: USD 1,234,567,890,123,456"
        )
        sanitized = sanitize_text(raw)
        facts = extract_attachment_facts(raw)

        self.assertEqual(facts, ["Reference: RFQ 7654321"])
        for secret in (
            "7654321",
            "7654322",
            "+1 (202) 555-0199",
            "1234-5678-9012-3456",
            "202-555-0199",
            "1234567890123456",
            "RFQ-1234567890123456",
            "PO-1234567890123456",
            "USD 1234-5678-9012-3456",
            "USD 1,234,567,890,123,456",
        ):
            self.assertNotIn(secret, sanitized)

    def test_final_constructed_fact_sanitizer_rejects_prose_and_sensitive_shapes(self) -> None:
        accepted = (
            "Reference: RFQ 7654321",
            "Quantity: 200 pcs",
            "Measurement: 12.5 x 20 mm",
            "Amount: USD 125.50",
            "Deadline: within 3 days",
            "Requested action: confirm quantity",
            "Quality issue: out_of_tolerance",
        )
        for fact in accepted:
            with self.subTest(accepted=fact):
                self.assertEqual(sanitize_constructed_fact(fact), fact)

        rejected = (
            "PRIVATE arbitrary attachment prose",
            "Reference: RFQ RFQ-1234567890123456",
            "Reference: PO 202-555-0199",
            "Requested action: confirm quantity PRIVATE trailing prose",
            "Quality issue: physical_damage PRIVATE trailing prose",
            "Deadline: 2026-07-18",
        )
        for fact in rejected:
            with self.subTest(rejected=fact):
                self.assertEqual(sanitize_constructed_fact(fact), "")

    def test_structured_business_facts_are_safe_across_pdf_docx_xlsx_and_ocr(self) -> None:
        pdf_text = "\n".join([
            "PRIVATE_PDF_CONTIGUOUS_PROSE confidential launch narrative must not survive.",
            "RFQ: 7654321",
            "Quantity: 1,250 pcs",
            "Total cost: USD 12,345.67",
            "Due date: 2026-07-18",
            "Please confirm the revised quantity for the confidential launch program.",
            "buyer-pdf@example.test +1 (202) 555-0199 7654322 C:/private/pdf.txt",
        ])
        ocr_text = "\n".join([
            "PRIVATE_OCR_CONTIGUOUS_PROSE arbitrary OCR narrative must not survive.",
            "Order No: 7123456",
            "Dimensions: 8 x 10 mm",
            "Amount: CNY 300.00",
            "Please investigate the damaged surface for the confidential launch program.",
            "Quality issue: cracked housing",
            "buyer-ocr@example.test 1234-5678-9012-3456 /home/private/ocr.txt",
        ])
        docx_content = self._structured_docx_bytes()
        xlsx_content = self._structured_xlsx_bytes()

        with TemporaryDirectory() as directory:
            items = [
                self._write(directory, "structured.pdf", "pdf", b"synthetic"),
                self._write(directory, "structured.docx", "docx", docx_content),
                self._write(directory, "structured.xlsx", "xlsx", xlsx_content),
                self._write(directory, "structured.png", "image", self._image_bytes()),
            ]
            page = MagicMock()
            page.extract_text.return_value = pdf_text
            reader = MagicMock()
            reader.pages = [page]
            ocr = MagicMock()
            ocr.image_to_string.return_value = ocr_text
            with patch.object(attachment_parser, "PdfReader", return_value=reader):
                with patch.object(attachment_parser, "pytesseract", ocr):
                    insights = parse_attachments(items)

        facts_by_name = {
            str(insight["filename"]): list(insight["key_facts"])
            for insight in insights
        }
        self.assertEqual(
            facts_by_name["structured.pdf"],
            [
                "Reference: RFQ 7654321",
                "Quantity: 1,250 pcs",
                "Amount: USD 12,345.67",
                "Deadline: due 2026-07-18",
                "Requested action: confirm quantity",
            ],
        )
        self.assertEqual(
            facts_by_name["structured.docx"],
            [
                "Reference: Invoice INV-7000001",
                "Measurement: 12.5 x 20 mm",
                "Requested action: provide quotation",
                "Quality issue: out_of_tolerance",
                "Reference: Tracking TRK-987654321",
            ],
        )
        self.assertEqual(
            facts_by_name["structured.xlsx"],
            [
                "Reference: PO 8123456",
                "Quantity: 400 units",
                "Amount: EUR 9.50",
                "Deadline: within 3 days",
                "Requested action: provide quotation",
            ],
        )
        self.assertEqual(
            facts_by_name["structured.png"],
            [
                "Reference: Order 7123456",
                "Measurement: 8 x 10 mm",
                "Amount: CNY 300.00",
                "Requested action: investigate quality issue",
                "Quality issue: physical_damage",
            ],
        )
        allowed_prefixes = (
            "Reference: ",
            "Quantity: ",
            "Measurement: ",
            "Amount: ",
            "Deadline: ",
            "Requested action: ",
            "Quality issue: ",
        )
        for insight in insights:
            self.assertEqual(insight["status"], "parsed")
            self.assertLessEqual(len(insight["key_facts"]), attachment_parser.MAX_KEY_FACTS)
            for fact in insight["key_facts"]:
                self.assertTrue(str(fact).startswith(allowed_prefixes), fact)
                self.assertLessEqual(len(str(fact)), attachment_parser.MAX_KEY_FACT_CHARACTERS)

        prompt = build_analysis_prompt(
            subject="Synthetic structured attachment test",
            sender="sender@example.test",
            clean_body="Please review the synthetic attachments.",
            attachment_insights=insights,
        )
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)
        save_analysis(
            connection,
            subject="Synthetic structured attachment test",
            sender="sender@example.test",
            analysis={"summary": "Safe synthetic result.", "attachment_insights": insights},
        )
        stored_json = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        serialized_result = json.dumps(insights, ensure_ascii=False)
        canaries = (
            "PRIVATE_PDF_CONTIGUOUS_PROSE",
            "PRIVATE_DOCX_CONTIGUOUS_PROSE",
            "PRIVATE_XLSX_CONTIGUOUS_PROSE",
            "PRIVATE_OCR_CONTIGUOUS_PROSE",
            "confidential launch program",
            "buyer-pdf@example.test",
            "buyer-docx@example.test",
            "buyer-xlsx@example.test",
            "buyer-ocr@example.test",
            "+1 (202) 555-0199",
            "1234-5678-9012-3456",
            "7654322",
            "C:/private/pdf.txt",
            r"\\fileserver\private\docx.txt",
            "https://private.example.test/xlsx",
            "/home/private/ocr.txt",
        )
        for secret in canaries:
            for boundary, value in (
                ("result", serialized_result),
                ("prompt", prompt),
                ("storage", stored_json),
            ):
                with self.subTest(boundary=boundary, secret=secret):
                    self.assertNotIn(secret, value)

    def test_sensitive_attachment_text_is_redacted_before_result_prompt_and_storage(self) -> None:
        raw_prefix = "PRIVATE-PROSE-PREFIX customer correspondence must remain confidential."
        sensitive_values = (
            raw_prefix,
            "buyer@example.test",
            "+1 (202) 555-0199",
            "1234-5678-9012-3456",
            r"C:\private\quote.txt",
            r"\\fileserver\private\quote.pdf",
            "/home/customer/private/quote.xlsx",
            "https://private.example.test/download?id=42",
        )
        payload = "\n".join(
            [
                raw_prefix,
                "Reference: RFQ-SAFE-42",
                "Quantity: 200 pcs",
                *sensitive_values[1:],
            ]
        )

        sanitized = sanitize_text(payload)
        for secret in sensitive_values[1:]:
            with self.subTest(boundary="sanitizer", secret=secret):
                self.assertNotIn(secret, sanitized)
        for marker in ("[email removed]", "[number removed]", "[path removed]", "[link removed]"):
            self.assertIn(marker, sanitized)

        with TemporaryDirectory() as directory:
            items = [
                self._write(directory, "sensitive.pdf", "pdf", b"synthetic"),
                self._write(directory, "sensitive.xlsx", "xlsx", self._xlsx_bytes()),
                self._write(directory, "sensitive.docx", "docx", self._docx_bytes()),
                self._write(directory, "sensitive.png", "image", self._image_bytes()),
            ]
            page = MagicMock()
            page.extract_text.return_value = payload
            reader = MagicMock()
            reader.pages = [page]
            worksheet = MagicMock()
            worksheet.title = "Sensitive"
            worksheet.iter_rows.return_value = iter([(payload,)])
            workbook = MagicMock()
            workbook.worksheets = [worksheet]
            paragraph = MagicMock()
            paragraph.text = payload
            document = MagicMock()
            document.paragraphs = [paragraph]
            document.tables = []
            ocr = MagicMock()
            ocr.image_to_string.return_value = payload

            with patch.object(attachment_parser, "PdfReader", return_value=reader):
                with patch.object(attachment_parser, "load_workbook", return_value=workbook):
                    with patch.object(attachment_parser, "Document", return_value=document):
                        with patch.object(attachment_parser, "pytesseract", ocr):
                            insights = parse_attachments(items)

        expected_summaries = (
            "PDF content parsed; review structured facts.",
            "XLSX content parsed; review structured facts.",
            "DOCX content parsed; review structured facts.",
            "Image OCR content parsed; review structured facts.",
        )
        for insight, expected_summary in zip(insights, expected_summaries, strict=True):
            with self.subTest(attachment_type=insight["type"]):
                self.assertEqual(insight["status"], "parsed")
                self.assertEqual(insight["summary"], expected_summary)
                self.assertIn("Reference: RFQ-SAFE-42", insight["key_facts"])
                self.assertIn("Quantity: 200 pcs", insight["key_facts"])
                self.assertLessEqual(len(insight["key_facts"]), attachment_parser.MAX_KEY_FACTS)

        prompt = build_analysis_prompt(
            subject="Synthetic attachment test",
            sender="sender@example.test",
            clean_body="Please review the synthetic attachments.",
            attachment_insights=insights,
        )
        connection = sqlite3.connect(":memory:")
        initialize_schema(connection)
        save_analysis(
            connection,
            subject="Synthetic attachment test",
            sender="sender@example.test",
            analysis={"summary": "Safe synthetic result.", "attachment_insights": insights},
        )
        stored_json = connection.execute(
            "SELECT analysis_json FROM email_analysis"
        ).fetchone()[0]
        serialized_result = json.dumps(insights, ensure_ascii=False)
        for secret in sensitive_values:
            for boundary, value in (
                ("result", serialized_result),
                ("prompt", prompt),
                ("storage", stored_json),
            ):
                with self.subTest(boundary=boundary, secret=secret):
                    self.assertNotIn(secret, value)

    def test_parse_pdf_returns_bounded_safe_text_facts(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "request.pdf", "pdf", self._pdf_bytes())

            result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "parsed")
            self.assertEqual(result[0]["summary"], "PDF content parsed; review structured facts.")
            self.assertIn("Quantity: 12", result[0]["key_facts"])
            self.assertNotIn("https://example.test/rfq", self._visible_text(result[0]))
            self.assertNotIn("\x00", self._visible_text(result[0]))
            self.assertLessEqual(len(self._visible_text(result[0])), 2_000)

    def test_parse_xlsx_returns_limited_sheet_facts(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "quote.xlsx", "xlsx", self._xlsx_bytes())

            result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "parsed")
            self.assertEqual(result[0]["summary"], "XLSX content parsed; review structured facts.")
            self.assertIn("Row limit", " ".join(result[0]["limitations"]))
            self.assertNotIn("https://example.test/quote", self._visible_text(result[0]))

    def test_parse_docx_returns_limited_paragraph_facts(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "summary.docx", "docx", self._docx_bytes())

            result = parse_attachments([stored])

            self.assertEqual(set(result[0]), EXPECTED_KEYS)
            self.assertEqual(result[0]["status"], "parsed")
            self.assertEqual(result[0]["summary"], "DOCX content parsed; review structured facts.")
            self.assertIn("Paragraph limit", " ".join(result[0]["limitations"]))

    def test_parse_docx_supports_table_only_documents(self) -> None:
        document = Document()
        table = document.add_table(rows=2, cols=2)
        table.cell(0, 0).text = "Reference"
        table.cell(0, 1).text = "Quantity"
        table.cell(1, 0).text = "RFQ-TABLE-42"
        table.cell(1, 1).text = "200 pcs"
        content = BytesIO()
        document.save(content)

        with TemporaryDirectory() as directory:
            stored = self._write(directory, "table-only.docx", "docx", content.getvalue())
            result = parse_attachments([stored])

        self.assertEqual(result[0]["status"], "parsed")
        visible = self._visible_text(result[0])
        self.assertIn("RFQ-TABLE-42", visible)
        self.assertIn("200 pcs", visible)

    def test_parse_docx_combines_paragraph_and_table_text(self) -> None:
        document = Document()
        document.add_paragraph("Mixed document introduction")
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "Part-MIXED-7"
        table.cell(0, 1).text = "Needs review"
        content = BytesIO()
        document.save(content)

        with TemporaryDirectory() as directory:
            stored = self._write(directory, "mixed.docx", "docx", content.getvalue())
            result = parse_attachments([stored])

        visible = self._visible_text(result[0])
        self.assertNotIn("Mixed document introduction", visible)
        self.assertIn("Part-MIXED-7", visible)

    def test_docx_table_rows_and_cells_stop_at_explicit_caps(self) -> None:
        unread_row_cell = _ObservedDocxCell("UNREACHED-ROW")
        unread_column_cell = _ObservedDocxCell("UNREACHED-CELL")
        bounded_row = MagicMock()
        bounded_row.cells = [
            _ObservedDocxCell(f"Cell {index}")
            for index in range(attachment_parser.MAX_DOCX_CELLS_PER_ROW)
        ] + [unread_column_cell]
        rows = [bounded_row]
        for _index in range(attachment_parser.MAX_DOCX_ROWS_PER_TABLE - 1):
            row = MagicMock()
            row.cells = [_ObservedDocxCell("bounded")]
            rows.append(row)
        unread_row = MagicMock()
        unread_row.cells = [unread_row_cell]
        table = MagicMock()
        table.rows = [*rows, unread_row]
        document = MagicMock()
        document.paragraphs = []
        document.tables = [table]

        with TemporaryDirectory() as directory:
            stored = self._write(directory, "bounded-table.docx", "docx", self._docx_bytes())
            with patch.object(attachment_parser, "Document", return_value=document):
                result = parse_attachments([stored])

        limitations = " ".join(result[0]["limitations"])
        self.assertIn("Table row limit", limitations)
        self.assertIn("Table cell limit", limitations)
        self.assertEqual(unread_row_cell.read_count, 0)
        self.assertEqual(unread_column_cell.read_count, 0)

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
            stored = self._write(directory, "dense.xlsx", "xlsx", self._xlsx_bytes())
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
            stored = self._write(directory, "dense.docx", "docx", self._docx_bytes())
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
                "https://example.test/private_(quote)",
                "http://[2001:db8::1]/private",
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
            for leaked_fragment in ("(quote)", "2001:db8", "/private"):
                self.assertNotIn(leaked_fragment, visible_text)
            self.assertEqual(result[0]["summary"], "Image OCR content parsed; review structured facts.")

    def test_pdf_decoder_failure_returns_exact_safe_limitation(self) -> None:
        secret = "PRIVATE_PDF_SOURCE"
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "broken.pdf", "pdf", b"synthetic")
            with patch.object(attachment_parser, "PdfReader", side_effect=RuntimeError(secret)):
                result = parse_attachments([stored])

        self._assert_safe_failure(
            result[0],
            "PDF content could not be decoded safely.",
            secret,
        )

    def test_xlsx_loader_failure_returns_exact_safe_limitation(self) -> None:
        secret = "PRIVATE_XLSX_CELL"
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "broken.xlsx", "xlsx", self._xlsx_bytes())
            with patch.object(
                attachment_parser,
                "load_workbook",
                side_effect=RuntimeError(secret),
            ):
                result = parse_attachments([stored])

        self._assert_safe_failure(
            result[0],
            "XLSX workbook content could not be parsed safely.",
            secret,
        )

    def test_docx_loader_failure_returns_exact_safe_limitation(self) -> None:
        secret = "PRIVATE_DOCX_TEXT"
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "broken.docx", "docx", self._docx_bytes())
            with patch.object(
                attachment_parser,
                "Document",
                side_effect=RuntimeError(secret),
            ):
                result = parse_attachments([stored])

        self._assert_safe_failure(
            result[0],
            "DOCX document content could not be parsed safely.",
            secret,
        )

    def test_image_verification_failure_returns_exact_safe_limitation(self) -> None:
        secret = "PRIVATE_IMAGE_BYTES"
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "broken.png", "image", b"synthetic")
            with patch.object(attachment_parser.Image, "open", side_effect=OSError(secret)):
                result = parse_attachments([stored])

        self._assert_safe_failure(
            result[0],
            "Image content could not be verified safely.",
            secret,
        )

    def test_ocr_failure_returns_exact_safe_limitation(self) -> None:
        secret = "PRIVATE_OCR_TEXT"
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "broken-ocr.png", "image", self._image_bytes())
            ocr = MagicMock()
            ocr.image_to_string.side_effect = RuntimeError(secret)

            with patch.object(attachment_parser, "pytesseract", ocr):
                result = parse_attachments([stored])

        self._assert_safe_failure(
            result[0],
            "OCR could not be completed; image metadata only.",
            secret,
        )

    def test_pdf_decoder_limits_are_lowered_before_reader_initialization(self) -> None:
        limit_names = (
            "ZLIB_MAX_OUTPUT_LENGTH",
            "LZW_MAX_OUTPUT_LENGTH",
            "RUN_LENGTH_MAX_OUTPUT_LENGTH",
            "JBIG2_MAX_OUTPUT_LENGTH",
            "MAX_DECLARED_STREAM_LENGTH",
            "MAX_ARRAY_BASED_STREAM_OUTPUT_LENGTH",
        )
        project_limit = 10 * 1024 * 1024
        initial_limits = {name: 75_000_000 for name in limit_names}
        initial_limits[limit_names[0]] = project_limit // 2
        expected_limits = {name: project_limit for name in limit_names}
        expected_limits[limit_names[0]] = project_limit // 2
        observed_limits: dict[str, int] = {}
        reader = MagicMock()
        reader.pages = []

        def build_reader(*_args: object, **_kwargs: object) -> MagicMock:
            observed_limits.update({name: getattr(pypdf_filters, name) for name in limit_names})
            return reader

        with TemporaryDirectory() as directory:
            stored = self._write(directory, "bounded.pdf", "pdf", b"synthetic")
            with patch.multiple(pypdf_filters, **initial_limits):
                with patch.object(attachment_parser, "PdfReader", side_effect=build_reader):
                    parse_attachments([stored])

        self.assertEqual(observed_limits, expected_limits)

    def test_malformed_office_packages_do_not_invoke_loaders(self) -> None:
        cases = (
            ("broken.docx", "docx", "Document"),
            ("broken.xlsx", "xlsx", "load_workbook"),
        )
        for filename, attachment_type, loader_name in cases:
            with self.subTest(attachment_type=attachment_type):
                with TemporaryDirectory() as directory:
                    stored = self._write(directory, filename, attachment_type, b"not a zip")
                    loader = MagicMock()

                    with patch.object(attachment_parser, loader_name, loader):
                        result = parse_attachments([stored])

                self.assertEqual(result[0]["status"], "metadata_only")
                expected = (
                    f"{attachment_type.upper()} package is malformed; "
                    "attachment content was not parsed."
                )
                self.assertEqual(result[0]["limitations"], [expected])
                loader.assert_not_called()

    def test_office_zip_entry_count_limit_prevents_xlsx_loader(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "many.xlsx", "xlsx", self._zip_bytes(257))
            loader = MagicMock()

            with patch.object(attachment_parser, "load_workbook", loader):
                result = parse_attachments([stored])

        self.assertIn("entry count", result[0]["limitations"][0].lower())
        loader.assert_not_called()

    def test_office_zip_entry_size_limit_prevents_docx_loader(self) -> None:
        declared_size = 10 * 1024 * 1024 + 1
        with TemporaryDirectory() as directory:
            stored = self._write(
                directory,
                "large.docx",
                "docx",
                self._zip_bytes(1, [declared_size]),
            )
            loader = MagicMock()

            with patch.object(attachment_parser, "Document", loader):
                result = parse_attachments([stored])

        self.assertIn("entry size", result[0]["limitations"][0].lower())
        loader.assert_not_called()

    def test_office_zip_total_size_limit_prevents_xlsx_loader(self) -> None:
        declared_sizes = [9 * 1024 * 1024] * 3
        with TemporaryDirectory() as directory:
            stored = self._write(
                directory,
                "expanded.xlsx",
                "xlsx",
                self._zip_bytes(3, declared_sizes),
            )
            loader = MagicMock()

            with patch.object(attachment_parser, "load_workbook", loader):
                result = parse_attachments([stored])

        self.assertIn("total uncompressed size", result[0]["limitations"][0].lower())
        loader.assert_not_called()

    def test_ocr_uses_explicit_timeout(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._write(directory, "timeout.png", "image", self._image_bytes())
            ocr = MagicMock()
            ocr.image_to_string.return_value = "bounded OCR"

            with patch.object(attachment_parser, "pytesseract", ocr):
                parse_attachments([stored])

        self.assertEqual(ocr.image_to_string.call_args.kwargs, {"timeout": 5})

    def test_pdf_exact_budget_reports_only_when_page_is_omitted(self) -> None:
        cases = ((False, False), (True, True))
        for has_remaining_page, expected_limit in cases:
            with self.subTest(has_remaining_page=has_remaining_page):
                pages = [MagicMock(), MagicMock()]
                pages[0].extract_text.return_value = "A" * 1_000
                pages[1].extract_text.return_value = "B" * 999
                if has_remaining_page:
                    remaining_page = MagicMock()
                    remaining_page.extract_text.return_value = "UNREACHED"
                    pages.append(remaining_page)
                reader = MagicMock()
                reader.pages = pages
                with TemporaryDirectory() as directory:
                    stored = self._write(directory, "exact.pdf", "pdf", b"synthetic")
                    with patch.object(attachment_parser, "PdfReader", return_value=reader):
                        result = parse_attachments([stored])

                self.assertEqual(self._has_character_limit(result[0]), expected_limit)
                if has_remaining_page:
                    remaining_page.extract_text.assert_not_called()

    def test_docx_exact_budget_reports_only_when_paragraph_is_omitted(self) -> None:
        cases = ((False, False), (True, True))
        for has_remaining_paragraph, expected_limit in cases:
            with self.subTest(has_remaining_paragraph=has_remaining_paragraph):
                paragraphs = [
                    _ObservedParagraph("A" * 1_000),
                    _ObservedParagraph("B" * 999),
                ]
                if has_remaining_paragraph:
                    paragraphs.append(_ObservedParagraph("UNREACHED"))
                document = MagicMock()
                document.paragraphs = paragraphs
                with TemporaryDirectory() as directory:
                    stored = self._write(directory, "exact.docx", "docx", self._docx_bytes())
                    with patch.object(attachment_parser, "Document", return_value=document):
                        result = parse_attachments([stored])

                self.assertEqual(self._has_character_limit(result[0]), expected_limit)
                if has_remaining_paragraph:
                    self.assertEqual(paragraphs[2].read_count, 0)

    def test_xlsx_exact_row_budget_reports_only_when_cell_is_omitted(self) -> None:
        cases = ((False, False), (True, True))
        for has_remaining_cell, expected_limit in cases:
            with self.subTest(has_remaining_cell=has_remaining_cell):
                unread_cell = _ObservedCell("UNREACHED")
                row: tuple[object, ...] = ("A" * 1_000, "B" * 94)
                if has_remaining_cell:
                    row = (*row, unread_cell)
                sheet = MagicMock()
                sheet.title = "S"
                sheet.iter_rows.return_value = iter([row])
                workbook = MagicMock()
                workbook.worksheets = [sheet]
                with TemporaryDirectory() as directory:
                    stored = self._write(directory, "exact.xlsx", "xlsx", self._xlsx_bytes())
                    with patch.object(attachment_parser, "load_workbook", return_value=workbook):
                        result = parse_attachments([stored])

                self.assertEqual(self._has_character_limit(result[0]), expected_limit)
                if has_remaining_cell:
                    self.assertEqual(unread_cell.read_count, 0)

    def test_xlsx_exact_total_budget_reports_omitted_row_or_sheet(self) -> None:
        cases = (("none", False), ("row", True), ("sheet", True))
        for remaining_kind, expected_limit in cases:
            with self.subTest(remaining_kind=remaining_kind):
                first_sheet = MagicMock()
                first_sheet.title = "S"
                rows = [("A" * 1_000,), ("B" * 993,)]
                if remaining_kind == "row":
                    rows.append(("UNREACHED",))
                first_sheet.iter_rows.return_value = iter(rows)
                worksheets = [first_sheet]
                if remaining_kind == "sheet":
                    second_sheet = MagicMock()
                    second_sheet.title = "Unreached"
                    second_sheet.iter_rows.return_value = iter([("UNREACHED",)])
                    worksheets.append(second_sheet)
                workbook = MagicMock()
                workbook.worksheets = worksheets
                with TemporaryDirectory() as directory:
                    stored = self._write(directory, "exact.xlsx", "xlsx", self._xlsx_bytes())
                    with patch.object(attachment_parser, "load_workbook", return_value=workbook):
                        result = parse_attachments([stored])

                self.assertEqual(self._has_character_limit(result[0]), expected_limit)
                if remaining_kind == "sheet":
                    second_sheet.iter_rows.assert_not_called()

    @staticmethod
    def _visible_text(insight: dict[str, object]) -> str:
        return " ".join([str(insight["summary"]), *(str(fact) for fact in insight["key_facts"])])

    @staticmethod
    def _has_character_limit(insight: dict[str, object]) -> bool:
        return "Character limit" in " ".join(insight["limitations"])

    def _assert_safe_failure(
        self,
        insight: dict[str, object],
        expected_limitation: str,
        secret: str,
    ) -> None:
        self.assertEqual(set(insight), EXPECTED_KEYS)
        self.assertEqual(insight["status"], "metadata_only")
        self.assertEqual(insight["limitations"], [expected_limitation])
        self.assertNotIn(secret, repr(insight))

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
    def _structured_docx_bytes() -> bytes:
        document = Document()
        document.add_paragraph(
            "PRIVATE_DOCX_CONTIGUOUS_PROSE confidential narrative must not survive. "
            "Invoice No: INV-7000001. Please provide the quotation for the confidential launch program. "
            r"buyer-docx@example.test \\fileserver\private\docx.txt"
        )
        table = document.add_table(rows=3, cols=2)
        table.cell(0, 0).text = "Tracking number"
        table.cell(0, 1).text = "TRK-987654321"
        table.cell(1, 0).text = "Dimensions"
        table.cell(1, 1).text = "12.5 x 20 mm"
        table.cell(2, 0).text = "Quality issue"
        table.cell(2, 1).text = "out of tolerance and scratched surface"
        content = BytesIO()
        document.save(content)
        return content.getvalue()

    @staticmethod
    def _structured_xlsx_bytes() -> bytes:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Structured"
        sheet.append(["PRIVATE_XLSX_CONTIGUOUS_PROSE", "arbitrary narrative must not survive"])
        sheet.append(["PO", "8123456"])
        sheet.append(["Quantity", "400 units"])
        sheet.append(["Unit cost", "EUR 9.50"])
        sheet.append(["Deadline", "within 3 days"])
        sheet.append(["Action required", "provide quotation"])
        sheet.append(["Private", "buyer-xlsx@example.test"])
        sheet.append(["Private URL", "https://private.example.test/xlsx"])
        content = BytesIO()
        workbook.save(content)
        return content.getvalue()

    @staticmethod
    def _image_bytes() -> bytes:
        image = Image.new("RGB", (10, 20), color="white")
        content = BytesIO()
        image.save(content, format="PNG")
        return content.getvalue()

    @staticmethod
    def _zip_bytes(entry_count: int, declared_sizes: list[int] | None = None) -> bytes:
        content = BytesIO()
        with ZipFile(content, "w", compression=ZIP_STORED) as archive:
            for index in range(entry_count):
                archive.writestr(f"entry-{index}.xml", b"x")
        payload = bytearray(content.getvalue())
        search_offset = 0
        for declared_size in declared_sizes or []:
            central_offset = payload.find(b"PK\x01\x02", search_offset)
            if central_offset < 0:
                raise AssertionError("Synthetic ZIP central directory is incomplete.")
            struct.pack_into("<I", payload, central_offset + 24, declared_size)
            search_offset = central_offset + 46
        return bytes(payload)


if __name__ == "__main__":
    unittest.main()
