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
from backend.private_knowledge.candidate_retention import (
    purge_expired_candidate_batches,
)
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
        self.review.expire_candidate(selected.card_id)

        self.assertIsNone(self.repository.get(selected.card_id))
        self.assertIsNotNone(self.repository.get(unrelated.card_id))

    def test_candidate_batch_expires_after_thirty_days_without_touching_neighbors(self) -> None:
        now = datetime(2026, 7, 14, 13, tzinfo=UTC)
        clock = MutableClock(now)
        candidate_root = self.root / "candidate"
        first = CandidateBatchStore(
            candidate_root, b"C" * 32, batch_id=str(uuid.uuid4()), clock=clock
        )
        adjacent = CandidateBatchStore(
            candidate_root, b"C" * 32, batch_id=str(uuid.uuid4()), clock=clock
        )
        first.write((DetachedCandidate(
            str(uuid.uuid4()), ("Synthetic support.",), ("1", "1")
        ),))
        adjacent.write((DetachedCandidate(
            str(uuid.uuid4()), ("Adjacent synthetic support.",), ("1", "1")
        ),))
        raw_sentinel = self.root / "raw-vault-record.bin"
        raw_sentinel.write_bytes(b"raw-sentinel")

        clock.value = now + timedelta(days=30)
        with self.assertRaisesRegex(PrivateKnowledgeError, "candidate_batch_expired"):
            first.read()

        self.assertFalse(first.path.exists())
        self.assertTrue(adjacent.path.exists())
        self.assertEqual(raw_sentinel.read_bytes(), b"raw-sentinel")

    def test_candidate_discard_reencrypts_neighbors_and_deletes_empty_batch(self) -> None:
        first = DetachedCandidate(
            str(uuid.uuid4()), ("First synthetic support.",), ("1", "1")
        )
        second = DetachedCandidate(
            str(uuid.uuid4()), ("Second synthetic support.",), ("3-5", "2-3")
        )
        store = CandidateBatchStore(
            self.root / "candidate", b"C" * 32, batch_id=str(uuid.uuid4())
        )
        store.write((first, second))

        store.discard(first.candidate_id)
        self.assertEqual(store.read(), (second,))
        store.discard(second.candidate_id)
        store.discard(second.candidate_id)

        self.assertFalse(store.path.exists())

    def test_bounded_retention_purge_removes_only_expired_candidate_batches(self) -> None:
        start = datetime(2026, 7, 14, 13, tzinfo=UTC)
        old = CandidateBatchStore(
            self.root / "candidate", b"C" * 32, batch_id=str(uuid.uuid4()),
            clock=lambda: start,
        )
        current = CandidateBatchStore(
            self.root / "candidate", b"C" * 32, batch_id=str(uuid.uuid4()),
            clock=lambda: start + timedelta(days=1),
        )
        for store, text in ((old, "Old support."), (current, "Current support.")):
            store.write((DetachedCandidate(
                str(uuid.uuid4()), (text,), ("1", "1")
            ),))
        raw_sentinel = self.root / "raw-vault-record.bin"
        raw_sentinel.write_bytes(b"raw-sentinel")

        removed = purge_expired_candidate_batches(
            self.root / "candidate", b"C" * 32,
            clock=lambda: start + timedelta(days=30),
        )

        self.assertEqual(removed, 1)
        self.assertFalse(old.path.exists())
        self.assertTrue(current.path.exists())
        self.assertEqual(raw_sentinel.read_bytes(), b"raw-sentinel")

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
        candidate = DetachedCandidate(
            str(uuid.uuid4()), ("<PERSON_1> requested status.",), ("1", "1")
        )
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

    def test_candidate_batch_binds_evidence_to_each_support_bundle(self) -> None:
        batch_id = str(uuid.uuid4())
        first = DetachedCandidate(
            str(uuid.uuid4()), ("A synthetic delivery request.",), ("1", "1")
        )
        second = DetachedCandidate(
            str(uuid.uuid4()),
            ("Synthetic support one.", "Synthetic support two."),
            ("3-5", "2-3"),
        )
        store = CandidateBatchStore(
            self.root / "candidate", b"C" * 32, batch_id=batch_id
        )

        store.write((first, second))
        loaded = store.read()

        self.assertEqual(loaded[0].evidence, ("1", "1"))
        self.assertEqual(loaded[1].evidence, ("3-5", "2-3"))
        self.assertEqual(loaded[1].support_texts, second.support_texts)

if __name__ == "__main__":
    unittest.main()
