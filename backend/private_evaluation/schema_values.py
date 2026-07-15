"""Frozen production-enum copies for the isolated evaluation schema."""

from __future__ import annotations


CATEGORIES = frozenset({
    "customer_inquiry", "order_followup", "payment", "contract", "complaint",
    "new_product_development", "internal", "marketing", "unknown",
})
RISK_TYPES = frozenset({
    "payment_risk", "delivery_risk", "contract_risk", "quality_risk",
    "security_risk", "commitment_risk", "prompt_injection_risk",
})
ACTION_TYPES = frozenset({
    "reply", "confirm", "prepare_quote", "check_inventory", "check_delivery",
    "escalate", "wait", "ignore",
})
LANGUAGES = frozenset({"zh-CN", "en"})
DIRECTIONS = frozenset({"inbound", "outbound", "thread"})
ATTACHMENT_KINDS = frozenset({"image", "pdf", "xlsx", "docx"})
