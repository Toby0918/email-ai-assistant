"""Fresh-process Git-byte snapshot and final-master receipt contracts."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV3

from .canonical import canonical, fingerprint, is_fingerprint
from ._git_byte_validation_v2 import GitByteStateError, is_oid, sha256
from .git_byte_types_v2 import (
    GitCommonStateRoleV2,
    GitCommonStateV2,
    GitWorktreeStateV2,
    SelectedGitByteV2,
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class GitByteSnapshotV2:
    snapshot_type: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    repository_identity_fingerprint: str = field(repr=False)
    selected_byte_count: int
    local_ref_count: int
    stable_common_state_role_count: int
    original_worktree_count: int
    reconstructed_worktree_count: int
    worktree_count: int
    ignored_content_reads: int
    private_content_reads: int
    selected_byte_state_fingerprint: str = field(repr=False)
    local_ref_state_fingerprint: str = field(repr=False)
    stable_common_state_fingerprint: str = field(repr=False)
    original_worktree_state_fingerprint: str = field(repr=False)
    reconstructed_worktree_state_fingerprint: str = field(repr=False)
    selected_bytes: tuple[SelectedGitByteV2, ...] = field(repr=False)
    local_refs: tuple[tuple[str, str], ...] = field(repr=False)
    stable_common_state: tuple[GitCommonStateV2, ...] = field(repr=False)
    original_worktrees: tuple[GitWorktreeStateV2, ...] = field(repr=False)
    reconstructed_worktrees: tuple[GitWorktreeStateV2, ...] = field(repr=False)
    snapshot_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("GitByteSnapshotV2 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {
            "binding",
            "repository_identity_fingerprint",
            "selected_bytes",
            "local_refs",
            "stable_common_state",
            "original_worktrees",
            "reconstructed_worktrees",
        }
        try:
            if set(values) != expected:
                raise GitByteStateError()
            refs = _normalize_refs(values["local_refs"])
            return _build_snapshot(
                values["binding"],
                values["repository_identity_fingerprint"],
                values["selected_bytes"],
                refs,
                values["stable_common_state"],
                values["original_worktrees"],
                values["reconstructed_worktrees"],
            )
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None

    @classmethod
    def from_json(cls, payload, *, binding):
        try:
            source = strict_git_byte_object_v2(payload)
            if canonical(source) != payload:
                raise GitByteStateError()
            expected = _snapshot_field_names()
            if set(source) != expected:
                raise GitByteStateError()
            result = _build_snapshot(
                binding,
                source["repository_identity_fingerprint"],
                tuple(SelectedGitByteV2.from_mapping(item) for item in source["selected_bytes"]),
                _parse_refs(source["local_refs"]),
                tuple(GitCommonStateV2.from_mapping(item) for item in source["stable_common_state"]),
                tuple(GitWorktreeStateV2.from_mapping(item) for item in source["original_worktrees"]),
                tuple(GitWorktreeStateV2.from_mapping(item) for item in source["reconstructed_worktrees"]),
            )
            if result.to_mapping() != source:
                raise GitByteStateError()
            return result
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None

    def to_mapping(self):
        return {
            "snapshot_type": self.snapshot_type,
            "binding_fingerprint": self.binding_fingerprint,
            "final_master_binding_fingerprint": self.final_master_binding_fingerprint,
            "final_commit_oid": self.final_commit_oid,
            "final_tree_oid": self.final_tree_oid,
            "repository_identity_fingerprint": self.repository_identity_fingerprint,
            "selected_byte_count": self.selected_byte_count,
            "local_ref_count": self.local_ref_count,
            "stable_common_state_role_count": self.stable_common_state_role_count,
            "original_worktree_count": self.original_worktree_count,
            "reconstructed_worktree_count": self.reconstructed_worktree_count,
            "worktree_count": self.worktree_count,
            "ignored_content_reads": self.ignored_content_reads,
            "private_content_reads": self.private_content_reads,
            "selected_byte_state_fingerprint": self.selected_byte_state_fingerprint,
            "local_ref_state_fingerprint": self.local_ref_state_fingerprint,
            "stable_common_state_fingerprint": self.stable_common_state_fingerprint,
            "original_worktree_state_fingerprint": self.original_worktree_state_fingerprint,
            "reconstructed_worktree_state_fingerprint": self.reconstructed_worktree_state_fingerprint,
            "selected_bytes": [item.to_mapping() for item in self.selected_bytes],
            "local_refs": [
                {"ref_fingerprint": name, "oid": oid} for name, oid in self.local_refs
            ],
            "stable_common_state": [item.to_mapping() for item in self.stable_common_state],
            "original_worktrees": [item.to_mapping() for item in self.original_worktrees],
            "reconstructed_worktrees": [item.to_mapping() for item in self.reconstructed_worktrees],
            "snapshot_fingerprint": self.snapshot_fingerprint,
        }

    def to_canonical_json(self):
        return canonical(self.to_mapping())


def _build_snapshot(binding, repository, selected, refs, common, originals, recreated):
    if type(binding) is not ApprovedCutoverBindingV3 or not is_fingerprint(repository):
        raise GitByteStateError()
    selected = tuple(sorted(selected, key=lambda item: item.path_fingerprint))
    common = tuple(common)
    originals = tuple(originals)
    recreated = tuple(recreated)
    _require_selected(selected)
    _require_common(common)
    _require_worktrees(originals, "original", refs)
    _require_worktrees(recreated, "reconstructed", refs)
    if tuple((item.role, item.placement, item.ref_fingerprint, item.commit_oid) for item in originals) != tuple(
        (item.role, item.placement, item.ref_fingerprint, item.commit_oid) for item in recreated
    ):
        raise GitByteStateError()
    segments = {
        "selected_byte_state_fingerprint": fingerprint("r2-selected-git-bytes-v2", [item.to_mapping() for item in selected]),
        "local_ref_state_fingerprint": fingerprint("r2-local-ref-state-v2", refs),
        "stable_common_state_fingerprint": fingerprint("r2-stable-git-common-state-v2", [item.to_mapping() for item in common]),
        "original_worktree_state_fingerprint": fingerprint("r2-original-worktrees-v2", [item.to_mapping() for item in originals]),
        "reconstructed_worktree_state_fingerprint": fingerprint("r2-reconstructed-worktrees-v2", [item.to_mapping() for item in recreated]),
    }
    body = _snapshot_body(binding, repository, selected, refs, common, originals, recreated, segments)
    serialized = _serialize_snapshot_body(body)
    return _allocate(
        GitByteSnapshotV2,
        {
            **body,
            "snapshot_fingerprint": fingerprint(
                "r2-git-byte-snapshot-v2", serialized
            ),
        },
    )


def _snapshot_body(binding, repository, selected, refs, common, originals, recreated, segments):
    return {
        "snapshot_type": "GitByteSnapshotV2",
        "binding_fingerprint": binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "repository_identity_fingerprint": repository,
        "selected_byte_count": len(selected),
        "local_ref_count": 14,
        "stable_common_state_role_count": 5,
        "original_worktree_count": 11,
        "reconstructed_worktree_count": 11,
        "worktree_count": 11,
        "ignored_content_reads": 0,
        "private_content_reads": 0,
        **segments,
        "selected_bytes": selected,
        "local_refs": refs,
        "stable_common_state": common,
        "original_worktrees": originals,
        "reconstructed_worktrees": recreated,
    }


def _serialize_snapshot_body(body):
    result = dict(body)
    result["selected_bytes"] = [
        item.to_mapping() for item in body["selected_bytes"]
    ]
    result["local_refs"] = [
        {"ref_fingerprint": name, "oid": oid}
        for name, oid in body["local_refs"]
    ]
    result["stable_common_state"] = [
        item.to_mapping() for item in body["stable_common_state"]
    ]
    result["original_worktrees"] = [
        item.to_mapping() for item in body["original_worktrees"]
    ]
    result["reconstructed_worktrees"] = [
        item.to_mapping() for item in body["reconstructed_worktrees"]
    ]
    return result


def _require_selected(values):
    if not 1 <= len(values) <= 10_000 or any(type(item) is not SelectedGitByteV2 for item in values) or len({item.path_fingerprint for item in values}) != len(values):
        raise GitByteStateError()


def _require_common(values):
    if tuple(item.role for item in values) != tuple(GitCommonStateRoleV2) or any(type(item) is not GitCommonStateV2 for item in values):
        raise GitByteStateError()


def _require_worktrees(values, kind, refs):
    ref_map = dict(refs)
    if len(values) != 11:
        raise GitByteStateError()
    for index, item in enumerate(values, start=1):
        placement = "embedded" if index <= 8 else "external"
        if type(item) is not GitWorktreeStateV2 or (item.role, item.placement, item.state_kind) != (f"worktree_{index:02d}", placement, kind) or ref_map.get(item.ref_fingerprint) != item.commit_oid:
            raise GitByteStateError()


def _normalize_refs(values):
    if type(values) is not tuple or len(values) != 14:
        raise GitByteStateError()
    result = []
    for name, oid in values:
        if type(name) is not str or not name.startswith("refs/heads/") or not is_oid(oid):
            raise GitByteStateError()
        result.append((sha256(name.encode("utf-8")), oid))
    result = tuple(sorted(result))
    if len({name for name, _oid in result}) != 14:
        raise GitByteStateError()
    return result


def _parse_refs(values):
    if type(values) is not list or len(values) != 14:
        raise GitByteStateError()
    result = tuple((item.get("ref_fingerprint"), item.get("oid")) for item in values if type(item) is dict and set(item) == {"ref_fingerprint", "oid"})
    if len(result) != 14 or any(not is_fingerprint(name) or not is_oid(oid) for name, oid in result) or tuple(sorted(result)) != result:
        raise GitByteStateError()
    return result


def _snapshot_field_names():
    return set(GitByteSnapshotV2.__dataclass_fields__)


def strict_git_byte_object_v2(payload):
    if type(payload) is not bytes or not 1 <= len(payload) <= 1_048_576:
        raise GitByteStateError()
    def pairs(values):
        result = {}
        for key, value in values:
            if type(key) is not str or key in result:
                raise GitByteStateError()
            result[key] = value
        return result
    try:
        value = json.loads(payload.decode("ascii"), object_pairs_hook=pairs, parse_constant=lambda _value: (_ for _ in ()).throw(GitByteStateError()))
    except GitByteStateError:
        raise
    except Exception:
        raise GitByteStateError() from None
    if type(value) is not dict:
        raise GitByteStateError()
    return value


def _allocate(kind, values):
    result = object.__new__(kind)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result
