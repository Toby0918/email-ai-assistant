"""Windows-only observations over a caller-owned temporary sandbox."""

from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.real_host_preflight.contracts import HostObjectKind
from backend.real_host_preflight.errors import RealHostPreflightError
from backend.real_host_preflight.windows_observation import (
    TestSandboxScopeV1,
    WindowsReadOnlyObserver,
)


@unittest.skipUnless(sys.platform == "win32", "Windows integration only")
class RealHostPreflightWindowsTests(unittest.TestCase):
    def test_scope_requires_exact_unexpired_test_authorization(self) -> None:
        class HostileAuthorization:
            @property
            def expires_at_epoch(self):
                raise AssertionError("duck attributes must not be read")

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(RealHostPreflightError) as wrong_type:
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=HostileAuthorization(),
                    observed_at_epoch=100,
                )
            self.assertEqual(
                wrong_type.exception.code,
                "sandbox_authorization_invalid",
            )

            with self.assertRaises(RealHostPreflightError) as expired:
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=200,
                )
            self.assertEqual(
                expired.exception.code,
                "sandbox_authorization_expired",
            )

    def test_file_identity_is_stable_across_read_only_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "stable.txt"
            target.touch()
            scope = TestSandboxScopeV1.create(
                root=root,
                authorization=_authorization(),
                observed_at_epoch=100,
            )
            observer = WindowsReadOnlyObserver(scope)

            first = observer.observe_existing(
                target,
                expected_kind=HostObjectKind.FILE,
            )
            second = observer.observe_existing(
                target,
                expected_kind=HostObjectKind.FILE,
            )

            self.assertEqual(first.file_id_128, second.file_id_128)
            self.assertEqual(
                first.object_identity_fingerprint,
                second.object_identity_fingerprint,
            )
            self.assertEqual(first.filesystem_name, "NTFS")
            self.assertFalse(first.has_reparse_point)
            self.assertNotIn(str(root), repr(first))

    def test_volume_observation_requires_local_fixed_ntfs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )

            volume = observer.observe_volume(root)

            self.assertEqual(volume.filesystem_name, "NTFS")
            self.assertEqual(volume.drive_type, "fixed")
            self.assertTrue(volume.complete)
            self.assertNotIn(str(root), repr(volume))

    def test_leaf_absence_fails_closed_after_target_appears(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "future.txt"
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )

            missing = observer.observe_absent(target)

            self.assertFalse(missing.present)
            self.assertEqual(missing.filesystem_name, "NTFS")
            self.assertNotIn(str(root), repr(missing))
            target.touch()
            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_absent(target)
            self.assertEqual(raised.exception.code, "host_object_already_present")

    def test_reparse_inserted_after_scope_creation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / "destination"
            destination.mkdir()
            (destination / "inside.txt").touch()
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )
            junction = root / "inserted"
            _create_junction(junction, destination)

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    junction / "inside.txt",
                    expected_kind=HostObjectKind.FILE,
                )

            self.assertEqual(
                raised.exception.code,
                "host_object_reparse_forbidden",
            )

    def test_existing_object_outside_scope_is_rejected_before_observation(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            tempfile.TemporaryDirectory() as outside_temporary,
        ):
            root = Path(temporary)
            outside = Path(outside_temporary) / "outside.txt"
            outside.touch()
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    outside,
                    expected_kind=HostObjectKind.FILE,
                )

            self.assertEqual(raised.exception.code, "host_object_outside_scope")

    def test_reserved_device_alias_is_rejected_before_observation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    root / "CON.txt",
                    expected_kind=HostObjectKind.FILE,
                )

            self.assertEqual(raised.exception.code, "host_scope_invalid")

    def test_expected_volume_mismatch_fails_closed_in_the_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "volume-bound.txt"
            target.touch()
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    target,
                    expected_kind=HostObjectKind.FILE,
                    expected_volume_fingerprint="f" * 64,
                )

            self.assertEqual(
                raised.exception.code,
                "host_volume_mismatch",
            )

    def test_native_failure_is_content_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing = root / "customer-secret-missing.txt"
            observer = WindowsReadOnlyObserver(
                TestSandboxScopeV1.create(
                    root=root,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            )

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    missing,
                    expected_kind=HostObjectKind.FILE,
                )

            rendered = f"{raised.exception!s} {raised.exception!r}"
            self.assertEqual(raised.exception.code, "host_object_unavailable")
            self.assertNotIn(str(root), rendered)
            self.assertNotIn(missing.name, rendered)
            self.assertNotIn("WinError", rendered)
            self.assertTrue(raised.exception.__suppress_context__)
            self.assertIsNone(raised.exception.__cause__)


def _authorization() -> TestSandboxAuthorizationV1:
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint="1" * 64,
        operation_fingerprint="2" * 64,
        phase="current_topology_preflight",
        expires_at_epoch=200,
    )


def _create_junction(link: Path, destination: Path) -> None:
    completed = subprocess.run(
        [
            "cmd.exe",
            "/d",
            "/c",
            "mklink",
            "/J",
            str(link),
            str(destination),
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError("temporary junction creation failed")


if __name__ == "__main__":
    unittest.main()
