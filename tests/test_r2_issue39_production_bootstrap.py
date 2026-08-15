from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_issue39_orchestrator.closure_binding import _Issue39ClosureBindingV1
from backend.r2_issue39_orchestrator.production_bootstrap import (
    bootstrap_fixed_issue39_journal_v1,
)
from backend.r2_issue39_orchestrator.production_evidence import (
    Issue39EvidencePackageV1,
)
from backend.r2_production_binding import ProductionCommandV2, production_action_fingerprint_v2
from tests.r2_execution_confirmation_fixture import execution_candidate, execution_claim
from tests.test_r2_transaction_journal_v2 import _binding


@unittest.skipUnless(os.name == "nt", "Windows durable bootstrap")
class Issue39ProductionBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.binding = _binding()
        self.closure = _Issue39ClosureBindingV1(
            SimpleNamespace(manifest_fingerprint="d" * 64),
            SimpleNamespace(receipt_fingerprint="e" * 64),
            object(), self.binding,
        )
        self.package = _package()
        self.commands = []

    def test_success_publishes_three_files_and_five_journal_frames(self):
        with self._ports():
            location, journal = bootstrap_fixed_issue39_journal_v1(
                closure=self.closure, package=self.package
            )

        self.assertEqual(journal.record_count, 5)
        self.assertEqual(len(tuple(location.directory.glob("*.r2j"))), 5)
        evidence = next((self.root / "evidence").iterdir())
        self.assertEqual(len(tuple(evidence.iterdir())), 3)

    def test_observation_only_crash_requires_resume_and_never_republishes(self):
        from backend.r2_issue39_orchestrator import durable_ledger

        original = durable_ledger.write_segment

        def interrupted(path, payload):
            original(path, payload)
            if path.name.startswith("000003-"):
                raise SystemExit("synthetic observation cut")

        with self._ports(), patch.object(
            durable_ledger, "write_segment", interrupted
        ):
            with self.assertRaises(SystemExit):
                bootstrap_fixed_issue39_journal_v1(
                    closure=self.closure, package=self.package
                )
        with self._ports():
            _location, journal = bootstrap_fixed_issue39_journal_v1(
                closure=self.closure, package=self.package
            )

        self.assertEqual(journal.record_count, 6)
        self.assertIn(ProductionCommandV2.RESUME, self.commands)

    def _ports(self):
        from backend.r2_issue39_orchestrator import production_bootstrap
        from backend.r2_issue39_orchestrator import production_evidence

        owner = "1" * 64

        def genesis(_closure, package):
            action = production_action_fingerprint_v2(
                self.binding, ProductionCommandV2.EVIDENCE_PUBLICATION,
                subject_fingerprint=package.reviewed_evidence_fingerprint,
            )
            claim = self._claim(
                ProductionCommandV2.EVIDENCE_PUBLICATION,
                action, owner, "0" * 64, 1,
            )
            return claim, _clock(), owner, "2" * 64

        def evidence(_closure, package, journal):
            action = hashlib.sha256(
                b"r2-issue39-evidence-attempt-action-v1\0"
                + bytes.fromhex(package.reviewed_evidence_fingerprint)
                + bytes.fromhex(journal.current_head_fingerprint)
            ).hexdigest()
            return self._claim(
                ProductionCommandV2.EVIDENCE_PUBLICATION, action, owner,
                journal.current_head_fingerprint,
                len(journal.execution_confirmation_claims) + 1,
            ), _clock()

        def resume(_closure, package, journal):
            action = production_action_fingerprint_v2(
                self.binding, ProductionCommandV2.RESUME,
                subject_fingerprint=package.reviewed_evidence_fingerprint,
            )
            return self._claim(
                ProductionCommandV2.RESUME, action, owner,
                journal.current_head_fingerprint,
                len(journal.execution_confirmation_claims) + 1,
            ), _clock()

        stack = ExitStack()
        stack.enter_context(patch.object(production_bootstrap, "_LEDGER_PARENT", self.root))
        stack.enter_context(patch.object(production_evidence, "_EVIDENCE_PARENT", self.root / "evidence"))
        stack.enter_context(patch.object(production_bootstrap, "_confirm_genesis", genesis))
        stack.enter_context(patch.object(production_bootstrap, "_confirm_evidence", evidence))
        stack.enter_context(patch.object(production_bootstrap, "_confirm_resume", resume))
        return stack

    def _claim(self, command, action, owner, head, sequence):
        self.commands.append(command)
        candidate = execution_candidate(
            self.binding, command=command, action_fingerprint=action,
            closure_manifest="d" * 64, solo_attestation="e" * 64,
            prior_head=head, journal_owner=owner,
            transition=self.package.reviewed_evidence_fingerprint,
            claim_sequence=sequence,
        )
        return execution_claim(self.binding, candidate=candidate, confirmed_at_epoch=102)


def _clock():
    return {"observed_at_epoch": 102, "observed_monotonic_ns": 4_000_000_000}


def _package():
    payload, runtime, runner = b"{}\n", b"{}\n", b"runner"
    combined = payload + b"\0" + runtime + b"\0" + runner
    fingerprint = lambda domain, value: hashlib.sha256(domain.encode("ascii") + b"\0" + value).hexdigest()
    return Issue39EvidencePackageV1(
        fingerprint("r2-issue39-reviewed-evidence-v1", combined),
        fingerprint("r2-issue39-evidence-identity-v1", combined),
        fingerprint("r2-issue39-evidence-package-v1", combined),
        fingerprint("r2-issue39-evidence-manifest-v1", payload),
        payload, runtime, runner,
    )


if __name__ == "__main__":
    unittest.main()
