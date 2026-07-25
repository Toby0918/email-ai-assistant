"""Synthetic review-plan tests for the migration evidence package."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
import zipfile
import json
from pathlib import Path

from backend.migration_evidence import (
    DirtyDisposition,
    HostBaseline,
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
    verify_migration_evidence_package,
)


def run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def create_repository(root: Path) -> Path:
    repository = root / "synthetic-repository"
    repository.mkdir()
    run_git(repository, "init", "--initial-branch=master")
    run_git(repository, "config", "user.name", "Synthetic Reviewer")
    run_git(repository, "config", "user.email", "reviewer@example.test")
    (repository / ".gitignore").write_text(
        ".env\n*.sqlite3\n.venv/\n",
        encoding="utf-8",
    )
    (repository / "backend").mkdir()
    (repository / "backend" / "service.py").write_text(
        "VALUE = 'committed'\n",
        encoding="utf-8",
    )
    run_git(repository, "add", ".gitignore", "backend/service.py")
    run_git(repository, "commit", "-m", "initial synthetic state")
    return repository


def host_baseline() -> HostBaseline:
    return HostBaseline(
        schema_version=1,
        acl_sha256="a" * 64,
        acl_entry_count=4,
        volume_sha256="b" * 64,
        filesystem_name="NTFS",
        drive_type="fixed",
        evidence_complete=True,
        content_observed=False,
    )


class MigrationEvidenceReviewTests(unittest.TestCase):
    def test_review_captures_diverged_local_remote_baseline_without_urls(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            remote = root / "remote.git"
            run_git(root, "init", "--bare", str(remote))
            repository = create_repository(root)
            run_git(repository, "remote", "add", "origin", str(remote))
            run_git(repository, "push", "-u", "origin", "master")
            peer = root / "peer"
            run_git(root, "clone", str(remote), str(peer))
            run_git(peer, "config", "user.name", "Synthetic Peer")
            run_git(
                peer,
                "config",
                "user.email",
                "peer@example.test",
            )
            (peer / "peer.md").write_text("peer\n", encoding="utf-8")
            run_git(peer, "add", "peer.md")
            run_git(peer, "commit", "-m", "peer commit")
            run_git(peer, "push", "origin", "master")
            (repository / "local.md").write_text(
                "local\n",
                encoding="utf-8",
            )
            run_git(repository, "add", "local.md")
            run_git(repository, "commit", "-m", "local commit")
            run_git(repository, "fetch", "origin")
            target = root / "target" / "baseline.migration-evidence.zip"
            target.parent.mkdir()

            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )

            self.assertEqual(
                review.git_baseline.branch_ref,
                "refs/heads/master",
            )
            self.assertEqual(review.git_baseline.upstream_ref, "origin/master")
            self.assertEqual(review.git_baseline.ahead, 1)
            self.assertEqual(review.git_baseline.behind, 1)
            self.assertEqual(
                tuple(item.name for item in review.git_baseline.remotes),
                ("origin",),
            )
            self.assertNotIn(str(remote), repr(review))

    def test_review_discovers_exact_dirty_refs_worktrees_and_exclusions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            target = root / "target" / "reviewed.migration-evidence.zip"
            target.parent.mkdir()
            (repository / "backend" / "service.py").write_text(
                "VALUE = 'reviewed dirty source'\n",
                encoding="utf-8",
            )
            (repository / "tests").mkdir()
            (repository / "tests" / "test_new.py").write_text(
                "def test_synthetic():\n    assert True\n",
                encoding="utf-8",
            )
            (repository / ".env").write_text(
                "SYNTHETIC_CREDENTIAL=never-read\n",
                encoding="utf-8",
            )
            (repository / "local.sqlite3").write_bytes(
                b"synthetic-private-sqlite-canary"
            )

            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(
                    "backend/service.py",
                    "tests/test_new.py",
                ),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )

            entries = {entry.path: entry for entry in review.dirty_entries}
            self.assertEqual(review.target, target)
            self.assertEqual(
                entries["backend/service.py"].disposition,
                DirtyDisposition.INCLUDED,
            )
            self.assertEqual(
                entries["tests/test_new.py"].disposition,
                DirtyDisposition.INCLUDED,
            )
            self.assertEqual(
                entries[".env"].disposition,
                DirtyDisposition.EXCLUDED,
            )
            self.assertEqual(
                entries["local.sqlite3"].disposition,
                DirtyDisposition.EXCLUDED,
            )
            self.assertEqual(
                review.reviewed_refs[0].name,
                "refs/heads/master",
            )
            self.assertEqual(review.reviewed_refs[0].oid, run_git(repository, "rev-parse", "HEAD"))
            self.assertEqual(review.worktrees[0].head_oid, run_git(repository, "rev-parse", "HEAD"))
            self.assertEqual(review.host_baseline, host_baseline())
            self.assertEqual(len(review.review_fingerprint), 64)
            int(review.review_fingerprint, 16)
            self.assertNotIn("never-read", repr(review))
            self.assertNotIn("synthetic-private-sqlite-canary", repr(review))

    def test_package_contains_independently_verified_bundle_and_hashed_payloads(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            target = root / "target" / "reviewed.migration-evidence.zip"
            target.parent.mkdir()
            (repository / "backend" / "service.py").write_text(
                "VALUE = 'restored tracked source'\n",
                encoding="utf-8",
            )
            (repository / "tests").mkdir()
            (repository / "tests" / "test_new.py").write_text(
                "RESTORED = True\n",
                encoding="utf-8",
            )
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(
                    "backend/service.py",
                    "tests/test_new.py",
                ),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )

            created = create_migration_evidence_package(
                review=review,
                confirmed_review_fingerprint=review.review_fingerprint,
            )
            verified = verify_migration_evidence_package(package=target)

            self.assertEqual(
                created.status,
                MigrationEvidenceStatus.CREATED,
            )
            self.assertEqual(
                verified.status,
                MigrationEvidenceStatus.VERIFIED,
            )
            self.assertEqual(created.counts.packages, 1)
            self.assertEqual(created.counts.refs, 1)
            self.assertEqual(created.counts.worktrees, 1)
            with zipfile.ZipFile(target, "r") as archive:
                names = archive.namelist()
                self.assertIn("manifest.json", names)
                self.assertIn("git/repository.bundle", names)
                self.assertIn(
                    "snapshot/worktree/backend/service.py",
                    names,
                )
                self.assertIn(
                    "snapshot/worktree/tests/test_new.py",
                    names,
                )
                manifest = json.loads(
                    archive.read("manifest.json").decode("utf-8")
                )
                listed = {entry["path"] for entry in manifest["files"]}
                self.assertEqual(
                    listed,
                    set(names) - {"manifest.json"},
                )
                self.assertRegex(
                    archive.comment.decode("ascii"),
                    r"\Asha256:[0-9a-f]{64}\Z",
                )
                bundle = root / "restored.bundle"
                bundle.write_bytes(archive.read("git/repository.bundle"))

            empty = root / "empty.git"
            run_git(root, "init", "--bare", str(empty))
            run_git(empty, "bundle", "verify", str(bundle))
            heads = run_git(empty, "bundle", "list-heads", str(bundle))
            self.assertEqual(
                heads,
                f"{run_git(repository, 'rev-parse', 'HEAD')} refs/heads/master",
            )


if __name__ == "__main__":
    unittest.main()
