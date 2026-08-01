"""Public transaction process behavior for Issue #73."""

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

from backend.cutover_composition_contracts import (
    ApprovedCutoverBindingV1,
    UNBOUND_FINGERPRINT,
)
from backend.r2_operator_process import authorization_envelope_message
from backend.r2_transaction_process import (
    TRANSACTION_ACKNOWLEDGEMENT,
    TRANSACTION_VERBS,
    TransactionProcessStatus,
)
from backend.r2_transaction_process.testing import SyntheticTransactionProcess
from tests.cutover_composition_fixtures import synthetic_context
from tests.cutover_contract_fixtures import opaque_fingerprint


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(7300)
OWNER = opaque_fingerprint(7301)
HEAD = opaque_fingerprint(7302)
PLAN = opaque_fingerprint(7303)


class _Terminal:
    def __init__(self, envelope: str, tty=(True, True, True)) -> None:
        self.envelope = envelope
        self.tty = tty
        self.reads = 0

    def tty_state(self):
        return self.tty

    def read_acknowledgement(self):
        return TRANSACTION_ACKNOWLEDGEMENT

    def read_hidden_envelope(self, maximum):
        self.reads += 1
        return self.envelope[: maximum + 1]


class R2TransactionProcessTests(unittest.TestCase):
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
        self.execution_key = Ed25519PrivateKey.generate()
        self.recovery_key = Ed25519PrivateKey.generate()
        self.head = HEAD
        self.plan = PLAN
        self.calls: list[str] = []

    def test_only_three_fixed_verbs_exist_and_hostile_argv_reads_nothing(self):
        self.assertEqual(
            TRANSACTION_VERBS,
            {"execute": "execute", "resume": "resume", "rollback": "rollback"},
        )
        process = self._process()
        for argv in (
            (),
            ("publish",),
            ("execute", "D:\\synthetic"),
            ("--profile",),
            ("--journal",),
            ("--recovery-target",),
            ("--force",),
            ("git", "reset"),
        ):
            terminal = _Terminal("")
            with self.subTest(argv=argv):
                result = process.run(argv=argv, terminal=terminal)
                self.assertIs(
                    result.status, TransactionProcessStatus.BLOCKED_COMMAND
                )
                self.assertEqual(result.counts(), (0, 1, 0))
                self.assertEqual(terminal.reads, 0)

    def test_execute_and_resume_use_execution_domain_and_one_action_each(self):
        process = self._process()
        execute = process.run(
            argv=("execute",),
            terminal=_Terminal(self._envelope("execute")),
        )
        self.head = opaque_fingerprint(7310)
        resume = process.run(
            argv=("resume",),
            terminal=_Terminal(
                self._envelope(
                    "resume",
                    nonce=opaque_fingerprint(7311),
                    crash_nonce=opaque_fingerprint(7312),
                )
            ),
        )
        self.assertIs(execute.status, TransactionProcessStatus.ACTION_COMPLETE)
        self.assertIs(resume.status, TransactionProcessStatus.ACTION_COMPLETE)
        self.assertEqual(execute.counts(), (1, 0, 1))
        self.assertEqual(resume.counts(), (1, 0, 1))
        self.assertEqual(self.calls, ["execute", "resume"])

    def test_resume_head_drift_and_cross_domain_fail_before_action(self):
        process = self._process()
        drifted = self._envelope(
            "resume", journal_head=opaque_fingerprint(7320)
        )
        wrong_domain = self._envelope(
            "resume", domain="recovery", signing_key=self.recovery_key
        )
        for envelope in (drifted, wrong_domain):
            result = process.run(
                argv=("resume",), terminal=_Terminal(envelope)
            )
            self.assertIs(
                result.status, TransactionProcessStatus.BLOCKED_AUTHORIZATION
            )
        self.assertEqual(self.calls, [])
        self.assertEqual(process.action_acquisitions, 0)

    def test_rollback_binds_recovery_domain_plan_head_and_crash_nonce(self):
        process = self._process()
        wrong_plan = self._envelope(
            "rollback", remaining_plan=opaque_fingerprint(7330)
        )
        rejected = process.run(
            argv=("rollback",), terminal=_Terminal(wrong_plan)
        )
        envelope = self._envelope("rollback")
        accepted = process.run(
            argv=("rollback",), terminal=_Terminal(envelope)
        )
        replayed = process.run(
            argv=("rollback",), terminal=_Terminal(envelope)
        )
        self.assertIs(
            rejected.status, TransactionProcessStatus.BLOCKED_AUTHORIZATION
        )
        self.assertIs(accepted.status, TransactionProcessStatus.ACTION_COMPLETE)
        self.assertIs(replayed.status, TransactionProcessStatus.BLOCKED_REPLAY)
        self.assertEqual(self.calls, ["rollback"])
        self.assertEqual(process.action_acquisitions, 1)

    def test_valid_real_authorization_remains_locked_with_zero_mutations(self):
        process = self._process(real_locked=True)
        result = process.run(
            argv=("execute",), terminal=_Terminal(self._envelope("execute"))
        )
        self.assertIs(
            result.status,
            TransactionProcessStatus.BLOCKED_NO_APPROVED_COMMAND,
        )
        self.assertEqual(result.counts(), (1, 0, 0))
        self.assertEqual(process.action_acquisitions, 0)
        self.assertEqual(self.calls, [])

    def test_production_module_rejects_extra_and_redirected_ingress(self):
        root = Path(__file__).resolve().parents[1]
        invalid = subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "backend.r2_transaction_process",
                "execute",
                "D:\\synthetic",
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
                "backend.r2_transaction_process",
                "rollback",
            ),
            cwd=root,
            input=TRANSACTION_ACKNOWLEDGEMENT + "\nignored\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((invalid.returncode, invalid.stderr), (2, ""))
        self.assertEqual((redirected.returncode, redirected.stderr), (3, ""))
        self.assertEqual(
            invalid.stdout,
            "BLOCKED_COMMAND accepted=0 rejected=1 mutations=0\n",
        )
        self.assertEqual(
            redirected.stdout,
            "BLOCKED_TTY accepted=0 rejected=1 mutations=0\n",
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows real TTY proof")
    def test_signed_execute_process_performs_one_action_on_real_tty(self):
        root = Path(__file__).resolve().parents[1]
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        with tempfile.TemporaryDirectory(prefix="r2-transaction-tty-") as raw:
            target = Path(raw) / "result.json"
            host = subprocess.run(
                (
                    str(pythonw),
                    "-B",
                    "-m",
                    "tests.windows_transaction_tty_host",
                    str(target),
                ),
                cwd=root,
                timeout=20,
                check=False,
            )
            self.assertEqual(host.returncode, 0)
            observed = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(observed, {"status": "complete", "exit_code": 0})

    def _process(self, *, real_locked=False):
        return SyntheticTransactionProcess.create(
            profile=self.profile,
            binding=self.binding,
            operation_fingerprint=OPERATION,
            journal_owner_fingerprint=OWNER,
            current_journal_head=lambda: self.head,
            remaining_reverse_plan=lambda: self.plan,
            observed_at_epoch=lambda: OBSERVED_AT,
            execution_public_key=_public_bytes(self.execution_key),
            recovery_public_key=_public_bytes(self.recovery_key),
            execute=lambda: self._action("execute"),
            resume=lambda: self._action("resume"),
            rollback=lambda: self._action("rollback"),
            real_locked=real_locked,
        )

    def _action(self, verb):
        self.calls.append(verb)
        return 1

    def _envelope(self, verb: str, **overrides: object) -> str:
        recovery = verb == "rollback"
        domain = overrides.pop("domain", "recovery" if recovery else "execution")
        key = overrides.pop(
            "signing_key", self.recovery_key if recovery else self.execution_key
        )
        envelope_nonce = overrides.pop("nonce", opaque_fingerprint(7399))
        operation = "recovery" if recovery else "cutover_execution"
        kind = (
            "RecoveryAuthorizationV1"
            if recovery
            else "CutoverExecutionAuthorizationV1"
        )
        authorization_body = {
            "authorization_type": kind,
            "operation": operation,
            "operation_fingerprint": OPERATION,
            "profile_fingerprint": self.profile.profile_fingerprint,
            "governing_master_commit": self.profile.governing_master_commit,
            "operator_fingerprint": self.profile.operator_fingerprint,
            "phase": verb,
            "issued_at_epoch": OBSERVED_AT - 20,
            "not_before_epoch": OBSERVED_AT - 10,
            "expires_at_epoch": OBSERVED_AT + 60,
        }
        context = {
            "context_type": "R2TransactionAuthorizationContextV1",
            "approved_binding_fingerprint": self.binding.binding_fingerprint,
            "journal_owner_fingerprint": OWNER,
            "journal_head_fingerprint": overrides.pop("journal_head", self.head),
            "remaining_plan_fingerprint": overrides.pop(
                "remaining_plan", self.plan if recovery else UNBOUND_FINGERPRINT
            ),
            "boundary_epoch": overrides.pop("boundary_epoch", OBSERVED_AT),
            "crash_nonce": overrides.pop("crash_nonce", opaque_fingerprint(7390)),
        }
        authorization_body.update(overrides)
        authorization = {
            **authorization_body,
            "authorization_fingerprint": hashlib.sha256(
                _canonical_json(authorization_body)
            ).hexdigest(),
        }
        envelope = {
            "envelope_type": "R2OperatorAuthorizationEnvelopeV1",
            "domain": domain,
            "nonce": envelope_nonce,
            "authorization": authorization,
            "context": context,
        }
        payload = _canonical_json(
            {
                **envelope,
                "signature": base64.b64encode(
                    key.sign(authorization_envelope_message(envelope))
                ).decode("ascii"),
            }
        )
        return base64.b64encode(payload).decode("ascii")


def _public_bytes(key):
    return key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
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
