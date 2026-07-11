"""Bounded request-intent and acknowledgement classification."""

from __future__ import annotations

import re


_TITLE_TOPIC = r"(?:quote|quotation|pricing|certificate|shipment|sample|quantity|invoice|payment|contract|order)"
_ZH_TITLE_TOPIC = r"(?:报价|询价|证书|认证|发货|交期|样品|数量|发票|付款|合同|订单)"
_REQUEST_RE = re.compile(
    r"\b(please|could you|need|confirm|provide)\b|"
    r"\b(?:rfq|quote|quotation|pricing|certificate|shipment|sample|invoice|payment|contract|order)\s+request\b|"
    r"\brequest(?:ing|ed)?\s+(?:rfq|quote|quotation|pricing|certificate|shipment|sample|invoice|payment|contract|order)\b|"
    rf"{_ZH_TITLE_TOPIC}(?:(?:、|，|,|和|及|以及){_ZH_TITLE_TOPIC})*(?:请求|需求)|"
    r"请(?!求)|麻烦|需要|确认|提供",
    re.IGNORECASE,
)
_DIRECT_REQUEST_RE = re.compile(
    r"\b(please|could you|need|provide)\b|请(?!求)|麻烦|需要|提供",
    re.IGNORECASE,
)
_RECEIPT_EVIDENCE_RE = re.compile(
    r"\b(receipt|received|acknowledged)\b|"
    r"\brequests?\b(?:\s+\w+){0,4}\s+attached\b|"
    r"收到|收悉|回执|请求.{0,12}(?:已附|随附|附件)",
    re.IGNORECASE,
)
_GENERIC_ACKNOWLEDGEMENT_RE = re.compile(r"\b(thanks?|noted)\b|谢谢", re.IGNORECASE)
_TRANSMITTAL_RE = re.compile(
    r"\b(?:please\s+)?(?:find|see)\s+(?:the\s+)?attached\b|"
    r"\b(?:attached|enclosed)\b.{0,80}\bfor\s+(?:your\s+)?reference\b|"
    r"请(?:查收|查看|参见).{0,80}(?:附件|随附)|(?:附件|随附).{0,80}供参考",
    re.IGNORECASE,
)
_DECLARATIVE_EVIDENCE_RE = re.compile(
    r"^\s*(?:i|we)\s+(?:hereby\s+)?confirm\b|"
    rf"\b(?:the\s+)?requested\s+{_TITLE_TOPIC}\b.{{0,80}}"
    r"\b(?:is|are|was|were)\s+(?:attached|enclosed)\b",
    re.IGNORECASE,
)
_NON_REQUEST_DETAIL_RE = re.compile(
    r"\b(is|are|was|were|has|have|had|attached|received|completed|resolved|pending|reference)\b|"
    r"已附|附件|供参考|已收到|已完成|待确认",
    re.IGNORECASE,
)
_COORDINATED_REQUEST_TITLE_RE = re.compile(
    rf"^\s*{_TITLE_TOPIC}(?:(?:\s*,\s*|\s+(?:and|&)\s+){_TITLE_TOPIC})+\s+requests?\s*$",
    re.IGNORECASE,
)
_ZH_COORDINATED_REQUEST_TITLE_RE = re.compile(
    rf"^\s*{_ZH_TITLE_TOPIC}(?:(?:、|，|,|和|及|以及){_ZH_TITLE_TOPIC})+(?:请求|需求)\s*$",
    re.IGNORECASE,
)


def has_request_syntax(text: str) -> bool:
    return _REQUEST_RE.search(text) is not None


def has_request_intent(text: str) -> bool:
    if (
        not has_request_syntax(text)
        or _RECEIPT_EVIDENCE_RE.search(text) is not None
        or _TRANSMITTAL_RE.search(text) is not None
        or _DECLARATIVE_EVIDENCE_RE.search(text) is not None
    ):
        return False
    return (
        _DIRECT_REQUEST_RE.search(text) is not None
        or _GENERIC_ACKNOWLEDGEMENT_RE.search(text) is None
    )


def is_non_request_detail(text: str) -> bool:
    return _NON_REQUEST_DETAIL_RE.search(text) is not None


def is_coordinated_request_title(text: str) -> bool:
    return any(
        pattern.fullmatch(text) is not None
        for pattern in (_COORDINATED_REQUEST_TITLE_RE, _ZH_COORDINATED_REQUEST_TITLE_RE)
    )
