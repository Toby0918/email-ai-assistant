from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_repository_transaction import (
    ForwardBoundary,
    RepositoryJournalDirection,
    RepositoryJournalEvent,
    RepositoryJournalOutcome,
    RepositoryJournalRecordV1,
    RepositoryMutationKind,
    ReverseBoundary,
)
from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)


def _fingerprint(label: str) -> str:
    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _record_body(**changes: object) -> dict[str, object]:
    body = {
        "schema_version": 1,
        "sequence": 1,
        "previous_record_hash": "0" * 64,
        "direction": RepositoryJournalDirection.FORWARD.value,
        "boundary": ForwardBoundary.SOURCE_FROZEN.value,
        "mutation_kind": RepositoryMutationKind.VERIFY.value,
        "mutation_index": 1,
        "operation_fingerprint": _fingerprint("operation"),
        "profile_fingerprint": _fingerprint("profile"),
        "governing_master_commit": "a" * 40,
        "authorization_fingerprint": _fingerprint("authorization"),
        "owner_fingerprint": _fingerprint("owner"),
        "before_observation_fingerprint": _fingerprint("before"),
        "expected_after_observation_fingerprint": _fingerprint("after"),
        "observed_effect_fingerprint": "0" * 64,
        "event": RepositoryJournalEvent.INTENT.value,
        "outcome": RepositoryJournalOutcome.PENDING.value,
    }
    return {**body, **changes}


class RepositoryTransactionJournalTests(unittest.TestCase):
    def test_intent_round_trips_as_strict_content_free_canonical_json(self):
        record = RepositoryJournalRecordV1.create(_record_body())

        restored = RepositoryJournalRecordV1.from_json(
            record.to_canonical_json()
        )

        self.assertEqual(restored.record_hash, record.record_hash)
        self.assertEqual(restored.sequence, 1)
        self.assertNotIn(_fingerprint("operation"), repr(record))
        self.assertNotIn("source_frozen", repr(record).casefold())

    def test_observed_and_committed_require_actual_nonzero_observation(self):
        actual = _fingerprint("actual")
        for event in (
            RepositoryJournalEvent.OBSERVED,
            RepositoryJournalEvent.COMMITTED,
        ):
            with self.subTest(event=event):
                record = RepositoryJournalRecordV1.create(
                    _record_body(
                        event=event.value,
                        outcome=RepositoryJournalOutcome.APPLIED.value,
                        observed_effect_fingerprint=actual,
                    )
                )
                self.assertEqual(
                    record.observed_effect_fingerprint,
                    actual,
                )

        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_journal_invalid$",
        ):
            RepositoryJournalRecordV1.create(
                _record_body(
                    event=RepositoryJournalEvent.OBSERVED.value,
                    outcome=RepositoryJournalOutcome.APPLIED.value,
                    observed_effect_fingerprint="0" * 64,
                )
            )

    def test_aborted_requires_exact_before_observation(self):
        before = _fingerprint("before")
        record = RepositoryJournalRecordV1.create(
            _record_body(
                event=RepositoryJournalEvent.ABORTED.value,
                outcome=RepositoryJournalOutcome.NOT_APPLIED.value,
                observed_effect_fingerprint=before,
            )
        )
        self.assertEqual(record.observed_effect_fingerprint, before)

        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_journal_invalid$",
        ):
            RepositoryJournalRecordV1.create(
                _record_body(
                    event=RepositoryJournalEvent.ABORTED.value,
                    outcome=RepositoryJournalOutcome.NOT_APPLIED.value,
                    observed_effect_fingerprint=_fingerprint("wrong"),
                )
            )

    def test_direction_requires_its_closed_boundary_enum(self):
        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_journal_invalid$",
        ):
            RepositoryJournalRecordV1.create(
                _record_body(
                    direction=RepositoryJournalDirection.REVERSE.value,
                    boundary=ForwardBoundary.SOURCE_FROZEN.value,
                )
            )

        reverse = RepositoryJournalRecordV1.create(
            _record_body(
                direction=RepositoryJournalDirection.REVERSE.value,
                boundary=ReverseBoundary.NEW_STATE_PRESERVED.value,
            )
        )
        self.assertEqual(
            reverse.boundary,
            ReverseBoundary.NEW_STATE_PRESERVED.value,
        )

    def test_unknown_duplicate_and_raw_fields_fail_closed(self):
        record = RepositoryJournalRecordV1.create(_record_body())
        mapping = record.to_mapping()
        mapping["path"] = "synthetic-path"
        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_journal_invalid$",
        ):
            RepositoryJournalRecordV1.from_mapping(mapping)

        payload = record.to_canonical_json().decode("ascii")
        duplicate = payload.replace(
            '"sequence":1',
            '"sequence":1,"sequence":1',
        ).encode("ascii")
        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_journal_invalid$",
        ):
            RepositoryJournalRecordV1.from_json(duplicate)

        noncanonical = json.dumps(record.to_mapping()).encode("ascii")
        with self.assertRaisesRegex(
            RepositoryTransactionError,
            "^repository_journal_invalid$",
        ):
            RepositoryJournalRecordV1.from_json(noncanonical)


if __name__ == "__main__":
    unittest.main()
