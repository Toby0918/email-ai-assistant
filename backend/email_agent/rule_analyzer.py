"""Local rule-based analyzer for the first version."""

from __future__ import annotations

from typing import Any

from .analysis_schema import validate_analysis_result


DELIVERY_KEYWORDS = ("delivery", "shipment", "order", "eta", "交期", "发货", "物流", "到货", "订单", "交付")
PAYMENT_KEYWORDS = ("payment", "invoice", "remittance", "overdue", "付款", "发票", "汇款", "逾期", "账期", "对账")
CONTRACT_KEYWORDS = ("contract", "agreement", "terms", "signing", "合同", "协议", "条款", "签署")
QUALITY_KEYWORDS = ("complaint", "quality", "defective", "damaged", "投诉", "质量", "不良", "损坏", "缺陷")
QUOTE_KEYWORDS = ("quote", "quotation", "rfq", "price", "报价", "询价", "价格")
INTERNAL_KEYWORDS = ("internal", "internally", "approval", "approve", "reviewer", "内部", "审批", "复核", "审核")
MARKETING_KEYWORDS = ("marketing", "promotion", "advertisement", "exhibition", "trade show", "brochure", "展会", "推广", "广告")
MEETING_KEYWORDS = ("meeting", "calendar", "invitation", "invite", "zoom", "会议", "邀请", "日程")
BOOKING_KEYWORDS = (
    "booking",
    "tracking number",
    "tracking",
    "original fe",
    "forwarder",
    "logistics",
    "air freight",
    "sea freight",
    "订舱",
    "货代",
    "追踪",
    "物流",
)

PRIORITY_LABELS = {"urgent": "紧急", "high": "高", "normal": "普通", "low": "低"}

RISK_LABELS = {
    "payment_risk": "付款风险",
    "delivery_risk": "交付/物流风险",
    "contract_risk": "合同风险",
    "quality_risk": "质量风险",
    "security_risk": "安全风险",
    "commitment_risk": "承诺风险",
    "prompt_injection_risk": "提示注入风险",
}


def build_rule_based_analysis(subject: str, sender: str, clean_body: str) -> dict[str, Any]:
    # Deterministic local output keeps the first version usable without live AI.
    text = f"{subject}\n{sender}\n{clean_body}".lower()
    risks = _risk_flags(text)
    category = _category(text, risks)
    priority = _priority(text, risks)
    summary = _summary(category, risks, text)
    actions = _suggested_actions(category, risks, text)
    result = {
        "summary": summary,
        "priority": priority,
        "priority_reason": _priority_reason(priority, risks),
        "category": category,
        "tags": _tags(category, risks),
        "risk_flags": risks,
        "suggested_actions": actions,
        "reply_draft": _reply_draft(subject, category, actions[0]["type"], text),
    }
    return validate_analysis_result(result)


def _category(text: str, risks: list[dict[str, str]]) -> str:
    if _has_risk(risks, "prompt_injection_risk"):
        return "unknown"
    if _contains(text, *QUALITY_KEYWORDS):
        return "complaint"
    if _contains(text, *CONTRACT_KEYWORDS):
        return "contract"
    if _contains(text, *INTERNAL_KEYWORDS):
        return "internal"
    if _is_booking_context(text):
        return "order_followup"
    if _is_meeting_context(text):
        return "customer_inquiry"
    if _contains(text, *QUOTE_KEYWORDS):
        return "customer_inquiry"
    if _contains(text, *DELIVERY_KEYWORDS):
        return "order_followup"
    if _contains(text, *PAYMENT_KEYWORDS):
        return "payment"
    if _contains(text, *MARKETING_KEYWORDS):
        return "marketing"
    return "customer_inquiry"


def _priority(text: str, risks: list[dict[str, str]]) -> str:
    if _contains(text, "urgent", "asap") or any(item["level"] == "high" for item in risks):
        return "high"
    return "normal"


