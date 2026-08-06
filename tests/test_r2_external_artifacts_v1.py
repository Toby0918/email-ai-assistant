"""Public-only R2 external artifact preparation contracts for Issue #105."""

from __future__ import annotations

import ctypes
import inspect
import hashlib
import os
import subprocess
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from backend.r2_ci_provenance_v2 import (
    CiProvenanceKindV2,
    CiProvenanceStatusV2,
    R2CiProvenanceBundleV2,
    R2CiProvenanceReceiptV2,
    fixed_suite_fingerprint_v2,
)
from backend.r2_final_master_closure import (
    ClosureGate,
    FinalMasterBindingV1,
)
from backend.r2_final_master_closure._canonical import canonical_json, fingerprint, strict_json_object
from backend.r2_final_master_closure.frozen_master import _allocate as _allocate_frozen
from backend.r2_operator_runbook_v2.receipt import (
    R2OperatorRunbookReceiptV2,
    RunbookVerificationStatusV2,
)
from backend.r2_operator_runbook_v2.review_registry import (
    blocker_resolution_fingerprint_v2,
    decision_registry_fingerprint_v2,
)
from backend.r2_operator_runbook_v2.state_machine import (
    operator_package_semantics_fingerprint_v2,
)
from backend.r2_production_binding import PublicKeyRoleV2
from backend.r2_production_binding.review import (
    production_composition_evidence_fingerprint_v2,
)
from backend.r2_production_composition import build_production_binding_candidate_v1
from backend.r2_repository_manifest.git_byte_receipt_v2 import (
    R2GitByteStateReceiptV1,
)
from backend.r2_retention_ledger_v2 import R2RetentionProofV2

from backend.r2_external_artifacts_v1 import (
    R2ExternalArtifactError,
    R2ExternalArtifactReviewInputsV1,
    R2GateSourceReviewV1,
    R2UnsignedExternalArtifactPackageV1,
    install_signed_external_artifacts_v1,
    prepare_unsigned_external_artifacts_v1,
)
from backend.r2_external_artifacts_v1.installer import (
    _close_file_id_guards,
    _open_file_id_guards,
    _publish_validated_files_v1,
    _rename_no_replace,
    _require_fresh_master_v1,
    _wait_for_handle,
)
from backend.r2_external_artifacts_v1.derivation import (
    _serialized_direct_fingerprint,
)
from backend.r2_external_artifacts_v1.review_inputs import (
    _require_source_review_mapping_v1,
)
from backend.r2_external_artifacts_v1.unsigned_package import (
    _require_package_integrity_v1,
)


@contextmanager
def _temporary_directory(*, prefix):
    temporary = tempfile.TemporaryDirectory(prefix=prefix, ignore_cleanup_errors=True)
    try:
        yield temporary.name
    finally:
        if os.name == "nt" and Path(temporary.name).exists():
            reset = subprocess.run(
                ["icacls.exe", temporary.name, "/reset", "/T", "/C", "/Q"],
                capture_output=True,
                text=True,
                check=False,
            )
            if reset.returncode != 0:
                raise AssertionError("temporary ACL reset failed")
        temporary.cleanup()
        if Path(temporary.name).exists():
            raise AssertionError("temporary directory cleanup failed")


