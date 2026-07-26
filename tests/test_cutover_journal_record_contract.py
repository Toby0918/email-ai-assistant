"""Issue #52 canonical journal record contract tests."""

from __future__ import annotations

import unittest

from backend.cutover_journal import (
    JournalContractError,
    JournalEventCode,
    JournalRecordV1,
    JournalStepCode,
)
from tests.cutover_journal_fixtures import (
    HostileComparison,
    opaque_fingerprint,
    valid_journal_record_body,
    valid_observed_record_body,
)


class JournalRecordContractTests(unittest.TestCase):
    def test_valid_record_is_canonical_immutable_and_hash_bound(self) -> None:
        record = JournalRecordV1.create(valid_journal_record_body())

        restored = JournalRecordV1.from_json(record.to_canonical_json())

        self.assertEqual(restored, record)
        self.assertEqual(restored.to_mapping(), record.to_mapping())
        self.assertEqual(len(record.record_hash), 64)
        self.assertNotIn(record.operation_fingerprint, repr(record))
        self.assertFalse(hasattr(record, "__dict__"))

    def test_step_and_event_codes_are_synthetic_and_closed(self) -> None:
        self.assertEqual(
            tuple(item.value for item in JournalStepCode),
            ("SYNTHETIC_PREPARE", "SYNTHETIC_PUBLISH"),
        )
        self.assertEqual(
            tuple(item.value for item in JournalEventCode),
            ("INTENT", "RESUME_BOUND", "EFFECT_OBSERVED", "COMMITTED"),
        )
        resumed = valid_journal_record_body()
        resumed["event_code"] = "RESUME_BOUND"
        resumed["authorization_fingerprint"] = opaque_fingerprint(9)

        self.assertEqual(
            JournalRecordV1.create(resumed).event_code,
            "RESUME_BOUND",
        )

    def test_event_outcome_direction_and_authorization_matrix_is_closed(
        self,
    ) -> None:
        cases = (
            valid_observed_record_body(),
            valid_observed_record_body(event_code="COMMITTED"),
            valid_observed_record_body(outcome="NOT_APPLIED"),
            valid_observed_record_body(direction="REVERSE"),
        )
        for value in cases:
            with self.subTest(
                event=value["event_code"],
                direction=value["direction"],
                outcome=value["effect_outcome"],
            ):
                self.assertEqual(
                    JournalRecordV1.create(value).effect_outcome,
                    value["effect_outcome"],
                )

        invalid_cases = []
        for field, invalid in (
            ("event_code", "UNKNOWN"),
            ("direction", "SIDEWAYS"),
            ("step_code", "ARBITRARY"),
            ("effect_outcome", "UNKNOWN"),
        ):
            value = valid_journal_record_body()
            value[field] = invalid
            invalid_cases.append(value)
        pending_observed = valid_observed_record_body()
        pending_observed["effect_outcome"] = "PENDING"
        invalid_cases.append(pending_observed)
        blind_reverse = valid_observed_record_body(direction="REVERSE")
        blind_reverse["authorization_fingerprint"] = blind_reverse[
            "forward_authorization_fingerprint"
        ]
        invalid_cases.append(blind_reverse)

        for value in invalid_cases:
            with self.assertRaisesRegex(
                JournalContractError, "^JOURNAL_RECORD_INVALID$"
            ):
                JournalRecordV1.create(value)

    def test_parser_fails_closed_on_hostile_or_noncanonical_record(self) -> None:
        record = JournalRecordV1.create(valid_journal_record_body())
        hostile = valid_journal_record_body()
        hostile["record_type"] = HostileComparison()
        tampered = record.to_mapping()
        tampered["owner_fingerprint"] = "f" * 64
        duplicate = record.to_canonical_json().replace(
            b'{"authorization_fingerprint":',
            b'{"sequence":1,"authorization_fingerprint":',
        )
        noncanonical = record.to_canonical_json().replace(b",", b", ", 1)

        invalid_values = (
            lambda: JournalRecordV1.create(hostile),
            lambda: JournalRecordV1.from_mapping(tampered),
            lambda: JournalRecordV1.from_json(duplicate),
            lambda: JournalRecordV1.from_json(noncanonical),
            lambda: JournalRecordV1.from_json(b'{"record_type":'),
        )
        for operation in invalid_values:
            with self.assertRaisesRegex(
                JournalContractError, "^JOURNAL_RECORD_INVALID$"
            ):
                operation()


if __name__ == "__main__":
    unittest.main()