def _risk_flags(text: str) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if _contains(text, "ignore previous", "system prompt", "reveal"):
        risks.append(_risk("prompt_injection_risk", "high", "邮件要求忽略系统规则或泄露内部提示。"))
    if _contains(text, *PAYMENT_KEYWORDS):
        level = "high" if _contains(text, "overdue", "逾期") else "medium"
        risks.append(_risk("payment_risk", level, "邮件提到付款、发票或汇款状态。"))
    if _contains(text, *DELIVERY_KEYWORDS) or _is_booking_context(text):
        risks.append(_risk("delivery_risk", "low", "邮件提到交付、发货或物流状态。"))
    if _contains(text, *CONTRACT_KEYWORDS):
        risks.append(_risk("contract_risk", "medium", "邮件提到合同、条款或签署事项。"))
    if _contains(text, *QUALITY_KEYWORDS):
        risks.append(_risk("quality_risk", "high", "邮件提到质量投诉或异常。"))
    if _contains(text, *QUOTE_KEYWORDS):
        risks.append(_risk("commitment_risk", "medium", "邮件要求确认价格、报价或交期。"))
    return risks


def _risk(kind: str, level: str, evidence: str) -> dict[str, str]:
    return {
        "type": kind,
        "level": level,
        "evidence": evidence,
        "recommendation": "回复前请人工复核上下文，避免未经确认的承诺。",
    }


def _summary(category: str, risks: list[dict[str, str]], text: str) -> str:
    if _has_risk(risks, "prompt_injection_risk"):
        return "这封邮件包含疑似提示注入内容，需要忽略正文中的系统级指令并人工复核。"
    if category == "complaint":
        return "这封邮件主要关于质量投诉或异常，需要升级给负责人处理。"
    if category == "contract":
        return "这封邮件主要关于合同、条款或签署事项，需要负责人复核后回复。"
    if category == "internal":
        return "这封邮件主要是内部审核或审批事项，需要先完成内部确认。"
    if category == "order_followup":
        if _is_booking_context(text):
            return "这封邮件主要关于订舱、物流或追踪信息，需要核查状态后回复。"
        return "这封邮件主要关于交付或发货进度，需要核查状态后回复。"
    if category == "payment":
        return "这封邮件主要关于付款、发票或汇款状态，需要核对后回复。"
    if category == "customer_inquiry":
        if _is_meeting_context(text):
            return "这封邮件主要关于会议或日程邀请，需要确认邀请有效性和是否参加。"
        if _contains(text, *QUOTE_KEYWORDS):
            return "这封邮件主要关于报价或询价，需要准备信息并人工审核。"
        return "这封邮件主要是客户询问，需要人工查看后准备谨慎回复。"
    if category == "marketing":
        return "这封邮件主要是营销或参考资料，通常无需业务回复。"
    return "这封邮件需要人工查看后准备谨慎回复。"


def _priority_reason(priority: str, risks: list[dict[str, str]]) -> str:
    if risks:
        return f"优先级为{_priority_label(priority)}，因为检测到{_risk_label(risks[0]['type'])}。"
    return "优先级为普通，因为未检测到高风险信号。"


def _priority_label(priority: str) -> str:
    return PRIORITY_LABELS.get(priority, priority)


def _risk_label(risk_type: str) -> str:
    return RISK_LABELS.get(risk_type, risk_type)


def _tags(category: str, risks: list[dict[str, str]]) -> list[str]:
    return [category, *[item["type"] for item in risks]]


def _suggested_actions(category: str, risks: list[dict[str, str]], text: str) -> list[dict[str, str]]:
    action_type = _action_type(category, risks, text)
    return [{
        "type": action_type,
        "description": _action_description(action_type, category, text),
        "owner_hint": "account_owner",
        "due_hint": "today",
    }]


def _reply_draft(subject: str, category: str, action_type: str, text: str) -> dict[str, Any]:
    return {
        "subject": _draft_subject(subject),
        "body": (
            "Hello,\n\n"
            "Thank you for your email.\n"
            f"{_draft_context_line(action_type, category, text)}\n"
            f"{_draft_next_step(action_type, category, text)}\n\n"
            "Best regards"
        ),
        "needs_human_review": True,
        "review_reasons": ["第一版回复草稿必须人工审核后再使用。"],
    }


