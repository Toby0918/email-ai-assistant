from __future__ import annotations

import io
import zipfile
import unittest
import sys

from backend.cutover_managed_activation import (
    ArtifactPublicationAdapter,
    ArtifactPublisher,
    ConfigPublicationAdapter,
    ConfigPublicationReceiptV1,
    ConfigPublisher,
    CrxPublicationReceiptV1,
    DatabasePublicationAdapter,
    LockedRuntimeBuilder,
    ManagedActivationAdapters,
    ManagedActivationError,
    ManagedActivationPhase,
    ManagedActivationReceiptSetV1,
    ManagedConfigV1,
    ManagedRuntimeReceiptV1,
    RuntimePublicationAdapter,
    StoppedDatabaseCopier,
    StoppedServiceReceiptV1,
    StoppedDatabaseCopyReceiptV1,
)
from backend.cutover_managed_activation.synthetic_scope import (
    _bind_test_sandbox_activation,
    _review_test_sandbox_activation,
)
from backend.cutover_managed_activation.runtime_limits import RuntimeTreeBudget
from backend.cutover_managed_activation.runtime_policy import (
    review_wheel_archive,
)
from backend.cutover_managed_activation.runtime_archive import (
    preflight_wheel_payload,
)
from tests.cutover_managed_activation_fixtures import (
    OBSERVED_AT,
    add_locked_support_wheel,
    authorization_for,
    build_runtime_scenario,
    profile_for_review,
)


MASTER = "7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd"
OPERATION = "1" * 64
PROFILE = "2" * 64
AUTHORIZATION = "3" * 64


def _receipt(receipt_type):
    return receipt_type.create(
        operation_fingerprint=OPERATION,
        profile_fingerprint=PROFILE,
        governing_master_commit=MASTER,
        authorization_fingerprint=AUTHORIZATION,
        input_fingerprints=("4" * 64,),
        observation_fingerprint="5" * 64,
        counts={"published": 1, "rejected": 0},
    )


