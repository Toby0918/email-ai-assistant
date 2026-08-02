"""Final-master receipt for one exact Git-byte snapshot."""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.r2_production_binding import ApprovedCutoverBindingV2

from .canonical import canonical, fingerprint
from ._git_byte_validation_v2 import GitByteStateError
from .git_byte_state_v2 import GitByteSnapshotV2, strict_git_byte_object_v2


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2GitByteStateReceiptV1:
    receipt_type: str
    status: str
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    repository_identity_fingerprint: str = field(repr=False)
    selected_byte_state_fingerprint: str = field(repr=False)
    local_ref_state_fingerprint: str = field(repr=False)
    stable_common_state_fingerprint: str = field(repr=False)
    original_worktree_state_fingerprint: str = field(repr=False)
    reconstructed_worktree_state_fingerprint: str = field(repr=False)
    snapshot_fingerprint: str = field(repr=False)
    selected_byte_count: int
    local_ref_count: int
    stable_common_state_role_count: int
    original_worktree_count: int
    reconstructed_worktree_count: int
    worktree_count: int
    ignored_content_reads: int
    private_content_reads: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2GitByteStateReceiptV1 requires create()")

    @classmethod
    def create(cls, *, binding, reviewed_snapshot, observed_snapshot):
        if (
            type(binding) is not ApprovedCutoverBindingV2
            or type(reviewed_snapshot) is not GitByteSnapshotV2
            or type(observed_snapshot) is not GitByteSnapshotV2
            or reviewed_snapshot.binding_fingerprint != binding.binding_fingerprint
            or observed_snapshot != reviewed_snapshot
        ):
            raise GitByteStateError()
        return _build_receipt(binding, reviewed_snapshot)

    @classmethod
    def from_json(cls, payload, *, binding, reviewed_snapshot):
        try:
            source = strict_git_byte_object_v2(payload)
            if canonical(source) != payload:
                raise GitByteStateError()
            result = _build_receipt(binding, reviewed_snapshot)
            if result.to_mapping() != source:
                raise GitByteStateError()
            return result
        except GitByteStateError:
            raise
        except Exception:
            raise GitByteStateError() from None

    def to_mapping(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}

    def to_canonical_json(self):
        return canonical(self.to_mapping())


def _build_receipt(binding, snapshot):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(snapshot) is not GitByteSnapshotV2
        or snapshot.binding_fingerprint != binding.binding_fingerprint
        or snapshot.final_master_binding_fingerprint
        != binding.final_master_binding_fingerprint
        or snapshot.final_commit_oid != binding.final_commit_oid
        or snapshot.final_tree_oid != binding.final_tree_oid
    ):
        raise GitByteStateError()
    names = (
        "binding_fingerprint",
        "final_master_binding_fingerprint",
        "final_commit_oid",
        "final_tree_oid",
        "repository_identity_fingerprint",
        "selected_byte_state_fingerprint",
        "local_ref_state_fingerprint",
        "stable_common_state_fingerprint",
        "original_worktree_state_fingerprint",
        "reconstructed_worktree_state_fingerprint",
        "snapshot_fingerprint",
        "selected_byte_count",
        "local_ref_count",
        "stable_common_state_role_count",
        "original_worktree_count",
        "reconstructed_worktree_count",
        "worktree_count",
        "ignored_content_reads",
        "private_content_reads",
    )
    body = {name: getattr(snapshot, name) for name in names}
    body.update(
        {
            "receipt_type": "R2GitByteStateReceiptV1",
            "status": "GIT_BYTE_STATE_VERIFIED",
            "source_package_fingerprint": binding.source_package_fingerprint,
        }
    )
    values = {
        **body,
        "receipt_fingerprint": fingerprint(
            "r2-git-byte-state-receipt-v1", body
        ),
    }
    result = object.__new__(R2GitByteStateReceiptV1)
    for name, value in values.items():
        object.__setattr__(result, name, value)
    return result
