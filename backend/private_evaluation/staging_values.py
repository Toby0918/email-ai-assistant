"""Pure strict value contract for a deidentified evaluation stage."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .errors import PrivateEvaluationError
from .schema import EvaluationCaseV1


_STAGE_FIELDS = frozenset({"schema_version", "stage_namespace", "cases"})


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationStageV1:
    schema_version: str
    stage_namespace: str
    cases: tuple[EvaluationCaseV1, ...] = field(repr=False)

    @classmethod
    def from_mapping(cls, value: object) -> EvaluationStageV1:
        if type(value) is not dict or set(value) != _STAGE_FIELDS:
            _invalid()
        if value["schema_version"] != "PrivateEvaluationStageV1":
            _invalid()
        namespace = _uuid4(value["stage_namespace"])
        raw_cases = value["cases"]
        if type(raw_cases) is not list or len(raw_cases) != 200:
            _invalid()
        try:
            cases = tuple(EvaluationCaseV1.from_mapping(item) for item in raw_cases)
        except PrivateEvaluationError:
            _invalid()
        if len({case.case_id for case in cases}) != 200:
            _invalid()
        return cls("PrivateEvaluationStageV1", namespace, cases)

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "stage_namespace": self.stage_namespace,
            "cases": [case.to_mapping() for case in self.cases],
        }


def _uuid4(value: object) -> str:
    if type(value) is not str:
        _invalid()
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        _invalid()
    if str(parsed) != value or parsed.version != 4:
        _invalid()
    return value


def _invalid() -> None:
    raise PrivateEvaluationError("evaluation_stage_schema_invalid")
