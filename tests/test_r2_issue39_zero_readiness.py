from __future__ import annotations

import unittest

from backend.r2_issue39_orchestrator.production_inputs import (
    Issue39ProductionInputsV1,
    Issue39ProductionInputStatusV1,
)
from backend.r2_issue39_orchestrator.zero_readiness import (
    _Issue39ZeroReadinessPortsV1,
    _observe_zero_mutation_readiness_v1,
)
from backend.r2_issue39_orchestrator.archive_parent_windows import (
    _allocate_readiness as _archive_parent,
)


class _Value:
    def __init__(self, **values):
        self.__dict__.update(values)

    def to_mapping(self):
        return dict(self.__dict__)


class Issue39ZeroReadinessTest(unittest.TestCase):
    def test_closure_artifacts_and_closed_issue_are_required_before_mutation(self):
        for issue, artifacts, expected in (
            ("CLOSED", True, True),
            ("OPEN", True, False),
            ("CLOSED", False, False),
        ):
            calls = []
            ports = _ports(calls, issue=issue, artifacts=artifacts)

            result = _observe_zero_mutation_readiness_v1(ports)

            self.assertIs(result.ready(), expected)
            self.assertNotIn("mutation", calls)

    def test_archive_parent_state_is_bound_and_blocked_before_mutation(self):
        results = {}
        for parent_state, expected in (
            ("PROVISIONABLE", True),
            ("READY", True),
            ("BLOCKED", False),
        ):
            calls = []
            ports = _ports(
                calls,
                issue="CLOSED",
                artifacts=True,
                parent_state=parent_state,
            )

            result = _observe_zero_mutation_readiness_v1(ports)

            self.assertIs(result.ready(), expected)
            self.assertEqual(result.archive_parent_state, parent_state)
            self.assertEqual(
                result.archive_parent_fingerprint,
                {"PROVISIONABLE": "1", "READY": "2", "BLOCKED": "0"}[
                    parent_state
                ] * 64,
            )
            self.assertNotIn("mutation", calls)
            results[parent_state] = result.readiness_fingerprint
        self.assertNotEqual(results["PROVISIONABLE"], results["READY"])


def _ports(calls, *, issue, artifacts, parent_state="READY"):
    manifest = _Value(
        manifest_fingerprint="a" * 64,
        final_master_binding_fingerprint="b" * 64,
        final_commit_oid="c" * 40,
        final_tree_oid="d" * 40,
        production_binding_fingerprint="e" * 64,
        issue39_authority_count=0,
        execution_authority_count=0,
        failure_count=0,
    )
    receipt = _Value(
        status="SOLO_MAINTAINER_ATTESTATION_RECORDED",
        manifest_fingerprint="a" * 64,
        receipt_fingerprint="f" * 64,
        final_master_binding_fingerprint="b" * 64,
        final_commit_oid="c" * 40,
        final_tree_oid="d" * 40,
        production_binding_fingerprint="e" * 64,
        issue39_authority_count=0,
        execution_authority_count=0,
    )
    inputs = Issue39ProductionInputsV1(
        Issue39ProductionInputStatusV1.READY, "1" * 64, 31, 1, 38,
        "2" * 64, "3" * 64, 3684, 66855518, "4" * 64,
        "5" * 64, "6" * 64,
    )

    def read_artifacts():
        calls.append("artifacts")
        if not artifacts:
            raise FileNotFoundError
        return b"manifest", b"receipt"

    return _Issue39ZeroReadinessPortsV1(
        lambda: calls.append("current") or manifest,
        read_artifacts, lambda _payload: manifest,
        lambda _payload: receipt, lambda: inputs,
        lambda: "SOURCE_VERIFIED",
        lambda: _archive_parent(
            parent_state,
            {"PROVISIONABLE": "1", "READY": "2", "BLOCKED": "0"}[
                parent_state
            ] * 64,
        ),
        lambda: issue,
    )


if __name__ == "__main__":
    unittest.main()
