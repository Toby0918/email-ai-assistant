"""Closed multi-process harness for the fixed Windows real-console proofs.

This test-only module intentionally keeps controller and worker modes together so
every subprocess executes the same reviewed bytes via ``python -m``.  It is the
single boundary for Job-owned process cleanup, external console input, the two
Issue #110 TTY proofs, and the retained dormant-process probe; production code
does not import it.  That closed harness role is the reason this file exceeds the
project's general 300-line recommendation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import ctypes
import time
from ctypes import wintypes
from pathlib import Path

from backend.migration_evidence_verifier.process_tree import ProcessTree


_STD_INPUT_HANDLE = -10
_KEY_EVENT = 0x0001
_PROCESS_TREE_CLEANUP_MARGIN_SECONDS = 1


class _Character(ctypes.Union):
    _fields_ = (
        ("UnicodeChar", wintypes.WCHAR),
        ("AsciiChar", ctypes.c_char),
    )


class _KeyEvent(ctypes.Structure):
    _fields_ = (
        ("bKeyDown", wintypes.BOOL),
        ("wRepeatCount", wintypes.WORD),
        ("wVirtualKeyCode", wintypes.WORD),
        ("wVirtualScanCode", wintypes.WORD),
        ("uChar", _Character),
        ("dwControlKeyState", wintypes.DWORD),
    )


class _Event(ctypes.Union):
    _fields_ = (
        ("KeyEvent", _KeyEvent),
        ("Padding", ctypes.c_byte * 16),
    )


class _InputRecord(ctypes.Structure):
    _fields_ = (("EventType", wintypes.WORD), ("Event", _Event))


def main() -> int:
    if len(sys.argv) == 3 and sys.argv[1] == "--controller-cleanup-proof":
        return _run_console_controller(
            Path(sys.argv[2]), "--controller-cleanup-worker", (), ()
        )
    if len(sys.argv) == 3 and sys.argv[1] == "--execution-confirmation-proof":
        return run_execution_confirmation_controller(Path(sys.argv[2]))
    if len(sys.argv) == 3 and sys.argv[1] == "--closure-cli-proof":
        return run_closure_cli_controller(Path(sys.argv[2]))
    if len(sys.argv) == 5 and sys.argv[1] == "--execution-confirmation-worker":
        return run_execution_confirmation_proof(
            Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
        )
    if len(sys.argv) == 4 and sys.argv[1] == "--closure-cli-worker":
        return run_closure_cli_proof(Path(sys.argv[2]), Path(sys.argv[3]))
    if len(sys.argv) == 3 and sys.argv[1] == "--controller-cleanup-worker":
        return run_controller_cleanup_worker(Path(sys.argv[2]))
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


def run_execution_confirmation_controller(target):
    requests = tuple(
        target.with_name(target.name + f".input-{index}.json")
        for index in (1, 2)
    )
    return _run_console_controller(
        target, "--execution-confirmation-worker", requests, (2, 3)
    )


def run_closure_cli_controller(target):
    request = target.with_name(target.name + ".input-1.json")
    return _run_console_controller(
        target, "--closure-cli-worker", (request,), (2,)
    )


def _run_console_controller(target, worker_mode, requests, line_counts):
    deadline = time.monotonic() + 15
    work_deadline = deadline - _PROCESS_TREE_CLEANUP_MARGIN_SECONDS
    if not _paths_are_create_only(target, requests):
        return 3
    process, console, tree = None, None, None
    result = 4
    try:
        tree = ProcessTree.prepare()
        process = _launch_console_worker(tree, worker_mode, target, requests)
        for index, (request, count) in enumerate(
                zip(requests, line_counts, strict=True), start=1):
            text = _wait_for_input_request(
                process, request, index, count, work_deadline
            )
            if console is None:
                console = _attach_console_input(process.pid)
            _write_console_input(*console, text)
        if console is not None:
            attached, console = console, None
            _free_console(attached)
        remaining = work_deadline - time.monotonic()
        if (remaining > 0 and process.wait(timeout=remaining) == 0
                and target.is_file()):
            result = 0
    except Exception:
        result = 4
    finally:
        if console is not None:
            try:
                _free_console(console)
            except Exception:
                result = 4
        if tree is not None:
            try:
                tree.terminate(process)
            except Exception:
                result = 4
    return result


def _launch_console_worker(tree, worker_mode, target, requests):
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    options = tree.popen_options()
    options["creationflags"] = (
        int(options["creationflags"]) | subprocess.CREATE_NEW_CONSOLE
    )
    process = subprocess.Popen(
        (
            str(Path(sys.executable).with_name("python.exe")),
            "-B", "-m", "tests.windows_real_tty_host",
            worker_mode, str(target), *(str(path) for path in requests),
        ),
        cwd=Path(__file__).resolve().parents[1],
        startupinfo=startup,
        close_fds=True,
        **options,
    )
    tree.attach(process)
    return process


def _free_console(console):
    if not console[0].FreeConsole():
        raise ctypes.WinError(ctypes.get_last_error())


def _paths_are_create_only(target, requests):
    paths = (target, *requests)
    return (
        target.parent.is_dir()
        and all(path.parent == target.parent for path in paths)
        and all(not path.exists() for path in paths)
        and all(not _request_stage(path).exists() for path in requests)
    )


def _wait_for_input_request(process, path, round_number, line_count, deadline):
    while time.monotonic() < deadline:
        if path.is_file():
            return _read_input_request(path, round_number, line_count)
        if process.poll() is not None:
            raise RuntimeError("console worker stopped")
        time.sleep(0.01)
    raise TimeoutError("console input request unavailable")


def _read_input_request(path, round_number, line_count):
    if path.stat().st_size > 10_000:
        raise RuntimeError("console input request oversized")
    value = json.loads(path.read_text(encoding="ascii"))
    if (
        type(value) is not dict
        or set(value) != {"request_type", "round", "text"}
        or value["request_type"] != "WindowsConsoleInputRequestV1"
        or value["round"] != round_number
        or type(value["text"]) is not str
        or value["text"].count("\r") != line_count
        or not value["text"].endswith("\r")
        or any(character != "\r" and not 32 <= ord(character) <= 126
               for character in value["text"])
    ):
        raise RuntimeError("console input request invalid")
    return value["text"]


def _request_stage(path):
    return path.with_name(path.name + ".stage")


def _publish_input_request(path, round_number, text):
    _publish_create_only_json(
        path,
        {
            "request_type": "WindowsConsoleInputRequestV1",
            "round": round_number,
            "text": text,
        },
    )


def _publish_create_only_json(path, value):
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":")
    ).encode("ascii")
    stage = _request_stage(path)
    if path.exists() or stage.exists() or not path.parent.is_dir():
        raise RuntimeError("console handoff collision")
    with stage.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    stage.rename(path)


def run_controller_cleanup_worker(target):
    try:
        if os.name != "nt" or target.exists() or not target.parent.is_dir():
            return 3
        _bind_real_console_streams()
        _publish_create_only_json(
            target,
            {
                "pid": os.getpid(),
                "request_type": "WindowsConsoleWorkerReadyV1",
            },
        )
        sys.stdin.read(1)
        return 4
    except Exception:
        return 4


def run_execution_confirmation_proof(target, first_request, second_request):
    try:
        if os.name != "nt" or not _paths_are_create_only(
                target, (first_request, second_request)):
            return 3
        _bind_real_console_streams()
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
            ExecutionConfirmationError, first_request, second_request,
        )
    except Exception:
        return 4


def run_closure_cli_proof(target, request):
    try:
        if os.name != "nt" or not _paths_are_create_only(target, (request,)):
            return 3
        _bind_real_console_streams()
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
            candidate_payload, receipt_payload, guard_ids, stable, request,
        )
    except Exception:
        return 4


def _run_closure_cli(target, cli, closure_type, fingerprint, acknowledgement,
                     candidate_payload, receipt_payload, guard_ids, stable,
                     request):
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
        counted_stderr.arm_after_flush(
            lambda: _publish_input_request(
                request, 1, fingerprint + "\r" + acknowledgement + "\r"
            )
        )
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


def _confirm_in_real_console(
        target, candidates, confirm, error_type, first_request, second_request):
    candidate, extra_candidate = candidates
    original_stdout, original_stderr = sys.stdout, sys.stderr
    counted_stdout = _CountingConsoleStream(original_stdout)
    counted_stderr = _CountingConsoleStream(original_stderr)
    try:
        sys.stdout, sys.stderr = counted_stdout, counted_stderr
        before = candidate._runtime.console.snapshot()
        _arm_execution_input(counted_stdout, first_request, 1, candidate, "")
        claim = confirm(candidate=candidate)
        after = candidate._runtime.console.snapshot()
        _arm_execution_input(
            counted_stdout, second_request, 2, extra_candidate, "EXTRA\r"
        )
        extra_line_rejected = _confirm_extra_line_rejected(
            confirm, extra_candidate, error_type
        )
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
    proof = _execution_console_proof(
        counted_stdout, counted_stderr, candidate, claim, before, after,
        extra_line_rejected,
    )
    target.write_text(json.dumps(proof, sort_keys=True, separators=(",", ":")),
                      encoding="utf-8")
    return 0


def _arm_execution_input(stream, path, round_number, candidate, extra_line):
    text = (
        candidate.candidate_fingerprint + "\r"
        + candidate.confirmation_acknowledgement + "\r" + extra_line
    )
    stream.arm_after_flush(
        lambda: _publish_input_request(path, round_number, text)
    )


def _confirm_extra_line_rejected(confirm, candidate, error_type):
    try:
        confirm(candidate=candidate)
    except error_type:
        return 1
    return 0


def _execution_console_proof(
        stdout, stderr, candidate, claim, before, after, extra_line_rejected):
    return {
        "candidate_line_count": stdout.writes.count(
            candidate.candidate_fingerprint + "\n"
        ),
        "acknowledgement_line_count": stdout.writes.count(
            candidate.confirmation_acknowledgement + "\n"
        ),
        "stdout_write_count": len(stdout.writes),
        "stderr_write_count": len(stderr.writes),
        "console_identity_stable": int(before == after),
        "extra_line_rejected": extra_line_rejected,
        "stdin_stdout_stderr_console_verified": int(len(before) == 3),
        "confirmation_recorded": int(claim.confirmed_at_epoch >= candidate.prepared_at_epoch),
    }


class _CountingConsoleStream:
    def __init__(self, stream):
        self._stream = stream
        self._after_flush = None
        self.writes = []

    def arm_after_flush(self, callback):
        if self._after_flush is not None:
            raise RuntimeError("console request already armed")
        self._after_flush = callback

    def write(self, value):
        self.writes.append(value)
        return self._stream.write(value)

    def flush(self):
        result = self._stream.flush()
        callback, self._after_flush = self._after_flush, None
        if callback is not None:
            callback()
        return result

    def isatty(self):
        return self._stream.isatty()

    def fileno(self):
        return self._stream.fileno()


def _attach_console_input(process_id):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _configure_console_kernel(kernel)
    time.sleep(0.08)
    if not kernel.AttachConsole(process_id):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        handle = kernel.GetStdHandle(_STD_INPUT_HANDLE)
        if not handle or handle == ctypes.c_void_p(-1).value:
            raise RuntimeError("console input unavailable")
        return kernel, handle
    except Exception:
        kernel.FreeConsole()
        raise


def _write_console_input(kernel, handle, value):
    if not kernel.FlushConsoleInputBuffer(handle):
        raise ctypes.WinError(ctypes.get_last_error())
    records = (_InputRecord * len(value))()
    for index, character in enumerate(value):
        records[index].EventType = _KEY_EVENT
        records[index].Event.KeyEvent = _KeyEvent(
            True, 1, 0, 0, _Character(UnicodeChar=character), 0
        )
    written = wintypes.DWORD()
    if not kernel.WriteConsoleInputW(
            handle, records, len(records), ctypes.byref(written)
    ) or written.value != len(records):
        raise RuntimeError("console input rejected")


def _configure_console_kernel(kernel):
    kernel.AttachConsole.argtypes = (wintypes.DWORD,)
    kernel.AttachConsole.restype = wintypes.BOOL
    kernel.GetStdHandle.argtypes = (wintypes.DWORD,)
    kernel.GetStdHandle.restype = wintypes.HANDLE
    kernel.FlushConsoleInputBuffer.argtypes = (wintypes.HANDLE,)
    kernel.FlushConsoleInputBuffer.restype = wintypes.BOOL
    kernel.WriteConsoleInputW.argtypes = (
        wintypes.HANDLE,
        ctypes.POINTER(_InputRecord),
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    )
    kernel.WriteConsoleInputW.restype = wintypes.BOOL
    kernel.FreeConsole.restype = wintypes.BOOL


def _bind_real_console_streams():
    from ctypes import wintypes
    from msvcrt import get_osfhandle

    streams = (
        open("CONIN$", "r", encoding="utf-8", errors="strict"),
        open("CONOUT$", "w", encoding="utf-8", errors="strict", buffering=1),
        open("CONOUT$", "w", encoding="utf-8", errors="strict", buffering=1),
    )
    kernel = ctypes.windll.kernel32
    get_mode = kernel.GetConsoleMode
    get_mode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    get_mode.restype = wintypes.BOOL
    set_standard = kernel.SetStdHandle
    set_standard.argtypes = (wintypes.DWORD, wintypes.HANDLE)
    set_standard.restype = wintypes.BOOL
    try:
        for stream, identifier in zip(streams, (-10, -11, -12), strict=True):
            handle = get_osfhandle(stream.fileno())
            mode = wintypes.DWORD()
            if (handle == -1 or get_mode(handle, ctypes.byref(mode)) != 1
                    or set_standard(identifier & 0xFFFFFFFF, handle) != 1):
                raise RuntimeError("console stream binding rejected")
        sys.stdin, sys.stdout, sys.stderr = streams
    except Exception:
        for stream in streams:
            stream.close()
        raise


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
