"""Bounded, display-safe parsing for supported temporary attachments."""

from __future__ import annotations

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
from .attachment_fact_safety import (
    MAX_ATTACHMENT_FACT_CHARACTERS,
    MAX_ATTACHMENT_FACTS,
    sanitize_constructed_fact,
)
from .attachment_facts import extract_attachment_facts
from .attachment_docx import (
    MAX_DOCX_CELLS_PER_ROW,
    MAX_DOCX_ROWS_PER_TABLE,
    collect_docx_text,
)
from .attachment_safety import (
    decoder_failure_limitation,
    enforce_pdf_decoder_limits,
    office_package_limitation,
)
from .attachment_text import MAX_EXTRACTED_CHARACTERS, TextBudget, sanitize_text


MAX_PDF_PAGES = 3
MAX_XLSX_SHEETS = 3
MAX_XLSX_ROWS_PER_SHEET = 30
MAX_PDF_PAGE_CHARACTERS = 1_000
MAX_XLSX_CELL_CHARACTERS = 1_000
MAX_XLSX_ROW_CHARACTERS = 1_100
MAX_OCR_CHARACTERS = 2_000
MAX_IMAGE_PIXELS = 25_000_000
OCR_TIMEOUT_SECONDS = 5
MAX_SUMMARY_CHARACTERS = 600
MAX_KEY_FACTS = MAX_ATTACHMENT_FACTS
MAX_KEY_FACT_CHARACTERS = MAX_ATTACHMENT_FACT_CHARACTERS

_ALLOWED_SUFFIXES = {
    "pdf": {".pdf"},
    "xlsx": {".xlsx"},
    "docx": {".docx"},
    "image": {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"},
}


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
        return _metadata_only(item, decoder_failure_limitation(item.type))


def _parse_pdf(item: StoredAttachment) -> dict[str, object]:
    enforce_pdf_decoder_limits()
    reader = PdfReader(str(item.path), strict=True)
    try:
        collector = TextBudget()
        for page in reader.pages[:MAX_PDF_PAGES]:
            if collector.exhausted:
                collector.mark_omitted()
                break
            collector.add(page.extract_text() or "", MAX_PDF_PAGE_CHARACTERS)
        limitations = _character_limitations(collector)
        if len(reader.pages) > MAX_PDF_PAGES:
            limitations.append("Page limit reached; remaining pages were not parsed.")
        return _text_insight(
            item,
            collector.text,
            limitations,
            "PDF",
            fact_text=collector.fact_text,
        )
    finally:
        reader.close()


def _parse_xlsx(item: StoredAttachment) -> dict[str, object]:
    package_limitation = office_package_limitation(item.path, item.type)
    if package_limitation:
        return _metadata_only(item, package_limitation)
    workbook = load_workbook(item.path, read_only=True, data_only=True, keep_links=False)
    try:
        all_worksheets = workbook.worksheets
        worksheets = all_worksheets[:MAX_XLSX_SHEETS]
        limitations: list[str] = []
        collector = TextBudget()
        for worksheet in worksheets:
            if collector.exhausted:
                collector.mark_omitted()
                break
            for row_number, row in enumerate(worksheet.iter_rows(values_only=True), start=1):
                if row_number > MAX_XLSX_ROWS_PER_SHEET:
                    limitations.append("Row limit reached; remaining rows were not parsed.")
                    break
                if collector.exhausted:
                    collector.mark_omitted()
                    break
                _collect_xlsx_row(collector, str(worksheet.title), row)
                if collector.exhausted and collector.truncated:
                    break
        if len(all_worksheets) > MAX_XLSX_SHEETS:
            limitations.append("Sheet limit reached; remaining sheets were not parsed.")
    finally:
        workbook.close()
    limitations = [*_character_limitations(collector), *limitations]
    return _text_insight(
        item,
        collector.text,
        limitations,
        "XLSX",
        fact_text=collector.fact_text,
    )


def _parse_docx(item: StoredAttachment) -> dict[str, object]:
    package_limitation = office_package_limitation(item.path, item.type)
    if package_limitation:
        return _metadata_only(item, package_limitation)
    document = Document(item.path)
    text, fact_text, limitations = collect_docx_text(document)
    return _text_insight(item, text, limitations, "DOCX", fact_text=fact_text)


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
            collector = TextBudget()
            collector.add(
                pytesseract.image_to_string(image, timeout=OCR_TIMEOUT_SECONDS),
                MAX_OCR_CHARACTERS,
            )
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
        fact_text=collector.fact_text,
    )


def _collect_xlsx_row(
    collector: TextBudget, sheet_title: str, row: tuple[object, ...]
) -> None:
    row_collector = TextBudget(MAX_XLSX_ROW_CHARACTERS)
    row_collector.add(sheet_title, MAX_XLSX_CELL_CHARACTERS, separator="")
    fact_values: list[str] = []
    has_value = False
    for cell_index, value in enumerate(row):
        if value is None:
            continue
        if row_collector.exhausted:
            if any(remaining is not None for remaining in row[cell_index:]):
                row_collector.mark_omitted()
            break
        separator = ": " if not has_value else " | "
        cell_text = str(value)
        row_collector.add(cell_text, MAX_XLSX_CELL_CHARACTERS, separator=separator)
        fact_values.append(cell_text[:MAX_XLSX_CELL_CHARACTERS])
        has_value = True
    if not has_value:
        return
    if row_collector.truncated:
        collector.truncated = True
    collector.add(
        row_collector.text,
        MAX_XLSX_ROW_CHARACTERS,
        fact_value=" | ".join(fact_values),
    )


def _character_limitations(collector: TextBudget) -> list[str]:
    if collector.truncated:
        return ["Character limit reached; remaining text was not parsed."]
    return []


def _text_insight(
    item: StoredAttachment,
    text: str,
    limitations: list[str],
    label: str,
    metadata_facts: list[str] | None = None,
    *,
    fact_text: str | None = None,
) -> dict[str, object]:
    sanitized = sanitize_text(text)
    if not sanitized:
        return _metadata_only(item, f"{label} contains no readable text.", metadata_facts)
    bounded = sanitized[:MAX_EXTRACTED_CHARACTERS].rstrip()
    if len(sanitized) > MAX_EXTRACTED_CHARACTERS:
        limitations = [*limitations, "Character limit reached; remaining text was not parsed."]
    facts = _facts_from_text(fact_text if fact_text is not None else bounded, metadata_facts)
    return _insight(
        item,
        "parsed",
        f"{label} content parsed; review structured facts.",
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
    safe_facts = [
        cleaned
        for fact in facts[:MAX_KEY_FACTS]
        if (cleaned := sanitize_constructed_fact(fact))
    ]
    return {
        "filename": item.safe_filename,
        "type": item.type,
        "status": status,
        "summary": sanitize_text(summary)[:MAX_SUMMARY_CHARACTERS],
        "key_facts": safe_facts,
        "limitations": [sanitize_text(value)[:MAX_KEY_FACT_CHARACTERS] for value in limitations],
    }


def _facts_from_text(text: str, metadata_facts: list[str] | None) -> list[str]:
    return extract_attachment_facts(text, metadata_facts)


def _extension_limitation(item: StoredAttachment) -> str | None:
    allowed_suffixes = _ALLOWED_SUFFIXES.get(item.type)
    if allowed_suffixes is None:
        return None
    suffix = Path(item.safe_filename).suffix.lower()
    if suffix in allowed_suffixes:
        return None
    expected = " or ".join(sorted(allowed_suffixes))
    return f"Only {expected} files are parsed for {item.type.upper()} attachments."
