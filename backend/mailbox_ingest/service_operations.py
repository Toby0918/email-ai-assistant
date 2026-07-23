"""Prepared service operations kept outside the administrator CLI parser."""

from __future__ import annotations

from pathlib import Path

from .authorization import AuthorizationScope, DateWindow
from .folder_policy import SelectedFolder
from .inventory import InventoryBundle
from .inventory_codec import encode_inventory_bundle
from .key_envelopes import (
    initialize_key_envelopes,
    load_vault_identity,
    rewrap_recovery_key,
)
from .governed_scan import scan_governed_mailbox
from .service_models import CliResult
from .vault_access import OpenedMailboxVault
from .vault_index import VaultIndex
from .operation_volume import bound_distinct_checker, revalidate_preflight_volume


class OpenedOperation:
    def __init__(self, opened: OpenedMailboxVault) -> None:
        self.opened = opened

    def close(self) -> None:
        self.opened.close()


class InitOperation:
    def __init__(
        self,
        vault: Path,
        recovery: Path,
        dpapi: object,
        project_root: Path,
        preflight_evidence: object,
        validate_volume: object,
        authorization_id: str,
        account: str,
        open_vault: object,
        clock: object,
    ) -> None:
        self.vault = vault
        self.recovery = recovery
        self.dpapi = dpapi
        self.project_root = project_root
        self.preflight_evidence = preflight_evidence
        self.validate_volume = validate_volume
        self.authorization_id = authorization_id
        self.account = account
        self.open_vault = open_vault
        self.clock = clock

    def execute(self, session: object | None) -> CliResult:
        if session is not None:
            raise ValueError
        evidence = revalidate_preflight_volume(
            self.validate_volume,
            self.vault,
            self.project_root,
            self.recovery,
            self.preflight_evidence,
        )
        initialize_key_envelopes(
            self.vault,
            self.recovery,
            self.dpapi,
            distinct_volume_check=bound_distinct_checker(
                self.vault, self.recovery, evidence
            ),
        )
        identity = load_vault_identity(self.vault)
        VaultIndex(
            self.vault / "vault-index.sqlite3", vault_id=identity.vault_id
        ).initialize()
        opened = self.open_vault(
            self.vault, dpapi=self.dpapi, clock=self.clock
        )
        try:
            opened.corpus_index.initialize()
            opened.create_authorization_binding(
                self.authorization_id, self.account
            )
        finally:
            opened.close()
        return CliResult("vault_initialized", count=0)

    def close(self) -> None:
        return None


class InventoryOperation(OpenedOperation):
    def __init__(
        self,
        opened: OpenedMailboxVault,
        scope: AuthorizationScope,
        window: DateWindow,
    ) -> None:
        super().__init__(opened)
        self.scope = scope
        self.window = window

    def execute(self, session: object | None) -> CliResult:
        if session is None:
            raise ValueError
        folders = self.opened.select_folders(session.list_folders())
        bundle = self.opened.inventory(
            session, scope=self.scope, folders=folders, window=self.window
        )
        self.opened.control.write("inventory", encode_inventory_bundle(bundle))
        return CliResult(
            "inventory_complete",
            count=bundle.inventory.total_count,
            fingerprint=bundle.inventory.fingerprint,
            opaque_ids=tuple(
                item.opaque_folder_id for item in bundle.inventory.folders
            ),
            inventory=bundle.inventory,
        )


