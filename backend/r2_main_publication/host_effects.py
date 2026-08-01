"""Fixed no-replace host effects used by the synthetic main tracer."""

from __future__ import annotations

import os
from pathlib import Path

from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_directory_primitive,
    _create_test_move_primitive,
)

from .permit import issue_host_effect_permit
from .windows_dacl import bind_projection


def move_object(state, source: Path, target: Path):
    primitive = _create_test_move_primitive(
        root=state.root,
        marker=state.marker,
        authorization=state.authorization,
        profile=state.profile,
        source=source,
        target_parent=target.parent,
        target=target,
        observed_at_epoch=state.observed_at_epoch,
    )
    return _run_primitive(state, primitive, "move_object")


def create_main(state):
    primitive = _create_test_directory_primitive(
        root=state.root,
        marker=state.marker,
        authorization=state.authorization,
        profile=state.profile,
        parent=state.container,
        target=state.main,
        observed_at_epoch=state.observed_at_epoch,
    )
    return _run_primitive(state, primitive, "create_directory")


def build_projection(state):
    directory = state.main / "projection-directory"
    file = state.main / "projection-file.bin"
    directory.mkdir()
    _create_projection_file(file)
    return bind_projection(
        main=state.main,
        directory_probe=directory,
        file_probe=file,
    )


def _run_primitive(state, primitive, method):
    permit = issue_host_effect_permit(
        profile=state.profile,
        authorization=state.authorization,
        owner_fingerprint=state.marker_identity,
        expectation=primitive.expectation,
    )
    try:
        return getattr(primitive, method)(
            intent=permit.intent,
            durable_permit=permit.permit,
        )
    finally:
        permit.close()


def _create_projection_file(path: Path) -> None:
    handle = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY,
        0o600,
    )
    try:
        os.write(handle, b"synthetic-projection-file-v1")
        os.fsync(handle)
    finally:
        os.close(handle)
