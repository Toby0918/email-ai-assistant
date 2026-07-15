"""Human review and lifecycle transitions for private knowledge cards."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from .errors import PrivateKnowledgeError
from .repository import AuthorityRepository
from .schema import KnowledgeCardV1


_OWNER_REQUIRED = {"price", "payment", "contract", "quality", "legal"}
_CONVERSATION_APPROVABLE = {"3-5", "6-10", "11+"}
_COUNTERPARTY_APPROVABLE = {"2-3", "4-10", "11+"}


class KnowledgeReviewService:
    def __init__(
        self,
        repository: AuthorityRepository,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        if not isinstance(repository, AuthorityRepository):
            raise PrivateKnowledgeError("repository_invalid")
        self._repository = repository
        self._clock = clock

    def create_candidate(self, card: KnowledgeCardV1) -> None:
        if not isinstance(card, KnowledgeCardV1) or card.lifecycle[0] != "candidate":
            raise PrivateKnowledgeError("candidate_invalid")
        created = _parse_time(card.lifecycle[1])
        expires = _parse_time(card.lifecycle[2])
        remaining = expires - created
        if (not timedelta(0) < remaining <= timedelta(days=30)
                or self._now() >= expires):
            raise PrivateKnowledgeError("candidate_expired")
        if card.lifecycle[3] is not None or any(card.review[index] for index in (1, 2, 3)):
            raise PrivateKnowledgeError("candidate_invalid")
        self._repository.insert(card)

    def record_business_approval(self, card_id: str, actor_ref: str) -> KnowledgeCardV1:
        return self._record_approval(card_id, actor_ref, 1, "business")

    def record_privacy_approval(self, card_id: str, actor_ref: str) -> KnowledgeCardV1:
        return self._record_approval(card_id, actor_ref, 2, "privacy_security")

    def record_owner_approval(self, card_id: str, actor_ref: str) -> KnowledgeCardV1:
        card = self._candidate(card_id)
        if card.applicability[0] not in _OWNER_REQUIRED:
            raise PrivateKnowledgeError("owner_approval_not_required")
        return self._record_approval(card_id, actor_ref, 3, "accountable_owner")

    def approve(self, card_id: str) -> KnowledgeCardV1:
        card = self._candidate(card_id)
        if card.evidence[0] not in _CONVERSATION_APPROVABLE or card.evidence[1] not in _COUNTERPARTY_APPROVABLE:
            raise PrivateKnowledgeError("evidence_insufficient")
        creator, business, privacy, owner = card.review
        if business is None or privacy is None:
            raise PrivateKnowledgeError("approval_incomplete")
        if card.applicability[0] in _OWNER_REQUIRED and owner is None:
            raise PrivateKnowledgeError("owner_approval_required")
        if len({item.actor_ref for item in (creator, business, privacy, owner) if item}) < (4 if owner else 3):
            raise PrivateKnowledgeError("actor_not_distinct")
        now = self._now()
        reviewed_at = max(
            _parse_time(item.approved_at)
            for item in (business, privacy, owner) if item is not None
        )
        due = min(now + timedelta(days=90), reviewed_at + timedelta(days=90))
        mapping = card.to_mapping()
        mapping["lifecycle"] = {
            "status": "approved", "created_at": card.lifecycle[1],
            "expires_at": _format_time(due), "review_due_at": _format_time(due),
        }
        return self._replace(mapping)

    def reject(self, card_id: str) -> None:
        card = self._repository.get(card_id)
        if card is None:
            return
        self._candidate(card_id)
        self._repository.delete(card_id)

    def expire(self) -> tuple[str, ...]:
        expired: list[str] = []
        now = self._now()
        for card in self._repository.list_cards():
            if card.lifecycle[0] == "candidate" and now >= _parse_time(card.lifecycle[2]):
                self._repository.delete(card.card_id)
                expired.append(card.card_id)
        return tuple(expired)

    def expire_candidate(self, card_id: str) -> None:
        card = self._repository.get(card_id)
        if card is None:
            return
        if (card.lifecycle[0] != "candidate"
                or self._now() < _parse_time(card.lifecycle[2])):
            raise PrivateKnowledgeError("candidate_not_expired")
        self._repository.delete(card.card_id)

    def deprecate(self, card_id: str) -> KnowledgeCardV1:
        card = self._existing(card_id)
        if card.lifecycle[0] == "revoked":
            raise PrivateKnowledgeError("revoked_terminal")
        if card.lifecycle[0] not in {"approved", "deprecated"}:
            raise PrivateKnowledgeError("transition_invalid")
        return self._status(card, "deprecated")

    def revoke(self, card_id: str) -> KnowledgeCardV1:
        card = self._existing(card_id)
        if card.lifecycle[0] == "revoked":
            raise PrivateKnowledgeError("revoked_terminal")
        return self._status(card, "revoked")

    def publication_candidates(self) -> tuple[KnowledgeCardV1, ...]:
        now = self._now()
        cards = []
        for card in self._repository.list_cards():
            due = card.lifecycle[3]
            if (card.lifecycle[0] == "approved" and due is not None
                    and now < _parse_time(due) and now < _parse_time(card.lifecycle[2])):
                cards.append(card)
        return tuple(sorted(cards, key=lambda item: item.card_id))

    def _record_approval(
        self, card_id: str, actor_ref: str, slot: int, role: str
    ) -> KnowledgeCardV1:
        card = self._candidate(card_id)
        if not isinstance(actor_ref, str) or not actor_ref.startswith("actor-"):
            raise PrivateKnowledgeError("actor_invalid")
        existing = [item.actor_ref for item in card.review if item is not None]
        if actor_ref in existing:
            raise PrivateKnowledgeError("actor_not_distinct")
        mapping = card.to_mapping()
        review = mapping["review"]
        review[{1: "business", 2: "privacy", 3: "owner"}[slot]] = {
            "actor_ref": actor_ref, "role": role,
            "approved_at": _format_time(self._now()), "card_version": card.version,
        }
        return self._replace(mapping)

    def _candidate(self, card_id: str) -> KnowledgeCardV1:
        card = self._existing(card_id)
        if card.lifecycle[0] != "candidate":
            raise PrivateKnowledgeError("transition_invalid")
        if self._now() >= _parse_time(card.lifecycle[2]):
            self._repository.delete(card.card_id)
            raise PrivateKnowledgeError("candidate_expired")
        return card

    def _existing(self, card_id: str) -> KnowledgeCardV1:
        card = self._repository.get(card_id)
        if card is None:
            raise PrivateKnowledgeError("card_missing")
        return card

    def _status(self, card: KnowledgeCardV1, status: str) -> KnowledgeCardV1:
        mapping = card.to_mapping()
        lifecycle = mapping["lifecycle"]
        lifecycle["status"] = status
        return self._replace(mapping)

    def _replace(self, mapping: dict[str, object]) -> KnowledgeCardV1:
        card = KnowledgeCardV1.from_mapping(mapping)
        self._repository.replace(card)
        return card

    def _now(self) -> datetime:
        try:
            value = self._clock()
        except Exception:
            raise PrivateKnowledgeError("clock_invalid") from None
        if not isinstance(value, datetime) or value.utcoffset() != timedelta(0) or value.microsecond:
            raise PrivateKnowledgeError("clock_invalid")
        return value


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, TypeError):
        raise PrivateKnowledgeError("timestamp_invalid") from None


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
