"""Fixed new-service requests and activation evidence."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import fail, fingerprint, is_fingerprint, is_uuid4

_ERROR = "service_activation_contract_invalid"
_FIXED_REQUEST_BODY = {
    "request_type": "provider-disabled-activation-synthetic/v1",
    "subject_class": "synthetic",
    "thread_class": "single_message",
    "content_class": "non_customer_non_private",
}
FIXED_SYNTHETIC_REQUEST_FINGERPRINT = fingerprint(
    "issue58-fixed-synthetic-request-v1",
    _FIXED_REQUEST_BODY,
    code=_ERROR,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class NewServiceStartRequestV1:
    role: str
    profile_fingerprint: str = field(repr=False)
    runtime_fingerprint: str = field(repr=False)
    config_fingerprint: str = field(repr=False)
    data_role_fingerprint: str = field(repr=False)
    nonce: str = field(repr=False)
    port: int
    primary_provider: str
    fallback_provider: str
    reads_environment: bool

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("NewServiceStartRequestV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        profile_fingerprint: object,
        runtime_fingerprint: object,
        config_fingerprint: object,
        data_role_fingerprint: object,
        nonce: object,
    ) -> NewServiceStartRequestV1:
        if (
            not is_fingerprint(profile_fingerprint)
            or not is_fingerprint(runtime_fingerprint)
            or not is_fingerprint(config_fingerprint)
            or not is_fingerprint(data_role_fingerprint)
            or not is_uuid4(nonce)
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        assignments = {
            "role": "reviewed_new_service",
            "profile_fingerprint": profile_fingerprint,
            "runtime_fingerprint": runtime_fingerprint,
            "config_fingerprint": config_fingerprint,
            "data_role_fingerprint": data_role_fingerprint,
            "nonce": nonce,
            "port": 8765,
            "primary_provider": "disabled",
            "fallback_provider": "disabled",
            "reads_environment": False,
        }
        for name, item in assignments.items():
            object.__setattr__(value, name, item)
        return value

@dataclass(frozen=True, slots=True, init=False, repr=False)
class SyntheticActivationRequestV1:
    request_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticActivationRequestV1 requires fixed()")

    @classmethod
    def fixed(cls) -> SyntheticActivationRequestV1:
        value = object.__new__(cls)
        object.__setattr__(
            value,
            "request_fingerprint",
            FIXED_SYNTHETIC_REQUEST_FINGERPRINT,
        )
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class SyntheticActivationEvidenceV1:
    request_fingerprint: str = field(repr=False)
    route: str
    provider_attempts: int
    result_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticActivationEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> SyntheticActivationEvidenceV1:
        if (
            set(values)
            != {
                "request_fingerprint",
                "route",
                "provider_attempts",
                "result_fingerprint",
            }
            or not is_fingerprint(values["request_fingerprint"])
            or values["route"] not in {"deterministic_rules", "remote"}
            or type(values["provider_attempts"]) is not int
            or not 0 <= values["provider_attempts"] <= 8
            or not is_fingerprint(values["result_fingerprint"])
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in values.items():
            object.__setattr__(value, name, item)
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class SyntheticRowEvidenceV1:
    request_fingerprint: str = field(repr=False)
    data_role_fingerprint: str = field(repr=False)
    matching_rows: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticRowEvidenceV1 requires create()")

    @classmethod
    def create(cls, **values: object) -> SyntheticRowEvidenceV1:
        if (
            set(values)
            != {
                "request_fingerprint",
                "data_role_fingerprint",
                "matching_rows",
            }
            or not is_fingerprint(values["request_fingerprint"])
            or not is_fingerprint(values["data_role_fingerprint"])
            or type(values["matching_rows"]) is not int
            or not 0 <= values["matching_rows"] <= 2
        ):
            fail(_ERROR)
        value = object.__new__(cls)
        for name, item in values.items():
            object.__setattr__(value, name, item)
        return value


@dataclass(frozen=True, slots=True, init=False, repr=False)
class NewServiceActivationReceiptV1:
    status: str
    nonce: str = field(repr=False)
    provider_attempts: int
    matching_rows: int
    input_fingerprints: tuple[str, ...] = field(repr=False)
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("NewServiceActivationReceiptV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        nonce: str,
        input_fingerprints: tuple[str, ...],
    ) -> NewServiceActivationReceiptV1:
        if (
            not is_uuid4(nonce)
            or type(input_fingerprints) is not tuple
            or len(input_fingerprints) != 6
            or not all(is_fingerprint(item) for item in input_fingerprints)
        ):
            fail(_ERROR)
        body = {
            "receipt_type": "NewServiceActivationReceiptV1",
            "status": "ACTIVATED_PROVIDER_DISABLED",
            "nonce_fingerprint": fingerprint(
                "issue58-activation-nonce-v1", nonce, code=_ERROR
            ),
            "provider_attempts": 0,
            "matching_rows": 1,
            "input_fingerprints": list(input_fingerprints),
        }
        value = object.__new__(cls)
        object.__setattr__(value, "status", body["status"])
        object.__setattr__(value, "nonce", nonce)
        object.__setattr__(value, "provider_attempts", 0)
        object.__setattr__(value, "matching_rows", 1)
        object.__setattr__(value, "input_fingerprints", input_fingerprints)
        object.__setattr__(
            value,
            "receipt_fingerprint",
            fingerprint("issue58-activation-receipt-v1", body, code=_ERROR),
        )
        return value
