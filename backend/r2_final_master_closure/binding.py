"""Immutable binding for one exact frozen final master."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import (
    canonical_json,
    fingerprint,
    is_fingerprint,
    is_git_oid,
    strict_json_object,
)
from .errors import FinalMasterClosureError
from .vocabulary import closure_map_fingerprint


_TYPE = "FinalMasterBindingV1"
_BODY_FIELDS = (
    "binding_type",
    "final_commit_oid",
    "final_tree_oid",
    "closure_map_fingerprint",
    "source_package_fingerprint",
    "runbook_fingerprint",
    "workflow_fingerprint",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FinalMasterBindingV1:
    binding_type: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    closure_map_fingerprint: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("FinalMasterBindingV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        final_commit_oid: object,
        final_tree_oid: object,
        source_package_fingerprint: object,
        runbook_fingerprint: object,
        workflow_fingerprint: object,
    ) -> FinalMasterBindingV1:
        body = _validated_body(
            {
                "binding_type": _TYPE,
                "final_commit_oid": final_commit_oid,
                "final_tree_oid": final_tree_oid,
                "closure_map_fingerprint": closure_map_fingerprint(),
                "source_package_fingerprint": source_package_fingerprint,
                "runbook_fingerprint": runbook_fingerprint,
                "workflow_fingerprint": workflow_fingerprint,
            }
        )
        return _construct(body)

    @classmethod
    def from_json(cls, payload: object) -> FinalMasterBindingV1:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise FinalMasterClosureError()
            if set(source) != {*_BODY_FIELDS, "binding_fingerprint"}:
                raise FinalMasterClosureError()
            body = _validated_body({name: source[name] for name in _BODY_FIELDS})
            expected = fingerprint("r2-final-master-binding-v1", body)
            if source["binding_fingerprint"] != expected:
                raise FinalMasterClosureError()
            return _construct(body)
        except FinalMasterClosureError:
            raise
        except Exception:
            raise FinalMasterClosureError() from None

    def to_mapping(self) -> dict[str, object]:
        return {
            **{name: getattr(self, name) for name in _BODY_FIELDS},
            "binding_fingerprint": self.binding_fingerprint,
        }

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def _validated_body(source: dict[str, object]) -> dict[str, object]:
    if (
        set(source) != set(_BODY_FIELDS)
        or source["binding_type"] != _TYPE
        or not is_git_oid(source["final_commit_oid"])
        or not is_git_oid(source["final_tree_oid"])
        or source["closure_map_fingerprint"] != closure_map_fingerprint()
        or not all(
            is_fingerprint(source[name])
            for name in (
                "source_package_fingerprint",
                "runbook_fingerprint",
                "workflow_fingerprint",
            )
        )
    ):
        raise FinalMasterClosureError()
    return dict(source)


def _construct(body: dict[str, object]) -> FinalMasterBindingV1:
    value = object.__new__(FinalMasterBindingV1)
    for name in _BODY_FIELDS:
        object.__setattr__(value, name, body[name])
    object.__setattr__(
        value,
        "binding_fingerprint",
        fingerprint("r2-final-master-binding-v1", body),
    )
    return value
