"""Issue #51 phase-specific real-host authorization contract tests."""

from __future__ import annotations

import hashlib
import unittest

from backend.cutover_contracts import (
    AuthorizationValidationStatus,
    CutoverContractError,
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    RecoveryAuthorizationV1,
    TestSandboxAuthorizationV1,
    validate_real_host_authorization,
)
from tests.cutover_contract_fixtures import (
    GOVERNING_MASTER,
    HostileComparison,
    HostileKey,
    canonical_json,
    opaque_fingerprint,
    valid_authorization_mapping,
    valid_profile_body,
)


AUTHORIZATION_CASES = (
    (
        RealPreflightAuthorizationV1,
        "RealPreflightAuthorizationV1",
        "real_preflight",
        "current_topology_preflight",
    ),
    (
        EvidencePublicationAuthorizationV1,
        "EvidencePublicationAuthorizationV1",
        "evidence_publication",
        "evidence_publication",
    ),
    (
        CutoverExecutionAuthorizationV1,
        "CutoverExecutionAuthorizationV1",
        "cutover_execution",
        "execute",
    ),
    (
        RecoveryAuthorizationV1,
        "RecoveryAuthorizationV1",
        "recovery",
        "rollback",
    ),
)


def parsed_authorization(
    authorization_class,
    profile: CutoverProfileV1,
    *,
    authorization_type: str,
    operation: str,
    phase: str,
    overrides: dict[str, object] | None = None,
):
    value = valid_authorization_mapping(
        authorization_type,
        profile_fingerprint=profile.profile_fingerprint,
        operator_fingerprint=profile.operator_fingerprint,
        operation=operation,
        phase=phase,
    )
    if overrides:
        value.update(overrides)
        body = {
            key: item
            for key, item in value.items()
            if key != "authorization_fingerprint"
        }
        value["authorization_fingerprint"] = hashlib.sha256(
            canonical_json(body)
        ).hexdigest()
    return authorization_class.from_mapping(value)


class CutoverAuthorizationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.profile = CutoverProfileV1.create(valid_profile_body())

    def test_four_real_authorization_types_are_distinct_and_canonical(
        self,
    ) -> None:
        instances = []
        for authorization_class, type_name, operation, phase in AUTHORIZATION_CASES:
            with self.subTest(type_name=type_name):
                authorization = parsed_authorization(
                    authorization_class,
                    self.profile,
                    authorization_type=type_name,
                    operation=operation,
                    phase=phase,
                )
                self.assertIs(type(authorization), authorization_class)
                self.assertFalse(hasattr(authorization, "__dict__"))
                self.assertNotIn(self.profile.profile_fingerprint, repr(authorization))
                self.assertEqual(
                    authorization_class.from_json(
                        authorization.to_canonical_json()
                    ),
                    authorization,
                )
                self.assertFalse(hasattr(authorization_class, "create"))
                instances.append(authorization)
        self.assertEqual(len({type(item) for item in instances}), 4)

    def test_each_authorization_accepts_only_its_fixed_phase_matrix(self) -> None:
        invalid_cases = (
            (
                RealPreflightAuthorizationV1,
                "RealPreflightAuthorizationV1",
                "real_preflight",
                "execute",
            ),
            (
                EvidencePublicationAuthorizationV1,
                "EvidencePublicationAuthorizationV1",
                "evidence_publication",
                "evidence_review",
            ),
            (
                CutoverExecutionAuthorizationV1,
                "CutoverExecutionAuthorizationV1",
                "cutover_execution",
                "rollback",
            ),
            (
                RecoveryAuthorizationV1,
                "RecoveryAuthorizationV1",
                "recovery",
                "resume",
            ),
        )
        for authorization_class, type_name, operation, phase in invalid_cases:
            value = valid_authorization_mapping(
                type_name,
                profile_fingerprint=self.profile.profile_fingerprint,
                operator_fingerprint=self.profile.operator_fingerprint,
                operation=operation,
                phase=phase,
            )
            with self.subTest(type_name=type_name, phase=phase):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^AUTHORIZATION_CONTRACT_INVALID$",
                ):
                    authorization_class.from_mapping(value)

    def test_real_host_validation_returns_exact_mismatch_codes(self) -> None:
        authorization = parsed_authorization(
            RealPreflightAuthorizationV1,
            self.profile,
            authorization_type="RealPreflightAuthorizationV1",
            operation="real_preflight",
            phase="current_topology_preflight",
        )
        base = {
            "profile": self.profile,
            "expected_operation": "real_preflight",
            "expected_operation_fingerprint": opaque_fingerprint(201),
            "expected_phase": "current_topology_preflight",
            "expected_operator_fingerprint": self.profile.operator_fingerprint,
            "observed_at_epoch": 1_800_000_010,
        }
        cases = (
            (
                None,
                base,
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_MISSING,
            ),
            (
                object(),
                base,
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_TYPE,
            ),
            (
                authorization,
                {
                    **base,
                    "profile": _different_profile(),
                    "expected_operator_fingerprint":
                        _different_profile().operator_fingerprint,
                },
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_PROFILE,
            ),
            (
                parsed_authorization(
                    RealPreflightAuthorizationV1,
                    self.profile,
                    authorization_type="RealPreflightAuthorizationV1",
                    operation="real_preflight",
                    phase="current_topology_preflight",
                    overrides={"governing_master_commit": "1" * 40},
                ),
                base,
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_MASTER,
            ),
            (
                authorization,
                {
                    **base,
                    "expected_operation": "evidence_publication",
                    "expected_phase": "evidence_publication",
                },
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_OPERATION,
            ),
            (
                parsed_authorization(
                    RealPreflightAuthorizationV1,
                    self.profile,
                    authorization_type="RealPreflightAuthorizationV1",
                    operation="real_preflight",
                    phase="current_topology_preflight",
                    overrides={"operator_fingerprint": opaque_fingerprint(250)},
                ),
                base,
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_OPERATOR,
            ),
            (
                authorization,
                {**base, "expected_phase": "host_baseline"},
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_PHASE,
            ),
        )
        for value, arguments, expected in cases:
            with self.subTest(expected=expected):
                result = validate_real_host_authorization(value, **arguments)
                self.assertIs(result.status, expected)
                self.assertEqual((result.accepted, result.rejected), (0, 1))

    def test_validation_uses_explicit_half_open_validity_window(self) -> None:
        authorization = parsed_authorization(
            RealPreflightAuthorizationV1,
            self.profile,
            authorization_type="RealPreflightAuthorizationV1",
            operation="real_preflight",
            phase="current_topology_preflight",
        )
        arguments = {
            "profile": self.profile,
            "expected_operation": "real_preflight",
            "expected_operation_fingerprint": opaque_fingerprint(201),
            "expected_phase": "current_topology_preflight",
            "expected_operator_fingerprint": self.profile.operator_fingerprint,
        }
        statuses = {
            1_800_000_009:
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_NOT_YET_VALID,
            1_800_000_010: AuthorizationValidationStatus.AUTHORIZED,
            1_800_000_609: AuthorizationValidationStatus.AUTHORIZED,
            1_800_000_610:
                AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_EXPIRED,
        }
        for observed, expected in statuses.items():
            with self.subTest(observed=observed):
                result = validate_real_host_authorization(
                    authorization,
                    observed_at_epoch=observed,
                    **arguments,
                )
                self.assertIs(result.status, expected)
                expected_counts = (1, 0) if expected.value == "AUTHORIZED" else (0, 1)
                self.assertEqual(
                    (result.accepted, result.rejected),
                    expected_counts,
                )

    def test_test_authorization_and_duck_type_cannot_become_real_authority(
        self,
    ) -> None:
        sandbox = TestSandboxAuthorizationV1.create(
            profile_fingerprint=self.profile.profile_fingerprint,
            operation_fingerprint=opaque_fingerprint(201),
            phase="current_topology_preflight",
            expires_at_epoch=1_800_000_610,
        )

        class HostileDuck:
            @property
            def profile_fingerprint(self):
                raise AssertionError("duck attributes must not be read")

        arguments = {
            "profile": self.profile,
            "expected_operation": "real_preflight",
            "expected_operation_fingerprint": opaque_fingerprint(201),
            "expected_phase": "current_topology_preflight",
            "expected_operator_fingerprint": self.profile.operator_fingerprint,
            "observed_at_epoch": 1_800_000_010,
        }
        for value in (sandbox, {}, HostileDuck()):
            with self.subTest(value_type=type(value).__name__):
                result = validate_real_host_authorization(value, **arguments)
                self.assertIs(
                    result.status,
                    AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_WRONG_TYPE,
                )

    def test_validator_rechecks_nominal_authorization_integrity(self) -> None:
        arguments = {
            "profile": self.profile,
            "expected_operation": "real_preflight",
            "expected_operation_fingerprint": opaque_fingerprint(201),
            "expected_phase": "current_topology_preflight",
            "expected_operator_fingerprint": self.profile.operator_fingerprint,
            "observed_at_epoch": 1_800_000_010,
        }
        for field, invalid_value in (
            ("authorization_fingerprint", "not-a-fingerprint"),
            ("issued_at_epoch", -999),
            ("expires_at_epoch", 2**100),
        ):
            authorization = parsed_authorization(
                RealPreflightAuthorizationV1,
                self.profile,
                authorization_type="RealPreflightAuthorizationV1",
                operation="real_preflight",
                phase="current_topology_preflight",
            )
            object.__setattr__(authorization, field, invalid_value)

            with self.subTest(field=field):
                result = validate_real_host_authorization(
                    authorization,
                    **arguments,
                )
                self.assertIs(
                    result.status,
                    AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_INVALID,
                )
                self.assertEqual((result.accepted, result.rejected), (0, 1))

    def test_validator_rechecks_profile_integrity_before_authorizing(self) -> None:
        authorization = parsed_authorization(
            RealPreflightAuthorizationV1,
            self.profile,
            authorization_type="RealPreflightAuthorizationV1",
            operation="real_preflight",
            phase="current_topology_preflight",
        )
        object.__setattr__(self.profile, "role_selections", object())

        result = validate_real_host_authorization(
            authorization,
            profile=self.profile,
            expected_operation="real_preflight",
            expected_operation_fingerprint=opaque_fingerprint(201),
            expected_phase="current_topology_preflight",
            expected_operator_fingerprint=self.profile.operator_fingerprint,
            observed_at_epoch=1_800_000_010,
        )

        self.assertIs(
            result.status,
            AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_INVALID,
        )
        self.assertEqual((result.accepted, result.rejected), (0, 1))

    def test_validator_fails_closed_on_cyclic_profile_state(self) -> None:
        authorization = parsed_authorization(
            RealPreflightAuthorizationV1,
            self.profile,
            authorization_type="RealPreflightAuthorizationV1",
            operation="real_preflight",
            phase="current_topology_preflight",
        )
        frozen_roles = self.profile.role_selections
        object.__setattr__(
            frozen_roles,
            "items",
            (("projects_parent", frozen_roles),),
        )

        result = validate_real_host_authorization(
            authorization,
            profile=self.profile,
            expected_operation="real_preflight",
            expected_operation_fingerprint=opaque_fingerprint(201),
            expected_phase="current_topology_preflight",
            expected_operator_fingerprint=self.profile.operator_fingerprint,
            observed_at_epoch=1_800_000_010,
        )

        self.assertIs(
            result.status,
            AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_INVALID,
        )
        self.assertEqual((result.accepted, result.rejected), (0, 1))

    def test_real_authorization_types_expose_no_unchecked_body_constructor(
        self,
    ) -> None:
        for authorization_class, *_unused in AUTHORIZATION_CASES:
            with self.subTest(authorization_class=authorization_class.__name__):
                self.assertFalse(hasattr(authorization_class, "_from_body"))

    def test_authorization_parser_rejects_unknown_duplicate_and_tampering(
        self,
    ) -> None:
        authorization = parsed_authorization(
            RealPreflightAuthorizationV1,
            self.profile,
            authorization_type="RealPreflightAuthorizationV1",
            operation="real_preflight",
            phase="current_topology_preflight",
        )
        unknown = authorization.to_mapping()
        unknown["message"] = "not allowed"
        tampered = authorization.to_mapping()
        tampered["authorization_fingerprint"] = "f" * 64
        duplicate = authorization.to_canonical_json().replace(
            b'{"authorization_fingerprint":',
            b'{"phase":"current_topology_preflight","authorization_fingerprint":',
            1,
        )
        lone_surrogate = authorization.to_canonical_json().replace(
            b'"authorization_type":"RealPreflightAuthorizationV1"',
            b'"authorization_type":"\\ud800"',
            1,
        )
        for value in (unknown, tampered):
            with self.assertRaisesRegex(
                CutoverContractError,
                "^AUTHORIZATION_CONTRACT_INVALID$",
            ):
                RealPreflightAuthorizationV1.from_mapping(value)
        with self.assertRaisesRegex(
            CutoverContractError,
            "^AUTHORIZATION_CONTRACT_INVALID$",
        ):
            RealPreflightAuthorizationV1.from_json(duplicate)
        with self.assertRaisesRegex(
            CutoverContractError,
            "^AUTHORIZATION_CONTRACT_INVALID$",
        ):
            RealPreflightAuthorizationV1.from_json(lone_surrogate)

    def test_authorization_mapping_fails_closed_before_hostile_comparison(
        self,
    ) -> None:
        base = valid_authorization_mapping(
            "RealPreflightAuthorizationV1",
            profile_fingerprint=self.profile.profile_fingerprint,
            operator_fingerprint=self.profile.operator_fingerprint,
            operation="real_preflight",
            phase="current_topology_preflight",
        )
        for field in (
            "authorization_type",
            "operation",
            "phase",
            "authorization_fingerprint",
        ):
            value = dict(base)
            value[field] = HostileComparison()
            with self.subTest(field=field):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^AUTHORIZATION_CONTRACT_INVALID$",
                ):
                    RealPreflightAuthorizationV1.from_mapping(value)

        authorization = RealPreflightAuthorizationV1.from_mapping(base)
        object.__setattr__(authorization, "phase", HostileComparison())
        result = validate_real_host_authorization(
            authorization,
            profile=self.profile,
            expected_operation="real_preflight",
            expected_operation_fingerprint=opaque_fingerprint(201),
            expected_phase="current_topology_preflight",
            expected_operator_fingerprint=self.profile.operator_fingerprint,
            observed_at_epoch=1_800_000_010,
        )
        self.assertIs(
            result.status,
            AuthorizationValidationStatus.BLOCKED_AUTHORIZATION_INVALID,
        )

        hostile_key = dict(base)
        authorization_type = hostile_key.pop("authorization_type")
        hostile_key = {
            HostileKey("authorization_type"): authorization_type,
            **hostile_key,
        }
        with self.assertRaisesRegex(
            CutoverContractError,
            "^AUTHORIZATION_CONTRACT_INVALID$",
        ):
            RealPreflightAuthorizationV1.from_mapping(hostile_key)

    def test_validity_and_numeric_fields_are_strictly_bounded(self) -> None:
        invalid_overrides = (
            {"issued_at_epoch": True},
            {"not_before_epoch": 1_799_999_999},
            {"expires_at_epoch": 1_800_100_000},
            {"operation_fingerprint": "A" * 64},
            {"governing_master_commit": GOVERNING_MASTER.upper()},
        )
        for overrides in invalid_overrides:
            value = valid_authorization_mapping(
                "RealPreflightAuthorizationV1",
                profile_fingerprint=self.profile.profile_fingerprint,
                operator_fingerprint=self.profile.operator_fingerprint,
                operation="real_preflight",
                phase="current_topology_preflight",
            )
            value.update(overrides)
            body = {
                key: item
                for key, item in value.items()
                if key != "authorization_fingerprint"
            }
            value["authorization_fingerprint"] = hashlib.sha256(
                canonical_json(body)
            ).hexdigest()
            with self.subTest(overrides=overrides):
                with self.assertRaisesRegex(
                    CutoverContractError,
                    "^AUTHORIZATION_CONTRACT_INVALID$",
                ):
                    RealPreflightAuthorizationV1.from_mapping(value)


def _different_profile() -> CutoverProfileV1:
    body = valid_profile_body()
    body["operator_fingerprint"] = opaque_fingerprint(251)
    return CutoverProfileV1.create(body)


if __name__ == "__main__":
    unittest.main()
