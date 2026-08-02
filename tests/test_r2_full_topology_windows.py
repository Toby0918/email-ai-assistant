"""One fresh physical NTFS sandbox across the highest R2 seams."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from backend.cutover_composition_contracts.canonical import fingerprint
from backend.r2_database_publication import QuiescencePrerequisitesV1
from backend.r2_evidence_process import EvidenceProcessStatus
from backend.r2_evidence_process.contracts import result as evidence_result
from scripts.r2_durable_journal_support import SyntheticDurableJournal
from scripts.r2_publication_receipt_support import read_verified_publications
from scripts.r2_synthetic_topology_support import _surface_source_paths
from scripts.r2_semantic_gap_support import execute_semantic_gap_matrix
from scripts.r2_semantic_owning_effects import execute_owning_effect
from scripts.r2_shared_topology_support import execute_shared_publications


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_r2_synthetic_topology.py"


@unittest.skipUnless(sys.platform == "win32", "Windows NTFS/TTY/process proof")
class R2FullTopologyWindowsTests(unittest.TestCase):
    def test_fixed_script_proves_complete_topology_without_public_leakage(self):
        completed = subprocess.run(
            (sys.executable, "-B", str(SCRIPT)),
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        self.assertEqual((completed.returncode, completed.stderr), (0, ""))
        value = json.loads(completed.stdout)
        self.assertEqual(value["status"], "R2_SYNTHETIC_VERIFICATION_COMPLETE")
        self.assertEqual(
            value["counts"],
            {
                "authorization_domains": 4,
                "independent_audits": 2,
                "managed_units": 4,
                "process_types": 3,
                "project_container_zones": 9,
                "repositories": 1,
                "semantic_gap_cases": 70,
                "worktrees": 11,
            },
        )
        self.assertEqual(value["terminal_status"], "CUTOVER_SUCCESS")
        self.assertEqual(value["provider_attempts"], 0)
        self.assertEqual(value["public_leakage"], 0)
        self.assertEqual(value["real_host_operations"], 0)
        self.assertEqual(len(set(value["fingerprints"].values())), 6)
        for forbidden in ("D:\\", "C:\\", "AppData", "email", "private"):
            self.assertNotIn(forbidden.lower(), completed.stdout.lower())

    def test_portable_contract_makes_no_windows_claim(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertIn('@unittest.skipUnless(sys.platform == "win32"', source)
        portable = (
            ROOT / "tests" / "test_r2_verification_evidence_contracts.py"
        ).read_text(encoding="utf-8")
        for forbidden in ("NTFS", "Windows ACL", "real TTY", "process isolation"):
            self.assertNotIn(forbidden, portable)

    def test_surface_closure_includes_dynamic_and_durable_implementations(self):
        observed = {
            path.relative_to(ROOT).as_posix()
            for path in _surface_source_paths(ROOT)
        }
        required = {
            "backend/r2_operator_process/dormant_context.py",
            "scripts/r2_durable_journal_support.py",
            "scripts/r2_semantic_case_journal.py",
            "scripts/r2_semantic_owning_effects.py",
            "scripts/r2_shared_topology_support.py",
            "tests/r2_validation_service_worker.py",
            "tests/r2_validation_audit_worker.py",
            "tests/windows_synthetic_tty_host.py",
            "tests/r2_preflight_process_worker.py",
            "tests/r2_evidence_process_worker.py",
            "tests/r2_transaction_process_worker.py",
        }
        self.assertEqual(required - observed, set())

    def test_all_case_bindings_and_receipts_are_durable(self):
        with tempfile.TemporaryDirectory(prefix="r2-durable-cases-") as raw:
            root = Path(raw)
            self.assertEqual(execute_semantic_gap_matrix(root), 70)
            journals = sorted((root / "semantic-gaps").glob("*/case.journal"))
            self.assertEqual(len(journals), 70)
            for journal in journals:
                records = [json.loads(line) for line in journal.read_text("ascii").splitlines()]
                self.assertEqual(
                    [item["record_type"] for item in records],
                    ["CASE_BINDING", "OWNING_RESULT", "EXECUTED_CASE_RECEIPT"],
                )
                self.assertEqual(records[-1]["binding"], records[0]["binding"])

    def test_recovery_and_final_seal_gaps_have_exact_effect_counts(self):
        gaps = (
            "before_intent",
            "after_intent",
            "after_effect",
            "after_stable_observation",
            "after_commit",
        )
        for direction in ("forward", "reverse"):
            for gap in gaps:
                with self.subTest(semantic="recovery", direction=direction, gap=gap):
                    result = execute_owning_effect(
                        "recovery", Path(), direction, gap
                    )
                    self.assertEqual(result["status"], "RECOVERY_RESTART_REQUIRED")
                    self.assertEqual(
                        result["mutations"],
                        0 if gap in ("before_intent", "after_intent") else 1,
                    )
        for gap in gaps:
            with self.subTest(semantic="final_seal", gap=gap):
                result = execute_owning_effect("final_seal", Path(), "forward", gap)
                self.assertEqual(result["status"], "RECOVERY_RESTART_REQUIRED")
                self.assertEqual(
                    result["appends"],
                    0 if gap in ("before_intent", "after_intent") else 1,
                )

    def test_all_publications_share_one_physical_container(self):
        with tempfile.TemporaryDirectory(
            prefix="r2-shared-publications-", dir=ROOT.anchor
        ) as raw:
            prerequisites = QuiescencePrerequisitesV1.create(
                preflight_fingerprint=fingerprint("r2-test-preflight-v1", 1),
                evidence_fingerprint=fingerprint("r2-test-evidence-v1", 1),
                fresh_gate_fingerprint=fingerprint("r2-test-gate-v1", 1),
            )
            topology = execute_shared_publications(Path(raw), prerequisites)
            for path in (
                topology.container,
                topology.runtime_executable,
                topology.database_path,
                topology.config_path,
            ):
                self.assertTrue(path.exists())
                self.assertIn(topology.root, (path, *path.parents))
            self.assertEqual(
                [type(value).__name__ for value in topology.receipts],
                [
                    "PostMoveMainAclConformanceReceiptV1",
                    "RepositoryTopologyReceiptV1",
                    "RuntimePublicationReceiptV1",
                    "DatabaseTransactionResultV1",
                    "CrxPublicationReceiptV1",
                    "ConfigPublicationReceiptV1",
                ],
            )
            self.assertEqual(
                topology.execution_order[:3],
                (
                    "quiescence:committed",
                    "main:committed",
                    "repository:committed",
                ),
            )
            self.assertEqual(
                topology.quiescence_prerequisites_fingerprint,
                prerequisites.contract_fingerprint,
            )
            journal = SyntheticDurableJournal(
                Path(raw) / "test-publication-receipts.journal"
            )
            publications = (
                evidence_result(EvidenceProcessStatus.PUBLISHED),
                *topology.receipts,
            )
            for publication in publications:
                journal.append_publication(publication)
            records = journal.records()
            verified = read_verified_publications(records)
            self.assertEqual(
                tuple(item.publication_type for item in verified),
                tuple(type(item).__name__ for item in publications),
            )
            tampered = [dict(item) for item in records]
            tampered[3]["receipt_fields"] = dict(
                tampered[3]["receipt_fields"]
            )
            tampered[3]["receipt_fields"]["receipt_fingerprint"] = "0" * 64
            with self.assertRaisesRegex(
                RuntimeError, "R2_DURABLE_PUBLICATION_RECEIPT_INVALID"
            ):
                read_verified_publications(tuple(tampered))
            tampered = [dict(item) for item in records]
            tampered[2]["predecessor"] = "0" * 64
            with self.assertRaisesRegex(
                RuntimeError, "R2_DURABLE_PUBLICATION_LINK_INVALID"
            ):
                read_verified_publications(tuple(tampered))


if __name__ == "__main__":
    unittest.main()
