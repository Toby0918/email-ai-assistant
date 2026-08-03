"""Single-action V2 transaction process contract for Issue #90."""

from __future__ import annotations

import base64
import hashlib
import json
import unittest

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_operator_process import production_authority_message_v2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
    production_action_fingerprint_v2,
)
from backend.r2_transaction_journal_v2 import R2JournalGenesisV2
from backend.r2_transaction_process.production_v2 import (
    TRANSACTION_PRODUCTION_VERBS_V2,
    TransactionProductionStatusV2,
    dormant_transaction_production_v2,
    transaction_action_fingerprint_v2,
)
from backend.r2_transaction_process.testing import SyntheticTransactionProductionV2


NOW = 2_200_000_000
PRE_GENESIS_HEAD = "1" * 64
OWNER = "2" * 64
TRANSITION = "3" * 64
PLAN = "4" * 64
UNBOUND_PLAN = "0" * 64


class _Terminal:
    def __init__(self, envelope: str) -> None:
        self.envelope = envelope

    def tty_state(self):
        return True, True, True

    def read_acknowledgement(self):
        return "ACKNOWLEDGE_R2_TRANSACTION_ACTION"

    def read_hidden_envelope(self, maximum):
        return self.envelope[: maximum + 1]


class R2TransactionProductionV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.keys = {role: Ed25519PrivateKey.generate() for role in PublicKeyRoleV2}
        self.binding = _binding(self.keys)
        self.genesis = _genesis(self.binding)

    def test_execute_resume_and_rollback_each_acquire_exactly_one_bound_action(self):
        self.assertEqual(
            TRANSACTION_PRODUCTION_VERBS_V2,
            {
                "execute": ProductionCommandV2.EXECUTE,
                "resume": ProductionCommandV2.RESUME,
                "rollback": ProductionCommandV2.ROLLBACK,
            },
        )
        for index, (verb, command) in enumerate(
            TRANSACTION_PRODUCTION_VERBS_V2.items(), start=1
        ):
            calls = []
            process = self._process(
                execute=lambda: calls.append("execute") or 1,
                resume=lambda: calls.append("resume") or 1,
                rollback=lambda: calls.append("rollback") or 1,
            )
            result = process.run(
                argv=(verb,),
                terminal=_Terminal(self._envelope(command, nonce=index)),
            )
            with self.subTest(verb=verb):
                self.assertIs(result.status, TransactionProductionStatusV2.ACTION_COMPLETE)
                self.assertEqual(result.counts(), (1, 0, 1))
                self.assertEqual(calls, [verb])
                self.assertEqual(process.total_action_acquisitions, 1)
                self.assertEqual(result.command, command)
                self.assertEqual(result.prior_journal_head_fingerprint, self.genesis.head_fingerprint)

    def test_action_domain_binding_and_head_mismatch_fail_before_action(self):
        command = ProductionCommandV2.RESUME
        cases = (
            self._envelope(command, nonce=10, transition="5" * 64),
            self._envelope(command, nonce=11, domain="recovery"),
            self._envelope(command, nonce=12, binding="6" * 64),
            self._envelope(command, nonce=13, prior_head="7" * 64),
        )
        for envelope in cases:
            calls = []
            process = self._process(
                execute=lambda: calls.append("execute") or 1,
                resume=lambda: calls.append("resume") or 1,
                rollback=lambda: calls.append("rollback") or 1,
            )
            result = process.run(argv=("resume",), terminal=_Terminal(envelope))
            with self.subTest(suffix=envelope[-12:]):
                self.assertIs(result.status, TransactionProductionStatusV2.BLOCKED_AUTHORITY)
                self.assertEqual(result.counts(), (0, 1, 0))
                self.assertEqual(calls, [])
                self.assertEqual(process.total_action_acquisitions, 0)

    def test_one_invocation_never_retries_or_runs_a_second_action(self):
        calls = []
        process = self._process(
            execute=lambda: calls.append("execute") or 2,
            resume=lambda: calls.append("resume") or 1,
            rollback=lambda: calls.append("rollback") or 1,
        )
        result = process.run(
            argv=("execute",),
            terminal=_Terminal(self._envelope(ProductionCommandV2.EXECUTE, nonce=20)),
        )
        self.assertIs(result.status, TransactionProductionStatusV2.BLOCKED_ACTION)
        self.assertEqual(result.counts(), (0, 1, 0))
        self.assertEqual(calls, ["execute"])
        self.assertEqual(process.total_action_acquisitions, 1)

    def test_command_surface_and_no_issuer_entry_are_dormant(self):
        for argv in ((), ("publish",), ("execute", "path"), ("--force",)):
            result = dormant_transaction_production_v2(argv=argv)
            self.assertIs(result.status, TransactionProductionStatusV2.BLOCKED_COMMAND)
            self.assertEqual(result.counts(), (0, 1, 0))
        result = dormant_transaction_production_v2(argv=("execute",))
        self.assertIs(
            result.status,
            TransactionProductionStatusV2.DORMANT_NO_EXTERNAL_ISSUER,
        )
        self.assertEqual(result.counts(), (0, 0, 0))

    def _process(self, **actions):
        return SyntheticTransactionProductionV2.create(
            binding=self.binding,
            reconstructed_genesis=self.genesis,
            transition_instance_fingerprint=TRANSITION,
            remaining_reverse_plan_fingerprint=PLAN,
            observed_at_epoch=lambda: NOW,
            **actions,
        )

    def _envelope(
        self,
        command,
        *,
        nonce,
        transition=TRANSITION,
        domain=None,
        binding=None,
        prior_head=None,
    ):
        recovery = command is ProductionCommandV2.ROLLBACK
        domain_value = domain or ("recovery" if recovery else "execution")
        operator = (
            OperatorRoleV2.RECOVERY_OPERATOR
            if recovery
            else OperatorRoleV2.EXECUTION_OPERATOR
        )
        key_role = (
            PublicKeyRoleV2.RECOVERY_VERIFICATION
            if recovery
            else PublicKeyRoleV2.EXECUTION_VERIFICATION
        )
        head = prior_head or self.genesis.head_fingerprint
        plan = PLAN if recovery else UNBOUND_PLAN
        action = transaction_action_fingerprint_v2(
            self.binding,
            command,
            journal_head_fingerprint=head,
            transition_instance_fingerprint=transition,
            remaining_reverse_plan_fingerprint=plan,
        )
        body = {
            "envelope_type": "R2ProductionAuthorityEnvelopeV2",
            "binding_fingerprint": binding or self.binding.binding_fingerprint,
            "final_master_binding_fingerprint": self.binding.final_master_binding_fingerprint,
            "operation_fingerprint": self.binding.operation_fingerprint,
            "command": command.value,
            "domain": domain_value,
            "operator_role": operator.value,
            "operator_fingerprint": dict(self.binding.operator_role_fingerprints)[operator],
            "public_key_role": key_role.value,
            "action_fingerprint": action,
            "envelope_nonce": f"{nonce + 100:064x}",
            "journal_owner_fingerprint": OWNER,
            "prior_journal_head_fingerprint": head,
            "claim_sequence": 2,
            "issued_at_epoch": NOW - 20,
            "not_before_epoch": NOW - 10,
            "expires_at_epoch": NOW + 60,
        }
        authority = hashlib.sha256(
            b"r2-production-authority-v2\0" + _canonical_json(body)
        ).hexdigest()
        signed = {**body, "authority_fingerprint": authority}
        signature = self.keys[key_role].sign(production_authority_message_v2(signed))
        payload = _canonical_json(
            {**signed, "signature": base64.b64encode(signature).decode("ascii")}
        )
        return base64.b64encode(payload).decode("ascii")