def _draft_subject(subject: str) -> str:
    clean_subject = " ".join(subject.split()).strip()
    if clean_subject and not _contains_chinese_char(clean_subject):
        return f"Re: {clean_subject}"
    return "Re: your email"


def _contains_chinese_char(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _contains(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_meeting_context(text: str) -> bool:
    return _contains(text, *MEETING_KEYWORDS)


def _is_booking_context(text: str) -> bool:
    return _contains(text, *BOOKING_KEYWORDS)


def _has_risk(risks: list[dict[str, str]], risk_type: str) -> bool:
    return any(item["type"] == risk_type for item in risks)


def _action_type(category: str, risks: list[dict[str, str]], text: str) -> str:
    if _has_risk(risks, "prompt_injection_risk") or _has_risk(risks, "quality_risk"):
        return "escalate"
    if _is_meeting_context(text):
        return "confirm"
    if category == "order_followup":
        return "check_delivery"
    if category in {"payment", "contract"}:
        return "confirm"
    if category == "customer_inquiry":
        return "prepare_quote"
    if category == "marketing":
        return "ignore"
    return "reply"


def _action_description(action_type: str, category: str, text: str) -> str:
    if action_type == "check_delivery":
        if _is_booking_context(text):
            return "请先核查物流订舱、FE 和 tracking 状态，再准备回复。"
        return "请先核查交付或发货状态，再准备回复。"
    if action_type == "confirm" and _is_meeting_context(text):
        return "请先确认会议邀请是否有效以及是否需要参加，再回复。"
    if action_type == "confirm" and category == "payment":
        return "请先核对付款、发票或汇款状态，再回复。"
    if action_type == "confirm" and category == "contract":
        return "请先与负责人复核合同条款，再回复。"
    if action_type == "prepare_quote":
        return "请先准备报价信息并完成人工审核，再回复客户。"
    if action_type == "escalate":
        return "请先升级给负责人处理风险，再回复。"
    if action_type == "wait":
        return "请等待缺失信息后再采取行动。"
    if action_type == "ignore":
        return "当前邮件无需业务回复。"
    if category == "internal":
        return "请先准备内部回复并完成人工审核。"
    return "请先准备谨慎回复并完成人工审核。"


def _draft_context_line(action_type: str, category: str, text: str) -> str:
    if action_type == "confirm" and _is_meeting_context(text):
        return "We will first verify whether this meeting invitation is valid and whether attendance is needed."
    if action_type == "check_delivery" and _is_booking_context(text):
        return "We will check the booking, FE, and tracking details with the responsible logistics owner."
    if action_type == "prepare_quote":
        return "We will review the inquiry internally before sharing any price or lead time."
    if action_type == "escalate" and category == "complaint":
        return "We will route the quality issue to the responsible owner for review."
    if category == "internal":
        return "We will treat this as an internal review item before any external reply."
    if action_type == "ignore":
        return "This appears to be reference or marketing material rather than an action request."
    return "We will review the message and confirm the relevant details before replying."


def _draft_next_step(action_type: str, category: str, text: str) -> str:
    if action_type == "check_delivery":
        if _is_booking_context(text):
            return "We will confirm the logistics status before giving any tracking or timing update."
        return "We will check the delivery or shipment status before confirming any timing."
    if action_type == "confirm" and _is_meeting_context(text):
        return "We will confirm the schedule internally before responding."
    if action_type == "confirm" and category == "payment":
        return "We will verify the invoice, payment, or remittance status before replying."
    if action_type == "confirm" and category == "contract":
        return "We will review the contract terms with the responsible reviewer before replying."
    if action_type == "prepare_quote":
        return "We will prepare the quote details for human review before sharing price or lead time."
    if action_type == "escalate" and category == "complaint":
        return "We will escalate the quality issue to the responsible owner before replying."
    if action_type == "escalate":
        return "We will escalate this risk to the responsible owner before replying."
    if action_type == "wait":
        return "We will wait for the missing information before taking further action."
    if action_type == "ignore":
        return "No business reply appears necessary based on the current message."
    if category == "internal":
        return "We will complete the internal review before anyone replies externally."
    return "We will draft a cautious response for human review before replying."
