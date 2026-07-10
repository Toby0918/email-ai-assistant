"""Bounded, display-safe parsing for supported temporary attachments."""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

from docx import Document
from openpyxl import load_workbook
from PIL import Image
from pypdf import PdfReader

try:
    import pytesseract
except ImportError:  # pragma: no cover - dependency is pinned but OCR remains optional.
    pytesseract = None

from .attachment_storage import StoredAttachment


MAX_PDF_PAGES = 3
MAX_XLSX_SHEETS = 3
MAX_XLSX_ROWS_PER_SHEET = 30
MAX_DOCX_PARAGRAPHS = 50
MAX_EXTRACTED_CHARACTERS = 2_000
MAX_PDF_PAGE_CHARACTERS = 1_000
MAX_XLSX_CELL_CHARACTERS = 1_000
MAX_XLSX_ROW_CHARACTERS = 1_100
MAX_DOCX_PARAGRAPH_CHARACTERS = 1_000
MAX_OCR_CHARACTERS = 2_000
MAX_IMAGE_PIXELS = 25_000_000
MAX_SUMMARY_CHARACTERS = 600
MAX_KEY_FACTS = 5
MAX_KEY_FACT_CHARACTERS = 240

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_URL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9+.-])(?:[A-Za-z][A-Za-z0-9+.-]*:|www\.)[^\s<>()\[\]{}]+",
    re.IGNORECASE,
)
_ALLOWED_SUFFIXES = {
    "pdf": {".pdf"},
    "xlsx": {".xlsx"},
    "docx": {".docx"},
    "image": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"},
}


class _TextBudget:
    def __init__(self, limit: int = MAX_EXTRACTED_CHARACTERS) -> None:
        self.limit = limit
        self.parts: list[str] = []
        self.character_count = 0
        self.truncated = False

    @property
    def exhausted(self) -> bool:
        return self.character_count >= self.limit

    @property
    def text(self) -> str:
        return "".join(self.parts)

    def add(self, value: str, unit_limit: int, separator: str = "\n") -> None:
        if self.exhausted:
            self.truncated = True
            return
        bounded_value = value[:unit_limit]
        if len(value) > unit_limit:
            self.truncated = True
        safe_value = _sanitize_text(bounded_value)
        if len(safe_value) > unit_limit:
            safe_value = safe_value[:unit_limit]
            self.truncated = True
        if not safe_value:
            return
        prefix = separator if self.parts else ""
        available = self.limit - self.character_count
        addition = f"{prefix}{safe_value}"
        if len(addition) > available:
            addition = addition[:available]
            self.truncated = True
        self.parts.append(addition)
        self.character_count += len(addition)


def parse_attachments(items: list[StoredAttachment]) -> list[dict[str, object]]:
    """Return bounded, de-identified insights for stored current-email attachments."""
    return [_parse_one(item) for item in items]


def _parse_one(item: StoredAttachment) -> dict[str, object]:
    extension_limitation = _extension_limitation(item)
    if extension_limitation:
        return _metadata_only(item, extension_limitation)

    parsers: dict[str, Callable[[StoredAttachment], dict[str, object]]] = {
        "pdf": _parse_pdf,
        "xlsx": _parse_xlsx,
        "docx": _parse_docx,
        "image": _parse_image,
    }
    parser = parsers.get(item.type)
    if parser is None:
        return _metadata_only(item, "Unsupported attachment type.")
    try:
        return parser(item)
    except Exception:
        return _metadata_only(item, "Attachment content could not be parsed.")


def _parse_pdf(item: StoredAttachment) -> dict[str, object]:
    reader = PdfReader(str(item.path), strict=True)
    try:
        collector = _TextBudget()
        for page in reader.pages[:MAX_PDF_PAGES]:
            if collector.exhausted:
                break
            collector.add(page.extract_text() or "", MAX_PDF_PAGE_CHARACTERS)
        limitations = _character_limitations(collector)
        if len(reader.pages) > MAX_PDF_PAGES:
            limitations.append("Page limit reached; remaining pages were not parsed.")
        return _text_insight(item, collector.text, limitations, "PDF")
    finally:
        reader.close()


def _parse_xlsx(item: StoredAttachment) -> dict[str, object]:
    workbook = load_workbook(item.path, read_only=True, data_only=True, keep_links=False)
    try:
        all_worksheets = workbook.worksheets
        worksheets = all_worksheets[:MAX_XLSX_SHEETS]
        limitations: list[str] = []
        collector = _TextBudget()
        for worksheet in worksheets:
            if collector.exhausted:
                break
            for row_number, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
                if row_number > MAX_XLSX_ROWS_PER_SHEET:
                    limitations.append("Row limit reached; remaining rows were not parsed.")
                    break
                _collect_xlsx_row(collector, str(worksheet.title), row)
                if collector.exhausted:
                    break
        if len(all_worksheets) > MAX_XLSX_SHEETS:
            limitations.append("Sheet limit reached; remaining sheets were not parsed.")
    finally:
        workbook.close()
    limitations = [*_character_limitations(collector), *limitations]
    return _text_insight(item, collector.text, limitations, "XLSX")


