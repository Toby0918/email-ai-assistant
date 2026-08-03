"""Reviewed bootstrap reachability for the three executable V2 roots."""

import base64
import hashlib
import io
import inspect
import json
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_evidence_process.bootstrap_v2 import EvidenceProductionBootstrapV2
from backend.r2_evidence_process.production_v2 import (
    EvidenceProductionRoleV2,
    complete_reviewed_evidence_publication_v2,
    main as evidence_main,
)
from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_operator_process import production_authority_message_v2
from backend.r2_preflight_process.bootstrap_v2 import PreflightProductionBootstrapV2
from backend.r2_preflight_process.production_v2 import (
    PREFLIGHT_PRODUCTION_VERBS_V2,
    PreflightProductionRolesV2,
    complete_preflight_read_v2,
    main as preflight_main,
)
from backend.r2_preflight_process.testing import SyntheticPreflightProductionV2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    DurableAuthorityClaimV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionBindingError,
    ProductionRoleV2,
    PublicKeyRoleV2,
    authority_domain_for_command_v2,
    command_production_role_v2,
    production_action_fingerprint_v2,
    production_callable_fingerprint_v2,
    require_reviewed_production_binding_receipt_v2,
    reviewed_production_binding_receipt_v2,
)
from backend.r2_transaction_journal_v2 import R2JournalGenesisV2
from backend.r2_transaction_process.bootstrap_v2 import TransactionProductionBootstrapV2
from backend.r2_transaction_process.production_v2 import (
    TransactionProductionRolesV2,
    complete_transaction_action_v2,
    main as transaction_main,
    transaction_action_fingerprint_v2,
)


NOW = 2_300_000_000
HEAD = "1" * 64
OWNER = "2" * 64
REVIEW = "3" * 64
TRANSITION = "4" * 64
PLAN = "5" * 64
UNBOUND_PLAN = "0" * 64


def _preflight_completion(binding, claim):
    return complete_preflight_read_v2(binding, claim)


def _evidence_completion(binding, claim):
    return complete_reviewed_evidence_publication_v2(
        binding=binding,
        claim=claim,
        reviewed_evidence_fingerprint=REVIEW,
        evidence_identity_fingerprint="6" * 64,
        package_fingerprint="7" * 64,
        manifest_fingerprint="8" * 64,
    )


def _transaction_completion(binding, claim, head, transition, plan):
    return complete_transaction_action_v2(binding, claim, head, transition, plan)


class _Terminal:
    def __init__(self, envelope, acknowledgement):
        self._envelope = envelope
        self._acknowledgement = acknowledgement

    def tty_state(self):
        return True, True, True

    def read_acknowledgement(self):
        return self._acknowledgement

    def read_hidden_envelope(self, maximum):
        return self._envelope[: maximum + 1]


