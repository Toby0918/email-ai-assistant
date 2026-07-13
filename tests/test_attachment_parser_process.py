"""Real-process tests for hard-deadline attachment parsing."""

from __future__ import annotations

import multiprocessing
import os
import time
import unittest
from datetime import UTC, datetime, timedelta
from multiprocessing.connection import Connection
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

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

    def start(self) -> None:
        self._process.start()

    def join(self, timeout: float | None = None) -> None:
        self.join_timeouts.append(timeout)
        self._process.join(timeout)

    def is_alive(self) -> bool:
        return self._process.is_alive()

    def terminate(self) -> None:
        self.terminate_calls += 1
        if not self._ignore_terminate:
            self._process.terminate()

    def kill(self) -> None:
        self.kill_calls += 1
        self._process.kill()

    @property
    def pid(self) -> int | None:
        return self._process.pid

    @property
    def exitcode(self) -> int | None:
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

    def start(self) -> None:
        self.start_calls += 1
        raise OSError(r"C:\private\spawn-secret")

    def is_alive(self) -> bool:
        return False


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


class AttachmentParserProcessTests(unittest.TestCase):
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
            self.assertEqual(process.terminate_calls, 1)
            self.assertEqual(process.kill_calls, 1)
            self.assertGreaterEqual(len(process.join_timeouts), 2)
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
            self.assertTrue(all(not process.is_alive() for process in context.processes))
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


if __name__ == "__main__":
    unittest.main()
