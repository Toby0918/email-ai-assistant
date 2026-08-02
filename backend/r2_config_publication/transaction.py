"""Independent loader-compatible Config PREPARE/PUBLISH transaction."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from backend.email_agent.config import build_managed_container_config
from backend.email_agent.managed_runtime_validation import read_managed_settings
from backend.r2_database_publication.windows_handle import SourceHandle

from .canonical import fingerprint
from .contracts import (
    ConfigCrashGap,
    ConfigFaultSelectorV1,
    ConfigPendingState,
    ConfigPublicationPrerequisiteV1,
    ConfigPublicationStatus,
    ManagedConfigSelectionV1,
    build_receipt,
)
from .journal import ConfigJournal


class SyntheticConfigPublicationTransaction:
    def __init__(
        self,
        *,
        selection,
        staging,
        target,
        journal,
        prerequisite,
        sqlite_path,
        attachment_temp_dir,
    ) -> None:
        self._selection = selection
        self._payload = selection.dotenv_bytes()
        self._document = hashlib.sha256(self._payload).hexdigest()
        self._staging = staging
        self._target = target
        self._prerequisite = prerequisite
        self._sqlite_path = sqlite_path
        self._attachment_temp_dir = attachment_temp_dir
        self._journal = ConfigJournal(journal)
        self._selector = ConfigFaultSelectorV1.none()
        self._staging_identity = None
        self._target_identity = "0" * 64
        self._state = ConfigPendingState.EFFECT_ABSENT_EXACT
        self._executed = False

    @property
    def records(self):
        return self._journal.records

    def execute(self, selector: ConfigFaultSelectorV1):
        if (
            self._executed
            or type(selector) is not ConfigFaultSelectorV1
            or type(self._prerequisite) is not ConfigPublicationPrerequisiteV1
        ):
            raise ValueError("config_transaction_invocation_invalid")
        self._executed = True
        self._selector = selector
        self._boundary("config_prepare", self._prepare)
        self._boundary("config_publish", self._publish)
        self._state = ConfigPendingState.EFFECT_PRESENT_EXACT
        return self._receipt(ConfigPublicationStatus.PUBLISHED)

    def recover(self):
        target_exact = _exact_document(self._target, self._payload)
        staging_exact = _exact_document(self._staging, self._payload)
        if target_exact and not self._staging.exists():
            self._state = ConfigPendingState.EFFECT_PRESENT_EXACT
            os.rename(self._target, self._staging)
            self._state = ConfigPendingState.EFFECT_ABSENT_EXACT
        elif not self._target.exists():
            self._state = ConfigPendingState.EFFECT_ABSENT_EXACT
        else:
            self._state = ConfigPendingState.EFFECT_AMBIGUOUS
        classified = fingerprint(
            "config-recovery-class-v1",
            [self._state.value, target_exact, staging_exact],
        )
        self._journal.append("config_recovery", "classified", classified)
        status = (
            ConfigPublicationStatus.INCIDENT_STOP
            if self._state is ConfigPendingState.EFFECT_AMBIGUOUS
            else ConfigPublicationStatus.RECOVERED
        )
        self._journal.append(
            "config_recovery",
            "committed",
            fingerprint("config-recovery-result-v1", status.value),
        )
        return self._receipt(status)

    def close(self) -> None:
        self._journal.close()

    def _prepare(self) -> str:
        payload = self._faulted_payload()
        _write_create_only(self._staging, payload)
        self._staging_identity = _identity(self._staging)
        if self._selector.kind == "partial_staging":
            raise RuntimeError("config_partial_staging")
        if self._staging.read_bytes() != self._payload:
            raise ValueError("config_document_drift")
        return fingerprint(
            "config-prepare-result-v1",
            [self._staging_identity, self._document],
        )

    def _publish(self) -> str:
        if self._selector.kind == "collision":
            self._target.write_bytes(b"synthetic-collision")
        if self._target.exists() or self._target.is_symlink():
            raise ValueError("config_target_collision")
        os.rename(self._staging, self._target)
        target_handle = SourceHandle(self._target)
        try:
            observed = target_handle.observe()
            payload = target_handle.read_all(limit=16 * 1024)
            if payload != self._payload:
                raise ValueError("config_target_drift")
            self._inject_target_replacement()
            self._verify_loader()
            if (
                target_handle.read_all(limit=16 * 1024) != self._payload
                or _identity(self._target) != self._staging_identity
            ):
                raise ValueError("config_target_drift")
            self._target_identity = observed.identity_fingerprint
            return fingerprint(
                "config-publish-result-v1",
                [self._target_identity, self._document],
            )
        finally:
            target_handle.close()

    def _verify_loader(self) -> None:
        settings = read_managed_settings(self._target)
        expected = {
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": ",".join(
                self._selection.internal_email_domains
            ),
            "EMAIL_AGENT_LOG_LEVEL": self._selection.log_level,
        }
        if settings != expected:
            raise ValueError("config_loader_mismatch")
        config = build_managed_container_config(
            sqlite_path=self._sqlite_path,
            attachment_temp_dir=self._attachment_temp_dir,
            settings=settings,
        )
        if self._selector.kind == "loader_mismatch" or not _expected_config(
            config, self._selection, self._sqlite_path, self._attachment_temp_dir
        ):
            raise ValueError("config_loader_mismatch")

    def _faulted_payload(self) -> bytes:
        if self._selector.kind == "partial_staging":
            return self._payload[: max(1, len(self._payload) // 2)]
        if self._selector.kind == "encoding_drift":
            return b"\xef\xbb\xbf" + self._payload
        if self._selector.kind == "line_ending_drift":
            return self._payload.replace(b"\n", b"\r\n")
        return self._payload

    def _inject_target_replacement(self) -> None:
        if self._selector.kind != "target_replacement":
            return
        try:
            os.rename(self._target, self._target.with_suffix(".replaced"))
        except OSError:
            raise ValueError("config_target_replacement_blocked") from None
        raise ValueError("config_target_replaced")

    def _boundary(self, boundary: str, callback) -> None:
        intent = fingerprint(
            "config-boundary-intent-v1",
            [boundary, self._prerequisite.contract_fingerprint],
        )
        self._journal.append(boundary, "intent", intent)
        self._cut(boundary, ConfigCrashGap.AFTER_INTENT)
        observed = callback()
        self._cut(boundary, ConfigCrashGap.AFTER_EFFECT)
        self._journal.append(boundary, "effect_observed", observed)
        self._cut(boundary, ConfigCrashGap.AFTER_STABLE_VERIFY)
        self._journal.append(boundary, "stable_verified", observed)
        self._journal.append(boundary, "committed", observed)
        self._cut(boundary, ConfigCrashGap.AFTER_COMMIT)

    def _cut(self, boundary: str, gap: ConfigCrashGap) -> None:
        if (
            self._selector.kind == "crash"
            and self._selector.boundary == boundary
            and self._selector.gap is gap
        ):
            raise RuntimeError("config_transaction_interrupted")

    def _receipt(self, status):
        retained = sum(
            path.exists() or path.is_symlink()
            for path in (self._staging, self._target)
        )
        return build_receipt(
            status=status,
            state=self._state,
            selection=self._selection,
            document=self._document,
            target=self._target_identity,
            retained=retained,
        )


def _write_create_only(path: Path, payload: bytes) -> None:
    handle = os.open(
        path,
        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_BINARY,
        0o600,
    )
    try:
        written = os.write(handle, payload)
        if written != len(payload):
            raise OSError("config_stage_write_failed")
        os.fsync(handle)
    finally:
        os.close(handle)


def _expected_config(config, selection, sqlite_path, attachment_temp_dir):
    return (
        config.log_level == selection.log_level
        and config.internal_email_domains == selection.internal_email_domains
        and config.sqlite_path == str(sqlite_path)
        and config.attachment_temp_dir == str(attachment_temp_dir)
        and config.openai_api_key is None
        and config.deepseek_api_key is None
        and config.llm_provider == "disabled"
        and config.text_fallback_provider == "disabled"
        and not config.private_knowledge_enabled
        and config.private_knowledge_authority_root == ""
        and config.private_knowledge_snapshot_path == ""
    )


def _exact_document(path: Path, expected: bytes) -> bool:
    return path.is_file() and not path.is_symlink() and path.read_bytes() == expected


def _identity(path: Path) -> str:
    metadata = path.stat(follow_symlinks=False)
    return fingerprint(
        "config-native-identity-v1",
        [metadata.st_dev, metadata.st_ino],
    )
