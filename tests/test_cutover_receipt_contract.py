"""Issue #51 canonical content-free receipt contract tests."""

from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverContractError,
    CutoverProfileV1,
    ReceiptEnvelopeV1,
    ReceiptStatus,
    ReceiptType,
    validate_real_host_authorization,
)
from tests.cutover_contract_fixtures import (
    GOVERNING_MASTER,
    HostileComparison,
    HostileKey,
    canonical_json,
    opaque_fingerprint,
    valid_profile_body,
)


RECEIPT_CASES = (
    (
        "PreflightReceiptV1",
        "PREFLIGHT_ACCEPTED",
        "real_preflight",
        "real_preflight_composition",
        "operation",
        ("profile", "authorization", "policy"),
        {"accepted": 1, "rejected": 0},
        {"observation_kind": "current_topology"},
    ),
    (
        "EvidenceReceiptV1",
        "EVIDENCE_ACCEPTED",
        "evidence_publication",
        "evidence_publication_composition",
        "evidence_package",
        ("profile", "authorization", "review"),
        {"packages": 1, "verified": 1, "rejected": 0},
        {"evidence_stage": "verification"},
    ),
    (
        "AclReceiptV1",
        "ACL_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "acl_policy",
        ("profile", "authorization", "policy", "source_observation"),
        {"accepted": 1, "rejected": 0},
        {"acl_scope": "container"},
    ),
    (
        "RepositoryReceiptV1",
        "REPOSITORY_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "repository_root",
        ("profile", "authorization", "prior_receipt", "source_observation"),
        {"accepted": 1, "rejected": 0},
        {"repository_stage": "final_verified"},
    ),
    (
        "WorktreeReceiptV1",
        "WORKTREE_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "worktree_roster",
        ("profile", "authorization", "prior_receipt", "source_observation"),
        {"worktrees": 11, "rejected": 0},
        {"worktree_stage": "final_verified"},
    ),
    (
        "RuntimeReceiptV1",
        "RUNTIME_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "runtime",
        ("profile", "authorization", "artifact", "policy"),
        {"components": 2, "rejected": 0},
        {"runtime_stage": "published"},
    ),
    (
        "DatabaseReceiptV1",
        "DATABASE_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "database",
        ("profile", "authorization", "source_observation", "policy"),
        {"databases": 1, "rejected": 0},
        {"database_stage": "verified"},
    ),
    (
        "ArtifactReceiptV1",
        "ARTIFACT_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "browser_extension",
        ("profile", "authorization", "artifact", "review"),
        {"artifacts": 1, "rejected": 0},
        {"artifact_kind": "browser_extension", "artifact_stage": "verified"},
    ),
    (
        "ConfigReceiptV1",
        "CONFIG_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "config",
        ("profile", "authorization", "config", "policy"),
        {"configurations": 1, "rejected": 0},
        {"config_stage": "verified"},
    ),
    (
        "ActivationReceiptV1",
        "ACTIVATION_ACCEPTED",
        "cutover_execution",
        "cutover_transaction_composition",
        "service",
        ("profile", "authorization", "prior_receipt", "config"),
        {"completed": 1, "failed": 0, "provider_attempts": 0},
        {"activation_stage": "rules_verified"},
    ),
    (
        "RollbackReceiptV1",
        "ROLLBACK_ACCEPTED",
        "recovery",
        "cutover_transaction_composition",
        "rollback",
        ("profile", "authorization", "journal", "prior_receipt"),
        {"completed": 1, "failed": 0},
        {"rollback_stage": "legacy_health_verified"},
    ),
    (
        "IncidentStopReceiptV1",
        "INCIDENT_STOP",
        "recovery",
        "cutover_transaction_composition",
        "operation",
        ("profile", "authorization", "journal", "source_observation"),
        {"incidents": 1},
        {"incident_class": "identity_ambiguous"},
    ),
)


def receipt_body(case=RECEIPT_CASES[0]) -> dict[str, object]:
    (
        receipt_type,
        status,
        operation,
        producer,
        subject_role,
        input_roles,
        counts,
        details,
    ) = case
    return {
        "receipt_type": receipt_type,
        "status": status,
        "operation": operation,
        "operation_fingerprint": opaque_fingerprint(301),
        "profile_fingerprint": opaque_fingerprint(302),
        "governing_master_commit": GOVERNING_MASTER,
        "authorization_fingerprint": opaque_fingerprint(303),
        "producer": producer,
        "subject_role": subject_role,
        "input_fingerprints": [
            {"role": role, "fingerprint": opaque_fingerprint(310 + index)}
            for index, role in enumerate(input_roles)
        ],
        "observation_fingerprint": opaque_fingerprint(350),
        "counts": dict(counts),
        "validity": {
            "issued_at_epoch": 1_800_000_000,
            "expires_at_epoch": 1_800_000_600,
        },
        "details": dict(details),
    }


