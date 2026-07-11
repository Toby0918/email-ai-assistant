"""Bounded request-intent and acknowledgement classification."""

from __future__ import annotations

import re


_REQUEST_RE = re.compile(
    r"\b(please|could you|need|confirm|provide)\b|"
    r"\b(?:rfq|quote|quotation|pricing|certificate|shipment|sample|invoice|payment|contract|order)\s+request\b|"
    r"\brequest(?:ing|ed)?\s+(?:rfq|quote|quotation|pricing|certificate|shipment|sample|invoice|payment|contract|order)\b|"
    r"请|麻烦|需要|确认|提供",
    re.IGNORECASE,
)
_DIRECT_REQUEST_RE = re.compile(
    r"\b(please|could you|need|provide)\b|请|麻烦|需要|提供",
    re.IGNORECASE,
)
_RECEIPT_EVIDENCE_RE = re.compile(
    r"\b(receipt|received|acknowledged)\b|收到|收悉|回执",
    re.IGNORECASE,
)
_GENERIC_ACKNOWLEDGEMENT_RE = re.compile(r"\b(thanks?|noted)\b|谢谢", re.IGNORECASE)
_NON_REQUEST_DETAIL_RE = re.compile(
    r"\b(is|are|was|were|has|have|had|attached|received|completed|resolved|pending|reference)\b|"
    r"已附|附件|供参考|已收到|已完成|待确认",
    re.IGNORECASE,
)
_TITLE_TOPIC = r"(?:quote|quotation|pricing|certificate|shipment|sample|quantity|invoice|payment|contract|order)"
_COORDINATED_REQUEST_TITLE_RE = re.compile(
    rf"^\s*{_TITLE_TOPIC}(?:\s+(?:and|&)\s+{_TITLE_TOPIC})+\s+requests?\s*$",
    re.IGNORECASE,
)


def has_request_syntax(text: str) -> bool:
    return _REQUEST_RE.search(text) is not None


def has_request_intent(text: str) -> bool:
    if not has_request_syntax(text) or _RECEIPT_EVIDENCE_RE.search(text) is not None:
        return False
    return (
        _DIRECT_REQUEST_RE.search(text) is not None
        or _GENERIC_ACKNOWLEDGEMENT_RE.search(text) is None
    )


def is_non_request_detail(text: str) -> bool:
    return _NON_REQUEST_DETAIL_RE.search(text) is not None


def is_coordinated_request_title(text: str) -> bool:
    return _COORDINATED_REQUEST_TITLE_RE.fullmatch(text) is not None
