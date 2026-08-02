"""Canonical, anchored durable receipt-link values for Issue #82."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.cutover_composition_contracts.canonical import (
    fingerprint,
    is_fingerprint,
)


INITIAL_RECEIPT_FINGERPRINT = "0" * 64
INITIAL_JOURNAL_HEAD_FINGERPRINT = "0" * 64


@dataclass(frozen=True, slots=True, init=False)
class ReceiptPredecessorLinkV1:
    record_type: str
    material_fingerprint: str = field(repr=False)
    receipt_fingerprint: str = field(repr=False)
    predecessor_fingerprint: str = field(repr=False)
    prior_head_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ReceiptPredecessorLinkV1 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {
            "record_type",
            "material_fingerprint",
            "predecessor_fingerprint",
            "prior_head_fingerprint",
        }
        fingerprints = tuple(
            values.get(name)
            for name in (
                "material_fingerprint",
                "predecessor_fingerprint",
                "prior_head_fingerprint",
            )
        )
        if (
            set(values) != expected
            or values["record_type"]
            not in {"PUBLICATION_RECEIPT", "CUTOVER_SUCCESS"}
            or not all(is_fingerprint(value) for value in fingerprints)
        ):
            raise ValueError("R2_RECEIPT_PREDECESSOR_LINK_INVALID")
        return _create(cls, values, fingerprints)


def is_valid_receipt_link(value: object) -> bool:
    if type(value) is not ReceiptPredecessorLinkV1:
        return False
    try:
        expected = ReceiptPredecessorLinkV1.create(
            record_type=value.record_type,
            material_fingerprint=value.material_fingerprint,
            predecessor_fingerprint=value.predecessor_fingerprint,
            prior_head_fingerprint=value.prior_head_fingerprint,
        )
    except ValueError:
        return False
    return value == expected


def _create(cls, values, fingerprints):
    material, predecessor, prior_head = fingerprints
    receipt = fingerprint(
        "r2-durable-journal-receipt-v1",
        [values["record_type"], predecessor, prior_head, material],
    )
    head = fingerprint("r2-durable-journal-head-v1", [prior_head, receipt])
    result = object.__new__(cls)
    fields = {
        **values,
        "receipt_fingerprint": receipt,
        "journal_head_fingerprint": head,
    }
    for name, item in fields.items():
        object.__setattr__(result, name, item)
    return result
