from __future__ import annotations

import json
import sys
import unittest

from backend.cutover_repository_transaction.durable_store import (
    _RepositoryJournalStore,
)
from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)
from backend.cutover_repository_transaction.journal_types import (
    ForwardBoundary,
    RepositoryJournalDirection,
    RepositoryMutationKind,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    build_synthetic_repository_scenario,
    profile_for_review,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class RepositoryTransactionDurableStoreTests(unittest.TestCase):
    def test_intent_is_durable_before_observed_and_committed(self):
        scenario, scope = _bound_scenario()
        try:
            store = _RepositoryJournalStore.begin(scope)
            intent = store.append_intent(
                direction=RepositoryJournalDirection.FORWARD,
                boundary=ForwardBoundary.SOURCE_FROZEN,
                kind=RepositoryMutationKind.VERIFY,
                mutation_index=1,
                before_fingerprint="1" * 64,
                expected_after_fingerprint="2" * 64,
            )

            files = tuple(scenario.journal_root.glob("*.json"))
            self.assertEqual(len(files), 1)
            payload = files[0].read_bytes()
            self.assertEqual(payload, intent.to_canonical_json())
            self.assertNotIn(str(scenario.root).encode(), payload)

            store.append_applied(intent, "5" * 64)
            records = store.verified_records()
            self.assertEqual([item.event for item in records], [
                "intent", "observed", "committed",
            ])
            self.assertEqual(len(tuple(scenario.journal_root.glob("*.json"))), 3)
            for path in scenario.journal_root.glob("*.json"):
                json.loads(path.read_bytes().decode("ascii"))
        finally:
            scenario.close()

    def test_reopen_rejects_a_corrupt_or_noncanonical_prefix(self):
        scenario, scope = _bound_scenario()
        try:
            store = _RepositoryJournalStore.begin(scope)
            store.append_intent(
                direction=RepositoryJournalDirection.FORWARD,
                boundary=ForwardBoundary.SOURCE_FROZEN,
                kind=RepositoryMutationKind.VERIFY,
                mutation_index=1,
                before_fingerprint="3" * 64,
                expected_after_fingerprint="4" * 64,
            )
            record_path = next(scenario.journal_root.glob("*.json"))
            record_path.write_bytes(record_path.read_bytes() + b"\n")

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_journal_invalid$",
            ):
                _RepositoryJournalStore.open_verified(scope)
        finally:
            scenario.close()


def _bound_scenario():
    scenario = build_synthetic_repository_scenario()
    review = _review_test_sandbox(scenario)
    profile = profile_for_review(review)
    authorization = authorization_for(profile, review.operation_fingerprint)
    scope = _bind_test_sandbox_transaction(
        review=review,
        profile=profile,
        authorization=authorization,
        observed_at_epoch=OBSERVED_AT,
    )
    return scenario, scope


if __name__ == "__main__":
    unittest.main()
