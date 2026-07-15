"""Purpose-separated deterministic stratified private-case selection."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .schema import (
    ACTION_TYPES,
    CATEGORIES,
    DIRECTIONS,
    LANGUAGES,
    RISK_TYPES,
    EvaluationCaseV1,
    EvaluationDatasetV1,
    PrivateEvaluationError,
)


SELECTION_PURPOSE = b"private-evaluation-selection/v1"


@dataclass(frozen=True, slots=True)
class EvaluationSelection:
    selected: tuple[EvaluationCaseV1, ...] = field(repr=False)
    gate: tuple[EvaluationCaseV1, ...] = field(repr=False)
    remaining_flash: tuple[EvaluationCaseV1, ...] = field(repr=False)
    paired: tuple[EvaluationCaseV1, ...] = field(repr=False)


def derive_selection_key(
    master_key: bytes | bytearray,
    namespace: str,
) -> bytes:
    if not isinstance(master_key, (bytes, bytearray)) or len(master_key) != 32:
        raise PrivateEvaluationError("evaluation_key_unavailable")
    try:
        salt = uuid.UUID(namespace).bytes
    except (ValueError, AttributeError):
        raise PrivateEvaluationError("dataset_schema_invalid") from None
    copy = bytearray(master_key)
    try:
        return HKDF(
            algorithm=hashes.SHA256(), length=32, salt=salt,
            info=SELECTION_PURPOSE,
        ).derive(bytes(copy))
    finally:
        _wipe(copy)


def select_private_cases(
    dataset: EvaluationDatasetV1,
    selection_key: bytes | bytearray,
) -> EvaluationSelection:
    if not isinstance(dataset, EvaluationDatasetV1):
        raise PrivateEvaluationError("dataset_schema_invalid")
    validated = EvaluationDatasetV1.from_mapping(dataset.to_mapping())
    key = _key(selection_key)
    try:
        selected = _round_robin_main(validated.cases, bytes(key), 200)
        _selected_coverage(selected)
        eligible = tuple(case for case in selected if case.approvals.pro_pair is not None)
        if len(eligible) < 40:
            raise PrivateEvaluationError("pair_approval_insufficient")
        paired = _round_robin_pair(eligible, bytes(key), 40)
        return EvaluationSelection(selected, selected[:20], selected[20:], paired)
    finally:
        _wipe(key)


def _round_robin_main(
    cases: tuple[EvaluationCaseV1, ...], key: bytes, count: int
) -> tuple[EvaluationCaseV1, ...]:
    return _round_robin(
        cases, key, count,
        case_message=lambda case: b"case/v1\0" + case.case_id.encode("ascii"),
        group_message=lambda encoded: b"stratum/v1\0" + encoded,
    )


def _round_robin_pair(
    cases: tuple[EvaluationCaseV1, ...], key: bytes, count: int
) -> tuple[EvaluationCaseV1, ...]:
    return _round_robin(
        cases, key, count,
        case_message=lambda case: b"pair/v1\0" + case.case_id.encode("ascii"),
        group_message=lambda encoded: b"pair/v1\0" + encoded,
    )


def _round_robin(cases, key, count, *, case_message, group_message):
    groups: dict[tuple[str, str, str, str], list[EvaluationCaseV1]] = defaultdict(list)
    for case in cases:
        groups[_stratum_key(case)].append(case)
    ordered_keys = sorted(
        groups,
        key=lambda item: (_digest(key, group_message(_stratum_json(item))), item),
    )
    queues = [
        sorted(groups[item], key=lambda case: (_digest(key, case_message(case)), case.case_id))
        for item in ordered_keys
    ]
    result: list[EvaluationCaseV1] = []
    offset = 0
    while len(result) < count:
        progressed = False
        for queue in queues:
            if offset < len(queue):
                result.append(queue[offset])
                progressed = True
                if len(result) == count:
                    break
        if not progressed:
            break
        offset += 1
    if len(result) != count:
        raise PrivateEvaluationError("dataset_case_count_invalid")
    return tuple(result)


def _stratum_key(case: EvaluationCaseV1) -> tuple[str, str, str, str]:
    value = case.stratum
    return value.category, value.language, value.direction, value.primary_risk


def _stratum_json(value: tuple[str, str, str, str]) -> bytes:
    category, language, direction, primary_risk = value
    return json.dumps(
        {
            "category": category, "direction": direction,
            "language": language, "primary_risk": primary_risk,
        },
        sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")


def _digest(key: bytes, message: bytes) -> bytes:
    return hmac.new(key, message, hashlib.sha256).digest()


def _selected_coverage(cases: tuple[EvaluationCaseV1, ...]) -> None:
    if (
        {case.stratum.category for case in cases} != CATEGORIES
        or {case.stratum.language for case in cases} != LANGUAGES
        or {case.stratum.direction for case in cases} != DIRECTIONS
        or {case.stratum.primary_risk for case in cases} != RISK_TYPES | {"none"}
        or not any(case.expected.mandatory_risk_types for case in cases)
        or not any(case.expected.required_action_types for case in cases)
        or any(action not in ACTION_TYPES for case in cases for action in case.expected.required_action_types)
    ):
        raise PrivateEvaluationError("dataset_strata_incomplete")


def _key(value: bytes | bytearray) -> bytearray:
    if not isinstance(value, (bytes, bytearray)) or len(value) != 32:
        raise PrivateEvaluationError("evaluation_key_unavailable")
    return bytearray(value)


def _wipe(value: bytearray) -> None:
    for index in range(len(value)):
        value[index] = 0
