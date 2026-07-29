from __future__ import annotations

import sys
import unittest
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
from backend.cutover_managed_activation import database_copier as database_module
from backend.cutover_managed_activation import runtime_builder as runtime_module
from backend.cutover_managed_activation import runtime_capture as capture_module
from backend.cutover_managed_activation import (
    runtime_verification as verification_module,
)
from backend.cutover_managed_activation import runtime_policy as policy_module
from backend.cutover_managed_activation.publication_scope import (
    PublicationScopeWindow,
)
from tests.cutover_managed_activation_fixtures import (
    EXPECTED_MASTER,
    OBSERVED_AT,
    authorization_for,
    add_startup_member,
    build_runtime_scenario,
    profile_for_review,
    replace_wheel_import,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
class ManagedActivationFailClosedTests(unittest.TestCase):
    def test_runtime_bounds_wheelhouse_enumeration_before_collection(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        child = next(scenario.wheelhouse.iterdir())
        wheel = policy_module.LockedWheelV1(
            distribution="synthetic",
            version="1.0",
            wheel=child.name,
            wheel_sha256="0" * 64,
            import_name="synthetic",
            import_sha256="0" * 64,
        )
        yielded = []

        class RepeatingWheelhouse:
            def iterdir(inner_self):
                yielded.append(1)
                yield child
                yielded.append(2)
                yield child
                raise AssertionError("enumeration was not bounded")

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_dependency_lock_invalid$"
        ):
            policy_module._review_wheelhouse(RepeatingWheelhouse(), (wheel,))

        self.assertEqual(yielded, [1, 2])

    def test_runtime_rejects_unreviewed_wheel_without_publication(self) -> None:
        scenario, scope = self._bound_scope()
        extra = scenario.wheelhouse / "unreviewed-1.0-py3-none-any.whl"
        extra.write_bytes(b"unreviewed")

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_dependency_lock_invalid$"
        ):
            LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(scenario.runtime_target.exists())
        self.assertTrue(extra.exists())

    def test_runtime_verifier_never_executes_installed_package_code(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        marker = scenario.root / "package-execution-marker"
        replace_wheel_import(
            scenario,
            "beautifulsoup4",
            (
                b"from pathlib import Path\n"
                + f"Path({str(marker)!r}).write_bytes(b'executed')\n".encode(
                    "utf-8"
                )
                + b"import socket\nsocket.socket()\n"
            ),
        )
        scope = self._scope_for(scenario)

        receipt = LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(dict(receipt.counts), {"published": 1, "rejected": 0})
        self.assertFalse(marker.exists())
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_rejects_interpreter_startup_wheel_member(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        add_startup_member(scenario, "beautifulsoup4")
        scope = self._scope_for(scenario)

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_wheel_invalid$"
        ):
            LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(scenario.runtime_target.exists())

    def test_runtime_rejects_oversized_raced_wheel_before_target(self) -> None:
        scenario, scope = self._bound_scope()
        wheel = next(scenario.wheelhouse.iterdir())
        original_open = runtime_module.open_python_source

        def race_after_review(*args, **kwargs):
            source = original_open(*args, **kwargs)
            with wheel.open("wb") as output:
                output.truncate(100_000_001)
            return source

        with mock.patch.object(
            runtime_module,
            "open_python_source",
            side_effect=race_after_review,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_source_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(scenario.runtime_target.exists())

    def test_runtime_applies_remaining_aggregate_before_wheel_read(self) -> None:
        scenario, scope = self._bound_scope()
        sizes = [
            (scenario.wheelhouse / wheel.wheel).stat().st_size
            for wheel in scope.review.runtime_inputs.wheels
        ]
        aggregate_limit = sizes[0] + sizes[1] - 1
        original_read = WindowsReadHandleApi.read_bounded
        attempted_limits = []
        rejected_limits = []

        def tracked_read(api, handle, *, limit):
            attempted_limits.append(limit)
            try:
                return original_read(api, handle, limit=limit)
            except ManagedActivationError:
                rejected_limits.append(limit)
                raise

        with (
            mock.patch.object(
                capture_module,
                "MAX_CAPTURED_WHEEL_BYTES",
                aggregate_limit,
            ),
            mock.patch.object(
                WindowsReadHandleApi,
                "read_bounded",
                tracked_read,
            ),
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_source_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(len(attempted_limits), 2)
        self.assertEqual(attempted_limits[1], sizes[1] - 1)
        self.assertEqual(rejected_limits, [sizes[1] - 1])
        self.assertFalse(scenario.runtime_target.exists())

    def test_runtime_rejects_source_tree_drift_after_authorization(self) -> None:
        scenario, scope = self._bound_scope()
        marker = scenario.root / "source-execution-marker"
        source_module = (
            scenario.python_source.parent / "Lib" / "venv" / "__init__.py"
        )
        replacement = source_module.with_name("replacement.py")
        replacement.write_bytes(
            (
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_bytes(b'executed')\n"
            ).encode("utf-8")
            + source_module.read_bytes()
        )
        replacement.replace(source_module)

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_python_source_invalid$"
        ):
            LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(marker.exists())
        self.assertFalse(scenario.runtime_target.exists())

    def test_runtime_holds_complete_source_tree_during_build(self) -> None:
        scenario, scope = self._bound_scope()
        source_module = (
            scenario.python_source.parent / "Lib" / "venv" / "__init__.py"
        )
        original_publish = runtime_module._publish_source_runtime
        write_was_blocked = []

        def assert_source_locked(source, tree):
            with self.assertRaises(PermissionError):
                source_module.open("r+b")
            write_was_blocked.append(True)
            return original_publish(source, tree)

        with mock.patch.object(
            runtime_module,
            "_publish_source_runtime",
            side_effect=assert_source_locked,
        ):
            LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(write_was_blocked, [True])

    def test_runtime_never_executes_added_source_namespace_entries(self) -> None:
        scenario, scope = self._bound_scope()
        marker = scenario.root / "source-namespace-execution-marker"
        source_root = scenario.python_source.parent
        original_publish = runtime_module._publish_source_runtime

        def inject_source_namespace(source, tree):
            site = source_root / "evilsite"
            site.mkdir()
            (site / "sitecustomize.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_bytes(b'executed')\n",
                "utf-8",
            )
            (source_root / "python312._pth").write_text(
                "evilsite\nimport site\n", "ascii"
            )
            return original_publish(source, tree)

        with mock.patch.object(
            runtime_module,
            "_publish_source_runtime",
            side_effect=inject_source_namespace,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_source_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertFalse(marker.exists())
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_kills_verifier_at_stdout_ceiling(self) -> None:
        scenario, scope = self._bound_scope()
        infinite_output = (
            "import sys\n"
            "while True:\n"
            " sys.stdout.write('x'*65536)\n"
            " sys.stdout.flush()\n"
        )
        with mock.patch.object(
            verification_module,
            "_verification_script",
            return_value=infinite_output,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError,
                "^runtime_self_verification_failed$",
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertTrue(scenario.runtime_target.is_dir())

    def test_runtime_never_executes_added_target_startup_namespace(
        self,
    ) -> None:
        scenario, scope = self._bound_scope()
        marker = scenario.root / "target-namespace-execution-marker"
        original_verify = runtime_module.verify_with_new_runtime
        write_was_blocked = []

        def inject_transient(target, review):
            pth = target / "python312._pth"
            with self.assertRaises(PermissionError):
                pth.write_text("evilsite\nimport site\n", "ascii")
            write_was_blocked.append(True)
            site = target / "evilsite"
            site.mkdir()
            startup = site / "sitecustomize.py"
            startup.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_bytes(b'executed')\n",
                "utf-8",
            )
            try:
                return original_verify(target, review)
            finally:
                startup.unlink()
                site.rmdir()

        with mock.patch.object(
            runtime_module,
            "verify_with_new_runtime",
            side_effect=inject_transient,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_changed$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(write_was_blocked, [True])
        self.assertFalse(marker.exists())
        self.assertEqual(
            (scenario.runtime_target / "python312._pth").read_bytes(),
            b"managed-startup.zip\nLib\nDLLs\n",
        )

    def test_runtime_target_collision_is_preserved(self) -> None:
        scenario, scope = self._bound_scope()
        scenario.runtime_target.mkdir()
        marker = scenario.runtime_target / "existing.marker"
        marker.write_bytes(b"preserve")

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_publication_failed$"
        ):
            LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(marker.read_bytes(), b"preserve")

    def test_runtime_flush_failure_retains_partial_target(self) -> None:
        scenario, scope = self._bound_scope()
        with mock.patch(
            "backend.cutover_managed_activation.windows_publication_io."
            "WindowsCreateOnlyApi.flush",
            side_effect=OSError("synthetic flush failure"),
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_tree_invalid$"
            ):
                LockedRuntimeBuilder.publish(scope=scope)
        self.assertTrue(scenario.runtime_target.is_dir())

    def test_database_rejects_each_sidecar_and_retains_it(self) -> None:
        for suffix in ("-wal", "-shm", "-journal"):
            with self.subTest(suffix=suffix):
                scenario = build_runtime_scenario()
                try:
                    scope = self._scope_for(scenario)
                    sidecar = scenario.database_source.with_name(
                        scenario.database_source.name + suffix
                    )
                    sidecar.write_bytes(b"synthetic-sidecar")
                    stopped = self._stopped(scope)
                    with self.assertRaisesRegex(
                        ManagedActivationError, "^database_sidecar_present$"
                    ):
                        StoppedDatabaseCopier.copy(
                            scope=scope,
                            stopped_service_receipt=stopped,
                        )
                    self.assertTrue(sidecar.exists())
                    self.assertFalse(scenario.database_target.exists())
                finally:
                    scenario.close()

    def test_database_requires_exact_stopped_receipt(self) -> None:
        scenario, scope = self._bound_scope()
        stopped = StoppedServiceReceiptV1.create(
            operation_fingerprint="8" * 64,
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

        with self.assertRaisesRegex(
            ManagedActivationError, "^stopped_service_receipt_invalid$"
        ):
            StoppedDatabaseCopier.copy(
                scope=scope, stopped_service_receipt=stopped
            )

        self.assertFalse(scenario.database_target.exists())

    def test_database_rejects_sidecar_created_during_copy_window(self) -> None:
        scenario, scope = self._bound_scope()
        sidecar = scenario.database_source.with_name(
            scenario.database_source.name + "-wal"
        )
        original = database_module._require_integrity
        created = False

        def create_late_sidecar(path):
            nonlocal created
            original(path)
            if path == scenario.database_source and not created:
                sidecar.write_bytes(b"synthetic-late-sidecar")
                created = True

        with mock.patch.object(
            database_module,
            "_require_integrity",
            side_effect=create_late_sidecar,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^database_sidecar_present$"
            ):
                StoppedDatabaseCopier.copy(
                    scope=scope,
                    stopped_service_receipt=self._stopped(scope),
                )

        self.assertTrue(sidecar.exists())
        self.assertTrue(scenario.database_target.exists())

    def test_database_rejects_sidecar_created_after_target_verification(
        self,
    ) -> None:
        scenario, scope = self._bound_scope()
        sidecar = scenario.database_source.with_name(
            scenario.database_source.name + "-wal"
        )
        original_verify = PublicationScopeWindow.verify_target

        def inject_late_sidecar(window):
            original_verify(window)
            if window._role == "database":
                sidecar.write_bytes(b"late-sidecar")

        with mock.patch.object(
            PublicationScopeWindow,
            "verify_target",
            inject_late_sidecar,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^database_sidecar_present$"
            ):
                StoppedDatabaseCopier.copy(
                    scope=scope,
                    stopped_service_receipt=self._stopped(scope),
                )

        self.assertTrue(sidecar.exists())
        self.assertTrue(scenario.database_target.exists())

    def test_database_integrity_failure_does_not_create_target(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        payload = scenario.database_source.read_bytes()
        scenario.database_source.write_bytes(payload[:200])
        scope = self._scope_for(scenario)

        with self.assertRaisesRegex(
            ManagedActivationError, "^database_integrity_failed$"
        ):
            StoppedDatabaseCopier.copy(
                scope=scope,
                stopped_service_receipt=self._stopped(scope),
            )

        self.assertFalse(scenario.database_target.exists())

    def test_database_collision_and_flush_failure_preserve_target(self) -> None:
        scenario, scope = self._bound_scope()
        scenario.database_target.write_bytes(b"existing")
        with self.assertRaisesRegex(
            ManagedActivationError, "^database_target_collision$"
        ):
            StoppedDatabaseCopier.copy(
                scope=scope,
                stopped_service_receipt=self._stopped(scope),
            )
        self.assertEqual(scenario.database_target.read_bytes(), b"existing")

        other, other_scope = self._bound_scope()
        with mock.patch(
            "backend.cutover_managed_activation.windows_publication_io."
            "WindowsCreateOnlyApi.flush",
            side_effect=OSError("synthetic flush failure"),
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^stopped_database_copy_failed$"
            ):
                StoppedDatabaseCopier.copy(
                    scope=other_scope,
                    stopped_service_receipt=self._stopped(other_scope),
                )
        self.assertTrue(other.database_target.exists())

    def test_crx_drift_collision_and_flush_failure_fail_closed(self) -> None:
        scenario, scope = self._bound_scope()
        scenario.crx_source.write_bytes(
            scenario.crx_source.read_bytes() + b"drift"
        )
        with self.assertRaisesRegex(
            ManagedActivationError, "^crx_source_changed$"
        ):
            ArtifactPublisher.publish(scope=scope)
        self.assertFalse(scenario.crx_target.exists())

        collision, collision_scope = self._bound_scope()
        collision.crx_target.write_bytes(b"existing")
        with self.assertRaisesRegex(
            ManagedActivationError, "^crx_target_collision$"
        ):
            ArtifactPublisher.publish(scope=collision_scope)
        self.assertEqual(collision.crx_target.read_bytes(), b"existing")

        partial, partial_scope = self._bound_scope()
        with mock.patch(
            "backend.cutover_managed_activation.windows_publication_io."
            "WindowsCreateOnlyApi.flush",
            side_effect=OSError("synthetic flush failure"),
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^crx_publication_failed$"
            ):
                ArtifactPublisher.publish(scope=partial_scope)
        self.assertTrue(partial.crx_target.exists())

    def test_crx_close_failure_is_fixed_and_retains_publication(self) -> None:
        scenario, scope = self._bound_scope()
        original_close = WindowsReadHandleApi.close

        def close_then_fail(api, handle):
            original_close(api, handle)
            raise OSError("synthetic close failure")

        with mock.patch.object(
            WindowsReadHandleApi,
            "close",
            new=close_then_fail,
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^crx_publication_failed$"
            ):
                ArtifactPublisher.publish(scope=scope)

        self.assertTrue(scenario.crx_target.exists())

    def test_scope_review_maps_disappearing_inputs_to_fixed_code(self) -> None:
        marker = build_runtime_scenario()
        self.addCleanup(marker.close)
        marker.marker.unlink()
        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_scope_invalid$"
        ):
            _review_test_sandbox_activation(marker)

        wheelhouse = build_runtime_scenario()
        self.addCleanup(wheelhouse.close)
        wheelhouse.wheelhouse.rename(wheelhouse.root / "moved-wheelhouse")
        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_scope_invalid$"
        ):
            _review_test_sandbox_activation(wheelhouse)

    def test_config_rejects_forbidden_unknown_and_expected_drift(self) -> None:
        scenario, scope = self._bound_scope()
        forbidden = {
            **scenario.config_values,
            "DEEPSEEK_API_KEY": "synthetic-forbidden",
        }
        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_config_invalid$"
        ):
            ManagedConfigV1.from_mapping(forbidden)
        changed = ManagedConfigV1.from_mapping(
            {
                **scenario.config_values,
                "EMAIL_AGENT_LOG_LEVEL": "ERROR",
            }
        )
        with self.assertRaisesRegex(
            ManagedActivationError, "^config_expected_value_mismatch$"
        ):
            ConfigPublisher.publish(scope=scope, config=changed)
        self.assertFalse(scenario.config_target.exists())

    def test_config_collision_and_flush_failure_preserve_target(self) -> None:
        scenario, scope = self._bound_scope()
        scenario.config_target.write_bytes(b"existing")
        config = ManagedConfigV1.from_mapping(scenario.config_values)
        with self.assertRaisesRegex(
            ManagedActivationError, "^config_target_collision$"
        ):
            ConfigPublisher.publish(scope=scope, config=config)
        self.assertEqual(scenario.config_target.read_bytes(), b"existing")

        partial, partial_scope = self._bound_scope()
        partial_config = ManagedConfigV1.from_mapping(partial.config_values)
        with mock.patch(
            "backend.cutover_managed_activation.windows_publication_io."
            "WindowsCreateOnlyApi.flush",
            side_effect=OSError("synthetic flush failure"),
        ):
            with self.assertRaisesRegex(
                ManagedActivationError, "^config_publication_failed$"
            ):
                ConfigPublisher.publish(
                    scope=partial_scope, config=partial_config
                )
        self.assertTrue(partial.config_target.exists())

    def _bound_scope(self):
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        return scenario, self._scope_for(scenario)

    def _scope_for(self, scenario):
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


if __name__ == "__main__":
    unittest.main()