class R2ExternalArtifactsV1Tests(unittest.TestCase):
    def test_exact_reviewed_outputs_produce_one_binding_and_fourteen_bodies(self):
        fixture = _fixture()

        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )

        self.assertIsInstance(package, R2UnsignedExternalArtifactPackageV1)
        self.assertEqual(package.artifact_count, 15)
        self.assertEqual(package.unsigned_gate_count, 14)
        self.assertEqual(package.signature_count, 0)
        self.assertEqual(
            package.reviewed_production_binding_json,
            fixture["production_binding"].to_canonical_json(),
        )
        self.assertEqual(
            tuple(item.gate for item in package.unsigned_gate_artifacts),
            tuple(ClosureGate),
        )
        self.assertEqual(
            tuple(item.filename for item in package.unsigned_gate_artifacts),
            tuple(
                f"{index:02d}-{gate.value}.json"
                for index, gate in enumerate(ClosureGate, start=1)
            ),
        )
        evidence = {
            item.gate: item.evidence_fingerprint
            for item in package.unsigned_gate_artifacts
        }
        self.assertEqual(
            evidence[ClosureGate.FINAL_MASTER_BINDING],
            fixture["frozen"].observation_fingerprint,
        )
        self.assertEqual(
            evidence[ClosureGate.PRODUCTION_COMPOSITION],
            production_composition_evidence_fingerprint_v2(
                fixture["binding"], fixture["production_binding"]
            ),
        )
        self.assertEqual(
            evidence[ClosureGate.GIT_BYTES],
            fixture["git_receipt"].receipt_fingerprint,
        )
        self.assertEqual(
            evidence[ClosureGate.DEPENDENCY_ACTION_PROVENANCE],
            fixture["ci_bundle"].bundle_fingerprint,
        )
        self.assertEqual(
            evidence[ClosureGate.PORTABLE_FULL_SUITE],
            fixture["ci_receipts"][0].receipt_fingerprint,
        )
        self.assertEqual(
            evidence[ClosureGate.RUNBOOK_SEMANTICS],
            fixture["runbook_receipt"].receipt_fingerprint,
        )
        self.assertEqual(
            evidence[ClosureGate.RETENTION_NO_DELETION],
            fixture["retention_proof"].proof_fingerprint,
        )

        reconstructed = R2UnsignedExternalArtifactPackageV1.from_json(
            package.to_canonical_json(), frozen_master=fixture["frozen"]
        )
        self.assertEqual(
            reconstructed.to_canonical_json(), package.to_canonical_json()
        )
        self.assertEqual(
            reconstructed.issuance_manifest_fingerprint,
            package.issuance_manifest_fingerprint,
        )

    def test_unsigned_package_mappings_cannot_mutate_internal_provenance(self):
        fixture = _fixture()
        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )
        exported = package.to_mapping()
        exported["supporting_provenance_records"][0]["source"]["status"] = (
            "MUTATED"
        )
        self.assertEqual(
            package.supporting_provenance_records[0].source_mapping["status"],
            "FROZEN_REMOTE_MASTER_VERIFIED",
        )
        self.assertNotEqual(exported, package.to_mapping())

    def test_windows_provenance_retains_both_complete_receipts(self):
        fixture = _fixture()
        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )
        record = package.supporting_provenance_records[
            list(ClosureGate).index(ClosureGate.WINDOWS_NATIVE)
        ]
        self.assertEqual(
            record.supporting_source_mappings,
            tuple(item.to_mapping() for item in fixture["ci_receipts"][1:]),
        )

    def test_preparation_rejects_self_consistent_non_integer_counts(self):
        fixture = _fixture()
        for bad in (False, 14.0):
            body = fixture["git_receipt"].to_mapping()
            body.pop("receipt_fingerprint")
            body["local_ref_count"] = bad
            forged = _allocate(
                R2GitByteStateReceiptV1, body, "receipt_fingerprint",
                "r2-git-byte-state-receipt-v1",
            )
            with self.subTest(value=bad), self.assertRaises(R2ExternalArtifactError):
                prepare_unsigned_external_artifacts_v1(
                    frozen_master=fixture["frozen"],
                    authority_verification_public_keys=fixture["authority_keys"],
                    review_inputs=_replace_review_inputs(
                        fixture["review_inputs"], git_byte_receipt=forged
                    ),
                )

        portable_body = fixture["ci_receipts"][0].to_mapping()
        portable_body.pop("receipt_fingerprint")
        portable_body["platform_lock_fingerprint"] = fixture[
            "ci_receipts"
        ][1].platform_lock_fingerprint
        portable = _allocate(
            R2CiProvenanceReceiptV2, portable_body, "receipt_fingerprint",
            "r2-ci-provenance-receipt-v2",
            {"status": CiProvenanceStatusV2, "provenance_kind": CiProvenanceKindV2},
        )
        receipts = (portable, *fixture["ci_receipts"][1:])
        with self.assertRaises(R2ExternalArtifactError):
            prepare_unsigned_external_artifacts_v1(
                frozen_master=fixture["frozen"],
                authority_verification_public_keys=fixture["authority_keys"],
                review_inputs=_replace_review_inputs(
                    fixture["review_inputs"],
                    ci_provenance_receipts=receipts,
                    ci_provenance_bundle=_ci_bundle(fixture["binding"], receipts),
                ),
            )

    def test_round_trip_rejects_recomputed_remote_ref_and_windows_receipt(self):
        fixture = _fixture()
        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )
        remote_tamper = package.to_mapping()
        final_record = remote_tamper["supporting_provenance_records"][0]
        final_record["source"]["remote_ref_fingerprint"] = "1" * 64
        final_body = dict(final_record["source"])
        final_body.pop("observation_fingerprint")
        final_record["evidence_fingerprint"] = fingerprint(
            "r2-frozen-remote-master-v1", final_body
        )
        final_record["source"]["observation_fingerprint"] = final_record[
            "evidence_fingerprint"
        ]
        _refingerprint_package(remote_tamper, 0)
        with self.assertRaises(R2ExternalArtifactError):
            R2UnsignedExternalArtifactPackageV1.from_json(
                canonical_json(remote_tamper), frozen_master=fixture["frozen"]
            )

        windows_tamper = package.to_mapping()
        index = list(ClosureGate).index(ClosureGate.WINDOWS_NATIVE)
        record = windows_tamper["supporting_provenance_records"][index]
        receipt = record["supporting_sources"][0]
        receipt["selected_byte_count"] = False
        receipt_body = dict(receipt)
        receipt_body.pop("receipt_fingerprint")
        receipt["receipt_fingerprint"] = fingerprint(
            "r2-ci-provenance-receipt-v2", receipt_body
        )
        record["source"]["source_fingerprints"][0]["fingerprint"] = receipt[
            "receipt_fingerprint"
        ]
        review_body = dict(record["source"])
        review_body.pop("review_fingerprint")
        record["evidence_fingerprint"] = fingerprint(
            "r2-gate-source-review-v1", review_body
        )
        record["source"]["review_fingerprint"] = record["evidence_fingerprint"]
        _refingerprint_package(windows_tamper, index)
        with self.assertRaises(R2ExternalArtifactError):
            R2UnsignedExternalArtifactPackageV1.from_json(
                canonical_json(windows_tamper), frozen_master=fixture["frozen"]
            )

    def test_preparation_rejects_arbitrary_or_mixed_binding_inputs(self):
        fixture = _fixture()
        source_parameters = inspect.signature(
            R2GateSourceReviewV1.create
        ).parameters
        prepare_parameters = inspect.signature(
            prepare_unsigned_external_artifacts_v1
        ).parameters
        self.assertNotIn("evidence_fingerprint", source_parameters)
        self.assertNotIn("evidence_fingerprint", prepare_parameters)

        wrong_binding = FinalMasterBindingV1.create(
            final_commit_oid="9" * 40,
            final_tree_oid="8" * 40,
            source_package_fingerprint="7" * 64,
            runbook_fingerprint="6" * 64,
            workflow_fingerprint="5" * 64,
        )
        wrong_frozen = _frozen(wrong_binding)
        with self.assertRaises(R2ExternalArtifactError):
            prepare_unsigned_external_artifacts_v1(
                frozen_master=wrong_frozen,
                authority_verification_public_keys=fixture["authority_keys"],
                review_inputs=fixture["review_inputs"],
            )

        duplicate_keys = dict(fixture["authority_keys"])
        duplicate_keys[PublicKeyRoleV2.RECOVERY_VERIFICATION] = duplicate_keys[
            PublicKeyRoleV2.EXECUTION_VERIFICATION
        ]
        with self.assertRaises(R2ExternalArtifactError):
            prepare_unsigned_external_artifacts_v1(
                frozen_master=fixture["frozen"],
                authority_verification_public_keys=duplicate_keys,
                review_inputs=fixture["review_inputs"],
            )

        with self.assertRaises(R2ExternalArtifactError):
            R2GateSourceReviewV1.create(
                gate=ClosureGate.DOCUMENTATION,
                final_master_binding=fixture["binding"],
                source_fingerprints={"evidence_fingerprint": "1" * 64},
            )

    def test_source_review_is_canonical_same_binding_and_gate_specific(self):
        binding = _binding()
        first = R2GateSourceReviewV1.create(
            gate=ClosureGate.LEAKAGE,
            final_master_binding=binding,
            source_fingerprints={
                "repository_leakage_scan": "1" * 64,
                "ci_leakage_reconciliation": "2" * 64,
            },
        )
        second = R2GateSourceReviewV1.create(
            gate=ClosureGate.LEAKAGE,
            final_master_binding=binding,
            source_fingerprints={
                "ci_leakage_reconciliation": "2" * 64,
                "repository_leakage_scan": "1" * 64,
            },
        )
        self.assertEqual(first, second)
        self.assertEqual(first.to_canonical_json(), second.to_canonical_json())
        self.assertEqual(first.review_result, "ACCEPTED")
        self.assertEqual(first.open_finding_count, 0)
        self.assertEqual(first.leakage_finding_count, 0)

        with self.assertRaises(R2ExternalArtifactError):
            R2GateSourceReviewV1.create(
                gate=ClosureGate.GIT_BYTES,
                final_master_binding=binding,
                source_fingerprints={"git_byte_receipt": "1" * 64},
            )

    def test_installer_rejects_unreviewed_manifest_and_invalid_signatures(self):
        fixture = _fixture()
        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )
        self.assertEqual(
            tuple(inspect.signature(install_signed_external_artifacts_v1).parameters),
            (
                "unsigned_package",
                "detached_signatures",
                "confirmed_manifest_fingerprint",
            ),
        )
        with self.assertRaises(R2ExternalArtifactError):
            install_signed_external_artifacts_v1(
                unsigned_package=package,
                detached_signatures=(bytes(64),) * 14,
                confirmed_manifest_fingerprint="0" * 64,
            )
        with self.assertRaises(R2ExternalArtifactError), patch(
            "backend.r2_external_artifacts_v1.installer._fixed_git_common_dir",
            side_effect=AssertionError("filesystem must not be reached"),
        ):
            install_signed_external_artifacts_v1(
                unsigned_package=package,
                detached_signatures=(bytes(64),) * 14,
                confirmed_manifest_fingerprint=(
                    package.issuance_manifest_fingerprint
                ),
            )

    def test_serialized_provenance_requires_exact_schema_and_semantics(self):
        fixture = _fixture()
        review = fixture["review_inputs"].documentation_review.to_mapping()
        review["unexpected_field"] = 0
        with self.assertRaises(R2ExternalArtifactError):
            _require_source_review_mapping_v1(
                ClosureGate.DOCUMENTATION, review, fixture["binding"]
            )

        portable = fixture["ci_receipts"][0].to_mapping()
        portable["portable_full_suite"] = 0
        body = {key: value for key, value in portable.items() if key != "receipt_fingerprint"}
        portable["receipt_fingerprint"] = fingerprint(
            "r2-ci-provenance-receipt-v2", body
        )
        with self.assertRaises(R2ExternalArtifactError):
            _serialized_direct_fingerprint(
                ClosureGate.PORTABLE_FULL_SUITE,
                portable,
                fixture["binding"],
                fixture["production_binding"],
            )

        review = fixture["review_inputs"].documentation_review.to_mapping()
        review["open_finding_count"] = False
        body = {key: value for key, value in review.items() if key != "review_fingerprint"}
        review["review_fingerprint"] = fingerprint(
            "r2-gate-source-review-v1", body
        )
        with self.assertRaises(R2ExternalArtifactError):
            _require_source_review_mapping_v1(
                ClosureGate.DOCUMENTATION, review, fixture["binding"]
            )

    def test_package_integrity_binds_the_exact_provenance_manifest(self):
        fixture = _fixture()
        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )
        manifest = strict_json_object(package.issuance_manifest_json)
        manifest["provenance_records"][0]["fingerprint"] = "0" * 64
        object.__setattr__(package, "issuance_manifest_json", canonical_json(manifest))
        with self.assertRaises(R2ExternalArtifactError):
            _require_package_integrity_v1(package)

        package = prepare_unsigned_external_artifacts_v1(
            frozen_master=fixture["frozen"],
            authority_verification_public_keys=fixture["authority_keys"],
            review_inputs=fixture["review_inputs"],
        )
        object.__setattr__(package, "artifact_count", 15.0)
        mapping = package.to_mapping()
        mapping.pop("package_fingerprint")
        object.__setattr__(package, "package_fingerprint", fingerprint(
            "r2-unsigned-external-artifact-package-v1", mapping
        ))
        with self.assertRaises(R2ExternalArtifactError):
            _require_package_integrity_v1(package)

    def test_validated_file_publication_is_atomic_no_clobber(self):
        manifest = "1" * 64
        files = _fixed_install_files()
        with _temporary_directory(prefix="issue105-publication-") as raw:
            common = Path(raw).resolve(strict=True)
            _publish_validated_files_v1(common, manifest, files)
            target = common / "r2-final-master-closure-v1"
            self.assertEqual(
                tuple(sorted(item.name for item in target.iterdir())),
                tuple(sorted(name for name, _payload in files)),
            )
            self.assertEqual(
                tuple((item.name, item.read_bytes()) for item in sorted(target.iterdir())),
                tuple(sorted(files)),
            )
            before = tuple((item.name, item.read_bytes()) for item in sorted(target.iterdir()))
            with self.assertRaises(R2ExternalArtifactError):
                _publish_validated_files_v1(common, manifest, files)
            self.assertEqual(
                tuple((item.name, item.read_bytes()) for item in sorted(target.iterdir())),
                before,
            )

    @unittest.skipUnless(os.name == "nt", "Windows file-ID commit provenance")
    def test_file_id_guards_cover_exact_children_on_calling_thread(self):
        manifest, files = "6" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-file-id-proof-") as raw:
            common = Path(raw).resolve(strict=True)
            caller = threading.get_native_id()
            captured = {"rename_threads": []}
            from backend.r2_external_artifacts_v1 import installer
            open_guards = installer._open_file_id_guards
            rename = installer._rename_no_replace

            def capture_guards(*arguments):
                captured["guards"] = open_guards(*arguments)
                return captured["guards"]

            def capture_rename(*arguments):
                captured["rename_threads"].append(threading.get_native_id())
                self.assertEqual(
                    tuple(guard[2] for guard in captured["guards"][:-1]),
                    tuple(name for name, _payload in files),
                )
                self.assertIsNone(captured["guards"][-1][2])
                self.assertTrue(all(guard[0] is not None for guard in captured["guards"]))
                result = rename(*arguments)
                self.assertTrue(
                    all(_wait_for_handle(guard[1], 0) == 258 for guard in captured["guards"])
                )
                return result

            with patch.object(
                installer, "_open_file_id_guards", side_effect=capture_guards
            ), patch.object(
                installer, "_rename_no_replace", side_effect=capture_rename
            ):
                _publish_validated_files_v1(common, manifest, files)

            self.assertEqual(captured["rename_threads"], [caller])
            self.assertEqual(len(captured["guards"]), len(files) + 1)
            self.assertTrue(all(guard[0] is None for guard in captured["guards"]))
            self.assertTrue(all(guard[1] is None for guard in captured["guards"]))

    @unittest.skipUnless(os.name == "nt", "Windows equivalent commit race")
    def test_equivalent_competing_rename_is_normalized_to_success(self):
        manifest, files = "9" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-equivalent-race-") as raw:
            common = Path(raw).resolve(strict=True)
            target = common / "r2-final-master-closure-v1"

            def commit_first(*arguments):
                _rename_no_replace(*arguments)
                return _rename_no_replace(*arguments)

            with patch(
                "backend.r2_external_artifacts_v1.installer._rename_no_replace",
                side_effect=commit_first,
            ):
                _publish_validated_files_v1(common, manifest, files)
            self.assertTrue(target.is_dir())
            self.assertEqual(
                tuple((item.name, item.read_bytes()) for item in sorted(target.iterdir())),
                tuple(sorted(files)),
            )

    @unittest.skipUnless(os.name == "nt", "Windows requiring-oplock ordering")
    def test_requiring_oplock_open_is_immediately_followed_by_request(self):
        files, calls = _fixed_install_files(), []
        with _temporary_directory(prefix="issue105-oplock-order-") as raw:
            stage = Path(raw).resolve(strict=True) / "stage"
            stage.mkdir()
            for name, payload in files:
                (stage / name).write_bytes(payload)
            from backend.r2_external_artifacts_v1 import installer
            next_handle = iter(range(100, 100 + len(files)))
            identities = {500: installer._identity(os.lstat(stage))[:2]}

            def open_path(path, _access, _share, _flags):
                if str(path).startswith("\\\\.\\"):
                    return 50
                calls.append(("open", 500))
                return 500

            def open_child(_volume, file_id):
                handle = next(next_handle)
                identities[handle] = (os.lstat(stage).st_dev, file_id)
                calls.append(("open", handle))
                return handle

            def request(handle, level):
                calls.append(("oplock", handle, level))
                return handle + 1_000, object(), object(), object(), object(), object()

            with patch.object(installer, "_windows_open", side_effect=open_path), patch.object(
                installer, "_windows_open_by_id", side_effect=open_child
            ), patch.object(installer, "_request_oplock", side_effect=request), patch.object(
                installer, "_handle_file_id", side_effect=lambda handle, _single=False: identities[handle]
            ), patch.object(installer, "_guarded_streams", return_value=(("::$DATA", 2),)), patch.object(
                installer, "_guarded_bytes_equal", return_value=True
            ), patch.object(
                installer, "_lock_guard_acls"
            ), patch.object(installer, "_require_guarded_files"), patch.object(
                installer, "_require_guarded_commit"
            ), patch.object(installer, "_cancel_overlapped"), patch.object(
                installer, "_close_windows_handle"
            ):
                guards = installer._open_file_id_guards(stage, files)
                installer._close_file_id_guards(guards)

            self.assertEqual(len(calls), 2 * (len(files) + 1))
            for index in range(0, len(calls), 2):
                self.assertEqual(calls[index][0], "open")
                self.assertEqual(calls[index + 1][:2], ("oplock", calls[index][1]))

    @unittest.skipUnless(os.name == "nt", "Windows alternate-stream rejection")
    def test_file_and_directory_alternate_streams_fail_before_publication(self):
        files = _fixed_install_files()
        for location in ("file", "directory"):
            with self.subTest(location=location), _temporary_directory(
                prefix=f"issue105-ads-{location}-"
            ) as raw:
                stage = Path(raw).resolve(strict=True) / "stage"
                stage.mkdir()
                for name, payload in files:
                    (stage / name).write_bytes(payload)
                owner = stage / files[0][0] if location == "file" else stage
                Path(f"{owner}:unreviewed").write_bytes(b"UNREVIEWED")
                guards = ()
                try:
                    with self.assertRaises(R2ExternalArtifactError):
                        guards = _open_file_id_guards(stage, files)
                finally:
                    _close_file_id_guards(guards)

    @unittest.skipUnless(os.name == "nt", "Windows single-link handle invariant")
    def test_hardlink_added_during_file_id_open_fails_closed(self):
        files = _fixed_install_files()
        with _temporary_directory(prefix="issue105-hardlink-race-") as raw:
            common = Path(raw).resolve(strict=True)
            stage, alias = common / "stage", common / "alias.json"
            stage.mkdir()
            for name, payload in files:
                (stage / name).write_bytes(payload)
            from backend.r2_external_artifacts_v1 import installer
            original_open = installer._windows_open_by_id
            injected = []

            def add_link_before_open(*arguments):
                if not injected:
                    os.link(stage / files[0][0], alias)
                    injected.append(True)
                return original_open(*arguments)

            guards = ()
            try:
                with patch.object(
                    installer, "_windows_open_by_id", side_effect=add_link_before_open
                ), self.assertRaises(R2ExternalArtifactError):
                    guards = _open_file_id_guards(stage, files)
            finally:
                _close_file_id_guards(guards)
            self.assertEqual(injected, [True])
            self.assertTrue(alias.exists())

    @unittest.skipUnless(os.name == "nt", "Windows file-ID commit guard")
    def test_file_id_oplocks_block_child_write_and_namespace_insertion(self):
        manifest, files = "a" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-file-id-guard-") as raw:
            common = Path(raw).resolve(strict=True)
            stage = common / f".r2-final-master-closure-v1.stage-{manifest}"
            stage.mkdir()
            for name, payload in files:
                (stage / name).write_bytes(payload)
            guards = _open_file_id_guards(stage, files)
            completed, errors = [], []

            def write_child():
                try:
                    (stage / files[0][0]).write_bytes(b"changed")
                    completed.append("write")
                except Exception as error:
                    errors.append(type(error))

            def add_child():
                try:
                    (stage / "unexpected.json").write_bytes(b"unexpected")
                    completed.append("add")
                except Exception as error:
                    errors.append(type(error))

            workers = [
                threading.Thread(target=write_child, daemon=True),
                threading.Thread(target=add_child, daemon=True),
            ]
            try:
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(2)
                    self.assertFalse(worker.is_alive())
            finally:
                _close_file_id_guards(guards)
            self.assertEqual(completed, [])
            self.assertEqual(errors, [PermissionError, PermissionError])

    @unittest.skipUnless(os.name == "nt", "Windows POSIX mutation guard")
    def test_file_id_oplocks_block_posix_unlink_and_replacement(self):
        files = _fixed_install_files()
        for operation in ("unlink", "replace"):
            with self.subTest(operation=operation), _temporary_directory(
                prefix=f"issue105-posix-{operation}-"
            ) as raw:
                common = Path(raw).resolve(strict=True)
                stage = common / "stage"
                stage.mkdir()
                for name, payload in files:
                    (stage / name).write_bytes(payload)
                child = stage / files[0][0]
                replacement = common / "replacement.json"
                replacement.write_bytes(b"replacement")
                guards = _open_file_id_guards(stage, files)
                errors = []

                def mutate():
                    try:
                        if operation == "unlink":
                            child.unlink()
                        else:
                            os.replace(replacement, child)
                    except Exception as error:
                        errors.append(type(error))

                worker = threading.Thread(target=mutate, daemon=True)
                try:
                    worker.start()
                    worker.join(2)
                    self.assertFalse(worker.is_alive())
                finally:
                    _close_file_id_guards(guards)
                self.assertEqual(errors, [PermissionError])

    @unittest.skipUnless(os.name == "nt", "Windows precommit mutation guard")
    def test_post_guard_namespace_mutation_is_denied_before_native_commit(self):
        manifest, files = "b" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-precommit-race-") as raw:
            common = Path(raw).resolve(strict=True)
            stage = common / f".r2-final-master-closure-v1.stage-{manifest}"
            target = common / "r2-final-master-closure-v1"
            workers, errors = [], []
            original_open = _open_file_id_guards

            def signal_before_return(directory, expected_files):
                guards = original_open(directory, expected_files)
                def mutate():
                    try:
                        (directory / "unexpected.json").write_bytes(b"x")
                    except Exception as error:
                        errors.append(type(error))
                worker = threading.Thread(
                    target=mutate,
                    daemon=True,
                )
                workers.append(worker)
                worker.start()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                return guards

            with patch(
                "backend.r2_external_artifacts_v1.installer._open_file_id_guards",
                side_effect=signal_before_return,
            ):
                _publish_validated_files_v1(common, manifest, files)
            self.assertEqual(errors, [PermissionError])
            self.assertTrue(target.is_dir())
            self.assertFalse(stage.exists())

    @unittest.skipUnless(os.name == "nt", "Windows immutable commit boundary")
    def test_mutations_after_quiet_check_cannot_poison_commit(self):
        manifest, files = "c" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-post-quiet-") as raw:
            common = Path(raw).resolve(strict=True)
            stage = common / f".r2-final-master-closure-v1.stage-{manifest}"
            target = common / "r2-final-master-closure-v1"
            replacement = common / "replacement.json"
            replacement.write_bytes(b"replacement")
            captured, errors, workers = {}, [], []
            from backend.r2_external_artifacts_v1 import installer
            original_open = installer._open_file_id_guards
            original_rename = installer._rename_no_replace

            def capture_guards(*arguments):
                captured["guards"] = original_open(*arguments)
                return captured["guards"]

            def mutate(operation):
                try:
                    operation()
                except Exception as error:
                    errors.append(type(error))

            def race_after_quiet(*arguments):
                operations = (
                    lambda: os.replace(replacement, stage / files[0][0]),
                    lambda: (stage / "unexpected.json").write_bytes(b"x"),
                )
                workers.extend(
                    threading.Thread(target=mutate, args=(operation,), daemon=True)
                    for operation in operations
                )
                for worker in workers:
                    worker.start()
                for worker in workers:
                    worker.join(2)
                    self.assertFalse(worker.is_alive())
                return original_rename(*arguments)

            with patch.object(
                installer, "_open_file_id_guards", side_effect=capture_guards
            ), patch.object(
                installer, "_rename_no_replace", side_effect=race_after_quiet
            ):
                _publish_validated_files_v1(common, manifest, files)
            for worker in workers:
                worker.join(2)
                self.assertFalse(worker.is_alive())
            self.assertEqual(errors, [PermissionError, PermissionError])
            self.assertEqual(
                tuple((item.name, item.read_bytes()) for item in sorted(target.iterdir())),
                tuple(sorted(files)),
            )

    @unittest.skipUnless(os.name == "nt", "Windows immutable release boundary")
    def test_mutation_after_target_validation_cannot_poison_release(self):
        manifest, files = "d" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-pre-release-") as raw:
            common = Path(raw).resolve(strict=True)
            target = common / "r2-final-master-closure-v1"
            captured, errors = {}, []
            from backend.r2_external_artifacts_v1 import installer
            original_open = installer._open_file_id_guards
            original_require = installer._require_guarded_files

            def capture_guards(*arguments):
                captured["guards"] = original_open(*arguments)
                return captured["guards"]

            def mutate():
                try:
                    (target / "unexpected.json").write_bytes(b"x")
                except Exception as error:
                    errors.append(type(error))

            def race_before_release(*arguments, **keywords):
                result = original_require(*arguments, **keywords)
                if arguments[0] == target and "worker" not in captured:
                    captured["worker"] = threading.Thread(target=mutate, daemon=True)
                    captured["worker"].start()
                    captured["worker"].join(2)
                    self.assertFalse(captured["worker"].is_alive())
                return result

            with patch.object(
                installer, "_open_file_id_guards", side_effect=capture_guards
            ), patch.object(
                installer, "_require_guarded_files", side_effect=race_before_release
            ):
                _publish_validated_files_v1(common, manifest, files)
            captured["worker"].join(2)
            self.assertFalse(captured["worker"].is_alive())
            self.assertEqual(errors, [PermissionError])
            self.assertEqual(
                tuple((item.name, item.read_bytes()) for item in sorted(target.iterdir())),
                tuple(sorted(files)),
            )

    @unittest.skipUnless(os.name == "nt", "Windows fixed-target name boundary")
    def test_target_rename_after_validation_is_denied_before_release(self):
        manifest, files = "f" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-target-name-release-") as raw:
            common = Path(raw).resolve(strict=True)
            target = common / "r2-final-master-closure-v1"
            moved = common / "moved"
            errors, captured = [], {}
            from backend.r2_external_artifacts_v1 import installer
            original_require = installer._require_guarded_files

            def rename_target():
                try:
                    target.rename(moved)
                except Exception as error:
                    errors.append(type(error))

            def race_before_release(*arguments, **keywords):
                result = original_require(*arguments, **keywords)
                if arguments[0] == target and "worker" not in captured:
                    captured["worker"] = threading.Thread(target=rename_target, daemon=True)
                    captured["worker"].start()
                    captured["worker"].join(2)
                    self.assertFalse(captured["worker"].is_alive())
                return result

            with patch.object(
                installer, "_require_guarded_files", side_effect=race_before_release
            ):
                _publish_validated_files_v1(common, manifest, files)
            self.assertEqual(errors, [PermissionError])
            self.assertTrue(target.is_dir())
            self.assertFalse(moved.exists())

    @unittest.skipUnless(os.name == "nt", "Windows stage identity binding")
    def test_stage_name_swap_is_rejected_before_native_commit(self):
        manifest, files = "7" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-stage-swap-") as raw:
            common = Path(raw).resolve(strict=True)
            stage = common / f".r2-final-master-closure-v1.stage-{manifest}"
            target = common / "r2-final-master-closure-v1"
            original_open = _open_file_id_guards

            def swap_before_guard(directory, expected_files):
                retained = directory.with_name(f"{directory.name}.retained")
                directory.rename(retained)
                directory.mkdir()
                for name, payload in expected_files:
                    (directory / name).write_bytes(payload)
                return original_open(directory, expected_files)

            with patch(
                "backend.r2_external_artifacts_v1.installer._open_file_id_guards",
                side_effect=swap_before_guard,
            ), self.assertRaises(R2ExternalArtifactError):
                _publish_validated_files_v1(common, manifest, files)
            self.assertFalse(target.exists())
            self.assertTrue(stage.is_dir())
            self.assertTrue(stage.with_name(f"{stage.name}.retained").is_dir())

    @unittest.skipUnless(os.name == "nt", "Windows directory-handle identity binding")
    def test_directory_handle_name_swap_cannot_publish_wrong_identity(self):
        manifest, files = "e" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-directory-handle-swap-") as raw:
            common = Path(raw).resolve(strict=True)
            stage = common / f".r2-final-master-closure-v1.stage-{manifest}"
            target = common / "r2-final-master-closure-v1"
            retained = stage.with_name(f"{stage.name}.retained")
            replacement = stage.with_name(f"{stage.name}.replacement")
            from backend.r2_external_artifacts_v1 import installer
            original_open = installer._windows_open

            def swap_during_directory_open(path, access, share, flags):
                if Path(path) != stage or access != 0x80050000:
                    return original_open(path, access, share, flags)
                stage.rename(retained)
                stage.mkdir()
                for index, (name, payload) in enumerate(files):
                    (stage / name).write_bytes(b"MALICIOUS" if index == 0 else payload)
                return original_open(stage, access, share, flags)

            with patch.object(
                installer, "_windows_open", side_effect=swap_during_directory_open
            ), self.assertRaises(R2ExternalArtifactError):
                _publish_validated_files_v1(common, manifest, files)
            self.assertFalse(target.exists())
            self.assertEqual((retained / files[0][0]).read_bytes(), files[0][1])
            self.assertEqual((stage / files[0][0]).read_bytes(), b"MALICIOUS")
            self.assertFalse(replacement.exists())

    @unittest.skipUnless(os.name == "nt", "Windows file-ID guard cleanup")
    def test_file_id_open_failure_closes_every_prior_guard(self):
        manifest, files = "8" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-guard-failure-") as raw:
            common = Path(raw).resolve(strict=True)
            opened, events, closed = [], [], []
            from backend.r2_external_artifacts_v1 import installer
            original_open = installer._windows_open_by_id
            original_request = installer._request_oplock
            original_close = installer._close_windows_handle

            def fail_second(*arguments):
                if opened:
                    raise R2ExternalArtifactError()
                handle = original_open(*arguments)
                opened.append(handle)
                return handle

            def capture_event(*arguments):
                result = original_request(*arguments)
                events.append(result[0])
                return result

            def track_close(handle):
                if handle in (*opened, *events):
                    closed.append(handle)
                return original_close(handle)

            with patch.object(
                installer, "_windows_open_by_id", side_effect=fail_second
            ), patch.object(
                installer, "_request_oplock", side_effect=capture_event
            ), patch.object(
                installer, "_close_windows_handle", side_effect=track_close
            ), self.assertRaises(R2ExternalArtifactError):
                _publish_validated_files_v1(common, manifest, files)
            self.assertEqual(len(opened), 1)
            self.assertEqual(len(events), 1)
            self.assertEqual(closed.count(opened[0]), 1)
            self.assertEqual(closed.count(events[0]), 1)
            self.assertFalse((common / "r2-final-master-closure-v1").exists())

    @unittest.skipUnless(os.name == "nt", "Windows oplock event cleanup")
    def test_oplock_api_lookup_failure_closes_created_event(self):
        from backend.r2_external_artifacts_v1 import installer
        event, closed = 987_654, []

        def api(name, *_arguments, **_keywords):
            if name == "CreateEventW":
                return lambda *_args: event
            if name == "CloseHandle":
                return lambda handle: closed.append(handle) or 1
            raise RuntimeError("synthetic API lookup failure")

        with patch.object(installer, "_windows_api", side_effect=api), self.assertRaises(
            R2ExternalArtifactError
        ):
            installer._request_oplock(123, 7)
        self.assertEqual(closed, [event])

    @unittest.skipUnless(os.name == "nt", "Windows pending oplock rejection cleanup")
    def test_pending_oplock_rejection_cancels_and_reaps_before_event_close(self):
        from backend.r2_external_artifacts_v1 import installer

        for wait_result in (0, RuntimeError("synthetic wait failure")):
            with self.subTest(wait_result=repr(wait_result)):
                event, calls, request_overlapped = 987_656, [], []

                def api(name, *_arguments, **_keywords):
                    if name == "CreateEventW":
                        return lambda *_args: event
                    if name == "DeviceIoControl":
                        def request(*args):
                            request_overlapped.append(args[-1]._obj)
                            ctypes.set_last_error(installer._ERROR_IO_PENDING)
                            calls.append("request")
                            return 0
                        return request
                    if name == "WaitForSingleObject":
                        def wait(*_args):
                            calls.append("wait")
                            if isinstance(wait_result, Exception):
                                raise wait_result
                            return wait_result
                        return wait
                    if name == "CancelIoEx":
                        return lambda handle, value: calls.append(
                            ("cancel", handle, value._obj is request_overlapped[0])
                        ) or 0
                    if name == "GetOverlappedResult":
                        return lambda handle, value, _count, blocking: calls.append(
                            (
                                "reap",
                                handle,
                                value._obj is request_overlapped[0],
                                blocking,
                            )
                        ) or 0
                    if name == "CloseHandle":
                        return lambda handle: calls.append(("close", handle)) or 1
                    raise AssertionError(name)

                with patch.object(
                    installer, "_windows_api", side_effect=api
                ), self.assertRaises(R2ExternalArtifactError):
                    installer._request_oplock(123, 7)
                self.assertEqual(
                    calls,
                    [
                        "request",
                        "wait",
                        ("cancel", 123, True),
                        ("reap", 123, True, 1),
                        ("close", event),
                    ],
                )

    @unittest.skipUnless(os.name == "nt", "Windows read event cleanup")
    def test_guarded_read_api_lookup_failure_closes_created_event(self):
        from backend.r2_external_artifacts_v1 import installer
        event, closed = 987_655, []

        def query(_handle, size):
            size._obj.value = 1
            return 1

        def api(name, *_arguments, **_keywords):
            if name == "GetFileSizeEx":
                return query
            if name == "CreateEventW":
                return lambda *_args: event
            if name == "CloseHandle":
                return lambda handle: closed.append(handle) or 1
            raise RuntimeError("synthetic API lookup failure")

        with patch.object(installer, "_windows_api", side_effect=api), self.assertRaises(
            RuntimeError
        ):
            installer._guarded_bytes_equal(123, b"x")
        self.assertEqual(closed, [event])

    @unittest.skipUnless(os.name == "nt", "Windows pending oplock cleanup")
    def test_guard_cleanup_cancels_and_reaps_pending_oplock_before_close(self):
        from backend.r2_external_artifacts_v1 import installer
        overlapped, calls = installer._Overlapped(), []

        def cancel(handle, value):
            calls.append(("cancel", handle, value._obj is overlapped))
            return 0

        def reap(handle, value, _count, blocking):
            calls.append(("reap", handle, value._obj is overlapped, blocking))
            return 0

        guard = [
            123,
            456,
            "name",
            (1, 2, 3),
            object(),
            object(),
            overlapped,
            cancel,
            reap,
        ]
        def close(handle):
            calls.append(("close", handle))

        with patch.object(
            installer,
            "_windows_api",
            side_effect=AssertionError("cleanup must use prebound APIs"),
        ), patch.object(installer, "_close_windows_handle", side_effect=close):
            installer._close_file_id_guards([guard])
        self.assertEqual(
            calls,
            [
                ("cancel", 123, True),
                ("reap", 123, True, 1),
                ("close", 123),
                ("close", 456),
            ],
        )
        self.assertIsNone(guard[0])
        self.assertIsNone(guard[1])

    def test_failed_commit_retains_stage_and_never_exposes_partial_target(self):
        manifest = "2" * 64
        files = _fixed_install_files()
        with _temporary_directory(prefix="issue105-failed-publication-") as raw:
            common = Path(raw).resolve(strict=True)
            with patch(
                "backend.r2_external_artifacts_v1.installer._rename_no_replace",
                side_effect=R2ExternalArtifactError(),
            ), self.assertRaises(R2ExternalArtifactError):
                _publish_validated_files_v1(common, manifest, files)
            target = common / "r2-final-master-closure-v1"
            stage = common / f".r2-final-master-closure-v1.stage-{manifest}"
            self.assertFalse(target.exists())
            self.assertTrue(stage.is_dir())
            self.assertEqual(
                tuple((item.name, item.read_bytes()) for item in sorted(stage.iterdir())),
                tuple(sorted(files)),
            )

    def test_fresh_master_guard_rejects_remote_move_and_commit_race(self):
        source = _fixture()["frozen"].to_mapping()
        moved = dict(source)
        moved["remote_ref_fingerprint"] = "9" * 64
        class _Moved:
            def to_mapping(self):
                return moved
        with patch(
            "backend.r2_external_artifacts_v1.installer._current_frozen_master_v1",
            return_value=_Moved(),
        ), self.assertRaises(R2ExternalArtifactError):
            _require_fresh_master_v1(source)

        manifest, files = "3" * 64, _fixed_install_files()
        with _temporary_directory(prefix="issue105-freshness-race-") as raw:
            common = Path(raw).resolve(strict=True)
            with patch(
                "backend.r2_external_artifacts_v1.installer._require_fresh_master_v1",
                side_effect=(None, R2ExternalArtifactError()),
            ), patch(
                "backend.r2_external_artifacts_v1.installer._rename_no_replace"
            ) as rename, self.assertRaises(R2ExternalArtifactError):
                _publish_validated_files_v1(
                    common, manifest, files, fresh_master_source=source
                )
            rename.assert_not_called()
            self.assertFalse((common / "r2-final-master-closure-v1").exists())
            self.assertTrue(
                (common / f".r2-final-master-closure-v1.stage-{manifest}").is_dir()
            )


