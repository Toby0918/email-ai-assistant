"""Git-object source package and CI provenance contracts for Issue #100."""

from __future__ import annotations

import hashlib
import os
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_ci_provenance_v2 import (
    CiProvenanceKindV2,
    CiProvenanceStatusV2,
    R2CiProvenanceBundleV2,
    R2CiProvenanceError,
    R2CiProvenanceReceiptV2,
    R2GitObjectEntryV2,
    R2GitObjectSourcePackageV2,
    R2WorkflowLockV2,
    fixed_suite_v2,
    fixed_suite_fingerprint_v2,
    portable_native_skip_reason_registry_v2,
)


class R2CiProvenanceV2Tests(unittest.TestCase):
    def setUp(self):
        self.lock = _workflow_lock()
        self.package = _package(self.lock)

    def test_git_object_package_binds_exact_final_commit_tree_and_bytes(self):
        package = self.package
        self.assertEqual(package.final_commit_oid, "1" * 40)
        self.assertEqual(package.final_tree_oid, "2" * 40)
        self.assertEqual(package.selected_entry_count, 3)
        self.assertEqual(package.selected_byte_count, 49)
        self.assertEqual(package.historical_package_count, 0)
        self.assertEqual(package.ignored_content_reads, 0)
        self.assertEqual(package.private_content_reads, 0)
        self.assertEqual(package.workflow_lock_fingerprint, self.lock.lock_fingerprint)
        self.assertEqual(self.lock.dependency_lock.lock_count, 2)
        self.assertEqual(self.lock.dependency_lock.dependency_count, 31)
        self.assertEqual(self.lock.dependency_lock.wheel_hash_count, 62)
        self.assertNotIn("synthetic", repr(package))
        self.assertNotIn("backend/app.py", package.to_canonical_json().decode("ascii"))

    def test_historical_or_byte_inconsistent_package_fails_closed(self):
        cases = (
            {"observed_commit_oid": "9" * 40},
            {"observed_tree_oid": "8" * 40},
            {"final_commit_oid": "7" * 40},
        )
        for change in cases:
            with self.subTest(change=change):
                with self.assertRaisesRegex(
                    R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
                ):
                    _package(self.lock, **change)
        with self.assertRaisesRegex(
            R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
        ):
            R2GitObjectEntryV2.create(
                relative_path="backend/app.py",
                mode="100644",
                blob_oid="0" * 40,
                content_bytes=b"synthetic application\n",
            )

    def test_workflow_actions_and_runners_are_hash_locked(self):
        self.assertEqual(self.lock.workflow_count, 3)
        self.assertGreaterEqual(self.lock.action_count, 3)
        for bad in (
            b"jobs:\n  gate:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n",
            b"jobs:\n  gate:\n    runs-on: windows-2022\n    steps:\n      - uses: actions/checkout@v4\n",
            b"jobs:\n  gate:\n    runs-on: windows-2022\n    continue-on-error: true\n",
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(
                    R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
                ):
                    R2WorkflowLockV2.create(
                        workflows=((".github/workflows/r2_provenance.yml", bad),),
                        dependency_locks=_dependency_locks(),
                    )

    def test_portable_registry_excludes_the_windows_composition_evidence_test(self):
        self.assertEqual(
            portable_native_skip_reason_registry_v2(),
            (
                "Windows integration only",
                "Windows sandbox evidence",
                "Windows sandbox required",
                "Windows Job Object test",
                "physical Windows claim",
                "Windows NTFS sandbox required",
                "Windows real TTY proof",
                "Windows process proof",
                "Windows NTFS/TTY/process proof",
                "Windows junction contract",
                "Windows sandbox evidence only; no Linux NTFS or ACL claim",
            ),
        )

    def test_windows_native_registry_is_the_exact_issue_110_suite(self):
        self.assertEqual(
            fixed_suite_v2(CiProvenanceKindV2.WINDOWS_NATIVE),
            (
                "tests.test_r2_main_publication_windows",
                "tests.test_r2_repository_manifest_windows",
                "tests.test_r2_runtime_publication_windows",
                "tests.test_r2_database_publication_windows",
                "tests.test_r2_crx_publication_windows",
                "tests.test_r2_config_publication_windows",
                "tests.test_r2_validation_lifecycle_windows",
                (
                    "tests.test_r2_full_topology_windows."
                    "R2FullTopologyWindowsTests."
                    "test_all_ten_fixed_verbs_ignore_terminal_environment_and_artifacts"
                ),
                (
                    "tests.test_r2_full_topology_windows."
                    "R2FullTopologyWindowsTests."
                    "test_poison_bootstrap_workers_remain_dormant"
                ),
                (
                    "tests.test_r2_ci_provenance_v2_adapter."
                    "R2CiProvenanceWindowsNativeAdapterTests."
                    "test_ci_budgeted_script_proves_complete_topology_without_public_leakage"
                ),
                (
                    "tests.test_r2_full_topology_windows."
                    "R2FullTopologyWindowsTests."
                    "test_portable_contract_makes_no_windows_process_claim"
                ),
                (
                    "tests.test_r2_full_topology_windows."
                    "R2FullTopologyWindowsTests."
                    "test_surface_closure_uses_new_dormant_roots_not_removed_ingress"
                ),
            ),
        )

    def test_windows_independent_registry_is_the_exact_issue_110_suite(self):
        self.assertEqual(
            fixed_suite_v2(CiProvenanceKindV2.WINDOWS_INDEPENDENT),
            (
                "tests.test_r2_preflight_production_v2",
                "tests.test_r2_evidence_production_v2",
                "tests.test_r2_transaction_production_v2",
                "tests.test_r2_execution_confirmation",
                "tests.test_close_r2_final_master",
            ),
        )

    def test_windows_registries_load_without_failed_tests(self):
        loader = unittest.TestLoader()
        registered = (
            fixed_suite_v2(CiProvenanceKindV2.WINDOWS_NATIVE)
            + fixed_suite_v2(CiProvenanceKindV2.WINDOWS_INDEPENDENT)
        )
        suite = loader.loadTestsFromNames(registered)
        failed_tests = tuple(
            test for test in _leaf_tests(suite)
            if type(test).__name__ == "_FailedTest"
        )
        self.assertEqual(loader.errors, [])
        self.assertEqual(failed_tests, ())

    def test_hosted_ordinal_probe_normalizes_subtests_and_is_exactly_gated(self):
        from tests import test_close_r2_final_master as target

        class Case:
            def id(self):
                return target._WINDOWS_INDEPENDENT_CASE_IDS[29]

        result = SimpleNamespace(
            failures=[(SimpleNamespace(test_case=Case()), "not emitted")],
            errors=[], skipped=[], unexpectedSuccesses=[],
        )
        hosted = {
            "GITHUB_ACTIONS": "true",
            "GITHUB_JOB": "windows-independent-provenance",
            "R2_CI_PROVENANCE_KIND": "windows_independent",
        }
        observed = []
        with patch.dict(os.environ, hosted), patch.object(
            target.os, "write", side_effect=lambda fd, value: observed.append((fd, value))
        ):
            target._probe_prior_windows_independent_result(result)
        self.assertEqual(observed, [
            (2, b"R2_WININD_HOSTED_FAILURE\n"),
            (2, b"R2_WININD_HOSTED_CASE_30\n"),
            (2, b"R2_WININD_HOSTED_PRIOR_NOT_CLEAN\n"),
        ])
        with patch.dict(os.environ, hosted | {"GITHUB_ACTIONS": "false"}), patch.object(
            target.os, "write"
        ) as write:
            target._probe_prior_windows_independent_result(result)
        write.assert_not_called()

    def test_three_independent_receipts_reconcile_without_skips_or_divergence(self):
        receipts = tuple(
            _receipt(self.package, kind, f"{index + 3:064x}")
            for index, kind in enumerate(CiProvenanceKindV2)
        )
        bundle = R2CiProvenanceBundleV2.create(
            source_package=self.package,
            workflow_lock=self.lock,
            receipts=receipts,
        )
        self.assertIs(bundle.status, CiProvenanceStatusV2.CI_PROVENANCE_RECONCILED)
        self.assertEqual(bundle.provenance_receipt_count, 3)
        self.assertEqual(bundle.required_skip_count, 0)
        self.assertEqual(bundle.platform_divergence_count, 0)
        self.assertEqual(bundle.leakage_finding_count, 0)
        self.assertEqual(bundle.hash_locked_dependency_count, 31)
        self.assertEqual(bundle.wheel_hash_count, 62)
        self.assertEqual(bundle.portable_full_suite_receipt_count, 1)
        portable = next(
            item for item in receipts
            if item.provenance_kind is CiProvenanceKindV2.PORTABLE
        )
        self.assertEqual(portable.portable_full_suite, 1)
        self.assertEqual(
            R2CiProvenanceBundleV2.from_json(
                bundle.to_canonical_json(),
                source_package=self.package,
                workflow_lock=self.lock,
                receipts=receipts,
            ),
            bundle,
        )

    def test_receipts_reject_skip_leakage_failure_stale_and_shared_runner(self):
        kind = CiProvenanceKindV2.PORTABLE
        base = _receipt_values(self.package, kind, "3" * 64)
        for change in (
            {"required_skip_count": 1},
            {"leakage_finding_count": 1},
            {"failure_count": 1},
            {"suite_fingerprint": "4" * 64},
        ):
            with self.subTest(change=tuple(change)):
                with self.assertRaisesRegex(
                    R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
                ):
                    R2CiProvenanceReceiptV2.create(**{**base, **change})

        receipt = R2CiProvenanceReceiptV2.create(**base)
        stale = _package(
            self.lock,
            final_commit_oid="7" * 40,
            observed_commit_oid="7" * 40,
        )
        with self.assertRaisesRegex(
            R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
        ):
            R2CiProvenanceReceiptV2.from_json(
                receipt.to_canonical_json(),
                source_package=stale,
                workflow_lock=self.lock,
            )

        receipts = tuple(
            _receipt(self.package, item, "3" * 64) for item in CiProvenanceKindV2
        )
        with self.assertRaisesRegex(
            R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
        ):
            R2CiProvenanceBundleV2.create(
                source_package=self.package,
                workflow_lock=self.lock,
                receipts=receipts,
            )

    def test_receipt_json_rejects_duplicate_unknown_and_raw_fields(self):
        receipt = _receipt(self.package, CiProvenanceKindV2.PORTABLE, "3" * 64)
        payload = receipt.to_canonical_json()
        duplicate = payload[:-1] + b',"status":"CI_PROVENANCE_VERIFIED"}'
        unknown = payload[:-1] + b',"path":"private"}'
        for candidate in (duplicate, unknown, b"{}", payload + b"\n"):
            with self.subTest(candidate=candidate[-30:]):
                with self.assertRaisesRegex(
                    R2CiProvenanceError, "R2_CI_PROVENANCE_INVALID"
                ):
                    R2CiProvenanceReceiptV2.from_json(
                        candidate,
                        source_package=self.package,
                        workflow_lock=self.lock,
                    )


def _blob_oid(content: bytes) -> str:
    framed = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(framed).hexdigest()


def _leaf_tests(test):
    if isinstance(test, unittest.TestSuite):
        for child in test:
            yield from _leaf_tests(child)
        return
    yield test


def _entry(path: str, content: bytes) -> R2GitObjectEntryV2:
    return R2GitObjectEntryV2.create(
        relative_path=path,
        mode="100644",
        blob_oid=_blob_oid(content),
        content_bytes=content,
    )


def _workflow_lock() -> R2WorkflowLockV2:
    sha = "a" * 40
    workflows = tuple(
        (
            f".github/workflows/{name}.yml",
            (
                "jobs:\n"
                "  gate:\n"
                f"    runs-on: {runner}\n"
                "    steps:\n"
                f"      - uses: actions/checkout@{sha}\n"
                + (
                    "      - run: pip install --only-binary=:all: --require-hashes -r requirements-ci-linux.lock\n"
                    "      - run: pip install --only-binary=:all: --require-hashes -r requirements-ci-windows.lock\n"
                    "      - run: pip install --only-binary=:all: --require-hashes -r requirements-ci-windows.lock\n"
                    if name == "r2_provenance" else ""
                )
            ).encode("ascii"),
        )
        for name, runner in (
            ("agent_guardrails", "ubuntu-24.04"),
            ("cleanup_agent", "ubuntu-24.04"),
            ("r2_provenance", "windows-2022"),
        )
    )
    return R2WorkflowLockV2.create(
        workflows=workflows, dependency_locks=_dependency_locks()
    )


def _dependency_locks():
    root = Path(__file__).resolve().parents[1]
    return tuple(
        (name, (root / name).read_bytes())
        for name in ("requirements-ci-linux.lock", "requirements-ci-windows.lock")
    )


def _package(lock: R2WorkflowLockV2, **changes) -> R2GitObjectSourcePackageV2:
    runbook = b"# exact synthetic runbook\n"
    values = {
        "final_commit_oid": "1" * 40,
        "final_tree_oid": "2" * 40,
        "observed_commit_oid": "1" * 40,
        "observed_tree_oid": "2" * 40,
        "entries": (
            _entry("backend/app.py", b"synthetic application\n"),
            _entry("docs/operations/r2_final_operator_runbook.md", runbook),
            _entry("README.md", b"x"),
        ),
        "workflow_lock": lock,
        "runbook_fingerprint": hashlib.sha256(
            b"r2-operator-runbook-document-v2\0" + runbook
        ).hexdigest(),
    }
    values.update(changes)
    return R2GitObjectSourcePackageV2.create(**values)


def _receipt_values(package, kind, runner_fingerprint):
    return {
        "source_package": package,
        "workflow_lock": _workflow_lock(),
        "provenance_kind": kind,
        "runner_fingerprint": runner_fingerprint,
        "installed_dependency_fingerprint": "a" * 64,
        "suite_fingerprint": fixed_suite_fingerprint_v2(kind),
        "required_skip_count": 0,
        "platform_divergence_count": 0,
        "leakage_finding_count": 0,
        "failure_count": 0,
    }


def _receipt(package, kind, runner_fingerprint):
    return R2CiProvenanceReceiptV2.create(
        **_receipt_values(package, kind, runner_fingerprint)
    )


if __name__ == "__main__":
    unittest.main()
