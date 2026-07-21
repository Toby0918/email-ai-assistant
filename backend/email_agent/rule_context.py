"""Build deterministic rule evidence from thread state and parsed attachments."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .email_facts import EmailFacts, extract_email_facts


ATTACHMENT_SEMANTIC_REVIEW = (
    "已解析附件未提取到结构化业务事实；回复前需人工核查附件是否影响当前结论。"
)
QUANTITY_SCOPE_REVIEW = (
    "邮件正文或不同附件中存在多个不同数量；回复前需人工核对各数值的业务含义和适用范围。"
)
_QUANTITY_NUMBER = (
    r"(?:\d{1,3}(?:,\d{3}){1,3}|\d{1,9})(?:\.\d{1,4})?"
)
_QUANTITY_RE = re.compile(
    r"^(?:Quantity:\s*|MOQ\s+)?"
    rf"(?P<values>{_QUANTITY_NUMBER}"
    rf"(?:\s*/\s*{_QUANTITY_NUMBER}){{0,3}})"
    r"(?:\s*(?P<unit>pc|pcs|piece|pieces|unit|units|set|sets|"
    r"kg|g|lb|lbs|件|个|套))?$",
    re.IGNORECASE,
)
_QUANTITY_UNITS = {
    "pc": "count",
    "pcs": "count",
    "piece": "count",
    "pieces": "count",
    "件": "count",
    "个": "count",
    "unit": "count",
    "units": "count",
    "set": "sets",
    "sets": "sets",
    "套": "sets",
    "kg": "kg",
    "g": "g",
    "lb": "lbs",
    "lbs": "lbs",
}
_BUSINESS_FACT_PREFIXES = (
    "reference:",
    "quantity:",
    "measurement:",
    "amount:",
    "deadline:",
    "requested action:",
    "quality issue:",
)


@dataclass(frozen=True)
class RuleAnalysisContext:
    text: str
    message_facts: EmailFacts
    facts: EmailFacts


def build_rule_context(
    subject: str,
    sender: str,
    clean_body: str,
    timeline: dict[str, object],
    insights: list[dict[str, object]],
) -> RuleAnalysisContext:
    """Use timeline evidence and only parsed attachment text for rule decisions."""
    thread_text = _thread_text(timeline)
    attachment_text = _parsed_attachment_text(insights)
    message_facts = extract_email_facts(
        subject,
        sender,
        _join(clean_body, thread_text),
    )
    attachment_facts = extract_email_facts("", "", attachment_text)
    return RuleAnalysisContext(
        text=_join(subject, sender, clean_body, thread_text, attachment_text).lower(),
        message_facts=message_facts,
        facts=_merge_facts(message_facts, attachment_facts),
    )


def parsed_attachment_fact_items(
    insights: list[dict[str, object]],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for insight in insights:
        if insight.get("status") != "parsed":
            continue
        filename = str(insight.get("filename") or "附件")
        facts = insight.get("key_facts")
        if not isinstance(facts, list):
            continue
        for fact in facts:
            if isinstance(fact, str) and fact.strip():
                items.append({
                    "label": f"附件 {filename}",
                    "value": fact.strip(),
                    "source": f"attachment:{filename}",
                })
    return items


def attachment_check_items(insights: list[dict[str, object]]) -> list[str]:
    items: list[str] = []
    for insight in insights:
        filename = str(insight.get("filename") or "附件")
        if insight.get("status") != "parsed":
            items.append(f"人工核查未完成解析的附件 {filename}")
        else:
            facts = insight.get("key_facts")
            if not _has_business_attachment_fact(facts):
                items.append(ATTACHMENT_SEMANTIC_REVIEW)
            if insight.get("limitations"):
                items.append(f"核查附件 {filename} 的解析范围和限制")
    return items


def cross_source_quantity_check_items(
    message_facts: EmailFacts,
    insights: list[dict[str, object]],
) -> list[str]:
    """Flag disjoint quantity evidence without guessing which source is right."""
    sources = [_quantity_values(message_facts.quantities)]
    sources.extend(
        values
        for insight in insights
        if insight.get("status") == "parsed"
        for values in [_attachment_quantity_values(insight)]
        if values
    )
    populated = [source for source in sources if source]
    for index, left in enumerate(populated):
        for right in populated[index + 1 :]:
            if _quantity_sources_differ(left, right):
                return [QUANTITY_SCOPE_REVIEW]
    return []


def attachment_limitation_items(insights: list[dict[str, object]]) -> list[str]:
    items: list[str] = []
    for insight in insights:
        filename = str(insight.get("filename") or "附件")
        limitations = insight.get("limitations")
        if isinstance(limitations, list):
            items.extend(
                f"附件 {filename} 解析限制：{value}"
                for value in limitations
                if isinstance(value, str) and value.strip()
            )
        if insight.get("status") != "parsed" and not limitations:
            items.append(f"附件 {filename} 未完成解析，需人工核查")
    return items


def _thread_text(timeline: dict[str, object]) -> str:
    if timeline.get("current_status") not in {"unresolved", "partially_resolved"}:
        return ""
    return str(timeline.get("latest_external_request") or "").strip()


def _parsed_attachment_text(insights: list[dict[str, object]]) -> str:
    values: list[str] = []
    for insight in insights:
        if insight.get("status") != "parsed":
            continue
        values.append(str(insight.get("summary") or ""))
        facts = insight.get("key_facts")
        if isinstance(facts, list):
            values.extend(str(item) for item in facts if isinstance(item, str))
    return _join(*values)


def _attachment_quantity_values(
    insight: dict[str, object],
) -> dict[str, set[str]]:
    facts = insight.get("key_facts")
    if not isinstance(facts, list):
        return {}
    return _quantity_values([
        fact
        for fact in facts
        if isinstance(fact, str)
        and fact.strip().casefold().startswith(("quantity:", "moq "))
    ])


def _has_business_attachment_fact(facts: object) -> bool:
    if not isinstance(facts, list):
        return False
    return any(
        isinstance(fact, str)
        and fact.strip().casefold().startswith(_BUSINESS_FACT_PREFIXES)
        for fact in facts
    )


def _quantity_values(facts: list[str]) -> dict[str, set[str]]:
    values: dict[str, set[str]] = {}
    for fact in facts:
        match = _QUANTITY_RE.fullmatch(fact.strip())
        if match is None:
            continue
        raw_unit = match.group("unit")
        unit = _QUANTITY_UNITS[raw_unit.casefold()] if raw_unit else "unspecified"
        normalized = {
            part.replace(",", "")
            for part in re.split(r"\s*/\s*", match.group("values"))
        }
        values.setdefault(unit, set()).update(normalized)
    return values


def _quantity_sources_differ(
    left: dict[str, set[str]],
    right: dict[str, set[str]],
) -> bool:
    if "unspecified" in left or "unspecified" in right:
        left_values = set().union(*left.values())
        right_values = set().union(*right.values())
        return _quantity_sets_differ(left_values, right_values)
    return any(
        _quantity_sets_differ(left[unit], right[unit])
        for unit in left.keys() & right.keys()
    )


def _quantity_sets_differ(left: set[str], right: set[str]) -> bool:
    return left.isdisjoint(right) or not (
        left.issubset(right) or right.issubset(left)
    )


def _merge_facts(primary: EmailFacts, secondary: EmailFacts) -> EmailFacts:
    return EmailFacts(
        references=_merge_values(primary.references, secondary.references),
        quantities=_merge_values(primary.quantities, secondary.quantities),
        measurements=_merge_values(primary.measurements, secondary.measurements),
        deadlines=_merge_values(primary.deadlines, secondary.deadlines),
        requested_actions=_merge_values(primary.requested_actions, secondary.requested_actions),
        quality_issues=_merge_values(primary.quality_issues, secondary.quality_issues),
    )


def _merge_values(first: list[str], second: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in [*first, *second]:
        key = item.lower()
        if key not in seen:
            values.append(item)
            seen.add(key)
    return values[:5]


def _join(*parts: str) -> str:
    return "\n".join(part for part in parts if part)
