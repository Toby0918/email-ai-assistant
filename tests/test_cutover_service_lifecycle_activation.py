"""Provider-disabled new-service activation tests for Issue #58."""

from __future__ import annotations

import unittest
import uuid

from backend.cutover_managed_activation import (
    ConfigPublicationReceiptV1,
    CrxPublicationReceiptV1,
    ManagedActivationReceiptSetV1,
    ManagedRuntimeReceiptV1,
    StoppedDatabaseCopyReceiptV1,
)
from backend.cutover_service_lifecycle import (
    ActivationFailureKind,
    NewServiceAdapter,
    ProviderDisabledServiceAdapters,
    ProviderDisabledServiceController,
    ServiceBoundaryFailure,
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
    SyntheticActivationEvidenceV1,
    SyntheticRowEvidenceV1,
)


OPERATION = "1" * 64
PROFILE = "2" * 64
MASTER = "3" * 40
AUTHORIZATION = "4" * 64
EXECUTABLE = "5" * 64


def publication_receipts() -> ManagedActivationReceiptSetV1:
    receipt_types = (
        ManagedRuntimeReceiptV1,
        StoppedDatabaseCopyReceiptV1,
        CrxPublicationReceiptV1,
        ConfigPublicationReceiptV1,
    )
    receipts = tuple(
        receipt_type.create(
            operation_fingerprint=OPERATION,
            profile_fingerprint=PROFILE,
            governing_master_commit=MASTER,
            authorization_fingerprint=AUTHORIZATION,
            input_fingerprints=(str(index) * 64,),
            observation_fingerprint=str(index + 4) * 64,
            counts={"published": 1, "rejected": 0},
        )
        for index, receipt_type in enumerate(receipt_types, start=1)
    )
    return ManagedActivationReceiptSetV1.create(receipts=receipts)


class _NewServiceHarness:
    def __init__(self) -> None:
        self.starts = 0
        self.health_checks = 0
        self.analyses = 0
        self.row_checks = 0
        self.start = None
        self.start_transform = lambda value: value
        self.health_transform = lambda value: value
        self.provider_attempts = 0

    def adapter(self) -> NewServiceAdapter:
        return NewServiceAdapter(
            start_provider_disabled=self.start_provider_disabled,
            read_health=self.read_health,
            analyze_fixed_synthetic=self.analyze_fixed_synthetic,
            observe_synthetic_row=self.observe_synthetic_row,
            stop_exact=self.stop_exact,
        )

    def start_provider_disabled(self, request):
        self.starts += 1
        self.start = ServiceStartEvidenceV1.create(
            role=ServiceRole.NEW,
            pid=4120,
            start_time_ns=1_900_000_000_000_000_000,
            executable_fingerprint=request.runtime_fingerprint,
            port=request.port,
            port_owner_pid=4120,
            profile_fingerprint=request.profile_fingerprint,
            runtime_fingerprint=request.runtime_fingerprint,
            config_fingerprint=request.config_fingerprint,
            data_role_fingerprint=request.data_role_fingerprint,
            nonce=request.nonce,
            primary_provider="disabled",
            fallback_provider="disabled",
        )
        return self.start_transform(self.start)

    def read_health(self, start):
        self.health_checks += 1
        return self.health_transform(
            ServiceHealthEvidenceV1.create_from_start(start)
        )

    def analyze_fixed_synthetic(self, request):
        self.analyses += 1
        return SyntheticActivationEvidenceV1.create(
            request_fingerprint=request.request_fingerprint,
            route="deterministic_rules",
            provider_attempts=self.provider_attempts,
            result_fingerprint="a" * 64,
        )

    def observe_synthetic_row(self, request):
        self.row_checks += 1
        return SyntheticRowEvidenceV1.create(
            request_fingerprint=request.request_fingerprint,
            data_role_fingerprint=publication_receipts().receipts[
                1
            ].receipt_fingerprint,
            matching_rows=1,
        )

    def stop_exact(self, start):
        return None


def adapters(harness: _NewServiceHarness):
    from backend.cutover_service_lifecycle import LegacyServiceAdapter

    legacy = LegacyServiceAdapter(
        start_provider_disabled_recovery=lambda request: None,
        read_health=lambda start: None,
        stop_exact=lambda start: None,
    )
    return ProviderDisabledServiceAdapters(
        new_service=harness.adapter(),
        legacy_service=legacy,
    )


