"""Mode-specific plaintext release rules for staged mailbox records."""

from __future__ import annotations

from typing import Protocol

from .knowledge_stage_helpers import filenames
from .scan_record_validation import (
    GOVERNED_SCAN_RECORD_FIELDS,
    RAW_SCAN_RECORD_FIELDS,
)


_MAX_PROJECTION_BYTES = 4 * 1024 * 1024


class _StageRecordRelease(Protocol):
    requires_pair: bool
    retains_evidence: bool

    def validate(self, value: dict[str, object]) -> None: ...

    def text(
        self, value: dict[str, object], header: bytes, bodies: tuple[bytes, ...],
    ) -> str: ...


class _KnowledgeRecordRelease:
    __slots__ = ()
    requires_pair = True
    retains_evidence = True

    def validate(self, value: dict[str, object]) -> None:
        if (
            set(value) != GOVERNED_SCAN_RECORD_FIELDS
            or type(value.get("schema_version")) is not int
            or value.get("schema_version") != 2
        ):
            raise ValueError
        _validate_v2_projection(value)

    def text(
        self, value: dict[str, object], _header: bytes,
        _bodies: tuple[bytes, ...],
    ) -> str:
        return str(value["learning_projection"])


class _EvaluationRecordRelease:
    __slots__ = ()
    requires_pair = False
    retains_evidence = False

    def validate(self, value: dict[str, object]) -> None:
        version = value.get("schema_version")
        if type(version) is not int:
            raise ValueError
        if version == 1 and set(value) == RAW_SCAN_RECORD_FIELDS:
            return
        if version == 2 and set(value) == GOVERNED_SCAN_RECORD_FIELDS:
            _validate_v2_projection(value)
            return
        raise ValueError

    def text(
        self, value: dict[str, object], header: bytes, bodies: tuple[bytes, ...],
    ) -> str:
        return "\n".join(
            [header.decode("utf-8", errors="replace")]
            + [item.decode("utf-8", errors="replace") for item in bodies]
            + filenames(value["attachments"])
        )


def _validate_v2_projection(value: dict[str, object]) -> None:
    projection = value.get("learning_projection")
    if (
        type(projection) is not str
        or not projection
        or len(projection.encode("utf-8")) > _MAX_PROJECTION_BYTES
    ):
        raise ValueError


_KNOWLEDGE_RELEASE = _KnowledgeRecordRelease()
_EVALUATION_RELEASE = _EvaluationRecordRelease()