class CutoverReceiptContractTests(unittest.TestCase):
    def test_all_required_receipt_status_families_are_closed_and_round_trip(
        self,
    ) -> None:
        expected_types = {case[0] for case in RECEIPT_CASES}
        expected_statuses = {case[1] for case in RECEIPT_CASES}

        self.assertEqual({item.value for item in ReceiptType}, expected_types)
        self.assertTrue(expected_statuses <= {item.value for item in ReceiptStatus})
        for case in RECEIPT_CASES:
            with self.subTest(receipt_type=case[0]):
                receipt = ReceiptEnvelopeV1.create(receipt_body(case))
                self.assertEqual(receipt.receipt_type, case[0])
                self.assertEqual(
                    ReceiptEnvelopeV1.from_json(
                        receipt.to_canonical_json()
                    ),
                    receipt,
                )

    def test_receipt_has_stable_golden_fingerprint_and_canonical_json(self) -> None:
        body = receipt_body()
        receipt = ReceiptEnvelopeV1.create(body)
        expected = hashlib.sha256(canonical_json(body)).hexdigest()

        self.assertEqual(receipt.receipt_fingerprint, expected)
        self.assertEqual(
            receipt.to_canonical_json(),
            canonical_json({**body, "receipt_fingerprint": expected}),
        )
        self.assertTrue(receipt.to_canonical_json().isascii())
        self.assertEqual(ReceiptEnvelopeV1.from_mapping(receipt.to_mapping()), receipt)

    def test_receipt_parser_rejects_duplicate_unknown_noncanonical_and_tampered(
        self,
    ) -> None:
        receipt = ReceiptEnvelopeV1.create(receipt_body())
        canonical = receipt.to_canonical_json()
        duplicate_top = canonical.replace(
            b'{"authorization_fingerprint":',
            b'{"status":"PREFLIGHT_ACCEPTED","authorization_fingerprint":',
            1,
        )
        duplicate_nested = canonical.replace(
            b'"counts":{"accepted":1,',
            b'"counts":{"accepted":1,"accepted":1,',
            1,
        )
        unknown = receipt.to_mapping()
        unknown["message"] = "not allowed"
        tampered = receipt.to_mapping()
        tampered["observation_fingerprint"] = opaque_fingerprint(399)
        pretty = json.dumps(receipt.to_mapping(), indent=2).encode("utf-8")
        lone_surrogate = canonical.replace(
            b'"receipt_type":"PreflightReceiptV1"',
            b'"receipt_type":"\\ud800"',
            1,
        )

        for payload in (
            duplicate_top,
            duplicate_nested,
            canonical + b"\n",
            pretty,
            lone_surrogate,
        ):
            with self.subTest(payload=payload[:40]):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^RECEIPT_CONTRACT_INVALID$",
                ):
                    ReceiptEnvelopeV1.from_json(payload)
        for value in (unknown, tampered):
            with self.assertRaisesRegex(
                CutoverContractError,
                "^RECEIPT_CONTRACT_INVALID$",
            ):
                ReceiptEnvelopeV1.from_mapping(value)

    def test_receipt_type_matrix_rejects_cross_family_and_open_details(
        self,
    ) -> None:
        mutations = []
        wrong_status = receipt_body()
        wrong_status["status"] = "DATABASE_ACCEPTED"
        mutations.append(wrong_status)
        wrong_operation = receipt_body()
        wrong_operation["operation"] = "cutover_execution"
        mutations.append(wrong_operation)
        wrong_producer = receipt_body()
        wrong_producer["producer"] = "cutover_transaction_composition"
        mutations.append(wrong_producer)
        wrong_subject = receipt_body()
        wrong_subject["subject_role"] = "repository_root"
        mutations.append(wrong_subject)
        unknown_count = receipt_body()
        unknown_count["counts"]["paths"] = 1
        mutations.append(unknown_count)
        open_details = receipt_body()
        open_details["details"]["message"] = "D:\\private"
        mutations.append(open_details)
        wrong_inputs = receipt_body()
        wrong_inputs["input_fingerprints"][0]["role"] = "raw_path"
        mutations.append(wrong_inputs)

        for value in mutations:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^RECEIPT_CONTRACT_INVALID$",
                ):
                    ReceiptEnvelopeV1.create(value)

    def test_unhashable_receipt_types_fail_with_fixed_contract_error(self) -> None:
        for invalid_type in ([], {}):
            body = receipt_body()
            body["receipt_type"] = invalid_type
            mapping = {
                **body,
                "receipt_fingerprint": opaque_fingerprint(399),
            }
            cases = (
                (ReceiptEnvelopeV1.create, body),
                (ReceiptEnvelopeV1.from_mapping, mapping),
                (ReceiptEnvelopeV1.from_json, canonical_json(mapping)),
            )
            for parser, value in cases:
                with self.subTest(
                    parser=parser.__name__,
                    invalid_type=type(invalid_type).__name__,
                ):
                    with self.assertRaisesRegex(
                        CutoverContractError,
                        "^RECEIPT_CONTRACT_INVALID$",
                    ):
                        parser(value)

    def test_receipt_mapping_fails_closed_before_hostile_comparison(self) -> None:
        for field in ("status", "operation", "producer", "subject_role"):
            body = receipt_body()
            body[field] = HostileComparison()
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^RECEIPT_CONTRACT_INVALID$",
                ):
                    ReceiptEnvelopeV1.create(body)

        input_role = receipt_body()
        input_role["input_fingerprints"][0]["role"] = HostileComparison()
        with self.assertRaisesRegex(
            CutoverContractError,
            "^RECEIPT_CONTRACT_INVALID$",
        ):
            ReceiptEnvelopeV1.create(input_role)

        mapping = ReceiptEnvelopeV1.create(receipt_body()).to_mapping()
        mapping["receipt_fingerprint"] = HostileComparison()
        with self.assertRaisesRegex(
            CutoverContractError,
            "^RECEIPT_CONTRACT_INVALID$",
        ):
            ReceiptEnvelopeV1.from_mapping(mapping)

        hostile_key = receipt_body()
        receipt_type = hostile_key.pop("receipt_type")
        hostile_key = {
            HostileKey("receipt_type"): receipt_type,
            **hostile_key,
        }
        with self.assertRaisesRegex(
            CutoverContractError,
            "^RECEIPT_CONTRACT_INVALID$",
        ):
            ReceiptEnvelopeV1.create(hostile_key)

    def test_receipt_counts_validity_and_fingerprints_are_strict(self) -> None:
        mutations = []
        boolean_count = receipt_body()
        boolean_count["counts"]["accepted"] = True
        mutations.append(boolean_count)
        negative_count = receipt_body()
        negative_count["counts"]["accepted"] = -1
        mutations.append(negative_count)
        huge_count = receipt_body()
        huge_count["counts"]["accepted"] = 1_000_001
        mutations.append(huge_count)
        boolean_time = receipt_body()
        boolean_time["validity"]["issued_at_epoch"] = False
        mutations.append(boolean_time)
        reversed_time = receipt_body()
        reversed_time["validity"]["expires_at_epoch"] = 1_799_999_999
        mutations.append(reversed_time)
        uppercase_hash = receipt_body()
        uppercase_hash["profile_fingerprint"] = "A" * 64
        mutations.append(uppercase_hash)

        for value in mutations:
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^RECEIPT_CONTRACT_INVALID$",
                ):
                    ReceiptEnvelopeV1.create(value)

    def test_receipt_is_immutable_content_free_and_not_authorization(self) -> None:
        receipt = ReceiptEnvelopeV1.create(receipt_body())
        serialized = receipt.to_canonical_json().decode("ascii")
        self.assertFalse(hasattr(ReceiptEnvelopeV1, "_from_body"))
        for forbidden in (
            "D:\\",
            "/home/",
            "S-1-5-",
            "D:(A;",
            "refs/heads/",
            "Traceback",
            "SELECT ",
            "message",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertFalse(hasattr(receipt, "__dict__"))
        self.assertNotIn(receipt.receipt_fingerprint, repr(receipt))

        profile = CutoverProfileV1.create(valid_profile_body())
        result = validate_real_host_authorization(
            receipt,
            profile=profile,
            expected_operation="real_preflight",
            expected_operation_fingerprint=opaque_fingerprint(301),
            expected_phase="current_topology_preflight",
            expected_operator_fingerprint=profile.operator_fingerprint,
            observed_at_epoch=1_800_000_010,
        )
        self.assertIs(
            result.status,
            AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_TYPE,
        )

    def test_mapping_results_do_not_mutate_the_frozen_receipt(self) -> None:
        receipt = ReceiptEnvelopeV1.create(receipt_body())
        before = receipt.to_canonical_json()
        mutable = receipt.to_mapping()
        mutable["counts"]["accepted"] = 0
        mutable["input_fingerprints"].clear()
        mutable["details"]["observation_kind"] = "pre_mutation_gate"

        self.assertEqual(receipt.to_canonical_json(), before)


if __name__ == "__main__":
    unittest.main()