def _genesis(binding):
    evidence_claim = DurableAuthorityClaimV2.create(
        binding=binding,
        command=ProductionCommandV2.EVIDENCE_PUBLICATION,
        action_fingerprint=production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint="8" * 64,
        ),
        authority_fingerprint="9" * 64,
        envelope_nonce="a" * 64,
        journal_owner_fingerprint=OWNER,
        prior_journal_head_fingerprint=PRE_GENESIS_HEAD,
        claim_sequence=1,
        issued_at_epoch=NOW - 100,
        not_before_epoch=NOW - 90,
        expires_at_epoch=NOW - 10,
        claimed_at_epoch=NOW - 80,
    )
    return R2JournalGenesisV2.create(
        binding=binding,
        reviewed_evidence_fingerprint="8" * 64,
        evidence_identity_fingerprint="b" * 64,
        package_fingerprint="c" * 64,
        manifest_fingerprint="d" * 64,
        journal_owner_fingerprint=OWNER,
        genesis_nonce="e" * 64,
        pre_genesis_head_fingerprint=PRE_GENESIS_HEAD,
        authority_claim=evidence_claim,
    )


def _binding(keys):
    final_master = FinalMasterBindingV1.create(
        final_commit_oid="1" * 40,
        final_tree_oid="2" * 40,
        source_package_fingerprint="3" * 64,
        runbook_fingerprint="4" * 64,
        workflow_fingerprint="5" * 64,
    )
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final_master,
        operation_fingerprint="f" * 64,
        operator_role_fingerprints={
            role: f"{index + 10:064x}" for index, role in enumerate(OperatorRoleV2)
        },
        verification_public_keys={
            role: keys[role].public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw,
            )
            for role in PublicKeyRoleV2
        },
        production_role_fingerprints={
            role: f"{index + 30:064x}" for index, role in enumerate(ProductionRoleV2)
        },
    )


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