def _fixture():
    binding = _binding()
    frozen = _frozen(binding)
    authority_keys = {
        role: bytes([index + 41]) * 32
        for index, role in enumerate(PublicKeyRoleV2)
    }
    production_binding = build_production_binding_candidate_v1(
        final_master_binding=binding,
        verification_public_keys=authority_keys,
    )
    git_receipt = _git_receipt(binding, production_binding)
    ci_receipts = _ci_receipts(binding)
    ci_bundle = _ci_bundle(binding, ci_receipts)
    retention_proof = _retention_proof(production_binding)
    runbook_receipt = _runbook_receipt(production_binding, retention_proof)
    reviews = {
        ClosureGate.CLOSURE_SURFACE_COMPLETENESS: _source_review(
            ClosureGate.CLOSURE_SURFACE_COMPLETENESS,
            binding,
            {
                "closure_map": binding.closure_map_fingerprint,
                "spec_coverage_review": "1" * 64,
            },
        ),
        ClosureGate.CRASH_RECOVERY: _source_review(
            ClosureGate.CRASH_RECOVERY,
            binding,
            {
                "rollback_plan": "2" * 64,
                "legacy_restoration_evidence": "3" * 64,
                "crash_matrix": "4" * 64,
                "fresh_process_suite": "5" * 64,
            },
        ),
        ClosureGate.DOCUMENTATION: _source_review(
            ClosureGate.DOCUMENTATION,
            binding,
            {
                "documentation_review": "6" * 64,
                "generated_status": "7" * 64,
            },
        ),
        ClosureGate.MECHANICAL_ARCHITECTURE: _source_review(
            ClosureGate.MECHANICAL_ARCHITECTURE,
            binding,
            {
                "standards_review": "8" * 64,
                "architecture_guard_run": "9" * 64,
                "mechanical_guard_run": "a" * 64,
                "static_guard_run": "b" * 64,
            },
        ),
        ClosureGate.LEAKAGE: _source_review(
            ClosureGate.LEAKAGE,
            binding,
            {
                "repository_leakage_scan": "c" * 64,
                "ci_leakage_reconciliation": "d" * 64,
            },
        ),
        ClosureGate.MAINTENANCE_SCOPE: _source_review(
            ClosureGate.MAINTENANCE_SCOPE,
            binding,
            {"maintenance_scan_output": "e" * 64},
            classified_nonblocking_finding_fingerprints=("f" * 64,),
        ),
    }
    review_inputs = R2ExternalArtifactReviewInputsV1.create(
        production_binding=production_binding,
        closure_surface_review=reviews[
            ClosureGate.CLOSURE_SURFACE_COMPLETENESS
        ],
        git_byte_receipt=git_receipt,
        ci_provenance_bundle=ci_bundle,
        ci_provenance_receipts=ci_receipts,
        runbook_receipt=runbook_receipt,
        crash_recovery_review=reviews[ClosureGate.CRASH_RECOVERY],
        retention_proof=retention_proof,
        documentation_review=reviews[ClosureGate.DOCUMENTATION],
        mechanical_architecture_review=reviews[
            ClosureGate.MECHANICAL_ARCHITECTURE
        ],
        leakage_review=reviews[ClosureGate.LEAKAGE],
        maintenance_review=reviews[ClosureGate.MAINTENANCE_SCOPE],
    )
    return {
        "binding": binding,
        "frozen": frozen,
        "authority_keys": authority_keys,
        "production_binding": production_binding,
        "git_receipt": git_receipt,
        "ci_receipts": ci_receipts,
        "ci_bundle": ci_bundle,
        "retention_proof": retention_proof,
        "runbook_receipt": runbook_receipt,
        "review_inputs": review_inputs,
    }


