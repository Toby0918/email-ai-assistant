"""Creator-owned commit binding regression coverage for Issue #54."""

from __future__ import annotations

import hashlib
import os
import unittest
import zipfile
from pathlib import Path
from unittest import mock

import backend.migration_evidence_publication.publication as composition
from backend.migration_evidence.archive_validation import (
    validate_package_payload,
)
from backend.migration_evidence.manifest import (
    build_archive,
    canonical_json,
    strict_json,
)
from backend.migration_evidence.snapshot import SnapshotPayload
from backend.migration_evidence_publication import (
    MigrationEvidencePublicationError,
)
from tests.migration_evidence_publication_fixtures import (
    PublicationReviewFixture,
)
from tests.test_migration_evidence_publication_create_verify import (
    _publish,
    _review,
)


def _alternate_valid_package(package: Path) -> bytes:
    with zipfile.ZipFile(package, "r") as archive:
        manifest = strict_json(archive.read("manifest.json"))
        payloads = {
            item["path"]: archive.read(item["path"])
            for item in manifest["files"]
        }
    snapshot = strict_json(payloads["snapshot/index.json"])
    mappings = snapshot["records"]
    index = next(
        offset
        for offset, item in enumerate(mappings)
        if item["worktree_archive_path"] is not None
    )
    mapping = dict(mappings[index])
    archive_path = mapping["worktree_archive_path"]
    altered = payloads[archive_path] + b"\nsynthetic race bytes\n"
    payloads[archive_path] = altered
    mapping["worktree_size"] = len(altered)
    mapping["worktree_sha256"] = hashlib.sha256(altered).hexdigest()
    mappings[index] = mapping
    payloads["snapshot/index.json"] = canonical_json(snapshot)
    records = tuple(SnapshotPayload(**item) for item in mappings)
    rebuilt = build_archive(
        review_fingerprint=manifest["review_fingerprint"],
        payloads=payloads,
        snapshot_records=records,
        refs=tuple(manifest["refs"]),
        worktrees=tuple(manifest["worktrees"]),
    )
    validate_package_payload(rebuilt)
    return rebuilt


class MigrationEvidencePublicationCommitBindingTests(
    unittest.TestCase
):
    def test_post_commit_valid_replacement_cannot_mint_receipt(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        real_create = composition.create_migration_evidence_package
        try:
            selection, review = _review(fixture)

            def create_then_replace(**values):
                result = real_create(**values)
                original = fixture.target.read_bytes()
                rebuilt = _alternate_valid_package(fixture.target)
                self.assertNotEqual(rebuilt, original)
                replacement = fixture.target.with_name(
                    "race-replacement.migration-evidence.zip"
                )
                replacement.write_bytes(rebuilt)
                os.replace(replacement, fixture.target)
                return result

            with mock.patch.object(
                composition,
                "create_migration_evidence_package",
                side_effect=create_then_replace,
            ), self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
            ):
                _publish(fixture, selection, review)
        finally:
            fixture.close()

    def test_post_rediscovery_source_drift_cannot_mint_receipt(
        self,
    ) -> None:
        fixture = PublicationReviewFixture()
        real_create = composition.create_migration_evidence_package
        source = fixture.repository / "backend" / "service.py"
        original = source.read_bytes()
        try:
            selection, review = _review(fixture)

            def drift_then_create(**values):
                source.write_bytes(
                    b"VALUE = 'post-rediscovery race bytes'\n"
                )
                return real_create(**values)

            with mock.patch.object(
                composition,
                "create_migration_evidence_package",
                side_effect=drift_then_create,
            ), self.assertRaisesRegex(
                MigrationEvidencePublicationError,
                "^MIGRATION_EVIDENCE_PUBLICATION_REJECTED$",
            ):
                _publish(fixture, selection, review)
            self.assertFalse(fixture.target.exists())
        finally:
            source.write_bytes(original)
            fixture.close()


if __name__ == "__main__":
    unittest.main()
