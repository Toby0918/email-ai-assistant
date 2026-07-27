"""Strict semantic verification tests for migration evidence packages."""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Callable
from unittest import mock

from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
    verify_migration_evidence_package,
)
from backend.migration_evidence.errors import MigrationEvidenceError
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
)

MIGRATION_EVIDENCE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "backend"
    / "migration_evidence"
)


def relative_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.level == 1
    }


def called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }


def rewrite_package(
    source: Path,
    target: Path,
    mutate: Callable[
        [dict[str, bytes], dict[str, object]],
        None,
    ],
) -> None:
    with zipfile.ZipFile(source, "r") as archive:
        payloads = {
            name: archive.read(name)
            for name in archive.namelist()
            if name != "manifest.json"
        }
        manifest = json.loads(
            archive.read("manifest.json").decode("utf-8")
        )
    mutate(payloads, manifest)
    encoded = json.dumps(
        manifest,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as archive:
        for name, payload in sorted(payloads.items()):
            archive.writestr(name, payload)
        archive.writestr("manifest.json", encoded)
        archive.comment = (
            b"sha256:" + hashlib.sha256(encoded).hexdigest().encode("ascii")
        )


class MigrationEvidenceVerificationTests(unittest.TestCase):
    def test_creator_and_verifier_have_separate_capabilities(self) -> None:
        creator = MIGRATION_EVIDENCE_ROOT / "package.py"
        shared_validator = (
            MIGRATION_EVIDENCE_ROOT / "archive_validation.py"
        )
        verifier = MIGRATION_EVIDENCE_ROOT / "verification.py"

        self.assertNotIn("verification", relative_imports(creator))
        self.assertNotIn(
            "_validate_package_payload",
            called_names(creator),
        )
        self.assertTrue(
            {"package", "publication"}.isdisjoint(
                relative_imports(verifier)
            )
        )
        self.assertTrue(
            {
                "create_migration_evidence_package",
                "publish_new_package",
            }.isdisjoint(called_names(verifier))
        )
        self.assertNotIn(
            "git_discovery",
            relative_imports(shared_validator),
        )
        self.assertNotIn("git_output", called_names(shared_validator))

    def test_importing_verifier_does_not_load_creator_or_publication(
        self,
    ) -> None:
        script = (
            "import backend.migration_evidence.verification\n"
            "import sys\n"
            "blocked = {\n"
            " 'backend.migration_evidence.package',\n"
            " 'backend.migration_evidence.publication',\n"
            "} & set(sys.modules)\n"
            "raise SystemExit(1 if blocked else 0)\n"
        )

        completed = subprocess.run(
            (sys.executable, "-B", "-c", script),
            cwd=MIGRATION_EVIDENCE_ROOT.parents[1],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )

        self.assertEqual(completed.returncode, 0)

    def test_semantic_validation_failure_cannot_cross_commit_point(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            target = (
                root
                / "target"
                / "prepublication.migration-evidence.zip"
            )
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )

            with mock.patch(
                "backend.migration_evidence.package._require_package_valid",
                create=True,
                side_effect=MigrationEvidenceError(
                    "migration_evidence_create_failed"
                ),
            ):
                result = create_migration_evidence_package(
                    review=review,
                    confirmed_review_fingerprint=(
                        review.review_fingerprint
                    ),
                )

            self.assertEqual(
                result.status,
                MigrationEvidenceStatus.FAILED,
            )
            self.assertFalse(target.exists())

    def test_package_larger_than_one_snapshot_file_still_verifies(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            (repository / "docs").mkdir()
            payload = b"x" * (9 * 1024 * 1024)
            for name in ("first.json", "second.json"):
                (repository / "docs" / name).write_bytes(payload)
            target = root / "target" / "large.migration-evidence.zip"
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(
                    "docs/first.json",
                    "docs/second.json",
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

            self.assertGreater(target.stat().st_size, 16 * 1024 * 1024)
            self.assertEqual(
                created.status,
                MigrationEvidenceStatus.CREATED,
            )
            self.assertEqual(
                verified.status,
                MigrationEvidenceStatus.VERIFIED,
            )

    def test_verifier_rejects_semantically_incomplete_or_drifted_packages(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            (repository / "backend" / "service.py").write_text(
                "VALUE = 'dirty'\n",
                encoding="utf-8",
            )
            target = root / "target" / "valid.migration-evidence.zip"
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=("backend/service.py",),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )
            created = create_migration_evidence_package(
                review=review,
                confirmed_review_fingerprint=review.review_fingerprint,
            )
            self.assertEqual(
                created.status,
                MigrationEvidenceStatus.CREATED,
            )

            def remove_host(payloads, manifest) -> None:
                del payloads["evidence/host.json"]
                manifest["files"] = [
                    item
                    for item in manifest["files"]
                    if item["path"] != "evidence/host.json"
                ]

            def invalidate_worktree_types(_payloads, manifest) -> None:
                manifest["worktrees"][0]["status_count"] = "one"

            def drift_snapshot(_payloads, manifest) -> None:
                manifest["snapshot_records"][0]["status"] = "M "

            def invalidate_review_fingerprint(
                _payloads,
                manifest,
            ) -> None:
                manifest["review_fingerprint"] = "not-a-digest"

            mutations = {
                "missing-host": remove_host,
                "invalid-worktree": invalidate_worktree_types,
                "snapshot-drift": drift_snapshot,
                "invalid-review": invalidate_review_fingerprint,
            }
            for name, mutate in mutations.items():
                with self.subTest(name=name):
                    tampered = (
                        root
                        / "target"
                        / f"{name}.migration-evidence.zip"
                    )
                    rewrite_package(target, tampered, mutate)
                    result = verify_migration_evidence_package(
                        package=tampered
                    )
                    self.assertEqual(
                        result.status,
                        MigrationEvidenceStatus.FAILED,
                    )
                    self.assertEqual(result.counts.rejected, 1)


if __name__ == "__main__":
    unittest.main()
