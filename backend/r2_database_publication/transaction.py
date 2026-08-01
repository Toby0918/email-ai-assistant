"""Quiescence-first, leased database publication and local recovery."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .canonical import fingerprint
from .contracts import (
    DatabaseCheckpoint,
    DatabaseCrashGap,
    DatabaseFaultSelectorV1,
    DatabaseTransactionResultV1,
    DatabaseTransactionStatus,
    QuiescencePrerequisitesV1,
)
from .journal import DatabaseJournal
from .lease import close_lease, copy_once, issue_lease, lease_read_passes, verify_again
from .service import LegacyServiceControllerRole, StoppedServiceReceiptV1

_SIDECARS = ("-wal", "-shm", "-journal")


class SyntheticDatabasePublicationTransaction:
    _stopped_receipt_type = StoppedServiceReceiptV1

    def __init__(self, *, source, staging, target, journal, prerequisites, controller) -> None:
        self._source = source
        self._staging = staging
        self._target = target
        self._prerequisites = prerequisites
        self._controller = controller
        self._journal = DatabaseJournal(journal)
        self._source_hash = _hash(source)
        self._lease = None
        self._selector = DatabaseFaultSelectorV1.none()
        self._events: list[str] = []
        self._checkpoints: list[DatabaseCheckpoint] = []
        self._executed = False

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(self._events)

    @property
    def checkpoints(self) -> tuple[DatabaseCheckpoint, ...]:
        return tuple(self._checkpoints)

    @property
    def records(self):
        return self._journal.records

    def execute(self, selector: DatabaseFaultSelectorV1) -> DatabaseTransactionResultV1:
        if self._executed or type(selector) is not DatabaseFaultSelectorV1:
            raise ValueError("database_transaction_invocation_invalid")
        self._executed = True
        self._selector = selector
        self._verify_prerequisites()
        stopped = self._quiesce()
        try:
            self._checkpoint(DatabaseCheckpoint.POST_STOP_BASELINE)
            self._checkpoint(DatabaseCheckpoint.PRE_COPY_LEASE)
            self._lease = issue_lease(self._source, stopped, self._source_hash)
            self._boundary("database_prepare", self._prepare)
            self._boundary("database_publish", self._publish)
            self._checkpoint(DatabaseCheckpoint.FINAL_OR_RECOVERY_VERIFY)
            self._journal.verify()
            return self._result(DatabaseTransactionStatus.PUBLISHED)
        finally:
            close_lease(self._lease)

    def recover(self) -> DatabaseTransactionResultV1:
        close_lease(self._lease)
        self._lease = None
        try:
            self._checkpoint(DatabaseCheckpoint.FINAL_OR_RECOVERY_VERIFY, inject=False)
        except ValueError:
            return self._result(DatabaseTransactionStatus.INCIDENT_STOP)
        state = self._classify_local_state()
        self._journal.append("database_recovery", "classified", fingerprint("database-recovery-class-v1", state))
        if state == "published_exact":
            os.rename(self._target, self._staging)
            state = "staging_exact"
        status = DatabaseTransactionStatus.INCIDENT_STOP if state in {"collision", "ambiguous"} else DatabaseTransactionStatus.RECOVERED
        self._journal.append("database_recovery", "committed", fingerprint("database-recovery-result-v1", status.value))
        return self._result(status)

    def close(self) -> None:
        close_lease(self._lease)
        self._journal.close()

    def _verify_prerequisites(self) -> None:
        if type(self._prerequisites) is not QuiescencePrerequisitesV1:
            raise ValueError("quiescence_prerequisites_invalid")
        self._events.append("prerequisites:verified")

    def _quiesce(self):
        material = self._prerequisites.contract_fingerprint
        self._journal.append("legacy_service_quiescence", "intent", material)
        self._events.append("quiescence:intent")
        receipt = self._controller.quiesce()
        self._events.append("service:stopped")
        self._journal.append("legacy_service_quiescence", "effect_observed", receipt.observation_fingerprint)
        self._journal.append("legacy_service_quiescence", "stable_verified", receipt.receipt_fingerprint)
        self._journal.append("legacy_service_quiescence", "committed", receipt.receipt_fingerprint)
        return receipt

    def _boundary(self, boundary: str, callback) -> None:
        material = fingerprint("database-boundary-intent-v1", [boundary, self._source_hash])
        self._journal.append(boundary, "intent", material)
        self._events.append(boundary + ":intent")
        self._cut(boundary, DatabaseCrashGap.AFTER_INTENT)
        observed = callback()
        self._cut(boundary, DatabaseCrashGap.AFTER_EFFECT)
        self._journal.append(boundary, "effect_observed", observed)
        self._cut(boundary, DatabaseCrashGap.AFTER_STABLE_VERIFY)
        self._journal.append(boundary, "stable_verified", observed)
        self._journal.append(boundary, "committed", observed)
        self._cut(boundary, DatabaseCrashGap.AFTER_COMMIT)

    def _prepare(self) -> str:
        partial = self._selector.kind == "partial_staging"
        size, digest = copy_once(self._lease, self._staging, partial=partial)
        if (
            digest != self._source_hash
            or size != self._source.stat().st_size
            or _hash(self._staging) != digest
        ):
            raise ValueError("database_prepare_mismatch")
        return fingerprint("database-prepare-observation-v1", [digest, size])

    def _publish(self) -> str:
        if self._selector.kind == "collision":
            self._target.write_bytes(b"synthetic-collision")
        if self._target.exists():
            raise ValueError("database_target_collision")
        os.rename(self._staging, self._target)
        size, digest = verify_again(self._lease)
        if self._selector.kind == "source_drift":
            digest = "0" * 64
        if digest != self._source_hash or size != self._target.stat().st_size or _hash(self._target) != digest:
            raise ValueError("database_source_drift")
        self._checkpoint(DatabaseCheckpoint.COPY_POSTVERIFY)
        return fingerprint("database-publish-observation-v1", [digest, size])

    def _checkpoint(self, checkpoint: DatabaseCheckpoint, *, inject: bool = True) -> None:
        if inject and self._selector.kind == "sidecar" and self._selector.checkpoint is checkpoint:
            self._source.with_name(self._source.name + self._selector.sidecar_suffix).write_bytes(b"synthetic-sidecar")
        self._checkpoints.append(checkpoint)
        if any(self._source.with_name(self._source.name + suffix).exists() for suffix in _SIDECARS):
            raise ValueError("database_sidecar_present")

    def _cut(self, boundary: str, gap: DatabaseCrashGap) -> None:
        if self._selector.kind == "crash" and self._selector.boundary == boundary and self._selector.gap is gap:
            raise RuntimeError("database_transaction_interrupted")

    def _classify_local_state(self) -> str:
        target = _existing_hash(self._target)
        staging = _existing_hash(self._staging)
        if target == self._source_hash and staging is None:
            return "published_exact"
        if target is None and staging in {None, self._source_hash}:
            return "staging_exact"
        if target is None and staging is not None:
            return "staging_partial"
        if target is not None and staging is not None:
            return "collision"
        return "ambiguous"

    def _result(self, status: DatabaseTransactionStatus) -> DatabaseTransactionResultV1:
        retained = sum(path.exists() for path in (self._staging, self._target))
        passes = 0 if self._lease is None else lease_read_passes(self._lease)
        body = [status.value, self._journal.head, passes, retained]
        return DatabaseTransactionResultV1(status, fingerprint("database-transaction-result-v1", body), passes, retained, 0)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _existing_hash(path: Path) -> str | None:
    return _hash(path) if path.is_file() else None
