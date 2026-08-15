from __future__ import annotations

import unittest
from dataclasses import dataclass

from backend.r2_issue39_orchestrator.readiness import (
    _Issue39ReadinessPorts,
    _observe_issue39_readiness_v1,
)


@dataclass
class _Value:
    values: dict[str, object]

    def __getattr__(self, name):
        return self.values[name]

    def to_mapping(self):
        return dict(self.values)


class Issue39ReadinessTest(unittest.TestCase):
    def test_exact_closure_closed_issue_and_archived_incident_are_eligible(self):
        result = _observe_issue39_readiness_v1(ports=_ports())

        self.assertTrue(result.ready())
        self.assertEqual(len(result.closure_fingerprint), 64)

    def test_mismatched_receipt_or_open_issue_fails_closed(self):
        for receipt_manifest, issue_state in (("f" * 64, "CLOSED"), ("a" * 64, "OPEN")):
            with self.subTest(receipt_manifest=receipt_manifest, issue_state=issue_state):
                result = _observe_issue39_readiness_v1(
                    ports=_ports(receipt_manifest=receipt_manifest, issue_state=issue_state)
                )
                self.assertFalse(result.ready())

    def test_current_master_or_guardrail_manifest_drift_fails_closed(self):
        ports = _ports()
        current = _Value(
            {
                **ports.derive_current_manifest().to_mapping(),
                "final_commit_oid": "9" * 40,
            }
        )
        drifted = _Issue39ReadinessPorts(
            ports.read_artifacts,
            ports.parse_manifest,
            ports.parse_receipt,
            lambda: current,
            ports.issue38_state,
            ports.incident_archived,
        )

        result = _observe_issue39_readiness_v1(ports=drifted)

        self.assertFalse(result.closure_eligible)
        self.assertTrue(result.issue38_closed)
        self.assertTrue(result.incident_archived)
        self.assertEqual(result.closure_fingerprint, "0" * 64)


def _ports(*, receipt_manifest="a" * 64, issue_state="CLOSED"):
    manifest = _Value(
        {
            "manifest_fingerprint": "a" * 64,
            "final_master_binding_fingerprint": "b" * 64,
            "final_commit_oid": "c" * 40,
            "final_tree_oid": "d" * 40,
            "production_binding_fingerprint": "e" * 64,
            "issue39_authority_count": 0,
            "execution_authority_count": 0,
            "failure_count": 0,
        }
    )
    receipt = _Value(
        {
            "status": "SOLO_MAINTAINER_ATTESTATION_RECORDED",
            "manifest_fingerprint": receipt_manifest,
            "receipt_fingerprint": "1" * 64,
            "final_master_binding_fingerprint": "b" * 64,
            "final_commit_oid": "c" * 40,
            "final_tree_oid": "d" * 40,
            "production_binding_fingerprint": "e" * 64,
            "issue39_authority_count": 0,
            "execution_authority_count": 0,
        }
    )
    return _Issue39ReadinessPorts(
        read_artifacts=lambda: (b"manifest", b"receipt"),
        parse_manifest=lambda _payload: manifest,
        parse_receipt=lambda _payload: receipt,
        derive_current_manifest=lambda: manifest,
        issue38_state=lambda: issue_state,
        incident_archived=lambda: True,
    )


if __name__ == "__main__":
    unittest.main()
