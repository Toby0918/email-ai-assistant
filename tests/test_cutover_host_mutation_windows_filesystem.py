"""Windows no-clobber effects in a caller-owned temporary NTFS sandbox."""

from __future__ import annotations

import sys
import tempfile
import threading
import unittest
import ctypes
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_host_mutation import FilesystemMutationKind
from backend.cutover_host_mutation.errors import CutoverHostMutationError
from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_directory_primitive,
    _create_test_file_publication_primitive,
    _create_test_move_primitive,
)
from backend.cutover_journal import DurabilityPlatform
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)
from tests.cutover_host_mutation_fixtures import durable_intent
from tests.windows_reparse_fixtures import create_test_junction


@unittest.skipUnless(sys.platform == "win32", "Windows integration only")
class CutoverHostMutationWindowsFilesystemTests(unittest.TestCase):
    def test_file_publication_is_handle_relative_no_replace_same_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            target_parent = root / "published"
            staging.mkdir()
            target_parent.mkdir()
            source = staging / "payload.bin"
            source.write_bytes(b"synthetic")
            target = target_parent / "payload.bin"
            primitive = _file_primitive(root, source, target)
            intent, permit, store = _intent(primitive)

            observation = primitive.publish_file(
                intent=intent,
                durable_permit=permit,
            )

            self.assertFalse(source.exists())
            self.assertEqual(target.read_bytes(), b"synthetic")
            self.assertIs(observation.kind, FilesystemMutationKind.PUBLISH_FILE)
            self.assertTrue(observation.same_identity)
            self.assertEqual(
                observation.source_identity_fingerprint,
                observation.target_identity_fingerprint,
            )
            self.assertTrue(observation.no_replace)
            self.assertNotIn(str(root), repr(observation))
            store.close()

    def test_file_publication_target_race_never_replaces_or_reselects(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            target_parent = root / "published"
            staging.mkdir()
            target_parent.mkdir()
            source = staging / "payload.bin"
            source.write_bytes(b"source")
            target = target_parent / "payload.bin"
            primitive = _file_primitive(root, source, target)
            target.write_bytes(b"preserve")
            intent, permit, store = _intent(primitive)

            with self.assertRaises(CutoverHostMutationError) as raised:
                primitive.publish_file(
                    intent=intent,
                    durable_permit=permit,
                )

            self.assertEqual(
                raised.exception.code,
                "filesystem_no_clobber_rejected",
            )
            self.assertEqual(source.read_bytes(), b"source")
            self.assertEqual(target.read_bytes(), b"preserve")
            self.assertEqual(
                sorted(item.name for item in target_parent.iterdir()),
                ["payload.bin"],
            )
            store.close()

    def test_target_appearance_after_durable_intent_is_no_clobber(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            staging = root / "staging"
            target_parent = root / "published"
            staging.mkdir()
            target_parent.mkdir()
            source = staging / "payload.bin"
            source.write_bytes(b"source")
            target = target_parent / "payload.bin"
            barrier = threading.Barrier(2)
            primitive = _file_primitive(
                root,
                source,
                target,
                target_race_barrier=barrier,
            )
            intent, permit, store = _intent(primitive)

            def publish_racing_target() -> None:
                barrier.wait(timeout=5)
                target.write_bytes(b"preserve")
                barrier.wait(timeout=5)

            racer = threading.Thread(target=publish_racing_target)
            racer.start()
            with self.assertRaises(CutoverHostMutationError) as raised:
                primitive.publish_file(
                    intent=intent,
                    durable_permit=permit,
                )
            racer.join(timeout=5)

            self.assertFalse(racer.is_alive())
            self.assertEqual(
                raised.exception.code,
                "filesystem_no_clobber_rejected",
            )
            self.assertEqual(source.read_bytes(), b"source")
            self.assertEqual(target.read_bytes(), b"preserve")
            store.close()

    def test_move_rejects_source_identity_drift_before_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_parent = root / "source"
            target_parent = root / "target"
            source_parent.mkdir()
            target_parent.mkdir()
            source = source_parent / "object"
            source.mkdir()
            target = target_parent / "object"
            primitive = _move_primitive(root, source, target)
            source.rename(source_parent / "retired")
            source.mkdir()
            intent, permit, store = _intent(primitive)
            handles_before = _process_handle_count()

            with self.assertRaises(CutoverHostMutationError) as raised:
                primitive.move_object(
                    intent=intent,
                    durable_permit=permit,
                )

            self.assertEqual(_process_handle_count(), handles_before)
            self.assertEqual(
                raised.exception.code,
                "filesystem_identity_changed",
            )
            self.assertTrue(source.is_dir())
            self.assertFalse(target.exists())
            target_parent.rename(root / "retired-target")
            store.close()

    def test_move_rejects_cross_volume_observation_before_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_parent = root / "source"
            target_parent = root / "target"
            source_parent.mkdir()
            target_parent.mkdir()
            source = source_parent / "object"
            source.mkdir()
            target = target_parent / "object"

            with self.assertRaises(CutoverHostMutationError) as raised:
                _move_primitive(
                    root,
                    source,
                    target,
                    source_volume_override=opaque_fingerprint(777),
                )

            self.assertEqual(
                raised.exception.code,
                "filesystem_volume_mismatch",
            )
            self.assertTrue(source.is_dir())
            self.assertFalse(target.exists())

    def test_create_only_directory_consumes_durable_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "parent"
            parent.mkdir()
            target = parent / "Container"
            primitive = _primitive(root, parent, target)
            intent, permit, store = _intent(primitive)

            observation = primitive.create_directory(
                intent=intent,
                durable_permit=permit,
            )

            self.assertTrue(target.is_dir())
            self.assertIs(
                observation.kind,
                FilesystemMutationKind.CREATE_DIRECTORY,
            )
            self.assertEqual(
                observation.journal_intent_fingerprint,
                intent.record_hash,
            )
            self.assertEqual(
                observation.journal_effect_fingerprint,
                intent.expected_after_observation_fingerprint,
            )
            self.assertFalse(observation.same_identity)
            self.assertTrue(observation.no_replace)
            self.assertNotIn(str(root), repr(observation))
            store.close()

    def test_create_only_directory_rejects_missing_and_replayed_permit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "parent"
            parent.mkdir()
            first = _primitive(root, parent, parent / "first")
            intent, permit, store = _intent(first)

            with self.assertRaises(CutoverHostMutationError) as missing:
                first.create_directory(intent=intent, durable_permit=None)
            self.assertEqual(
                missing.exception.code,
                "filesystem_journal_intent_required",
            )
            self.assertFalse((parent / "first").exists())

            first.create_directory(intent=intent, durable_permit=permit)
            second = _primitive(root, parent, parent / "second")
            with self.assertRaises(CutoverHostMutationError) as replayed:
                second.create_directory(
                    intent=intent,
                    durable_permit=permit,
                )
            self.assertEqual(
                replayed.exception.code,
                "filesystem_journal_intent_required",
            )
            self.assertFalse((parent / "second").exists())
            store.close()

    def test_existing_target_is_never_repaired_removed_or_reselected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "parent"
            target = parent / "Container"
            marker = target / "preserve.txt"
            target.mkdir(parents=True)
            marker.write_text("preserve", encoding="utf-8")
            primitive = _primitive(root, parent, target)
            intent, permit, store = _intent(primitive)

            with self.assertRaises(CutoverHostMutationError) as raised:
                primitive.create_directory(
                    intent=intent,
                    durable_permit=permit,
                )

            self.assertEqual(
                raised.exception.code,
                "filesystem_no_clobber_rejected",
            )
            self.assertEqual(marker.read_text(encoding="utf-8"), "preserve")
            self.assertEqual(
                sorted(item.name for item in parent.iterdir()),
                ["Container"],
            )
            store.close()

    def test_parent_identity_drift_blocks_before_effect(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "parent"
            parent.mkdir()
            target = parent / "Container"
            primitive = _primitive(root, parent, target)
            parent.rename(root / "retired-parent")
            parent.mkdir()
            intent, permit, store = _intent(primitive)
            handles_before = _process_handle_count()

            with self.assertRaises(CutoverHostMutationError) as raised:
                primitive.create_directory(
                    intent=intent,
                    durable_permit=permit,
                )

            self.assertEqual(_process_handle_count(), handles_before)
            self.assertEqual(
                raised.exception.code,
                "filesystem_identity_changed",
            )
            self.assertFalse(target.exists())
            parent.rename(root / "replacement-parent")
            store.close()

    def test_reparse_parent_inserted_after_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / "parent"
            alternate = root / "alternate"
            parent.mkdir()
            alternate.mkdir()
            target = parent / "Container"
            primitive = _primitive(root, parent, target)
            parent.rmdir()
            create_test_junction(parent, alternate)
            intent, permit, store = _intent(primitive)

            with self.assertRaises(CutoverHostMutationError) as raised:
                primitive.create_directory(
                    intent=intent,
                    durable_permit=permit,
                )

            self.assertEqual(
                raised.exception.code,
                "filesystem_reparse_rejected",
            )
            self.assertFalse((alternate / "Container").exists())
            store.close()


def _primitive(root: Path, parent: Path, target: Path):
    profile, authorization, marker = _scope(root)
    return _create_test_directory_primitive(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        parent=parent,
        target=target,
        observed_at_epoch=100,
    )


def _file_primitive(
    root: Path,
    source: Path,
    target: Path,
    *,
    target_race_barrier: object | None = None,
):
    profile, authorization, marker = _scope(root)
    return _create_test_file_publication_primitive(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        source=source,
        target_parent=target.parent,
        target=target,
        observed_at_epoch=100,
        _target_race_barrier=target_race_barrier,
    )


def _move_primitive(
    root: Path,
    source: Path,
    target: Path,
    *,
    source_volume_override: str | None = None,
):
    profile, authorization, marker = _scope(root)
    return _create_test_move_primitive(
        root=root,
        marker=marker,
        authorization=authorization,
        profile=profile,
        source=source,
        target_parent=target.parent,
        target=target,
        observed_at_epoch=100,
        _source_volume_override=source_volume_override,
    )


def _scope(root: Path):
    profile = CutoverProfileV1.create(valid_profile_body())
    authorization = TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=opaque_fingerprint(700),
        phase="execute",
        expires_at_epoch=200,
    )
    marker = root / ".codex-cutover-mutation-test-sandbox"
    marker.touch(exist_ok=True)
    return profile, authorization, marker


def _intent(primitive):
    expectation = primitive.expectation
    return durable_intent(
        before_fingerprint=expectation.before_fingerprint,
        expected_after_fingerprint=expectation.expected_after_fingerprint,
        platform=DurabilityPlatform.WINDOWS,
    )


def _process_handle_count() -> int:
    count = ctypes.c_ulong()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.argtypes = ()
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.GetProcessHandleCount.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
    )
    kernel.GetProcessHandleCount.restype = ctypes.c_int
    if not kernel.GetProcessHandleCount(
        kernel.GetCurrentProcess(),
        ctypes.byref(count),
    ):
        raise OSError(ctypes.get_last_error())
    return count.value


if __name__ == "__main__":
    unittest.main()
