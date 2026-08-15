from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_issue39_orchestrator.action_catalog import (
    build_fixed_production_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.closure_binding import (
    _Issue39ClosureBindingV1,
)
from backend.r2_issue39_orchestrator.preparation import (
    Issue39PrepareStatusV1,
    _allocate_prepared_execution_v1,
)
from backend.r2_issue39_orchestrator.production_evidence import (
    Issue39EvidencePackageV1,
)
from backend.r2_issue39_orchestrator.production_preflight import (
    _Issue39PreflightPortsV1,
    _run_issue39_preflight_v1,
)
from backend.r2_issue39_orchestrator.preflight_progress import resume_subject
from backend.r2_issue39_orchestrator.readiness import _observation
from backend.r2_issue39_orchestrator.roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    Issue39WorktreeV1,
)
from backend.r2_production_binding import (
    ProductionCommandV2,
    production_action_fingerprint_v2,
)
from tests.r2_execution_confirmation_fixture import (
    execution_candidate,
    execution_claim,
)
from tests.test_r2_transaction_journal_v2 import _binding


class Issue39ProductionPreflightTest(unittest.TestCase):
    def test_six_reads_each_persist_claim_before_observation(self):
        binding = _binding()
        prepared = _prepared()
        catalog = build_fixed_production_action_catalog_v1(prepared)
        package = _package()
        closure = _Issue39ClosureBindingV1(
            SimpleNamespace(manifest_fingerprint="d" * 64),
            SimpleNamespace(receipt_fingerprint="e" * 64),
            object(),
            binding,
        )
        calls = []
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            from backend.r2_issue39_orchestrator import preflight_ledger

            with patch.object(preflight_ledger, "_ROOT", root):
                def opener(**values):
                    return preflight_ledger._open_preflight_ledger_v1(**values)

                def confirm(actual, subject, transition, ledger):
                    calls.append("confirm:" + actual.value)
                    action = (
                        production_action_fingerprint_v2(
                            binding, actual,
                            subject_fingerprint=resume_subject(
                                transition, ledger.head
                            ),
                        )
                        if actual is ProductionCommandV2.RESUME
                        else production_action_fingerprint_v2(binding, subject)
                    )
                    candidate = execution_candidate(
                        binding,
                        command=actual,
                        action_fingerprint=action,
                        closure_manifest="d" * 64,
                        solo_attestation="e" * 64,
                        prior_head=ledger.head,
                        journal_owner=ledger.owner_fingerprint,
                        transition=transition,
                        claim_sequence=sum(
                            item.kind == "claim" for item in ledger.records
                        ) + 1,
                        prepared_at_epoch=100,
                        confirmed_at_epoch=102,
                    )
                    claim = execution_claim(
                        binding, candidate=candidate, confirmed_at_epoch=102
                    )
                    return claim, {
                        "observed_at_epoch": 102,
                        "observed_monotonic_ns": 4_000_000_000,
                    }

                def observe(command):
                    calls.append("observe:" + command.value)
                    return hashlib.sha256(command.value.encode("ascii")).hexdigest()

                ports = _Issue39PreflightPortsV1(confirm, observe, opener)
                receipt = _run_issue39_preflight_v1(
                    prepared=prepared,
                    closure=closure,
                    catalog=catalog,
                    package=None,
                    phase="before_evidence",
                    ports=ports,
                )
                for phase in ("after_evidence", "recovery"):
                    receipt = _run_issue39_preflight_v1(
                        prepared=prepared,
                        closure=closure,
                        catalog=catalog,
                        package=package,
                        phase=phase,
                        prior=receipt,
                        ports=ports,
                    )

            files = tuple(root.rglob("*.p39"))

        self.assertEqual(len(files), 12)
        self.assertEqual(len(calls), 12)
        self.assertTrue(all(
            calls[index].startswith("confirm:")
            and calls[index + 1].startswith("observe:")
            for index in range(0, len(calls), 2)
        ))


def _prepared():
    worktrees = tuple(
        Issue39WorktreeV1(
            f"worktree_{index:02d}",
            "embedded" if index <= 2 else "external",
            f"{index:064x}",
        )
        for index in range(1, 7)
    )
    roster = Issue39BoundRosterV1(
        Issue39RosterStatusV1.VERIFIED,
        worktrees,
        "c" * 64,
        Path("D:/synthetic"),
        (),
    )
    return _allocate_prepared_execution_v1(
        Issue39PrepareStatusV1.VERIFIED,
        "a" * 64,
        6, 2, 4,
        _observation(True, True, True, "b" * 64),
        None,
        roster,
    )


def _package():
    return Issue39EvidencePackageV1(
        "1" * 64, "2" * 64, "3" * 64, "4" * 64,
        b"{}\n", b"{}\n", b"synthetic-runner",
    )


if __name__ == "__main__":
    unittest.main()
