"""Public fixed-process behavior for Issue #72 evidence publication."""

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
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.r2_evidence_process import (
    EVIDENCE_ACKNOWLEDGEMENT,
    EVIDENCE_VERBS,
    EvidenceProcessStatus,
)
from backend.r2_evidence_process.testing import SyntheticEvidenceProcess
from backend.r2_operator_process import (
    AuthorizationEnvelopeDomain,
    authorization_envelope_message,
)
from tests.cutover_composition_fixtures import synthetic_context
from tests.cutover_contract_fixtures import opaque_fingerprint


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(7200)
CONFIRMED_REVIEW = opaque_fingerprint(7201)


class _Terminal:
    def __init__(self, envelope: str, *, tty=(True, True, True)) -> None:
        self.envelope = envelope
        self.tty = tty
        self.reads = 0

    def tty_state(self):
        return self.tty

    def read_acknowledgement(self):
        return EVIDENCE_ACKNOWLEDGEMENT

    def read_hidden_envelope(self, maximum):
        self.reads += 1
        return self.envelope[: maximum + 1]


class R2EvidenceProcessTests(unittest.TestCase):
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
        self.key = Ed25519PrivateKey.generate()
        self.public_key = self.key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )

    def test_only_publish_is_accepted_and_stronger_values_read_nothing(self):
        self.assertEqual(EVIDENCE_VERBS, {"publish": "evidence_publication"})
        process = self._process(lambda: 1)
        for argv in (
            (),
            ("verify",),
            ("publish", "D:\\synthetic"),
            ("--target",),
            ("--profile",),
            ("--journal",),
            ("--force",),
        ):
            terminal = _Terminal("")
            with self.subTest(argv=argv):
                result = process.run(argv=argv, terminal=terminal)
                self.assertIs(result.status, EvidenceProcessStatus.BLOCKED_COMMAND)
                self.assertEqual(result.counts(), (0, 1, 0))
                self.assertEqual(terminal.reads, 0)

    def test_valid_authorization_publishes_create_only_exactly_once(self):
        with tempfile.TemporaryDirectory(prefix="r2-evidence-") as raw:
            target = Path(raw) / "published.evidence"
            calls = 0

            def publish() -> int:
                nonlocal calls
                calls += 1
                with target.open("xb") as stream:
                    stream.write(b"SYNTHETIC_R2_EVIDENCE\n")
                return 1

            process = self._process(publish)
            envelope = self._envelope()
            first = process.run(
                argv=("publish",), terminal=_Terminal(envelope)
            )
            second = process.run(
                argv=("publish",), terminal=_Terminal(envelope)
            )

            self.assertIs(first.status, EvidenceProcessStatus.PUBLISHED)
            self.assertEqual(first.counts(), (1, 0, 1))
            self.assertIs(second.status, EvidenceProcessStatus.BLOCKED_REPLAY)
            self.assertEqual(second.counts(), (0, 1, 0))
            self.assertEqual(calls, 1)
            self.assertEqual(
                target.read_bytes(), b"SYNTHETIC_R2_EVIDENCE\n"
            )

    def test_wrong_review_domain_binding_and_expiry_precede_publication(self):
        calls = 0

        def publish() -> int:
            nonlocal calls
            calls += 1
            return 1

        cases = (
            (self._process(publish, review=opaque_fingerprint(7290)), self._envelope()),
            (
                self._process(publish),
                self._envelope(
                    domain=AuthorizationEnvelopeDomain.PREFLIGHT,
                    authorization_type="RealPreflightAuthorizationV1",
                    operation="real_preflight",
                ),
            ),
            (
                self._process(publish),
                self._envelope(profile_fingerprint=opaque_fingerprint(7291)),
            ),
            (
                self._process(publish),
                self._envelope(expires_at_epoch=OBSERVED_AT),
            ),
        )
        for process, envelope in cases:
            with self.subTest(envelope=envelope[-20:]):
                result = process.run(
                    argv=("publish",), terminal=_Terminal(envelope)
                )
                self.assertIs(
                    result.status, EvidenceProcessStatus.BLOCKED_AUTHORIZATION
                )
                self.assertEqual(result.counts(), (0, 1, 0))
                self.assertEqual(process.publication_acquisitions, 0)
        self.assertEqual(calls, 0)

    def test_valid_real_entry_stays_locked_before_issue_39(self):
        process = self._process(lambda: 1, real_locked=True)
        result = process.run(
            argv=("publish",), terminal=_Terminal(self._envelope())
        )
        self.assertIs(
            result.status, EvidenceProcessStatus.BLOCKED_NO_APPROVED_COMMAND
        )
        self.assertEqual(result.counts(), (1, 0, 0))
        self.assertEqual(process.publication_acquisitions, 0)

    def test_failed_create_only_attempt_is_never_retried(self):
        calls = 0

        def fail_after_effect() -> int:
            nonlocal calls
            calls += 1
            raise OSError("synthetic post-effect failure")

        process = self._process(fail_after_effect)
        first = process.run(
            argv=("publish",), terminal=_Terminal(self._envelope())
        )
        second = process.run(
            argv=("publish",),
            terminal=_Terminal(
                self._envelope(nonce=opaque_fingerprint(7288))
            ),
        )
        self.assertIs(first.status, EvidenceProcessStatus.BLOCKED_PUBLICATION)
        self.assertIs(second.status, EvidenceProcessStatus.BLOCKED_PUBLICATION)
        self.assertEqual(calls, 1)
        self.assertEqual(process.publication_acquisitions, 1)

    def test_production_module_is_the_v2_no_issuer_root(self):
        root = Path(__file__).resolve().parents[1]
        invalid = subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "backend.r2_evidence_process",
                "publish",
                "synthetic-target",
            ),
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
        redirected = subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "backend.r2_evidence_process",
                "publish",
            ),
            cwd=root,
            input=EVIDENCE_ACKNOWLEDGEMENT + "\nignored\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((invalid.returncode, invalid.stderr), (2, ""))
        self.assertEqual((redirected.returncode, redirected.stderr), (0, ""))
        self.assertEqual(
            invalid.stdout,
            "BLOCKED_COMMAND accepted=0 rejected=1 published=0\n",
        )
        self.assertEqual(
            redirected.stdout,
            "DORMANT_NO_EXTERNAL_ISSUER accepted=0 rejected=0 published=0\n",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows real TTY proof")
    def test_signed_evidence_process_publishes_once_on_real_tty(self):
        root = Path(__file__).resolve().parents[1]
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        with tempfile.TemporaryDirectory(prefix="r2-evidence-tty-") as raw:
            result_path = Path(raw) / "result.json"
            host = subprocess.run(
                (
                    str(pythonw),
                    "-B",
                    "-m",
                    "tests.windows_evidence_tty_host",
                    str(result_path),
                ),
                cwd=root,
                timeout=20,
                check=False,
            )
            self.assertEqual(host.returncode, 0)
            result = json.loads(result_path.read_text(encoding="utf-8"))
        self.assertEqual(result, {"status": "complete", "exit_code": 0})

    def _process(self, publish, *, review=CONFIRMED_REVIEW, real_locked=False):
        return SyntheticEvidenceProcess.create(
            profile=self.profile,
            binding=self.binding,
            operation_fingerprint=OPERATION,
            confirmed_review_fingerprint=review,
            expected_review_fingerprint=CONFIRMED_REVIEW,
            verification_public_key=self.public_key,
            observed_at_epoch=lambda: OBSERVED_AT,
            publish_confirmed_review=publish,
            real_locked=real_locked,
        )

    def _envelope(self, **overrides: object) -> str:
        domain = overrides.pop(
            "domain", AuthorizationEnvelopeDomain.EVIDENCE
        )
        nonce = overrides.pop("nonce", opaque_fingerprint(7299))
        body = {
            "authorization_type": overrides.pop(
                "authorization_type", "EvidencePublicationAuthorizationV1"
            ),
            "operation": overrides.pop("operation", "evidence_publication"),
            "operation_fingerprint": OPERATION,
            "profile_fingerprint": self.profile.profile_fingerprint,
            "governing_master_commit": self.profile.governing_master_commit,
            "operator_fingerprint": self.profile.operator_fingerprint,
            "phase": "evidence_publication",
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
        envelope = {
            "envelope_type": "R2OperatorAuthorizationEnvelopeV1",
            "domain": domain.value,
            "nonce": nonce,
            "authorization": authorization,
        }
        payload = _canonical_json(
            {
                **envelope,
                "signature": base64.b64encode(
                    self.key.sign(authorization_envelope_message(envelope))
                ).decode("ascii"),
            }
        )
        return base64.b64encode(payload).decode("ascii")


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
