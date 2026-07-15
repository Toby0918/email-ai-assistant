"""Pure stage-to-final private evaluation dataset construction."""

from __future__ import annotations

import uuid

from .errors import PrivateEvaluationError
from .schema import EvaluationDatasetV1
from .staging_values import EvaluationStageV1


def build_evaluation_dataset(stage: EvaluationStageV1) -> EvaluationDatasetV1:
    """Revalidate one strict 200-case stage under a fresh final namespace."""
    if type(stage) is not EvaluationStageV1:
        raise PrivateEvaluationError("dataset_schema_invalid")
    validated_stage = EvaluationStageV1.from_mapping(stage.to_mapping())
    if sum(
        case.approvals.pro_pair is not None for case in validated_stage.cases
    ) < 40:
        raise PrivateEvaluationError("pair_approval_insufficient")
    namespace = str(uuid.uuid4())
    if namespace == validated_stage.stage_namespace:
        raise PrivateEvaluationError("dataset_schema_invalid")
    return EvaluationDatasetV1.from_mapping({
        "schema_version": "PrivateEvaluationDatasetV1",
        "dataset_namespace": namespace,
        "cases": [case.to_mapping() for case in validated_stage.cases],
    })
