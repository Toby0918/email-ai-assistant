"""Strict common-envelope validation for staged mailbox records."""

from __future__ import annotations

from datetime import datetime

from .scan_record_validation import validate_scan_record
from .stage_record_release import _StageRecordRelease


def validate_stage_record(
    value: object,
    scope: str,
    start: datetime,
    end: datetime,
    fingerprint: str | None,
    release: _StageRecordRelease,
) -> tuple[bytes, tuple[bytes, ...]]:
    validated = validate_scan_record(value)
    release.validate(validated.value)
    if (
        validated.value["scope"] != scope
        or (
            fingerprint is not None
            and validated.value["fingerprint"] != fingerprint
        )
        or not start <= validated.internal_date < end
    ):
        raise ValueError
    return validated.header, validated.bodies


__all__ = ["validate_stage_record"]
