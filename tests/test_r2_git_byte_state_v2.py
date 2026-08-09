"""Git-object byte and topology state contracts for Issue #92."""

from __future__ import annotations

import hashlib
import json
import unittest

from backend.r2_production_binding import (
    ApprovedCutoverBindingV3,
    OperatorRoleV2,
    ProductionRoleV2,
)
from backend.r2_solo_maintainer_closure import FinalMasterBindingV1
from backend.r2_repository_manifest import (
    GitByteSnapshotV2,
    GitByteStateError,
    GitCommonStateRoleV2,
    GitCommonStateV2,
    GitWorktreeStateV2,
    R2GitByteStateReceiptV1,
    SelectedGitByteV2,
)


class R2GitByteStateV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.selected = (
            _selected("backend/app.py", b"print('synthetic')\n"),
            _selected("docs/guide.md", b"synthetic guide\n"),
        )

    def test_exact_state_binds_git_bytes_refs_common_state_and_worktrees(self):
        reviewed = self._snapshot()
        observed = GitByteSnapshotV2.from_json(
            reviewed.to_canonical_json(), binding=self.binding
        )
        receipt = R2GitByteStateReceiptV1.create(
            binding=self.binding,
            reviewed_snapshot=reviewed,
            observed_snapshot=observed,
        )

        self.assertEqual(receipt.status, "GIT_BYTE_STATE_VERIFIED")
        self.assertEqual(receipt.selected_byte_count, 2)
        self.assertEqual(receipt.local_ref_count, 14)
        self.assertEqual(receipt.worktree_count, 11)
        self.assertEqual(receipt.original_worktree_count, 11)
        self.assertEqual(receipt.reconstructed_worktree_count, 11)
        self.assertEqual(receipt.stable_common_state_role_count, 5)
        self.assertEqual(receipt.ignored_content_reads, 0)
        self.assertEqual(receipt.private_content_reads, 0)
        self.assertEqual(receipt.binding_fingerprint, self.binding.binding_fingerprint)
        self.assertEqual(receipt.final_commit_oid, self.binding.final_commit_oid)
        self.assertEqual(receipt.final_tree_oid, self.binding.final_tree_oid)
        self.assertEqual(
            R2GitByteStateReceiptV1.from_json(
                receipt.to_canonical_json(),
                binding=self.binding,
                reviewed_snapshot=reviewed,
            ),
            receipt,
        )

    def test_same_size_eol_and_index_only_drift_fail_before_snapshot(self):
        original = b"line one\nline two\n"
        oid = _blob_oid(original)
        cases = (
            {"checkout_bytes": b"line 0ne\nline two\n"},
            {"checkout_bytes": b"line one\r\nline two\r\n"},
            {"index_oid": "f" * 40},
            {"index_stage": 1},
            {"assume_unchanged": True},
            {"skip_worktree": True},
        )
        for change in cases:
            values = {
                "relative": "backend/exact.py",
                "mode": "100644",
                "blob_oid": oid,
                "git_object_bytes": original,
                "checkout_bytes": original,
                "index_oid": oid,
                "index_mode": "100644",
                "index_stage": 0,
                "assume_unchanged": False,
                "skip_worktree": False,
            }
            values.update(change)
            with self.subTest(change=change):
                with self.assertRaisesRegex(
                    GitByteStateError, "R2_GIT_BYTE_STATE_INVALID"
                ):
                    SelectedGitByteV2.create(**values)

    def test_ref_common_original_admin_and_reconstructed_bytes_drift_fail(self):
        reviewed = self._snapshot()
        cases = (
            self._snapshot(ref_oid="e" * 40),
            self._snapshot(common_bytes=b"changed common state"),
            self._snapshot(original_admin_bytes=b"changed original admin"),
            self._snapshot(reconstructed_checkout_bytes=b"changed checkout"),
        )
        for observed in cases:
            with self.subTest(snapshot=observed.snapshot_fingerprint):
                with self.assertRaisesRegex(
                    GitByteStateError, "R2_GIT_BYTE_STATE_INVALID"
                ):
                    R2GitByteStateReceiptV1.create(
                        binding=self.binding,
                        reviewed_snapshot=reviewed,
                        observed_snapshot=observed,
                    )

    def test_exact_cardinalities_and_zero_content_expansion_are_closed(self):
        with self.assertRaisesRegex(
            GitByteStateError, "R2_GIT_BYTE_STATE_INVALID"
        ):
            self._snapshot(ref_count=13)
        with self.assertRaisesRegex(
            GitByteStateError, "R2_GIT_BYTE_STATE_INVALID"
        ):
            self._snapshot(worktree_count=10)

        snapshot = self._snapshot()
        self.assertEqual(snapshot.ignored_content_reads, 0)
        self.assertEqual(snapshot.private_content_reads, 0)
        public = snapshot.to_canonical_json().decode("ascii")
        for raw in (
            "backend/app.py",
            "docs/guide.md",
            "refs/heads/synthetic-00",
            "original admin",
            "reconstructed admin",
        ):
            self.assertNotIn(raw, public)

    def test_fresh_process_rejects_tamper_and_mixed_binding(self):
        reviewed = self._snapshot()
        receipt = R2GitByteStateReceiptV1.create(
            binding=self.binding,
            reviewed_snapshot=reviewed,
            observed_snapshot=reviewed,
        )
        tampered = receipt.to_mapping()
        tampered["local_ref_count"] = 13
        payload = json.dumps(
            tampered,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("ascii")
        with self.assertRaisesRegex(
            GitByteStateError, "R2_GIT_BYTE_STATE_INVALID"
        ):
            R2GitByteStateReceiptV1.from_json(
                payload,
                binding=self.binding,
                reviewed_snapshot=reviewed,
            )
        with self.assertRaisesRegex(
            GitByteStateError, "R2_GIT_BYTE_STATE_INVALID"
        ):
            R2GitByteStateReceiptV1.from_json(
                receipt.to_canonical_json(),
                binding=_binding(final_commit="a" * 40),
                reviewed_snapshot=reviewed,
            )

    def _snapshot(
        self,
        *,
        ref_count=14,
        worktree_count=11,
        ref_oid=None,
        common_bytes=b"stable common state",
        original_admin_bytes=b"original admin",
        reconstructed_checkout_bytes=b"reconstructed checkout",
    ):
        refs = tuple(
            (
                f"refs/heads/synthetic-{index:02d}",
                ref_oid if index == 0 and ref_oid else f"{index + 20:040x}",
            )
            for index in range(ref_count)
        )
        common = tuple(
            GitCommonStateV2.create(role=role, content_bytes=common_bytes + role.value.encode("ascii"))
            for role in GitCommonStateRoleV2
        )
        originals = tuple(
            _worktree(
                index,
                "original",
                original_admin_bytes if index == 1 else b"original admin" + bytes([index]),
                b"original checkout" + bytes([index]),
            )
            for index in range(1, worktree_count + 1)
        )
        reconstructed = tuple(
            _worktree(
                index,
                "reconstructed",
                b"reconstructed admin" + bytes([index]),
                reconstructed_checkout_bytes if index == 1 else b"reconstructed checkout" + bytes([index]),
            )
            for index in range(1, worktree_count + 1)
        )
        return GitByteSnapshotV2.create(
            binding=self.binding,
            repository_identity_fingerprint="9" * 64,
            selected_bytes=self.selected,
            local_refs=refs,
            stable_common_state=common,
            original_worktrees=originals,
            reconstructed_worktrees=reconstructed,
        )


def _selected(relative, content):
    oid = _blob_oid(content)
    return SelectedGitByteV2.create(
        relative=relative,
        mode="100644",
        blob_oid=oid,
        git_object_bytes=content,
        checkout_bytes=content,
        index_oid=oid,
        index_mode="100644",
        index_stage=0,
        assume_unchanged=False,
        skip_worktree=False,
    )


def _worktree(index, state_kind, admin_bytes, checkout_bytes):
    return GitWorktreeStateV2.create(
        role=f"worktree_{index:02d}",
        placement="embedded" if index <= 8 else "external",
        state_kind=state_kind,
        branch_ref=f"refs/heads/synthetic-{index:02d}",
        commit_oid=f"{index + 20:040x}",
        physical_identity_fingerprint=f"{index + 60:064x}",
        admin_identity_fingerprint=f"{index + 80:064x}",
        admin_content_bytes=admin_bytes,
        checkout_bytes=checkout_bytes,
    )


def _blob_oid(content):
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _binding(*, final_commit="1" * 40):
    final_master = FinalMasterBindingV1.create(
        final_commit_oid=final_commit,
        final_tree_oid="2" * 40,
        source_package_fingerprint="3" * 64,
        runbook_fingerprint="4" * 64,
        workflow_fingerprint="5" * 64,
    )
    return ApprovedCutoverBindingV3.create(
        final_master_binding=final_master,
        operation_fingerprint="6" * 64,
        operator_role_fingerprints={
            role: f"{index + 10:064x}" for index, role in enumerate(OperatorRoleV2)
        },
        production_role_fingerprints={
            role: f"{index + 30:064x}" for index, role in enumerate(ProductionRoleV2)
        },
    )


if __name__ == "__main__":
    unittest.main()
