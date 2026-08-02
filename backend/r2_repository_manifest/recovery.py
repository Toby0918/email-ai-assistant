"""No-delete exact rollback for every Issue #75 partial topology."""

from __future__ import annotations

from pathlib import Path

from backend.cutover_repository_transaction.windows_identity import (
    directory_identity,
)
from backend.r2_main_publication.host_effects import move_object
from backend.r2_main_publication.windows_dacl import (
    capture_tree,
    restore_tree_dacls,
)

from .contracts import build_receipt
from .host import create_directory
from .types import ManifestBoundary
from .verification import verify_reverse


def rollback_transaction(state, journal, *, effect):
    _preserve_new_topology(state, effect)
    _restore_manifest_and_anchor(state, effect)
    _restore_original_worktrees(state, effect)
    effect(
        ManifestBoundary.ACL_CONFORMANCE,
        1,
        lambda: restore_tree_dacls(
            capture_tree(state.container), state.baseline
        ),
    )
    effect(
        ManifestBoundary.FINAL_VERIFICATION,
        1,
        lambda: verify_reverse(state),
    )
    return build_receipt(
        status="LEGACY_FLAT_LAYOUT_RESTORED",
        manifest_fingerprint=state.manifest.contract.manifest_fingerprint,
        journal_head_fingerprint=journal.head,
        retained_residue_count=len(state.manifest.residue),
    )


def _preserve_new_topology(state, effect) -> None:
    if not state.container.is_dir() or not state.legacy.is_dir():
        return
    _preserve_new_admins(state, effect)
    _preserve_external_targets(state, effect)
    effect(
        ManifestBoundary.CONTAINER_PUBLICATION,
        1,
        lambda: move_object(state, state.container, state.failed_container),
    )


def _preserve_new_admins(state, effect) -> None:
    root = Path(state.scope.review.scenario.rollback_root) / "new-admin"
    if not root.exists():
        effect(
            ManifestBoundary.WORKTREE_RECONSTRUCTION,
            90,
            lambda: create_directory(state, root),
        )
    for index, item in enumerate(state.recreated, start=1):
        if item.admin.exists():
            effect(
                ManifestBoundary.WORKTREE_RECONSTRUCTION,
                index,
                lambda item=item: move_object(
                    state, item.admin, root / item.reviewed.paths.role
                ),
            )


def _preserve_external_targets(state, effect) -> None:
    root = Path(state.scope.review.scenario.rollback_root) / "new-external"
    if not root.exists():
        effect(
            ManifestBoundary.WORKTREE_RECONSTRUCTION,
            91,
            lambda: create_directory(state, root),
        )
    for index, item in enumerate(
        state.scope.review.observations[8:], start=20
    ):
        if item.paths.target.exists():
            effect(
                ManifestBoundary.WORKTREE_RECONSTRUCTION,
                index,
                lambda item=item: move_object(
                    state, item.paths.target, root / item.paths.role
                ),
            )


def _restore_manifest_and_anchor(state, effect) -> None:
    if not state.legacy.exists():
        return
    active_main = (
        state.failed_container / "main"
        if state.failed_container.exists()
        else state.main
    )
    if active_main.exists():
        indexed = tuple(enumerate(state.manifest.moves, start=1))
        for index, item in reversed(indexed):
            source = active_main / item.relative
            target = state.legacy / item.relative
            if source.exists():
                if target.exists():
                    raise ValueError("repository_manifest_reverse_ambiguous")
                effect(
                    ManifestBoundary.MANIFEST_RELOCATION,
                    index,
                    lambda source=source, target=target: move_object(
                        state, source, target
                    ),
                )
    if not state.container.exists():
        effect(
            ManifestBoundary.LEGACY_ANCHOR_RENAME,
            1,
            lambda: move_object(state, state.legacy, state.container),
        )


def _restore_original_worktrees(state, effect) -> None:
    scenario = state.scope.review.scenario
    if not state.container.exists():
        raise ValueError("repository_manifest_reverse_ambiguous")
    for index, item in enumerate(state.scope.review.observations, start=12):
        source = Path(scenario.admin_preservation) / item.paths.role
        if source.exists():
            effect(
                ManifestBoundary.WORKTREE_PRESERVATION,
                index,
                lambda source=source, item=item: move_object(
                    state, source, item.admin
                ),
            )
    for index, item in enumerate(state.scope.review.observations, start=1):
        source = Path(scenario.worktree_preservation) / item.paths.role
        if source.exists():
            effect(
                ManifestBoundary.WORKTREE_PRESERVATION,
                index,
                lambda source=source, item=item: move_object(
                    state, source, item.paths.original
                ),
            )
    if directory_identity(state.container) != state.scope.review.repository_object_identity:
        raise ValueError("repository_manifest_reverse_ambiguous")
