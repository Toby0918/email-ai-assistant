"""Generated final R2 operator runbook for Issue #99."""

from __future__ import annotations

from pathlib import Path
import unittest

from backend.r2_evidence_process.production_v2 import EVIDENCE_PRODUCTION_VERBS_V2
from backend.r2_evidence_process.contracts import EVIDENCE_ACKNOWLEDGEMENT
from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_operator_runbook_v2 import (
    OperatorCommandEffectV2,
    OperatorPhaseV2,
    OperatorSurfaceV2,
    R2OperatorRunbookReceiptV2,
    RunbookVerificationStatusV2,
    command_catalog_v2,
    executable_verb_map_v2,
    operator_package_semantics_fingerprint_v2,
    operator_state_machine_v2,
    render_r2_operator_runbook_v2,
    resolve_operator_command_v2,
    runbook_document_fingerprint_v2,
)
from backend.r2_preflight_process.production_v2 import PREFLIGHT_PRODUCTION_VERBS_V2
from backend.r2_preflight_process.contracts import PREFLIGHT_ACKNOWLEDGEMENT
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
)
from backend.r2_retention_ledger_v2 import R2RetentionLedgerV2, R2RetentionProofV2
from backend.r2_transaction_process.production_v2 import TRANSACTION_PRODUCTION_VERBS_V2
from backend.r2_transaction_process.contracts import TRANSACTION_ACKNOWLEDGEMENT
from tests.r2_rollback_recovery_v2_fixture import complete_forward_journal, rollback_plan


ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "docs" / "operations" / "r2_final_operator_runbook.md"


