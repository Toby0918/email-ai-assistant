"""Bounded document and spreadsheet attachment text collection."""

from __future__ import annotations

from typing import Any

from .attachment_model_context import AttachmentAnalysisBundle
from .attachment_safety import enforce_pdf_decoder_limits, office_package_limitation
from .attachment_storage import StoredAttachment
from .attachment_text import (
    TextBudget,
    character_limitations,
    collect_xlsx_row,
    metadata_only,
)


MAX_DOCX_PARAGRAPHS = 50
MAX_DOCX_TABLES = 5
MAX_DOCX_ROWS_PER_TABLE = 30
MAX_DOCX_CELLS_PER_ROW = 20
MAX_DOCX_PARAGRAPH_CHARACTERS = 1_000
MAX_DOCX_CELL_CHARACTERS = 500
MAX_DOCX_ROW_CHARACTERS = 1_100
MAX_PDF_PAGES = 3
MAX_PDF_PAGE_CHARACTERS = 1_000
MAX_XLSX_SHEETS = 3
MAX_XLSX_ROWS_PER_SHEET = 30


def parse_pdf_bundle(
    item: StoredAttachment,
    source_id: str,
    reader_factory: Any,
    text_projector: Any,
) -> AttachmentAnalysisBundle:
    enforce_pdf_decoder_limits()
    reader = reader_factory(str(item.path), strict=True)
    try:
        collector = TextBudget()
        for page in reader.pages[:MAX_PDF_PAGES]:
            if collector.exhausted:
                collector.mark_omitted()
                break
            collector.add(page.extract_text() or "", MAX_PDF_PAGE_CHARACTERS)
        limitations = character_limitations(collector)
        if len(reader.pages) > MAX_PDF_PAGES:
            limitations.append("Page limit reached; remaining pages were not parsed.")
        return text_projector(
            item, source_id, collector.text, limitations, "PDF", fact_text=collector.fact_text
        )
    finally:
        reader.close()


def parse_xlsx_bundle(
    item: StoredAttachment,
    source_id: str,
    workbook_loader: Any,
    text_projector: Any,
) -> AttachmentAnalysisBundle:
    package_limitation = office_package_limitation(item.path, item.type)
    if package_limitation:
        return metadata_only(item, package_limitation)
    workbook = workbook_loader(item.path, read_only=True, data_only=True, keep_links=False)
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
                collect_xlsx_row(collector, str(worksheet.title), row)
                if collector.exhausted and collector.truncated:
                    break
        if len(all_worksheets) > MAX_XLSX_SHEETS:
            limitations.append("Sheet limit reached; remaining sheets were not parsed.")
    finally:
        workbook.close()
    return text_projector(
        item,
        source_id,
        collector.text,
        [*character_limitations(collector), *limitations],
        "XLSX",
        fact_text=collector.fact_text,
    )


def parse_docx_bundle(
    item: StoredAttachment,
    source_id: str,
    document_factory: Any,
    text_projector: Any,
) -> AttachmentAnalysisBundle:
    package_limitation = office_package_limitation(item.path, item.type)
    if package_limitation:
        return metadata_only(item, package_limitation)
    document = document_factory(item.path)
    text, fact_text, limitations = collect_docx_text(document)
    return text_projector(item, source_id, text, limitations, "DOCX", fact_text=fact_text)


def collect_docx_text(document: Any) -> tuple[str, str, list[str]]:
    """Collect bounded paragraph and table text under one character budget."""
    paragraphs = document.paragraphs
    tables = document.tables
    collector = TextBudget()
    structural_limitations: list[str] = []
    for paragraph in paragraphs[:MAX_DOCX_PARAGRAPHS]:
        if collector.exhausted:
            collector.mark_omitted()
            break
        collector.add(paragraph.text, MAX_DOCX_PARAGRAPH_CHARACTERS)
    if len(paragraphs) > MAX_DOCX_PARAGRAPHS:
        structural_limitations.append("Paragraph limit reached; remaining paragraphs were not parsed.")
    _collect_tables(collector, tables, structural_limitations)
    limitations = []
    if collector.truncated:
        limitations.append("Character limit reached; remaining text was not parsed.")
    limitations.extend(dict.fromkeys(structural_limitations))
    return collector.text, collector.fact_text, limitations


def _collect_tables(collector: TextBudget, tables: list[Any], limitations: list[str]) -> None:
    for table in tables[:MAX_DOCX_TABLES]:
        if collector.exhausted:
            collector.mark_omitted()
            break
        rows = table.rows
        for row in rows[:MAX_DOCX_ROWS_PER_TABLE]:
            if collector.exhausted:
                collector.mark_omitted()
                break
            cells = row.cells
            if len(cells) > MAX_DOCX_CELLS_PER_ROW:
                limitations.append("Table cell limit reached; remaining cells were not parsed.")
            _collect_row(collector, cells[:MAX_DOCX_CELLS_PER_ROW])
        if len(rows) > MAX_DOCX_ROWS_PER_TABLE:
            limitations.append("Table row limit reached; remaining rows were not parsed.")
    if len(tables) > MAX_DOCX_TABLES:
        limitations.append("Table limit reached; remaining tables were not parsed.")


def _collect_row(collector: TextBudget, cells: list[Any]) -> None:
    row_collector = TextBudget(MAX_DOCX_ROW_CHARACTERS)
    for cell in cells:
        if row_collector.exhausted:
            row_collector.mark_omitted()
            break
        row_collector.add(str(cell.text), MAX_DOCX_CELL_CHARACTERS, separator=" | ")
    if row_collector.truncated:
        collector.truncated = True
    collector.add(
        row_collector.text,
        MAX_DOCX_ROW_CHARACTERS,
        fact_value=row_collector.fact_text,
    )
