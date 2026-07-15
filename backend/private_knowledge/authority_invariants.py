"""Cross-field authority invariants shared by schema and publication."""

from __future__ import annotations

from datetime import datetime, timedelta

from .errors import PrivateKnowledgeError


_OWNER_REQUIRED = {"price", "payment", "contract", "quality", "legal"}
_ROLES = ("creator", "business", "privacy_security", "accountable_owner")
_CONVERSATION_APPROVABLE = {"3-5", "6-10", "11+"}
_COUNTERPARTY_APPROVABLE = {"2-3", "4-10", "11+"}


def validate_authority_invariants(
    card: object,
    *,
    error_code: str = "schema_invalid",
) -> None:
    try:
        version = card.version
        accountability = card.applicability[0]
        reviews = card.review
        status, created, expires, review_due = card.lifecycle
        present = tuple(item for item in reviews if item is not None)
        if any(
            item.role != _ROLES[index] or item.card_version != version
            for index, item in enumerate(reviews)
            if item is not None
        ):
            raise ValueError
        if len({item.actor_ref for item in present}) != len(present):
            raise ValueError
        if status == "candidate":
            remaining = _timestamp(expires) - _timestamp(created)
            if (review_due is not None or not timedelta(0) < remaining
                    <= timedelta(days=30)):
                raise ValueError
        if status == "approved":
            if reviews[1] is None or reviews[2] is None or review_due is None:
                raise ValueError
            if accountability in _OWNER_REQUIRED and reviews[3] is None:
                raise ValueError
            if expires != review_due:
                raise ValueError
            if (card.evidence[0] not in _CONVERSATION_APPROVABLE
                    or card.evidence[1] not in _COUNTERPARTY_APPROVABLE):
                raise ValueError
            reviewed_at = max(_timestamp(item.approved_at) for item in present[1:])
            due = _timestamp(review_due)
            if not reviewed_at < due <= reviewed_at + timedelta(days=90):
                raise ValueError
    except (AttributeError, IndexError, TypeError, ValueError):
        raise PrivateKnowledgeError(error_code) from None


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value[:-1] + "+00:00")
