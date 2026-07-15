"""Synthetic stage-to-final private evaluation dataset build tests."""

from __future__ import annotations

import importlib
import importlib.util
import os
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from backend.private_evaluation import repository_io
from backend.private_evaluation.errors import PrivateEvaluationError
from backend.private_evaluation.repository import (
    DATASET_MAGIC,
    DATASET_PURPOSE,
    read_encrypted_dataset,
)
from backend.private_evaluation.staging_repository import (
    STAGE_MAGIC,
    STAGE_PURPOSE,
    EvaluationStageV1,
    read_encrypted_stage,
    write_encrypted_stage,
)
from tests.private_evaluation_fixtures import dataset_mapping, uuid4_for


def _load_builder(test: unittest.TestCase):
    name = "backend.private_evaluation.dataset_builder"
    test.assertIsNotNone(importlib.util.find_spec(name), "dataset builder module is missing")
    module = importlib.import_module(name)
    test.assertTrue(
        hasattr(module, "build_evaluation_dataset"),
        "build_evaluation_dataset is missing",
    )
    return module


def _load_new_writer(test: unittest.TestCase):
    module = importlib.import_module("backend.private_evaluation.repository")
    test.assertTrue(
        hasattr(module, "write_new_encrypted_dataset"),
        "create-only final dataset writer is missing",
    )
    return module.write_new_encrypted_dataset


def stage_value(*, pair_count: int = 200) -> EvaluationStageV1:
    source = dataset_mapping(200, pair_count=pair_count)
    return EvaluationStageV1.from_mapping({
        "schema_version": "PrivateEvaluationStageV1",
        "stage_namespace": uuid4_for(70_000),
        "cases": source["cases"],
    })