def _replace_review_inputs(inputs, **changes):
    values = {
        name: getattr(inputs, name)
        for name in R2ExternalArtifactReviewInputsV1.__dataclass_fields__
    }
    values.update(changes)
    return R2ExternalArtifactReviewInputsV1.create(**values)


def _refingerprint_package(mapping, index):
    record = mapping["supporting_provenance_records"][index]
    record_body = {
        key: value for key, value in record.items()
        if key != "provenance_fingerprint"
    }
    record["provenance_fingerprint"] = fingerprint(
        "r2-gate-derivation-provenance-v1", record_body
    )
    artifact = mapping["unsigned_gate_artifacts"][index]
    artifact["evidence_fingerprint"] = record["evidence_fingerprint"]
    artifact["unsigned_body"]["evidence_fingerprint"] = record[
        "evidence_fingerprint"
    ]
    artifact["body_sha256"] = hashlib.sha256(
        canonical_json(artifact["unsigned_body"])
    ).hexdigest()
    manifest = mapping["issuance_manifest"]
    manifest["files"][index + 1]["sha256"] = artifact["body_sha256"]
    manifest["provenance_records"][index]["fingerprint"] = record[
        "provenance_fingerprint"
    ]
    manifest_body = dict(manifest)
    manifest_body.pop("issuance_manifest_fingerprint")
    manifest_fingerprint = fingerprint(
        "r2-external-artifact-issuance-manifest-v1", manifest_body
    )
    manifest["issuance_manifest_fingerprint"] = manifest_fingerprint
    mapping["issuance_manifest_fingerprint"] = manifest_fingerprint
    package_body = dict(mapping)
    package_body.pop("package_fingerprint")
    mapping["package_fingerprint"] = fingerprint(
        "r2-unsigned-external-artifact-package-v1", package_body
    )


