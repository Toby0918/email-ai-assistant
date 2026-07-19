"""Tests for bounded, temporary current-email attachment storage."""

from __future__ import annotations

import base64
import os
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.email_agent.attachment_storage import (
    AttachmentInputError,
    AttachmentOperationError,
    cleanup_expired_attachments,
    remove_stored_attachments,
    store_attachment_files,
)
from backend.email_agent.config import load_config


class AttachmentStorageTests(unittest.TestCase):
    def test_remove_stored_attachments_empties_request_directory_after_success(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)
            stored = store_attachment_files([self._file("current.pdf", b"current")], config)

            remove_stored_attachments(tuple(stored))

            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_remove_stored_attachments_deletes_only_exact_batch_and_is_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)
            stored = store_attachment_files([self._file("current.pdf", b"current")], config)
            unrelated = Path(directory) / "unrelated.pdf"
            unrelated.write_bytes(b"unrelated")

            remove_stored_attachments(tuple(stored))
            remove_stored_attachments(tuple(stored))

            self.assertFalse(stored[0].path.exists())
            self.assertTrue(unrelated.exists())

    def test_remove_stored_attachments_never_raises_or_exposes_unlink_failure(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)
            stored = store_attachment_files([self._file("current.pdf", b"current")], config)

            with patch.object(Path, "unlink", side_effect=OSError("PRIVATE_PATH_DETAIL")):
                remove_stored_attachments(tuple(stored))

            self.assertTrue(stored[0].path.exists())

    def test_store_attachment_files_rejects_file_over_byte_limit(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory, attachment_max_file_bytes=3)

            with self.assertRaises(AttachmentInputError):
                store_attachment_files([self._file("large.pdf", b"four")], config)

    def test_store_attachment_files_rejects_file_count_over_limit(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory, attachment_max_files=1)

            with self.assertRaises(AttachmentInputError):
                store_attachment_files([self._file("one.pdf", b"a"), self._file("two.pdf", b"b")], config)

    def test_store_attachment_files_rejects_total_bytes_over_limit(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory, attachment_max_file_bytes=8, attachment_max_total_bytes=3)

            with self.assertRaises(AttachmentInputError):
                store_attachment_files([self._file("one.pdf", b"ab"), self._file("two.pdf", b"cd")], config)

    def test_store_attachment_files_writes_only_contained_safe_files(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)

            stored = store_attachment_files([self._file("../../outside.pdf", b"safe")], config)

            self.assertEqual(stored[0].safe_filename, "outside.pdf")
            self.assertEqual(Path(stored[0].path).read_bytes(), b"safe")
            self.assertTrue(Path(stored[0].path).resolve().is_relative_to(Path(directory).resolve()))

    def test_store_attachment_files_removes_batch_when_later_write_fails(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)

            with patch(
                "backend.email_agent.attachment_storage.os.utime",
                side_effect=[None, OSError("disk write failed")],
            ):
                with self.assertRaises(AttachmentOperationError):
                    store_attachment_files(
                        [self._file("one.pdf", b"one"), self._file("two.pdf", b"two")],
                        config,
                    )

            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_cleanup_expired_attachments_converts_os_errors_to_input_error(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)
            expired = Path(directory) / "expired.pdf"
            expired.write_bytes(b"expired")
            now = datetime(2026, 7, 10, tzinfo=UTC)
            expired_at = now - timedelta(seconds=1)
            os.utime(expired, (expired_at.timestamp(), expired_at.timestamp()))
            with patch.object(Path, "unlink", side_effect=OSError("permission denied")):
                with self.assertRaises(AttachmentOperationError):
                    cleanup_expired_attachments(config, now=now)

    def test_cleanup_expired_attachments_deletes_only_expired_files(self) -> None:
        with TemporaryDirectory() as directory:
            config = self._config(directory)
            storage_dir = Path(directory)
            expired = storage_dir / "expired.pdf"
            current = storage_dir / "current.pdf"
            expired.write_bytes(b"expired")
            current.write_bytes(b"current")
            now = datetime(2026, 7, 10, tzinfo=UTC)
            os.utime(expired, (now.timestamp(), (now - timedelta(seconds=1)).timestamp()))
            os.utime(current, (now.timestamp(), (now + timedelta(hours=1)).timestamp()))

            removed = cleanup_expired_attachments(config, now=now)

            self.assertEqual(removed, 1)
            self.assertFalse(expired.exists())
            self.assertTrue(current.exists())

    def _config(self, directory: str, **values: int) -> object:
        return replace(load_config(dotenv_path=None), attachment_temp_dir=directory, **values)

    @staticmethod
    def _file(filename: str, content: bytes) -> dict[str, str]:
        return {
            "filename": filename,
            "type": "pdf",
            "content_base64": base64.b64encode(content).decode("ascii"),
        }


if __name__ == "__main__":
    unittest.main()
