"""Finite local bridge for grounded Chinese claims over English source text."""

from __future__ import annotations

import re
import unicodedata
from typing import Pattern

_ALLOWED_POINTERS = frozenset({
    "/analysis/summary",
    "/analysis/priority_reason",
})
_CLAUSE_RE = re.compile(r"[^.!?;\n。！？；\u0085\u2028\u2029]+")
_NONCURRENT_PREFIX_RE = re.compile(
    r"^\s*(?:if|whether|unless|when|example|for\s+reference|reference|"
    r"report|history|quoted)\b|"
    r"^\s*(?:如果|若|是否|除非|当|例如|举例|仅供参考|供参考|参考|报告|历史|引用)",
    re.IGNORECASE,
)
_BLOCKED_CONTEXT_RE = re.compile(
    r"\b(?:not|never|no|without|cannot|can't|unable|"
    r"refus(?:e|ed|es|ing)|reject(?:ed|s|ing)?|cancel(?:led|ed|s|ing|ling)?|"
    r"withdrawn|withdrew|withdraw(?:s|ing)?|declin(?:e|ed|es|ing)|"
    r"completed|resolved|closed|archived|finished|fulfilled|done)\b|"
    r"(?:不|未|无法|不能|不可|未能|取消|撤回|拒绝|已拒绝|"
    r"已撤回|已取消|已?完成|已?解决|已?关闭|已归档)",
    re.IGNORECASE,
)
_NEGATED_REQUEST_RE = re.compile(
    r"\b(?:(?:do|does|did|is|are|was|were|will|would|should|could|has|have|had)"
    r"\s+(?:not\s+)?|(?:don|doesn|didn|isn|aren|wasn|weren|won|wouldn|"
    r"shouldn|couldn|hasn|haven|hadn|can)['’]t\s+)"
    r"(?:request(?:s|ed|ing)?|ask(?:s|ed|ing)?)\b",
    re.IGNORECASE,
)


def _phrase(pattern: str) -> Pattern[str]:
    return re.compile(pattern, re.IGNORECASE)


_ACTIVE_REQUESTER = (
    r"(?:(?:the\s+)?(?:customer|sender|recipient|supplier|buyer|client|partner)"
    r"\s+(?:requests|asks)|(?:they|we|i)\s+(?:request|ask))"
)
_ZH_REQUESTER = r"(?:对方|客户|供应商|发件方|收件方|买方|合作方|我们|我)(?:请求|要求|询问)"
_GAP = r"[^,，:：.!?;。！？；\r\n]"


def _role_request(tail: str) -> Pattern[str]:
    return _phrase(rf"^\s*{_ACTIVE_REQUESTER}\s+{tail}")


def _zh_role_request(tail: str) -> Pattern[str]:
    return _phrase(rf"^\s*{_ZH_REQUESTER}{tail}")


_TEMPLATE_CODES = {
    "邮件请求人工核查当前事项。": "review_request",
    "邮件请求确认当前处理状态。": "status_confirmation",
    "邮件请求确认交付或发货安排。": "delivery_confirmation",
    "邮件请求提供或确认报价信息。": "quote_request",
    "邮件请求提供或核查相关文件。": "document_request",
    "邮件报告质量或包装异常，需要人工核查。": "quality_issue",
    "邮件询问付款或发票事项。": "payment_inquiry",
    "邮件包含包装或标签要求，需要人工核查。": "packaging_instruction",
    "邮件表达了紧急处理需求。": "urgent_request",
}
_NORMALIZED_TEMPLATE_CODES = {
    unicodedata.normalize("NFKC", template): code
    for template, code in _TEMPLATE_CODES.items()
}

