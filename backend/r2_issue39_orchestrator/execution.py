"""Nominal single-use execution shell for the Issue #39 state machine."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True, init=False, repr=False)
class Issue39BoundExecutionV1:
    _read_readiness: object = field(repr=False)
    _run_preflight: object = field(repr=False)
    _publish_evidence: object = field(repr=False)
    _execute_transaction: object = field(repr=False)
    _rollback_transaction: object = field(repr=False)
    _state: object = field(repr=False)
    _synthetic_test_only: bool = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("Issue39BoundExecutionV1 requires a reviewed binder")


def _allocate_execution_v1(
    *, read_readiness, run_preflight, publish_evidence,
    execute_transaction, rollback_transaction, state, synthetic
):
    if (
        not callable(read_readiness)
        or not callable(run_preflight)
        or not callable(publish_evidence)
        or not callable(execute_transaction)
        or not callable(rollback_transaction)
        or type(synthetic) is not bool
    ):
        raise TypeError("R2_ISSUE39_EXECUTION_INVALID")
    value = object.__new__(Issue39BoundExecutionV1)
    object.__setattr__(value, "_read_readiness", read_readiness)
    object.__setattr__(value, "_run_preflight", run_preflight)
    object.__setattr__(value, "_publish_evidence", publish_evidence)
    object.__setattr__(value, "_execute_transaction", execute_transaction)
    object.__setattr__(value, "_rollback_transaction", rollback_transaction)
    object.__setattr__(value, "_state", state)
    object.__setattr__(value, "_synthetic_test_only", synthetic)
    return value
