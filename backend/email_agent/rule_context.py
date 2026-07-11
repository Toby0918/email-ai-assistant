"""Build deterministic rule evidence from thread state and parsed attachments."""

from __future__ import annotations

from dataclasses import dataclass

from .email_facts import EmailFacts, extract_email_facts


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
        elif insight.get("limitations"):
            items.append(f"核查附件 {filename} 的解析范围和限制")
    return items


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
