"""Keep explicit conditions, document instructions and shipping date roles."""
from __future__ import annotations

import re
from typing import Any


_DATE = re.compile(
    r"(?P<label>pick[- ]?up\s+scheduled|cut[ -]?off|ETD|ETA)\s*:\s*"
    r"(?P<value>TBA|\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{4}-\d{2}-\d{2})", re.I,
)
_DATE_LABELS = {"pickupscheduled": "计划提货", "cutoff": "截关/截单",
                "etd": "预计离港 ETD", "eta": "预计到港 ETA"}
_WAIT = re.compile(
    r"(?:Remove the marking only after my confirmation[.!。]?\s*)?"
    r"Please wait for my (?:approval|confirmation)[.!。]?", re.I,
)
_VERSION = re.compile(
    r"The previous (?:packing list|invoice|drawing) is superseded[.!。]?\s*"
    r"Please use (?:this|the) revised version instead[.!。]?", re.I,
)


def apply_business_conditions(result: dict[str, Any], body: str) -> None:
    if any(risk["type"] in {"security_risk", "prompt_injection_risk"}
           for risk in result["risk_flags"]):
        return
    brief = result["decision_brief"]
    # Only standalone labeled schedule clauses are read as date-role evidence.
    # Embedded questions, negations and quoted/conditional clauses do not match.
    dates = [match for clause in re.split(r"[\n.;。；]+", body)
             if (match := _DATE.fullmatch(clause.strip()))]
    for match in dates:
        role = re.sub(r"[-\s]", "", match["label"].lower())
        brief["key_facts"].append({"label": _DATE_LABELS[role], "value": match["value"],
                                   "source": "latest_message"})
    if dates:
        brief["must_check"].append("计划提货、截关/截单、ETD 和 ETA 是不同时间字段；不代表实际提货、离港或到港。未写年份或时区时不自行补全。")
    if _WAIT.fullmatch(body.strip()):
        conclusion = "当前变更须等待发件人确认；正文没有授予立即执行的权限。"
        result.update(category="customer_inquiry", summary=conclusion)
        result["tags"] = [tag for tag in result["tags"] if tag != "internal"] + ["pending_sender_confirmation"]
        brief["one_line_conclusion"] = conclusion
        brief["requested_outcome"] = "发件人要求先等待其批准，再处理变更。"
        brief["must_check"].append("核对发件人的确认以及适用变更范围；不能用内部批准代替对方确认。")
        action = {"type": "wait", "description": "等待发件人明确确认该变更。",
                  "owner_hint": "account_owner", "due_hint": ""}
        result["suggested_actions"] = [action]
        # Preserve independently supplied open thread work.
        thread_steps = [step for step in brief["next_steps"] if step["source"] == "thread"]
        brief["next_steps"] = [*thread_steps[:3], {
            "step": action["description"], "owner_hint": action["owner_hint"],
            "due_hint": "", "source": "assistant_suggestion",
        }]
        brief["reply_recommendation"] = {"should_reply": True, "reply_type": "acknowledge",
                                          "reason": "可确认已收到等待批准的要求，不承诺提前执行。"}
        result["reply_draft"]["body"] = (
            "Hello,\n\nWe will wait for your confirmation before making the requested change.\n\nBest regards"
        )
    if _VERSION.fullmatch(body.strip()):
        conclusion = "发件人明确提出版本替代：旧文件被替代，应核对本次修订文件。"
        result["summary"] = brief["one_line_conclusion"] = conclusion
        brief["requested_outcome"] = "使用修订版本；实际文件内容、差异和适用范围仍需核验。"
        brief["key_facts"].append({"label": "版本替代指令", "value": body.strip(), "source": "latest_message"})
        brief["must_check"].append("按文件内容、修订标识和本次明确指令核对版本，不能仅凭相同文件名认定内容相同。")
        if not result["attachment_insights"]:
            brief["missing_info"].append("本次未提供修订附件，无法比较实际数值或确认新文件内容。")
