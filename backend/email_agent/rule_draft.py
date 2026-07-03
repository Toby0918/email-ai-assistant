"""Rule-based English reply draft construction."""

from __future__ import annotations

from typing import Any

from .email_facts import EmailFacts


def build_reply_draft(
    subject: str,
    category: str,
    actions: list[dict[str, str]],
    is_meeting: bool,
    is_booking: bool,
    facts: EmailFacts,
) -> dict[str, Any]:
    action_types = [item["type"] for item in actions]
    body_lines = ["Hello,", "", "Thank you for your email."]
    body_lines.extend(_draft_lines(action_types, category, is_meeting, is_booking, facts))
    body_lines.extend(["", "Best regards"])
    return {
        "subject": _draft_subject(subject),
        "body": "\n".join(body_lines),
        "needs_human_review": True,
        "review_reasons": ["第一版回复草稿必须人工审核后再使用。"],
    }


def _draft_subject(subject: str) -> str:
    clean_subject = " ".join(subject.split()).strip()
    if clean_subject and not _contains_chinese_char(clean_subject):
        return f"Re: {clean_subject}"
    return "Re: your email"


def _draft_lines(
    action_types: list[str],
    category: str,
    is_meeting: bool,
    is_booking: bool,
    facts: EmailFacts,
) -> list[str]:
    details = _english_fact_clause(facts)
    target = f" for {details}" if details else ""
    lines: list[str] = []
    if "confirm" in action_types and is_meeting:
        lines.append("We will first verify whether this meeting invitation is valid and whether attendance is needed.")
    if "check_delivery" in action_types:
        lines.append(_delivery_draft_line(is_booking, target))
    if "prepare_quote" in action_types:
        if category == "new_product_development":
            lines.append(
                "We will review the project scope and assess feasibility against the requested cost target before sharing any technical or commercial feedback."
            )
        else:
            lines.append("We will prepare the quote details for human review before sharing any price or lead time.")
    if "escalate" in action_types:
        lines.append(_escalation_draft_line(category, target, facts))
    if "confirm" in action_types and category == "payment":
        lines.append("We will verify the invoice, payment, or remittance status before replying.")
    if "confirm" in action_types and category == "contract":
        lines.append("We will review the contract terms with the responsible reviewer before replying.")
    if "ignore" in action_types:
        lines.append("No business reply appears necessary based on the current message.")
    if category == "internal" and not lines:
        lines.append("We will complete the internal review before anyone replies externally.")
    return lines or ["We will draft a cautious response for human review before replying."]


def _delivery_draft_line(is_booking: bool, target: str) -> str:
    if is_booking:
        return f"We will check the booking, FE, and tracking details{target} with the responsible logistics owner."
    return f"We will check the delivery or shipment status{target} before confirming any timing."


def _escalation_draft_line(category: str, target: str, facts: EmailFacts) -> str:
    deadline = f" {facts.deadlines[0]}" if facts.deadlines else ""
    if category == "complaint":
        return f"We will escalate the quality issue{target} and prepare the RCA and corrective action response for human review{deadline}."
    return f"We will escalate this risk{target} to the responsible owner before replying."


def _english_fact_clause(facts: EmailFacts) -> str:
    items = [*facts.references, *facts.quantities, *facts.measurements, *facts.quality_issues[:1], *facts.requested_actions[:1], *facts.deadlines]
    return "; ".join(item for item in _unique(items) if not _contains_chinese_char(item))


def _contains_chinese_char(value: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in value)


def _unique(items: list[str]) -> list[str]:
    values: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.lower()
        if key not in seen:
            values.append(item)
            seen.add(key)
    return values
