"""Detached Windows probe proving terminal input cannot unlock preflight."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import ctypes
from pathlib import Path


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--execution-confirmation-proof":
        return run_execution_confirmation_proof(Path(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--closure-cli-proof":
        return run_closure_cli_proof(Path(sys.argv[2]))
    if len(sys.argv) != 2:
        return 2
    target = Path(sys.argv[1])
    if target.exists() or not target.parent.is_dir():
        return 3
    result = run_dormant_module(
        "backend.r2_preflight_process",
        "current-topology",
        target.parent,
    )
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


def run_execution_confirmation_proof(target):
    try:
        if os.name != "nt" or target.exists() or not target.parent.is_dir():
            return 3
        from backend.r2_production_binding import (
            ExecutionConfirmationError,
            ProductionCommandV2,
            confirm_execution_confirmation_v1,
            prepare_execution_confirmation_v1,
            production_action_fingerprint_v2,
        )
        from tests.r2_execution_confirmation_fixture import (
            CLOSURE_MANIFEST,
            SOLO_ATTESTATION,
            production_binding,
        )

        binding = production_binding()
        action = production_action_fingerprint_v2(
            binding, ProductionCommandV2.EXECUTE
        )
        candidates = tuple(
            _prepare_execution_candidate(
                prepare_execution_confirmation_v1, binding,
                ProductionCommandV2.EXECUTE, action, sequence,
                CLOSURE_MANIFEST, SOLO_ATTESTATION,
            )
            for sequence in (1, 2)
        )
        return _confirm_in_real_console(
            target, candidates, confirm_execution_confirmation_v1,
            ExecutionConfirmationError,
        )
    except Exception:
        return 4


def run_closure_cli_proof(target):
    try:
        if os.name != "nt" or target.exists() or not target.parent.is_dir():
            return 3
        from backend.r2_solo_maintainer_closure import closure as closure_adapter
        from scripts import close_r2_final_master as cli

        fingerprint = "1" * 64
        acknowledgement = "CONFIRM_SOLO_MAINTAINER_CLOSURE_V1_NOT_ISSUE39_AUTHORITY"
        candidate_payload = (
            '{"confirmation_acknowledgement":"' + acknowledgement
            + '","manifest_fingerprint":"' + fingerprint + '"}'
        ).encode("ascii")
        receipt_payload = b'{"receipt":"recorded"}'
        guard_ids, stable = [], [0]

        class _Value:
            def __init__(self, payload):
                self.payload = payload

            def to_canonical_json(self):
                return self.payload

        class _Closure:
            def prepare(self):
                guard_ids.append(id(closure_adapter._ACTIVE_CONSOLE_CEREMONY.get()))
                return _Value(candidate_payload)

            def confirm(self, supplied_fingerprint, supplied_acknowledgement):
                if (supplied_fingerprint != fingerprint
                        or supplied_acknowledgement != acknowledgement):
                    raise RuntimeError("input mismatch")
                guard = closure_adapter._ACTIVE_CONSOLE_CEREMONY.get()
                guard.require_current()
                stable[0] = 1
                guard_ids.append(id(guard))
                with closure_adapter._console_ceremony() as nested:
                    guard_ids.append(id(nested))
                return _Value(receipt_payload)

        return _run_closure_cli(
            target, cli, _Closure, fingerprint, acknowledgement,
            candidate_payload, receipt_payload, guard_ids, stable,
        )
    except Exception:
        return 4


def _run_closure_cli(target, cli, closure_type, fingerprint, acknowledgement,
                     candidate_payload, receipt_payload, guard_ids, stable):
    original = (sys.argv, sys.stdout, sys.stderr, cli.SoloMaintainerClosure,
                cli._read_console_line, cli._require_no_pending_input)
    counted_stdout = _CountingConsoleStream(sys.stdout)
    counted_stderr = _CountingConsoleStream(sys.stderr)
    reads, pending_checks = [0], [0]

    def read_line(handle):
        reads[0] += 1
        return original[4](handle)

    def require_no_pending(ceremony):
        pending_checks[0] += 1
        return original[5](ceremony)

    try:
        sys.argv = ["close_r2_final_master.py", "confirm"]
        sys.stdout, sys.stderr = counted_stdout, counted_stderr
        cli.SoloMaintainerClosure = closure_type
        cli._read_console_line = read_line
        cli._require_no_pending_input = require_no_pending
        _queue_console_input(fingerprint + "\r" + acknowledgement + "\r")
        exit_code = cli.main()
    finally:
        (sys.argv, sys.stdout, sys.stderr, cli.SoloMaintainerClosure,
         cli._read_console_line, cli._require_no_pending_input) = original
    candidate_line = candidate_payload.decode("ascii") + "\n"
    receipt_line = receipt_payload.decode("ascii") + "\n"
    proof = {
        "acknowledgement_count": "".join(counted_stderr.writes).count(acknowledgement),
        "candidate_line_count": counted_stderr.writes.count(candidate_line),
        "exit_code": exit_code,
        "fingerprint_count": "".join(counted_stderr.writes).count(fingerprint),
        "pending_check_count": pending_checks[0],
        "read_count": reads[0],
        "receipt_line_count": counted_stdout.writes.count(receipt_line),
        "same_guard_object": int(len(guard_ids) == 3 and len(set(guard_ids)) == 1),
        "stable_console": stable[0],
        "stderr_write_count": len(counted_stderr.writes),
        "stdout_write_count": len(counted_stdout.writes),
    }
    target.write_text(json.dumps(proof, sort_keys=True, separators=(",", ":")),
                      encoding="utf-8")
    return 0


def _prepare_execution_candidate(prepare, binding, command, action, sequence,
                                 closure_manifest, solo_attestation):
    return prepare(
        binding=binding,
        closure_manifest_fingerprint=closure_manifest,
        solo_maintainer_attestation_receipt_fingerprint=solo_attestation,
        command=command,
        action_fingerprint=action,
        journal_owner_fingerprint="2" * 64,
        prior_journal_head_fingerprint="3" * 64,
        transition_instance_fingerprint="4" * 64,
        remaining_reverse_plan_fingerprint="0" * 64,
        claim_sequence=sequence,
    )


def _confirm_in_real_console(target, candidates, confirm, error_type):
    candidate, extra_candidate = candidates
    original_stdout, original_stderr = sys.stdout, sys.stderr
    counted_stdout = _CountingConsoleStream(original_stdout)
    counted_stderr = _CountingConsoleStream(original_stderr)
    try:
        sys.stdout, sys.stderr = counted_stdout, counted_stderr
        before = candidate._runtime.console.snapshot()
        _queue_console_input(
            candidate.candidate_fingerprint
            + "\r"
            + candidate.confirmation_acknowledgement
            + "\r"
        )
        claim = confirm(candidate=candidate)
        after = candidate._runtime.console.snapshot()
        _queue_console_input(
            extra_candidate.candidate_fingerprint + "\r"
            + extra_candidate.confirmation_acknowledgement + "\rEXTRA\r"
        )
        try:
            confirm(candidate=extra_candidate)
        except error_type:
            extra_line_rejected = 1
        else:
            extra_line_rejected = 0
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
    proof = {
        "candidate_line_count": counted_stdout.writes.count(
            candidate.candidate_fingerprint + "\n"
        ),
        "acknowledgement_line_count": counted_stdout.writes.count(
            candidate.confirmation_acknowledgement + "\n"
        ),
        "stdout_write_count": len(counted_stdout.writes),
        "stderr_write_count": len(counted_stderr.writes),
        "console_identity_stable": int(before == after),
        "extra_line_rejected": extra_line_rejected,
        "stdin_stdout_stderr_console_verified": int(len(before) == 3),
        "confirmation_recorded": int(claim.confirmed_at_epoch >= candidate.prepared_at_epoch),
    }
    target.write_text(
        json.dumps(proof, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


class _CountingConsoleStream:
    def __init__(self, stream):
        self._stream = stream
        self.writes = []

    def write(self, value):
        self.writes.append(value)
        return self._stream.write(value)

    def flush(self):
        return self._stream.flush()

    def isatty(self):
        return self._stream.isatty()

    def fileno(self):
        return self._stream.fileno()


def _queue_console_input(value):
    from ctypes import wintypes

    class KeyEvent(ctypes.Structure):
        _fields_ = (("down", wintypes.BOOL), ("repeat", wintypes.WORD),
                    ("virtual_key", wintypes.WORD), ("scan", wintypes.WORD),
                    ("character", wintypes.WCHAR), ("control", wintypes.DWORD))

    class Event(ctypes.Union):
        _fields_ = (("key", KeyEvent),)

    class InputRecord(ctypes.Structure):
        _fields_ = (("event_type", wintypes.WORD), ("event", Event))

    records = (InputRecord * len(value))()
    for index, character in enumerate(value):
        records[index].event_type = 1
        records[index].event.key = KeyEvent(
            True, 1, 13 if character == "\r" else 0, 0, character, 0
        )
    handle = __import__("msvcrt").get_osfhandle(sys.stdin.fileno())
    written = wintypes.DWORD()
    accepted = ctypes.windll.kernel32.WriteConsoleInputW(
        ctypes.c_void_p(handle), records, len(records), ctypes.byref(written)
    )
    if accepted == 0 or written.value != len(records):
        raise RuntimeError("console input rejected")


def run_dormant_module(module, verb, workdir):
    root = Path(__file__).resolve().parents[1]
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONPATH": str(root),
            "R2_ISSUE39_APPROVED": "1",
            "R2_EXECUTION_CONFIRMATION": "synthetic-unlock-attempt",
        }
    )
    completed = subprocess.run(
        (sys.executable, "-B", "-m", module, verb),
        cwd=workdir,
        env=environment,
        input="synthetic-unlock-attempt\n",
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return {
        "exit_code": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


if __name__ == "__main__":
    raise SystemExit(main())
