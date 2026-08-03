"""Public process and authorization behavior for Issue #71."""

from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    authorization_envelope_message,
)
from backend.r2_preflight_process import (
    PREFLIGHT_ACKNOWLEDGEMENT,
    PREFLIGHT_VERBS,
    PreflightProcessStatus,
)
from backend.r2_preflight_process.testing import (
    SyntheticPreflightProcess,
)
from tests.cutover_composition_fixtures import synthetic_context
from tests.cutover_contract_fixtures import opaque_fingerprint


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(7100)


class _Terminal:
    def __init__(
        self,
        *,
        tty: tuple[bool, bool, bool] = (True, True, True),
        acknowledgement: str = PREFLIGHT_ACKNOWLEDGEMENT,
        envelope: str = "",
    ) -> None:
        self.tty = tty
        self.acknowledgement = acknowledgement
        self.envelope = envelope
        self.ack_reads = 0
        self.envelope_reads = 0

    def tty_state(self) -> tuple[bool, bool, bool]:
        return self.tty

    def read_acknowledgement(self) -> str:
        self.ack_reads += 1
        return self.acknowledgement

    def read_hidden_envelope(self, maximum: int) -> str:
        self.envelope_reads += 1
        return self.envelope[: maximum + 1]


class R2PreflightProcessTests(unittest.TestCase):
    def setUp(self) -> None:
        profile, sequence, _binding = synthetic_context(
            operation_fingerprint=OPERATION
        )
        self.profile = profile
        self.binding = ApprovedCutoverBindingV1.create(
            profile=profile,
            operation_fingerprint=OPERATION,
            authorization_sequence=sequence,
        )
        self.preflight_key = Ed25519PrivateKey.generate()
        self.evidence_key = Ed25519PrivateKey.generate()

    def test_only_six_fixed_preflight_verbs_exist(self) -> None:
        self.assertEqual(
            PREFLIGHT_VERBS,
            {
                "current-topology": "current_topology_preflight",
                "host-baseline": "host_baseline",
                "evidence-review": "evidence_review",
                "evidence-verification": "evidence_verification",
                "final-audit-readiness": "final_audit_readiness",
                "recovery-inspection": "recovery_inspection",
            },
        )

    def test_command_surface_rejects_missing_extra_and_free_form_values(self) -> None:
        process = self._process()
        hostile = (
            (),
            ("execute",),
            ("current-topology", "D:\\synthetic"),
            ("--profile",),
            ("--authorization", "value"),
            ("--journal", "value"),
            ("--recovery",),
            ("--force",),
        )
        for argv in hostile:
            terminal = _Terminal()
            with self.subTest(argv=argv):
                result = process.run(argv=argv, terminal=terminal)
                self.assertIs(result.status, PreflightProcessStatus.BLOCKED_COMMAND)
                self.assertEqual(result.counts(), (0, 1, 0))
                self.assertEqual((terminal.ack_reads, terminal.envelope_reads), (0, 0))

    def test_production_module_is_the_v2_no_issuer_root(self) -> None:
        root = Path(__file__).resolve().parents[1]
        invalid = subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "backend.r2_preflight_process",
                "execute",
            ),
            cwd=root,
            input="",
            text=True,
            capture_output=True,
            check=False,
        )
        redirected = subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "backend.r2_preflight_process",
                "current-topology",
            ),
            cwd=root,
            input=PREFLIGHT_ACKNOWLEDGEMENT + "\nignored\n",
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual((invalid.returncode, invalid.stderr), (2, ""))
        self.assertEqual((redirected.returncode, redirected.stderr), (0, ""))
        self.assertEqual(
            invalid.stdout,
            "BLOCKED_COMMAND accepted=0 rejected=1 read_operations=0\n",
        )
        self.assertEqual(
            redirected.stdout,
            "DORMANT_NO_EXTERNAL_ISSUER accepted=0 rejected=0 read_operations=0\n",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows real TTY proof")
    def test_signed_process_observes_three_real_ttys_and_stays_locked(self) -> None:
        root = Path(__file__).resolve().parents[1]
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        with tempfile.TemporaryDirectory(prefix="r2-preflight-tty-") as raw:
            result_path = Path(raw) / "result.json"
            host = subprocess.run(
                (
                    str(pythonw),
                    "-B",
                    "-m",
                    "tests.windows_real_tty_host",
                    str(result_path),
                ),
                cwd=root,
                timeout=20,
                check=False,
            )
            self.assertEqual(host.returncode, 0)
            result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["exit_code"], 0)

    def test_all_three_real_tty_channels_precede_every_read(self) -> None:
        process = self._process()
        for tty in ((False, True, True), (True, False, True), (True, True, False)):
            terminal = _Terminal(tty=tty)
            with self.subTest(tty=tty):
                result = process.run(
                    argv=("current-topology",), terminal=terminal
                )
                self.assertIs(result.status, PreflightProcessStatus.BLOCKED_TTY)
                self.assertEqual((terminal.ack_reads, terminal.envelope_reads), (0, 0))

    def test_exact_acknowledgement_precedes_one_hidden_bounded_read(self) -> None:
        process = self._process()
        for acknowledgement in ("", "y", PREFLIGHT_ACKNOWLEDGEMENT + " "):
            terminal = _Terminal(acknowledgement=acknowledgement)
            with self.subTest(acknowledgement=acknowledgement):
                result = process.run(
                    argv=("current-topology",), terminal=terminal
                )
                self.assertIs(
                    result.status,
                    PreflightProcessStatus.BLOCKED_ACKNOWLEDGEMENT,
                )
                self.assertEqual((terminal.ack_reads, terminal.envelope_reads), (1, 0))

        terminal = _Terminal(envelope="A" * 90_000)
        result = process.run(argv=("current-topology",), terminal=terminal)
        self.assertIs(result.status, PreflightProcessStatus.BLOCKED_ENVELOPE)
        self.assertEqual((terminal.ack_reads, terminal.envelope_reads), (1, 1))

    def test_valid_real_authorization_is_consumed_once_but_stays_locked(self) -> None:
        process = self._process()
        envelope = self._envelope(phase="current_topology_preflight")

        first = process.run(
            argv=("current-topology",), terminal=_Terminal(envelope=envelope)
        )
        second = process.run(
            argv=("current-topology",), terminal=_Terminal(envelope=envelope)
        )

        self.assertIs(
            first.status,
            PreflightProcessStatus.BLOCKED_NO_APPROVED_COMMAND,
        )
        self.assertEqual(first.counts(), (1, 0, 0))
        self.assertIs(second.status, PreflightProcessStatus.BLOCKED_REPLAY)
        self.assertEqual(second.counts(), (0, 1, 0))
        self.assertEqual(process.reader_acquisitions, 0)

    def test_binding_drift_expiry_and_cross_domain_fail_before_reader(self) -> None:
        process = self._process()
        cases = (
            self._envelope(
                phase="current_topology_preflight",
                profile_fingerprint=opaque_fingerprint(7110),
            ),
            self._envelope(
                phase="current_topology_preflight",
                governing_master_commit="1" * 40,
            ),
            self._envelope(
                phase="current_topology_preflight",
                operator_fingerprint=opaque_fingerprint(7111),
            ),
            self._envelope(
                phase="current_topology_preflight",
                operation="evidence_publication",
            ),
            self._envelope(
                phase="current_topology_preflight",
                operation_fingerprint=opaque_fingerprint(7112),
            ),
            self._envelope(phase="host_baseline"),
            self._envelope(
                phase="current_topology_preflight",
                expires_at_epoch=OBSERVED_AT,
            ),
            self._envelope(
                phase="current_topology_preflight",
                domain=AuthorizationEnvelopeDomain.EVIDENCE,
                signing_key=self.evidence_key,
            ),
        )
        for envelope in cases:
            with self.subTest(envelope=envelope[-24:]):
                result = process.run(
                    argv=("current-topology",),
                    terminal=_Terminal(envelope=envelope),
                )
                self.assertIs(
                    result.status,
                    PreflightProcessStatus.BLOCKED_AUTHORIZATION,
                )
                self.assertEqual(result.counts(), (0, 1, 0))
        self.assertEqual(process.reader_acquisitions, 0)

    def test_public_values_are_fixed_and_content_free(self) -> None:
        process = self._process()
        result = process.run(
            argv=("current-topology",),
            terminal=_Terminal(
                envelope=self._envelope(phase="current_topology_preflight")
            ),
        )
        public = f"{result.status.value} {result.counts()} {result!r}"
        self.assertEqual(
            set(result.to_mapping()),
            {"status", "accepted", "rejected", "host_operations"},
        )
        for forbidden in (
            "D:\\",
            self.profile.profile_fingerprint,
            self.profile.operator_fingerprint,
            self.profile.governing_master_commit,
            OPERATION,
            "command",
            "exception",
            "mailbox",
            "provider",
        ):
            self.assertNotIn(forbidden, public)

    def _process(self) -> SyntheticPreflightProcess:
        return SyntheticPreflightProcess.create(
            profile=self.profile,
            binding=self.binding,
            operation_fingerprint=OPERATION,
            verification_public_key=_public_bytes(self.preflight_key),
            observed_at_epoch=lambda: OBSERVED_AT,
        )

    def _envelope(self, *, phase: str, **overrides: object) -> str:
        domain = overrides.pop(
            "domain", AuthorizationEnvelopeDomain.PREFLIGHT
        )
        signing_key = overrides.pop("signing_key", self.preflight_key)
        authorization = _authorization_mapping(
            self.profile,
            phase=phase,
            **overrides,
        )
        body = {
            "envelope_type": "R2OperatorAuthorizationEnvelopeV1",
            "domain": domain.value,
            "nonce": opaque_fingerprint(7199),
            "authorization": authorization,
        }
        signature = signing_key.sign(authorization_envelope_message(body))
        payload = _canonical_json(
            {**body, "signature": base64.b64encode(signature).decode("ascii")}
        )
        return base64.b64encode(payload).decode("ascii")


def _authorization_mapping(profile, *, phase: str, **overrides: object):
    body = {
        "authorization_type": "RealPreflightAuthorizationV1",
        "operation": "real_preflight",
        "operation_fingerprint": OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": OBSERVED_AT - 20,
        "not_before_epoch": OBSERVED_AT - 10,
        "expires_at_epoch": OBSERVED_AT + 60,
    }
    body.update(overrides)
    authorization = {
        **body,
        "authorization_fingerprint": hashlib.sha256(
            _canonical_json(body)
        ).hexdigest(),
    }
    return authorization


def _public_bytes(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


if __name__ == "__main__":
    unittest.main()