def _binding():
    return FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


def _frozen(binding):
    return _allocate_frozen(
        binding,
        {
            "observation_type": "R2FrozenRemoteMasterV1",
            "status": "FROZEN_REMOTE_MASTER_VERIFIED",
            "binding_fingerprint": binding.binding_fingerprint,
            "remote_ref_fingerprint": "0" * 64,
            "final_commit_oid": binding.final_commit_oid,
            "final_tree_oid": binding.final_tree_oid,
            "source_package_fingerprint": binding.source_package_fingerprint,
            "runbook_fingerprint": binding.runbook_fingerprint,
            "workflow_fingerprint": binding.workflow_fingerprint,
            "exact_match": 1,
            "historical_master_count": 0,
            "dirty_path_count": 0,
        },
    )


def _source_review(
    gate,
    binding,
    sources,
    classified_nonblocking_finding_fingerprints=(),
):
    return R2GateSourceReviewV1.create(
        gate=gate,
        final_master_binding=binding,
        source_fingerprints=sources,
        classified_nonblocking_finding_fingerprints=(
            classified_nonblocking_finding_fingerprints
        ),
    )


def _git_receipt(binding, production_binding):
    body = {
        "receipt_type": "R2GitByteStateReceiptV1",
        "status": "GIT_BYTE_STATE_VERIFIED",
        "binding_fingerprint": production_binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "repository_identity_fingerprint": "1" * 64,
        "selected_byte_state_fingerprint": "2" * 64,
        "local_ref_state_fingerprint": "3" * 64,
        "stable_common_state_fingerprint": "4" * 64,
        "original_worktree_state_fingerprint": "5" * 64,
        "reconstructed_worktree_state_fingerprint": "6" * 64,
        "snapshot_fingerprint": "7" * 64,
        "selected_byte_count": 100,
        "local_ref_count": 14,
        "stable_common_state_role_count": 5,
        "original_worktree_count": 11,
        "reconstructed_worktree_count": 11,
        "worktree_count": 11,
        "ignored_content_reads": 0,
        "private_content_reads": 0,
    }
    return _allocate(
        R2GitByteStateReceiptV1,
        body,
        "receipt_fingerprint",
        "r2-git-byte-state-receipt-v1",
    )