# Each entry is a finite directional phrase contract. Bounded gaps are part of
# the contract; independent terms elsewhere in a clause are not authority.
_CODE_PHRASES: dict[str, tuple[Pattern[str], ...]] = {
    "review_request": (
        _phrase(rf"^\s*(?:please\s+)?(?:review|check|verify|inspect)\b{_GAP}{{0,24}}\b(?:packaging|document|file|details?|request|matter|item)\b"),
        _role_request(r"(?:(?:an?\s+|the\s+)?(?:packaging|document|file|details?|request|matter|item)\s+(?:review|check|verification|inspection)|to\s+(?:review|check|verify|inspect)\s+(?:the\s+)?(?:packaging|document|file|details?|request|matter|item))\b"),
        _phrase(rf"^\s*请(?:核查|检查|审核|复核){_GAP}{{0,16}}(?:包装|文件|详情|请求|事项)"),
        _zh_role_request(rf"(?:核查|检查|审核|复核){_GAP}{{0,12}}(?:包装|文件|详情|请求|事项)"),
    ),
    "status_confirmation": (
        _phrase(rf"^\s*(?:please\s+)?(?:confirm|check|verify|update)\b{_GAP}{{0,20}}\b(?:status|progress|state)\b"),
        _role_request(r"(?:(?:confirmation|review|check|update)\s+(?:of\s+)?(?:the\s+)?(?:current\s+)?(?:status|progress|state)|to\s+(?:confirm|check|verify|update)\s+(?:the\s+)?(?:current\s+)?(?:status|progress|state))\b"),
        _phrase(rf"^\s*请(?:确认|核查|检查|更新){_GAP}{{0,12}}(?:状态|进度)"),
        _zh_role_request(rf"(?:确认|核查|检查|更新){_GAP}{{0,12}}(?:状态|进度)"),
    ),
    "delivery_confirmation": (
        _phrase(rf"^\s*(?:please\s+)?(?:confirm|check|verify|update)\b{_GAP}{{0,24}}\b(?:delivery|shipment|shipping|dispatch|eta)\b"),
        _role_request(r"(?:(?:confirmation|review|check|update)\s+(?:of\s+)?(?:the\s+)?(?:delivery|shipment|shipping|dispatch|eta)(?:\s+schedule)?|to\s+(?:confirm|check|verify|update)\s+(?:the\s+)?(?:delivery|shipment|shipping|dispatch|eta))\b"),
        _phrase(rf"^\s*请(?:确认|核查|检查|更新){_GAP}{{0,12}}(?:交付|交期|发货|出货)"),
        _zh_role_request(rf"(?:确认|核查|检查|更新){_GAP}{{0,12}}(?:交付|交期|发货|出货)"),
    ),
    "quote_request": (
        _phrase(rf"^\s*(?:please\s+)?(?:provide|send|share|confirm)\b{_GAP}{{0,24}}\b(?:quote|quotation|pricing|price)\b"),
        _role_request(r"(?:(?:an?\s+|the\s+)?(?:quote|quotation|pricing|price)|to\s+(?:provide|send|share|confirm)\s+(?:an?\s+|the\s+)?(?:quote|quotation|pricing|price))\b"),
        _phrase(rf"^\s*请(?:提供|发送|分享|确认)?{_GAP}{{0,12}}(?:报价|询价|价格)"),
        _zh_role_request(rf"(?:提供|发送|分享|确认)?{_GAP}{{0,12}}(?:报价|询价|价格)"),
    ),
    "document_request": (
        _phrase(rf"^\s*(?:please\s+)?(?:provide|send|share|attach|review|check|verify)\b{_GAP}{{0,24}}\b(?:document|file|certificate|report|drawing|packing\s+list)\b"),
        _role_request(r"(?:(?:for\s+)?(?:the\s+)?(?:inspection\s+)?(?:document|file|certificate|report|drawing|packing\s+list)|to\s+(?:provide|send|share|attach|review|check|verify)\s+(?:the\s+)?(?:document|file|certificate|report|drawing|packing\s+list))\b"),
        _phrase(rf"^\s*请(?:提供|发送|分享|附上|核查|检查|审核){_GAP}{{0,12}}(?:文件|证书|报告|图纸|装箱单)"),
        _zh_role_request(rf"(?:提供|发送|分享|附上|核查|检查|审核){_GAP}{{0,12}}(?:文件|证书|报告|图纸|装箱单)"),
    ),
    "quality_issue": (
        _phrase(rf"^\s*(?:please\s+)?(?:review|check|verify|inspect)\b{_GAP}{{0,24}}\b(?:damaged|defective|broken|torn|leaking|incorrect|quality|packaging|package|carton|label|product|component)\b"),
        _role_request(r"(?:(?:an?\s+|the\s+)?(?:review|inspection)\s+of\s+(?:the\s+)?(?:damaged|defective|broken|torn|leaking|incorrect)?\s*(?:packaging|package|carton|label|product|component)|to\s+(?:review|check|verify|inspect)\s+(?:the\s+)?(?:damaged|defective|broken|torn|leaking|incorrect)?\s*(?:packaging|package|carton|label|product|component))\b"),
        _phrase(r"^\s*(?:the\s+)?(?:packaging|package|packing|carton|label|product|component)\s+(?:is|appears)\s+(?:visibly\s+)?(?:damaged|defective|broken|torn|leaking|incorrect)\b"),
        _phrase(rf"^\s*请(?:核查|检查|审核|复核){_GAP}{{0,12}}(?:质量|异常|破损|损坏|缺陷|包装|纸箱|标签|产品|部件)"),
        _zh_role_request(rf"(?:核查|检查|审核|复核){_GAP}{{0,12}}(?:质量|异常|破损|损坏|缺陷|包装|纸箱|标签|产品|部件)"),
    ),
    "payment_inquiry": (
        _phrase(rf"^\s*(?:please\s+)?(?:confirm|check|review|provide|send)\b{_GAP}{{0,24}}\b(?:payment|invoice|billing)\b"),
        _role_request(r"(?:(?:about|regarding)\s+(?:the\s+)?(?:payment|invoice|billing)(?:\s+(?:payment|issue|question))?|to\s+(?:confirm|check|review|provide|send)\s+(?:the\s+)?(?:payment|invoice|billing))\b"),
        _phrase(rf"^\s*请(?:询问|咨询|确认|核查|检查){_GAP}{{0,12}}(?:付款|支付|发票|账单)"),
        _zh_role_request(rf"(?:询问|咨询|确认|核查|检查){_GAP}{{0,12}}(?:付款|支付|发票|账单)"),
    ),
    "packaging_instruction": (
        _phrase(rf"^\s*(?:please\s+)?(?:place|position|apply|attach|stick|put|mark)\b{_GAP}{{0,28}}\b(?:packaging|packing|package|carton|label)\b"),
        _role_request(r"(?:(?:the\s+)?(?:label|packaging|packing|carton)\s+(?:placement|position|requirement|instruction)|to\s+(?:place|position|apply|attach|stick|put|mark)\s+(?:the\s+)?(?:label|packaging|packing|carton))\b"),
        _phrase(rf"^请(?:放置|定位|贴|附上|标记){_GAP}{{0,16}}(?:包装|装箱|纸箱|标签)"),
        _zh_role_request(rf"(?:放置|定位|贴|附上|标记){_GAP}{{0,12}}(?:包装|装箱|纸箱|标签)"),
    ),
    "urgent_request": (
        _phrase(rf"^\s*(?:please\s+)?(?:(?:urgent|urgently|asap|immediately)\s+)?(?:support|handle|reply|respond|review|confirm|ship)\b{_GAP}{{0,20}}\b(?:urgent|urgently|asap|immediately|dispatch|delivery|issue|request)\b"),
        _role_request(r"(?:an?\s+|the\s+)?(?:urgent|immediate|asap|high\s+priority)\s+(?:dispatch|delivery|review|support|action|response)\b"),
        _phrase(rf"^\s*请(?:紧急|尽快|立即|优先)?{_GAP}{{0,12}}(?:支持|处理|回复|发货|交付|核查|确认)"),
        _zh_role_request(rf"(?:紧急|尽快|立即|优先){_GAP}{{0,12}}(?:支持|处理|回复|发货|交付|核查|确认)"),
    ),
}


