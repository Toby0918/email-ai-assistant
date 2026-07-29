from __future__ import annotations

import contextlib
import ctypes
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.cutover_managed_activation import (
    ArtifactPublisher,
    ConfigPublisher,
    LockedRuntimeBuilder,
    ManagedActivationError,
    ManagedConfigV1,
    StoppedDatabaseCopier,
    StoppedServiceReceiptV1,
)
from backend.cutover_managed_activation.synthetic_scope import (
    _bind_test_sandbox_activation,
    _review_test_sandbox_activation,
)
from backend.cutover_managed_activation.windows_file_handles import (
    WindowsReadHandleApi,
)
from backend.cutover_managed_activation.windows_publication_io import (
    WindowsCreateOnlyApi,
)
from backend.cutover_managed_activation.publication_scope import (
    PublicationScopeWindow,
)
from backend.cutover_managed_activation import runtime_builder as runtime_module
from tests.windows_reparse_fixtures import create_test_junction
from tests.cutover_managed_activation_fixtures import (
    EXPECTED_MASTER,
    OBSERVED_AT,
    authorization_for,
    build_runtime_scenario,
    profile_for_review,
    wheel_bytes_with_extra_member,
)

_INVALID_HANDLE = ctypes.c_void_p(-1).value


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
class ManagedActivationWindowsEdgeTests(unittest.TestCase):
    def test_scope_rejects_python_source_outside_owned_sandbox(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scenario.python_source = Path(sys._base_executable).resolve(
            strict=True
        )

        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_scope_invalid$"
        ):
            _review_test_sandbox_activation(scenario)

    def test_scope_rejects_ads_target_without_modifying_base_file(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        base = scenario.config_target.parent / "existing.json"
        base.write_bytes(b"preserve")
        scenario.config_target = base.with_name(base.name + ":newstream")

        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_scope_invalid$"
        ):
            _review_test_sandbox_activation(scenario)

        self.assertEqual(base.read_bytes(), b"preserve")
        self.assertFalse(scenario.config_target.exists())

    def test_scope_rejects_superscript_reserved_device_targets(self) -> None:
        for name in ("COM¹.json", "COM²", "COM³.cfg", "LPT¹", "LPT².x", "LPT³"):
            with self.subTest(name=name):
                scenario = build_runtime_scenario()
                try:
                    scenario.config_target = (
                        scenario.config_target.parent / name
                    )
                    with self.assertRaisesRegex(
                        ManagedActivationError,
                        "^managed_activation_scope_invalid$",
                    ):
                        _review_test_sandbox_activation(scenario)
                    self.assertFalse(scenario.config_target.exists())
                finally:
                    scenario.close()

    def test_created_file_handle_denies_concurrent_writer(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        window = PublicationScopeWindow.open(scope=scope, role="config")
        window.create_target()
        try:
            with self.assertRaises(PermissionError):
                scenario.config_target.open("r+b")
        finally:
            window.close(active_error=False)

    def test_bound_scope_snapshots_targets_and_rejects_parent_replacement(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        reviewed_target = scope.review.scenario.config_target
        self.assertIsNot(scope.review.scenario, scenario)

        outside_owner = tempfile.TemporaryDirectory(
            prefix="issue57-outside-"
        )
        self.addCleanup(outside_owner.cleanup)
        scenario.config_target = Path(outside_owner.name) / "retarget.json"
        ConfigPublisher.publish(
            scope=scope,
            config=ManagedConfigV1.from_mapping(scenario.config_values),
        )
        self.assertTrue(reviewed_target.exists())
        self.assertFalse(scenario.config_target.exists())

        replaced = build_runtime_scenario()
        self.addCleanup(replaced.close)
        replaced_scope = self._scope(replaced)
        parent = replaced_scope.review.scenario.config_target.parent
        retained_parent = replaced.root / "retained-config-parent"
        parent.rename(retained_parent)
        parent.mkdir()
        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_scope_drift$"
        ):
            ConfigPublisher.publish(
                scope=replaced_scope,
                config=ManagedConfigV1.from_mapping(
                    replaced.config_values
                ),
            )
        self.assertFalse(
            replaced_scope.review.scenario.config_target.exists()
        )
        self.assertFalse(
            (retained_parent / replaced.config_target.name).exists()
        )

    def test_runtime_rejects_source_replacement_and_wrong_versions(self) -> None:
        replaced = build_runtime_scenario()
        self.addCleanup(replaced.close)
        replaced_scope = self._scope(replaced)
        source_copy = replaced.python_source.with_name("replacement.exe")
        shutil.copyfile(replaced.python_source, source_copy)
        with source_copy.open("ab") as output:
            output.write(b"replacement")
        source_copy.replace(replaced.python_source)

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_python_source_invalid$"
        ):
            LockedRuntimeBuilder.publish(scope=replaced_scope)
        self.assertFalse(replaced.runtime_target.exists())

        wrong = build_runtime_scenario()
        self.addCleanup(wrong.close)
        wrong_scope = self._scope(wrong)
        manifest = json.loads(
            wrong.python_source_manifest.read_text("ascii")
        )
        manifest["python_version"] = "3.12.12"
        wrong.python_source_manifest.write_text(
            json.dumps(
                manifest,
                ensure_ascii=True,
                allow_nan=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "ascii",
        )
        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_python_source_invalid$"
        ):
            LockedRuntimeBuilder.publish(scope=wrong_scope)
        self.assertFalse(wrong.runtime_target.exists())

    def test_runtime_installs_captured_wheel_bytes_not_raced_path(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        wheel = next(scenario.wheelhouse.iterdir())
        original_bytes = wheel.read_bytes()
        raced_bytes = wheel_bytes_with_extra_member(
            wheel,
            "unreviewed_payload.py",
            b"RACED = True\n",
        )
        original_install = runtime_module._install_locked_wheels

        def race_install(*args, **kwargs):
            wheel.write_bytes(raced_bytes)
            try:
                return original_install(*args, **kwargs)
            finally:
                wheel.write_bytes(original_bytes)

        with mock.patch.object(
            runtime_module,
            "_install_locked_wheels",
            side_effect=race_install,
        ):
            LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(
            (
                scenario.runtime_target
                / "Lib"
                / "site-packages"
                / "unreviewed_payload.py"
            ).exists()
        )

    def test_runtime_rejects_unreviewed_child_added_after_install(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        original_install = runtime_module._install_locked_wheels

        def inject_extra(captured, tree):
            original_install(captured, tree)
            extra = (
                scenario.runtime_target
                / "Lib"
                / "site-packages"
                / "unreviewed_child.py"
            )
            extra.write_bytes(b"UNREVIEWED = True\n")

        with mock.patch.object(
            runtime_module,
            "_install_locked_wheels",
            side_effect=inject_extra,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_invalid$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertTrue(
            (
                scenario.runtime_target
                / "Lib"
                / "site-packages"
                / "unreviewed_child.py"
            ).exists()
        )

    def test_runtime_rejects_transient_child_without_executing_it(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        marker = scenario.root / "transient-execution-marker"
        original_verify = runtime_module.verify_with_new_runtime

        def inject_transient(target, review):
            transient = target / "Lib" / "site-packages" / "hashlib.py"
            transient.write_bytes(
                b"from pathlib import Path\n"
                + f"Path({str(marker)!r}).write_bytes(b'executed')\n".encode(
                    "utf-8"
                )
                + b"from _hashlib import openssl_sha256 as sha256\n"
            )
            try:
                return original_verify(target, review)
            finally:
                transient.unlink()

        with mock.patch.object(
            runtime_module,
            "verify_with_new_runtime",
            side_effect=inject_transient,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(marker.exists())
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_never_imports_transient_hashlib_package(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        marker = scenario.root / "hashlib-package-execution-marker"
        original_verify = runtime_module.verify_with_new_runtime

        def inject_transient(target, review):
            package = target / "Lib" / "hashlib"
            package.mkdir()
            startup = package / "__init__.py"
            startup.write_text(
                f"open({str(marker)!r},'wb').write(b'executed')\n",
                "utf-8",
            )
            try:
                return original_verify(target, review)
            finally:
                startup.unlink()
                package.rmdir()

        with mock.patch.object(
            runtime_module,
            "verify_with_new_runtime",
            side_effect=inject_transient,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(marker.exists())
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_startup_never_imports_transient_encoding_package(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        marker = scenario.root / "encoding-package-execution-marker"
        original_verify = runtime_module.verify_with_new_runtime

        def inject_transient(target, review):
            package = target / "Lib" / "encodings" / "aliases"
            package.mkdir()
            startup = package / "__init__.py"
            startup.write_text(
                f"open({str(marker)!r},'wb').write(b'executed')\n",
                "utf-8",
            )
            try:
                return original_verify(target, review)
            finally:
                startup.unlink()
                package.rmdir()

        with mock.patch.object(
            runtime_module,
            "verify_with_new_runtime",
            side_effect=inject_transient,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(marker.exists())
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_startup_never_imports_transient_codecs_package(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        marker = scenario.root / "codecs-package-execution-marker"
        original_verify = runtime_module.verify_with_new_runtime

        def inject_transient(target, review):
            package = target / "Lib" / "codecs"
            package.mkdir()
            startup = package / "__init__.py"
            startup.write_text(
                f"open({str(marker)!r},'wb').write(b'executed')\n",
                "utf-8",
            )
            try:
                return original_verify(target, review)
            finally:
                startup.unlink()
                package.rmdir()

        with mock.patch.object(
            runtime_module,
            "verify_with_new_runtime",
            side_effect=inject_transient,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(marker.exists())
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_rejects_persistent_root_alternate_data_stream(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        original_publish = runtime_module._publish_source_runtime

        def inject_stream(source, tree):
            original_publish(source, tree)
            Path(str(scenario.runtime_target) + ":unreviewed").write_bytes(
                b"stream"
            )

        with mock.patch.object(
            runtime_module,
            "_publish_source_runtime",
            side_effect=inject_stream,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_invalid$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertTrue(
            Path(str(scenario.runtime_target) + ":unreviewed").exists()
        )

    def test_runtime_rejects_transient_root_alternate_data_stream(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        original_verify = runtime_module.verify_with_new_runtime

        def inject_stream(target, review):
            stream = Path(str(target) + ":unreviewed")
            stream.write_bytes(b"stream")
            try:
                return original_verify(target, review)
            finally:
                stream.unlink()

        with mock.patch.object(
            runtime_module,
            "verify_with_new_runtime",
            side_effect=inject_stream,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_rejects_post_source_site_packages_junction(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        outside_owner = tempfile.TemporaryDirectory(
            prefix="issue57-runtime-outside-"
        )
        self.addCleanup(outside_owner.cleanup)
        outside = Path(outside_owner.name)
        original_publish = runtime_module._publish_source_runtime

        def inject_junction(source, tree):
            original_publish(source, tree)
            site_packages = (
                scenario.runtime_target / "Lib" / "site-packages"
            )
            create_test_junction(site_packages, outside)

        with mock.patch.object(
            runtime_module,
            "_publish_source_runtime",
            side_effect=inject_junction,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_invalid$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(list(outside.iterdir()), [])

    def test_runtime_rejects_post_source_alternate_data_stream(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        original_publish = runtime_module._publish_source_runtime

        def inject_stream(source, tree):
            original_publish(source, tree)
            stream = Path(
                str(scenario.runtime_target / "python.exe") + ":unreviewed"
            )
            stream.write_bytes(b"unreviewed-stream")

        with mock.patch.object(
            runtime_module,
            "_publish_source_runtime",
            side_effect=inject_stream,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_invalid$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertTrue(scenario.runtime_target.exists())

    def test_crx_rejects_mutation_during_target_verification(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        original_verify = PublicationScopeWindow.verify_target

        def inject_target_bytes(window):
            original_verify(window)
            if window._role == "artifact":
                window.write_all(b"unreviewed-target-bytes")

        with mock.patch.object(
            PublicationScopeWindow,
            "verify_target",
            inject_target_bytes,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^crx_copy_mismatch$"
            ):
                ArtifactPublisher.publish(scope=scope)

        self.assertTrue(scenario.crx_target.exists())

    def test_database_source_handle_denies_concurrent_writer(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        api = WindowsReadHandleApi()
        handle = api.open_existing(
            scenario.database_source, deny_write=True
        )
        try:
            writer = _open_writer(scenario.database_source)
            self.assertTrue(writer is None or writer == _INVALID_HANDLE)
        finally:
            api.close(handle)

    def test_database_lock_and_source_replacement_fail_before_copy(self) -> None:
        locked = build_runtime_scenario()
        self.addCleanup(locked.close)
        locked_scope = self._scope(locked)
        writer = _open_writer(locked.database_source)
        self.assertNotIn(writer, (None, _INVALID_HANDLE))
        try:
            with self.assertRaisesRegex(
                ManagedActivationError,
                "^managed_activation_handle_open_failed$",
            ):
                StoppedDatabaseCopier.copy(
                    scope=locked_scope,
                    stopped_service_receipt=self._stopped(locked_scope),
                )
        finally:
            _close_handle(writer)
        self.assertFalse(locked.database_target.exists())

        replaced = build_runtime_scenario()
        self.addCleanup(replaced.close)
        replaced_scope = self._scope(replaced)
        original = replaced.root / "retained-original.sqlite3"
        replaced.database_source.rename(original)
        replaced.database_source.write_bytes(original.read_bytes())
        with self.assertRaisesRegex(
            ManagedActivationError, "^database_source_changed$"
        ):
            StoppedDatabaseCopier.copy(
                scope=replaced_scope,
                stopped_service_receipt=self._stopped(replaced_scope),
            )
        self.assertTrue(original.exists())
        self.assertFalse(replaced.database_target.exists())

    def test_copy_mismatch_is_detected_and_partial_is_retained(self) -> None:
        database = build_runtime_scenario()
        self.addCleanup(database.close)
        database_scope = self._scope(database)
        real_read = WindowsCreateOnlyApi.read_all

        def corrupt_read(api, handle):
            return real_read(api, handle) + b"copy-mismatch"

        with mock.patch.object(
            WindowsCreateOnlyApi,
            "read_all",
            new=corrupt_read,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^database_copy_mismatch$"
            ):
                StoppedDatabaseCopier.copy(
                    scope=database_scope,
                    stopped_service_receipt=self._stopped(database_scope),
                )
        self.assertTrue(database.database_target.exists())

        crx = build_runtime_scenario()
        self.addCleanup(crx.close)
        crx_scope = self._scope(crx)

        with mock.patch.object(
            WindowsCreateOnlyApi,
            "read_all",
            new=corrupt_read,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^crx_copy_mismatch$"
            ):
                ArtifactPublisher.publish(scope=crx_scope)
        self.assertTrue(crx.crx_target.exists())

        config = build_runtime_scenario()
        self.addCleanup(config.close)
        config_scope = self._scope(config)

        with mock.patch.object(
            WindowsCreateOnlyApi,
            "read_all",
            new=corrupt_read,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^config_copy_mismatch$"
            ):
                ConfigPublisher.publish(
                    scope=config_scope,
                    config=ManagedConfigV1.from_mapping(
                        config.config_values
                    ),
                )
        self.assertTrue(config.config_target.exists())

    def test_failure_output_and_repr_are_content_free(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        scope = self._scope(scenario)
        scenario.config_target.write_bytes(b"existing")
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
            stderr
        ):
            try:
                ConfigPublisher.publish(
                    scope=scope,
                    config=ManagedConfigV1.from_mapping(
                        scenario.config_values
                    ),
                )
            except ManagedActivationError as error:
                rendered = f"{error!s}|{error!r}|{scope!r}"
            else:
                self.fail("collision must fail")
        combined = stdout.getvalue() + stderr.getvalue() + rendered
        self.assertNotIn(str(scenario.root), combined)
        self.assertNotIn("example.test", combined)
        self.assertNotIn("existing", combined)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def _scope(self, scenario):
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        authorization = authorization_for(
            profile, review.operation_fingerprint
        )
        return _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )

    def _stopped(self, scope):
        return StoppedServiceReceiptV1.create(
            operation_fingerprint=scope.review.operation_fingerprint,
            profile_fingerprint=scope.profile.profile_fingerprint,
            governing_master_commit=EXPECTED_MASTER,
            authorization_fingerprint=scope.authorization_fingerprint,
            service_role_fingerprint=(
                scope.review.stopped_service_role_fingerprint
            ),
            database_source_fingerprint=(
                scope.review.database_source_fingerprint
            ),
            observation_fingerprint="7" * 64,
        )


def _open_writer(path: Path):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
        ctypes.c_void_p,
    )
    kernel.CreateFileW.restype = ctypes.c_void_p
    return kernel.CreateFileW(
        str(path),
        0x40000000,
        0,
        None,
        3,
        0,
        None,
    )


def _close_handle(handle: int) -> None:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    if not kernel.CloseHandle(handle):
        raise RuntimeError("synthetic_handle_close_failed")


if __name__ == "__main__":
    unittest.main()