def _parse_docx(item: StoredAttachment) -> dict[str, object]:
    document = Document(item.path)
    paragraphs = document.paragraphs
    collector = _TextBudget()
    for paragraph in paragraphs[:MAX_DOCX_PARAGRAPHS]:
        if collector.exhausted:
            break
        collector.add(paragraph.text, MAX_DOCX_PARAGRAPH_CHARACTERS)
    limitations = _character_limitations(collector)
    if len(paragraphs) > MAX_DOCX_PARAGRAPHS:
        limitations.append("Paragraph limit reached; remaining paragraphs were not parsed.")
    return _text_insight(item, collector.text, limitations, "DOCX")


def _parse_image(item: StoredAttachment) -> dict[str, object]:
    with Image.open(item.path) as image:
        width, height = image.size
        image.verify()
    dimensions = f"Image dimensions: {width} x {height}."
    if width * height > MAX_IMAGE_PIXELS:
        return _metadata_only(item, "Image pixel limit exceeded; OCR was not attempted.", [dimensions])
    if pytesseract is None:
        return _metadata_only(item, "OCR is unavailable; image metadata only.", [dimensions])
    try:
        with Image.open(item.path) as image:
            collector = _TextBudget()
            collector.add(pytesseract.image_to_string(image), MAX_OCR_CHARACTERS)
    except Exception:
        return _metadata_only(item, "OCR could not be completed; image metadata only.", [dimensions])
    if not collector.text:
        return _metadata_only(item, "OCR returned no readable text; image metadata only.", [dimensions])
    return _text_insight(
        item,
        collector.text,
        _character_limitations(collector),
        "Image OCR",
        [dimensions],
    )


def _collect_xlsx_row(
    collector: _TextBudget, sheet_title: str, row: tuple[object, ...]
) -> None:
    row_collector = _TextBudget(MAX_XLSX_ROW_CHARACTERS)
    row_collector.add(sheet_title, MAX_XLSX_CELL_CHARACTERS, separator="")
    has_value = False
    for value in row:
        if value is None:
            continue
        if row_collector.exhausted:
            break
        separator = ": " if not has_value else " | "
        row_collector.add(str(value), MAX_XLSX_CELL_CHARACTERS, separator=separator)
        has_value = True
    if not has_value:
        return
    if row_collector.truncated:
        collector.truncated = True
    collector.add(row_collector.text, MAX_XLSX_ROW_CHARACTERS)


def _character_limitations(collector: _TextBudget) -> list[str]:
    if collector.truncated:
        return ["Character limit reached; remaining text was not parsed."]
    return []


def _text_insight(
    item: StoredAttachment,
    text: str,
    limitations: list[str],
    label: str,
    metadata_facts: list[str] | None = None,
) -> dict[str, object]:
    sanitized = _sanitize_text(text)
    if not sanitized:
        return _metadata_only(item, f"{label} contains no readable text.", metadata_facts)
    bounded = sanitized[:MAX_EXTRACTED_CHARACTERS].rstrip()
    if len(sanitized) > MAX_EXTRACTED_CHARACTERS:
        limitations = [*limitations, "Character limit reached; remaining text was not parsed."]
    facts = _facts_from_text(bounded, metadata_facts)
    return _insight(
        item,
        "parsed",
        f"{label}: {bounded[:MAX_SUMMARY_CHARACTERS].rstrip()}",
        facts,
        limitations,
    )


def _metadata_only(
    item: StoredAttachment, limitation: str, facts: list[str] | None = None
) -> dict[str, object]:
    return _insight(
        item,
        "metadata_only",
        f"{item.type.upper()} attachment metadata only.",
        facts or [f"Size: {item.byte_size} bytes."],
        [limitation],
    )


def _insight(
    item: StoredAttachment,
    status: str,
    summary: str,
    facts: list[str],
    limitations: list[str],
) -> dict[str, object]:
    return {
        "filename": item.safe_filename,
        "type": item.type,
        "status": status,
        "summary": _sanitize_text(summary)[:MAX_SUMMARY_CHARACTERS],
        "key_facts": [_sanitize_text(fact)[:MAX_KEY_FACT_CHARACTERS] for fact in facts[:MAX_KEY_FACTS]],
        "limitations": [_sanitize_text(limitation)[:MAX_KEY_FACT_CHARACTERS] for limitation in limitations],
    }


def _facts_from_text(text: str, metadata_facts: list[str] | None) -> list[str]:
    facts = list(metadata_facts or [])
    for value in re.split(r"[\r\n]+", text):
        cleaned = _sanitize_text(value)
        if cleaned and cleaned not in facts:
            facts.append(cleaned)
        if len(facts) >= MAX_KEY_FACTS:
            break
    return facts


def _sanitize_text(value: str) -> str:
    without_controls = _CONTROL_CHARACTERS.sub("", value)
    without_urls = _URL_PATTERN.sub("[link removed]", without_controls)
    return re.sub(r"\s+", " ", without_urls).strip()


def _extension_limitation(item: StoredAttachment) -> str | None:
    allowed_suffixes = _ALLOWED_SUFFIXES.get(item.type)
    if allowed_suffixes is None:
        return None
    suffix = Path(item.safe_filename).suffix.lower()
    if suffix in allowed_suffixes:
        return None
    expected = " or ".join(sorted(allowed_suffixes))
    return f"Only {expected} files are parsed for {item.type.upper()} attachments."
