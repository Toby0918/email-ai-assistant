"""Separate-process, read-only Migration Evidence Package verification."""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import stat
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import backend.migration_evidence_verifier.worker as verifier_worker
from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
)
from backend.migration_evidence.manifest import (
    build_archive,
    strict_json,
)
from backend.migration_evidence.snapshot import SnapshotPayload
from backend.migration_evidence_verifier.canonical import (
    VerifierProcessError,
)
from backend.migration_evidence_verifier import (
    PackageVerificationStatus,
    verify_package_in_separate_process,
)
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
)


def create_synthetic_package(root: Path) -> Path:
    repository = create_repository(root)
    target = (
        root
        / "published"
        / "reviewed.migration-evidence.zip"
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
    result = create_migration_evidence_package(
        review=review,
        confirmed_review_fingerprint=review.review_fingerprint,
    )
    if result.status is not MigrationEvidenceStatus.CREATED:
        raise AssertionError("synthetic package creation failed")
    return target


def process_fingerprint(process_id: int) -> str:
    return canonical_fingerprint(
        {
            "process_id": process_id,
            "schema": "MigrationEvidenceVerifierProcessV1",
        }
    )


def canonical_fingerprint(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def manifest_bytes(package: Path) -> bytes:
    with zipfile.ZipFile(package, "r") as archive:
        return archive.read("manifest.json")


def rewrite_manifest_with_stale_comment(
    source: Path,
    target: Path,
) -> None:
    with zipfile.ZipFile(source, "r") as archive:
        entries = [
            (item, archive.read(item))
            for item in archive.infolist()
        ]
        comment = archive.comment
    with zipfile.ZipFile(
        target,
        "w",
        compression=zipfile.ZIP_STORED,
    ) as archive:
        for info, payload in entries:
            if info.filename == "manifest.json":
                value = json.loads(payload.decode("utf-8"))
                value["review_fingerprint"] = "f" * 64
                payload = json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            archive.writestr(info, payload)
        archive.comment = comment


def rewrite_with_invalid_bundle(source: Path) -> bytes:
    with zipfile.ZipFile(source, "r") as archive:
        manifest = strict_json(archive.read("manifest.json"))
        payloads = {
            item["path"]: archive.read(item["path"])
            for item in manifest["files"]
        }
    payloads["git/repository.bundle"] = (
        b"synthetic invalid Git bundle bytes"
    )
    return build_archive(
        review_fingerprint=manifest["review_fingerprint"],
        payloads=payloads,
        snapshot_records=tuple(
            SnapshotPayload(**item)
            for item in manifest["snapshot_records"]
        ),
        refs=tuple(manifest["refs"]),
        worktrees=tuple(manifest["worktrees"]),
    )


class MigrationEvidenceVerifierProcessTests(unittest.TestCase):
    def test_valid_package_is_reread_in_a_different_process(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            package = create_synthetic_package(
                Path(temporary).resolve()
            )
            before = package.read_bytes()

            observation = verify_package_in_separate_process(
                package=package
            )

            self.assertIs(
                observation.status,
                PackageVerificationStatus.VERIFIED,
            )
            self.assertEqual(
                observation.package_sha256,
                hashlib.sha256(before).hexdigest(),
            )
            manifest = manifest_bytes(package)
            manifest_value = json.loads(manifest.decode("utf-8"))
            manifest_sha256 = hashlib.sha256(
                manifest
            ).hexdigest()
            self.assertEqual(
                observation.review_fingerprint,
                manifest_value["review_fingerprint"],
            )
            package_stat = package.stat()
            self.assertEqual(
                observation.manifest_sha256,
                manifest_sha256,
            )
            self.assertEqual(
                observation.package_identity_fingerprint,
                canonical_fingerprint(
                    {
                        "schema": (
                            "MigrationEvidencePackageIdentityV1"
                        ),
                        "device": package_stat.st_dev,
                        "inode": package_stat.st_ino,
                        "mode_type": stat.S_IFMT(
                            package_stat.st_mode
                        ),
                        "links": package_stat.st_nlink,
                        "size": package_stat.st_size,
                        "modified_ns": package_stat.st_mtime_ns,
                        "package_sha256": hashlib.sha256(
                            before
                        ).hexdigest(),
                        "manifest_sha256": manifest_sha256,
                    }
                ),
            )
            self.assertEqual(observation.files, 5)
            self.assertEqual(observation.refs, 1)
            self.assertEqual(observation.worktrees, 1)
            self.assertEqual(
                observation.counts_fingerprint,
                canonical_fingerprint(
                    {
                        "schema": (
                            "MigrationEvidenceAggregateCountsV1"
                        ),
                        "files": 5,
                        "refs": 1,
                        "worktrees": 1,
                    }
                ),
            )
            self.assertNotEqual(
                observation.process_fingerprint,
                process_fingerprint(os.getpid()),
            )
            self.assertEqual(package.read_bytes(), before)

    def test_corruption_and_manifest_mismatch_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            package = create_synthetic_package(root)
            corrupted = (
                root
                / "published"
                / "corrupted.migration-evidence.zip"
            )
            original = package.read_bytes()
            corrupted.write_bytes(original[:-64])
            mismatched = (
                root
                / "published"
                / "manifest-mismatch.migration-evidence.zip"
            )
            rewrite_manifest_with_stale_comment(package, mismatched)
            linked = (
                root
                / "published"
                / "linked.migration-evidence.zip"
            )
            os.link(package, linked)

            for candidate in (corrupted, mismatched, linked):
                with self.subTest(candidate=candidate.name):
                    before = candidate.read_bytes()
                    observation = verify_package_in_separate_process(
                        package=candidate
                    )

                    self.assertIs(
                        observation.status,
                        PackageVerificationStatus.REJECTED,
                    )
                    self.assertEqual(
                        observation.review_fingerprint,
                        "0" * 64,
                    )
                    self.assertEqual(observation.files, 0)
                    self.assertEqual(observation.refs, 0)
                    self.assertEqual(observation.worktrees, 0)
                    self.assertEqual(candidate.read_bytes(), before)

    def test_path_aba_cannot_substitute_verified_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            package = create_synthetic_package(root)
            verified_payload = package.read_bytes()
            invalid_payload = rewrite_with_invalid_bundle(package)
            package.write_bytes(invalid_payload)
            held = package.with_name(
                "held-invalid.migration-evidence.zip"
            )
            replacement = package.with_name(
                "replacement-valid.migration-evidence.zip"
            )
            real_verify = verifier_worker.verify_existing_payload

            def transient_replacement(**values):
                os.replace(package, held)
                replacement.write_bytes(verified_payload)
                os.replace(replacement, package)
                try:
                    return real_verify(**values)
                finally:
                    package.unlink()
                    os.replace(held, package)

            request = {
                "schema_version": "PackageVerificationRequestV1",
                "package": str(package),
            }
            with mock.patch.object(
                verifier_worker,
                "verify_existing_payload",
                side_effect=transient_replacement,
            ), self.assertRaises(VerifierProcessError):
                verifier_worker._verify(
                    request,
                    process_fingerprint(os.getpid()),
                )
            self.assertEqual(package.read_bytes(), invalid_payload)

    def test_public_output_is_content_free_and_worker_is_distinct(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(
            prefix="secret-worktree-ref-oid-"
        ) as temporary:
            package = create_synthetic_package(
                Path(temporary).resolve()
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            logs = io.StringIO()
            handler = logging.StreamHandler(logs)
            root_logger = logging.getLogger()
            root_logger.addHandler(handler)
            try:
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    first = verify_package_in_separate_process(
                        package=package
                    )
                    second = verify_package_in_separate_process(
                        package=package
                    )
            finally:
                root_logger.removeHandler(handler)

            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(logs.getvalue(), "")
            self.assertEqual(
                repr(first),
                "<PackageVerificationObservationV1>",
            )
            self.assertNotEqual(
                first.process_fingerprint,
                second.process_fingerprint,
            )
            public = repr(
                (
                    first,
                    second,
                    stdout.getvalue(),
                    stderr.getvalue(),
                    logs.getvalue(),
                )
            )
            for forbidden in (
                str(package),
                "secret-worktree-ref-oid",
                "refs/heads/master",
                "Synthetic Reviewer",
                "reviewer@example.test",
                "Traceback",
                "Exception",
            ):
                self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
