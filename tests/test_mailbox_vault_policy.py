"""Synthetic policy tests for the project-external mailbox vault."""

from __future__ import annotations

import importlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.mailbox_ingest.drive_policy import (
    FixedWindowsVolumeProbe,
    validate_vault_location,
)
from backend.mailbox_ingest.errors import VaultError
from backend.mailbox_ingest.models import VolumeInfo


class FakeVolumeProbe:
    def __init__(self, evidence: dict[str, VolumeInfo]) -> None:
        self.evidence = evidence
        self.paths: list[Path] = []

    def inspect(self, path: Path) -> VolumeInfo:
        resolved = path.resolve()
        self.paths.append(resolved)
        return self.evidence[str(resolved)]


def _volume(
    volume_id: str,
    *,
    filesystem: str = "NTFS",
    removable: bool = True,
    encrypted: bool = True,
    protection_on: bool = True,
    locked: bool = False,
    encryption_percentage: int = 100,
    reparse_point: bool = False,
) -> VolumeInfo:
    return VolumeInfo(
        stable_volume_id=volume_id,
        filesystem=filesystem,
        is_removable=removable,
        is_fully_encrypted=encrypted,
        protection_on=protection_on,
        is_locked=locked,
        encryption_percentage=encryption_percentage,
        is_reparse_point=reparse_point,
    )


class VaultLocationPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project"
        self.vault = self.root / "external" / "vault"
        self.recovery = self.root / "recovery" / "offline.key"
        self.system_temp = self.root / "system-temp"
        for path in (
            self.project,
            self.vault,
            self.recovery.parent,
            self.system_temp,
        ):
            path.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _probe(self, **vault_overrides: object) -> FakeVolumeProbe:
        return FakeVolumeProbe(
            {
                str(self.vault.resolve()): _volume("vault-volume", **vault_overrides),
                str(self.recovery.parent.resolve()): _volume(
                    "recovery-volume", removable=False
                ),
            }
        )

    def _validate(self, probe: FakeVolumeProbe | None = None):
        return validate_vault_location(
            self.vault,
            self.project,
            self.recovery,
            probe=probe or self._probe(),
            system_temp=self.system_temp,
        )

    def test_accepts_proven_external_ntfs_bitlocker_volume(self) -> None:
        evidence = self._validate()

        self.assertTrue(evidence.verified)
        self.assertNotIn(str(self.vault), repr(evidence))
        self.assertNotIn(str(self.recovery), repr(evidence))

    def test_rejects_relative_missing_and_forbidden_ancestry(self) -> None:
        cases = {
            "relative": Path("relative-vault"),
            "missing": self.root / "missing",
            "project": self.project / "nested-vault",
            "onedrive": self.root / "OneDrive" / "vault",
            "temp": self.system_temp / "vault",
        }
        (self.project / "nested-vault").mkdir()
        (self.root / "OneDrive" / "vault").mkdir(parents=True)
        (self.system_temp / "vault").mkdir()

        for label, vault in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(VaultError) as caught:
                    validate_vault_location(
                        vault,
                        self.project,
                        self.recovery,
                        probe=self._probe(),
                        system_temp=self.system_temp,
                    )
                self.assertNotIn(str(vault), str(caught.exception))
                self.assertNotIn(str(vault), repr(caught.exception))

    def test_rejects_reparse_non_ntfs_or_unproven_bitlocker(self) -> None:
        cases = (
            {"reparse_point": True},
            {"filesystem": "exFAT"},
            {"removable": False},
            {"encrypted": False},
            {"protection_on": False},
            {"locked": True},
            {"encryption_percentage": 99},
        )

        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(VaultError) as caught:
                    self._validate(self._probe(**overrides))
                self.assertRegex(caught.exception.code, r"^[a-z0-9_]+$")
                self.assertNotIn("vault-volume", repr(caught.exception))

    def test_rejects_recovery_material_on_same_volume(self) -> None:
        probe = FakeVolumeProbe(
            {
                str(self.vault.resolve()): _volume("same-volume"),
                str(self.recovery.parent.resolve()): _volume(
                    "same-volume", removable=False
                ),
            }
        )

        with self.assertRaisesRegex(VaultError, "recovery_volume_not_separate"):
            self._validate(probe)

    def test_probe_failure_is_sanitized(self) -> None:
        class ExplodingProbe:
            def inspect(self, path: Path) -> VolumeInfo:
                raise RuntimeError(f"native failure at {path}")

        with self.assertRaises(VaultError) as caught:
            self._validate(ExplodingProbe())

        self.assertEqual(caught.exception.code, "volume_probe_failed")
        self.assertNotIn("native failure", str(caught.exception))
        self.assertNotIn(str(self.vault), repr(caught.exception))

    def test_filesystem_probe_errors_do_not_leak_paths(self) -> None:
        with mock.patch.object(
            Path, "exists", side_effect=OSError(f"denied {self.vault}")
        ):
            with self.assertRaises(VaultError) as caught:
                self._validate()

        self.assertEqual(caught.exception.code, "invalid_path")
        self.assertNotIn(str(self.vault), repr(caught.exception))

    def test_windows_probe_uses_fixed_argv_without_shell(self) -> None:
        completed = mock.Mock(
            returncode=0,
            stdout=(
                '{"stable_volume_id":"fixed-id","filesystem":"NTFS",'
                '"is_removable":true,"is_fully_encrypted":true,'
                '"protection_on":true,"is_locked":false,'
                '"encryption_percentage":100,"is_reparse_point":false}'
            ),
            stderr="ignored native detail",
        )
        runner = mock.Mock(return_value=completed)
        probe = FixedWindowsVolumeProbe(runner=runner, platform="win32")

        result = probe.inspect(self.vault)

        self.assertEqual(result.stable_volume_id, "fixed-id")
        argv = runner.call_args.args[0]
        self.assertIsInstance(argv, list)
        self.assertEqual(argv[-1], str(self.vault))
        self.assertNotIn(str(self.vault), " ".join(argv[:-1]))
        self.assertFalse(runner.call_args.kwargs["shell"])

    def test_non_windows_probe_fails_with_fixed_code(self) -> None:
        probe = FixedWindowsVolumeProbe(platform="linux")

        with self.assertRaisesRegex(VaultError, "unsupported_platform"):
            probe.inspect(self.vault)

    def test_module_import_does_not_load_winapi_or_probe_host(self) -> None:
        module_name = "backend.mailbox_ingest.drive_policy"
        with mock.patch("subprocess.run") as run:
            imported = importlib.reload(sys.modules[module_name])

        self.assertIsNotNone(imported)
        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
