"""V2 evidence publication and journal-genesis contract for Issue #89."""

from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_evidence_process.production_v2 import (
    EvidenceProductionStatusV2,
    dormant_evidence_production_v2,
)
from backend.r2_evidence_process.testing import SyntheticEvidenceProductionV2
from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_operator_process import production_authority_message_v2
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
    production_action_fingerprint_v2,
)
from backend.r2_transaction_journal_v2 import JournalGenesisError, R2JournalGenesisV2


NOW = 2_100_000_000
PRE_GENESIS_HEAD = "7" * 64
REVIEW = "8" * 64
EVIDENCE_IDENTITY = "9" * 64
PACKAGE = "a" * 64
MANIFEST = "b" * 64


class _Terminal:
    def __init__(self, envelope: str) -> None:
        self.envelope = envelope
        self.reads = 0

    def tty_state(self):
        return True, True, True

    def read_acknowledgement(self):
        self.reads += 1
        return "ACKNOWLEDGE_R2_EVIDENCE_PUBLICATION"

    def read_hidden_envelope(self, maximum):
        self.reads += 1
        return self.envelope[: maximum + 1]


class R2EvidenceProductionV2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.keys = {role: Ed25519PrivateKey.generate() for role in PublicKeyRoleV2}
        self.binding = _binding(self.keys)

    def test_publish_is_create_only_and_emits_reconstructible_bound_genesis(self):
        calls = 0
        with tempfile.TemporaryDirectory(prefix="r2-evidence-v2-") as raw:
            target = Path(raw) / "reviewed.evidence"

            def publish() -> int:
                nonlocal calls
                calls += 1
                with target.open("xb") as stream:
                    stream.write(b"SYNTHETIC_REVIEWED_EVIDENCE_V2\n")
                return 1

            process = self._process(publish)
            result = process.run(
                argv=("publish",),
                terminal=_Terminal(self._envelope()),
            )
            self.assertEqual(target.read_bytes(), b"SYNTHETIC_REVIEWED_EVIDENCE_V2\n")

        self.assertIs(result.status, EvidenceProductionStatusV2.PUBLISHED)
        self.assertEqual(result.counts(), (1, 0, 1))
        self.assertEqual(calls, 1)
        self.assertEqual(result.evidence_identity_fingerprint, EVIDENCE_IDENTITY)
        genesis = process.genesis
        reconstructed = R2JournalGenesisV2.from_json(
            genesis.to_canonical_json(),
            binding=self.binding,
        )
        self.assertEqual(reconstructed, genesis)
        self.assertEqual(
            reconstructed.final_master_binding_fingerprint,
            self.binding.final_master_binding_fingerprint,
        )
        self.assertEqual(reconstructed.evidence_identity_fingerprint, EVIDENCE_IDENTITY)
        self.assertEqual(reconstructed.authority_claim.command, ProductionCommandV2.EVIDENCE_PUBLICATION)
        self.assertEqual(result.genesis_head_fingerprint, reconstructed.head_fingerprint)
        tampered = genesis.to_mapping()
        tampered["head_fingerprint"] = "0" * 64
        with self.assertRaisesRegex(JournalGenesisError, "R2_JOURNAL_GENESIS_INVALID"):
            R2JournalGenesisV2.from_json(
                _canonical_json(tampered),
                binding=self.binding,
            )

    def test_fresh_process_reconstruction_rejects_same_authority_before_publish(self):
        first = self._process(lambda: 1)
        envelope = self._envelope()
        result = first.run(argv=("publish",), terminal=_Terminal(envelope))
        self.assertIs(result.status, EvidenceProductionStatusV2.PUBLISHED)
        reconstructed = R2JournalGenesisV2.from_json(
            first.genesis.to_canonical_json(), binding=self.binding
        )
        calls = 0

        def publish_again() -> int:
            nonlocal calls
            calls += 1
            return 1

        restarted = self._process(publish_again, genesis=reconstructed)
        replay = restarted.run(argv=("publish",), terminal=_Terminal(envelope))
        self.assertIs(replay.status, EvidenceProductionStatusV2.BLOCKED_AUTHORITY)
        self.assertEqual(replay.counts(), (0, 1, 0))
        self.assertEqual(calls, 0)

    def test_wrong_review_binding_domain_and_freshness_precede_publication(self):
        cases = (
            self._envelope(review="c" * 64),
            self._envelope(binding="d" * 64),
            self._envelope(domain="preflight"),
            self._envelope(expires=NOW),
        )
        for envelope in cases:
            calls = []
            process = self._process(lambda: calls.append(1) or 1)
            result = process.run(argv=("publish",), terminal=_Terminal(envelope))
            with self.subTest(suffix=envelope[-12:]):
                self.assertIs(result.status, EvidenceProductionStatusV2.BLOCKED_AUTHORITY)
                self.assertEqual(calls, [])
                self.assertIsNone(process.genesis)

    def test_single_command_and_no_issuer_entry_are_dormant(self):
        for argv in ((), ("verify",), ("publish", "path"), ("--force",)):
            result = dormant_evidence_production_v2(argv=argv)
            self.assertIs(result.status, EvidenceProductionStatusV2.BLOCKED_COMMAND)
            self.assertEqual(result.counts(), (0, 1, 0))
        result = dormant_evidence_production_v2(argv=("publish",))
        self.assertIs(
            result.status,
            EvidenceProductionStatusV2.DORMANT_NO_EXTERNAL_ISSUER,
        )
        self.assertEqual(result.counts(), (0, 0, 0))

    def _process(self, publish, *, genesis=None):
        return SyntheticEvidenceProductionV2.create(
            binding=self.binding,
            reviewed_evidence_fingerprint=REVIEW,
            evidence_identity_fingerprint=EVIDENCE_IDENTITY,
            package_fingerprint=PACKAGE,
            manifest_fingerprint=MANIFEST,
            journal_owner_fingerprint="6" * 64,
            genesis_nonce="5" * 64,
            pre_genesis_head_fingerprint=PRE_GENESIS_HEAD,
            observed_at_epoch=lambda: NOW,
            create_only_publish=publish,
            reconstructed_genesis=genesis,
        )

    def _envelope(self, *, review=REVIEW, binding=None, domain="evidence", expires=None):
        command = ProductionCommandV2.EVIDENCE_PUBLICATION
        body = _authority_body(
            self.binding,
            command,
            reviewed_evidence_fingerprint=review,
            binding_fingerprint=binding,
            domain=domain,
            expires_at_epoch=expires,
        )
        signature = self.keys[PublicKeyRoleV2.EVIDENCE_VERIFICATION].sign(
            production_authority_message_v2(body)
        )
        payload = _canonical_json(
            {**body, "signature": base64.b64encode(signature).decode("ascii")}
        )
        return base64.b64encode(payload).decode("ascii")


