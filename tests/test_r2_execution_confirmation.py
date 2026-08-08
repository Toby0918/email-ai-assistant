"""Pure dormant Execution Confirmation V1 contracts."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.r2_production_binding import (
    ExecutionConfirmationCandidateV1,
    ExecutionConfirmationClaimV1,
    ExecutionConfirmationError,
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    confirm_execution_confirmation_v1,
    validate_new_execution_confirmation_claim,
)
from tests.r2_execution_confirmation_fixture import (
    ACKNOWLEDGEMENT,
    execution_candidate,
    execution_claim,
    production_binding,
)


_CANDIDATE_FIELDS = {
    "candidate_type",
    "status",
    "confirmation_policy",
    "production_binding_fingerprint",
    "final_master_binding_fingerprint",
    "closure_manifest_fingerprint",
    "solo_maintainer_attestation_receipt_fingerprint",
    "command",
    "command_domain",
    "operator_role_fingerprint",
    "operation_fingerprint",
    "action_fingerprint",
    "journal_owner_fingerprint",
    "prior_journal_head_fingerprint",
    "transition_instance_fingerprint",
    "remaining_reverse_plan_fingerprint",
    "claim_sequence",
    "confirmation_acknowledgement",
    "prepared_at_epoch",
    "expires_at_epoch",
    "confirmation_window_seconds",
    "single_use",
    "candidate_fingerprint",
}
_CLAIM_FIELDS = {
    "claim_type",
    "status",
    "confirmation_policy",
    "production_binding_fingerprint",
    "final_master_binding_fingerprint",
    "closure_manifest_fingerprint",
    "solo_maintainer_attestation_receipt_fingerprint",
    "command",
    "command_domain",
    "operator_role_fingerprint",
    "operation_fingerprint",
    "action_fingerprint",
    "journal_owner_fingerprint",
    "prior_journal_head_fingerprint",
    "transition_instance_fingerprint",
    "remaining_reverse_plan_fingerprint",
    "claim_sequence",
    "prepared_at_epoch",
    "confirmed_at_epoch",
    "expires_at_epoch",
    "confirmation_window_seconds",
    "acknowledgement",
    "acknowledgement_fingerprint",
    "assurance_model",
    "operator_count",
    "independent_reviewer_count",
    "external_signer_count",
    "execution_confirmation_count",
    "single_use",
    "replay_count",
    "provider_attempt_count",
    "deletion_operation_count",
    "claim_fingerprint",
}
_PROCESS_SYNCHRONIZE_AND_TERMINATE = 0x00100001
_WAIT_OBJECT_0 = 0
_WAIT_TIMEOUT = 258
_CONTROLLER_PROBE_EVENTS = (
    "attach", "request_1", "write_1", "request_2", "write_2",
    "free", "process_wait", "tree_terminate",
)
_EXECUTION_FAILURE_STATES = {
    (False, False, False): b"R2_EXECUTION_HOSTED_STATE_000\n",
    (False, False, True): b"R2_EXECUTION_HOSTED_STATE_001\n",
    (False, True, False): b"R2_EXECUTION_HOSTED_STATE_010\n",
    (False, True, True): b"R2_EXECUTION_HOSTED_STATE_011\n",
    (True, False, False): b"R2_EXECUTION_HOSTED_STATE_100\n",
    (True, False, True): b"R2_EXECUTION_HOSTED_STATE_101\n",
    (True, True, False): b"R2_EXECUTION_HOSTED_STATE_110\n",
    (True, True, True): b"R2_EXECUTION_HOSTED_STATE_111\n",
}


class _ControllerProcessProbe:
    pid = 123

    def __init__(self, target, events):
        self._target = target
        self._events = events

    def poll(self):
        return None

    def wait(self, timeout=None):
        self._target.write_text("{}", encoding="ascii")
        self._events.append("process_wait")
        return 0


class _ControllerTreeProbe:
    def __init__(self, events):
        self._events = events

    def terminate(self, process):
        self._events.append("tree_terminate")


def _windows_process_kernel():
    import ctypes
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel.TerminateProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    return kernel


def _wait_for_cleanup_ready(controller, ready):
    import time

    deadline = time.monotonic() + 10
    while not ready.is_file() and time.monotonic() < deadline:
        if controller.poll() is not None:
            raise AssertionError("cleanup controller stopped before worker readiness")
        time.sleep(0.01)
    if not ready.is_file():
        raise AssertionError("cleanup worker readiness timed out")
    return json.loads(ready.read_text(encoding="ascii"))


def _close_worker_handle(kernel, worker_handle):
    if not worker_handle:
        return
    try:
        state = kernel.WaitForSingleObject(worker_handle, 0)
        if state == _WAIT_TIMEOUT:
            terminated = kernel.TerminateProcess(worker_handle, 4)
            state = kernel.WaitForSingleObject(worker_handle, 5000)
            if not terminated and state != _WAIT_OBJECT_0:
                raise AssertionError("blocked worker fallback termination failed")
        if state != _WAIT_OBJECT_0:
            raise AssertionError("blocked worker survived cleanup")
    finally:
        if not kernel.CloseHandle(worker_handle):
            raise AssertionError("blocked worker handle close failed")


def _hosted_probe(marker):
    try:
        os.write(2, marker)
    except OSError:
        pass


class R2ExecutionConfirmationTests(unittest.TestCase):
    def test_console_controller_attaches_before_post_display_handoff(self):
        from tests import windows_real_tty_host as host

        events = []

        def wait_for_request(process, path, round_number, line_count, deadline):
            self.assertIn("attach", events)
            events.append(f"request_{round_number}")
            return "x\r" * line_count

        def write_input(kernel, handle, text):
            round_number = len([event for event in events if event.startswith("write_")]) + 1
            self.assertEqual(events[-1], f"request_{round_number}")
            events.append(f"write_{round_number}")

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "execution-confirmation-proof.json"
            process = _ControllerProcessProbe(target, events)
            tree = _ControllerTreeProbe(events)
            with patch.object(host.ProcessTree, "prepare", return_value=tree), \
                    patch.object(host, "_launch_console_worker", return_value=process), \
                    patch.object(host, "_attach_console_input", side_effect=(lambda pid: (
                        events.append("attach") or (object(), object())
                    ))), \
                    patch.object(host, "_wait_for_input_request", side_effect=wait_for_request), \
                    patch.object(host, "_write_console_input", side_effect=write_input), \
                    patch.object(host, "_free_console", side_effect=(lambda console: events.append("free"))):
                result = host.run_execution_confirmation_controller(target)

        self.assertEqual(result, 0)
        self.assertEqual(tuple(events), _CONTROLLER_PROBE_EVENTS)

    def test_candidate_and_claim_have_exact_closed_schemas(self):
        binding = production_binding()
        candidate = execution_candidate(binding)
        claim = execution_claim(binding, candidate=candidate)

        self.assertEqual(set(candidate.to_mapping()), _CANDIDATE_FIELDS)
        self.assertEqual(set(claim.to_mapping()), _CLAIM_FIELDS)
        self.assertEqual(candidate.status, "AWAITING_EXECUTION_CONFIRMATION")
        self.assertEqual(claim.status, "EXECUTION_CONFIRMATION_RECORDED")
        self.assertEqual(candidate.expires_at_epoch, 400)
        self.assertEqual(candidate.confirmation_window_seconds, 300)
        self.assertEqual(candidate.single_use, 1)
        self.assertEqual(candidate.confirmation_acknowledgement, ACKNOWLEDGEMENT)
        self.assertEqual(claim.assurance_model, "SOLE_MAINTAINER_SELF_REVIEW")
        self.assertEqual(
            (
                claim.operator_count,
                claim.independent_reviewer_count,
                claim.external_signer_count,
            ),
            (1, 0, 0),
        )
        self.assertEqual(
            (
                claim.execution_confirmation_count,
                claim.single_use,
                claim.replay_count,
                claim.provider_attempt_count,
                claim.deletion_operation_count,
            ),
            (1, 1, 0, 0, 0),
        )
        self.assertEqual(
            ExecutionConfirmationCandidateV1.from_json(
                candidate.to_canonical_json(),
                binding=binding,
            ),
            candidate,
        )
        self.assertEqual(
            ExecutionConfirmationClaimV1.from_json(
                claim.to_canonical_json(),
                binding=binding,
            ),
            claim,
        )

    def test_candidate_claim_and_acknowledgement_use_exact_domains(self):
        candidate = execution_candidate()
        claim = execution_claim(candidate=candidate)
        candidate_body = candidate.to_mapping()
        candidate_body.pop("candidate_fingerprint")
        claim_body = claim.to_mapping()
        claim_body.pop("claim_fingerprint")
        acknowledgement_body = {"acknowledgement": ACKNOWLEDGEMENT}

        self.assertEqual(
            candidate.candidate_fingerprint,
            _fingerprint("r2-execution-confirmation-candidate-v1", candidate_body),
        )
        self.assertEqual(
            claim.claim_fingerprint,
            _fingerprint("r2-execution-confirmation-claim-v1", claim_body),
        )
        self.assertEqual(
            claim.acknowledgement_fingerprint,
            _fingerprint(
                "r2-execution-confirmation-claim-v1",
                acknowledgement_body,
            ),
        )
        self.assertNotEqual(
            claim.acknowledgement_fingerprint,
            _fingerprint(
                "r2-execution-confirmation-policy-v1",
                acknowledgement_body,
            ),
        )

    def test_confirmation_requires_exact_fingerprint_ack_and_half_open_window(self):
        cases = (
            {"supplied_fingerprint": "f" * 64},
            {"supplied_acknowledgement": ACKNOWLEDGEMENT.lower()},
            {"supplied_acknowledgement": ACKNOWLEDGEMENT + " "},
            {"supplied_acknowledgement": ACKNOWLEDGEMENT + "\x1b"},
            {"confirmed_at_epoch": 400},
            {"confirmed_monotonic_ns": 301_000_000_000},
            {"confirmed_at_epoch": 99},
            {"confirmed_monotonic_ns": 999_999_999},
        )

        for options in cases:
            with self.subTest(options=options):
                candidate = execution_candidate(**options)
                with self.assertRaisesRegex(
                    ExecutionConfirmationError,
                    "R2_EXECUTION_CONFIRMATION_INVALID",
                ):
                    confirm_execution_confirmation_v1(candidate=candidate)

    def test_confirmation_uses_visible_single_reads_stable_console_and_is_single_use(self):
        candidate = execution_candidate()
        console = candidate._runtime.console

        claim = confirm_execution_confirmation_v1(candidate=candidate)

        self.assertEqual(
            console.displayed,
            [candidate.candidate_fingerprint, ACKNOWLEDGEMENT],
        )
        self.assertEqual(console.fingerprint_read_count, 1)
        self.assertEqual(console.acknowledgement_read_count, 1)
        self.assertEqual(console.pending_check_count, 1)
        self.assertEqual(console.snapshot_count, 2)
        self.assertEqual(claim.confirmed_at_epoch, 102)
        with self.assertRaises(ExecutionConfirmationError):
            confirm_execution_confirmation_v1(candidate=candidate)

    def test_pending_third_line_is_rejected_and_consumes_candidate(self):
        candidate = execution_candidate(pending_input=True)
        console = candidate._runtime.console

        with self.assertRaises(ExecutionConfirmationError):
            confirm_execution_confirmation_v1(candidate=candidate)

        self.assertEqual(console.fingerprint_read_count, 1)
        self.assertEqual(console.acknowledgement_read_count, 1)
        self.assertEqual(console.pending_check_count, 1)
        with self.assertRaises(ExecutionConfirmationError):
            confirm_execution_confirmation_v1(candidate=candidate)

    def test_prepare_does_not_read_console_and_handle_drift_consumes_candidate(self):
        changed = (("stdin", 0, 99), ("stdout", 1, 11), ("stderr", 2, 12))
        candidate = execution_candidate(console_identity_after=changed)
        console = candidate._runtime.console
        self.assertEqual(console.snapshot_count, 0)
        self.assertEqual(console.displayed, [])

        with self.assertRaises(ExecutionConfirmationError):
            confirm_execution_confirmation_v1(candidate=candidate)
        self.assertEqual(console.fingerprint_read_count, 1)
        self.assertEqual(console.acknowledgement_read_count, 1)
        with self.assertRaises(ExecutionConfirmationError):
            confirm_execution_confirmation_v1(candidate=candidate)

    @unittest.skipUnless(os.name == "nt", "Windows real TTY proof")
    def test_windows_real_console_proves_three_handles_and_exact_two_lines(self):
        _hosted_probe(b"R2_EXECUTION_HOSTED_START\n")
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "execution-confirmation-proof.json"
            requests = tuple(
                target.with_name(target.name + f".input-{index}.json")
                for index in (1, 2)
            )
            try:
                completed = subprocess.run(
                    (
                        os.fsdecode(Path(os.sys.executable).with_name("pythonw.exe")),
                        "-B", "-m", "tests.windows_real_tty_host",
                        "--execution-confirmation-proof", str(target),
                    ),
                    cwd=Path(__file__).resolve().parents[1],
                    timeout=20,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                _hosted_probe(b"R2_EXECUTION_HOSTED_TIMEOUT\n")
                _hosted_probe(_EXECUTION_FAILURE_STATES[
                    (requests[0].is_file(), requests[1].is_file(), target.is_file())
                ])
                raise
            if completed.returncode != 0:
                _hosted_probe(b"R2_EXECUTION_HOSTED_NONZERO\n")
                _hosted_probe(_EXECUTION_FAILURE_STATES[
                    (requests[0].is_file(), requests[1].is_file(), target.is_file())
                ])
            try:
                self.assertEqual(completed.returncode, 0)
                self.assertEqual(
                    json.loads(target.read_text(encoding="utf-8")),
                    {
                        "acknowledgement_line_count": 2,
                        "candidate_line_count": 1,
                        "confirmation_recorded": 1,
                        "console_identity_stable": 1,
                        "extra_line_rejected": 1,
                        "stderr_write_count": 0,
                        "stdin_stdout_stderr_console_verified": 1,
                        "stdout_write_count": 4,
                    },
                )
            except Exception:
                _hosted_probe(b"R2_EXECUTION_HOSTED_PROOF_INVALID\n")
                _hosted_probe(_EXECUTION_FAILURE_STATES[
                    (requests[0].is_file(), requests[1].is_file(), target.is_file())
                ])
                raise
        _hosted_probe(b"R2_EXECUTION_HOSTED_PASS\n")

    @unittest.skipUnless(os.name == "nt", "Windows real TTY proof")
    def test_windows_controller_kill_closes_blocked_worker_job(self):
        _hosted_probe(b"R2_CLEANUP_HOSTED_START\n")
        kernel = _windows_process_kernel()
        controller, worker_handle = None, None
        failure_marker = b"R2_CLEANUP_HOSTED_READY_FAIL\n"
        try:
            with tempfile.TemporaryDirectory() as directory:
                ready = Path(directory) / "blocked-worker-ready.json"
                controller = subprocess.Popen(
                    (
                        os.fsdecode(Path(os.sys.executable).with_name("pythonw.exe")),
                        "-B", "-m", "tests.windows_real_tty_host",
                        "--controller-cleanup-proof", str(ready),
                    ),
                    cwd=Path(__file__).resolve().parents[1],
                )
                payload = _wait_for_cleanup_ready(controller, ready)
                failure_marker = b"R2_CLEANUP_HOSTED_PAYLOAD_FAIL\n"
                self.assertEqual(set(payload), {"pid", "request_type"})
                self.assertEqual(
                    payload["request_type"], "WindowsConsoleWorkerReadyV1"
                )
                self.assertIs(type(payload["pid"]), int)
                failure_marker = b"R2_CLEANUP_HOSTED_OPEN_FAIL\n"
                worker_handle = kernel.OpenProcess(
                    _PROCESS_SYNCHRONIZE_AND_TERMINATE, False, payload["pid"]
                )
                self.assertTrue(worker_handle)
                failure_marker = b"R2_CLEANUP_HOSTED_NOT_BLOCKED\n"
                self.assertEqual(
                    kernel.WaitForSingleObject(worker_handle, 0), _WAIT_TIMEOUT
                )
                failure_marker = b"R2_CLEANUP_HOSTED_CONTROLLER_FAIL\n"
                self.assertIsNone(controller.poll())
                controller.kill()
                controller.wait(timeout=5)
                failure_marker = b"R2_CLEANUP_HOSTED_WORKER_SURVIVED\n"
                self.assertEqual(
                    kernel.WaitForSingleObject(worker_handle, 5000), _WAIT_OBJECT_0
                )
        except Exception:
            _hosted_probe(failure_marker)
            raise
        finally:
            try:
                if controller is not None and controller.poll() is None:
                    controller.kill()
                    controller.wait(timeout=5)
            finally:
                try:
                    _close_worker_handle(kernel, worker_handle)
                except Exception:
                    _hosted_probe(b"R2_CLEANUP_HOSTED_FINALIZER_FAIL\n")
                    raise
        _hosted_probe(b"R2_CLEANUP_HOSTED_PASS\n")

    def test_parsed_values_are_review_only_and_cannot_restore_live_capability(self):
        binding = production_binding()
        candidate = execution_candidate(binding)
        claim = execution_claim(binding, candidate=candidate)
        parsed_candidate = ExecutionConfirmationCandidateV1.from_json(
            candidate.to_canonical_json(),
            binding=binding,
        )
        parsed_claim = ExecutionConfirmationClaimV1.from_json(
            claim.to_canonical_json(),
            binding=binding,
        )

        with self.assertRaises(ExecutionConfirmationError):
            confirm_execution_confirmation_v1(candidate=parsed_candidate)
        with self.assertRaises(ExecutionConfirmationError):
            validate_new_execution_confirmation_claim(
                binding=binding,
                candidate=parsed_claim,
                durable_claims=(),
                observed_at_epoch=103,
                observed_monotonic_ns=4_000_000_000,
                expected_prior_journal_head_fingerprint="3" * 64,
            )

    def test_durable_validation_rejects_replay_stale_or_wrong_head(self):
        binding = production_binding()
        first_candidate = execution_candidate(binding)
        first = execution_claim(binding, candidate=first_candidate)

        self.assertIs(
            validate_new_execution_confirmation_claim(
                binding=binding,
                candidate=first,
                durable_claims=(),
                observed_at_epoch=103,
                observed_monotonic_ns=4_000_000_000,
                expected_prior_journal_head_fingerprint="3" * 64,
            ),
            first,
        )
        replay_candidate = execution_candidate(
            binding,
            action_fingerprint=first.action_fingerprint,
            prior_head="5" * 64,
            claim_sequence=2,
        )
        replay = execution_claim(binding, candidate=replay_candidate)
        with self.assertRaises(ExecutionConfirmationError):
            validate_new_execution_confirmation_claim(
                binding=binding,
                candidate=replay,
                durable_claims=(first,),
                observed_at_epoch=103,
                observed_monotonic_ns=4_000_000_000,
                expected_prior_journal_head_fingerprint="5" * 64,
            )
        for durable, observed, monotonic, head in (
            ((first,), 103, 4_000_000_000, "3" * 64),
            ((), 400, 4_000_000_000, "3" * 64),
            ((), 103, 301_000_000_000, "3" * 64),
            ((), 103, 4_000_000_000, "5" * 64),
        ):
            with self.subTest(observed=observed, monotonic=monotonic, head=head):
                with self.assertRaises(ExecutionConfirmationError):
                    validate_new_execution_confirmation_claim(
                        binding=binding,
                        candidate=first,
                        durable_claims=durable,
                        observed_at_epoch=observed,
                        observed_monotonic_ns=monotonic,
                        expected_prior_journal_head_fingerprint=head,
                    )

    def test_all_commands_derive_the_exact_domain_and_operator_role(self):
        binding = production_binding()
        operator_roles = dict(binding.operator_role_fingerprints)
        roles = {
            AuthorityDomainV2.PREFLIGHT: OperatorRoleV2.PREFLIGHT_OPERATOR,
            AuthorityDomainV2.EVIDENCE: OperatorRoleV2.EVIDENCE_OPERATOR,
            AuthorityDomainV2.EXECUTION: OperatorRoleV2.EXECUTION_OPERATOR,
            AuthorityDomainV2.RECOVERY: OperatorRoleV2.RECOVERY_OPERATOR,
        }

        for command in ProductionCommandV2:
            with self.subTest(command=command):
                candidate = execution_candidate(binding, command=command)
                self.assertEqual(
                    candidate.command_domain,
                    dict(binding.command_domains)[command],
                )
                self.assertEqual(
                    candidate.operator_role_fingerprint,
                    operator_roles[roles[candidate.command_domain]],
                )

    def test_parsers_reject_noncanonical_duplicate_extra_or_v2_payloads(self):
        binding = production_binding()
        candidate = execution_candidate(binding)
        mapping = candidate.to_mapping()
        payloads = (
            json.dumps(mapping).encode("ascii"),
            candidate.to_canonical_json()[:-1] + b',"extra":0}',
            b'{"candidate_type":"ExecutionConfirmationCandidateV1",'
            b'"candidate_type":"ExecutionConfirmationCandidateV1"}',
            b'{"claim_type":"DurableAuthorityClaimV2"}',
        )

        for payload in payloads:
            with self.subTest(payload=payload[:40]):
                with self.assertRaises(ExecutionConfirmationError):
                    ExecutionConfirmationCandidateV1.from_json(
                        payload,
                        binding=binding,
                    )
        with self.assertRaises(ExecutionConfirmationError):
            ExecutionConfirmationClaimV1.from_json(
                b'{"claim_type":"DurableAuthorityClaimV2"}',
                binding=binding,
            )


def _fingerprint(domain, value):
    canonical = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + canonical).hexdigest()


if __name__ == "__main__":
    unittest.main()
