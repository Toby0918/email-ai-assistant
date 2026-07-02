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


def build_rule_based_analysis(subject: str, sender: str, clean_body: str) -> dict[str, Any]:
    # Deterministic local output keeps the first version usable without live AI.
    text = f"{subject}\n{sender}\n{clean_body}".lower()
    risks = _risk_flags(text)
    category = _category(text, risks)
    priority = _priority(text, risks)
    summary = _summary(subject, clean_body)
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
        risks.append(_risk("prompt_injection_risk", "high", "Email asks the system to ignore rules."))
    if _contains(text, *PAYMENT_KEYWORDS):
        level = "high" if _contains(text, "overdue", "逾期") else "medium"
        risks.append(_risk("payment_risk", level, "Email mentions payment or invoice."))
    if _contains(text, *DELIVERY_KEYWORDS) or _is_booking_context(text):
        risks.append(_risk("delivery_risk", "low", "Email mentions delivery, shipment, or logistics."))
    if _contains(text, *CONTRACT_KEYWORDS):
        risks.append(_risk("contract_risk", "medium", "Email mentions contract terms."))
    if _contains(text, *QUALITY_KEYWORDS):
        risks.append(_risk("quality_risk", "high", "Email mentions a quality complaint."))
    if _contains(text, *QUOTE_KEYWORDS):
        risks.append(_risk("commitment_risk", "medium", "Email asks for price or quote confirmation."))
    return risks


def _risk(kind: str, level: str, evidence: str) -> dict[str, str]:
    return {
        "type": kind,
        "level": level,
        "evidence": evidence,
        "recommendation": "Review the context before replying.",
    }


def _summary(subject: str, clean_body: str) -> str:
    snippet = " ".join(clean_body.split())[:160]
    return f"{subject}: {snippet}" if subject else snippet


def _priority_reason(priority: str, risks: list[dict[str, str]]) -> str:
    if risks:
        return f"Priority is {priority} because {risks[0]['type']} was detected."
    return "Priority is normal because no high-risk signal was detected."


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
        "subject": f"Re: {subject}" if subject else "Re: your email",
        "body": (
            "Hello,\n\n"
            "Thank you for your email.\n"
            f"{_draft_context_line(action_type, category, text)}\n"
            f"{_draft_next_step(action_type, category, text)}\n\n"
            "Best regards"
        ),
        "needs_human_review": True,
        "review_reasons": ["First-version draft must be reviewed before use."],
    }


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
            return "Check logistics booking, FE, and tracking status before drafting a reply."
        return "Check delivery or shipment status before drafting a reply."
    if action_type == "confirm" and _is_meeting_context(text):
        return "Confirm whether the meeting invitation is valid and attendance is needed before replying."
    if action_type == "confirm" and category == "payment":
        return "Confirm payment, invoice, or remittance status before replying."
    if action_type == "confirm" and category == "contract":
        return "Confirm contract terms with the responsible reviewer before replying."
    if action_type == "prepare_quote":
        return "Prepare quote details for human review before any customer reply."
    if action_type == "escalate":
        return "Escalate this risk to the responsible owner before replying."
    if action_type == "wait":
        return "Wait for more information before taking action."
    if action_type == "ignore":
        return "No business action is needed for this message."
    if category == "internal":
        return "Prepare an internal response for human review."
    return "Draft a cautious reply for human review."


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
