"""Stopped-source, write-blocking, create-only SQLite publication."""

from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)

from .canonical import canonical_json, fail
from .errors import ManagedActivationError
from .publication_scope import PublicationScopeWindow
from .receipts import StoppedDatabaseCopyReceiptV1
from .scope_models import _SyntheticActivationScope
from .stopped_service import StoppedServiceReceiptV1

_ERROR = "stopped_database_copy_failed"
_SIDECARS = ("-wal", "-shm", "-journal")


class StoppedDatabaseCopier:
    """Copy one exact stopped SQLite source without mutating it."""

    def __new__(cls, *args: object, **kwargs: object):
        raise TypeError("StoppedDatabaseCopier exposes copy() only")

    @classmethod
    def copy(
        cls,
        *,
        scope: object,
        stopped_service_receipt: object,
    ) -> StoppedDatabaseCopyReceiptV1:
        if type(scope) is not _SyntheticActivationScope:
            fail("database_scope_invalid")
        stopped = _validated_stopped_receipt(scope, stopped_service_receipt)
        source = scope.review.scenario.database_source
        target = scope.review.scenario.database_target
        api = WindowsReadHandleApi()
        handle = None
        try:
            handle = api.open_existing(source, deny_write=True)
            original = api.observe(handle)
            return _copy_held(
                scope, stopped, api, handle, original, source, target
            )
        except ManagedActivationError:
            raise
        except Exception:
            fail(_ERROR)
        finally:
            if handle is not None:
                try:
                    api.close(handle)
                except Exception:
                    if not _exception_active():
                        fail(_ERROR)


def _copy_held(scope, stopped, api, handle, original, source, target):
    _validate_source_identity(scope, original)
    source_hash = _hash_file(source)
    if source_hash != scope.review.database_source_fingerprint:
        fail("database_source_changed")
    _require_absent_sidecars(source)
    _require_integrity(source)
    receipt = _publish_held_target(
        scope, stopped, api, handle, original, source, target, source_hash
    )
    _require_absent_sidecars(source)
    if _hash_file(source) != source_hash:
        fail("database_source_changed")
    api.require_stable(handle, original, source)
    return receipt


def _publish_held_target(
    scope, stopped, api, handle, original, source, target, source_hash
):
    window = None
    try:
        window = PublicationScopeWindow.open(scope=scope, role="database")
        window.create_target()
        window.copy_from_path(source)
        window.flush()
        destination = window.read_all()
        destination_hash = hashlib.sha256(destination).hexdigest()
        if destination_hash != source_hash:
            fail("database_copy_mismatch")
        _require_integrity(target)
        if _hash_file(source) != source_hash:
            fail("database_source_changed")
        _require_absent_sidecars(source)
        api.require_stable(handle, original, source)
        window.verify_target()
        receipt = _receipt(
            scope, stopped, original, source_hash, destination_hash, target
        )
    except ManagedActivationError as error:
        if window is not None:
            window.close(active_error=True)
        _map_target_error(error)
    except Exception:
        if window is not None:
            window.close(active_error=True)
        raise
    try:
        window.close(active_error=False)
    except ManagedActivationError:
        fail(_ERROR)
    return receipt


def _map_target_error(error: ManagedActivationError) -> None:
    if str(error) in {
        "database_target_collision",
        "database_copy_mismatch",
        "database_source_changed",
        "database_sidecar_present",
        "database_integrity_failed",
        "managed_activation_scope_drift",
    }:
        raise error
    fail(_ERROR)


def _receipt(scope, stopped, original, source_hash, destination_hash, target):
    observation = hashlib.sha256(
        canonical_json(
            {
                "source_identity": original.object_identity_fingerprint,
                "source_sha256": source_hash,
                "destination_sha256": destination_hash,
                "size_bytes": target.stat().st_size,
                "flushed": True,
            },
            code=_ERROR,
        )
    ).hexdigest()
    return StoppedDatabaseCopyReceiptV1.create(
        operation_fingerprint=scope.review.operation_fingerprint,
        profile_fingerprint=scope.profile.profile_fingerprint,
        governing_master_commit=scope.profile.governing_master_commit,
        authorization_fingerprint=scope.authorization_fingerprint,
        input_fingerprints=(
            stopped.receipt_fingerprint,
            source_hash,
            scope.review.database_schema_fingerprint,
        ),
        observation_fingerprint=observation,
        counts={"published": 1, "rejected": 0},
    )


def _validated_stopped_receipt(scope, value) -> StoppedServiceReceiptV1:
    if type(value) is not StoppedServiceReceiptV1:
        fail("stopped_service_receipt_invalid")
    stopped = StoppedServiceReceiptV1.from_mapping(value.to_mapping())
    if (
        stopped.operation_fingerprint
        != scope.review.operation_fingerprint
        or stopped.profile_fingerprint != scope.profile.profile_fingerprint
        or stopped.governing_master_commit
        != scope.profile.governing_master_commit
        or stopped.authorization_fingerprint
        != scope.authorization_fingerprint
        or stopped.database_source_fingerprint
        != scope.review.database_source_fingerprint
        or stopped.service_role_fingerprint
        != scope.review.stopped_service_role_fingerprint
    ):
        fail("stopped_service_receipt_invalid")
    return stopped


def _validate_source_identity(scope, observed) -> None:
    if (
        observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or not observed.fixed_drive
        or observed.object_identity_fingerprint
        != scope.review.database_native_identity
    ):
        fail("database_source_changed")


def _require_absent_sidecars(source: Path) -> None:
    for suffix in _SIDECARS:
        sidecar = source.with_name(source.name + suffix)
        try:
            sidecar.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            fail("database_sidecar_present")
        fail("database_sidecar_present")


def _require_integrity(path: Path) -> None:
    connection = None
    try:
        uri = path.resolve(strict=True).as_uri() + "?mode=ro&immutable=1"
        connection = sqlite3.connect(uri, uri=True, timeout=0)
        connection.execute("PRAGMA query_only = ON")
        result = connection.execute("PRAGMA quick_check(1)").fetchall()
        if result != [("ok",)]:
            fail("database_integrity_failed")
    except (OSError, sqlite3.Error):
        fail("database_integrity_failed")
    finally:
        if connection is not None:
            connection.close()


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            while True:
                block = handle.read(64 * 1024)
                if not block:
                    break
                digest.update(block)
    except OSError:
        fail(_ERROR)
    return digest.hexdigest()


def _exception_active() -> bool:
    import sys

    return sys.exc_info()[0] is not None
