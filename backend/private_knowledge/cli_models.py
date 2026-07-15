"""Content-free value objects shared by the private CLI and command service."""

from __future__ import annotations

import argparse
import re
import uuid
from dataclasses import dataclass
from typing import Callable

from .errors import PrivateKnowledgeError


@dataclass(frozen=True, slots=True)
class PrivateCliResult:
    code: str
    item_id: str | None = None
    count: int = 0

    def __post_init__(self) -> None:
        if (not isinstance(self.code, str)
                or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", self.code) is None
                or type(self.count) is not int or self.count < 0):
            raise PrivateKnowledgeError("cli_result_invalid")
        if self.item_id is not None:
            _uuid4(self.item_id)

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {"ok": True, "code": self.code, "count": self.count}
        if self.item_id is not None:
            value["item_id"] = self.item_id
        return value


@dataclass(frozen=True, slots=True)
class PrivateCliDependencies:
    dispatch: Callable[[argparse.Namespace], PrivateCliResult]
    emit: Callable[[dict[str, object]], None]


def _uuid4(value: str) -> None:
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise PrivateKnowledgeError("cli_result_invalid") from None
    if str(parsed) != value or parsed.version != 4:
        raise PrivateKnowledgeError("cli_result_invalid")