class ManagedActivationContractTests(unittest.TestCase):
    def test_wheel_archive_metadata_is_bounded_before_extraction(self) -> None:
        payload = io.BytesIO()
        with zipfile.ZipFile(
            payload, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            archive.writestr("package/__init__.py", b"x" * 1_000_000)

        with zipfile.ZipFile(io.BytesIO(payload.getvalue())) as archive:
            with self.assertRaisesRegex(
                ManagedActivationError, "^runtime_wheel_invalid$"
            ):
                review_wheel_archive(
                    archive,
                    max_members=10,
                    max_member_bytes=2_000_000,
                    max_expanded_bytes=2_000_000,
                    max_compression_ratio=10,
                )

    def test_runtime_tree_budget_rejects_entry_and_byte_overflow(self) -> None:
        entries = RuntimeTreeBudget(max_entries=1, max_bytes=10)
        entries.add_directory(("Lib",))
        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_tree_invalid$"
        ):
            entries.add_file(("Lib", "extra.py"), 1)

        size = RuntimeTreeBudget(max_entries=2, max_bytes=3)
        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_tree_invalid$"
        ):
            size.add_file(("large.py",), 4)

    def test_wheel_central_directory_is_bounded_before_zipfile_parse(
        self,
    ) -> None:
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            for index in range(4097):
                archive.writestr(f"package/member-{index}.txt", b"")

        with self.assertRaisesRegex(
            ManagedActivationError, "^runtime_wheel_invalid$"
        ):
            preflight_wheel_payload(payload.getvalue())

    def test_phase_returns_exact_chained_publication_receipts(self) -> None:
        runtime = _receipt(ManagedRuntimeReceiptV1)
        database = _receipt(StoppedDatabaseCopyReceiptV1)
        crx = _receipt(CrxPublicationReceiptV1)
        config = _receipt(ConfigPublicationReceiptV1)
        adapters = ManagedActivationAdapters(
            runtime=RuntimePublicationAdapter(lambda: runtime),
            database=DatabasePublicationAdapter(lambda: database),
            artifact=ArtifactPublicationAdapter(lambda: crx),
            config=ConfigPublicationAdapter(lambda: config),
        )

        receipt_set = ManagedActivationPhase.create(
            operation_fingerprint=OPERATION,
            profile_fingerprint=PROFILE,
            governing_master_commit=MASTER,
            authorization_fingerprint=AUTHORIZATION,
        ).publish(adapters)

        self.assertEqual(
            receipt_set.receipt_fingerprints,
            (
                runtime.receipt_fingerprint,
                database.receipt_fingerprint,
                crx.receipt_fingerprint,
                config.receipt_fingerprint,
            ),
        )
        self.assertEqual(receipt_set.published, 4)
        self.assertEqual(receipt_set.rejected, 0)

    def test_phase_rejects_receipt_chain_drift(self) -> None:
        runtime = _receipt(ManagedRuntimeReceiptV1)
        database = _receipt(StoppedDatabaseCopyReceiptV1)
        crx = _receipt(CrxPublicationReceiptV1)
        config = ConfigPublicationReceiptV1.create(
            operation_fingerprint="9" * 64,
            profile_fingerprint=PROFILE,
            governing_master_commit=MASTER,
            authorization_fingerprint=AUTHORIZATION,
            input_fingerprints=("4" * 64,),
            observation_fingerprint="5" * 64,
            counts={"published": 1, "rejected": 0},
        )
        adapters = ManagedActivationAdapters(
            runtime=RuntimePublicationAdapter(lambda: runtime),
            database=DatabasePublicationAdapter(lambda: database),
            artifact=ArtifactPublicationAdapter(lambda: crx),
            config=ConfigPublicationAdapter(lambda: config),
        )

        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_phase_invalid$"
        ):
            ManagedActivationPhase.create(
                operation_fingerprint=OPERATION,
                profile_fingerprint=PROFILE,
                governing_master_commit=MASTER,
                authorization_fingerprint=AUTHORIZATION,
            ).publish(adapters)

    def test_phase_stops_before_later_adapters_after_invalid_receipt(
        self,
    ) -> None:
        calls = []
        phase = ManagedActivationPhase.create(
            operation_fingerprint=OPERATION,
            profile_fingerprint=PROFILE,
            governing_master_commit=MASTER,
            authorization_fingerprint=AUTHORIZATION,
        )
        adapters = ManagedActivationAdapters(
            runtime=RuntimePublicationAdapter(
                lambda: calls.append("runtime") or object()
            ),
            database=DatabasePublicationAdapter(
                lambda: calls.append("database")
                or _receipt(StoppedDatabaseCopyReceiptV1)
            ),
            artifact=ArtifactPublicationAdapter(
                lambda: calls.append("artifact")
                or _receipt(CrxPublicationReceiptV1)
            ),
            config=ConfigPublicationAdapter(
                lambda: calls.append("config")
                or _receipt(ConfigPublicationReceiptV1)
            ),
        )

        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_phase_invalid$"
        ):
            phase.publish(adapters)

        self.assertEqual(calls, ["runtime"])

    def test_receipt_set_rejects_unvalidated_construction(self) -> None:
        with self.assertRaises(TypeError):
            ManagedActivationReceiptSetV1(
                receipt_fingerprints=("not-a-fingerprint",),
                published=99,
                rejected=-1,
            )

        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_phase_invalid$"
        ):
            ManagedActivationReceiptSetV1.create(
                receipts=("1" * 64, "2" * 64, "3" * 64, "4" * 64)
            )

    def test_receipt_set_round_trip_revalidates_exact_typed_chain(self) -> None:
        receipts = (
            _receipt(ManagedRuntimeReceiptV1),
            _receipt(StoppedDatabaseCopyReceiptV1),
            _receipt(CrxPublicationReceiptV1),
            _receipt(ConfigPublicationReceiptV1),
        )
        value = ManagedActivationReceiptSetV1.create(receipts=receipts)

        rebuilt = ManagedActivationReceiptSetV1.from_mapping(
            value.to_mapping()
        )

        self.assertEqual(rebuilt, value)
        self.assertEqual(rebuilt.operation_fingerprint, OPERATION)
        forged = value.to_mapping()
        forged["receipts"] = list(reversed(forged["receipts"]))
        with self.assertRaisesRegex(
            ManagedActivationError, "^managed_activation_phase_invalid$"
        ):
            ManagedActivationReceiptSetV1.from_mapping(forged)

    @unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
    def test_runtime_is_built_offline_and_verified_by_new_runtime(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        authorization = authorization_for(
            profile, review.operation_fingerprint
        )
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )

        receipt = LockedRuntimeBuilder.publish(scope=scope)

        self.assertIs(type(receipt), ManagedRuntimeReceiptV1)
        self.assertEqual(
            receipt.profile_fingerprint, profile.profile_fingerprint
        )
        archive_path = scenario.runtime_target / "managed-startup.zip"
        source_encodings = (
            scenario.python_source.parent / "Lib" / "encodings"
        )
        expected_members = sorted(
            "encodings/" + path.relative_to(source_encodings).as_posix()
            for path in source_encodings.rglob("*")
            if path.is_file()
        )
        with zipfile.ZipFile(archive_path, "r") as archive:
            self.assertEqual(sorted(archive.namelist()), expected_members)
            self.assertTrue(
                all(
                    info.compress_type == zipfile.ZIP_STORED
                    and info.date_time == (1980, 1, 1, 0, 0, 0)
                    for info in archive.infolist()
                )
            )
        self.assertEqual(
            (scenario.runtime_target / "python312._pth").read_bytes(),
            b"managed-startup.zip\nLib\nDLLs\n",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
    def test_runtime_lock_accepts_reviewed_transitive_platform_wheel(
        self,
    ) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        add_locked_support_wheel(scenario)
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization_for(
                profile, review.operation_fingerprint
            ),
            observed_at_epoch=OBSERVED_AT,
        )

        receipt = LockedRuntimeBuilder.publish(scope=scope)

        self.assertEqual(dict(receipt.counts), {"published": 1, "rejected": 0})
        self.assertTrue(
            (
                scenario.runtime_target
                / "Lib"
                / "site-packages"
                / "runtime_support"
                / "__init__.py"
            ).is_file()
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
    def test_config_is_canonical_non_secret_create_only_publication(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        authorization = authorization_for(
            profile, review.operation_fingerprint
        )
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )
        config = ManagedConfigV1.from_mapping(scenario.config_values)

        receipt = ConfigPublisher.publish(scope=scope, config=config)

        self.assertIs(type(receipt), ConfigPublicationReceiptV1)
        self.assertEqual(
            receipt.profile_fingerprint, profile.profile_fingerprint
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
    def test_complete_phase_publishes_four_chained_receipts(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        authorization = authorization_for(
            profile, review.operation_fingerprint
        )
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )
        stopped = StoppedServiceReceiptV1.create(
            operation_fingerprint=review.operation_fingerprint,
            profile_fingerprint=profile.profile_fingerprint,
            governing_master_commit=MASTER,
            authorization_fingerprint=scope.authorization_fingerprint,
            service_role_fingerprint=(
                review.stopped_service_role_fingerprint
            ),
            database_source_fingerprint=(
                review.database_source_fingerprint
            ),
            observation_fingerprint="7" * 64,
        )
        config = ManagedConfigV1.from_mapping(scenario.config_values)
        adapters = ManagedActivationAdapters(
            runtime=RuntimePublicationAdapter(
                lambda: LockedRuntimeBuilder.publish(scope=scope)
            ),
            database=DatabasePublicationAdapter(
                lambda: StoppedDatabaseCopier.copy(
                    scope=scope,
                    stopped_service_receipt=stopped,
                )
            ),
            artifact=ArtifactPublicationAdapter(
                lambda: ArtifactPublisher.publish(scope=scope)
            ),
            config=ConfigPublicationAdapter(
                lambda: ConfigPublisher.publish(
                    scope=scope,
                    config=config,
                )
            ),
        )

        receipts = ManagedActivationPhase.create(
            operation_fingerprint=review.operation_fingerprint,
            profile_fingerprint=profile.profile_fingerprint,
            governing_master_commit=MASTER,
            authorization_fingerprint=scope.authorization_fingerprint,
        ).publish(adapters)

        self.assertEqual((receipts.published, receipts.rejected), (4, 0))
        self.assertEqual(len(set(receipts.receipt_fingerprints)), 4)

    @unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
    def test_crx_copy_is_exact_reviewed_create_only_publication(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        authorization = authorization_for(
            profile, review.operation_fingerprint
        )
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )

        receipt = ArtifactPublisher.publish(scope=scope)

        self.assertIs(type(receipt), CrxPublicationReceiptV1)
        self.assertEqual(
            receipt.profile_fingerprint, profile.profile_fingerprint
        )
        self.assertEqual(
            receipt.governing_master_commit, MASTER
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows sandbox evidence")
    def test_database_copy_holds_exact_stopped_source_window(self) -> None:
        scenario = build_runtime_scenario()
        self.addCleanup(scenario.close)
        review = _review_test_sandbox_activation(scenario)
        profile = profile_for_review(review)
        authorization = authorization_for(
            profile, review.operation_fingerprint
        )
        scope = _bind_test_sandbox_activation(
            review=review,
            profile=profile,
            authorization=authorization,
            observed_at_epoch=OBSERVED_AT,
        )
        stopped = StoppedServiceReceiptV1.create(
            operation_fingerprint=review.operation_fingerprint,
            profile_fingerprint=profile.profile_fingerprint,
            governing_master_commit=MASTER,
            authorization_fingerprint=scope.authorization_fingerprint,
            service_role_fingerprint=(
                review.stopped_service_role_fingerprint
            ),
            database_source_fingerprint=(
                review.database_source_fingerprint
            ),
            observation_fingerprint="7" * 64,
        )

        receipt = StoppedDatabaseCopier.copy(
            scope=scope, stopped_service_receipt=stopped
        )

        self.assertIs(type(receipt), StoppedDatabaseCopyReceiptV1)
        self.assertEqual(
            receipt.profile_fingerprint, profile.profile_fingerprint
        )


if __name__ == "__main__":
    unittest.main()