class ScanOperation(OpenedOperation):
    def __init__(
        self,
        opened: OpenedMailboxVault,
        scope: AuthorizationScope,
        bundle: InventoryBundle,
        confirmed_fingerprint: str,
        sales_policy: object | None = None,
    ) -> None:
        super().__init__(opened)
        if confirmed_fingerprint != bundle.inventory.fingerprint:
            raise ValueError("inventory_fingerprint_mismatch")
        if scope.opaque_scope_id != bundle.inventory.opaque_scope_id:
            raise ValueError("inventory_scope_mismatch")
        self.scope = scope
        self.bundle = bundle
        self.confirmed = confirmed_fingerprint
        self.sales_policy = sales_policy

    def execute(self, session: object | None) -> CliResult:
        if session is None:
            raise ValueError
        folders = tuple(
            SelectedFolder(
                folder.mailbox,
                folder.role,
                folder.opaque_folder_id,
                folder.wire_mailbox,
            )
            for folder in self.bundle.evidence
        )
        window = DateWindow(
            self.bundle.inventory.window_start,
            self.bundle.inventory.window_end,
        )

        def rebuild() -> InventoryBundle:
            return self.opened.inventory(
                session, scope=self.scope, folders=folders, window=window
            )

        if self.sales_policy is None:
            raise ValueError("sales_policy_invalid")
        with self.opened.sales_identity_key() as identity_key:
            report = scan_governed_mailbox(
                session=session,
                inventory_bundle=self.bundle,
                confirmed_fingerprint=self.confirmed,
                vault=self.opened.vault,
                control_store=self.opened.control,
                rebuild_inventory=rebuild,
                sales_policy=self.sales_policy,
                corpus_index=self.opened.corpus_index,
                identity_key=bytes(identity_key),
            )
        return CliResult(
            "scan_complete",
            count=report.processed_count,
            aggregate_counts=report.to_counts(),
        )


class VerifyOperation(OpenedOperation):
    def execute(self, session: object | None) -> CliResult:
        if session is not None:
            raise ValueError
        self.opened.corpus_index.validate()
        record_ids = self.opened.corpus_index.vault_record_ids()
        report = self.opened.vault.verify()
        dangling = self.opened.vault.count_inactive_or_missing_records(record_ids)
        failures = (
            report.missing_count + report.orphan_count
            + report.integrity_failure_count + report.write_pending_count
            + dangling
        )
        return CliResult("verify_complete", count=failures)


class PurgeOperation(OpenedOperation):
    def __init__(self, opened: OpenedMailboxVault, limit: int) -> None:
        super().__init__(opened)
        self.limit = limit

    def execute(self, session: object | None) -> CliResult:
        if session is not None:
            raise ValueError
        with self.opened.vault.coordinated_mutation():
            record_ids = self.opened.vault.plan_expired_purge(limit=self.limit)
            self.opened.corpus_index.purge_records(record_ids)
            report = self.opened.vault.purge_planned(record_ids)
        return CliResult("purge_complete", count=report.deleted_count)


class RevokeOperation(OpenedOperation):
    def __init__(self, opened: OpenedMailboxVault, confirmation: str) -> None:
        super().__init__(opened)
        self.confirmation = confirmation

    def execute(self, session: object | None) -> CliResult:
        if session is not None:
            raise ValueError
        self.opened.vault.revoke(self.confirmation)
        return CliResult("revoke_complete", count=0)


class RewrapOperation:
    def __init__(
        self,
        vault: Path,
        current_recovery: Path,
        new_recovery: Path,
        confirmation: str,
        project_root: Path,
        preflight_evidence: object,
        validate_volume: object,
        opened: OpenedMailboxVault,
    ) -> None:
        self.opened = opened
        identity = load_vault_identity(vault)
        if confirmation != f"REWRAP:{identity.vault_id}":
            raise ValueError("rewrap_confirmation_required")
        self.vault = vault
        self.current_recovery = current_recovery
        self.new_recovery = new_recovery
        self.project_root = project_root
        self.preflight_evidence = preflight_evidence
        self.validate_volume = validate_volume

    def execute(self, session: object | None) -> CliResult:
        if session is not None:
            raise ValueError
        evidence = revalidate_preflight_volume(
            self.validate_volume,
            self.vault,
            self.project_root,
            self.new_recovery,
            self.preflight_evidence,
        )
        rewrap_recovery_key(
            self.vault,
            self.current_recovery,
            self.new_recovery,
            distinct_volume_check=bound_distinct_checker(
                self.vault, self.new_recovery, evidence
            ),
        )
        return CliResult("recovery_rewrap_complete", count=0)

    def close(self) -> None:
        self.opened.close()
__all__ = [
    "InitOperation",
    "InventoryOperation",
    "PurgeOperation",
    "RevokeOperation",
    "RewrapOperation",
    "ScanOperation",
    "VerifyOperation",
]