class R2OperatorRunbookV2Tests(unittest.TestCase):
    def setUp(self):
        self.binding = _binding()
        self.binding, self.foundation, self.managed, self.validation, self.journal = (
            complete_forward_journal(self.binding)
        )
        self.rollback = rollback_plan(
            self.binding,
            self.foundation,
            self.managed,
            self.validation,
            self.journal,
        )
        ledger = R2RetentionLedgerV2.project(
            binding=self.binding,
            foundation_plan=self.foundation,
            managed_plan=self.managed,
            validation_plan=self.validation,
            rollback_plan=self.rollback,
            journal=self.journal,
        )
        self.retention = R2RetentionProofV2.create(
            binding=self.binding, ledger=ledger, journal=self.journal
        )

    def test_catalog_is_the_exact_executable_vocabulary(self):
        catalog = command_catalog_v2()
        self.assertEqual(len(catalog), 10)
        self.assertEqual(tuple(item.command for item in catalog), tuple(ProductionCommandV2))
        self.assertEqual(len({item.verb for item in catalog}), 10)
        self.assertEqual(
            executable_verb_map_v2(OperatorSurfaceV2.PREFLIGHT),
            PREFLIGHT_PRODUCTION_VERBS_V2,
        )
        self.assertEqual(
            executable_verb_map_v2(OperatorSurfaceV2.EVIDENCE),
            EVIDENCE_PRODUCTION_VERBS_V2,
        )
        self.assertEqual(
            executable_verb_map_v2(OperatorSurfaceV2.TRANSACTION),
            TRANSACTION_PRODUCTION_VERBS_V2,
        )
        self.assertTrue(all(item.max_operations == 1 for item in catalog))
        self.assertTrue(all(item.destructive_capability_count == 0 for item in catalog))
        acknowledgements = {
            OperatorSurfaceV2.PREFLIGHT: PREFLIGHT_ACKNOWLEDGEMENT,
            OperatorSurfaceV2.EVIDENCE: EVIDENCE_ACKNOWLEDGEMENT,
            OperatorSurfaceV2.TRANSACTION: TRANSACTION_ACKNOWLEDGEMENT,
        }
        self.assertTrue(
            all(item.acknowledgement == acknowledgements[item.surface] for item in catalog)
        )

    def test_state_machine_covers_forward_recovery_rollback_and_retention(self):
        rules = operator_state_machine_v2()
        self.assertEqual(tuple(item.phase for item in rules), tuple(OperatorPhaseV2))
        by_phase = {item.phase: item for item in rules}
        self.assertEqual(
            by_phase[OperatorPhaseV2.FORWARD].allowed_effects,
            (OperatorCommandEffectV2.FORWARD,),
        )
        self.assertIn(
            OperatorCommandEffectV2.RESUME,
            by_phase[OperatorPhaseV2.FORWARD_RECOVERY].allowed_effects,
        )
        self.assertEqual(
            by_phase[OperatorPhaseV2.FORWARD_RECOVERY].allowed_commands,
            ("recovery-inspection", "resume", "rollback"),
        )
        self.assertEqual(
            by_phase[OperatorPhaseV2.ROLLBACK_RECOVERY].allowed_commands,
            ("recovery-inspection", "rollback"),
        )
        self.assertEqual(
            by_phase[OperatorPhaseV2.RETENTION_RECONCILIATION].allowed_commands,
            (),
        )
        self.assertEqual(
            by_phase[OperatorPhaseV2.HUMAN_FINAL_REVIEW].allowed_commands,
            (),
        )
        self.assertTrue(all(item.deletion_capability_count == 0 for item in rules))

    def test_committed_runbook_is_exact_renderer_output(self):
        rendered = render_r2_operator_runbook_v2()
        self.assertEqual(RUNBOOK.read_bytes(), rendered)
        self.assertEqual(runbook_document_fingerprint_v2(), self.binding.runbook_fingerprint)
        text = rendered.decode("utf-8")
        for entry in command_catalog_v2():
            self.assertIn(f"`{entry.verb}`", text)
        self.assertIn("DORMANT_NO_EXTERNAL_ISSUER", text)
        self.assertIn("LEGACY_FLAT_LAYOUT_RESTORED", text)
        self.assertIn("zero deletion capability", text)

    def test_receipt_binds_current_master_package_semantics_and_retention(self):
        receipt = self._receipt()
        restarted = R2OperatorRunbookReceiptV2.from_json(
            receipt.to_canonical_json(),
            binding=self.binding,
            retention_proof=self.retention,
            document=render_r2_operator_runbook_v2(),
            source_package_fingerprint=self.binding.source_package_fingerprint,
            package_semantics_fingerprint=operator_package_semantics_fingerprint_v2(),
        )
        self.assertEqual(restarted, receipt)
        self.assertIs(receipt.status, RunbookVerificationStatusV2.RUNBOOK_SEMANTICS_VERIFIED)
        self.assertEqual(
            (
                receipt.historical_command_count,
                receipt.deletion_capability_count,
                receipt.mixed_binding_count,
            ),
            (0, 0, 0),
        )

    def test_stale_master_package_historical_semantics_and_aliases_fail(self):
        good = {
            "binding": self.binding,
            "retention_proof": self.retention,
            "document": render_r2_operator_runbook_v2(),
            "source_package_fingerprint": self.binding.source_package_fingerprint,
            "package_semantics_fingerprint": operator_package_semantics_fingerprint_v2(),
        }
        for replacement in (
            {"binding": _stale_binding()},
            {"source_package_fingerprint": "e" * 64},
            {"package_semantics_fingerprint": "f" * 64},
            {"retention_proof": object()},
            {"document": good["document"] + b"\n"},
        ):
            with self.subTest(field=tuple(replacement)):
                with self.assertRaisesRegex(ValueError, "R2_OPERATOR_RUNBOOK_INVALID"):
                    R2OperatorRunbookReceiptV2.create(**{**good, **replacement})
        for verb in ("cutover", "rollback-all", "r1-resume", "cleanup", "prune"):
            with self.assertRaisesRegex(ValueError, "R2_OPERATOR_RUNBOOK_INVALID"):
                resolve_operator_command_v2(OperatorSurfaceV2.TRANSACTION, verb)

    def _receipt(self):
        return R2OperatorRunbookReceiptV2.create(
            binding=self.binding,
            retention_proof=self.retention,
            document=render_r2_operator_runbook_v2(),
            source_package_fingerprint=self.binding.source_package_fingerprint,
            package_semantics_fingerprint=operator_package_semantics_fingerprint_v2(),
        )


def _binding():
    final = FinalMasterBindingV1.create(
        final_commit_oid="1" * 40,
        final_tree_oid="2" * 40,
        source_package_fingerprint="3" * 64,
        runbook_fingerprint=runbook_document_fingerprint_v2(),
        workflow_fingerprint="5" * 64,
    )
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final,
        operation_fingerprint="6" * 64,
        operator_role_fingerprints={role: f"{index + 10:064x}" for index, role in enumerate(OperatorRoleV2)},
        verification_public_keys={role: bytes([index + 1]) * 32 for index, role in enumerate(PublicKeyRoleV2)},
        production_role_fingerprints={role: f"{index + 30:064x}" for index, role in enumerate(ProductionRoleV2)},
    )


def _stale_binding():
    final = FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final,
        operation_fingerprint="f" * 64,
        operator_role_fingerprints={role: f"{index + 80:064x}" for index, role in enumerate(OperatorRoleV2)},
        verification_public_keys={role: bytes([index + 10]) * 32 for index, role in enumerate(PublicKeyRoleV2)},
        production_role_fingerprints={role: f"{index + 100:064x}" for index, role in enumerate(ProductionRoleV2)},
    )


if __name__ == "__main__":
    unittest.main()
