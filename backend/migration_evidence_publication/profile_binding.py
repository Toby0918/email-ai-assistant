"""Derive exact content-free Cutover Profile evidence selections."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .review_bridge import (
    MigrationEvidenceReview,
    capture_snapshot,
    require_existing_non_reparse_directory,
    source_snapshot_fingerprint,
)

from .canonical import fingerprint, path_fingerprint
from .profile_git_binding import (
    directory_selection,
    git_common_directory,
    git_executable_selection,
    worktree_roster,
)


@dataclass(frozen=True, slots=True, repr=False)
class _ProfileBindings:
    evidence_roles: dict[str, str]
    reviewed_git_selections: dict[str, str]
    worktree_roster: tuple[dict[str, str], ...]
    selection_fingerprint: str
    git_fingerprint: str
    host_fingerprint: str
    counts: dict[str, int]
    counts_fingerprint: str
    source_snapshot_fingerprint: str


def _profile_bindings_for_review(
    review: MigrationEvidenceReview,
    ordered_worktree_paths: tuple[Path, ...],
) -> _ProfileBindings:
    ordered, reviewed_by_path = _validate_review_scope(
        review,
        ordered_worktree_paths,
    )
    git_selections, common_identity = _base_git_selections(review)
    dirty_layers, snapshot_mapping, source_fingerprint = _dirty_layers(
        review
    )
    git_selections["dirty_layers"] = dirty_layers
    roster = worktree_roster(ordered, reviewed_by_path)
    git_selections["worktree_topology"] = fingerprint(
        "migration-evidence-git-worktree-topology-v1",
        [item["selection_fingerprint"] for item in roster],
    )
    return _build_profile_bindings(
        review=review,
        git_selections=git_selections,
        roster=roster,
        common_identity=common_identity,
        snapshot_mapping=snapshot_mapping,
        source_snapshot=source_fingerprint,
    )


def _validate_review_scope(
    review: MigrationEvidenceReview,
    ordered_worktree_paths: tuple[Path, ...],
) -> tuple[tuple[Path, ...], dict[Path, object]]:
    if (
        type(review) is not MigrationEvidenceReview
        or type(ordered_worktree_paths) is not tuple
        or len(ordered_worktree_paths) != 11
    ):
        raise ValueError("MIGRATION_EVIDENCE_PROFILE_BINDING_REJECTED")
    ordered = tuple(
        require_existing_non_reparse_directory(path)
        for path in ordered_worktree_paths
    )
    if len(set(ordered)) != 11 or ordered[0] != review.repository_root:
        raise ValueError("MIGRATION_EVIDENCE_PROFILE_BINDING_REJECTED")
    reviewed_by_path = {item.path: item for item in review.worktrees}
    if set(reviewed_by_path) != set(ordered):
        raise ValueError("MIGRATION_EVIDENCE_PROFILE_BINDING_REJECTED")
    return ordered, reviewed_by_path


def _base_git_selections(
    review: MigrationEvidenceReview,
) -> tuple[dict[str, str], str]:
    common_directory = git_common_directory(review.repository_root)
    common_identity = directory_selection(common_directory)
    remote_configuration = fingerprint(
        "migration-evidence-git-remote-configuration-v1",
        [
            {
                "name": item.name,
                "url_sha256": item.url_sha256,
                "fetch_sha256": item.fetch_sha256,
            }
            for item in review.git_baseline.remotes
        ],
    )
    local_refs = fingerprint(
        "migration-evidence-git-local-refs-v1",
        [
            {"name": item.name, "oid": item.oid}
            for item in review.reviewed_refs
        ],
    )
    return {
        "repository_identity": directory_selection(
            review.repository_root
        ),
        "common_directory_identity": common_identity,
        "git_executable": git_executable_selection(
            review.repository_root
        ),
        "remote_configuration": remote_configuration,
        "local_refs": local_refs,
    }, common_identity


def _dirty_layers(
    review: MigrationEvidenceReview,
) -> tuple[str, list[dict[str, object]], str]:
    snapshot_records, payloads = capture_snapshot(review)
    try:
        snapshot_mapping = [
            {
                "path": item.path,
                "status": item.status,
                "tracked": item.tracked,
                "index_mode": item.index_mode,
                "index_size": item.index_size,
                "index_sha256": item.index_sha256,
                "worktree_size": item.worktree_size,
                "worktree_sha256": item.worktree_sha256,
            }
            for item in snapshot_records
        ]
    finally:
        payloads.clear()
    source_fingerprint = source_snapshot_fingerprint(snapshot_records)
    dirty_fingerprint = fingerprint(
        "migration-evidence-git-dirty-layers-v1",
        {
            "entries": [
                {
                    "path": item.path,
                    "status": item.status,
                    "tracked": item.tracked,
                    "ignored": item.ignored,
                    "disposition": item.disposition.value,
                    "reason": item.reason.value,
                }
                for item in review.dirty_entries
            ],
            "source_snapshot_fingerprint": (
                source_fingerprint
            ),
        },
    )
    return dirty_fingerprint, snapshot_mapping, source_fingerprint


def _build_profile_bindings(
    *,
    review: MigrationEvidenceReview,
    git_selections: dict[str, str],
    roster: tuple[dict[str, str], ...],
    common_identity: str,
    snapshot_mapping: list[dict[str, object]],
    source_snapshot: str,
) -> _ProfileBindings:
    evidence_roles = _evidence_roles(review, common_identity, roster)
    counts = _review_counts(review, snapshot_mapping)
    git_fingerprint = fingerprint(
        "migration-evidence-reviewed-git-v1",
        git_selections,
    )
    host_fingerprint = fingerprint(
        "migration-evidence-reviewed-host-v1",
        _host_mapping(review),
    )
    counts_fingerprint = fingerprint(
        "migration-evidence-review-counts-v1",
        counts,
    )
    selection_fingerprint = fingerprint(
        "migration-evidence-profile-bound-selection-v1",
        {
            "evidence_roles": evidence_roles,
            "reviewed_git_selections": git_selections,
            "worktree_roster": [
                item["selection_fingerprint"] for item in roster
            ],
            "git_fingerprint": git_fingerprint,
            "host_fingerprint": host_fingerprint,
            "counts_fingerprint": counts_fingerprint,
        },
    )
    return _ProfileBindings(
        evidence_roles=evidence_roles,
        reviewed_git_selections=git_selections,
        worktree_roster=roster,
        selection_fingerprint=selection_fingerprint,
        git_fingerprint=git_fingerprint,
        host_fingerprint=host_fingerprint,
        counts=counts,
        counts_fingerprint=counts_fingerprint,
        source_snapshot_fingerprint=source_snapshot,
    )


def _evidence_roles(
    review: MigrationEvidenceReview,
    common_identity: str,
    roster: tuple[dict[str, str], ...],
) -> dict[str, str]:
    target_parent_identity = directory_selection(review.target.parent)
    worktree_selections = [
        item["selection_fingerprint"] for item in roster
    ]
    sources = {
        "review_root": {
            "path_sha256": path_fingerprint(review.repository_root)
        },
        "package_target": {
            "path_sha256": path_fingerprint(review.target),
            "parent_identity_fingerprint": target_parent_identity,
        },
        "journal_root": {
            "path_sha256": path_fingerprint(review.target.parent),
            "parent_identity_fingerprint": target_parent_identity,
        },
        "git_records_preservation": {
            "common_directory_identity": common_identity
        },
        "worktree_preservation": {
            "worktree_selections": worktree_selections
        },
        "rollback_publication": {
            "path_sha256": path_fingerprint(review.target.parent),
            "parent_identity_fingerprint": target_parent_identity,
            "publication": "create_only",
        },
    }
    return {
        role: fingerprint(
            "migration-evidence-role-selection-v1",
            {"role": role, "selection": sources[role]},
        )
        for role in sources
    }


def _host_mapping(review: MigrationEvidenceReview) -> dict[str, object]:
    value = review.host_baseline
    return {
        "schema_version": value.schema_version,
        "acl_sha256": value.acl_sha256,
        "acl_entry_count": value.acl_entry_count,
        "volume_sha256": value.volume_sha256,
        "filesystem_name": value.filesystem_name,
        "drive_type": value.drive_type,
        "evidence_complete": value.evidence_complete,
        "content_observed": value.content_observed,
    }


def _review_counts(
    review: MigrationEvidenceReview,
    snapshot_mapping: list[dict[str, object]],
) -> dict[str, int]:
    included = sum(
        item.disposition.value == "included"
        for item in review.dirty_entries
    )
    dirty = len(review.dirty_entries)
    return {
        "dirty_entries": dirty,
        "included_dirty_entries": included,
        "excluded_dirty_entries": dirty - included,
        "refs": len(review.reviewed_refs),
        "worktrees": len(review.worktrees),
        "source_records": len(snapshot_mapping),
        "source_bytes": sum(
            item["index_size"] + item["worktree_size"]
            for item in snapshot_mapping
        ),
    }
