"""Bounded parent-side transport for isolated attachment workers."""

from __future__ import annotations

import pickle
from collections.abc import Callable
from multiprocessing.connection import BUFSIZE, Connection
from typing import Any


MAX_WORKER_MESSAGE_BYTES = BUFSIZE * 2
_POLL_INTERVAL_SECONDS = 0.05


def receive_worker_message(
    process: Any,
    receive_connection: Connection,
    deadline: float,
    clock: Callable[[], float],
) -> tuple[object | None, bool]:
    """Read before child exit can block on a full one-way pipe."""
    while True:
        remaining = deadline - clock()
        if remaining <= 0:
            return None, True
        try:
            ready = receive_connection.poll(
                min(_POLL_INTERVAL_SECONDS, remaining)
            )
        except Exception:
            return None, False
        if ready:
            return _read_worker_message(receive_connection)
        if _process_alive(process) is False:
            if clock() >= deadline:
                return None, True
            try:
                final_ready = receive_connection.poll(0)
            except Exception:
                return None, False
            return (
                _read_worker_message(receive_connection)
                if final_ready else (None, False)
            )


def _read_worker_message(
    receive_connection: Connection,
) -> tuple[object | None, bool]:
    try:
        payload = receive_connection.recv_bytes(MAX_WORKER_MESSAGE_BYTES)
        return pickle.loads(payload), False
    except Exception:
        return None, False


def _process_alive(process: Any) -> bool | None:
    try:
        value = process.is_alive()
    except Exception:
        return None
    return value if isinstance(value, bool) else None
