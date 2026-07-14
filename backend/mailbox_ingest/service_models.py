"""Small CLI/service handoff contracts without runtime side effects."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass(frozen=True)
class CliResult:
    code: str
    count: int | None = None
    fingerprint: str | None = None
    opaque_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"ok": True, "code": self.code}
        if self.count is not None:
            payload["count"] = self.count
        if self.fingerprint is not None:
            payload["fingerprint"] = self.fingerprint
        if self.opaque_ids:
            payload["opaque_ids"] = list(self.opaque_ids)
        return payload


class PreparedOperation(Protocol):
    def execute(self, session: object | None) -> CliResult: ...


@dataclass(frozen=True)
class CliDependencies:
    preflight: Callable[[argparse.Namespace], object]
    prepare: Callable[[argparse.Namespace, object], PreparedOperation]
    getpass: Callable[[str], str]
    session_factory: Callable[[str, str], object]
    emit: Callable[[dict[str, object]], None]


__all__ = ["CliDependencies", "CliResult", "PreparedOperation"]
