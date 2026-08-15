"""Stable create-only migration of the fixed historical SQLite database."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

from backend.cutover_managed_activation.windows_file_handles import WindowsReadHandleApi

from .durable_io import read_segment, write_segment


_DATABASE_BYTES = 12_288


def prepare_database(host, attempt):
    source = database_source()
    require_absent_sidecars(source)
    if os.path.lexists(host._layout.database_target):
        raise ValueError("R2_ISSUE39_DATABASE_TARGET_COLLISION")
    api = WindowsReadHandleApi()
    handle = None
    try:
        handle = api.open_existing(source, deny_write=True)
        observed = api.observe(handle)
        _require_source_identity(host, observed)
        if api.require_size_bounded(handle, limit=_DATABASE_BYTES) != _DATABASE_BYTES:
            raise ValueError("R2_ISSUE39_DATABASE_SOURCE_DRIFT")
        payload = api.read_bounded(handle, limit=_DATABASE_BYTES)
        write_segment(attempt, payload)
        if hashlib.sha256(read_segment(attempt)).digest() != hashlib.sha256(payload).digest():
            raise ValueError("R2_ISSUE39_DATABASE_COPY_INVALID")
        database_integrity(attempt)
        require_absent_sidecars(source)
        api.require_stable(handle, observed, source)
    finally:
        if handle is not None:
            api.close(handle)


def database_exact(host, path):
    from .production_path_checks import regular_file

    if not regular_file(path):
        return False
    source = database_source()
    require_absent_sidecars(source)
    api = WindowsReadHandleApi()
    source_handle = target_handle = None
    try:
        source_handle = api.open_existing(source, deny_write=True)
        target_handle = api.open_existing(path, deny_write=True)
        source_observed = api.observe(source_handle)
        target_observed = api.observe(target_handle)
        _require_source_identity(host, source_observed)
        if not _same_database_bytes(api, source_handle, target_handle):
            return False
        database_integrity(path)
        api.require_stable(source_handle, source_observed, source)
        api.require_stable(target_handle, target_observed, path)
        require_absent_sidecars(source)
        return True
    finally:
        if target_handle is not None:
            api.close(target_handle)
        if source_handle is not None:
            api.close(source_handle)


def _require_source_identity(host, observed):
    if (
        observed.object_identity_fingerprint
        != host._prepared._inputs.database_identity_fingerprint
    ):
        raise ValueError("R2_ISSUE39_DATABASE_SOURCE_DRIFT")


def _same_database_bytes(api, source_handle, target_handle):
    source_size, source_hash = api.hash_bounded(source_handle, limit=_DATABASE_BYTES)
    target_size, target_hash = api.hash_bounded(target_handle, limit=_DATABASE_BYTES)
    return source_size == _DATABASE_BYTES and (
        source_size, source_hash
    ) == (target_size, target_hash)


def database_source():
    return Path(r"D:\Projects\email-ai-assistant\-local-data\email_agent.sqlite3")


def require_absent_sidecars(source):
    if any(os.path.lexists(str(source) + suffix) for suffix in ("-wal", "-shm", "-journal")):
        raise ValueError("R2_ISSUE39_DATABASE_SIDECAR_PRESENT")


def database_integrity(path):
    connection = None
    try:
        uri = path.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True, timeout=0)
        connection.execute("PRAGMA query_only = ON")
        if connection.execute("PRAGMA quick_check(1)").fetchall() != [("ok",)]:
            raise ValueError("R2_ISSUE39_DATABASE_INTEGRITY_INVALID")
    finally:
        if connection is not None:
            connection.close()
