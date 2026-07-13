"""Language and unsafe-operation predicates for provider-authored prose."""

from __future__ import annotations

import re


_CHINESE_RE = re.compile(r"[\u3400-\u9fff]")
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


def has_chinese(value: str) -> bool:
    return bool(_CHINESE_RE.search(value))


def has_unsafe_operation(value: str) -> bool:
    return bool(_AUTO_ACTION_RE.search(value) or _ACTION_CLAIM_RE.search(value))


def has_unconditional_commitment(value: str) -> bool:
    return bool(_COMMITMENT_RE.search(value))


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
