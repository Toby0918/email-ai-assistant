"""Language and unsafe-operation predicates for provider-authored prose."""

from __future__ import annotations

import re


_CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
_CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
_AUTO_ACTION_RE = re.compile(
    r"(?:自动|直接|无需人工|系统将).{0,16}(?:发送|回复|删除|归档|移动|转发|支付|签署)|"
    r"\b(?:auto(?:matically)?[- ]?|directly[- ]?|without human (?:review|approval).{0,12})"
    r"(?:send|reply|delete|archive|move|forward|pay|sign)\b|"
    r"\b(?:send|reply|delete|archive|move|forward|pay|sign).{0,12}"
    r"(?:automatically|directly|without human (?:review|approval))\b",
    re.IGNORECASE,
)
_ACTION_CLAIM_RE = re.compile(
    r"(?:已|已经)(?:发送|回复|删除|归档|移动|转发|支付|签署)|"
    r"\b(?:sent|replied|deleted|archived|moved|forwarded|paid|signed)\b",
    re.IGNORECASE,
)
_COMMITMENT_RE = re.compile(
    r"\b(?:i|we)\s+(?:(?:will|shall)\s+(?:ship|dispatch|deliver|fulfil|fulfill|pay)|"
    r"(?:will\s+)?(?:guarantee|commit(?:\s+to)?|accept|agree(?:\s+to)?).{0,32}"
    r"(?:price|quote|delivery|payment|contract|terms?|quality|warranty|legal|liability))\b|"
    r"(?:我方|我们|我).{0,12}(?:保证|承诺|接受|同意|会|将).{0,20}"
    r"(?:发货|交付|履行|付款|支付|价格|报价|合同|条款|质量|保修|法律|责任|赔偿)",
    re.IGNORECASE,
)
_CLAUSE_RE = re.compile(r"[^;；.!?。！？\n]+")
_PASSIVE_STATUS_RE = re.compile(
    r"\b(?:is|are|was|were|has been|have been)\s+"
    r"(?:now\s+)?(?:guaranteed|confirmed|final|accepted|approved|agreed|scheduled)\b|"
    r"(?:已|已经|现已)(?:保证|确认|最终确定|接受|批准|同意|安排)",
    re.IGNORECASE,
)
_SAFE_PASSIVE_CONTEXT_RE = re.compile(
    r"\b(?:not|never|whether|if|pending|unconfirmed)\b|"
    r"\b(?:review|check|verify|ask(?:s|ed)?)\s+(?:whether|if)\b|"
    r"(?:尚未|并未|没有|未被|是否|能否|待确认|待审核|请(?:审核|检查|核实|复核))",
    re.IGNORECASE,
)
_CONSEQUENTIAL_TERMS = {
    "price": re.compile(r"\b(price|quote|quotation|cost|discount)\b|价格|报价|折扣", re.I),
    "delivery": re.compile(r"\b(deliver|delivery|shipment|dispatch|eta)\b|交付|交期|发货", re.I),
    "payment": re.compile(r"\b(pay|payment|invoice)\b|付款|支付|发票", re.I),
    "contract": re.compile(r"\b(contract|terms?)\b|合同|条款", re.I),
    "quality": re.compile(r"\b(quality|warranty|specification)\b|质量|保修|规格", re.I),
    "legal": re.compile(r"\b(legal|liability|liable|indemnity)\b|法律|责任|赔偿", re.I),
}
_HTML_RE = re.compile(r"<\s*/?\s*[A-Z][^>]*>", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]\r\n]*\]\([^\)\r\n]+\)")
_URI_RE = re.compile(
    r"(?<![\w.+-])(?P<scheme>[A-Z][A-Z0-9+.-]{1,31}):[^\s<>{}\[\]]+",
    re.IGNORECASE,
)
_WEB_ADDRESS_RE = re.compile(
    r"(?<![@\w.-])(?:www\.)?(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+"
    r"[A-Z]{2,63}(?::\d{1,5})?(?:/[^\s<>{}\[\]]*)?",
    re.IGNORECASE,
)
_TOOL_INSTRUCTION_RE = re.compile(
    r"(?:执行|运行|调用|点击|打开|访问).{0,8}(?:命令|脚本|工具|链接)|"
    r"\b(?:run|execute|invoke|call|open|click|visit)\s+(?:the\s+)?"
    r"(?:command|script|tool|shell|powershell|cmd|link)\b",
    re.IGNORECASE,
)
_BUSINESS_URI_LABELS = {
    "amount", "deadline", "due", "invoice", "part", "po", "price", "qty",
    "quantity", "rfq", "size", "total", "usd", "eur", "cny", "rmb",
}
_COMMON_ENGLISH_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "best", "by", "can", "check",
    "confirm", "dear", "details", "dispatched", "email", "for", "friday", "from",
    "has", "have", "i", "in", "information", "is", "it", "of", "on", "or", "order",
    "our", "please", "po", "provide", "received", "regarding", "request", "review",
    "shipment", "thank", "thanks", "that", "the", "this", "to", "update", "verify",
    "we", "will", "with", "you", "your", "acknowledged",
}
_NON_ENGLISH_MARKERS = {
    "asunto", "bonjour", "demande", "examinerons", "gracias", "hola", "información",
    "informations", "merci", "nous", "objet", "revisaremos", "solicitud", "votre",
}
_DISCLOSURE_VERBS = (
    "disclose", "reveal", "share", "send", "provide", "披露", "透露", "分享",
    "发送", "发给", "提供", "提交", "发来",
)
_SECRET_TERMS = (
    "credential", "password", "passcode", "api key", "api-key", "api_key",
    "authorization header", "authorization value", "cookie", "access token",
    "auth token", "session token", "session secret", "session id", "凭据", "密码",
    "口令", "api 密钥", "api密钥", "授权头", "授权值", "访问令牌", "认证令牌",
    "会话令牌", "会话密钥", "会话 id",
)
_BENIGN_SECRET_OBJECT_RE = re.compile(
    r"password[\s_-]+reset[\s_-]+(?:status|policy|schedule)|"
    r"api[\s_-]*key[\s_-]+rotation[\s_-]+(?:policy|status|schedule)|"
    r"(?:(?:access|auth|session)[\s_-]+)?token[\s_-]+"
    r"(?:expiry|expiration|expired(?:[\s_-]+status)?)|"
    r"cookie[\s_-]+(?:issue|policy)|密码重置(?:状态|策略|计划|进度)?|"
    r"api\s*密钥轮换(?:策略|状态|计划|日程|进度)?|"
    r"(?:访问|认证|会话)?令牌(?:过期|到期)(?:状态|时间|日期)?|cookie(?:问题|策略|状态)",
    re.IGNORECASE,
)


