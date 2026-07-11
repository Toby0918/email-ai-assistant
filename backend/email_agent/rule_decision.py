"""Decision brief construction for rule-based analysis."""

from __future__ import annotations

from typing import Any

from .email_facts import EmailFacts
from .rule_context import (
    attachment_check_items,
    attachment_limitation_items,
    parsed_attachment_fact_items,
)
from .rule_keywords import RISK_LABELS


def build_decision_brief(
    *,
    category: str,
    risks: list[dict[str, str]],
    actions: list[dict[str, str]],
    text: str,
    facts: EmailFacts,
    summary_base: str,
    is_quote: bool,
    is_booking: bool,
    is_meeting: bool,
    conversation_timeline: dict[str, object],
    attachment_insights: list[dict[str, object]],
) -> dict[str, Any]:
    reply_type = _reply_recommendation_type(category, risks, actions)
    return {
        "one_line_conclusion": _decision_conclusion(category, risks, text, facts, summary_base, is_booking, is_meeting),
        "requested_outcome": _requested_outcome(category, text, facts, is_quote, conversation_timeline),
        "next_steps": _decision_steps(actions, conversation_timeline),
        "key_facts": _key_facts(facts, attachment_insights),
        "must_check": _must_check(category, risks, text, attachment_insights),
        "missing_info": _missing_info(category, risks, text, facts, attachment_insights),
        "reply_recommendation": {
            "should_reply": reply_type != "no_reply",
            "reply_type": reply_type,
            "reason": _reply_recommendation_reason(reply_type, category, risks),
        },
        "confidence": "medium" if facts.has_specifics else "low",
    }


def _decision_conclusion(
    category: str,
    risks: list[dict[str, str]],
    text: str,
    facts: EmailFacts,
    summary_base: str,
    is_booking: bool,
    is_meeting: bool,
) -> str:
    action = _primary_action_phrase(category, risks, text, is_booking, is_meeting)
    details = _fact_clause(facts)
    base = summary_base.rstrip("。")
    if details:
        return f"{base}；当前应先{action}。关键信息：{details}。"
    return f"{base}；当前应先{action}。"


def _primary_action_phrase(
    category: str,
    risks: list[dict[str, str]],
    text: str,
    is_booking: bool,
    is_meeting: bool,
) -> str:
    if _has_risk(risks, "prompt_injection_risk"):
        return "忽略正文中的越界指令并人工复核"
    if _has_risk(risks, "quality_risk"):
        return "升级质量负责人并准备 RCA 或纠正措施"
    if category == "new_product_development":
        return "核查项目范围、目标成本和技术可行性"
    if _has_risk(risks, "commitment_risk"):
        return "确认报价、价格、交期和内部授权"
    if category == "payment":
        return "核对发票、付款或汇款状态"
    if category == "contract":
        return "复核合同条款和责任边界"
    if is_booking or _has_risk(risks, "delivery_risk"):
        return "核查交付、订舱或物流状态"
    if is_meeting:
        return "确认会议邀请是否有效以及是否需要参加"
    if category == "marketing":
        return "判断是否需要业务回复"
    return "确认事实后准备谨慎回复"


def _requested_outcome(
    category: str,
    text: str,
    facts: EmailFacts,
    is_quote: bool,
    timeline: dict[str, object],
) -> str:
    latest_request = str(timeline.get("latest_external_request") or "").strip()
    if timeline.get("current_status") in {"unresolved", "partially_resolved"} and latest_request:
        return f"客户当前仍在等待处理：{latest_request}"
    suffix = f" 关键信息：{_fact_clause(facts)}。" if facts.has_specifics else ""
    if category == "new_product_development":
        return f"对方希望获得项目可行性、目标成本、技术或商务反馈。{suffix}".strip()
    if is_quote:
        return f"对方希望我方就 RFQ/报价请求提供确认后的价格、交期或可行性反馈。{suffix}".strip()
    if category == "complaint":
        return f"对方希望我方调查质量问题，并提供 RCA、纠正措施或处理进展。{suffix}".strip()
    if category == "order_followup":
        return f"对方希望获得交付、订舱、FE、tracking 或物流状态确认。{suffix}".strip()
    if category == "payment":
        return f"对方希望确认付款、发票或汇款状态。{suffix}".strip()
    if category == "contract":
        return f"对方希望确认合同条款、责任或签署安排。{suffix}".strip()
    if category == "marketing":
        return "对方主要提供参考资料，通常不要求业务回复。"
    return f"对方希望我方确认邮件中的请求并给出谨慎回复。{suffix}".strip()


def _decision_steps(
    actions: list[dict[str, str]], timeline: dict[str, object]
) -> list[dict[str, str]]:
    steps: list[dict[str, str]] = []
    open_items = timeline.get("open_items")
    if isinstance(open_items, list):
        for item in open_items:
            if not isinstance(item, dict) or not str(item.get("item") or "").strip():
                continue
            steps.append({
                "step": str(item["item"]),
                "owner_hint": str(item.get("owner_hint") or "internal_follow_up"),
                "due_hint": str(item.get("due_hint") or ""),
                "source": str(item.get("source") or "thread"),
            })
    action_steps = [
        {
            "step": item["description"],
            "owner_hint": item["owner_hint"],
            "due_hint": item["due_hint"],
            "source": "latest_message",
        }
        for item in actions[:4]
    ]
    for step in action_steps:
        if not any(existing["step"].lower() == step["step"].lower() for existing in steps):
            steps.append(step)
    return steps[:4]