def _ci_receipts(binding):
    result = []
    for index, kind in enumerate(CiProvenanceKindV2, start=1):
        body = {
            "receipt_type": "R2CiProvenanceReceiptV2",
            "status": "CI_PROVENANCE_VERIFIED",
            "provenance_kind": kind.value,
            "final_commit_oid": binding.final_commit_oid,
            "final_tree_oid": binding.final_tree_oid,
            "source_package_fingerprint": binding.source_package_fingerprint,
            "selected_entry_count": 300,
            "selected_byte_count": 1000,
            "workflow_lock_fingerprint": binding.workflow_fingerprint,
            "dependency_lock_fingerprint": "8" * 64,
            "platform_lock_fingerprint": f"{9 if kind is CiProvenanceKindV2.PORTABLE else 10:064x}",
            "runbook_fingerprint": binding.runbook_fingerprint,
            "suite_fingerprint": fixed_suite_fingerprint_v2(kind),
            "runner_fingerprint": f"{index + 30:064x}",
            "installed_dependency_fingerprint": f"{index + 40:064x}",
            "hash_locked_dependency_count": 31,
            "wheel_hash_count": 31,
            "portable_full_suite": int(kind is CiProvenanceKindV2.PORTABLE),
            "historical_package_count": 0,
            "required_skip_count": 0,
            "platform_divergence_count": 0,
            "leakage_finding_count": 0,
            "failure_count": 0,
            "private_content_reads": 0,
            "worktree_content_reads": 0,
        }
        result.append(
            _allocate(
                R2CiProvenanceReceiptV2,
                body,
                "receipt_fingerprint",
                "r2-ci-provenance-receipt-v2",
                {
                    "status": CiProvenanceStatusV2,
                    "provenance_kind": CiProvenanceKindV2,
                },
            )
        )
    return tuple(sorted(result, key=lambda item: item.provenance_kind.value))


