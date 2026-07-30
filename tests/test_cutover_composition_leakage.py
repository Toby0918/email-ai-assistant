"""Cross-surface output leakage tests for Issue #59 compositions."""

from __future__ import annotations

import contextlib
import io
import json
import logging
import unittest

from backend.cutover_composition_contracts import CompositionContractError
from backend.real_host_preflight_composition import RealHostPreflightRolesV1
from tests.cutover_composition_binders import (
    TestOwnedCompositionScopeV1,
    bind_test_preflight,
)
from tests.cutover_composition_fixtures import OBSERVED_AT, synthetic_context
from tests.test_cutover_transaction_composition_root import _success_chain


FORBIDDEN = (
    r"D:\Projects\secret-customer",
    "S-1-5-21-111-222-333-444",
    "O:BAG:SYD:(A;;FA;;;SY)",
    "refs/heads/customer-contract",
    "worktree-private-name",
    "git worktree move",
    "PowerShell -EncodedCommand",
    "Traceback (most recent call last)",
    "credential=top-secret",
    "mailbox@example.test",
    "provider-private-payload",
    "vault-plaintext",
    "private customer content",
    "database row: Alice",
    "unexpected_dynamic_field",
)


class CutoverCompositionLeakageTests(unittest.TestCase):
    def test_receipt_chain_repr_json_stdout_and_logs_are_content_free(
        self,
    ) -> None:
        _profile, _sequence, binding = synthetic_context()
        chain = _success_chain(binding)
        rendered = json.dumps(chain.to_mapping(), sort_keys=True)
        surfaces = (rendered, repr(chain), repr(chain.receipts))

        for secret in FORBIDDEN:
            with self.subTest(secret=secret):
                self.assertTrue(all(secret not in surface for surface in surfaces))

    def test_hostile_adapter_exception_is_replaced_and_not_emitted(self) -> None:
        _profile, sequence, binding = synthetic_context()
        secret = " | ".join(FORBIDDEN)

        def hostile(_prior):
            raise RuntimeError(secret)

        roles = RealHostPreflightRolesV1(
            binding_fingerprint=binding.binding_fingerprint,
            current_topology=hostile,
            host_baseline=hostile,
            evidence_review=hostile,
            evidence_verification=hostile,
            final_audit_readiness=hostile,
            recovery_inspection=hostile,
        )
        scope = TestOwnedCompositionScopeV1.create()
        self.addCleanup(scope.close)
        composition = bind_test_preflight(
            scope=scope,
            binding=binding,
            authorization_sequence=sequence,
            roles=roles,
            observed_at_epoch=OBSERVED_AT,
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        logs = io.StringIO()
        handler = logging.StreamHandler(logs)
        root = logging.getLogger()
        root.addHandler(handler)
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(
                stderr
            ), self.assertRaisesRegex(
                CompositionContractError,
                "^REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED$",
            ) as raised:
                composition.run_current_topology()
        finally:
            root.removeHandler(handler)

        public = " ".join(
            (
                str(raised.exception),
                repr(raised.exception),
                stdout.getvalue(),
                stderr.getvalue(),
                logs.getvalue(),
            )
        )
        for forbidden in FORBIDDEN:
            self.assertNotIn(forbidden, public)


if __name__ == "__main__":
    unittest.main()