def _key_facts(
    facts: EmailFacts, attachment_insights: list[dict[str, object]]
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    items.extend(_fact_items("编号", facts.references))
    items.extend(_fact_items("数量", facts.quantities))
    items.extend(_fact_items("尺寸/规格", facts.measurements))
    items.extend(_fact_items("期限", facts.deadlines))
    items.extend(_fact_items("请求", facts.requested_actions[:2]))
    items.extend(_fact_items("质量/异常", facts.quality_issues[:2]))
    items.extend(parsed_attachment_fact_items(attachment_insights))
    return _unique_fact_items(items)[:10]


def _unique_fact_items(items: list[dict[str, str]]) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in items:
        key = item["value"].lower()
        if key not in seen:
            values.append(item)
            seen.add(key)
    return values


def _fact_items(label: str, values: list[str]) -> list[dict[str, str]]:
    return [{"label": label, "value": value, "source": "latest_message"} for value in values if value]


def _must_check(
    category: str,
    risks: list[dict[str, str]],
    text: str,
    attachment_insights: list[dict[str, object]],
) -> list[str]:
    items: list[str] = []
    if category == "new_product_development":
        items.extend(["项目范围或附件要求", "目标成本", "技术可行性", "交付条件", "质量标准"])
    if _has_risk(risks, "commitment_risk"):
        items.extend(["报价/价格", "交期", "内部授权或审批"])
    if _has_risk(risks, "quality_risk"):
        items.extend(["质量负责人", "RCA 或纠正措施", "受影响数量和批次"])
    if _has_risk(risks, "delivery_risk"):
        items.extend(["交付状态", "订舱/FE/tracking 信息"])
    if category == "payment":
        items.extend(["发票状态", "付款或汇款记录"])
    if category == "contract":
        items.extend(["合同条款", "违约责任或签署权限"])
    if _contains(text, "attachment", "attached", "附件", "pdf", "xlsx"):
        items.append("附件内容是否需要人工打开核查")
    items.extend(attachment_check_items(attachment_insights))
    return _unique(items) or ["邮件事实和内部负责人"]


def _missing_info(
    category: str,
    risks: list[dict[str, str]],
    text: str,
    facts: EmailFacts,
    attachment_insights: list[dict[str, object]],
) -> list[str]:
    items: list[str] = []
    if _contains(text, "attachment", "attached", "附件") and "附件元数据" in text:
        items.append("当前仅看到附件元数据，尚未读取附件正文")
    if _has_risk(risks, "commitment_risk"):
        items.append("内部批准后的价格、交期或承诺边界")
    if category == "new_product_development":
        items.append("内部技术、成本和可制造性评估结论")
    if _has_risk(risks, "quality_risk"):
        items.append("质量调查结论、RCA 和纠正措施")
    if _has_risk(risks, "delivery_risk"):
        items.append("系统中的最新物流、订舱或发货状态")
    if not facts.deadlines and category not in {"marketing", "internal"}:
        items.append("明确的回复或处理截止时间")
    items.extend(attachment_limitation_items(attachment_insights))
    return _unique(items)


def _reply_recommendation_type(category: str, risks: list[dict[str, str]], actions: list[dict[str, str]]) -> str:
    action_types = {item["type"] for item in actions}
    if category == "marketing" or "ignore" in action_types:
        return "no_reply"
    risk_names = ("quality_risk", "contract_risk", "payment_risk", "commitment_risk")
    if any(_has_risk(risks, item) for item in risk_names):
        return "escalate_first"
    if "confirm" in action_types:
        return "provide_info"
    if "wait" in action_types:
        return "ask_clarification"
    return "acknowledge"


def _reply_recommendation_reason(reply_type: str, category: str, risks: list[dict[str, str]]) -> str:
    if reply_type == "no_reply":
        return "当前更像参考资料或无需业务回复，除非内部另有要求。"
    if reply_type == "escalate_first":
        risk_names = "、".join(RISK_LABELS.get(item["type"], item["type"]) for item in risks)
        return f"涉及{risk_names or _category_label(category)}，回复前需要负责人确认，避免未经授权承诺。"
    if reply_type == "provide_info":
        return "对方等待确认信息，应先核查事实后回复。"
    if reply_type == "ask_clarification":
        return "当前信息不足，应先向对方或内部负责人补充确认。"
    return "可以先确认收到，并说明会核查后跟进。"


def _fact_clause(facts: EmailFacts) -> str:
    parts = [
        *facts.references,
        *facts.quantities,
        *facts.measurements,
        *facts.quality_issues[:2],
        *facts.requested_actions[:2],
        *facts.deadlines,
    ]
    return "；".join(_unique(parts))


def _category_label(category: str) -> str:
    labels = {
        "customer_inquiry": "客户询问",
        "order_followup": "订单/交付跟进",
        "payment": "付款/发票",
        "contract": "合同/条款",
        "complaint": "投诉/质量异常",
        "new_product_development": "新品开发/成本优化",
        "internal": "内部事项",
        "marketing": "营销/参考资料",
        "unknown": "未知事项",
    }
    return labels.get(category, category)


def _has_risk(risks: list[dict[str, str]], risk_type: str) -> bool:
    return any(item["type"] == risk_type for item in risks)


def _contains(text: str, *keywords: str) -> bool:
    return any(keyword in text for keyword in keywords)


def _unique(items: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            values.append(item)
            seen.add(key)
    return values