def has_chinese(value: str) -> bool:
    return bool(_CHINESE_RE.search(value))


def looks_english(subject: str, body: str) -> bool:
    text_tokens = re.findall(r"[A-Za-zÀ-ÿ]+", (subject + "\n" + body).lower())
    body_tokens = re.findall(r"[A-Za-zÀ-ÿ]+", body.lower())
    if _CJK_RE.search(subject + "\n" + body):
        return False
    if any(token in _NON_ENGLISH_MARKERS for token in text_tokens):
        return False
    # Short business acknowledgements need one hit; longer prose needs 2, capped at 3.
    required_hits = 1 if len(body_tokens) <= 3 else min(3, 2 + len(body_tokens) // 12)
    return sum(token in _COMMON_ENGLISH_WORDS for token in body_tokens) >= required_hits


def is_security_disclosure_request(value: str) -> bool:
    for segment in re.split(r"[.!?。！？;\n]+", value.lower()):
        candidate = _BENIGN_SECRET_OBJECT_RE.sub("", segment)
        if any(word in candidate for word in _DISCLOSURE_VERBS) and any(
            word in candidate for word in _SECRET_TERMS
        ):
            return True
    return False


def has_unsafe_operation(value: str) -> bool:
    return bool(_AUTO_ACTION_RE.search(value) or _ACTION_CLAIM_RE.search(value))


def has_unconditional_commitment(value: str) -> bool:
    return bool(_COMMITMENT_RE.search(value) or passive_commitment_categories(value))


def passive_commitment_categories(value: str) -> frozenset[str]:
    """Return consequential categories asserted as settled in passive voice."""
    categories: set[str] = set()
    for clause in _CLAUSE_RE.findall(value):
        if "?" in clause or "？" in clause or _SAFE_PASSIVE_CONTEXT_RE.search(clause):
            continue
        if not _PASSIVE_STATUS_RE.search(clause):
            continue
        categories.update(
            name for name, pattern in _CONSEQUENTIAL_TERMS.items() if pattern.search(clause)
        )
    return frozenset(categories)


def is_safe_model_text(*values: object) -> bool:
    """Apply the reusable fail-closed policy to provider-authored text."""
    for value in values:
        for text in _text_leaves(value):
            if (
                _contains_link_or_markup(text)
                or _TOOL_INSTRUCTION_RE.search(text)
                or has_unsafe_operation(text)
                or has_unconditional_commitment(text)
            ):
                return False
    return True


def _text_leaves(value: object):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _text_leaves(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _text_leaves(child)


def _contains_link_or_markup(value: str) -> bool:
    if _HTML_RE.search(value) or _MARKDOWN_LINK_RE.search(value) or _WEB_ADDRESS_RE.search(value):
        return True
    for match in _URI_RE.finditer(value):
        scheme = match.group("scheme").casefold()
        if scheme not in _BUSINESS_URI_LABELS or match.group(0).startswith(f"{scheme}://"):
            return True
    return False


def validate_public_language(value: dict[str, object]) -> None:
    brief = value["decision_brief"]
    required = [value["summary"], value["priority_reason"], brief["one_line_conclusion"],
                brief["requested_outcome"], brief["reply_recommendation"]["reason"]]
    required += [item["step"] for item in brief["next_steps"]] + brief["must_check"] + brief["missing_info"]
    timeline = value["conversation_timeline"]
    required += [timeline["previous_context"], timeline["status_reason"]]
    required += [item["item"] for item in timeline["open_items"]]
    required += [item[field] for item in value["risk_flags"] for field in ("evidence", "recommendation")]
    required += [item["description"] for item in value["suggested_actions"]] + value["reply_draft"]["review_reasons"]
    if any(item and not has_chinese(item) for item in required):
        raise ValueError("Analysis prose must be Chinese.")
    draft = value["reply_draft"]
    if has_chinese(draft["subject"]) or has_chinese(draft["body"]):
        raise ValueError("External reply draft must be English.")
