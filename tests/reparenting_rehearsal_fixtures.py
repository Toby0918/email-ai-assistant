from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import tempfile
from unittest import mock

import backend.reparenting_rehearsal.rehearsal as orchestration
from backend.reparenting_rehearsal import (
    PublicationBoundary,
    ReviewedWorktreeChoice,
    rehearse_repository_reparenting,
)
from backend.reparenting_rehearsal.baseline import RepositoryBaseline


@contextmanager
def observed_public_rehearsal(
    *,
    worktree_choices: tuple[ReviewedWorktreeChoice, ...],
    fail_at: PublicationBoundary | None,
):
    """Keep the public seam's private scope observable until assertions end."""

    with tempfile.TemporaryDirectory(
        prefix="issue36-observer-"
    ) as parent:
        baselines: list[RepositoryBaseline] = []
        real_capture = orchestration.capture_repository_baseline

        def capture(*args, **kwargs):
            baseline = real_capture(*args, **kwargs)
            baselines.append(baseline)
            return baseline

        with (
            mock.patch.object(tempfile, "tempdir", parent),
            mock.patch.object(
                orchestration,
                "capture_repository_baseline",
                side_effect=capture,
            ),
        ):
            result = rehearse_repository_reparenting(
                worktree_choices=worktree_choices,
                fail_at=fail_at,
            )
        scopes = tuple(
            path
            for path in Path(parent).iterdir()
            if path.name.startswith("issue36-synthetic-")
        )
        if len(scopes) != 1:
            raise AssertionError(
                f"expected one preserved synthetic scope, found {len(scopes)}"
            )
        if len(baselines) != 1:
            raise AssertionError(
                f"expected one captured baseline, found {len(baselines)}"
            )
        yield result, scopes[0], baselines[0]
