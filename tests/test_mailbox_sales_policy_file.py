from __future__ import annotations

import os
import stat
import tempfile
import types
import unittest
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from backend.mailbox_ingest import sales_policy_file
from backend.project_layout import RepositoryPlacement, StandaloneStateKind


@dataclass(frozen=True)
class _Layout:
    root: Path
    project: Path
    external: Path
    system_temp: Path

    @property
    def policy(self) -> Path:
        return self.external / "policy.json"


@contextmanager
def _layout() -> Iterator[_Layout]:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        layout = _Layout(
            root,
            root / "project",
            root / "external",
            root / "synthetic-system-temp",
        )
        for directory in (layout.project, layout.external, layout.system_temp):
            directory.mkdir()
        yield layout


def _identity(payload: object) -> object:
    return payload


def _read(
    layout: _Layout,
    *,
    path: Path | None = None,
    parser: object = _identity,
    system_temp: Path | None = None,
) -> object:
    with mock.patch.object(
        sales_policy_file,
        "_system_temp_root",
        return_value=system_temp or layout.system_temp,
    ):
        return sales_policy_file.read_sales_policy(
            path or layout.policy,
            project_root=layout.project,
            parser=parser,  # type: ignore[arg-type]
        )


class SalesPolicyFileTests(unittest.TestCase):
    def _assert_invalid_payload(self, payload: bytes) -> None:
        with _layout() as layout:
            layout.policy.write_bytes(payload)
            parser = mock.Mock(return_value=object())
            with self.assertRaises(sales_policy_file.SalesPolicyFileError) as caught:
                _read(layout, parser=parser)
            self.assertEqual(caught.exception.code, "sales_policy_invalid")
            parser.assert_not_called()

    def test_reads_strict_json_through_injected_policy_parser(self) -> None:
        with _layout() as layout:
            layout.policy.write_text(
                '{"schema_version":"SyntheticPolicyV1"}', encoding="utf-8"
            )
            parsed_payloads: list[object] = []
            expected = object()

            def parser(payload: object) -> object:
                parsed_payloads.append(payload)
                return expected

            self.assertIs(_read(layout, parser=parser), expected)
            self.assertEqual(
                parsed_payloads, [{"schema_version": "SyntheticPolicyV1"}]
            )

    def test_uses_the_strict_default_policy_parser(self) -> None:
        with _layout() as layout:
            layout.policy.write_text(
                (
                    '{"schema_version":1,'
                    '"company_domain":"seller.example.test",'
                    '"salesperson_allowlist":["agent@seller.example.test"]}'
                ),
                encoding="utf-8",
            )
            with (
                mock.patch.object(
                    sales_policy_file,
                    "_system_temp_root",
                    return_value=layout.system_temp,
                ),
            ):
                actual = sales_policy_file.read_sales_policy(
                    layout.policy, project_root=layout.project
                )
            self.assertEqual(repr(actual), "SalesCorpusPolicy(<redacted>)")

    def test_all_failures_use_one_fixed_redacted_error(self) -> None:
        canary = "customer-policy-secret.json"
        with self.assertRaises(sales_policy_file.SalesPolicyFileError) as caught:
            sales_policy_file.read_sales_policy(
                Path(canary), project_root=Path.cwd()
            )
        error = caught.exception
        self.assertEqual(error.code, "sales_policy_invalid")
        self.assertEqual(str(error), "sales_policy_invalid")
        self.assertEqual(
            repr(error), "SalesPolicyFileError(code='sales_policy_invalid')"
        )
        self.assertNotIn(canary, str(error) + repr(error))

        with _layout() as layout:
            layout.policy.write_text("{}", encoding="utf-8")

            def leaking_parser(_payload: object) -> object:
                raise RuntimeError(f"parser leaked {canary}")

            with self.assertRaises(sales_policy_file.SalesPolicyFileError) as parsed:
                _read(layout, parser=leaking_parser)
            self.assertNotIn(canary, str(parsed.exception) + repr(parsed.exception))

    def test_rejects_project_temp_and_onedrive_locations(self) -> None:
        with _layout() as layout:
            onedrive = layout.root / "OneDrive - Synthetic"
            onedrive.mkdir()
            cases = (
                (layout.project / "policy.json", layout.system_temp),
                (layout.system_temp / "policy.json", layout.system_temp),
                (onedrive / "policy.json", layout.system_temp),
            )
            for policy, system_temp in cases:
                policy.write_text("{}", encoding="utf-8")
                with self.subTest(parent=policy.parent.name):
                    with self.assertRaises(sales_policy_file.SalesPolicyFileError):
                        _read(layout, path=policy, system_temp=system_temp)

    def test_rejects_every_project_container_zone_and_allows_external_file(
        self,
    ) -> None:
        with _layout() as layout:
            container = layout.root / "managed" / "email_ai_assistant"
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
            with mock.patch.object(
                sales_policy_file,
                "_system_temp_root",
                return_value=layout.system_temp,
            ):
                for zone in zones:
                    policy = zone / "nested" / "sales-policy.json"
                    policy.parent.mkdir(parents=True, exist_ok=True)
                    policy.write_text("{}", encoding="utf-8")
                    with self.subTest(zone=zone), self.assertRaises(
                        sales_policy_file.SalesPolicyFileError
                    ):
                        sales_policy_file.read_sales_policy(
                            policy,
                            project_root=repository,
                            parser=_identity,
                        )

                layout.policy.write_text("{}", encoding="utf-8")
                self.assertEqual(
                    sales_policy_file.read_sales_policy(
                        layout.policy,
                        project_root=repository,
                        parser=_identity,
                    ),
                    {},
                )

    def test_explicit_standalone_state_root_is_not_external_policy_storage(
        self,
    ) -> None:
        with _layout() as layout:
            repository = layout.root / "portable-repository"
            state = layout.root / "standalone-state"
            repository.mkdir()
            state.mkdir()
            placement = RepositoryPlacement.standalone(
                repository_root=repository,
                state_root=state,
                state_kind=StandaloneStateKind.SYNTHETIC,
            )
            state_policy = state / "sales-policy.json"
            state_policy.write_text("{}", encoding="utf-8")
            layout.policy.write_text("{}", encoding="utf-8")

            with mock.patch.object(
                sales_policy_file,
                "_system_temp_root",
                return_value=layout.system_temp,
            ):
                with self.assertRaises(
                    sales_policy_file.SalesPolicyFileError
                ):
                    sales_policy_file.read_sales_policy(
                        state_policy,
                        project_root=placement,
                        parser=_identity,
                    )
                self.assertEqual(
                    sales_policy_file.read_sales_policy(
                        layout.policy,
                        project_root=placement,
                        parser=_identity,
                    ),
                    {},
                )

    def test_rejects_non_strict_or_oversized_json_before_parser(self) -> None:
        invalid_payloads = (
            b'{"duplicate":1,"duplicate":2}',
            b'{"not_a_number":NaN}',
            b'{"infinite":Infinity}',
            b'{"secret":"CANARY",}',
            b'\xff',
            b'{}' + (b' ' * (64 * 1024 - 1)),
        )
        for payload in invalid_payloads:
            with self.subTest(payload_size=len(payload)):
                self._assert_invalid_payload(payload)

    def test_accepts_valid_json_at_the_exact_64_kib_boundary(self) -> None:
        with _layout() as layout:
            layout.policy.write_bytes(b'{}' + (b' ' * (64 * 1024 - 2)))
            self.assertEqual(_read(layout), {})

    def test_rejects_directory_target(self) -> None:
        with _layout() as layout:
            with self.assertRaises(sales_policy_file.SalesPolicyFileError):
                _read(layout, path=layout.external)

    def test_rejects_size_and_identity_changes_before_open(self) -> None:
        with _layout() as layout:
            for kind in ("size", "identity"):
                layout.policy.write_text("{}", encoding="utf-8")
                displaced = layout.external / f"displaced-{kind}.json"

                def race(stage: str, target: Path) -> None:
                    if stage != "read_before_open":
                        return
                    if kind == "size":
                        target.write_text('{"changed":true}', encoding="utf-8")
                    else:
                        target.replace(displaced)
                        target.write_text("{}", encoding="utf-8")

                with self.subTest(race=kind), mock.patch.object(
                    sales_policy_file, "_test_race_hook", new=race
                ):
                    with self.assertRaises(sales_policy_file.SalesPolicyFileError):
                        _read(layout)

    def test_rejects_symlink_mode_and_windows_reparse_attribute(self) -> None:
        with _layout() as layout:
            layout.policy.write_text("{}", encoding="utf-8")
            real_lstat = os.lstat
            cases = (
                ("symlink", stat.S_IFLNK | 0o777, 0),
                ("reparse", None, 0x400),
            )
            for label, forced_mode, attributes in cases:
                def reparse_lstat(path: object) -> object:
                    metadata = real_lstat(path)
                    if Path(path) != layout.policy:
                        return metadata
                    return types.SimpleNamespace(
                        st_mode=forced_mode or metadata.st_mode,
                        st_file_attributes=attributes,
                        st_dev=metadata.st_dev,
                        st_ino=metadata.st_ino,
                        st_size=metadata.st_size,
                        st_mtime_ns=metadata.st_mtime_ns,
                    )

                with self.subTest(reparse=label), mock.patch.object(
                    sales_policy_file.os, "lstat", side_effect=reparse_lstat
                ):
                    with self.assertRaises(sales_policy_file.SalesPolicyFileError):
                        _read(layout)

    def test_rejects_size_change_after_descriptor_read(self) -> None:
        with _layout() as layout:
            layout.policy.write_text("{}", encoding="utf-8")
            mutation_completed = False

            def race(stage: str, target: Path) -> None:
                nonlocal mutation_completed
                if stage == "read_after_open":
                    target.write_text('{"changed":true}', encoding="utf-8")
                    mutation_completed = True

            with mock.patch.object(
                sales_policy_file, "_test_race_hook", new=race
            ):
                with self.assertRaises(sales_policy_file.SalesPolicyFileError):
                    _read(layout)
            self.assertTrue(mutation_completed)

    def test_revalidates_original_alias_after_descriptor_read(self) -> None:
        with _layout() as layout:
            layout.policy.write_text("{}", encoding="utf-8")
            alternate = layout.external / "alternate.json"
            alternate.write_text("{}", encoding="utf-8")
            real_validate = sales_policy_file._validate_read_path
            validation_count = 0

            def drifting_alias(path: Path) -> Path:
                nonlocal validation_count
                validation_count += 1
                target = real_validate(path)
                return alternate.resolve(strict=True) if validation_count > 1 else target

            with mock.patch.object(
                sales_policy_file,
                "_validate_read_path",
                side_effect=drifting_alias,
            ):
                with self.assertRaises(sales_policy_file.SalesPolicyFileError):
                    _read(layout)
            self.assertGreaterEqual(validation_count, 2)


if __name__ == "__main__":
    unittest.main()
