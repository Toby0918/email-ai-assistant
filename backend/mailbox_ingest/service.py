"""Small administrator service facade for isolated CLI operations."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .attachment_manifest import parse_reviewed_manifest, prepare_attachments
from .authorization import freeze_window
from .dpapi import DpapiProtector
from .drive_policy import validate_vault_location
from .existing_vault_policy import validate_existing_vault_location
from .imap_readonly import ReadOnlyImapSession
from .inventory_codec import decode_inventory_bundle
from .service_models import CliDependencies
from .service_operations import (
    AttachmentOperation,
    InitOperation,
    InventoryOperation,
    PurgeOperation,
    RevokeOperation,
    RewrapOperation,
    ScanOperation,
    VerifyOperation,
)
from .vault_access import open_mailbox_vault


MAX_MANIFEST_BYTES = 1024 * 1024


@dataclass(frozen=True)
class LocalPreflight:
    vault: Path
    project_root: Path


class MailboxVaultService:
    def __init__(
        self,
        *,
        project_root: Path | None = None,
        epoch_clock: Callable[[], int] | None = None,
        utc_clock: Callable[[], datetime] | None = None,
        validate_new: Callable[..., object] = validate_vault_location,
        validate_existing: Callable[..., object] = validate_existing_vault_location,
        open_vault: Callable[..., object] = open_mailbox_vault,
        dpapi_factory: Callable[[], object] = DpapiProtector,
        session_builder: Callable[[str, str], object] = ReadOnlyImapSession,
    ) -> None:
        self.project_root = (
            Path(__file__).resolve().parents[2]
            if project_root is None
            else Path(project_root)
        )
        self.epoch_clock = (
            (lambda: int(time.time())) if epoch_clock is None else epoch_clock
        )
        self.utc_clock = (
            (lambda: datetime.now(timezone.utc)) if utc_clock is None else utc_clock
        )
        self._validate_new = validate_new
        self._validate_existing = validate_existing
        self._open_vault = open_vault
        self._dpapi_factory = dpapi_factory
        self._session_builder = session_builder

    def preflight(self, arguments: argparse.Namespace) -> LocalPreflight:
        vault = Path(arguments.vault)
        if arguments.command == "init":
            self._validate_new(
                vault, self.project_root, Path(arguments.recovery_key)
            )
        elif arguments.command == "rewrap-recovery":
            self._validate_new(
                vault, self.project_root, Path(arguments.new_recovery_key)
            )
        else:
            self._validate_existing(vault, self.project_root)
        return LocalPreflight(vault, self.project_root)

    def prepare(self, arguments: argparse.Namespace, local: object):
        if not isinstance(local, LocalPreflight):
            raise ValueError
        if arguments.command == "init":
            return InitOperation(
                local.vault, Path(arguments.recovery_key), self._dpapi_factory()
            )
        if arguments.command == "rewrap-recovery":
            return RewrapOperation(
                local.vault,
                Path(arguments.current_recovery_key),
                Path(arguments.new_recovery_key),
                arguments.confirm,
            )
        opened = self._open_vault(
            local.vault,
            dpapi=self._dpapi_factory(),
            clock=self.epoch_clock,
        )
        try:
            scope = opened.authorization_scope(
                arguments.authorization_id, arguments.account
            )
            return self._opened_operation(arguments, opened, scope)
        except Exception:
            opened.close()
            raise

    def _opened_operation(self, arguments, opened, scope):
        command = arguments.command
        if command == "inventory":
            return InventoryOperation(opened, scope, freeze_window(self.utc_clock()))
        if command == "scan":
            bundle = decode_inventory_bundle(opened.control.read("inventory"))
            return ScanOperation(
                opened,
                scope,
                bundle,
                arguments.confirm_inventory_fingerprint,
            )
        if command == "attachments":
            bundle = decode_inventory_bundle(opened.control.read("inventory"))
            manifest = parse_reviewed_manifest(
                _read_manifest(Path(arguments.manifest)),
                expected_scope=scope.opaque_scope_id,
                expected_fingerprint=bundle.inventory.fingerprint,
                now_utc=self.epoch_clock(),
            )
            prepared = prepare_attachments(
                manifest, read_source_record=opened.vault.get_record
            )
            return AttachmentOperation(opened, prepared)
        if command == "verify":
            return VerifyOperation(opened)
        if command == "purge-expired":
            return PurgeOperation(opened, arguments.limit)
        if command == "revoke":
            return RevokeOperation(opened, arguments.confirm)
        raise ValueError

    def session_factory(self, account: str, password: str) -> object:
        return self._session_builder(account, password)


def _read_manifest(path: Path) -> object:
    try:
        metadata = path.lstat()
        if path.is_symlink() or not path.is_file() or not 1 <= metadata.st_size <= MAX_MANIFEST_BYTES:
            raise ValueError
        raw = path.read_bytes()
        if len(raw) != metadata.st_size:
            raise ValueError
        return json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise ValueError("attachment_manifest_invalid") from None


def build_cli_dependencies(
    *,
    getpass_function: Callable[[str], str],
    emit: Callable[[dict[str, object]], None],
    service: MailboxVaultService | None = None,
) -> CliDependencies:
    selected = MailboxVaultService() if service is None else service
    return CliDependencies(
        selected.preflight,
        selected.prepare,
        getpass_function,
        selected.session_factory,
        emit,
    )


__all__ = ["MailboxVaultService", "build_cli_dependencies"]
