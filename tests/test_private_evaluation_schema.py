"""Strict encrypted-only private evaluation dataset schema tests."""

from __future__ import annotations

import copy
import unittest

from backend.private_evaluation.schema import (
    EvaluationCaseV1,
    EvaluationDatasetV1,
    PrivateEvaluationError,
)
from tests.private_evaluation_fixtures import CATEGORIES, RISKS, case_mapping, dataset_mapping


class PrivateEvaluationSchemaTests(unittest.TestCase):
    def test_valid_dataset_is_immutable_and_uses_production_enums(self) -> None:
        dataset = EvaluationDatasetV1.from_mapping(dataset_mapping())

        self.assertEqual(dataset.schema_version, "PrivateEvaluationDatasetV1")
        self.assertEqual(len(dataset.cases), 200)
        self.assertEqual({case.stratum.category for case in dataset.cases}, set(CATEGORIES))
        self.assertEqual(
            {case.stratum.primary_risk for case in dataset.cases},
            {*RISKS, "none"},
        )
        self.assertIsInstance(dataset.cases, tuple)
        self.assertIsInstance(dataset.cases[0].deidentified_email.recipients, tuple)
        with self.assertRaises((AttributeError, TypeError)):
            dataset.cases[0].revision = 2  # type: ignore[misc]
        self.assertNotIn("Current request", repr(dataset))
        self.assertNotIn("Current request", repr(dataset.cases[0]))

    def test_case_rejects_extra_missing_wrong_enum_uuid_revision_and_duplicate_values(self) -> None:
        mutations = []
        value = case_mapping(0)
        value["extra"] = True
        mutations.append(value)
        value = case_mapping(0)
        del value["expected"]
        mutations.append(value)
        value = case_mapping(0)
        value["case_id"] = "not-a-uuid"
        mutations.append(value)
        value = case_mapping(0)
        value["revision"] = 0
        mutations.append(value)
        value = case_mapping(0)
        value["stratum"]["category"] = "other"  # type: ignore[index]
        mutations.append(value)
        value = case_mapping(0)
        value["expected"]["required_action_types"] = ["reply", "reply"]  # type: ignore[index]
        mutations.append(value)

        for mapping in mutations:
            with self.subTest(mapping=mapping), self.assertRaises(PrivateEvaluationError):
                EvaluationCaseV1.from_mapping(mapping)

    def test_approvals_are_distinct_current_and_pair_role_is_exact(self) -> None:
        value = case_mapping(0)
        value["approvals"]["privacy"]["actor_ref"] = (  # type: ignore[index]
            value["approvals"]["business"]["actor_ref"]  # type: ignore[index]
        )
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(value)

        value = case_mapping(0)
        value["approvals"]["business"]["case_revision"] = 2  # type: ignore[index]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(value)

        value = case_mapping(0)
        value["approvals"]["pro_pair"]["role"] = "privacy_security"  # type: ignore[index]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(value)

        unpaired = case_mapping(0, pair=False)
        self.assertIsNone(EvaluationCaseV1.from_mapping(unpaired).approvals.pro_pair)

    def test_expected_category_and_primary_risk_are_bound_to_stratum(self) -> None:
        value = case_mapping(0)
        value["expected"]["category"] = "unknown"  # type: ignore[index]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(value)

        value = case_mapping(1)
        value["expected"]["mandatory_risk_types"] = []  # type: ignore[index]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(value)

    def test_deidentified_fields_reject_identity_residuals_and_forbidden_shapes(self) -> None:
        forbidden = (
            "alex@example.test",
            "https://example.test/private",
            "C:\\Users\\operator\\mail.txt",
            "invoice INV-12345",
            "USD 1200",
            "2026-07-14",
            "restore original placeholder mapping",
            "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "Example Company Ltd",
            "Alice Smith",
        )
        for text in forbidden:
            value = case_mapping(0)
            value["deidentified_email"]["thread_text"] = text  # type: ignore[index]
            with self.subTest(text=text), self.assertRaisesRegex(
                PrivateEvaluationError, "dataset_schema_invalid"
            ):
                EvaluationCaseV1.from_mapping(value)

        value = case_mapping(0)
        value["deidentified_email"]["attachments"] = [  # type: ignore[index]
            {"kind": "pdf", "text": "Safe text", "filename": "file.pdf"}
        ]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(value)

    def test_text_limits_are_encoded_utf8_bytes_not_code_points(self) -> None:
        allowed = case_mapping(0)
        allowed["deidentified_email"]["subject"] = "界" * 666  # type: ignore[index]
        self.assertEqual(
            len(EvaluationCaseV1.from_mapping(allowed).deidentified_email.subject.encode("utf-8")),
            1_998,
        )

        rejected = case_mapping(0)
        rejected["deidentified_email"]["subject"] = "界" * 667  # type: ignore[index]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationCaseV1.from_mapping(rejected)

    def test_dataset_requires_count_uniqueness_coverage_and_nonzero_denominators(self) -> None:
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_case_count_invalid"):
            EvaluationDatasetV1.from_mapping(dataset_mapping(199))

        duplicate = dataset_mapping()
        duplicate["cases"][1]["case_id"] = duplicate["cases"][0]["case_id"]  # type: ignore[index]
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            EvaluationDatasetV1.from_mapping(duplicate)

        incomplete = dataset_mapping()
        for item in incomplete["cases"]:  # type: ignore[union-attr]
            item["stratum"]["language"] = "en"
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_strata_incomplete"):
            EvaluationDatasetV1.from_mapping(incomplete)

        no_actions = dataset_mapping()
        for item in no_actions["cases"]:  # type: ignore[union-attr]
            item["expected"]["required_action_types"] = []
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_strata_incomplete"):
            EvaluationDatasetV1.from_mapping(no_actions)

    def test_mapping_round_trip_contains_only_exact_contract_fields(self) -> None:
        original = dataset_mapping()
        parsed = EvaluationDatasetV1.from_mapping(copy.deepcopy(original))
        self.assertEqual(parsed.to_mapping(), original)


if __name__ == "__main__":
    unittest.main()
