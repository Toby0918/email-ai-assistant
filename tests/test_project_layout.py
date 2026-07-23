"""Public contract tests for repository placement and operational layout."""

from __future__ import annotations

import tempfile
import unittest
from dataclasses import fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.project_layout import (
    DirectoryIdentity,
    FlatOperationalLayoutAdapter,
    OperationalLayout,
    PlacementError,
    RepositoryPlacement,
    StandaloneStateKind,
)


ROOT = Path(__file__).resolve().parents[1]


class RepositoryPlacementTests(unittest.TestCase):
    def test_placement_can_only_be_created_through_validating_factories(self) -> None:
        with self.assertRaises(TypeError):
            RepositoryPlacement(
                repository_root=Path("repository"),
                project_container=None,
                standalone_state_root=Path("state"),
                protected_roots=(),
            )

    def test_managed_placement_accepts_exact_canonical_main_relationship(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            repository_root = project_container / "main"
            repository_root.mkdir(parents=True)

            placement = RepositoryPlacement.managed(
                repository_root=repository_root,
                project_container=project_container,
            )

        self.assertEqual(placement.repository_root, repository_root.resolve())
        self.assertEqual(placement.project_container, project_container.resolve())
        self.assertIsNone(placement.standalone_state_root)
        self.assertIsNone(placement.standalone_state_kind)
        self.assertEqual(placement.protected_roots, (project_container.resolve(),))

    def test_standalone_placement_requires_explicit_temporary_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory) / "portable-clone"
            state_root = Path(directory) / "verification-state"
            repository_root.mkdir()
            state_root.mkdir()

            placement = RepositoryPlacement.standalone(
                repository_root=repository_root,
                state_root=state_root,
                state_kind=StandaloneStateKind.TEMPORARY,
            )

        self.assertEqual(placement.repository_root, repository_root.resolve())
        self.assertIsNone(placement.project_container)
        self.assertEqual(placement.standalone_state_root, state_root.resolve())
        self.assertEqual(
            placement.standalone_state_kind,
            StandaloneStateKind.TEMPORARY,
        )
        self.assertEqual(
            placement.protected_roots,
            (repository_root.resolve(), state_root.resolve()),
        )

    def test_managed_placement_rejects_noncanonical_relationships_with_fixed_code(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cases = (
                (
                    root / "email_ai_assistant" / "repository",
                    root / "email_ai_assistant",
                ),
                (
                    root / "arbitrary-container" / "main",
                    root / "arbitrary-container",
                ),
                (
                    root / "other-parent" / "main",
                    root / "email_ai_assistant",
                ),
            )
            for repository_root, project_container in cases:
                repository_root.mkdir(parents=True, exist_ok=True)
                project_container.mkdir(parents=True, exist_ok=True)
                with self.subTest(repository_root=repository_root):
                    with self.assertRaises(PlacementError) as caught:
                        RepositoryPlacement.managed(
                            repository_root=repository_root,
                            project_container=project_container,
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "managed_relationship_invalid",
                    )
                    self.assertEqual(
                        str(caught.exception),
                        "managed_relationship_invalid",
                    )
                    self.assertNotIn(str(repository_root), repr(caught.exception))

    def test_missing_or_unreadable_identity_fails_with_fixed_code(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            repository_root = project_container / "main"
            project_container.mkdir()

            with self.assertRaises(PlacementError) as missing:
                RepositoryPlacement.managed(
                    repository_root=repository_root,
                    project_container=project_container,
                )

            repository_root.mkdir()

            def unreadable(path: Path) -> object:
                raise OSError(f"private native detail for {path}")

            with self.assertRaises(PlacementError) as unreadable_error:
                RepositoryPlacement.managed(
                    repository_root=repository_root,
                    project_container=project_container,
                    inspect_directory=unreadable,
                )

        self.assertEqual(
            missing.exception.code,
            "placement_identity_unavailable",
        )
        self.assertEqual(
            unreadable_error.exception.code,
            "placement_identity_unavailable",
        )
        self.assertNotIn("private native detail", repr(unreadable_error.exception))

    def test_standalone_rejects_unclassified_or_overlapping_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository_root = root / "portable-clone"
            nested_state = repository_root / "state"
            separate_state = root / "verification-state"
            nested_state.mkdir(parents=True)
            separate_state.mkdir()

            cases = (
                (separate_state, "temporary"),
                (nested_state, StandaloneStateKind.TEMPORARY),
            )
            for state_root, state_kind in cases:
                with self.subTest(state_root=state_root, state_kind=state_kind):
                    with self.assertRaises(PlacementError) as caught:
                        RepositoryPlacement.standalone(
                            repository_root=repository_root,
                            state_root=state_root,
                            state_kind=state_kind,  # type: ignore[arg-type]
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "standalone_state_root_invalid",
                    )

    def test_alias_to_canonical_main_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            canonical_repository = project_container / "main"
            alias_repository = Path(directory) / "alias-main"
            canonical_repository.mkdir(parents=True)
            alias_repository.mkdir()

            def aliasing_inspector(path: Path) -> object:
                canonical = (
                    canonical_repository
                    if path == alias_repository
                    else path
                )
                return SimpleNamespace(
                    canonical_path=canonical.resolve(),
                    device=7,
                    inode=11 if path == alias_repository else 12,
                    has_reparse_component=False,
                )

            with self.assertRaises(PlacementError) as caught:
                RepositoryPlacement.managed(
                    repository_root=alias_repository,
                    project_container=project_container,
                    inspect_directory=aliasing_inspector,
                )

        self.assertEqual(caught.exception.code, "placement_alias_invalid")

    def test_injected_identity_cannot_bless_parent_reference_alias(self) -> None:
        project_container = (
            Path(Path.cwd().anchor)
            / "synthetic"
            / "alias"
            / ".."
            / "email_ai_assistant"
        )
        repository_root = project_container / "main"

        def echoing_inspector(path: Path) -> DirectoryIdentity:
            return DirectoryIdentity(
                canonical_path=path,
                device=7,
                inode=11 if path == repository_root else 12,
            )

        with self.assertRaises(PlacementError) as caught:
            RepositoryPlacement.managed(
                repository_root=repository_root,
                project_container=project_container,
                inspect_directory=echoing_inspector,
            )

        self.assertEqual(caught.exception.code, "placement_alias_invalid")

    def test_missing_reparse_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            repository_root = project_container / "main"
            repository_root.mkdir(parents=True)

            def incomplete_inspector(path: Path) -> object:
                return SimpleNamespace(
                    canonical_path=path,
                    device=7,
                    inode=11 if path == repository_root else 12,
                )

            with self.assertRaises(PlacementError) as caught:
                RepositoryPlacement.managed(
                    repository_root=repository_root,
                    project_container=project_container,
                    inspect_directory=incomplete_inspector,
                )

        self.assertEqual(
            caught.exception.code,
            "placement_identity_unavailable",
        )

    def test_reparse_component_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            repository_root = project_container / "main"
            repository_root.mkdir(parents=True)

            def reparse_inspector(path: Path) -> DirectoryIdentity:
                return DirectoryIdentity(
                    canonical_path=path,
                    device=7,
                    inode=11 if path == repository_root else 12,
                    has_reparse_component=path == repository_root,
                )

            with self.assertRaises(PlacementError) as caught:
                RepositoryPlacement.managed(
                    repository_root=repository_root,
                    project_container=project_container,
                    inspect_directory=reparse_inspector,
                )

        self.assertEqual(caught.exception.code, "placement_reparse_forbidden")

    def test_identity_change_during_managed_validation_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            repository_root = project_container / "main"
            repository_root.mkdir(parents=True)
            calls: dict[Path, int] = {}

            def drifting_inspector(path: Path) -> DirectoryIdentity:
                calls[path] = calls.get(path, 0) + 1
                inode = (
                    99
                    if path == repository_root and calls[path] > 1
                    else 11 if path == repository_root else 12
                )
                return DirectoryIdentity(path, 7, inode)

            with self.assertRaises(PlacementError) as caught:
                RepositoryPlacement.managed(
                    repository_root=repository_root,
                    project_container=project_container,
                    inspect_directory=drifting_inspector,
                )

        self.assertEqual(caught.exception.code, "placement_identity_changed")
        self.assertEqual(calls[repository_root], 2)
        self.assertEqual(calls[project_container], 2)


class OperationalLayoutTests(unittest.TestCase):
    def test_layout_direct_construction_cannot_bypass_mode_mapping(self) -> None:
        absolute = Path("C:/synthetic/absolute")

        with self.assertRaises(PlacementError) as caught:
            OperationalLayout(
                runtime_root=absolute,
                data_root=absolute,
                temporary_root=absolute,
                log_root=absolute,
                artifact_root=absolute,
                worktree_root=absolute,
                configuration_root=absolute,
            )

        self.assertEqual(caught.exception.code, "operational_layout_invalid")

    def test_layout_rejects_relative_locations_with_fixed_code(self) -> None:
        relative = Path("relative")

        with self.assertRaises(PlacementError) as caught:
            OperationalLayout(
                runtime_root=relative,
                data_root=relative,
                temporary_root=relative,
                log_root=relative,
                artifact_root=relative,
                worktree_root=relative,
                configuration_root=relative,
            )

        self.assertEqual(caught.exception.code, "operational_layout_invalid")

    def test_layout_requires_a_validated_repository_placement(self) -> None:
        unvalidated = SimpleNamespace(
            project_container=Path("C:/synthetic/email_ai_assistant"),
            standalone_state_root=None,
        )

        with self.assertRaises(PlacementError) as caught:
            OperationalLayout.for_placement(unvalidated)  # type: ignore[arg-type]

        self.assertEqual(caught.exception.code, "operational_layout_invalid")

    def test_managed_layout_returns_only_absolute_ordinary_locations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            project_container = Path(directory) / "email_ai_assistant"
            repository_root = project_container / "main"
            repository_root.mkdir(parents=True)
            placement = RepositoryPlacement.managed(
                repository_root=repository_root,
                project_container=project_container,
            )

            layout = OperationalLayout.for_placement(placement)

        expected = {
            "runtime_root": project_container / "Runtimes",
            "data_root": project_container / "LocalData",
            "temporary_root": project_container / "RuntimeTemp",
            "log_root": project_container / "Logs",
            "artifact_root": project_container / "Artifacts",
            "worktree_root": project_container / "Worktrees",
            "configuration_root": project_container / "Config",
        }
        for field, path in expected.items():
            with self.subTest(field=field):
                self.assertEqual(getattr(layout, field), path.resolve())
                self.assertTrue(getattr(layout, field).is_absolute())
                self.assertFalse(getattr(layout, field).exists())

    def test_standalone_layout_is_contained_by_explicit_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory) / "portable-clone"
            state_root = Path(directory) / "verification-state"
            repository_root.mkdir()
            state_root.mkdir()
            placement = RepositoryPlacement.standalone(
                repository_root=repository_root,
                state_root=state_root,
                state_kind=StandaloneStateKind.SYNTHETIC,
            )

            layout = OperationalLayout.for_placement(placement)

        for path in (
            layout.runtime_root,
            layout.data_root,
            layout.temporary_root,
            layout.log_root,
            layout.artifact_root,
            layout.worktree_root,
            layout.configuration_root,
        ):
            self.assertEqual(path.parent, state_root.resolve())
            self.assertTrue(path.is_absolute())

    def test_layout_does_not_resolve_children_after_root_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory) / "portable-clone"
            state_root = Path(directory) / "verification-state"
            repository_root.mkdir()
            state_root.mkdir()
            placement = RepositoryPlacement.standalone(
                repository_root=repository_root,
                state_root=state_root,
                state_kind=StandaloneStateKind.SYNTHETIC,
            )

            with patch.object(
                Path,
                "resolve",
                side_effect=OSError("private reparse loop detail"),
            ):
                layout = OperationalLayout.for_placement(placement)

        self.assertEqual(layout.runtime_root, state_root / "Runtimes")
        self.assertEqual(layout.data_root, state_root / "LocalData")
        self.assertNotIn("private reparse loop detail", repr(layout))

    def test_flat_adapter_preserves_current_locations_without_a_third_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository_root = Path(directory) / "current-flat-repository"
            repository_root.mkdir()

            layout = FlatOperationalLayoutAdapter.resolve(repository_root)

        repository = repository_root.resolve()
        self.assertEqual(layout.runtime_root, repository / ".venv")
        self.assertEqual(layout.data_root, repository / "outputs")
        self.assertEqual(
            layout.temporary_root,
            repository / "outputs" / "attachment_temp",
        )
        self.assertEqual(layout.log_root, repository / "outputs")
        self.assertEqual(layout.artifact_root, repository / "outputs")
        self.assertEqual(layout.worktree_root, repository / ".worktrees")
        self.assertEqual(layout.configuration_root, repository)
        self.assertFalse(hasattr(RepositoryPlacement, "flat"))
        self.assertFalse(hasattr(RepositoryPlacement, "transition"))

    def test_flat_adapter_maps_missing_repository_to_fixed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            missing_repository = Path(directory) / "missing-flat-repository"

            with self.assertRaises(PlacementError) as caught:
                FlatOperationalLayoutAdapter.resolve(missing_repository)

        self.assertEqual(
            caught.exception.code,
            "placement_identity_unavailable",
        )


