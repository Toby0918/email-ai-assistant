"""Strict semantic verification tests for migration evidence packages."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Callable

from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
    verify_migration_evidence_package,
)
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
)


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
