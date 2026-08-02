"""Independent stopped-layout and final-running audit behavior for Issue #80."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from backend.r2_independent_audits import (
    AuditDisposition,
    AuditKind,
    IndependentAuditObservationV1,
    IndependentFinalRunningHealthReceiptV1,
    IndependentStoppedLayoutAuditReceiptV1,
)
from backend.r2_independent_audits.testing import SyntheticIndependentAudit
from tests.cutover_contract_fixtures import opaque_fingerprint


NOW = 1_900_000_000
OPERATION = opaque_fingerprint(8000)
BINDING = opaque_fingerprint(8001)
HEAD = opaque_fingerprint(8002)
IDENTITIES = opaque_fingerprint(8003)
HEALTH = opaque_fingerprint(8004)


class R2IndependentAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.entries = []

    def test_receipts_are_exact_nominal_nonserializable_values(self) -> None:
        for receipt_type in (
            IndependentStoppedLayoutAuditReceiptV1,
            IndependentFinalRunningHealthReceiptV1,
        ):
            with self.subTest(receipt_type=receipt_type.__name__):
                with self.assertRaises(TypeError):
                    receipt_type()
        receipt = self._audit(AuditKind.STOPPED_LAYOUT).run(
            self._observation(AuditKind.STOPPED_LAYOUT)
        ).receipt
        self.assertIs(type(receipt), IndependentStoppedLayoutAuditReceiptV1)
        self.assertNotIn(OPERATION, repr(receipt))
        with self.assertRaises(TypeError):
            receipt.__reduce__()

    def test_one_prebound_sink_appends_only_one_content_free_attestation(self):
        audit = self._audit(AuditKind.STOPPED_LAYOUT)
        first = audit.run(self._observation(AuditKind.STOPPED_LAYOUT))
        second = audit.run(self._observation(AuditKind.STOPPED_LAYOUT))

        self.assertIs(first.disposition, AuditDisposition.ATTESTED)
        self.assertIs(second.disposition, AuditDisposition.INCIDENT_STOP)
        self.assertEqual(len(self.entries), 1)
        self.assertEqual(
            set(self.entries[0]),
            {
                "attestation_type",
                "audit_kind",
                "attestation_fingerprint",
                "observed_at_epoch",
                "expires_at_epoch",
            },
        )
        self.assertEqual(self.entries[0]["expires_at_epoch"], NOW + 300)
        public = json.dumps(self.entries[0], sort_keys=True)
        for forbidden in ("D:\\", "path", "email", "provider", OPERATION):
            self.assertNotIn(forbidden, public.lower())

    def test_head_identity_health_mismatch_and_ambiguity_fail_closed(self):
        cases = (
            (
                self._observation(
                    AuditKind.FINAL_RUNNING_HEALTH,
                    journal_head=opaque_fingerprint(8010),
                ),
                AuditDisposition.ROLLBACK_REQUIRED,
            ),
            (
                self._observation(
                    AuditKind.FINAL_RUNNING_HEALTH,
                    identities=opaque_fingerprint(8011),
                ),
                AuditDisposition.ROLLBACK_REQUIRED,
            ),
            (
                self._observation(
                    AuditKind.FINAL_RUNNING_HEALTH,
                    health=opaque_fingerprint(8012),
                ),
                AuditDisposition.ROLLBACK_REQUIRED,
            ),
            (
                self._observation(
                    AuditKind.FINAL_RUNNING_HEALTH,
                    unambiguous=False,
                ),
                AuditDisposition.INCIDENT_STOP,
            ),
        )
        for observation, expected in cases:
            with self.subTest(expected=expected):
                entries = []
                audit = self._audit(
                    AuditKind.FINAL_RUNNING_HEALTH, entries=entries
                )
                result = audit.run(observation)
                self.assertIs(result.disposition, expected)
                self.assertIsNone(result.receipt)
                self.assertEqual(entries, [])

    def test_expiry_requires_a_completely_fresh_sink_and_invocation(self):
        audit = self._audit(
            AuditKind.STOPPED_LAYOUT,
            now=lambda: NOW + 301,
            observed_at=NOW,
        )
        expired = audit.run(self._observation(AuditKind.STOPPED_LAYOUT))
        replay = audit.run(self._observation(AuditKind.STOPPED_LAYOUT))
        fresh = self._audit(
            AuditKind.STOPPED_LAYOUT,
            entries=[],
            now=lambda: NOW + 301,
            observed_at=NOW + 301,
        ).run(
            self._observation(
                AuditKind.STOPPED_LAYOUT, observed_at=NOW + 301
            )
        )
        self.assertIs(expired.disposition, AuditDisposition.EXPIRED)
        self.assertIs(replay.disposition, AuditDisposition.INCIDENT_STOP)
        self.assertIs(fresh.disposition, AuditDisposition.ATTESTED)

    def test_wrong_kind_and_sink_swap_are_incident_stops(self) -> None:
        stopped = self._audit(AuditKind.STOPPED_LAYOUT)
        wrong = stopped.run(self._observation(AuditKind.FINAL_RUNNING_HEALTH))
        self.assertIs(wrong.disposition, AuditDisposition.INCIDENT_STOP)
        self.assertEqual(self.entries, [])

    def test_two_audits_execute_in_different_fresh_os_processes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        commands = [
            (
                sys.executable,
                "-B",
                "-m",
                "tests.r2_independent_audit_worker",
                kind.value,
            )
            for kind in (AuditKind.STOPPED_LAYOUT, AuditKind.FINAL_RUNNING_HEALTH)
        ]
        processes = [
            subprocess.Popen(
                command,
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for command in commands
        ]
        observed = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=20)
            self.assertEqual((process.returncode, stderr), (0, ""))
            observed.append(json.loads(stdout))
        self.assertNotEqual(observed[0]["process_id"], observed[1]["process_id"])
        self.assertNotIn(os.getpid(), [item["process_id"] for item in observed])
        self.assertEqual(
            [item["audit_kind"] for item in observed],
            ["stopped_layout", "final_running_health"],
        )
        self.assertEqual([item["journal_entries"] for item in observed], [1, 1])

    def _audit(self, kind, *, entries=None, now=None, observed_at=NOW):
        return SyntheticIndependentAudit.create(
            kind=kind,
            operation_fingerprint=OPERATION,
            approved_binding_fingerprint=BINDING,
            journal_head_fingerprint=HEAD,
            approved_identities_fingerprint=IDENTITIES,
            health_evidence_fingerprint=HEALTH,
            observed_at_epoch=observed_at,
            now=now or (lambda: NOW),
            append_attestation=(entries if entries is not None else self.entries).append,
        )

    def _observation(self, kind, **overrides):
        return IndependentAuditObservationV1(
            audit_kind=kind,
            operation_fingerprint=OPERATION,
            approved_binding_fingerprint=BINDING,
            journal_head_fingerprint=overrides.get("journal_head", HEAD),
            approved_identities_fingerprint=overrides.get(
                "identities", IDENTITIES
            ),
            health_evidence_fingerprint=overrides.get("health", HEALTH),
            observed_at_epoch=overrides.get("observed_at", NOW),
            unambiguous=overrides.get("unambiguous", True),
        )


if __name__ == "__main__":
    unittest.main()
