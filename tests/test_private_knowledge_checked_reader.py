"""Descriptor-bound private-knowledge read tests with synthetic race hooks."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.private_knowledge import key_store
from backend.private_knowledge.atomic_ciphertext import read_ciphertext
from backend.private_knowledge.checked_reader import (
    read_bounded_checked,
    validate_read_path,
)
from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.read_only_file import read_snapshot_file


class PrivateKnowledgeCheckedReaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "synthetic.pksnap"
        self.path.write_bytes(b"A" * 64)

    def _read(self, hook=lambda _stage, _path: None, maximum: int = 1024) -> bytes:
        return read_bounded_checked(
            self.path,
            maximum,
            lambda path: validate_read_path(
                path, error_code="synthetic_read_failed"
            ),
            hook,
            error_code="synthetic_read_failed",
        )

    def test_uses_bounded_descriptor_read_without_path_read_bytes(self) -> None:
        with patch.object(
            Path, "read_bytes", side_effect=AssertionError("path read is forbidden")
        ):
            self.assertEqual(self._read(), b"A" * 64)

        self.path.write_bytes(b"B" * 65)
        with self.assertRaisesRegex(PrivateKnowledgeError, "synthetic_read_failed"):
            self._read(maximum=64)

    def test_detects_target_swap_before_descriptor_open(self) -> None:
        replacement = self.root / "replacement.pksnap"
        replacement.write_bytes(b"B" * 64)
        swapped = False

        def hook(stage: str, _path: Path) -> None:
            nonlocal swapped
            if stage == "read_before_open" and not swapped:
                os.replace(replacement, self.path)
                swapped = True

        with self.assertRaisesRegex(PrivateKnowledgeError, "synthetic_read_failed"):
            self._read(hook)

    def test_detects_target_or_size_swap_after_descriptor_open(self) -> None:
        for mutation in ("replace", "append"):
            with self.subTest(mutation=mutation):
                self.path.write_bytes(b"A" * 64)
                replacement = self.root / f"{mutation}.pksnap"
                replacement.write_bytes(b"B" * 64)
                changed = False

                def hook(stage: str, _path: Path) -> None:
                    nonlocal changed
                    if stage != "read_after_open" or changed:
                        return
                    if mutation == "replace":
                        os.replace(replacement, self.path)
                    else:
                        with self.path.open("ab") as handle:
                            handle.write(b"C")
                    changed = True

                with self.assertRaisesRegex(
                    PrivateKnowledgeError, "synthetic_read_failed"
                ):
                    self._read(hook)

    def test_authority_and_snapshot_readers_route_through_checked_reader(self) -> None:
        replacement = self.root / "replacement.bin"
        replacement.write_bytes(b"B" * 64)

        def swap(_stage: str, _path: Path) -> None:
            if replacement.exists():
                os.replace(replacement, self.path)

        with patch(
            "backend.private_knowledge.atomic_ciphertext._test_read_race_hook",
            side_effect=swap,
            create=True,
        ), self.assertRaisesRegex(PrivateKnowledgeError, "envelope_read_failed"):
            read_ciphertext(
                self.path, maximum=1024, code="envelope_read_failed"
            )

        self.path.write_bytes(b"A" * 64)
        replacement.write_bytes(b"B" * 64)
        with patch(
            "backend.private_knowledge.read_only_file._test_race_hook",
            side_effect=swap,
            create=True,
        ), self.assertRaisesRegex(PrivateKnowledgeError, "snapshot_unavailable"):
            read_snapshot_file(self.path)

    def test_authority_open_preserves_configured_root_for_reparse_revalidation(self) -> None:
        configured = self.root / "configured-authority"
        configured.mkdir()
        swapped_target = self.root / "forbidden-after-policy-check"
        swapped_target.mkdir()
        path_type = type(configured)
        original_resolve = path_type.resolve

        def synthetic_root_swap(path, *args, **kwargs):
            if path == configured:
                return swapped_target
            return original_resolve(path, *args, **kwargs)

        with patch.object(path_type, "resolve", new=synthetic_root_swap), patch.object(
            key_store,
            "read_ciphertext",
            side_effect=PrivateKnowledgeError("key_envelope_read_failed"),
        ) as reader, self.assertRaisesRegex(
            PrivateKnowledgeError, "key_envelope_read_failed"
        ):
            key_store.open_authority_keys(configured, object())

        self.assertEqual(
            reader.call_args.args[0],
            configured / "authority-keys.pkenv",
        )


if __name__ == "__main__":
    unittest.main()
