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
        self.project = self.root / "synthetic-project"
        self.project.mkdir()
        self.synthetic_temp = str(self.root / "synthetic-system-temp")

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

    def test_missing_private_root_rejects_existing_parent_identity_drift(
        self,
    ) -> None:
        external = self.root / "external"
        replaced = self.root / "external-before-drift"
        external.mkdir()
        authority = external / "authority"
        mutated = False

        def mutate(stage: str, path: Path) -> None:
            nonlocal mutated
            if stage == "after_anchor_identity" and path == authority:
                external.rename(replaced)
                external.mkdir()
                mutated = True

        with patch(
            "backend.private_knowledge.storage_policy._test_path_hook",
            side_effect=mutate,
        ), patch(
            "backend.private_knowledge.storage_policy.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ), self.assertRaisesRegex(
            PrivateKnowledgeError,
            "private_storage_path_invalid",
        ):
            validate_private_storage(self.project, authority)

        self.assertTrue(mutated)

    def test_missing_snapshot_rejects_existing_parent_identity_drift(
        self,
    ) -> None:
        external = self.root / "snapshot-parent"
        replaced = self.root / "snapshot-parent-before-drift"
        external.mkdir()
        snapshot = external / "knowledge.pksnap"
        mutated = False

        def mutate(stage: str, path: Path) -> None:
            nonlocal mutated
            if stage == "after_anchor_identity" and path == snapshot:
                external.rename(replaced)
                external.mkdir()
                mutated = True

        with patch(
            "backend.private_knowledge.snapshot_path._test_path_hook",
            side_effect=mutate,
        ), patch(
            "backend.private_knowledge.snapshot_path.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ), self.assertRaisesRegex(
            PrivateKnowledgeError,
            "snapshot_path_invalid",
        ):
            validate_snapshot_path(snapshot, project_root=self.project)

        self.assertTrue(mutated)

    def test_unreadable_private_and_snapshot_anchor_state_uses_fixed_errors(
        self,
    ) -> None:
        authority = self.root / "external-authority"
        snapshot = self.root / "external-snapshot.pksnap"
        with patch(
            "backend.private_knowledge.storage_policy._existing_anchor_identity",
            side_effect=OSError("synthetic private detail"),
        ), self.assertRaises(PrivateKnowledgeError) as storage_error:
            validate_private_storage(self.project, authority)
        with patch(
            "backend.private_knowledge.snapshot_path._existing_anchor_identity",
            side_effect=OSError("synthetic private detail"),
        ), self.assertRaises(PrivateKnowledgeError) as snapshot_error:
            validate_snapshot_path(snapshot, project_root=self.project)

        self.assertEqual(storage_error.exception.code, "private_storage_path_invalid")
        self.assertEqual(snapshot_error.exception.code, "snapshot_path_invalid")
        self.assertNotIn("synthetic private detail", repr(storage_error.exception))
        self.assertNotIn("synthetic private detail", repr(snapshot_error.exception))

    def test_all_project_container_zones_are_rejected_for_private_stores(
        self,
    ) -> None:
        container = self.root / "managed" / "email_ai_assistant"
        repository = container / "main"
        repository.mkdir(parents=True)
        zones = (
            container,
            repository,
            container / "Runtimes",
            container / "LocalData",
            container / "RuntimeTemp",
            container / "Logs",
            container / "Artifacts",
            container / "Worktrees",
            container / "Config",
            container / "OperatorPrivate",
        )

        with patch(
            "backend.private_knowledge.storage_policy.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ):
            for zone in zones:
                with self.subTest(zone=zone), self.assertRaisesRegex(
                    PrivateKnowledgeError,
                    "private_storage_path_invalid",
                ):
                    validate_private_storage(
                        repository,
                        zone / "nested" / "authority",
                    )
                with self.subTest(
                    stage_zone=zone
                ), self.assertRaisesRegex(
                    PrivateKnowledgeError,
                    "private_storage_path_invalid",
                ):
                    validate_stage_storage(
                        zone / "nested" / "candidate",
                        self.root / "synthetic-raw-vault",
                        repository,
                    )

    def test_snapshot_rejects_project_container_zones(self) -> None:
        container = self.root / "managed" / "email_ai_assistant"
        repository = container / "main"
        repository.mkdir(parents=True)
        zones = (
            container,
            repository,
            container / "Runtimes",
            container / "LocalData",
            container / "RuntimeTemp",
            container / "Logs",
            container / "Artifacts",
            container / "Worktrees",
            container / "Config",
            container / "OperatorPrivate",
        )

        with patch(
            "backend.private_knowledge.snapshot_path.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ):
            for zone in zones:
                with self.subTest(zone=zone), self.assertRaisesRegex(
                    PrivateKnowledgeError,
                    "snapshot_path_invalid",
                ):
                    validate_snapshot_path(
                        zone / "nested" / "knowledge.pksnap",
                        project_root=repository,
                    )

    def test_missing_project_identity_maps_to_private_fixed_error(self) -> None:
        missing_project = self.root / "missing-project"

        with patch(
            "backend.private_knowledge.storage_policy.tempfile.gettempdir",
            return_value=self.synthetic_temp,
        ), self.assertRaisesRegex(
            PrivateKnowledgeError,
            "private_storage_path_invalid",
        ):
            validate_private_storage(
                missing_project,
                self.root / "external-authority",
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
                            store / "runtime" / "knowledge.pksnap",
                            project_root=self.project,
                        )


if __name__ == "__main__":
    unittest.main()