class PrivateEvaluationDatasetBuilderTests(unittest.TestCase):
    def test_builder_accepts_only_stage_and_creates_fresh_valid_namespace(self) -> None:
        builder = _load_builder(self)
        stage = stage_value()

        dataset = builder.build_evaluation_dataset(stage)

        self.assertEqual(dataset.schema_version, "PrivateEvaluationDatasetV1")
        self.assertEqual(len(dataset.cases), 200)
        self.assertEqual(dataset.cases, stage.cases)
        self.assertNotEqual(dataset.dataset_namespace, stage.stage_namespace)
        self.assertEqual(uuid.UUID(dataset.dataset_namespace).version, 4)
        self.assertNotIn(stage.cases[0].case_id, repr(dataset))

        for invalid in (stage.to_mapping(), tuple(stage.cases), object()):
            with self.subTest(value_type=type(invalid).__name__), self.assertRaisesRegex(
                PrivateEvaluationError, "dataset_schema_invalid"
            ):
                builder.build_evaluation_dataset(invalid)

    def test_builder_revalidates_pair_approval_and_rejects_namespace_reuse(self) -> None:
        builder = _load_builder(self)
        with self.assertRaisesRegex(
            PrivateEvaluationError, "pair_approval_insufficient"
        ):
            builder.build_evaluation_dataset(stage_value(pair_count=39))

        stage = stage_value()
        with patch(
            "backend.private_evaluation.dataset_builder.uuid.uuid4",
            return_value=uuid.UUID(stage.stage_namespace),
        ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_schema_invalid"):
            builder.build_evaluation_dataset(stage)

    def test_real_stage_to_final_round_trip_uses_distinct_crypto_and_keeps_stage(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        key = bytearray(b"B" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            stage_dir = root / "stage"
            final_dir = root / "final"
            stage_dir.mkdir()
            final_dir.mkdir()
            stage_path = stage_dir / "reviewed.pkevalstage"
            final_path = final_dir / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository_path.tempfile.gettempdir",
                return_value="C:/SyntheticPolicyTemp",
            ):
                write_encrypted_stage(stage_path, stage_value().cases, key)
                loaded_stage = read_encrypted_stage(stage_path, key)
                dataset = builder.build_evaluation_dataset(loaded_stage)
                write_new(final_path, dataset, key)
                loaded_dataset = read_encrypted_dataset(final_path, key)
                stage_preserved = stage_path.is_file()

            stage_frame = stage_path.read_bytes()
            final_frame = final_path.read_bytes()

        self.assertEqual(loaded_dataset, dataset)
        self.assertTrue(stage_frame.startswith(STAGE_MAGIC))
        self.assertTrue(final_frame.startswith(DATASET_MAGIC))
        self.assertNotEqual(STAGE_MAGIC, DATASET_MAGIC)
        self.assertNotEqual(STAGE_PURPOSE, DATASET_PURPOSE)
        self.assertNotEqual(stage_frame[9:25], final_frame[9:25])
        self.assertNotEqual(stage_frame[33:45], final_frame[33:45])
        self.assertTrue(stage_preserved)

    def test_final_dataset_rejects_the_staging_directory(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        key = bytearray(b"D" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            stage_path = root / "reviewed.pkevalstage"
            final_path = root / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository_path.tempfile.gettempdir",
                return_value="C:/SyntheticPolicyTemp",
            ):
                write_encrypted_stage(stage_path, stage_value().cases, key)
                dataset = builder.build_evaluation_dataset(
                    read_encrypted_stage(stage_path, key)
                )
                with self.assertRaisesRegex(
                    PrivateEvaluationError, "dataset_unavailable"
                ):
                    write_new(final_path, dataset, key)

            self.assertTrue(stage_path.is_file())
            self.assertFalse(final_path.exists())
            self.assertEqual(tuple(root.glob(".*.tmp")), ())

    def test_create_only_writer_rejects_existing_target_without_modifying_it(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"N" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            path.write_bytes(b"existing-synthetic-ciphertext")
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                write_new(path, dataset, key)
            self.assertEqual(path.read_bytes(), b"existing-synthetic-ciphertext")
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_create_only_writer_rejects_target_creation_race_and_leaves_no_partial(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"R" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"

            def create_racer(stage: str, _path: Path) -> None:
                if stage == "write_before_replace" and not path.exists():
                    path.write_bytes(b"racing-synthetic-file")

            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository._test_race_hook",
                side_effect=create_racer,
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                write_new(path, dataset, key)

            self.assertEqual(path.read_bytes(), b"racing-synthetic-file")
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_create_only_publication_never_clobbers_a_post_revalidation_racer(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"P" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            original_revalidate = repository_io._revalidate
            raced = False

            def race_after_revalidation(
                original, target, parent_before, target_before, validate,
            ) -> None:
                nonlocal raced
                original_revalidate(
                    original, target, parent_before, target_before, validate
                )
                if target_before is None and not raced:
                    raced = True
                    path.write_bytes(b"post-validation-racing-file")

            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository_io._revalidate",
                side_effect=race_after_revalidation,
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                write_new(path, dataset, key)

            self.assertEqual(path.read_bytes(), b"post-validation-racing-file")
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_create_only_commit_has_no_target_rollback_cleanup_window(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"F" * 32)
        real_unlink = Path.unlink
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            path = root / "dataset.pkeval"
            after_publication_hook_called = False
            target_cleanup_attempted = False

            def fail_after_publication(stage: str, _path: Path) -> None:
                nonlocal after_publication_hook_called
                if stage == "write_after_replace":
                    after_publication_hook_called = True
                    raise OSError("synthetic-post-publication-failure")

            def swap_competitor_at_target_unlink(
                candidate: Path, *args, **kwargs,
            ) -> None:
                nonlocal target_cleanup_attempted
                if candidate == path:
                    target_cleanup_attempted = True
                    real_unlink(candidate)
                    candidate.write_bytes(b"post-publication-competitor")
                real_unlink(candidate, *args, **kwargs)

            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository._test_race_hook",
                side_effect=fail_after_publication,
            ), patch.object(Path, "unlink", new=swap_competitor_at_target_unlink):
                write_new(path, dataset, key)
                loaded = read_encrypted_dataset(path, key)

            self.assertFalse(after_publication_hook_called)
            self.assertFalse(target_cleanup_attempted)
            self.assertEqual(loaded, dataset)
            self.assertEqual(tuple(root.glob(".*.tmp")), ())

    def test_create_only_link_success_cannot_be_misreported_by_wrapper_error(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"L" * 32)
        real_link = os.link

        def link_then_raise(source, destination, **kwargs) -> None:
            real_link(source, destination, **kwargs)
            raise OSError("synthetic-link-wrapper-failure")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository_io.os.link",
                side_effect=link_then_raise,
            ):
                write_new(path, dataset, key)
                loaded = read_encrypted_dataset(path, key)

            self.assertEqual(loaded, dataset)
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_create_only_link_success_survives_wrapper_keyboard_interrupt(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"I" * 32)
        real_link = os.link

        def link_then_interrupt(source, destination, **kwargs) -> None:
            real_link(source, destination, **kwargs)
            raise KeyboardInterrupt("synthetic-link-wrapper-interrupt")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository_io.os.link",
                side_effect=link_then_interrupt,
            ):
                try:
                    write_new(path, dataset, key)
                except KeyboardInterrupt:
                    self.fail("committed link was misreported as interrupted")
                loaded = read_encrypted_dataset(path, key)

            self.assertEqual(loaded, dataset)
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_create_only_success_survives_interrupt_after_publish_helper(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"H" * 32)
        real_publish = repository_io._publish_new
        helper_returned = False

        def publish_then_interrupt(stage, target, expected) -> None:
            nonlocal helper_returned
            real_publish(stage, target, expected)
            helper_returned = True
            raise KeyboardInterrupt("synthetic-post-helper-interrupt")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository_io._publish_new",
                side_effect=publish_then_interrupt,
            ):
                try:
                    write_new(path, dataset, key)
                except KeyboardInterrupt:
                    self.fail("committed write was interrupted after helper return")
                loaded = read_encrypted_dataset(path, key)

            self.assertTrue(helper_returned)
            self.assertEqual(loaded, dataset)
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())

    def test_create_only_temp_cleanup_failure_cannot_change_committed_success(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"T" * 32)
        real_unlink = Path.unlink
        cleanup_failed = False

        def unlink_stage_then_raise(candidate: Path, *args, **kwargs) -> None:
            nonlocal cleanup_failed
            if candidate.name.endswith(".tmp") and not cleanup_failed:
                cleanup_failed = True
                raise OSError("synthetic-temp-cleanup-wrapper-failure")
            real_unlink(candidate, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch.object(Path, "unlink", new=unlink_stage_then_raise):
                write_new(path, dataset, key)
                loaded = read_encrypted_dataset(path, key)

            self.assertTrue(cleanup_failed)
            self.assertEqual(loaded, dataset)
            remaining = tuple(path.parent.glob(".*.tmp"))
            self.assertEqual(len(remaining), 1)
            remaining[0].unlink()

    def test_create_only_temp_cleanup_interrupt_cannot_change_committed_success(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"K" * 32)
        real_unlink = Path.unlink
        cleanup_interrupted = False

        def unlink_stage_then_interrupt(candidate: Path, *args, **kwargs) -> None:
            nonlocal cleanup_interrupted
            if candidate.name.endswith(".tmp") and not cleanup_interrupted:
                cleanup_interrupted = True
                raise KeyboardInterrupt("synthetic-temp-cleanup-interrupt")
            real_unlink(candidate, *args, **kwargs)

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch.object(Path, "unlink", new=unlink_stage_then_interrupt):
                try:
                    write_new(path, dataset, key)
                except KeyboardInterrupt:
                    self.fail("committed write was interrupted by temp cleanup")
                loaded = read_encrypted_dataset(path, key)

            self.assertTrue(cleanup_interrupted)
            self.assertEqual(loaded, dataset)
            remaining = tuple(path.parent.glob(".*.tmp"))
            self.assertEqual(len(remaining), 1)
            remaining[0].unlink()

    def test_create_only_stage_close_failure_leaves_no_target_or_temp(self) -> None:
        builder = _load_builder(self)
        write_new = _load_new_writer(self)
        dataset = builder.build_evaluation_dataset(stage_value())
        key = bytearray(b"C" * 32)
        real_close = os.close

        def close_then_fail(descriptor: int) -> None:
            real_close(descriptor)
            raise OSError("synthetic-close-failure")

        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "dataset.pkeval"
            with patch(
                "backend.private_evaluation.repository._validate_external_dataset_path",
                return_value=path,
            ), patch(
                "backend.private_evaluation.repository_io.os.close",
                side_effect=close_then_fail,
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                write_new(path, dataset, key)

            self.assertFalse(path.exists())
            self.assertEqual(tuple(path.parent.glob(".*.tmp")), ())


if __name__ == "__main__":
    unittest.main()
