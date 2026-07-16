"""Bounded ordinary-file reader kept separate from all write helpers."""

from __future__ import annotations

from pathlib import Path

from .checked_reader import read_bounded_checked, validate_read_path
from .errors import PrivateKnowledgeError


def read_snapshot_file(path: Path, *, maximum: int = 4 * 1024 * 1024) -> bytes:
    target = Path(path)
    try:
        return read_bounded_checked(
            target,
            maximum,
            lambda value: validate_read_path(
                value, error_code="snapshot_unavailable"
            ),
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


def _test_race_hook(_stage: str, _path: Path) -> None:
    """No-op seam; tests may mutate paths and all identity checks still run."""
    return None
