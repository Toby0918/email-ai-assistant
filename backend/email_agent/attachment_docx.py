"""Bounded DOCX paragraph and table text collection."""

from __future__ import annotations

from typing import Any

from .attachment_text import TextBudget


MAX_DOCX_PARAGRAPHS = 50
MAX_DOCX_TABLES = 5
MAX_DOCX_ROWS_PER_TABLE = 30
MAX_DOCX_CELLS_PER_ROW = 20
MAX_DOCX_PARAGRAPH_CHARACTERS = 1_000
MAX_DOCX_CELL_CHARACTERS = 500
MAX_DOCX_ROW_CHARACTERS = 1_100


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
