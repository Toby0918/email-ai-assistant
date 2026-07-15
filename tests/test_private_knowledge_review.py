"""Review lifecycle and encrypted authority repository tests."""

from __future__ import annotations

import tempfile
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.repository import (
    AUTHORITY_MAGIC,
    CANDIDATE_MAGIC,
    AuthorityRepository,
    CandidateBatchStore,
    DetachedCandidate,
)
from backend.private_knowledge.review import KnowledgeReviewService
from backend.private_knowledge.schema import KnowledgeCardV1
from tests.test_knowledge_card_schema import valid_card


UTC = timezone.utc


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


def card_with(
    *,
    card_id: str | None = None,
    accountability: str = "general",
    conversation_bucket: str = "3-5",
    counterparty_bucket: str = "2-3",
) -> KnowledgeCardV1:
    value = valid_card()
    value["card_id"] = card_id or str(uuid.uuid4())
    value["applicability"]["accountability"] = accountability  # type: ignore[index]
    value["evidence"]["conversation_bucket"] = conversation_bucket  # type: ignore[index]
    value["evidence"]["counterparty_bucket"] = counterparty_bucket  # type: ignore[index]
    return KnowledgeCardV1.from_mapping(value)


class PrivateKnowledgeReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.authority_id = str(uuid.uuid4())
        self.key = b"A" * 32
        self.repository = AuthorityRepository(
            self.root / "authority", self.key, authority_id=self.authority_id
        )
        self.repository.initialize()
        self.clock = MutableClock(datetime(2026, 7, 14, 13, tzinfo=UTC))
        self.review = KnowledgeReviewService(self.repository, clock=self.clock)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_threshold_dual_review_distinct_actors_and_approval_transition(self) -> None:
        card = card_with()
        self.review.create_candidate(card)
        self.review.record_business_approval(card.card_id, "actor-business-001")
        with self.assertRaisesRegex(PrivateKnowledgeError, "actor_not_distinct"):
            self.review.record_privacy_approval(card.card_id, "actor-business-001")
        self.review.record_privacy_approval(card.card_id, "actor-privacy-001")

        approved = self.review.approve(card.card_id)

        self.assertEqual(approved.lifecycle[0], "approved")
        self.assertEqual(
            approved.lifecycle[3], "2026-10-12T13:00:00Z"
        )

        insufficient = card_with(conversation_bucket="2")
        self.review.create_candidate(insufficient)
        self.review.record_business_approval(insufficient.card_id, "actor-business-002")
        self.review.record_privacy_approval(insufficient.card_id, "actor-privacy-002")
        with self.assertRaisesRegex(PrivateKnowledgeError, "evidence_insufficient"):
            self.review.approve(insufficient.card_id)

    def test_accountable_rules_require_separate_owner_approval(self) -> None:
        for accountability in ("price", "payment", "contract", "quality", "legal"):
            card = card_with(accountability=accountability)
            self.review.create_candidate(card)
            self.review.record_business_approval(card.card_id, "actor-business-100")
            self.review.record_privacy_approval(card.card_id, "actor-privacy-100")
            with self.subTest(accountability=accountability), self.assertRaisesRegex(
                PrivateKnowledgeError, "owner_approval_required"
            ):
                self.review.approve(card.card_id)
            self.review.record_owner_approval(card.card_id, "actor-owner-100")
            self.assertEqual(self.review.approve(card.card_id).lifecycle[0], "approved")

    def test_candidate_expiry_rejection_review_due_deprecation_and_revocation(self) -> None:
        expired = card_with()
        self.review.create_candidate(expired)
        self.clock.value = datetime(2026, 8, 13, 12, tzinfo=UTC)
        with self.assertRaisesRegex(PrivateKnowledgeError, "candidate_expired"):
            self.review.approve(expired.card_id)
        self.assertIsNone(self.repository.get(expired.card_id))

        rejected = card_with()
        self.clock.value = datetime(2026, 7, 14, 13, tzinfo=UTC)
        self.review.create_candidate(rejected)
        self.review.reject(rejected.card_id)
        self.assertIsNone(self.repository.get(rejected.card_id))

        approved = card_with()
        self.review.create_candidate(approved)
        self.review.record_business_approval(approved.card_id, "actor-business-200")
        self.review.record_privacy_approval(approved.card_id, "actor-privacy-200")
        self.review.approve(approved.card_id)
        self.assertEqual(len(self.review.publication_candidates()), 1)
        self.clock.value += timedelta(days=90)
        self.assertEqual(self.review.publication_candidates(), ())
        self.review.deprecate(approved.card_id)
        self.assertEqual(self.repository.get(approved.card_id).lifecycle[0], "deprecated")
        self.review.revoke(approved.card_id)
        self.assertEqual(self.repository.get(approved.card_id).lifecycle[0], "revoked")
        with self.assertRaisesRegex(PrivateKnowledgeError, "revoked_terminal"):
            self.review.deprecate(approved.card_id)

    def test_single_item_expiry_does_not_delete_other_expired_candidates(self) -> None:
        selected = card_with()
        unrelated = card_with()
        self.review.create_candidate(selected)
        self.review.create_candidate(unrelated)
        self.clock.value = datetime(2026, 8, 13, 13, tzinfo=UTC)

        self.review.expire_candidate(selected.card_id)

        self.assertIsNone(self.repository.get(selected.card_id))
        self.assertIsNotNone(self.repository.get(unrelated.card_id))

    def test_authority_state_is_encrypted_authenticated_atomic_and_not_candidate_namespace(self) -> None:
        card = card_with()
        self.repository.insert(card)
        state_path = self.root / "authority" / "authority.pkauth"
        ciphertext = state_path.read_bytes()
        self.assertTrue(ciphertext.startswith(AUTHORITY_MAGIC))
        self.assertNotIn(card.generic_rule.encode(), ciphertext)

        wrong = AuthorityRepository(
            self.root / "authority", b"B" * 32, authority_id=self.authority_id
        )
        with self.assertRaisesRegex(PrivateKnowledgeError, "repository_authentication_failed"):
            wrong.get(card.card_id)

        batch_id = str(uuid.uuid4())
        batch = CandidateBatchStore(
            self.root / "candidate", b"C" * 32, batch_id=batch_id
        )
        candidate = DetachedCandidate(str(uuid.uuid4()), "<PERSON_1> requested status.")
        batch.write((candidate,))
        batch_bytes = batch.path.read_bytes()
        self.assertTrue(batch_bytes.startswith(CANDIDATE_MAGIC))
        self.assertNotEqual(AUTHORITY_MAGIC, CANDIDATE_MAGIC)
        with self.assertRaisesRegex(PrivateKnowledgeError, "candidate_authentication_failed"):
            CandidateBatchStore(
                self.root / "candidate", self.key, batch_id=batch_id
            ).read()

        crashing = AuthorityRepository(
            self.root / "authority",
            self.key,
            authority_id=self.authority_id,
            crash_hook=lambda point: (_ for _ in ()).throw(RuntimeError())
            if point == "before_replace" else None,
        )
        with self.assertRaisesRegex(PrivateKnowledgeError, "repository_write_failed"):
            crashing.delete(card.card_id)
        self.assertEqual(self.repository.get(card.card_id), card)


if __name__ == "__main__":
    unittest.main()
