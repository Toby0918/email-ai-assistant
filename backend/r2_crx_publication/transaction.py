"""Independent held-source CRX PREPARE/PUBLISH transaction."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from backend.r2_database_publication.windows_handle import SourceHandle

from .canonical import fingerprint
from .contracts import (
    CrxCrashGap,
    CrxFaultSelectorV1,
    CrxPendingState,
    CrxPublicationPrerequisiteV1,
    CrxPublicationStatus,
    build_receipt,
)
from .journal import CrxJournal
from .review import ReviewedCrxV1, format_version, review_source


class SyntheticCrxPublicationTransaction:
    def __init__(self, *, source, staging, target, journal, prerequisite, review):
        self._source = source
        self._staging = staging
        self._target = target
        self._prerequisite = prerequisite
        self._review: ReviewedCrxV1 = review
        self._journal = CrxJournal(journal)
        self._selector = CrxFaultSelectorV1.none()
        self._source_handle = None
        self._staging_identity = None
        self._target_identity = "0" * 64
        self._state = CrxPendingState.EFFECT_ABSENT_EXACT
        self._executed = False

    @property
    def records(self):
        return self._journal.records

    def execute(self, selector: CrxFaultSelectorV1):
        if self._executed or type(selector) is not CrxFaultSelectorV1:
            raise ValueError("crx_transaction_invocation_invalid")
        self._executed = True
        self._selector = selector
        self._open_source()
        try:
            self._boundary("crx_prepare", self._prepare)
            self._boundary("crx_publish", self._publish)
            self._state = CrxPendingState.EFFECT_PRESENT_EXACT
            return self._receipt(CrxPublicationStatus.PUBLISHED)
        finally:
            self._close_source()

    def recover(self):
        target_exact = _exact_artifact(self._target, self._review)
        staging_exact = _exact_artifact(self._staging, self._review)
        if target_exact and not self._staging.exists():
            self._state = CrxPendingState.EFFECT_PRESENT_EXACT
            os.rename(self._target, self._staging)
            self._state = CrxPendingState.EFFECT_ABSENT_EXACT
        elif not self._target.exists():
            self._state = CrxPendingState.EFFECT_ABSENT_EXACT
        else:
            self._state = CrxPendingState.EFFECT_AMBIGUOUS
        material = fingerprint(
            "crx-recovery-class-v1",
            [self._state.value, target_exact, staging_exact],
        )
        self._journal.append("crx_recovery", "classified", material)
        status = (
            CrxPublicationStatus.INCIDENT_STOP
            if self._state is CrxPendingState.EFFECT_AMBIGUOUS
            else CrxPublicationStatus.RECOVERED
        )
        self._journal.append(
            "crx_recovery",
            "committed",
            fingerprint("crx-recovery-result-v1", status.value),
        )
        return self._receipt(status)

    def close(self) -> None:
        self._close_source()
        self._journal.close()

    def _open_source(self) -> None:
        if type(self._prerequisite) is not CrxPublicationPrerequisiteV1:
            raise ValueError("crx_prerequisite_invalid")
        handle = SourceHandle(self._source)
        observed = handle.observe()
        payload = handle.read_all(limit=1024 * 1024 * 1024)
        if not _matches_review(payload, observed.identity_fingerprint, self._review):
            handle.close()
            raise ValueError("crx_source_changed")
        self._source_handle = handle

    def _prepare(self) -> str:
        payload = self._source_handle.read_all(limit=1024 * 1024 * 1024)
        partial = self._selector.kind == "partial_staging"
        written = payload[: max(1, len(payload) // 2)] if partial else payload
        _write_create_only(self._staging, written)
        self._staging_identity = _native_identity(self._staging)
        if partial:
            raise RuntimeError("crx_partial_staging")
        self._inject_source_or_review_failure()
        if self._staging.read_bytes() != payload:
            raise ValueError("crx_staging_verification_failed")
        return fingerprint(
            "crx-prepare-result-v1",
            [self._staging_identity, self._review.artifact_hash],
        )

    def _publish(self) -> str:
        self._inject_target_fault()
        if self._target.exists() or self._target.is_symlink():
            raise ValueError("crx_target_collision")
        os.rename(self._staging, self._target)
        target_handle = SourceHandle(self._target)
        try:
            observed = target_handle.observe()
            payload = target_handle.read_all(limit=1024 * 1024 * 1024)
            digest = hashlib.sha256(payload).hexdigest()
            if self._selector.kind == "verification_failure":
                try:
                    self._target.write_bytes(b"blocked-verification-race")
                except OSError:
                    raise ValueError(
                        "crx_target_verification_write_blocked"
                    ) from None
                raise ValueError("crx_target_verification_hold_failed")
            source_payload = self._source_handle.read_all(
                limit=1024 * 1024 * 1024
            )
            if (
                digest != self._review.artifact_hash
                or payload != source_payload
                or not _matches_review(
                    source_payload,
                    self._review.source_identity_fingerprint,
                    self._review,
                )
                or _native_identity(self._target) != self._staging_identity
            ):
                raise ValueError("crx_final_verification_failed")
            self._target_identity = observed.identity_fingerprint
            target_handle.read_all(limit=1024 * 1024 * 1024)
            self._source_handle.read_all(limit=1024 * 1024 * 1024)
            return fingerprint(
                "crx-publish-result-v1",
                [self._target_identity, digest],
            )
        finally:
            target_handle.close()

    def _inject_source_or_review_failure(self) -> None:
        if self._selector.kind == "source_replacement":
            try:
                os.rename(self._source, self._source.with_suffix(".replaced"))
            except OSError:
                raise ValueError("crx_source_replacement_blocked") from None
            raise ValueError("crx_source_replaced")
        if self._selector.kind == "hash_drift":
            raise ValueError("crx_hash_drift")
        if self._selector.kind == "size_drift":
            raise ValueError("crx_size_drift")

    def _inject_target_fault(self) -> None:
        if self._selector.kind in {"collision", "target_race"}:
            self._target.write_bytes(b"synthetic-collision")
        elif self._selector.kind == "reparse":
            try:
                os.symlink(self._source, self._target)
            except OSError:
                self._target.mkdir()

    def _boundary(self, boundary: str, callback) -> None:
        intent = fingerprint(
            "crx-boundary-intent-v1",
            [boundary, self._prerequisite.contract_fingerprint],
        )
        self._journal.append(boundary, "intent", intent)
        self._cut(boundary, CrxCrashGap.AFTER_INTENT)
        observed = callback()
        self._cut(boundary, CrxCrashGap.AFTER_EFFECT)
        self._journal.append(boundary, "effect_observed", observed)
        self._cut(boundary, CrxCrashGap.AFTER_STABLE_VERIFY)
        self._journal.append(boundary, "stable_verified", observed)
        self._journal.append(boundary, "committed", observed)
        self._cut(boundary, CrxCrashGap.AFTER_COMMIT)

    def _cut(self, boundary: str, gap: CrxCrashGap) -> None:
        if (
            self._selector.kind == "crash"
            and self._selector.boundary == boundary
            and self._selector.gap is gap
        ):
            raise RuntimeError("crx_transaction_interrupted")

    def _close_source(self) -> None:
        if self._source_handle is not None:
            self._source_handle.close()
            self._source_handle = None

    def _receipt(self, status):
        retained = sum(
            path.exists() or path.is_symlink()
            for path in (self._staging, self._target)
        )
        return build_receipt(
            status=status,
            state=self._state,
            review=self._review,
            target_identity=self._target_identity,
            retained=retained,
        )


def _write_create_only(path: Path, payload: bytes) -> None:
    handle = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY,
        0o600,
    )
    try:
        offset = 0
        while offset < len(payload):
            written = os.write(handle, payload[offset : offset + 64 * 1024])
            if written <= 0:
                raise OSError("crx_stage_write_failed")
            offset += written
        os.fsync(handle)
    finally:
        os.close(handle)


def _matches_review(payload: bytes, identity: str, review: ReviewedCrxV1):
    return (
        identity == review.source_identity_fingerprint
        and len(payload) == review.size_bytes
        and hashlib.sha256(payload).hexdigest() == review.artifact_hash
        and format_version(payload) == review.format_version
    )


def _exact_artifact(path: Path, review: ReviewedCrxV1) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        observed = review_source(path)
    except Exception:
        return False
    return (
        observed.artifact_hash == review.artifact_hash
        and observed.size_bytes == review.size_bytes
        and observed.format_version == review.format_version
    )


def _native_identity(path: Path) -> str:
    stat = path.stat(follow_symlinks=False)
    return fingerprint("crx-native-identity-v1", [stat.st_dev, stat.st_ino])
