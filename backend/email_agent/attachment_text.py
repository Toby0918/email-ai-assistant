"""Bounded text accumulation and privacy-safe display sanitization."""

from __future__ import annotations

import re
from pathlib import Path

from .attachment_fact_safety import (
    MAX_ATTACHMENT_FACT_CHARACTERS,
    MAX_ATTACHMENT_FACTS,
    sanitize_constructed_fact,
)
from .attachment_facts import extract_attachment_facts
from .attachment_model_context import (
    AttachmentAnalysisBundle,
    AttachmentModelCandidate,
    attachment_model_candidate,
)
from .attachment_storage import StoredAttachment


MAX_EXTRACTED_CHARACTERS = 2_000
MAX_XLSX_CELL_CHARACTERS = 1_000
MAX_XLSX_ROW_CHARACTERS = 1_100
MAX_SUMMARY_CHARACTERS = 600
MAX_KEY_FACTS = MAX_ATTACHMENT_FACTS
MAX_KEY_FACT_CHARACTERS = MAX_ATTACHMENT_FACT_CHARACTERS
_DISPLAY_INSIGHT_KEYS = {"filename", "type", "status", "summary", "key_facts", "limitations"}

_CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_NON_WHITESPACE_TOKEN = re.compile(r"\S+")
_URI_MARKER = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*:|www\.)\S", re.IGNORECASE)
_EMAIL_ADDRESS = re.compile(
    r"(?<![\w.+-])[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}(?![\w.-])",
    re.IGNORECASE,
)
_LOCAL_PATH = re.compile(
    r"(?<!\w)(?:[A-Z]:[\\/][^\s]+|\\\\[^\\/\s]+[\\/][^\s]+|~?[\\/]"
    r"(?:[^\\/\s]+[\\/])+[^\s]*)",
    re.IGNORECASE,
)
_LONG_DIGIT_SEQUENCE = re.compile(r"\d(?:[\s(),.+_:/\\-]*\d){6,}")


class TextBudget:
    def __init__(self, limit: int = MAX_EXTRACTED_CHARACTERS) -> None:
        self.limit = limit
        self.parts: list[str] = []
        self.fact_parts: list[str] = []
        self.character_count = 0
        self.fact_character_count = 0
        self.truncated = False

    @property
    def exhausted(self) -> bool:
        return self.character_count >= self.limit

    @property
    def text(self) -> str:
        return "".join(self.parts)

    @property
    def fact_text(self) -> str:
        return "".join(self.fact_parts)

    def add(
        self,
        value: str,
        unit_limit: int,
        separator: str = "\n",
        *,
        fact_value: str | None = None,
    ) -> None:
        if self.exhausted:
            self.truncated = True
            return
        bounded_value = value[:unit_limit]
        self._add_fact_source(
            (fact_value if fact_value is not None else bounded_value)[:unit_limit],
            separator,
        )
        if len(value) > unit_limit:
            self.truncated = True
        safe_value = sanitize_text(bounded_value)
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

    def _add_fact_source(self, value: str, separator: str) -> None:
        if not value or self.fact_character_count >= self.limit:
            return
        prefix = separator if self.fact_parts else ""
        addition = f"{prefix}{_CONTROL_CHARACTERS.sub('', value)}"
        available = self.limit - self.fact_character_count
        bounded = addition[:available]
        self.fact_parts.append(bounded)
        self.fact_character_count += len(bounded)

    def mark_omitted(self) -> None:
        self.truncated = True


def sanitize_text(value: str) -> str:
    without_controls = _CONTROL_CHARACTERS.sub("", value)
    without_urls = _NON_WHITESPACE_TOKEN.sub(_redact_uri_token, without_controls)
    without_emails = _EMAIL_ADDRESS.sub("[email removed]", without_urls)
    without_paths = _LOCAL_PATH.sub("[path removed]", without_emails)
    without_long_numbers = _LONG_DIGIT_SEQUENCE.sub("[number removed]", without_paths)
    return re.sub(r"\s+", " ", without_long_numbers).strip()


def _redact_uri_token(match: re.Match[str]) -> str:
    token = match.group(0)
    if _URI_MARKER.search(token):
        return "[link removed]"
    return token


def collect_xlsx_row(
    collector: TextBudget, sheet_title: str, row: tuple[object, ...]
) -> None:
    """Add one bounded worksheet row to the shared text collector."""
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


def character_limitations(collector: TextBudget) -> list[str]:
    if collector.truncated:
        return ["Character limit reached; remaining text was not parsed."]
    return []


def text_insight(
    item: StoredAttachment,
    source_id: str,
    text: str,
    limitations: list[str],
    label: str,
    metadata_facts: list[str] | None = None,
    *,
    fact_text: str | None = None,
) -> AttachmentAnalysisBundle:
    """Build matching display and private model projections from bounded text."""
    sanitized = sanitize_text(text)
    if not sanitized:
        return metadata_only(item, f"{label} contains no readable text.", metadata_facts)
    bounded = sanitized[:MAX_EXTRACTED_CHARACTERS].rstrip()
    if len(sanitized) > MAX_EXTRACTED_CHARACTERS:
        limitations = [*limitations, "Character limit reached; remaining text was not parsed."]
    facts = extract_attachment_facts(fact_text if fact_text is not None else bounded, metadata_facts)
    display_insight = _insight(
        item,
        "parsed",
        f"{label} content parsed; review structured facts.",
        facts,
        limitations,
    )
    candidate_text = fact_text if fact_text is not None else text
    return AttachmentAnalysisBundle(
        display_insight,
        attachment_model_candidate(source_id, candidate_text),
    )


def metadata_only(
    item: StoredAttachment, limitation: str, facts: list[str] | None = None
) -> AttachmentAnalysisBundle:
    """Return a safe display-only result with no private model candidate."""
    return AttachmentAnalysisBundle(_insight(
        item,
        "metadata_only",
        f"{item.type.upper()} attachment metadata only.",
        facts or [f"Size: {item.byte_size} bytes."],
        [limitation],
    ), None)


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


def valid_worker_bundle(
    value: object,
    item: StoredAttachment,
    source_id: str,
) -> bool:
    """Validate the complete one-shot worker result before accepting private text."""
    if not isinstance(value, AttachmentAnalysisBundle):
        return False
    insight = value.display_insight
    if not isinstance(insight, dict) or set(insight) != _DISPLAY_INSIGHT_KEYS:
        return False
    if insight.get("filename") != item.safe_filename:
        return False
    if insight.get("type") != item.type or insight.get("status") not in {"parsed", "metadata_only"}:
        return False
    if not isinstance(insight.get("summary"), str):
        return False
    for key in ("key_facts", "limitations"):
        entries = insight.get(key)
        if not isinstance(entries, list) or not all(isinstance(entry, str) for entry in entries):
            return False
    candidate = value.model_candidate
    if candidate is None:
        return insight["status"] == "metadata_only"
    return (
        insight["status"] == "parsed"
        and isinstance(candidate, AttachmentModelCandidate)
        and candidate.source_id == source_id
        and isinstance(candidate.text, str)
    )


def extension_limitation(
    item: StoredAttachment,
    allowed_suffixes_by_type: dict[str, set[str]],
) -> str | None:
    allowed_suffixes = allowed_suffixes_by_type.get(item.type)
    if allowed_suffixes is None:
        return None
    suffix = Path(item.safe_filename).suffix.lower()
    if suffix in allowed_suffixes:
        return None
    expected = " or ".join(sorted(allowed_suffixes))
    return f"Only {expected} files are parsed for {item.type.upper()} attachments."