def _binding(keys) -> ApprovedCutoverBindingV2:
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


def _authority_body(binding, command, *, reviewed_evidence_fingerprint, binding_fingerprint, domain, expires_at_epoch):
    operator = OperatorRoleV2.EVIDENCE_OPERATOR
    key_role = PublicKeyRoleV2.EVIDENCE_VERIFICATION
    body = {
        "envelope_type": "R2ProductionAuthorityEnvelopeV2",
        "binding_fingerprint": binding_fingerprint or binding.binding_fingerprint,
        "final_master_binding_fingerprint": binding.final_master_binding_fingerprint,
        "operation_fingerprint": binding.operation_fingerprint,
        "command": command.value,
        "domain": domain,
        "operator_role": operator.value,
        "operator_fingerprint": dict(binding.operator_role_fingerprints)[operator],
        "public_key_role": key_role.value,
        "action_fingerprint": production_action_fingerprint_v2(
            binding, command, subject_fingerprint=reviewed_evidence_fingerprint
        ),
        "envelope_nonce": "c" * 64,
        "journal_owner_fingerprint": "6" * 64,
        "prior_journal_head_fingerprint": PRE_GENESIS_HEAD,
        "claim_sequence": 1,
        "issued_at_epoch": NOW - 20,
        "not_before_epoch": NOW - 10,
        "expires_at_epoch": expires_at_epoch or NOW + 60,
    }
    authority = hashlib.sha256(
        b"r2-production-authority-v2\0" + _canonical_json(body)
    ).hexdigest()
    return {**body, "authority_fingerprint": authority}


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
