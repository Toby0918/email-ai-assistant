"""Mechanical ownership of the Issue #59 affected safety matrix."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from backend.cutover_repository_transaction import SyntheticCrashGap


ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"

REQUIRED_TESTS = {
    "test_real_host_preflight_windows.py": {
        "test_leaf_absence_fails_closed_after_target_appears",
        "test_reparse_inserted_after_scope_creation_is_rejected",
        "test_scope_requires_exact_unexpired_test_authorization",
    },
    "test_real_host_preflight_windows_composition.py": {
        "test_parent_replacement_between_complete_passes_is_rejected",
        "test_git_drift_between_complete_passes_is_rejected",
    },
    "test_cutover_host_mutation_windows_filesystem.py": {
        "test_target_appearance_after_durable_intent_is_no_clobber",
        "test_move_rejects_source_identity_drift_before_effect",
        "test_parent_identity_drift_blocks_before_effect",
        "test_reparse_parent_inserted_after_binding_is_rejected",
    },
    "test_cutover_host_mutation_windows_acl.py": {
        "test_apply_is_journaled_exact_and_leaves_adjacent_acls_unchanged",
        "test_guarded_container_blocks_child_insertion_until_acl_apply",
    },
    "test_cutover_repository_transaction_crash_gaps.py": {
        "test_every_reverse_crash_gap_resumes_to_exact_original_state",
        "test_forward_move_crash_gaps_are_safely_classified",
        "test_nonfinal_legacy_reverse_main_gap_resumes_exactly",
    },
    "test_cutover_repository_transaction_fail_closed.py": {
        "test_target_collision_is_rejected_without_clobber",
        "test_final_zone_inventory_drift_is_rejected",
        "test_admin_preservation_collision_stops_before_effect",
        "test_target_race_after_durable_intent_is_no_clobber",
        "test_ref_and_admin_content_drift_are_rejected",
    },
    "test_cutover_managed_activation_fail_closed.py": {
        "test_runtime_target_collision_is_preserved",
        "test_database_collision_and_flush_failure_preserve_target",
        "test_crx_drift_collision_and_flush_failure_fail_closed",
        "test_config_collision_and_flush_failure_preserve_target",
    },
    "test_cutover_managed_activation_windows_edges.py": {
        "test_bound_scope_snapshots_targets_and_rejects_parent_replacement",
        "test_runtime_rejects_source_replacement_and_wrong_versions",
        "test_database_lock_and_source_replacement_fail_before_copy",
    },
    "test_cutover_service_lifecycle_activation.py": {
        "test_every_start_identity_field_is_exact",
        "test_publication_chain_mismatch_is_rejected",
    },
    "test_cutover_service_lifecycle_rollback.py": {
        "test_every_legacy_prerequisite_drift_incident_stops",
    },
    "test_cutover_service_lifecycle_windows_sandbox.py": {
        "test_full_failed_activation_preserves_and_restores_exact_topology",
        "test_preexisting_failed_container_collision_incident_stops",
    },
    "test_migration_evidence_publication_create_verify.py": {
        "test_target_collision_is_preserved",
    },
}

WINDOWS_EVIDENCE_MODULES = {
    name
    for name in REQUIRED_TESTS
    if "windows" in name
}


class CutoverCompositionCoverageContractTests(unittest.TestCase):
    def test_affected_matrix_owners_and_cases_remain_present(self) -> None:
        for filename, expected in REQUIRED_TESTS.items():
            with self.subTest(filename=filename):
                self.assertEqual(_test_names(TESTS / filename) & expected, expected)

    def test_crash_gap_enum_is_exact_intent_effect_observed_commit(self) -> None:
        self.assertEqual(
            {item.value for item in SyntheticCrashGap},
            {
                "none",
                "after_intent",
                "after_effect",
                "after_observed",
                "after_committed",
            },
        )

    def test_windows_claim_owners_are_explicitly_platform_gated(self) -> None:
        for filename in WINDOWS_EVIDENCE_MODULES:
            source = (TESTS / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertIn(
                    '@unittest.skipUnless(sys.platform == "win32"',
                    source,
                )

    def test_portable_composition_tests_make_no_windows_behavior_claim(self) -> None:
        for filename in (
            "test_cutover_composition_operator_lock.py",
            "test_cutover_composition_receipt_chain.py",
            "test_real_host_preflight_composition_root.py",
            "test_migration_evidence_publication_composition_root.py",
            "test_cutover_transaction_composition_root.py",
        ):
            source = (TESTS / filename).read_text(encoding="utf-8")
            with self.subTest(filename=filename):
                self.assertNotIn("proves NTFS", source)
                self.assertNotIn("proves Windows ACL", source)


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


if __name__ == "__main__":
    unittest.main()