def _ci_bundle(binding, receipts):
    receipt_set = fingerprint(
        "r2-ci-provenance-receipt-set-v2",
        [item.receipt_fingerprint for item in receipts],
    )
    body = {
        "bundle_type": "R2CiProvenanceBundleV2",
        "status": "CI_PROVENANCE_RECONCILED",
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "workflow_lock_fingerprint": binding.workflow_fingerprint,
        "dependency_lock_fingerprint": "8" * 64,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "provenance_receipt_count": 3,
        "historical_package_count": 0,
        "required_skip_count": 0,
        "platform_divergence_count": 0,
        "leakage_finding_count": 0,
        "failure_count": 0,
        "runner_fingerprint_count": 3,
        "hash_locked_dependency_count": 31,
        "wheel_hash_count": 62,
        "portable_full_suite_receipt_count": 1,
        "receipt_set_fingerprint": receipt_set,
    }
    return _allocate(
        R2CiProvenanceBundleV2,
        body,
        "bundle_fingerprint",
        "r2-ci-provenance-bundle-v2",
        {"status": CiProvenanceStatusV2},
    )


def _retention_proof(production_binding):
    body = {
        "proof_type": "R2RetentionProofV2",
        "binding_fingerprint": production_binding.binding_fingerprint,
        "ledger_fingerprint": "1" * 64,
        "journal_head_fingerprint": "2" * 64,
        "reconciled_entry_count": 80,
        "untracked_artifact_count": 0,
        "deletion_capability_count": 0,
        "overwrite_capability_count": 0,
        "prune_capability_count": 0,
        "automatic_expiry_capability_count": 0,
        "private_payload_field_count": 0,
    }
    return _allocate(
        R2RetentionProofV2,
        body,
        "proof_fingerprint",
        "r2-retention-proof-v2",
    )


