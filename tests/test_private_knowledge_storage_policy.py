"""Synthetic default-path isolation probes for private knowledge stores."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.snapshot_path import validate_snapshot_path
from backend.private_knowledge.storage_policy import (
    validate_private_storage,
    validate_stage_storage,
)


class PrivateKnowledgeStoragePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).absolute()
        self.project = Path("C:/synthetic-project")
        self.synthetic_temp = str(Path("C:/synthetic-system-temp"))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_private_and_stage_roots_reject_raw_vault_marker_ancestors(self) -> None:
        markers = (
            Path("vault-index.sqlite3"),
            Path("keys") / "recovery-state.json",
        )
        for marker in markers:
            for marker_is_directory in (False, True):
                with self.subTest(
                    marker=str(marker), marker_is_directory=marker_is_directory
                ):
                    raw = self.root / f"raw-{marker.name}-{marker_is_directory}"
                    marker_path = raw / marker
                    marker_path.parent.mkdir(parents=True, exist_ok=True)
                    if marker_is_directory:
                        marker_path.mkdir()
                    else:
                        marker_path.write_bytes(b"synthetic-marker")
                    authority = raw / "authority"
                    candidate = raw / "candidate"
                    with patch(
                        "backend.private_knowledge.storage_policy.tempfile.gettempdir",
                        return_value=self.synthetic_temp,
                    ):
                        with self.assertRaisesRegex(
                            PrivateKnowledgeError,
                            "private_storage_path_invalid",
                        ):
                            validate_private_storage(self.project, authority)
                        with self.assertRaisesRegex(
                            PrivateKnowledgeError,
                            "private_storage_path_invalid",
                        ):
                            validate_private_storage(self.project, candidate)
                        with self.assertRaisesRegex(
                            PrivateKnowledgeError,
                            "private_storage_path_invalid",
                        ):
                            validate_stage_storage(
                                candidate, self.root / "unrelated-vault", self.project
                            )

    def test_private_storage_checks_original_alias_before_resolution(self) -> None:
        original = self.root / "alias" / "authority"
        resolved = self.root / "target" / "authority"
        real_resolve = Path.resolve

        def resolve(path: Path, strict: bool = False) -> Path:
            if path == original:
                return resolved
            return real_resolve(path, strict=strict)

        def reject(path: Path) -> None:
            if path == original:
                raise PrivateKnowledgeError("private_storage_path_invalid")

        with patch.object(Path, "resolve", resolve), patch(
            "backend.private_knowledge.storage_policy._reject_reparse_components",
            side_effect=reject,
        ), patch(
            "backend.private_knowledge.storage_policy.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ), self.assertRaisesRegex(
            PrivateKnowledgeError, "private_storage_path_invalid"
        ):
            validate_private_storage(self.project, original)

    def test_ordinary_external_synthetic_roots_remain_valid(self) -> None:
        with patch(
            "backend.private_knowledge.storage_policy.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ):
            validate_private_storage(
                self.project, self.root / "authority", self.root / "candidate"
            )
            validate_stage_storage(
                self.root / "stage", self.root / "raw", self.project
            )

    def test_snapshot_rejects_file_or_directory_private_and_raw_markers(self) -> None:
        markers = (
            Path("candidate-key.pkenv"),
            Path("authority-keys.pkenv"),
            Path("vault-index.sqlite3"),
            Path("keys") / "recovery-state.json",
        )
        for marker in markers:
            for marker_is_directory in (False, True):
                with self.subTest(
                    marker=str(marker), marker_is_directory=marker_is_directory
                ):
                    store = self.root / f"store-{marker.name}-{marker_is_directory}"
                    marker_path = store / marker
                    marker_path.parent.mkdir(parents=True, exist_ok=True)
                    if marker_is_directory:
                        marker_path.mkdir()
                    else:
                        marker_path.write_bytes(b"synthetic-marker")
                    with patch(
                        "backend.private_knowledge.snapshot_path.tempfile.gettempdir",
                        return_value=self.synthetic_temp,
                    ), self.assertRaisesRegex(
                        PrivateKnowledgeError, "snapshot_path_invalid"
                    ):
                        validate_snapshot_path(
                            store / "runtime" / "knowledge.pksnap"
                        )


if __name__ == "__main__":
    unittest.main()
