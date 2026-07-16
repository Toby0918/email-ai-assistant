"""Bounded ordinary-file reader kept separate from all write helpers."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .checked_reader import read_bounded_checked, validate_read_path
from .errors import PrivateKnowledgeError


def read_snapshot_file(
    path: Path,
    *,
    maximum: int = 4 * 1024 * 1024,
    prevalidated_target: Path | None = None,
    path_validator: Callable[[Path], Path] | None = None,
) -> bytes:
    target = Path(path)
    try:
        return read_bounded_checked(
            target,
            maximum,
            _reader_validator(prevalidated_target, path_validator),
            _test_race_hook,
            error_code="snapshot_unavailable",
        )
    except PrivateKnowledgeError:
        try:
            target.lstat()
        except FileNotFoundError:
            raise PrivateKnowledgeError("snapshot_missing") from None
        except OSError:
            pass
        raise


def _reader_validator(
    prevalidated_target: Path | None,
    path_validator: Callable[[Path], Path] | None,
) -> Callable[[Path], Path]:
    if prevalidated_target is None and path_validator is None:
        return lambda value: validate_read_path(
            value, error_code="snapshot_unavailable"
        )
    if prevalidated_target is None or path_validator is None:
        raise PrivateKnowledgeError("snapshot_unavailable")
    expected = Path(prevalidated_target)

    def validate(value: Path) -> Path:
        try:
            current = Path(path_validator(Path(value)))
        except Exception:
            raise PrivateKnowledgeError("snapshot_unavailable") from None
        if current != expected:
            raise PrivateKnowledgeError("snapshot_unavailable")
        return validate_read_path(current, error_code="snapshot_unavailable")

    return validate


def _test_race_hook(_stage: str, _path: Path) -> None:
    """No-op seam; tests may mutate paths and all identity checks still run."""
    return None
