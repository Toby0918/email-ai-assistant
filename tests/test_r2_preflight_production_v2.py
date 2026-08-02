"""Production V2 reachability and dormancy contract for Issue #88."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_operator_process.production_v2 import production_authority_message_v2
from backend.r2_preflight_process.production_v2 import (
    PREFLIGHT_PRODUCTION_VERBS_V2,
    PreflightProductionStatusV2,
    dormant_preflight_production_v2,
)
from backend.r2_preflight_process.testing import SyntheticPreflightProductionV2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
    production_action_fingerprint_v2,
)


NOW = 2_000_000_000
HEAD = "7" * 64


class _Terminal:
    def __init__(self, envelope: str) -> None:
        self.envelope = envelope
        self.reads = 0

    def tty_state(self):
        return True, True, True

    def read_acknowledgement(self):
        self.reads += 1
        return "ACKNOWLEDGE_R2_PREFLIGHT"

    def read_hidden_envelope(self, maximum):
        self.reads += 1
        return self.envelope[: maximum + 1]


class R2PreflightProductionV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.keys = {role: Ed25519PrivateKey.generate() for role in PublicKeyRoleV2}
        self.binding = _binding(self.keys)

    def test_exact_six_verbs_reach_exactly_one_complete_read_only_role(self):
        self.assertEqual(
            PREFLIGHT_PRODUCTION_VERBS_V2,
            {
                "current-topology": ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
                "host-baseline": ProductionCommandV2.HOST_BASELINE,
                "evidence-review": ProductionCommandV2.EVIDENCE_REVIEW,
                "evidence-verification": ProductionCommandV2.EVIDENCE_VERIFICATION,
                "final-audit-readiness": ProductionCommandV2.FINAL_AUDIT_READINESS,
                "recovery-inspection": ProductionCommandV2.RECOVERY_INSPECTION,
            },
        )
        for index, (verb, command) in enumerate(
            PREFLIGHT_PRODUCTION_VERBS_V2.items(), start=1
        ):
            process = SyntheticPreflightProductionV2.create(
                binding=self.binding,
                observed_at_epoch=lambda: NOW,
            )
            result = process.run(
                argv=(verb,),
                terminal=_Terminal(self._envelope(command, nonce=index)),
                durable_claims=(),
                expected_prior_journal_head_fingerprint=HEAD,
            )
            with self.subTest(verb=verb):
                self.assertIs(result.status, PreflightProductionStatusV2.COMPLETED)
                self.assertEqual(result.counts(), (1, 0, 1))
                self.assertEqual(process.role_invocations(command), 1)
                self.assertEqual(process.total_role_invocations, 1)

    def test_wrong_binding_domain_verb_and_staleness_fail_before_any_role(self):
        command = ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT
        cases = (
            ("current-topology", self._envelope(command, nonce=10, binding="a" * 64)),
            ("current-topology", self._envelope(command, nonce=11, domain="evidence")),
            ("host-baseline", self._envelope(command, nonce=12)),
            ("current-topology", self._envelope(command, nonce=13, expires=NOW)),
        )
        for verb, envelope in cases:
            process = SyntheticPreflightProductionV2.create(
                binding=self.binding,
                observed_at_epoch=lambda: NOW,
            )
            result = process.run(
                argv=(verb,),
                terminal=_Terminal(envelope),
                durable_claims=(),
                expected_prior_journal_head_fingerprint=HEAD,
            )
            with self.subTest(verb=verb, suffix=envelope[-12:]):
                self.assertIs(
                    result.status,
                    PreflightProductionStatusV2.BLOCKED_AUTHORITY,
                )
                self.assertEqual(result.counts(), (0, 1, 0))
                self.assertEqual(process.total_role_invocations, 0)

    def test_command_surface_and_no_issuer_entry_are_dormant_and_content_free(self):
        for argv in ((), ("execute",), ("current-topology", "path"), ("--force",)):
            result = dormant_preflight_production_v2(argv=argv)
            self.assertIs(result.status, PreflightProductionStatusV2.BLOCKED_COMMAND)
            self.assertEqual(result.counts(), (0, 1, 0))

        result = dormant_preflight_production_v2(argv=("current-topology",))
        self.assertIs(
            result.status,
            PreflightProductionStatusV2.DORMANT_NO_EXTERNAL_ISSUER,
        )
        self.assertEqual(result.counts(), (0, 0, 0))
        public = f"{result!r} {result.to_mapping()}"
        for forbidden in ("path", "private", "payload", HEAD, self.binding.binding_fingerprint):
            self.assertNotIn(forbidden, public.lower())

    def _envelope(self, command, *, nonce, binding=None, domain="preflight", expires=None):
        body = _authority_body(
            self.binding,
            command,
            nonce=nonce,
            binding_fingerprint=binding,
            domain=domain,
            expires_at_epoch=expires,
        )
        signature = self.keys[PublicKeyRoleV2.PREFLIGHT_VERIFICATION].sign(
            production_authority_message_v2(body)
        )
        payload = _canonical_json(
            {**body, "signature": base64.b64encode(signature).decode("ascii")}
        )
        return base64.b64encode(payload).decode("ascii")


def _binding(keys) -> ApprovedCutoverBindingV2:
    final_master = FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final_master,
        operation_fingerprint="f" * 64,
        operator_role_fingerprints={
            role: f"{index + 10:064x}" for index, role in enumerate(OperatorRoleV2)
        },
        verification_public_keys={
            role: keys[role].public_key().public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            for role in PublicKeyRoleV2
        },
        production_role_fingerprints={
            role: f"{index + 30:064x}" for index, role in enumerate(ProductionRoleV2)
        },
    )


def _authority_body(binding, command, *, nonce, binding_fingerprint, domain, expires_at_epoch):
    operator_fingerprints = dict(binding.operator_role_fingerprints)
    body = {
        "envelope_type": "R2ProductionAuthorityEnvelopeV2",
        "binding_fingerprint": binding_fingerprint or binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "operation_fingerprint": binding.operation_fingerprint,
        "command": command.value,
        "domain": domain,
        "operator_role": OperatorRoleV2.PREFLIGHT_OPERATOR.value,
        "operator_fingerprint": operator_fingerprints[OperatorRoleV2.PREFLIGHT_OPERATOR],
        "public_key_role": PublicKeyRoleV2.PREFLIGHT_VERIFICATION.value,
        "action_fingerprint": production_action_fingerprint_v2(binding, command),
        "envelope_nonce": f"{nonce + 100:064x}",
        "journal_owner_fingerprint": "6" * 64,
        "prior_journal_head_fingerprint": HEAD,
        "claim_sequence": 1,
        "issued_at_epoch": NOW - 20,
        "not_before_epoch": NOW - 10,
        "expires_at_epoch": expires_at_epoch or NOW + 60,
    }
    authority_fingerprint = hashlib.sha256(
        b"r2-production-authority-v2\0" + _canonical_json(body)
    ).hexdigest()
    return {**body, "authority_fingerprint": authority_fingerprint}


def _canonical_json(value):
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


if __name__ == "__main__":
    unittest.main()