class R2ProductionBootstrapV2Tests(unittest.TestCase):
    def setUp(self):
        self.keys = {role: Ed25519PrivateKey.generate() for role in PublicKeyRoleV2}
        self.binding = _binding(self.keys)
        self.receipt = _review_receipt(self.binding)

    def test_three_main_roots_reach_one_reviewed_role_with_valid_authority(self):
        preflight_roles = PreflightProductionRolesV2.create(
            binding=self.binding,
            **{
                command.value: _preflight_completion
                for command in PREFLIGHT_PRODUCTION_VERBS_V2.values()
            },
        )
        preflight = PreflightProductionBootstrapV2.create(
            binding=self.binding,
            reviewed_binding_receipt=self.receipt,
            roles=preflight_roles,
            durable_claims=(),
            expected_prior_journal_head_fingerprint=HEAD,
        )
        command = ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT
        self.assertEqual(
            _run_main(
                preflight_main,
                ("current-topology",),
                preflight,
                self._terminal(command, production_action_fingerprint_v2(self.binding, command)),
            ),
            "PREFLIGHT_COMPLETE accepted=1 rejected=0 read_operations=1\n",
        )

        evidence_roles = EvidenceProductionRoleV2.create(
            binding=self.binding,
            publish_reviewed_evidence=_evidence_completion,
        )
        evidence = EvidenceProductionBootstrapV2.create(
            binding=self.binding,
            reviewed_binding_receipt=self.receipt,
            role=evidence_roles,
            reviewed_evidence_fingerprint=REVIEW,
            durable_claims=(),
            expected_prior_journal_head_fingerprint=HEAD,
            journal_owner_fingerprint=OWNER,
            genesis_nonce="9" * 64,
        )
        command = ProductionCommandV2.EVIDENCE_PUBLICATION
        self.assertEqual(
            _run_main(
                evidence_main,
                ("publish",),
                evidence,
                self._terminal(
                    command,
                    production_action_fingerprint_v2(
                        self.binding, command, subject_fingerprint=REVIEW
                    ),
                    acknowledgement="ACKNOWLEDGE_R2_EVIDENCE_PUBLICATION",
                ),
            ),
            "EVIDENCE_PUBLISHED accepted=1 rejected=0 published=1\n",
        )

        genesis = _genesis(self.binding)
        transaction_roles = TransactionProductionRolesV2.create(
            binding=self.binding,
            execute=_transaction_completion,
            resume=_transaction_completion,
            rollback=_transaction_completion,
        )
        transaction = TransactionProductionBootstrapV2.create(
            binding=self.binding,
            reviewed_binding_receipt=self.receipt,
            roles=transaction_roles,
            durable_claims=(genesis.authority_claim,),
            current_journal_head_fingerprint=genesis.head_fingerprint,
            transition_instance_fingerprint=TRANSITION,
            remaining_reverse_plan_fingerprint=UNBOUND_PLAN,
        )
        command = ProductionCommandV2.EXECUTE
        action = transaction_action_fingerprint_v2(
            self.binding,
            command,
            journal_head_fingerprint=genesis.head_fingerprint,
            transition_instance_fingerprint=TRANSITION,
            remaining_reverse_plan_fingerprint=UNBOUND_PLAN,
        )
        self.assertEqual(
            _run_main(
                transaction_main,
                ("execute",),
                transaction,
                self._terminal(
                    command,
                    action,
                    prior_head=genesis.head_fingerprint,
                    acknowledgement="ACKNOWLEDGE_R2_TRANSACTION_ACTION",
                ),
            ),
            "TRANSACTION_ACTION_COMPLETE accepted=1 rejected=0 mutations=1\n",
        )

    def test_reviewed_bootstrap_rejects_testing_only_role_bypass(self):
        synthetic = SyntheticPreflightProductionV2.create(
            binding=self.binding,
            observed_at_epoch=lambda: NOW,
        )
        with self.assertRaises(TypeError):
            PreflightProductionBootstrapV2.create(
                binding=self.binding,
                reviewed_binding_receipt=self.receipt,
                roles=synthetic._roles,
                durable_claims=(),
                expected_prior_journal_head_fingerprint=HEAD,
            )

    def test_bootstrap_requires_matching_review_receipt_and_explicit_fields(self):
        roles = PreflightProductionRolesV2.create(
            binding=self.binding,
            **{
                command.value: _preflight_completion
                for command in PREFLIGHT_PRODUCTION_VERBS_V2.values()
            },
        )
        other = _binding({
            role: Ed25519PrivateKey.generate() for role in PublicKeyRoleV2
        })
        other_receipt = _review_receipt(other)
        with self.assertRaises(TypeError):
            PreflightProductionBootstrapV2.create(
                binding=self.binding,
                reviewed_binding_receipt=other_receipt,
                roles=roles,
                durable_claims=(),
                expected_prior_journal_head_fingerprint=HEAD,
            )
        evidence_role = EvidenceProductionRoleV2.create(
            binding=self.binding,
            publish_reviewed_evidence=_evidence_completion,
        )
        with self.assertRaises(TypeError):
            EvidenceProductionBootstrapV2.create(
                binding=self.binding,
                reviewed_binding_receipt=other_receipt,
                role=evidence_role,
                reviewed_evidence_fingerprint=REVIEW,
                durable_claims=(),
                expected_prior_journal_head_fingerprint=HEAD,
                journal_owner_fingerprint=OWNER,
                genesis_nonce="9" * 64,
            )
        transaction_roles = TransactionProductionRolesV2.create(
            binding=self.binding,
            execute=_transaction_completion,
            resume=_transaction_completion,
            rollback=_transaction_completion,
        )
        with self.assertRaises(TypeError):
            TransactionProductionBootstrapV2.create(
                binding=self.binding,
                reviewed_binding_receipt=other_receipt,
                roles=transaction_roles,
                durable_claims=(),
                current_journal_head_fingerprint=HEAD,
                transition_instance_fingerprint=TRANSITION,
                remaining_reverse_plan_fingerprint=UNBOUND_PLAN,
            )
        for bootstrap_type in (
            PreflightProductionBootstrapV2,
            EvidenceProductionBootstrapV2,
            TransactionProductionBootstrapV2,
        ):
            parameters = inspect.signature(bootstrap_type.create).parameters.values()
            self.assertFalse(any(
                item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters
            ))
            self.assertIn(
                "reviewed_binding_receipt",
                inspect.signature(bootstrap_type.create).parameters,
            )

    def test_main_has_no_terminal_or_clock_injection_surface(self):
        for main in (preflight_main, evidence_main, transaction_main):
            parameters = inspect.signature(main).parameters
            self.assertNotIn("terminal", parameters)
            self.assertNotIn("observed_at_epoch", parameters)

    def test_main_rejects_wrong_bootstrap_type_without_touching_system_tty(self):
        cases = (
            (preflight_main, ("current-topology",),
             "BLOCKED_COMPOSITION accepted=0 rejected=1 read_operations=0\n"),
            (evidence_main, ("publish",),
             "BLOCKED_PUBLICATION accepted=0 rejected=1 published=0\n"),
            (transaction_main, ("execute",),
             "BLOCKED_ACTION accepted=0 rejected=1 mutations=0\n"),
        )
        for main, argv, expected in cases:
            output = io.StringIO()
            with redirect_stdout(output):
                code = main(argv=argv, bootstrap=object())
            self.assertEqual(code, 0)
            self.assertEqual(output.getvalue(), expected)

    def test_tampered_review_receipt_cannot_open_any_bootstrap(self):
        replacements = {
            "receipt_type": "FORGED",
            "production_composition_evidence_fingerprint": "0" * 64,
            "verified": 0,
            "receipt_fingerprint": "1" * 64,
        }
        for field, replacement in replacements.items():
            original = getattr(self.receipt, field)
            try:
                object.__setattr__(self.receipt, field, replacement)
                with self.assertRaises(ProductionBindingError):
                    require_reviewed_production_binding_receipt_v2(
                        self.binding, self.receipt
                    )
            finally:
                object.__setattr__(self.receipt, field, original)

    def _terminal(
        self,
        command,
        action,
        *,
        prior_head=HEAD,
        acknowledgement="ACKNOWLEDGE_R2_PREFLIGHT",
    ):
        domain = authority_domain_for_command_v2(command)
        operator = {
            "preflight": OperatorRoleV2.PREFLIGHT_OPERATOR,
            "evidence": OperatorRoleV2.EVIDENCE_OPERATOR,
            "execution": OperatorRoleV2.EXECUTION_OPERATOR,
            "recovery": OperatorRoleV2.RECOVERY_OPERATOR,
        }[domain.value]
        key_role = {
            "preflight": PublicKeyRoleV2.PREFLIGHT_VERIFICATION,
            "evidence": PublicKeyRoleV2.EVIDENCE_VERIFICATION,
            "execution": PublicKeyRoleV2.EXECUTION_VERIFICATION,
            "recovery": PublicKeyRoleV2.RECOVERY_VERIFICATION,
        }[domain.value]
        body = {
            "envelope_type": "R2ProductionAuthorityEnvelopeV2",
            "binding_fingerprint": self.binding.binding_fingerprint,
            "final_master_binding_fingerprint": self.binding.final_master_binding_fingerprint,
            "operation_fingerprint": self.binding.operation_fingerprint,
            "command": command.value,
            "domain": domain.value,
            "operator_role": operator.value,
            "operator_fingerprint": dict(self.binding.operator_role_fingerprints)[operator],
            "public_key_role": key_role.value,
            "action_fingerprint": action,
            "envelope_nonce": hashlib.sha256(command.value.encode()).hexdigest(),
            "journal_owner_fingerprint": OWNER,
            "prior_journal_head_fingerprint": prior_head,
            "claim_sequence": (
                2
                if command in {
                    ProductionCommandV2.EXECUTE,
                    ProductionCommandV2.RESUME,
                    ProductionCommandV2.ROLLBACK,
                }
                else 1
            ),
            "issued_at_epoch": NOW - 20,
            "not_before_epoch": NOW - 10,
            "expires_at_epoch": NOW + 60,
        }
        authority = hashlib.sha256(
            b"r2-production-authority-v2\0" + _json(body)
        ).hexdigest()
        signed = {**body, "authority_fingerprint": authority}
        signature = self.keys[key_role].sign(production_authority_message_v2(signed))
        envelope = base64.b64encode(
            _json({**signed, "signature": base64.b64encode(signature).decode("ascii")})
        ).decode("ascii")
        return _Terminal(envelope, acknowledgement)


