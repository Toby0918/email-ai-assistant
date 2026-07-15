"""Strict aggregate-only reporting for private model evaluations."""

from __future__ import annotations

import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from .errors import PrivateEvaluationError
from .metrics import ModelMetrics


FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"
SCHEMA_VERSION = "PrivateEvaluationAggregateV1"
STATUS_CODES = frozenset({"blocked", "gate_stopped", "flash_complete", "comparison_complete"})
DECISION_CODES = frozenset({
    "not_evaluated", "gate_failed", "flash_rejected", "retain_flash",
    "pro_candidate_qualified",
})
ERROR_CODES = frozenset({
    "operator_confirmation_required", "dataset_unavailable",
    "evaluation_key_unavailable", "dataset_decrypt_invalid",
    "dataset_schema_invalid", "dataset_case_count_invalid",
    "dataset_strata_incomplete", "pair_approval_insufficient",
    "provider_configuration_unavailable", "human_judge_unavailable",
    "human_judge_failed", "provider_error", "schema_violation",
    "safety_violation", "grounding_violation", "privacy_violation",
    "latency_gate_failed", "aggregate_serialization_violation",
    "fallback_observed",
})
TOP_KEYS = frozenset({
    "schema_version", "status_code", "models", "counts", "metrics",
    "error_code_counts", "decision_code",
})
COUNT_KEYS = frozenset({
    "selected", "gate_target", "pair_target", "flash_attempted",
    "flash_completed", "pro_attempted", "pro_completed",
})
METRIC_GROUP_KEYS = frozenset({"flash", "paired_flash", "pro"})
METRIC_KEYS = frozenset({
    "schema_success_rate", "unsafe_action_count",
    "unsupported_critical_fact_count", "mandatory_risk_recall",
    "category_macro_f1", "required_action_recall", "usefulness_rate",
    "fallback_rate", "p95_seconds", "quality_score",
})
RATE_KEYS = METRIC_KEYS - frozenset({
    "unsafe_action_count", "unsupported_critical_fact_count", "p95_seconds",
})


@dataclass(frozen=True, slots=True)
class AggregateReport:
    schema_version: str
    status_code: str
    models: Mapping[str, str]
    counts: Mapping[str, int]
    metrics: Mapping[str, Mapping[str, float | int] | None]
    error_code_counts: Mapping[str, int]
    decision_code: str

    @classmethod
    def from_mapping(cls, raw: object) -> "AggregateReport":
        try:
            mapping = _plain_mapping(raw, TOP_KEYS)
            _fixed_fields(mapping)
            models = _models(mapping["models"])
            counts = _counts(mapping["counts"])
            metrics = _metrics(mapping["metrics"])
            errors = _errors(mapping["error_code_counts"])
            _consistent(mapping["status_code"], mapping["decision_code"], counts, metrics)
            return cls(
                SCHEMA_VERSION, mapping["status_code"], MappingProxyType(models),
                MappingProxyType(counts), MappingProxyType(metrics),
                MappingProxyType(errors), mapping["decision_code"],
            )
        except PrivateEvaluationError:
            raise
        except Exception:
            raise PrivateEvaluationError("aggregate_serialization_violation") from None

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version, "status_code": self.status_code,
            "models": dict(self.models), "counts": dict(self.counts),
            "metrics": {
                name: None if value is None else dict(value)
                for name, value in self.metrics.items()
            },
            "error_code_counts": dict(self.error_code_counts),
            "decision_code": self.decision_code,
        }


def make_report(
    *, status: str, decision: str, flash_attempted: int = 0,
    flash_completed: int = 0, pro_attempted: int = 0, pro_completed: int = 0,
    flash_metrics: ModelMetrics | None = None,
    pair_flash_metrics: ModelMetrics | None = None,
    pro_metrics: ModelMetrics | None = None,
    errors: Mapping[str, int] | None = None,
) -> AggregateReport:
    raw = {
        "schema_version": SCHEMA_VERSION, "status_code": status,
        "models": {"flash": FLASH_MODEL, "pro": PRO_MODEL},
        "counts": {
            "selected": 200, "gate_target": 20, "pair_target": 40,
            "flash_attempted": flash_attempted, "flash_completed": flash_completed,
            "pro_attempted": pro_attempted, "pro_completed": pro_completed,
        },
        "metrics": {
            "flash": _metric_mapping(flash_metrics),
            "paired_flash": _metric_mapping(pair_flash_metrics),
            "pro": _metric_mapping(pro_metrics),
        },
        "error_code_counts": dict(errors or {}), "decision_code": decision,
    }
    return AggregateReport.from_mapping(raw)


