from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
)
from backend.migration_evidence_publication.package_observation import (
    observe_created_package,
)
from backend.migration_evidence_verifier import (
    PackageVerificationStatus,
    verify_package_in_separate_process,
)
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
)


class CreatedPackageObservationTests(unittest.TestCase):
    def test_observation_binds_hashes_physical_identity_and_counts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repository = create_repository(root)
            (repository / "backend" / "notes.py").write_text(
                "synthetic review note\n",
                encoding="utf-8",
            )
            publication = root / "publication"
            publication.mkdir()
            target = publication / "reviewed.migration-evidence.zip"
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=("backend/notes.py",),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )
            created = create_migration_evidence_package(
                review=review,
                confirmed_review_fingerprint=review.review_fingerprint,
            )
            self.assertIs(
                created.status,
                MigrationEvidenceStatus.CREATED,
            )

            observation = observe_created_package(package=target)
            verified = verify_package_in_separate_process(
                package=target
            )

            self.assertEqual(
                observation.review_fingerprint,
                review.review_fingerprint,
            )
            self.assertIs(
                verified.status,
                PackageVerificationStatus.VERIFIED,
            )
            self.assertEqual(
                observation.counts.files,
                created.counts.files,
            )
            self.assertEqual(observation.counts.refs, 1)
            self.assertEqual(observation.counts.worktrees, 1)
            for fingerprint in (
                observation.package_sha256,
                observation.manifest_sha256,
                observation.package_identity_fingerprint,
                observation.counts_fingerprint,
            ):
                self.assertEqual(len(fingerprint), 64)
                self.assertTrue(
                    set(fingerprint)
                    <= set("0123456789abcdef")
                )
            self.assertEqual(
                (
                    observation.package_sha256,
                    observation.manifest_sha256,
                    observation.package_identity_fingerprint,
                    observation.counts_fingerprint,
                ),
                (
                    verified.package_sha256,
                    verified.manifest_sha256,
                    verified.package_identity_fingerprint,
                    verified.counts_fingerprint,
                ),
            )
            self.assertNotIn(str(target), repr(observation))
            self.assertNotIn("refs/heads/master", repr(observation))

    def test_exact_byte_replacement_changes_package_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            repository = create_repository(root)
            (repository / "backend" / "notes.py").write_text(
                "synthetic review note\n",
                encoding="utf-8",
            )
            publication = root / "publication"
            publication.mkdir()
            target = publication / "reviewed.migration-evidence.zip"
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=("backend/notes.py",),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )
            create_migration_evidence_package(
                review=review,
                confirmed_review_fingerprint=review.review_fingerprint,
            )
            before = observe_created_package(package=target)
            payload = target.read_bytes()
            replacement = target.with_name("replacement.bin")
            replacement.write_bytes(payload)
            os.replace(replacement, target)

            after = observe_created_package(package=target)

            self.assertEqual(
                after.package_sha256,
                before.package_sha256,
            )
            self.assertEqual(
                after.manifest_sha256,
                before.manifest_sha256,
            )
            self.assertNotEqual(
                after.package_identity_fingerprint,
                before.package_identity_fingerprint,
            )


if __name__ == "__main__":
    unittest.main()
