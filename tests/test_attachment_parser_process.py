"""Real-process tests for hard-deadline attachment parsing."""

from __future__ import annotations

import multiprocessing
import os
import pickle
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import BUFSIZE, Connection
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from unittest.mock import patch

from backend.email_agent import attachment_parser
from backend.email_agent.attachment_model_context import (
    AttachmentAnalysisBundle,
    AttachmentModelCandidate,
)
from backend.email_agent.attachment_storage import StoredAttachment


TIMEOUT_LIMITATION = "Attachment parsing timed out; content was not parsed."
WORKER_FAILURE_LIMITATION = "Attachment content could not be parsed in the isolated worker."


def _display(item: StoredAttachment, status: str = "parsed") -> dict[str, object]:
    return {
        "filename": item.safe_filename,
        "type": item.type,
        "status": status,
        "summary": "Synthetic attachment result.",
        "key_facts": ["Synthetic fact."],
        "limitations": [],
    }


def _valid_bundle(item: StoredAttachment, source_id: str) -> AttachmentAnalysisBundle:
    return AttachmentAnalysisBundle(
        _display(item),
        AttachmentModelCandidate(source_id, "Synthetic model candidate."),
    )


def _hang_target(
    _item: StoredAttachment,
    _source_id: str,
    _deadline: float,
    _send_connection: Connection,
) -> None:
    while True:
        time.sleep(0.05)


def _crash_target(
    _item: StoredAttachment,
    _source_id: str,
    _deadline: float,
    _send_connection: Connection,
) -> None:
    os._exit(23)


