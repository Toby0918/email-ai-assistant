"""Strict validation for canonical content-free receipt bodies."""

from __future__ import annotations

from ._canonical import is_exact_str
from .errors import CutoverContractError
from .profile_schema import _is_commit, _is_fingerprint
from .receipt_matrix import RECEIPT_SCHEMAS, ReceiptSchema


RECEIPT_ERROR = "RECEIPT_CONTRACT_INVALID"
RECEIPT_BODY_KEYS = (
    "receipt_type",
    "status",
    "operation",
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_commit",
    "authorization_fingerprint",
    "producer",
    "subject_role",
    "input_fingerprints",
    "observation_fingerprint",
    "counts",
    "validity",
    "details",
)


def validate_receipt_body(value: object) -> dict[str, object]:
    source = _exact_dict(value, RECEIPT_BODY_KEYS)
    receipt_type = source["receipt_type"]
    if type(receipt_type) is not str:
        _invalid()
    schema = RECEIPT_SCHEMAS.get(receipt_type)
    if schema is None or not _valid_envelope_bindings(source, schema):
        _invalid()
    return {
        "receipt_type": receipt_type,
        "status": source["status"],
        "operation": source["operation"],
        "operation_fingerprint": source["operation_fingerprint"],
        "profile_fingerprint": source["profile_fingerprint"],
        "governing_master_commit": source["governing_master_commit"],
        "authorization_fingerprint": source["authorization_fingerprint"],
        "producer": source["producer"],
        "subject_role": source["subject_role"],
        "input_fingerprints": _input_fingerprints(
            source["input_fingerprints"], schema
        ),
        "observation_fingerprint": source["observation_fingerprint"],
        "counts": _counts(source["counts"], schema),
        "validity": _validity(source["validity"], schema),
        "details": _details(source["details"], schema),
    }


def _valid_envelope_bindings(
    source: dict[str, object], schema: ReceiptSchema
) -> bool:
    return (
        type(source["receipt_type"]) is str
        and type(source["status"]) is str
        and source["status"] in schema.statuses
        and is_exact_str(source["operation"], schema.operation)
        and _is_fingerprint(source["operation_fingerprint"])
        and _is_fingerprint(source["profile_fingerprint"])
        and _is_commit(source["governing_master_commit"])
        and _is_fingerprint(source["authorization_fingerprint"])
        and is_exact_str(source["producer"], schema.producer)
        and is_exact_str(source["subject_role"], schema.subject_role)
        and _is_fingerprint(source["observation_fingerprint"])
    )


def _input_fingerprints(
    value: object, schema: ReceiptSchema
) -> list[dict[str, str]]:
    if type(value) is not list or len(value) != len(schema.input_roles):
        _invalid()
    result: list[dict[str, str]] = []
    fingerprints: set[str] = set()
    for item, expected_role in zip(value, schema.input_roles, strict=True):
        source = _exact_dict(item, ("role", "fingerprint"))
        fingerprint = source["fingerprint"]
        if (
            not is_exact_str(source["role"], expected_role)
            or not _is_fingerprint(fingerprint)
            or fingerprint in fingerprints
        ):
            _invalid()
        fingerprints.add(fingerprint)
        result.append({"role": expected_role, "fingerprint": fingerprint})
    return result


def _counts(value: object, schema: ReceiptSchema) -> dict[str, int]:
    source = _exact_dict(value, schema.count_keys)
    result: dict[str, int] = {}
    for key in schema.count_keys:
        item = source[key]
        if type(item) is not int or not 0 <= item <= 1_000_000:
            _invalid()
        result[key] = item
    return result


def _validity(value: object, schema: ReceiptSchema) -> dict[str, int]:
    source = _exact_dict(value, ("issued_at_epoch", "expires_at_epoch"))
    issued = source["issued_at_epoch"]
    expires = source["expires_at_epoch"]
    if (
        type(issued) is not int
        or type(expires) is not int
        or not 0 <= issued < expires < 2**63
        or expires - issued > schema.maximum_validity_seconds
    ):
        _invalid()
    return {"issued_at_epoch": issued, "expires_at_epoch": expires}


def _details(value: object, schema: ReceiptSchema) -> dict[str, str]:
    keys = tuple(key for key, _allowed in schema.detail_values)
    source = _exact_dict(value, keys)
    result: dict[str, str] = {}
    for key, allowed in schema.detail_values:
        item = source[key]
        if type(item) is not str or item not in allowed:
            _invalid()
        result[key] = item
    return result


def _exact_dict(
    value: object, expected_keys: tuple[str, ...]
) -> dict[str, object]:
    if (
        type(value) is not dict
        or any(type(key) is not str for key in value)
        or set(value) != set(expected_keys)
    ):
        _invalid()
    return value

def _invalid() -> None:
    raise CutoverContractError(RECEIPT_ERROR)
