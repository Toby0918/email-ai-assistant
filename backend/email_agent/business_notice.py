"""Recognize narrowly supported current-message notices without inventing tasks.

Only complete, affirmative statements are eligible to replace generic advice.
Unrecognized clauses, open thread work and selected attachments retain the normal
review path. A sender's reported state is never independent operational proof.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Notice:
    pattern: str
    label: str
    conclusion: str
    check: str


_NOTICES = (
    Notice(
        r"(?:the\s+)?(?:shipment|cargo|goods)\s+(?:has|have)\s+been\s+delivered"
        r"(?:\s+to\s+(?:the\s+)?receiving\s+warehouse)?",
        "交付通知", "发件人报告货物已送达收货地点",
        "这是邮件报告的送达状态；不等于已核验签收凭证、所有订单或最终验收。",
    ),
    Notice(
        r"(?:our\s+)?finance\s+team\s+is\s+processing\s+(?:the\s+)?payment",
        "付款进度", "发件人报告付款处理中",
        "付款处理中不等于已经汇出、银行到账或已获放货授权。",
    ),
    Notice(
        r"(?:the\s+)?invoice\s+has\s+been\s+posted\s+and\s+will\s+be\s+paid\s+in\s+next\s+week['’]s\s+payment\s+run",
        "发票处理进度", "发件人报告发票已入账，并计划在其邮件时点的下一周付款批次支付",
        "发票已入账和未来付款批次安排不等于到账；不能根据邮件中的下一周推定今天已付或逾期。",
    ),
    Notice(
        r"we\s+will\s+send\s+(?:the\s+)?bank\s+slip\s+once\s+available",
        "待提供凭据", "银行回单仍待发件人提供",
        "未来提供银行回单的承诺不等于当前已附回单或已经到账。",
    ),
    Notice(
        r"(?:please\s+find\s+attached\s+(?:the\s+)?approved\s+PPAP|"
        r"(?:the\s+)?PPAP\s+(?:has\s+been|is)\s+approved)",
        "审批通知", "发件人报告 PPAP 已批准",
        "核对该 PPAP 的料号、表面处理、图纸版本和批准范围；邮件陈述不代替附件核验。",
    ),
    Notice(
        r"(?:the\s+)?drawing\s+has\s+been\s+updated\s+to\s+revision\s+[A-Z0-9-]{1,12}",
        "图纸版本通知", "发件人报告图纸版本已更新",
        "需查看所选附件才能核验实际图纸版本；版本更新不自动扩大批准范围。",
    ),
)
_COURTESY = re.compile(r"(?:hello|hi|dear\s+\w+|thank\s+you|thanks|noted)[,!\s]*", re.I)
_AUTO_SUBJECT = re.compile(r"^(?:(?:re|fw|fwd):\s*)*(?:automatic reply|auto(?:matic)?[- ]reply|自动回复|respuesta autom[aá]tica|resposta autom[aá]tica)\s*[:：]", re.I)
_OFFICE = re.compile(r"I am out of (?:the )?office(?: and will return on [A-Za-z]+ \d{1,2})?", re.I)
_QUALIFICATION = re.compile(
    r"\b(?:if|unless|not|pending|correction|incorrect|withdrawn|retracted|however)\b|"
    r"\b(?:subject to|only after)\b|更正|尚未|待批准|如果|除非", re.I,
)


def apply_business_notice(
    result: dict[str, Any], body: str, subject: str,
) -> None:
    """Refine the public local result using only the submitted current body."""
    if any(risk["type"] in {"security_risk", "prompt_injection_risk"}
           for risk in result["risk_flags"]):
        return
    content = re.split(r"(?im)^\s*(?:best regards|kind regards|regards|--|此致|祝好)\s*[,!。]?\s*$", body)[0]
    if "?" in content or "？" in content or _QUALIFICATION.search(content):
        return
    clauses = [part.strip() for part in re.split(r"[\n.!?。！？;；]+", content) if part.strip()]
    meaningful = [part for part in clauses if not _COURTESY.fullmatch(part)]
    timeline = result["conversation_timeline"]
    unresolved_request = (timeline.get("current_status") in {"unresolved", "partially_resolved"}
                          and bool(str(timeline.get("latest_external_request") or "").strip()))
    has_review_work = bool(result["attachment_insights"] or timeline.get("open_items") or unresolved_request)
    courtesy_only = bool(clauses) and not meaningful
    office_only = bool(meaningful) and _AUTO_SUBJECT.search(subject) and all(_OFFICE.fullmatch(part) for part in meaningful)
    if (courtesy_only or office_only) and not has_review_work:
        conclusion = ("当前邮件是离岗自动回复；返岗日期不代表业务交付期限。" if office_only
                      else "当前正文仅为致谢或确认收到，没有明确提出新的业务请求。")
        result.update(category="unknown", priority="normal", priority_reason="正文没有提出新的业务请求。",
                      risk_flags=[], tags=["automatic_reply" if office_only else "acknowledgement"])
        brief = result["decision_brief"]
        brief["key_facts"] = []
        brief["missing_info"] = []
        brief["must_check"] = ["本判断只适用于当前正文，不代表未提供的历史事项已经解决。"]
        _set_notice_advice(result, conclusion)
        return
    matches = [(part, notice) for part in meaningful for notice in _NOTICES
               if re.fullmatch(notice.pattern, part, re.I)]
    if not matches:
        return
    brief = result["decision_brief"]
    for part, notice in matches:
        brief["key_facts"].append({"label": notice.label, "value": part,
                                   "source": "latest_message"})
        if notice.check not in brief["must_check"]:
            brief["must_check"].append(notice.check)
    matched_text = {part for part, _ in matches}
    brief["key_facts"] = [item for item in brief["key_facts"]
                          if not (item["label"] == "请求" and item["value"] in matched_text)]
    conclusion = "；".join(dict.fromkeys(notice.conclusion for _, notice in matches)) + "。"
    if len(matches) != len(meaningful):
        brief["one_line_conclusion"] = conclusion + brief["one_line_conclusion"]
        return
    if has_review_work:
        result["summary"] = brief["one_line_conclusion"] = conclusion + "附件或已提供的线程另有内容需要核查。"
        if not timeline.get("open_items") and not unresolved_request:
            brief["requested_outcome"] = "正文提供状态通知；还需核查所选附件，不能据此认定全部事项已完成。"
        _set_review_notice_advice(result)
        return
    _set_notice_advice(result, conclusion)


def _set_notice_advice(result: dict[str, Any], conclusion: str) -> None:
    brief = result["decision_brief"]
    result["summary"] = conclusion
    brief["one_line_conclusion"] = conclusion
    brief["requested_outcome"] = "当前正文是状态通知，没有明确提出新的处理请求。"
    brief["reply_recommendation"] = {
        "should_reply": False, "reply_type": "no_reply",
        "reason": "这段正文仅报告状态；可按业务需要确认收到，无需自动追加查询或承诺。",
    }
    brief["confidence"] = "medium"
    action = {"type": "ignore", "description": "记录发件人报告的状态；如需确认收到，先人工审核。",
              "owner_hint": "account_owner", "due_hint": ""}
    result["suggested_actions"] = [action]
    brief["next_steps"] = [{"step": action["description"], "owner_hint": action["owner_hint"],
                            "due_hint": "", "source": "assistant_suggestion"}]
    result["reply_draft"]["body"] = "Hello,\n\nThank you for the update.\n\nBest regards"
    result["reply_draft"]["review_reasons"].append("状态通知通常无需回复；本草稿仅供人工选择确认收到。")
    _clear_internal_approval_category(result)


def _clear_internal_approval_category(result: dict[str, Any]) -> None:
    if result["category"] == "internal":
        result["category"] = "customer_inquiry"
        result["tags"] = [tag for tag in result["tags"] if tag != "internal"] + ["status_notice"]


def _set_review_notice_advice(result: dict[str, Any]) -> None:
    """Review selected evidence/open work without re-inventing a status request."""
    brief = result["decision_brief"]
    action = {"type": "confirm", "description": "核查所选附件及已提供线程中的未决事项；当前通知不代表全部事项完成。",
              "owner_hint": "account_owner", "due_hint": ""}
    escalations = [item for item in result["suggested_actions"] if item["type"] == "escalate"]
    result["suggested_actions"] = [*escalations, action]
    thread_steps = [item for item in brief["next_steps"] if item["source"] == "thread"]
    steps = [{"step": item["description"], "owner_hint": item["owner_hint"],
              "due_hint": item["due_hint"], "source": "assistant_suggestion"}
             for item in result["suggested_actions"]]
    brief["next_steps"] = [*thread_steps[:4-len(steps)], *steps]
    brief["reply_recommendation"] = {
        "should_reply": True, "reply_type": "escalate_first" if escalations else "acknowledge",
        "reason": "先核查附件或已提供的未决事项；不能因收到状态通知而跳过这些核查。",
    }
    result["reply_draft"]["body"] = (
        "Hello,\n\nThank you for the update. We will review the supporting documents "
        "and outstanding items before responding further.\n\nBest regards"
    )
    _clear_internal_approval_category(result)