class ProviderDisabledActivationTests(unittest.TestCase):
    def test_fixed_activation_uses_one_fresh_nonce_and_zero_providers(self):
        harness = _NewServiceHarness()
        controller = ProviderDisabledServiceController.create(
            profile_fingerprint=PROFILE,
            adapters=adapters(harness),
        )

        receipt = controller.activate_new(publication_receipts())

        self.assertEqual(receipt.status, "ACTIVATED_PROVIDER_DISABLED")
        self.assertEqual(receipt.provider_attempts, 0)
        self.assertEqual(receipt.matching_rows, 1)
        self.assertEqual(
            (harness.starts, harness.health_checks, harness.analyses,
             harness.row_checks),
            (1, 1, 1, 1),
        )
        self.assertEqual(uuid.UUID(receipt.nonce).version, 4)
        self.assertEqual(harness.start.nonce, receipt.nonce)
        with self.assertRaisesRegex(
            Exception, "^service_forward_start_prohibited$"
        ):
            controller.activate_new(publication_receipts())

    def test_stale_health_nonce_is_identity_ambiguity(self) -> None:
        harness = _NewServiceHarness()

        def stale(health):
            mapping = health.to_mapping()
            mapping["nonce"] = str(uuid.uuid4())
            stale_start = ServiceStartEvidenceV1.create(
                role=ServiceRole.NEW,
                **{
                    key: value
                    for key, value in mapping.items()
                    if key not in {"role", "healthy"}
                },
            )
            return ServiceHealthEvidenceV1.create_from_start(stale_start)

        harness.health_transform = stale
        controller = ProviderDisabledServiceController.create(
            profile_fingerprint=PROFILE,
            adapters=adapters(harness),
        )

        with self.assertRaises(ServiceBoundaryFailure) as raised:
            controller.activate_new(publication_receipts())

        self.assertIs(
            raised.exception.kind,
            ActivationFailureKind.IDENTITY_AMBIGUITY,
        )
        self.assertEqual(harness.analyses, 0)

    def test_provider_attempt_is_provider_boundary_ambiguity(self) -> None:
        harness = _NewServiceHarness()
        harness.provider_attempts = 1
        controller = ProviderDisabledServiceController.create(
            profile_fingerprint=PROFILE,
            adapters=adapters(harness),
        )

        with self.assertRaises(ServiceBoundaryFailure) as raised:
            controller.activate_new(publication_receipts())

        self.assertIs(
            raised.exception.kind,
            ActivationFailureKind.PROVIDER_BOUNDARY_AMBIGUITY,
        )
        self.assertEqual(harness.row_checks, 0)

    def test_every_start_identity_field_is_exact(self) -> None:
        changes = {
            "role": ServiceRole.LEGACY,
            "executable_fingerprint": "6" * 64,
            "port": 8766,
            "profile_fingerprint": "7" * 64,
            "runtime_fingerprint": "8" * 64,
            "config_fingerprint": "9" * 64,
            "data_role_fingerprint": "b" * 64,
            "nonce": str(uuid.uuid4()),
        }
        for field, replacement in changes.items():
            with self.subTest(field=field):
                harness = _NewServiceHarness()

                def transform(start, field=field, replacement=replacement):
                    mapping = start.to_mapping()
                    mapping[field] = replacement
                    role = (
                        mapping.pop("role")
                        if field == "role"
                        else ServiceRole(mapping.pop("role"))
                    )
                    return ServiceStartEvidenceV1.create(
                        role=role, **mapping
                    )

                harness.start_transform = transform
                controller = ProviderDisabledServiceController.create(
                    profile_fingerprint=PROFILE,
                    adapters=adapters(harness),
                )
                with self.assertRaises(ServiceBoundaryFailure) as raised:
                    controller.activate_new(publication_receipts())
                self.assertIs(
                    raised.exception.kind,
                    ActivationFailureKind.IDENTITY_AMBIGUITY,
                )
                self.assertEqual(harness.health_checks, 0)

    def test_health_rejects_stale_process_and_port_owner(self) -> None:
        for field in ("pid", "start_time_ns", "port"):
            with self.subTest(field=field):
                harness = _NewServiceHarness()

                def stale(health, field=field):
                    mapping = health.to_mapping()
                    mapping.pop("healthy")
                    mapping.pop("role")
                    if field == "pid":
                        mapping["pid"] += 1
                        mapping["port_owner_pid"] += 1
                    else:
                        mapping[field] += 1
                    changed = ServiceStartEvidenceV1.create(
                        role=ServiceRole.NEW, **mapping
                    )
                    return ServiceHealthEvidenceV1.create_from_start(changed)

                harness.health_transform = stale
                controller = ProviderDisabledServiceController.create(
                    profile_fingerprint=PROFILE,
                    adapters=adapters(harness),
                )
                with self.assertRaises(ServiceBoundaryFailure) as raised:
                    controller.activate_new(publication_receipts())
                self.assertIs(
                    raised.exception.kind,
                    ActivationFailureKind.IDENTITY_AMBIGUITY,
                )

    def test_arbitrary_adapter_container_is_rejected(self) -> None:
        with self.assertRaisesRegex(
            Exception, "^service_adapter_bundle_invalid$"
        ):
            ProviderDisabledServiceController.create(
                profile_fingerprint=PROFILE,
                adapters=object(),
            )


if __name__ == "__main__":
    unittest.main()
