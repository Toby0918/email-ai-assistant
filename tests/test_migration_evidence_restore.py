"""Synthetic round-trip tests for Git, index, and worktree evidence."""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
)
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
    run_git,
)


def status_bytes(repository: Path) -> bytes:
    completed = subprocess.run(
        (
            "git",
            "-c",
            "status.renames=false",
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        ),
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def index_bytes(repository: Path, path: str) -> bytes:
    completed = subprocess.run(
        ("git", "ls-files", "--stage", "-z", "--", path),
        cwd=repository,
        check=True,
        capture_output=True,
    )
    return completed.stdout


def write_payload(
    repository: Path,
    path: str,
    payload: bytes,
) -> None:
    target = repository.joinpath(*path.split("/"))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def restore_snapshot(
    repository: Path,
    archive: zipfile.ZipFile,
    records: list[dict[str, object]],
) -> None:
    for record in records:
        path = str(record["path"])
        target = repository.joinpath(*path.split("/"))
        index_path = record["index_archive_path"]
        if record["tracked"] is True:
            if index_path is None:
                run_git(repository, "rm", "-f", "--ignore-unmatch", "--", path)
            else:
                write_payload(repository, path, archive.read(str(index_path)))
                run_git(repository, "add", "--", path)
        worktree_path = record["worktree_archive_path"]
        if worktree_path is None:
            target.unlink(missing_ok=True)
        else:
            write_payload(repository, path, archive.read(str(worktree_path)))


class MigrationEvidenceRestoreTests(unittest.TestCase):
    def test_source_layer_drift_after_capture_fails_before_publication(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            (repository / "backend" / "service.py").write_text(
                "VALUE = 'dirty'\n",
                encoding="utf-8",
            )
            target = root / "target" / "drift.migration-evidence.zip"
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=("backend/service.py",),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )

            with mock.patch(
                "backend.migration_evidence.snapshot.read_checked_file",
                side_effect=(b"captured-first", b"drifted-later"),
            ):
                result = create_migration_evidence_package(
                    review=review,
                    confirmed_review_fingerprint=review.review_fingerprint,
                )

            self.assertEqual(
                result.status,
                MigrationEvidenceStatus.FAILED,
            )
            self.assertFalse(target.exists())

    def test_bundle_and_snapshot_restore_index_worktree_and_local_refs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            for path, text in {
                "backend/staged.py": "VALUE = 'committed staged'\n",
                "backend/mixed.py": "VALUE = 'committed mixed'\n",
                "docs/obsolete.md": "committed obsolete\n",
                "docs/renamed-old.md": "committed rename\n",
            }.items():
                write_payload(repository, path, text.encode("utf-8"))
            run_git(repository, "add", "backend", "docs")
            run_git(repository, "commit", "-m", "add synthetic restore sources")
            run_git(repository, "branch", "local-preserved")
            linked = root / "linked-worktree"
            run_git(
                repository,
                "worktree",
                "add",
                "-b",
                "linked-preserved",
                str(linked),
            )

            write_payload(
                repository,
                "backend/service.py",
                b"VALUE = 'unstaged worktree'\n",
            )
            write_payload(
                repository,
                "backend/staged.py",
                b"VALUE = 'staged index'\n",
            )
            run_git(repository, "add", "backend/staged.py")
            write_payload(
                repository,
                "backend/mixed.py",
                b"VALUE = 'mixed index'\n",
            )
            run_git(repository, "add", "backend/mixed.py")
            write_payload(
                repository,
                "backend/mixed.py",
                b"VALUE = 'mixed worktree'\n",
            )
            (repository / "docs" / "obsolete.md").unlink()
            run_git(
                repository,
                "mv",
                "docs/renamed-old.md",
                "docs/renamed-new.md",
            )
            write_payload(
                repository,
                "tests/test_untracked.py",
                b"RESTORED = True\n",
            )
            expected_status = status_bytes(repository)
            target = root / "target" / "reviewed.migration-evidence.zip"
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(
                    "backend/mixed.py",
                    "backend/service.py",
                    "backend/staged.py",
                    "docs/obsolete.md",
                    "docs/renamed-new.md",
                    "docs/renamed-old.md",
                    "tests/test_untracked.py",
                ),
                reviewed_refs=(
                    "refs/heads/linked-preserved",
                    "refs/heads/local-preserved",
                    "refs/heads/master",
                ),
                approved_worktrees=(repository, linked),
                host_baseline=host_baseline(),
            )

            result = create_migration_evidence_package(
                review=review,
                confirmed_review_fingerprint=review.review_fingerprint,
            )

            self.assertEqual(
                result.status,
                MigrationEvidenceStatus.CREATED,
            )
            with zipfile.ZipFile(target, "r") as archive:
                manifest = json.loads(
                    archive.read("manifest.json").decode("utf-8")
                )
                records = manifest["snapshot_records"]
                for record in records:
                    self.assertEqual(
                        set(record),
                        {
                            "path",
                            "status",
                            "tracked",
                            "index_archive_path",
                            "index_mode",
                            "index_size",
                            "index_sha256",
                            "worktree_archive_path",
                            "worktree_size",
                            "worktree_sha256",
                        },
                    )
                bundle = root / "restored.bundle"
                bundle.write_bytes(
                    archive.read("git/repository.bundle")
                )
                restored = root / "restored"
                run_git(root, "clone", str(bundle), str(restored))
                run_git(restored, "config", "user.name", "Restorer")
                run_git(
                    restored,
                    "config",
                    "user.email",
                    "restorer@example.invalid",
                )
                restore_snapshot(restored, archive, records)

            self.assertEqual(status_bytes(restored), expected_status)
            for record in records:
                path = str(record["path"])
                self.assertEqual(
                    index_bytes(restored, path),
                    index_bytes(repository, path),
                )
            heads = run_git(
                restored,
                "bundle",
                "list-heads",
                str(bundle),
            )
            expected_heads = "\n".join(
                f"{item.oid} {item.name}"
                for item in review.reviewed_refs
            )
            self.assertEqual(heads, expected_heads)
            run_git(restored, "fsck", "--full")
            for ref in review.reviewed_refs:
                run_git(restored, "cat-file", "-e", f"{ref.oid}^{{commit}}")
            linked_record = next(
                item
                for item in review.worktrees
                if item.branch_ref == "refs/heads/linked-preserved"
            )
            restored_linked = root / "restored-linked"
            run_git(
                restored,
                "branch",
                "linked-preserved",
                linked_record.head_oid,
            )
            run_git(
                restored,
                "worktree",
                "add",
                str(restored_linked),
                "linked-preserved",
            )
            self.assertEqual(
                run_git(restored_linked, "symbolic-ref", "HEAD"),
                linked_record.branch_ref,
            )
            self.assertEqual(
                run_git(restored_linked, "rev-parse", "HEAD"),
                linked_record.head_oid,
            )


if __name__ == "__main__":
    unittest.main()
