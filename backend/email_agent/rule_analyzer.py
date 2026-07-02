"""Local rule-based analyzer for the first version."""

from __future__ import annotations

from typing import Any

from .analysis_schema import validate_analysis_result
from .email_facts import EmailFacts, extract_email_facts
from .rule_draft import build_reply_draft


DELIVERY_KEYWORDS = ("delivery", "shipment", "order", "eta", "交期", "发货", "物流", "到货", "订单", "交付")
PAYMENT_KEYWORDS = ("payment", "invoice", "remittance", "overdue", "付款", "发票", "汇款", "逾期", "账期", "对账")
CONTRACT_KEYWORDS = ("contract", "agreement", "terms", "signing", "合同", "协议", "条款", "签署")
QUALITY_KEYWORDS = ("complaint", "quality", "defective", "damaged", "投诉", "质量", "不良", "损坏", "缺陷")
QUOTE_KEYWORDS = ("quote", "quotation", "rfq", "price", "报价", "询价", "价格")
INTERNAL_KEYWORDS = ("internal", "internally", "approval", "approve", "reviewer", "内部", "审批", "复核", "审核")
MARKETING_KEYWORDS = ("marketing", "promotion", "advertisement", "exhibition", "trade show", "brochure", "展会", "推广", "广告")
MEETING_KEYWORDS = ("meeting", "calendar", "invitation", "invite", "zoom", "会议", "邀请", "日程")
BOOKING_KEYWORDS = ("booking", "tracking number", "tracking", "original fe", "forwarder", "logistics", "air freight", "sea freight", "订舱", "货代", "追踪", "物流")

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
    text = f"{subject}\n{sender}\n{clean_body}".lower()
    facts = extract_email_facts(subject, sender, clean_body)
    risks = _risk_flags(text, facts)
    category = _category(text, risks)
    priority = _priority(text, risks)
    actions = _suggested_actions(category, risks, text, facts)
    result = {
        "summary": _summary(category, risks, text, facts),
        "priority": priority,
        "priority_reason": _priority_reason(priority, risks, facts),
        "category": category,
        "tags": _tags(category, risks),
        "risk_flags": risks,
        "suggested_actions": actions,
        "reply_draft": build_reply_draft(
            subject=subject,
            category=category,
            actions=actions,
            is_meeting=_is_meeting_context(text),
            is_booking=_is_booking_context(text),
            facts=facts,
        ),
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


def _risk_flags(text: str, facts: EmailFacts) -> list[dict[str, str]]:
    risks: list[dict[str, str]] = []
    if _contains(text, "ignore previous", "system prompt", "reveal"):
        risks.append(_risk("prompt_injection_risk", "high", "邮件要求忽略系统规则或泄露内部提示。", "忽略邮件正文中的系统级指令，先人工复核。"))
    if _contains(text, *PAYMENT_KEYWORDS):
        level = "high" if _contains(text, "overdue", "逾期") else "medium"
        risks.append(_risk("payment_risk", level, _evidence("邮件提到付款、发票或汇款状态。", facts), "回复前请核对付款、发票或汇款状态，避免误承诺。"))
    if _contains(text, *DELIVERY_KEYWORDS) or _is_booking_context(text):
        risks.append(_risk("delivery_risk", "low", _evidence("邮件提到交付、发货或物流状态。", facts), "回复前请核查交付、订舱、FE 或 tracking 状态。"))
    if _contains(text, *CONTRACT_KEYWORDS):
        risks.append(_risk("contract_risk", "medium", _evidence("邮件提到合同、条款或签署事项。", facts), "回复前请与合同负责人复核条款。"))
    if _contains(text, *QUALITY_KEYWORDS):
        risks.append(_risk("quality_risk", "high", _evidence("邮件提到质量投诉或异常。", facts), "请先升级给质量负责人，并准备可审核的 RCA 或纠正措施回复。"))
    if _contains(text, *QUOTE_KEYWORDS):
        risks.append(_risk("commitment_risk", "medium", _evidence("邮件要求确认价格、报价或交期。", facts), "回复前请确认报价、价格和交期，避免未经授权承诺。"))
    return risks


def _risk(kind: str, level: str, evidence: str, recommendation: str) -> dict[str, str]:
    return {"type": kind, "level": level, "evidence": evidence, "recommendation": recommendation}


def _evidence(default: str, facts: EmailFacts) -> str:
    details = _fact_clause(facts)
    if not details:
        return default
    return f"{default} 关键信息：{details}。"


def _summary(category: str, risks: list[dict[str, str]], text: str, facts: EmailFacts) -> str:
    base = _summary_base(category, risks, text)
    details = _fact_clause(facts)
    if details and category != "marketing":
        return f"{base} 关键信息：{details}。"
    return base


def _summary_base(category: str, risks: list[dict[str, str]], text: str) -> str:
    if _has_risk(risks, "prompt_injection_risk"):
        return "这封邮件包含疑似提示注入内容，需要忽略正文中的系统级指令并人工复核。"
    if category == "complaint":
        return "这封邮件主要关于质量投诉或异常，需要升级给负责人处理。"
    if category == "contract":
        return "这封邮件主要关于合同、条款或签署事项，需要负责人复核后回复。"
    if category == "internal":
        return "这封邮件主要是内部审核或审批事项，需要先完成内部确认。"
    if category == "order_followup":
        return "这封邮件主要关于订舱、物流或追踪信息，需要核查状态后回复。" if _is_booking_context(text) else "这封邮件主要关于交付或发货进度，需要核查状态后回复。"
    if category == "payment":
        return "这封邮件主要关于付款、发票或汇款状态，需要核对后回复。"
    if category == "customer_inquiry":
        if _is_meeting_context(text):
            return "这封邮件主要关于会议或日程邀请，需要确认邀请有效性和是否参加。"
        return "这封邮件主要关于报价或询价，需要准备信息并人工审核。" if _contains(text, *QUOTE_KEYWORDS) else "这封邮件主要是客户询问，需要人工查看后准备谨慎回复。"
    if category == "marketing":
        return "这封邮件主要是营销或参考资料，通常无需业务回复。"
    return "这封邮件需要人工查看后准备谨慎回复。"


def _priority_reason(priority: str, risks: list[dict[str, str]], facts: EmailFacts) -> str:
    details = _fact_clause(facts)
    suffix = f" 相关事实：{details}。" if details else ""
    if risks:
        return f"优先级为{_priority_label(priority)}，因为检测到{_risk_label(risks[0]['type'])}。{suffix}".strip()
    return f"优先级为普通，因为未检测到高风险信号。{suffix}".strip()


def _priority_label(priority: str) -> str:
    return PRIORITY_LABELS.get(priority, priority)


def _risk_label(risk_type: str) -> str:
    return RISK_LABELS.get(risk_type, risk_type)


def _tags(category: str, risks: list[dict[str, str]]) -> list[str]:
    return [category, *[item["type"] for item in risks]]


def _suggested_actions(category: str, risks: list[dict[str, str]], text: str, facts: EmailFacts) -> list[dict[str, str]]:
    action_types = _action_types(category, risks, text)
    return [_action(action_type, category, text, facts) for action_type in action_types]


def _action_types(category: str, risks: list[dict[str, str]], text: str) -> list[str]:
    if _has_risk(risks, "prompt_injection_risk"):
        return ["escalate"]
    actions: list[str] = []
    if _has_risk(risks, "quality_risk"):
        actions.append("escalate")
    if _has_risk(risks, "delivery_risk"):
        actions.append("check_delivery")
    if _is_meeting_context(text) or category in {"payment", "contract"}:
        actions.append("confirm")
    if _has_risk(risks, "commitment_risk"):
        actions.append("prepare_quote")
    if not actions:
        actions.append("ignore" if category == "marketing" else "reply")
    return _unique(actions)


def _action(action_type: str, category: str, text: str, facts: EmailFacts) -> dict[str, str]:
    return {
        "type": action_type,
        "description": _action_description(action_type, category, text, facts),
        "owner_hint": _owner_hint(action_type, category),
        "due_hint": facts.deadlines[0] if facts.deadlines else "today",
    }


def _action_description(action_type: str, category: str, text: str, facts: EmailFacts) -> str:
    details = _fact_clause(facts)
    prefix = f"针对 {details}，" if details else ""
    if action_type == "check_delivery":
        return f"{prefix}请先核查物流订舱、FE 和 tracking 状态，再准备回复。" if _is_booking_context(text) else f"{prefix}请先核查交付或发货状态，再准备回复。"
    if action_type == "confirm" and _is_meeting_context(text):
        return f"{prefix}请先确认会议邀请是否有效以及是否需要参加，再回复。"
    if action_type == "confirm" and category == "payment":
        return f"{prefix}请先核对付款、发票或汇款状态，再回复。"
    if action_type == "confirm" and category == "contract":
        return f"{prefix}请先与负责人复核合同条款，再回复。"
    if action_type == "prepare_quote":
        return f"{prefix}请先准备报价信息并完成人工审核，再回复客户。"
    if action_type == "escalate":
        return f"{prefix}请先升级给负责人处理风险，再回复。"
    if action_type == "ignore":
        return "当前邮件无需业务回复。"
    return f"{prefix}请先准备谨慎回复并完成人工审核。"


def _owner_hint(action_type: str, category: str) -> str:
    if action_type == "check_delivery":
        return "logistics_owner"
    if action_type == "escalate" and category == "complaint":
        return "quality_owner"
    if category == "payment":
        return "finance_owner"
    if category == "contract":
        return "contract_owner"
    return "account_owner"


def _fact_clause(facts: EmailFacts) -> str:
    parts = [*facts.references, *facts.quantities, *facts.measurements, *facts.quality_issues[:2], *facts.requested_actions[:2], *facts.deadlines]
    return "；".join(_unique(parts))


def _contains(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords)


def _is_meeting_context(text: str) -> bool:
    return _contains(text, *MEETING_KEYWORDS)


def _is_booking_context(text: str) -> bool:
    return _contains(text, *BOOKING_KEYWORDS)


def _has_risk(risks: list[dict[str, str]], risk_type: str) -> bool:
    return any(item["type"] == risk_type for item in risks)


def _unique(items: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            values.append(item)
            seen.add(key)
    return values