def write_aggregate_report(report: AggregateReport, path: Path) -> None:
    stage: Path | None = None
    try:
        validated = AggregateReport.from_mapping(report.to_mapping())
        target = Path(path)
        payload = json.dumps(
            validated.to_mapping(), ensure_ascii=True, allow_nan=False,
            separators=(",", ":"), sort_keys=True,
        ).encode("utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        stage = Path(name)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(stage, target)
        stage = None
        _sync_directory(target.parent)
    except Exception:
        raise PrivateEvaluationError("aggregate_serialization_violation") from None
    finally:
        if stage is not None:
            try:
                stage.unlink(missing_ok=True)
            except OSError:
                pass


def _plain_mapping(raw: object, keys: frozenset[str]) -> dict[str, object]:
    if type(raw) is not dict or set(raw) != keys:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    return raw


def _fixed_fields(mapping: dict[str, object]) -> None:
    if mapping["schema_version"] != SCHEMA_VERSION:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if mapping["status_code"] not in STATUS_CODES or mapping["decision_code"] not in DECISION_CODES:
        raise PrivateEvaluationError("aggregate_serialization_violation")


def _models(raw: object) -> dict[str, str]:
    mapping = _plain_mapping(raw, frozenset({"flash", "pro"}))
    if mapping != {"flash": FLASH_MODEL, "pro": PRO_MODEL}:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    return {"flash": FLASH_MODEL, "pro": PRO_MODEL}


def _counts(raw: object) -> dict[str, int]:
    mapping = _plain_mapping(raw, COUNT_KEYS)
    if any(type(value) is not int or value < 0 for value in mapping.values()):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if mapping["selected"] != 200 or mapping["gate_target"] != 20 or mapping["pair_target"] != 40:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if mapping["flash_completed"] > mapping["flash_attempted"] or mapping["flash_attempted"] > 200:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if mapping["pro_completed"] > mapping["pro_attempted"] or mapping["pro_attempted"] > 40:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    return dict(mapping)


def _metrics(raw: object) -> dict[str, Mapping[str, float | int] | None]:
    mapping = _plain_mapping(raw, METRIC_GROUP_KEYS)
    return {name: _one_metric(mapping[name]) for name in ("flash", "paired_flash", "pro")}


def _one_metric(raw: object) -> Mapping[str, float | int] | None:
    if raw is None:
        return None
    mapping = _plain_mapping(raw, METRIC_KEYS)
    for name, value in mapping.items():
        if name in {"unsafe_action_count", "unsupported_critical_fact_count"}:
            valid = type(value) is int and value >= 0
        else:
            valid = type(value) in {int, float} and math.isfinite(value)
            valid = valid and (value >= 0) and (name not in RATE_KEYS or value <= 1)
        if not valid:
            raise PrivateEvaluationError("aggregate_serialization_violation")
    return MappingProxyType(dict(mapping))


def _errors(raw: object) -> dict[str, int]:
    if type(raw) is not dict or not set(raw).issubset(ERROR_CODES):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if any(type(value) is not int or value < 1 for value in raw.values()):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    return dict(raw)


def _consistent(status: object, decision: object, counts: Mapping[str, int], metrics) -> None:
    expected = {
        "blocked": {"not_evaluated"}, "gate_stopped": {"gate_failed"},
        "flash_complete": {"flash_rejected"},
        "comparison_complete": {"retain_flash", "pro_candidate_qualified"},
    }
    if decision not in expected[status]:
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if status == "blocked" and any(counts[name] for name in (
        "flash_attempted", "flash_completed", "pro_attempted", "pro_completed",
    )):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if status == "flash_complete" and (counts["flash_completed"] != 200 or metrics["flash"] is None):
        raise PrivateEvaluationError("aggregate_serialization_violation")
    if status == "comparison_complete" and (
        counts["flash_completed"] != 200 or counts["pro_completed"] != 40
        or any(metrics[name] is None for name in METRIC_GROUP_KEYS)
    ):
        raise PrivateEvaluationError("aggregate_serialization_violation")


def _metric_mapping(value: ModelMetrics | None) -> dict[str, float | int] | None:
    if value is None:
        return None
    return {name: getattr(value, name) for name in METRIC_KEYS}


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