def render_cross_language_claim_contract() -> str:
    """Return the exact public templates shared by prompt and validator."""
    return "|".join(_TEMPLATE_CODES)


def cross_language_claim_is_grounded(
    text: str,
    grounding_text: str,
    *,
    pointer: str,
) -> bool:
    """Return only whether a fixed template has a directional source phrase."""
    if pointer not in _ALLOWED_POINTERS or type(text) is not str:
        return False
    template = unicodedata.normalize("NFKC", text).strip()
    code = _NORMALIZED_TEMPLATE_CODES.get(template)
    if code is None or type(grounding_text) is not str:
        return False
    normalized_source = unicodedata.normalize("NFKC", grounding_text).casefold()
    if _has_unsafe_unicode_obfuscation(normalized_source):
        return False
    return any(
        _clause_supports(code, clause.group(0))
        for clause in _CLAUSE_RE.finditer(normalized_source)
    )


def _clause_supports(code: str, clause: str) -> bool:
    if (
        _NONCURRENT_PREFIX_RE.search(clause)
        or _BLOCKED_CONTEXT_RE.search(clause)
        or _NEGATED_REQUEST_RE.search(clause)
    ):
        return False
    return any(pattern.search(clause) for pattern in _CODE_PHRASES[code])


def _has_unsafe_unicode_obfuscation(value: str) -> bool:
    if any(unicodedata.category(char) in {"Cf", "Mn", "Me"} for char in value):
        return True
    has_ascii_latin = any("a" <= char <= "z" for char in value)
    has_confusable_script = any(
        "GREEK" in unicodedata.name(char, "")
        or "CYRILLIC" in unicodedata.name(char, "")
        for char in value
    )
    return has_ascii_latin and has_confusable_script
