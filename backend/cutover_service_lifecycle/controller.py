"""Narrow provider-disabled new and legacy service controller."""

from __future__ import annotations

import uuid

from backend.cutover_managed_activation import (
    ManagedActivationReceiptSetV1,
)

from .activation_contracts import (
    NewServiceActivationReceiptV1,
    NewServiceStartRequestV1,
    SyntheticActivationEvidenceV1,
    SyntheticActivationRequestV1,
    SyntheticRowEvidenceV1,
)
from .adapters import has_exact_adapters
from .canonical import fail, fingerprint, is_fingerprint
from .contracts import (
    ServiceHealthEvidenceV1,
    ServiceStartEvidenceV1,
    ServiceStopEvidenceV1,
)
from .failures import ActivationFailureKind, ServiceBoundaryFailure
from .legacy_contracts import LegacyServiceRecoveryReceiptV1
from .legacy_recovery import run_legacy_recovery


class ProviderDisabledServiceController:
    """Operate only the reviewed new and legacy service adapter roles."""

    __slots__ = (
        "_profile",
        "_adapters",
        "_state",
        "_new_start",
        "_new_identity_proven",
        "_activation_nonce",
        "_legacy_attempted",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ProviderDisabledServiceController requires create()")

    @classmethod
    def create(
        cls, *, profile_fingerprint: object, adapters: object
    ) -> ProviderDisabledServiceController:
        if not is_fingerprint(profile_fingerprint):
            fail("service_controller_binding_invalid")
        if not has_exact_adapters(adapters):
            fail("service_adapter_bundle_invalid")
        value = object.__new__(cls)
        value._profile = profile_fingerprint
        value._adapters = adapters
        value._state = "ready"
        value._new_start = None
        value._new_identity_proven = False
        value._activation_nonce = None
        value._legacy_attempted = False
        return value

    def activate_new(
        self, publications: object
    ) -> NewServiceActivationReceiptV1:
        if self._state != "ready":
            fail("service_forward_start_prohibited")
        receipts = _validated_publications(publications, self._profile)
        self._state = "starting"
        request = _start_request(receipts, self._profile)
        start = self._call_start(request)
        self._new_start = start
        self._validate_start(request, start)
        self._new_identity_proven = True
        self._activation_nonce = request.nonce
        health = self._call_health(start)
        self._validate_health(start, health)
        synthetic = SyntheticActivationRequestV1.fixed()
        result = self._call_analysis(synthetic)
        self._validate_analysis(synthetic, result)
        row = self._call_row(synthetic)
        self._validate_row(synthetic, receipts, row)
        self._state = "activated"
        return _activation_receipt(
            request, start, health, synthetic, result, row
        )

    @property
    def exact_new_start(self) -> ServiceStartEvidenceV1 | None:
        return self._new_start

    def stop_new_exact(self) -> ServiceStopEvidenceV1:
        if not self._new_identity_proven:
            fail("service_new_identity_not_proven")
        try:
            stopped = self._adapters.new_service.stop_exact(self._new_start)
        except Exception:
            fail("service_new_stop_failed")
        expected = ServiceStopEvidenceV1.create_from_start(self._new_start)
        if type(stopped) is not ServiceStopEvidenceV1 or stopped != expected:
            fail("service_new_stop_failed")
        return stopped

    def contain_new_if_proven(self) -> tuple[int, int]:
        if not self._new_identity_proven:
            return (0, 0)
        try:
            self.stop_new_exact()
        except Exception:
            return (1, 0)
        return (1, 1)

    def recover_legacy(
        self, prerequisites: object
    ) -> LegacyServiceRecoveryReceiptV1:
        if self._legacy_attempted:
            fail("legacy_recovery_not_available")
        self._legacy_attempted = True
        return run_legacy_recovery(
            adapter=self._adapters.legacy_service,
            profile_fingerprint=self._profile,
            prerequisites=prerequisites,
            activation_nonce=self._activation_nonce,
        )

    def _call_start(self, request):
        try:
            return self._adapters.new_service.start_provider_disabled(request)
        except ServiceBoundaryFailure:
            raise
        except Exception:
            raise ServiceBoundaryFailure(
                ActivationFailureKind.SAFETY_AMBIGUITY
            ) from None

    def _call_health(self, start):
        try:
            return self._adapters.new_service.read_health(start)
        except ServiceBoundaryFailure:
            raise
        except Exception:
            raise ServiceBoundaryFailure(
                ActivationFailureKind.HEALTH_REJECTED
            ) from None

    def _call_analysis(self, request):
        try:
            return self._adapters.new_service.analyze_fixed_synthetic(request)
        except ServiceBoundaryFailure:
            raise
        except Exception:
            raise ServiceBoundaryFailure(
                ActivationFailureKind.DETERMINISTIC_RESULT_REJECTED
            ) from None

    def _call_row(self, request):
        try:
            return self._adapters.new_service.observe_synthetic_row(request)
        except ServiceBoundaryFailure:
            raise
        except Exception:
            raise ServiceBoundaryFailure(
                ActivationFailureKind.PERSISTENCE_REJECTED
            ) from None

    @staticmethod
    def _validate_start(request, start) -> None:
        if type(start) is not ServiceStartEvidenceV1:
            _boundary(ActivationFailureKind.SAFETY_AMBIGUITY)
        expected = {
            "role": request.role,
            "profile_fingerprint": request.profile_fingerprint,
            "runtime_fingerprint": request.runtime_fingerprint,
            "executable_fingerprint": request.runtime_fingerprint,
            "config_fingerprint": request.config_fingerprint,
            "data_role_fingerprint": request.data_role_fingerprint,
            "nonce": request.nonce,
            "port": request.port,
        }
        if any(getattr(start, name) != item for name, item in expected.items()):
            _boundary(ActivationFailureKind.IDENTITY_AMBIGUITY)

    @staticmethod
    def _validate_health(start, health) -> None:
        if type(health) is not ServiceHealthEvidenceV1:
            _boundary(ActivationFailureKind.SAFETY_AMBIGUITY)
        expected = {**start.to_mapping(), "healthy": True}
        if health.to_mapping() != expected:
            _boundary(ActivationFailureKind.IDENTITY_AMBIGUITY)

    @staticmethod
    def _validate_analysis(request, result) -> None:
        if type(result) is not SyntheticActivationEvidenceV1:
            _boundary(ActivationFailureKind.SAFETY_AMBIGUITY)
        if result.provider_attempts != 0:
            _boundary(ActivationFailureKind.PROVIDER_BOUNDARY_AMBIGUITY)
        if (
            result.request_fingerprint != request.request_fingerprint
            or result.route != "deterministic_rules"
        ):
            _boundary(ActivationFailureKind.DETERMINISTIC_RESULT_REJECTED)

    @staticmethod
    def _validate_row(request, receipts, row) -> None:
        if type(row) is not SyntheticRowEvidenceV1:
            _boundary(ActivationFailureKind.SAFETY_AMBIGUITY)
        if (
            row.request_fingerprint != request.request_fingerprint
            or row.data_role_fingerprint
            != receipts.receipts[1].receipt_fingerprint
            or row.matching_rows != 1
        ):
            _boundary(ActivationFailureKind.PERSISTENCE_REJECTED)


def _validated_publications(value, profile):
    if type(value) is not ManagedActivationReceiptSetV1:
        fail("service_publication_receipts_invalid")
    try:
        rebuilt = ManagedActivationReceiptSetV1.from_mapping(
            value.to_mapping()
        )
    except Exception:
        fail("service_publication_receipts_invalid")
    if rebuilt != value or rebuilt.profile_fingerprint != profile:
        fail("service_publication_receipts_invalid")
    return rebuilt


def _start_request(receipts, profile):
    return NewServiceStartRequestV1.create(
        profile_fingerprint=profile,
        runtime_fingerprint=receipts.receipts[0].receipt_fingerprint,
        config_fingerprint=receipts.receipts[3].receipt_fingerprint,
        data_role_fingerprint=receipts.receipts[1].receipt_fingerprint,
        nonce=str(uuid.uuid4()),
    )


def _activation_receipt(request, start, health, synthetic, result, row):
    values = (
        fingerprint(
            "issue58-start-evidence-v1",
            start.to_mapping(),
            code="service_activation_receipt_invalid",
        ),
        fingerprint(
            "issue58-health-evidence-v1",
            health.to_mapping(),
            code="service_activation_receipt_invalid",
        ),
        synthetic.request_fingerprint,
        result.result_fingerprint,
        row.data_role_fingerprint,
        request.config_fingerprint,
    )
    return NewServiceActivationReceiptV1.create(
        nonce=request.nonce,
        input_fingerprints=values,
    )


def _boundary(kind: ActivationFailureKind) -> None:
    raise ServiceBoundaryFailure(kind) from None