def _run_main(main, argv, bootstrap, terminal):
    output = io.StringIO()
    module = main.__module__.replace(".production_v2", ".bootstrap_v2")
    with (
        patch(f"{module}.SystemTerminal", return_value=terminal),
        patch(f"{module}._current_epoch", return_value=NOW),
        redirect_stdout(output),
    ):
        code = main(argv=argv, bootstrap=bootstrap)
    if code != 0:
        raise AssertionError(code)
    return output.getvalue()


def _binding(keys):
    callbacks = {
        **{
            command: _preflight_completion
            for command in tuple(ProductionCommandV2)[:6]
        },
        ProductionCommandV2.EVIDENCE_PUBLICATION: _evidence_completion,
        ProductionCommandV2.EXECUTE: _transaction_completion,
        ProductionCommandV2.RESUME: _transaction_completion,
        ProductionCommandV2.ROLLBACK: _transaction_completion,
    }
    roles = {
        role: hashlib.sha256(("role:" + role.value).encode()).hexdigest()
        for role in ProductionRoleV2
    }
    for command, callback in callbacks.items():
        roles[command_production_role_v2(command)] = (
            production_callable_fingerprint_v2(command, callback)
        )
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
        operator_role_fingerprints={
            role: hashlib.sha256(("operator:" + role.value).encode()).hexdigest()
            for role in OperatorRoleV2
        },
        verification_public_keys={
            role: keys[role].public_key().public_bytes_raw()
            for role in PublicKeyRoleV2
        },
        production_role_fingerprints=roles,
    )


