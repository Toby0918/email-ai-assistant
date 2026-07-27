"""Narrow binding values for the seven final ContainerAudit readers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .canonical import is_fingerprint


AuditReader = Callable[[], object]


@dataclass(frozen=True, slots=True, init=False, repr=False)
class BoundAuditCallbackV1:
    binding_fingerprint: str
    reader: AuditReader

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated audit callback construction required")

    @classmethod
    def create(
        cls,
        *,
        binding_fingerprint: str,
        reader: AuditReader,
    ) -> BoundAuditCallbackV1:
        if not is_fingerprint(binding_fingerprint) or not callable(reader):
            raise ValueError("FINAL_AUDIT_COMPOSITION_REJECTED")
        value = object.__new__(cls)
        object.__setattr__(
            value,
            "binding_fingerprint",
            binding_fingerprint,
        )
        object.__setattr__(value, "reader", reader)
        return value


@dataclass(frozen=True, slots=True, repr=False)
class FinalAuditCallbacksV1:
    filesystem: BoundAuditCallbackV1
    acl: BoundAuditCallbackV1
    volume: BoundAuditCallbackV1
    git: BoundAuditCallbackV1
    worktree: BoundAuditCallbackV1
    runtime: BoundAuditCallbackV1
    sqlite: BoundAuditCallbackV1

    def ordered(self) -> tuple[BoundAuditCallbackV1, ...]:
        return (
            self.filesystem,
            self.acl,
            self.volume,
            self.git,
            self.worktree,
            self.runtime,
            self.sqlite,
        )
