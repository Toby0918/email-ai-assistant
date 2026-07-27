"""Windows-only observations over a caller-owned temporary sandbox."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.cutover_contracts import TestSandboxAuthorizationV1
from backend.real_host_preflight.contracts import HostObjectKind
from backend.real_host_preflight.errors import RealHostPreflightError
from backend.real_host_preflight.windows_observation import (
    TestSandboxScopeV1,
    WindowsReadOnlyObserver,
    _issue_test_sandbox_permit,
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
            marker = _create_marker(root)
            with self.assertRaises(RealHostPreflightError) as wrong_type:
                _issue_test_sandbox_permit(
                    root=root,
                    marker=marker,
                    authorization=HostileAuthorization(),
                    observed_at_epoch=100,
                )
            self.assertEqual(
                wrong_type.exception.code,
                "sandbox_authorization_invalid",
            )

            with self.assertRaises(RealHostPreflightError) as expired:
                _issue_test_sandbox_permit(
                    root=root,
                    marker=marker,
                    authorization=_authorization(),
                    observed_at_epoch=200,
                )
            self.assertEqual(
                expired.exception.code,
                "sandbox_authorization_expired",
            )

            with self.assertRaises(RealHostPreflightError) as wrong_phase:
                _issue_test_sandbox_permit(
                    root=root,
                    marker=marker,
                    authorization=_authorization(phase="execute"),
                    observed_at_epoch=100,
                )
            self.assertEqual(
                wrong_phase.exception.code,
                "sandbox_authorization_invalid",
            )

    def test_scope_requires_present_marker_and_single_use_permit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            missing_marker = root / ".codex-preflight-test-sandbox"
            with self.assertRaises(RealHostPreflightError) as missing:
                _issue_test_sandbox_permit(
                    root=root,
                    marker=missing_marker,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
            self.assertEqual(missing.exception.code, "host_scope_invalid")

            permit = _permit(root)
            TestSandboxScopeV1.create(permit=permit)
            with self.assertRaises(RealHostPreflightError) as replay:
                TestSandboxScopeV1.create(permit=permit)
            self.assertEqual(replay.exception.code, "host_scope_invalid")

    def test_permit_is_bound_to_marker_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = _create_marker(root)
            permit = _issue_test_sandbox_permit(
                root=root,
                marker=marker,
                authorization=_authorization(),
                observed_at_epoch=100,
            )
            marker.rename(root / "retired-test-sandbox-marker")
            marker.touch()

            with self.assertRaises(RealHostPreflightError) as raised:
                TestSandboxScopeV1.create(permit=permit)

            self.assertEqual(
                raised.exception.code,
                "host_object_identity_changed",
            )

    def test_observer_revalidates_marker_lease_on_every_operation(self) -> None:
        operations = (
            (
                "existing",
                lambda observer, root: observer.observe_existing(
                    root / "lease-target.txt",
                    expected_kind=HostObjectKind.FILE,
                ),
            ),
            (
                "volume",
                lambda observer, root: observer.observe_volume(root),
            ),
            (
                "absent",
                lambda observer, root: observer.observe_absent(
                    root / "future-target.txt"
                ),
            ),
        )
        for replacement, (operation_name, operation) in (
            (replacement, operation)
            for replacement in (False, True)
            for operation in operations
        ):
            with (
                self.subTest(
                    replacement=replacement,
                    operation=operation_name,
                ),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                marker = _create_marker(root)
                target = root / "lease-target.txt"
                target.touch()
                permit = _issue_test_sandbox_permit(
                    root=root,
                    marker=marker,
                    authorization=_authorization(),
                    observed_at_epoch=100,
                )
                observer = WindowsReadOnlyObserver(
                    TestSandboxScopeV1.create(permit=permit)
                )
                marker.rename(root / "retired-marker")
                if replacement:
                    marker.touch()

                with self.assertRaises(RealHostPreflightError) as raised:
                    operation(observer, root)

                self.assertEqual(
                    raised.exception.code,
                    "host_object_identity_changed",
                )

    def test_file_identity_is_stable_across_read_only_reopens(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "stable.txt"
            target.touch()
            scope = _scope(root)
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
            observer = WindowsReadOnlyObserver(_scope(root))

            volume = observer.observe_volume(root)

            self.assertEqual(volume.filesystem_name, "NTFS")
            self.assertEqual(volume.drive_type, "fixed")
            self.assertTrue(volume.complete)
            self.assertNotIn(str(root), repr(volume))

    def test_leaf_absence_fails_closed_after_target_appears(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "future.txt"
            observer = WindowsReadOnlyObserver(_scope(root))

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
            observer = WindowsReadOnlyObserver(_scope(root))
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
            observer = WindowsReadOnlyObserver(_scope(root))

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    outside,
                    expected_kind=HostObjectKind.FILE,
                )

            self.assertEqual(raised.exception.code, "host_object_outside_scope")

    def test_outside_hard_link_alias_inside_scope_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temporary,
            tempfile.TemporaryDirectory() as outside_temporary,
        ):
            root = Path(temporary)
            outside = Path(outside_temporary) / "outside.txt"
            inside_alias = root / "inside-alias.txt"
            outside.touch()
            os.link(outside, inside_alias)
            observer = WindowsReadOnlyObserver(_scope(root))

            with self.assertRaises(RealHostPreflightError) as raised:
                observer.observe_existing(
                    inside_alias,
                    expected_kind=HostObjectKind.FILE,
                )

            self.assertEqual(
                raised.exception.code,
                "host_object_alias_forbidden",
            )

    def test_scope_and_observer_bindings_cannot_be_reassigned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scope = _scope(root)
            observer = WindowsReadOnlyObserver(scope)

            with self.assertRaises(Exception):
                object.__setattr__(scope, "_root", root / "other")
            with self.assertRaises(Exception):
                object.__setattr__(observer, "_scope", object())

    def test_reserved_device_aliases_are_rejected_before_observation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            observer = WindowsReadOnlyObserver(_scope(root))

            for alias in (
                "CON.txt",
                "CONIN$",
                "CONOUT$.log",
                "COM0",
                "LPT0",
                "COM¹",
                "LPT³.txt",
            ):
                with self.subTest(alias=alias):
                    with self.assertRaises(RealHostPreflightError) as raised:
                        observer.observe_existing(
                            root / alias,
                            expected_kind=HostObjectKind.FILE,
                        )
                    self.assertEqual(
                        raised.exception.code,
                        "host_scope_invalid",
                    )

    def test_expected_volume_mismatch_fails_closed_in_the_sandbox(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "volume-bound.txt"
            target.touch()
            observer = WindowsReadOnlyObserver(_scope(root))

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
            observer = WindowsReadOnlyObserver(_scope(root))

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


def _authorization(
    *,
    phase: str = "current_topology_preflight",
) -> TestSandboxAuthorizationV1:
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint="1" * 64,
        operation_fingerprint="2" * 64,
        phase=phase,
        expires_at_epoch=200,
    )


def _create_marker(root: Path) -> Path:
    marker = root / ".codex-preflight-test-sandbox"
    marker.touch()
    return marker


def _permit(root: Path):
    return _issue_test_sandbox_permit(
        root=root,
        marker=_create_marker(root),
        authorization=_authorization(),
        observed_at_epoch=100,
    )


def _scope(root: Path) -> TestSandboxScopeV1:
    return TestSandboxScopeV1.create(permit=_permit(root))


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