def _review_receipt(binding):
    final = FinalMasterBindingV1.create(
        final_commit_oid=binding.final_commit_oid,
        final_tree_oid=binding.final_tree_oid,
        source_package_fingerprint=binding.source_package_fingerprint,
        runbook_fingerprint=binding.runbook_fingerprint,
        workflow_fingerprint=binding.workflow_fingerprint,
    )
    return reviewed_production_binding_receipt_v2(final, binding)


def _genesis(binding):
    claim = DurableAuthorityClaimV2.create(
        binding=binding,
        command=ProductionCommandV2.EVIDENCE_PUBLICATION,
        action_fingerprint=production_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EVIDENCE_PUBLICATION,
            subject_fingerprint=REVIEW,
        ),
        authority_fingerprint="a" * 64,
        envelope_nonce="b" * 64,
        journal_owner_fingerprint=OWNER,
        prior_journal_head_fingerprint=HEAD,
        claim_sequence=1,
        issued_at_epoch=NOW - 100,
        not_before_epoch=NOW - 90,
        expires_at_epoch=NOW - 10,
        claimed_at_epoch=NOW - 80,
    )
    return R2JournalGenesisV2.create(
        binding=binding,
        reviewed_evidence_fingerprint=REVIEW,
        evidence_identity_fingerprint="6" * 64,
        package_fingerprint="7" * 64,
        manifest_fingerprint="8" * 64,
        journal_owner_fingerprint=OWNER,
        genesis_nonce="9" * 64,
        pre_genesis_head_fingerprint=HEAD,
        authority_claim=claim,
    )


def _json(value):
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


if __name__ == "__main__":
    unittest.main()
