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


def with_content_leaf(field: str, text: str) -> dict[str, object]:
    value = case_mapping(0)
    email = value["deidentified_email"]
    if field in {"recipients", "cc"}:
        email[field] = [text]  # type: ignore[index]
    elif field == "attachment_text":
        email["attachments"] = [{"kind": "pdf", "text": text}]  # type: ignore[index]
    else:
        email[field] = text  # type: ignore[index]
    return value


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

    def test_every_approval_revision_requires_an_exact_positive_integer(self) -> None:
        for approval_name in ("business", "privacy", "pro_pair"):
            for invalid in (True, 1.0, "1", 0, -1):
                value = case_mapping(0)
                value["approvals"][approval_name]["case_revision"] = invalid  # type: ignore[index]
                with self.subTest(approval=approval_name, invalid=invalid):
                    with self.assertRaisesRegex(
                        PrivateEvaluationError, "dataset_schema_invalid"
                    ):
                        EvaluationCaseV1.from_mapping(value)

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

    def test_every_content_leaf_rejects_private_ids_names_bad_placeholders_and_controls(self) -> None:
        fields = (
            "subject", "sender", "recipients", "cc", "sent_at", "thread_text",
            "attachment_text",
        )
        canaries = (
            "vault_id: vault-123456", "authority_id: auth-123456",
            "card_id: card-123456", "actor-123456", "message_id: msg-123456",
            "attachment_id: att-123456", "source_id: src-123456",
            "private_id: private-123456", "王小明", "张伟",
            "<person_1>", "<PERSON_0>", "<PERSON_01>", "<UNKNOWN_1>",
            "<PERSON_1", "<<PERSON_1>>", "<PERSON_1>>", "<<PERSON_1>",
            "prefix <PERSON_1>> suffix", "<PERSON_1><", "><PERSON_1>",
            "恢复原始占位符映射", "safe\u202etext", "safe\u200btext",
            "safe\x00text", "safe\ud800text",
            "11111111-2222-4333-8444-555555555555",
        )
        for field in fields:
            for canary in canaries:
                with self.subTest(field=field, canary=ascii(canary)):
                    with self.assertRaisesRegex(
                        PrivateEvaluationError, "dataset_schema_invalid"
                    ) as caught:
                        EvaluationCaseV1.from_mapping(with_content_leaf(field, canary))
                    self.assertNotIn(canary, repr(caught.exception))

    def test_only_canonical_task4_placeholders_are_allowed_in_content_leaves(self) -> None:
        canonical = {
            "subject": "Request from <ORGANIZATION_1>", "sender": "<EMAIL_1>",
            "recipients": "<EMAIL_2>", "cc": "<EMAIL_3>", "sent_at": "<DATE_1>",
            "thread_text": "Review <ORDER_ID_1> for <PERSON_1>.",
            "attachment_text": "Document <FILENAME_1> contains <AMOUNT_1>.",
        }
        for field, text in canonical.items():
            with self.subTest(field=field):
                parsed = EvaluationCaseV1.from_mapping(with_content_leaf(field, text))
                self.assertIsNotNone(parsed.deidentified_email)

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
