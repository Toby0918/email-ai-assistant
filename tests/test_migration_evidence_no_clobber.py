"""Create-only publication tests for migration evidence packages."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.migration_evidence.errors import MigrationEvidenceError
from backend.migration_evidence.publication import publish_new_package


class MigrationEvidenceNoClobberTests(unittest.TestCase):
    def test_existing_target_is_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = (
                Path(temporary).resolve()
                / "existing.migration-evidence.zip"
            )
            target.write_bytes(b"competitor")

            with self.assertRaises(MigrationEvidenceError):
                publish_new_package(target, b"reviewed")

            self.assertEqual(target.read_bytes(), b"competitor")
            self.assertEqual(
                tuple(target.parent.glob(f".{target.name}.*.tmp")),
                (),
            )

    def test_stage_swap_cannot_publish_unreviewed_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = (
                Path(temporary).resolve()
                / "race.migration-evidence.zip"
            )
            real_link = os.link

            def replace_stage_then_link(
                source,
                destination,
                **kwargs,
            ) -> None:
                source_path = Path(source)
                source_path.unlink()
                source_path.write_bytes(b"unreviewed")
                real_link(source, destination, **kwargs)

            with mock.patch(
                "backend.migration_evidence.publication.os.link",
                side_effect=replace_stage_then_link,
            ):
                with self.assertRaises(MigrationEvidenceError):
                    publish_new_package(target, b"reviewed")

            self.assertFalse(target.exists())

    def test_partial_write_never_creates_final_target(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = (
                Path(temporary).resolve()
                / "partial.migration-evidence.zip"
            )
            real_write = os.write
            calls = 0

            def fail_after_prefix(descriptor, payload):
                nonlocal calls
                calls += 1
                if calls == 1:
                    return real_write(descriptor, payload[:2])
                raise OSError("synthetic write failure")

            with mock.patch(
                "backend.migration_evidence.publication.os.write",
                side_effect=fail_after_prefix,
            ):
                with self.assertRaises(MigrationEvidenceError):
                    publish_new_package(target, b"reviewed")

            self.assertFalse(target.exists())
            self.assertEqual(
                tuple(target.parent.glob(f".{target.name}.*.tmp")),
                (),
            )

    def test_link_success_then_wrapper_error_keeps_exact_commit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = (
                Path(temporary).resolve()
                / "committed.migration-evidence.zip"
            )
            real_link = os.link

            def link_then_raise(source, destination, **kwargs) -> None:
                real_link(source, destination, **kwargs)
                raise OSError("synthetic wrapper error")

            with mock.patch(
                "backend.migration_evidence.publication.os.link",
                side_effect=link_then_raise,
            ):
                publish_new_package(target, b"reviewed")

            self.assertEqual(target.read_bytes(), b"reviewed")


if __name__ == "__main__":
    unittest.main()