class ProjectLayoutCapabilityTests(unittest.TestCase):
    def test_returned_values_carry_only_approved_path_metadata(self) -> None:
        self.assertEqual(
            {field.name for field in fields(RepositoryPlacement)},
            {
                "repository_root",
                "project_container",
                "standalone_state_root",
                "standalone_state_kind",
                "protected_roots",
            },
        )
        self.assertEqual(
            {field.name for field in fields(OperationalLayout)},
            {
                "runtime_root",
                "data_root",
                "temporary_root",
                "log_root",
                "artifact_root",
                "worktree_root",
                "configuration_root",
            },
        )

    def test_documentation_records_issue_30_compatibility_boundary(self) -> None:
        required_phrases = {
            "AGENTS.md": "backend.project_layout",
            "README.md": "RepositoryPlacement",
            "CONTEXT.md": "Flat Layout Transition Adapter",
            "docs/constraints/tooling_constraints.md": "RepositoryPlacement",
            "docs/constraints/architecture_constraints.md": "backend/project_layout",
            "docs/decisions/0009-project-container-and-repository-boundaries.md": (
                "Issue #30 compatibility seam"
            ),
            "docs/operations/project_container_migration_task_brief.md": (
                "No parent-level `AGENTS.md`"
            ),
            "docs/operations/testing_checklist.md": (
                "Repository placement compatibility seam"
            ),
        }
        for relative_path, phrase in required_phrases.items():
            with self.subTest(path=relative_path):
                text = (ROOT / relative_path).read_text(encoding="utf-8")
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