def _runbook_receipt(production_binding, retention):
    body = {
        "receipt_type": "R2OperatorRunbookReceiptV2",
        "status": "RUNBOOK_SEMANTICS_VERIFIED",
        "binding_fingerprint": production_binding.binding_fingerprint,
        "final_commit_oid": production_binding.final_commit_oid,
        "final_tree_oid": production_binding.final_tree_oid,
        "source_package_fingerprint": production_binding.source_package_fingerprint,
        "runbook_fingerprint": production_binding.runbook_fingerprint,
        "package_semantics_fingerprint": operator_package_semantics_fingerprint_v2(),
        "retention_proof_fingerprint": retention.proof_fingerprint,
        "decision_registry_fingerprint": decision_registry_fingerprint_v2(),
        "blocker_resolution_fingerprint": blocker_resolution_fingerprint_v2(),
        "catalog_command_count": 10,
        "state_phase_count": 8,
        "decision_count": 14,
        "r1_blocker_class_count": 4,
        "historical_command_count": 0,
        "deletion_capability_count": 0,
        "mixed_binding_count": 0,
    }
    return _allocate(
        R2OperatorRunbookReceiptV2,
        body,
        "receipt_fingerprint",
        "r2-operator-runbook-receipt-v2",
        {"status": RunbookVerificationStatusV2},
    )


def _allocate(kind, body, fingerprint_name, domain, enum_fields=None):
    value = object.__new__(kind)
    enum_fields = enum_fields or {}
    for name, item in body.items():
        enum_type = enum_fields.get(name)
        object.__setattr__(value, name, enum_type(item) if enum_type else item)
    object.__setattr__(value, fingerprint_name, fingerprint(domain, body))
    return value


def _fixed_install_files():
    names = ["reviewed-production-binding-v2.json"]
    names.extend(
        f"{index:02d}-{gate.value}.json"
        for index, gate in enumerate(ClosureGate, start=1)
    )
    return tuple((name, b"{}") for name in names)


if __name__ == "__main__":
    unittest.main()