def _eof_target(
    _item: StoredAttachment,
    _source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    send_connection.close()


def _malformed_target(
    _item: StoredAttachment,
    _source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    try:
        send_connection.send({"private_path": r"C:\private\customer.pdf"})
    finally:
        send_connection.close()


def _unpicklable_target(
    _item: StoredAttachment,
    _source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    try:
        send_connection.send_bytes(b"not-a-pickle C:\\private\\customer.pdf")
    finally:
        send_connection.close()


def _wrong_source_target(
    item: StoredAttachment,
    _source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    try:
        send_connection.send(_valid_bundle(item, "attachment:999"))
    finally:
        send_connection.close()


def _wrong_filename_target(
    item: StoredAttachment,
    source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    display = _display(item)
    display["filename"] = "private-customer-name.pdf"
    try:
        send_connection.send(AttachmentAnalysisBundle(
            display,
            AttachmentModelCandidate(source_id, "partial private candidate"),
        ))
    finally:
        send_connection.close()


def _extra_field_target(
    item: StoredAttachment,
    source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    display = _display(item)
    display["private_path"] = r"C:\private\customer.pdf"
    try:
        send_connection.send(AttachmentAnalysisBundle(
            display,
            AttachmentModelCandidate(source_id, "partial private candidate"),
        ))
    finally:
        send_connection.close()


def _shared_deadline_target(
    item: StoredAttachment,
    source_id: str,
    _deadline: float,
    send_connection: Connection,
) -> None:
    if source_id == "attachment:0":
        try:
            send_connection.send(_valid_bundle(item, source_id))
        finally:
            send_connection.close()
        return
    _hang_target(item, source_id, _deadline, send_connection)


class _TrackedProcess:
    def __init__(self, process: multiprocessing.Process, *, ignore_terminate: bool = False) -> None:
        self._process = process
        self._ignore_terminate = ignore_terminate
        self.join_timeouts: list[float | None] = []
        self.terminate_calls = 0
        self.kill_calls = 0
        self.close_calls = 0
        self._closed_alive = False
        self._closed_exitcode: int | None = None

    def start(self) -> None:
        self._process.start()

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)
        self._process.join(timeout)

    def is_alive(self) -> bool:
        if self.close_calls:
            return self._closed_alive
        return self._process.is_alive()

    def terminate(self) -> None:
        self.terminate_calls += 1
        if not self._ignore_terminate:
            self._process.terminate()

    def kill(self) -> None:
        self.kill_calls += 1
        self._process.kill()

    def close(self) -> None:
        self.close_calls += 1
        self._closed_alive = self._process.is_alive()
        self._closed_exitcode = self._process.exitcode
        self._process.close()

    @property
    def pid(self) -> int | None:
        return self._process.pid

    @property
    def exitcode(self) -> int | None:
        if self.close_calls:
            return self._closed_exitcode
        return self._process.exitcode


class _SpawnContextWrapper:
    def __init__(
        self,
        worker_target: Callable[[StoredAttachment, str, float, Connection], None],
        *,
        ignore_terminate: bool = False,
    ) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._worker_target = worker_target
        self._ignore_terminate = ignore_terminate
        self.processes: list[_TrackedProcess] = []
        self.pipes: list[tuple[Connection, Connection]] = []
        self.worker_deadlines: list[float] = []

    def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
        pipe = self._context.Pipe(duplex=duplex)
        self.pipes.append(pipe)
        return pipe

    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _TrackedProcess:
        del target
        self.worker_deadlines.append(args[2])
        process = _TrackedProcess(
            self._context.Process(target=self._worker_target, args=args),
            ignore_terminate=self._ignore_terminate,
        )
        self.processes.append(process)
        return process


class _StartFailureProcess:
    def __init__(self) -> None:
        self.start_calls = 0
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1
        raise OSError(r"C:\private\spawn-secret")

    def is_alive(self) -> bool:
        return False

    def close(self) -> None:
        self.close_calls += 1


class _StartFailureContext:
    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")
        self.processes: list[_StartFailureProcess] = []
        self.pipes: list[tuple[Connection, Connection]] = []

    def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
        pipe = self._context.Pipe(duplex=duplex)
        self.pipes.append(pipe)
        return pipe

    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _StartFailureProcess:
        del target, args
        process = _StartFailureProcess()
        self.processes.append(process)
        return process


class _ConstructionFailureContext:
    def __init__(self, failure_stage: str) -> None:
        self._context = multiprocessing.get_context("spawn")
        self._failure_stage = failure_stage
        self.pipes: list[tuple[Connection, Connection]] = []

    def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
        if self._failure_stage == "pipe":
            raise OSError(r"C:\private\pipe-secret")
        pipe = self._context.Pipe(duplex=duplex)
        self.pipes.append(pipe)
        return pipe

    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _StartFailureProcess:
        del target, args
        raise OSError(r"C:\private\process-secret")

    def cleanup(self) -> None:
        for receive_connection, send_connection in self.pipes:
            receive_connection.close()
            send_connection.close()


class _ReadyConnection:
    def __init__(self) -> None:
        self.poll_calls = 0
        self.recv_calls = 0

    def poll(self, _timeout: float = 0.0) -> bool:
        self.poll_calls += 1
        return True

    def recv(self) -> object:
        self.recv_calls += 1
        return object()

    def recv_bytes(self, _maxlength: int | None = None) -> bytes:
        self.recv_calls += 1
        return b""


class _AlwaysAliveProcess:
    def __init__(self) -> None:
        self.join_timeouts: list[float | None] = []

    def is_alive(self) -> bool:
        return True

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)


class _CaptureSendConnection:
    def __init__(self) -> None:
        self.sent_objects: list[object] = []
        self.sent_bytes: list[bytes] = []
        self.close_calls = 0

    def send(self, value: object) -> None:
        self.sent_objects.append(value)

    def send_bytes(self, value: bytes) -> None:
        self.sent_bytes.append(value)

    def close(self) -> None:
        self.close_calls += 1


class _DeadlineBeforeStartProcess:
    def __init__(self) -> None:
        self.start_calls = 0
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def is_alive(self) -> bool:
        return False

    def close(self) -> None:
        self.close_calls += 1


class _DeadlineBeforeStartContext:
    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")
        self.processes: list[_DeadlineBeforeStartProcess] = []
        self.pipes: list[tuple[Connection, Connection]] = []

    def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
        pipe = self._context.Pipe(duplex=duplex)
        self.pipes.append(pipe)
        return pipe

    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _DeadlineBeforeStartProcess:
        del target, args
        process = _DeadlineBeforeStartProcess()
        self.processes.append(process)
        return process


class _RaiseAfterStartProcess(_TrackedProcess):
    def start(self) -> None:
        self._process.start()
        raise OSError(r"C:\private\post-start-secret")

    def force_cleanup(self) -> None:
        try:
            alive = self._process.is_alive()
        except ValueError:
            return
        if alive:
            self._process.terminate()
        self._process.join(1)
        try:
            self._process.close()
        except ValueError:
            pass


class _RaiseAfterStartContext(_SpawnContextWrapper):
    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _RaiseAfterStartProcess:
        del target
        self.worker_deadlines.append(args[2])
        process = _RaiseAfterStartProcess(
            self._context.Process(target=_hang_target, args=args),
        )
        self.processes.append(process)
        return process


class _CloseRaisingConnection:
    def __init__(self, connection: Connection) -> None:
        self._connection = connection
        self.close_calls = 0

    @property
    def closed(self) -> bool:
        return self._connection.closed

    def close(self) -> None:
        self.close_calls += 1
        self._connection.close()
        raise OSError(r"C:\private\close-secret")

    def poll(self, timeout: float = 0.0) -> bool:
        return self._connection.poll(timeout)

    def recv_bytes(self, maxlength: int | None = None) -> bytes:
        return self._connection.recv_bytes(maxlength)


class _CleanupErrorProcess:
    def __init__(self) -> None:
        self.start_calls = 0
        self.join_calls = 0
        self.is_alive_calls = 0
        self.terminate_calls = 0
        self.kill_calls = 0
        self.close_calls = 0

    def start(self) -> None:
        self.start_calls += 1

    def join(self, _timeout: float | None = None) -> None:
        self.join_calls += 1
        raise OSError(r"C:\private\join-secret")

    def is_alive(self) -> bool:
        self.is_alive_calls += 1
        raise AssertionError("private liveness state")

    def terminate(self) -> None:
        self.terminate_calls += 1
        raise OSError(r"C:\private\terminate-secret")

    def kill(self) -> None:
        self.kill_calls += 1
        raise AssertionError("private kill state")

    def close(self) -> None:
        self.close_calls += 1
        raise OSError(r"C:\private\process-close-secret")


class _CleanupErrorContext:
    def __init__(self) -> None:
        self._context = multiprocessing.get_context("spawn")
        self.processes: list[_CleanupErrorProcess] = []
        self.pipes: list[tuple[_CloseRaisingConnection, _CloseRaisingConnection]] = []

    def Pipe(self, duplex: bool = True) -> tuple[_CloseRaisingConnection, _CloseRaisingConnection]:
        receive_connection, send_connection = self._context.Pipe(duplex=duplex)
        wrapped = (
            _CloseRaisingConnection(receive_connection),
            _CloseRaisingConnection(send_connection),
        )
        self.pipes.append(wrapped)
        return wrapped

    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _CleanupErrorProcess:
        del target, args
        process = _CleanupErrorProcess()
        self.processes.append(process)
        return process

    def cleanup(self) -> None:
        for receive_connection, send_connection in self.pipes:
            for connection in (receive_connection, send_connection):
                if not connection.closed:
                    connection._connection.close()


class _BlockingLifecycleProcess:
    def __init__(self, *, start_delay: float = 0.0, control_delay: float = 0.0) -> None:
        self.start_delay = start_delay
        self.control_delay = control_delay
        self.start_finished = threading.Event()
        self.stopped = threading.Event()
        self.closed = threading.Event()
        self._alive = False
        self.terminate_calls = 0
        self.kill_calls = 0

    def start(self) -> None:
        time.sleep(self.start_delay)
        self._alive = True
        self.start_finished.set()

    def join(self, timeout: float | None = None) -> None:
        if timeout:
            time.sleep(min(timeout, 0.01))

    def is_alive(self) -> bool:
        return self._alive

    def terminate(self) -> None:
        self.terminate_calls += 1
        time.sleep(self.control_delay)

    def kill(self) -> None:
        self.kill_calls += 1
        time.sleep(self.control_delay)
        self._alive = False
        self.stopped.set()

    def close(self) -> None:
        time.sleep(self.control_delay)
        self.closed.set()


class _BlockingLifecycleContext:
    def __init__(self, process: _BlockingLifecycleProcess) -> None:
        self._context = multiprocessing.get_context("spawn")
        self.process = process
        self.pipes: list[tuple[Connection, Connection]] = []

    def Pipe(self, duplex: bool = True) -> tuple[Connection, Connection]:
        pipe = self._context.Pipe(duplex=duplex)
        self.pipes.append(pipe)
        return pipe

    def Process(self, *, target: Callable[..., None], args: tuple[Any, ...]) -> _BlockingLifecycleProcess:
        del target, args
        return self.process


class AttachmentParserProcessTests(unittest.TestCase):
    def test_receive_never_reads_a_ready_pipe_while_process_is_alive(self) -> None:
        process = _AlwaysAliveProcess()
        connection = _ReadyConnection()
        clock_values = iter((99.0, 101.0))

        message, timed_out = attachment_parser._receive_message(
            process,
            connection,
            100.0,
            lambda: next(clock_values),
        )

        self.assertTrue(timed_out)
        self.assertIsNone(message)
        self.assertEqual(connection.recv_calls, 0)
        self.assertGreaterEqual(len(process.join_timeouts), 1)

    def test_worker_message_limit_is_strictly_below_pipe_capacity(self) -> None:
        limit = getattr(attachment_parser, "_MAX_WORKER_MESSAGE_BYTES", None)

        self.assertIsInstance(limit, int)
        self.assertGreater(limit, 0)
        self.assertLess(limit, BUFSIZE)

    def test_worker_sends_only_bounded_serialized_bytes(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "oversized.pdf")
            oversized = AttachmentAnalysisBundle(
                _display(item),
                AttachmentModelCandidate("attachment:0", "X" * (BUFSIZE * 2)),
            )
            connection = _CaptureSendConnection()

            with patch.object(attachment_parser, "_parse_one_bundle", return_value=oversized):
                attachment_parser._attachment_worker(
                    item,
                    "attachment:0",
                    time.monotonic() + 3,
                    connection,
                )

        self.assertEqual(connection.sent_objects, [])
        self.assertEqual(len(connection.sent_bytes), 1)
        self.assertLessEqual(
            len(connection.sent_bytes[0]),
            attachment_parser._MAX_WORKER_MESSAGE_BYTES,
        )
        transferred = pickle.loads(connection.sent_bytes[0])
        self.assertEqual(transferred.display_insight["status"], "metadata_only")
        self.assertIsNone(transferred.model_candidate)
        self.assertEqual(connection.close_calls, 1)

    def test_deadline_expiring_during_construction_prevents_start(self) -> None:
        with TemporaryDirectory() as directory:
            items = [
                self._item(directory, f"construction-deadline-{index}.pdf")
                for index in range(3)
            ]
            context = _DeadlineBeforeStartContext()
            clock_values = [99.0, 101.0]

            result = self._parse_bundles(
                items,
                deadline=100.0,
                mp_context=context,
                clock=lambda: clock_values.pop(0) if clock_values else 101.0,
            )

        self.assertEqual(len(result), 3)
        self.assertTrue(all(
            bundle.display_insight["limitations"] == [TIMEOUT_LIMITATION]
            for bundle in result
        ))
        self.assertEqual(len(context.processes), 1)
        self.assertEqual(context.processes[0].start_calls, 0)
        self.assertTrue(self._wait_until(lambda: context.processes[0].close_calls == 1))
        self.assertEqual(context.processes[0].close_calls, 1)
        self._assert_all_pipes_closed(context.pipes)

    def test_live_child_is_cleaned_when_start_raises_after_spawning(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "post-start-failure.pdf")
            context = _RaiseAfterStartContext(_hang_target)
            try:
                result = self._parse_bundles(
                    [item],
                    deadline=time.monotonic() + 3,
                    mp_context=context,
                )

                process = context.processes[0]
                self.assertTrue(self._wait_until(
                    lambda: not process.is_alive() and process.close_calls == 1
                ))
                self.assertEqual(
                    result[0].display_insight["limitations"],
                    [WORKER_FAILURE_LIMITATION],
                )
                self.assertFalse(process.is_alive())
                self.assertGreaterEqual(process.terminate_calls, 1)
                self.assertEqual(process.close_calls, 1)
                self._assert_all_pipes_closed(context.pipes)
            finally:
                for process in context.processes:
                    process.force_cleanup()

    def test_cleanup_errors_never_escape_or_replace_safe_timeout(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "cleanup-errors.pdf")
            context = _CleanupErrorContext()
            clock_values = [99.0, 99.0, 99.0, 101.0]
            try:
                try:
                    result = self._parse_bundles(
                        [item],
                        deadline=100.0,
                        mp_context=context,
                        clock=lambda: clock_values.pop(0) if clock_values else 101.0,
                    )
                except (OSError, AssertionError) as exc:
                    self.fail(f"cleanup error escaped: {type(exc).__name__}")

                process = context.processes[0]
                self.assertTrue(self._wait_until(lambda: process.close_calls == 1))
                self.assertEqual(result[0].display_insight["limitations"], [TIMEOUT_LIMITATION])
                self.assertGreaterEqual(process.join_calls, 1)
                self.assertGreaterEqual(process.is_alive_calls, 1)
                self.assertGreaterEqual(process.terminate_calls, 1)
                self.assertGreaterEqual(process.kill_calls, 1)
                self.assertEqual(process.close_calls, 1)
                self._assert_all_pipes_closed(context.pipes)
            finally:
                context.cleanup()

    def test_blocking_start_returns_by_deadline_then_quarantines_delayed_worker(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "blocking-start.pdf")
            process = _BlockingLifecycleProcess(start_delay=0.3)
            context = _BlockingLifecycleContext(process)
            started = time.monotonic()

            result = self._parse_bundles(
                [item], deadline=started + 0.05, mp_context=context
            )
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.2)
            self.assertEqual(result[0].display_insight["limitations"], [TIMEOUT_LIMITATION])
            self.assertTrue(process.start_finished.wait(timeout=1.0))
            self.assertTrue(process.stopped.wait(timeout=1.0))
            self.assertTrue(process.closed.wait(timeout=1.0))
            self.assertFalse(process.is_alive())
            self._assert_all_pipes_closed(context.pipes)

    def test_blocking_cleanup_controls_do_not_overrun_deadline_or_leave_worker(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "blocking-cleanup.pdf")
            process = _BlockingLifecycleProcess(control_delay=0.25)
            context = _BlockingLifecycleContext(process)
            started = time.monotonic()

            result = self._parse_bundles(
                [item], deadline=started + 0.05, mp_context=context
            )
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 0.2)
            self.assertEqual(result[0].display_insight["limitations"], [TIMEOUT_LIMITATION])
            self.assertTrue(process.stopped.wait(timeout=2.0))
            self.assertTrue(process.closed.wait(timeout=2.0))
            self.assertGreaterEqual(process.terminate_calls, 1)
            self.assertGreaterEqual(process.kill_calls, 1)
            self.assertFalse(process.is_alive())
            self._assert_all_pipes_closed(context.pipes)

    def test_default_spawn_uses_production_worker_and_returns_validated_bundle(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "wrong.txt")
            baseline_pids = {child.pid for child in multiprocessing.active_children()}

            result = attachment_parser.parse_attachment_bundles(
                [item],
                deadline=time.monotonic() + 5,
            )

        self.assertEqual(result[0].display_insight["status"], "metadata_only")
        self.assertIn("Only .pdf files", result[0].display_insight["limitations"][0])
        self.assertIsNone(result[0].model_candidate)
        active_pids = {child.pid for child in multiprocessing.active_children()}
        self.assertFalse(active_pids - baseline_pids)

    def test_spawned_hanging_worker_is_terminated_killed_joined_and_closed(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "hanging.pdf")
            context = _SpawnContextWrapper(_hang_target, ignore_terminate=True)
            baseline_pids = {child.pid for child in multiprocessing.active_children()}
            started = time.monotonic()

            result = self._parse_bundles(
                [item],
                deadline=started + 0.3,
                mp_context=context,
            )

            self.assertLess(time.monotonic() - started, 2.0)
            self.assertEqual(result[0].display_insight["status"], "metadata_only")
            self.assertEqual(result[0].display_insight["limitations"], [TIMEOUT_LIMITATION])
            self.assertIsNone(result[0].model_candidate)
            self.assertEqual(len(context.processes), 1)
            process = context.processes[0]
            self.assertTrue(self._wait_until(
                lambda: not process.is_alive() and process.close_calls == 1
            ))
            self.assertEqual(process.terminate_calls, 1)
            self.assertEqual(process.kill_calls, 1)
            self.assertGreaterEqual(len(process.join_timeouts), 2)
            self.assertEqual(process.close_calls, 1)
            self.assertFalse(process.is_alive())
            self.assertIsNotNone(process.exitcode)
            self._assert_all_pipes_closed(context.pipes)
            active_pids = {child.pid for child in multiprocessing.active_children()}
            self.assertFalse(active_pids - baseline_pids)

    def test_shared_deadline_stops_starting_workers_after_expiry(self) -> None:
        with TemporaryDirectory() as directory:
            items = [self._item(directory, f"item-{index}.pdf") for index in range(3)]
            context = _SpawnContextWrapper(_shared_deadline_target)
            deadline = 100.0

            def shared_clock() -> float:
                return 101.0 if len(context.processes) >= 2 else 99.0

            result = self._parse_bundles(
                items,
                deadline=deadline,
                mp_context=context,
                clock=shared_clock,
            )

            self.assertEqual(len(result), 3)
            self.assertEqual(result[0].display_insight["status"], "parsed")
            self.assertEqual(result[0].model_candidate.source_id, "attachment:0")
            self.assertTrue(all(
                bundle.display_insight["limitations"] == [TIMEOUT_LIMITATION]
                for bundle in result[1:]
            ))
            self.assertEqual(len(context.processes), 2)
            self.assertEqual(context.worker_deadlines, [deadline, deadline])
            self.assertTrue(self._wait_until(
                lambda: all(process.close_calls == 1 for process in context.processes)
            ))
            self.assertTrue(all(not process.is_alive() for process in context.processes))
            self.assertTrue(all(process.close_calls == 1 for process in context.processes))
            self._assert_all_pipes_closed(context.pipes)

    def test_expired_before_start_returns_safe_result_without_creating_process(self) -> None:
        with TemporaryDirectory() as directory:
            items = [self._item(directory, f"expired-{index}.pdf") for index in range(3)]
            context = _SpawnContextWrapper(_hang_target)

            result = self._parse_bundles(
                items,
                deadline=time.monotonic() - 0.01,
                mp_context=context,
            )

            self.assertEqual(len(result), 3)
            self.assertTrue(all(
                bundle.display_insight["limitations"] == [TIMEOUT_LIMITATION]
                and bundle.model_candidate is None
                for bundle in result
            ))
            self.assertEqual(context.processes, [])
            self.assertEqual(context.pipes, [])

    def test_crash_eof_and_malformed_messages_are_fixed_safe_failures(self) -> None:
        cases = (
            _crash_target,
            _eof_target,
            _malformed_target,
            _unpicklable_target,
            _wrong_source_target,
            _wrong_filename_target,
            _extra_field_target,
        )
        for target in cases:
            with self.subTest(target=target.__name__), TemporaryDirectory() as directory:
                item = self._item(directory, "safe-name.pdf")
                context = _SpawnContextWrapper(target)

                result = self._parse_bundles(
                    [item],
                    deadline=time.monotonic() + 3,
                    mp_context=context,
                )

                self.assertEqual(
                    result[0].display_insight["limitations"],
                    [WORKER_FAILURE_LIMITATION],
                )
                self.assertIsNone(result[0].model_candidate)
                self.assertNotIn("private", repr(result).lower())
                self.assertTrue(all(not process.is_alive() for process in context.processes))
                self.assertEqual(context.processes[0].close_calls, 1)
                self._assert_all_pipes_closed(context.pipes)

    def test_start_failure_is_fixed_safe_failure_and_closes_endpoints(self) -> None:
        with TemporaryDirectory() as directory:
            item = self._item(directory, "start-failure.pdf")
            context = _StartFailureContext()

            result = self._parse_bundles(
                [item],
                deadline=time.monotonic() + 3,
                mp_context=context,
            )

            self.assertEqual(
                result[0].display_insight["limitations"],
                [WORKER_FAILURE_LIMITATION],
            )
            self.assertIsNone(result[0].model_candidate)
            self.assertNotIn("spawn-secret", repr(result))
            self.assertEqual(context.processes[0].start_calls, 1)
            self.assertTrue(self._wait_until(lambda: context.processes[0].close_calls == 1))
            self.assertEqual(context.processes[0].close_calls, 1)
            self._assert_all_pipes_closed(context.pipes)

    def test_pipe_and_process_creation_failures_are_fixed_safe_failures(self) -> None:
        for failure_stage in ("pipe", "process"):
            with self.subTest(failure_stage=failure_stage), TemporaryDirectory() as directory:
                item = self._item(directory, "construction-failure.pdf")
                context = _ConstructionFailureContext(failure_stage)
                try:
                    try:
                        result = self._parse_bundles(
                            [item],
                            deadline=time.monotonic() + 3,
                            mp_context=context,
                        )
                    except OSError as exc:
                        self.fail(f"{failure_stage} OSError escaped: {type(exc).__name__}")
                    self.assertEqual(
                        result[0].display_insight["limitations"],
                        [WORKER_FAILURE_LIMITATION],
                    )
                    self.assertIsNone(result[0].model_candidate)
                    self._assert_all_pipes_closed(context.pipes)
                finally:
                    context.cleanup()

    @staticmethod
    def _parse_bundles(
        items: list[StoredAttachment],
        *,
        deadline: float,
        mp_context: object,
        clock: Callable[[], float] = time.monotonic,
    ) -> list[AttachmentAnalysisBundle]:
        parser = getattr(attachment_parser, "parse_attachment_bundles", None)
        if parser is None:
            raise AssertionError("parse_attachment_bundles must be implemented")
        return parser(items, deadline=deadline, mp_context=mp_context, clock=clock)

    @staticmethod
    def _item(directory: str, filename: str) -> StoredAttachment:
        path = Path(directory) / filename
        path.write_bytes(b"synthetic")
        return StoredAttachment(
            safe_filename=filename,
            type="pdf",
            path=path,
            byte_size=path.stat().st_size,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )

    @staticmethod
    def _assert_all_pipes_closed(pipes: list[tuple[Connection, Connection]]) -> None:
        for receive_connection, send_connection in pipes:
            if not receive_connection.closed or not send_connection.closed:
                raise AssertionError("parse_attachment_bundles left a pipe endpoint open")

    @staticmethod
    def _wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(0.01)
        return predicate()


if __name__ == "__main__":
    unittest.main()
