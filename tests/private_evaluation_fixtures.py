"""Synthetic-only fixtures for private evaluation tests."""

from __future__ import annotations

import copy
import json
import uuid


CATEGORIES = (
    "customer_inquiry", "order_followup", "payment", "contract", "complaint",
    "new_product_development", "internal", "marketing", "unknown",
)
RISKS = (
    "payment_risk", "delivery_risk", "contract_risk", "quality_risk",
    "security_risk", "commitment_risk", "prompt_injection_risk",
)
ACTIONS = (
    "reply", "confirm", "prepare_quote", "check_inventory", "check_delivery",
    "escalate", "wait", "ignore",
)


def uuid4_for(index: int) -> str:
    return str(uuid.UUID(int=index + 1, version=4))


def approval(role: str, actor_index: int, revision: int = 1) -> dict[str, object]:
    return {
        "actor_ref": uuid4_for(10_000 + actor_index),
        "role": role,
        "approved_at": "2026-07-14T12:00:00Z",
        "case_revision": revision,
    }


def case_mapping(index: int, *, pair: bool = True) -> dict[str, object]:
    category = CATEGORIES[index % len(CATEGORIES)]
    risk_index = index % (len(RISKS) + 1)
    primary_risk = "none" if risk_index == len(RISKS) else RISKS[risk_index]
    mandatory = [] if primary_risk == "none" else [primary_risk]
    return {
        "schema_version": "PrivateEvaluationCaseV1",
        "case_id": uuid4_for(index),
        "revision": 1,
        "approvals": {
            "business": approval("business", index * 3 + 1),
            "privacy": approval("privacy_security", index * 3 + 2),
            "pro_pair": approval("pro_pair", index * 3 + 3) if pair else None,
        },
        "stratum": {
            "category": category,
            "language": ("zh-CN", "en")[index % 2],
            "direction": ("inbound", "outbound", "thread")[index % 3],
            "primary_risk": primary_risk,
        },
        "deidentified_email": {
            "subject": "Current request from <ORGANIZATION_1>",
            "sender": "<EMAIL_1>",
            "recipients": ["<EMAIL_2>"],
            "cc": [],
            "sent_at": "<DATE_1>",
            "thread_text": "Please review the current request and confirm the next safe step.",
            "attachments": [],
        },
        "expected": {
            "category": category,
            "mandatory_risk_types": mandatory,
            "required_action_types": [ACTIONS[index % len(ACTIONS)]],
        },
    }


def dataset_mapping(count: int = 200, *, pair_count: int | None = None) -> dict[str, object]:
    if pair_count is None:
        pair_count = count
    return {
        "schema_version": "PrivateEvaluationDatasetV1",
        "dataset_namespace": uuid4_for(99_000),
        "cases": [case_mapping(index, pair=index < pair_count) for index in range(count)],
    }


def cloned(value: dict[str, object]) -> dict[str, object]:
    return copy.deepcopy(value)


def envelope_json_for(case: object) -> str:
    from backend.email_agent.deepseek_analysis_contract import complete_envelope_example

    envelope = complete_envelope_example()
    expected = case.expected
    analysis = envelope["analysis"]
    analysis["category"] = expected.category
    analysis["risk_flags"] = [
        {
            "type": risk,
            "level": "low",
            "evidence": "当前请求需要人工核查。",
            "recommendation": "请先人工确认再采取行动。",
        }
        for risk in expected.mandatory_risk_types
    ]
    analysis["suggested_actions"] = [
        {
            "type": action,
            "description": "请人工核查当前请求。",
            "owner_hint": "",
            "due_hint": "",
        }
        for action in expected.required_action_types
    ]
    return json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
