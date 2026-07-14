"""Public context-managed construction for an already validated vault."""

from __future__ import annotations

import os
import hmac
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .authorization import AuthorizationError, AuthorizationScope, DateWindow
from .control_store import ControlStoreError, EncryptedControlStore
from .dpapi import DpapiProtector
from .errors import VaultError
from .folder_policy import RawFolder, SelectedFolder, select_mail_folders
from .inventory import InventoryBundle, build_inventory
from .key_envelopes import load_vault_identity, open_master_key
from .models import SecretBuffer
from .vault import MailboxVault
from .vault_crypto import VaultCrypto
from .vault_index import VaultIndex


@dataclass(frozen=True)
class VaultIdentity:
    vault_id: str
    key_version: int


@dataclass
class _OpeningResources:
    crypto: VaultCrypto | None = None
    control: EncryptedControlStore | None = None
    keys: list[SecretBuffer] = field(default_factory=list)

    def close(self) -> None:
        if self.control is not None:
            self.control.close()
        if self.crypto is not None:
            self.crypto.close()
        for key in self.keys:
            key.wipe()


@dataclass
class OpenedMailboxVault:
    identity: VaultIdentity
    vault: MailboxVault
    control: EncryptedControlStore
    vault_root: Path = field(repr=False)
    _scope_key: SecretBuffer = field(repr=False)
    _folder_key: SecretBuffer = field(repr=False)
    _fingerprint_key: SecretBuffer = field(repr=False)
    _closed: bool = False

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.control.close()
        self.vault.close()
        self._scope_key.wipe()
        self._folder_key.wipe()
        self._fingerprint_key.wipe()

    def authorization_scope(
        self, authorization_id: str, account: str
    ) -> AuthorizationScope:
        self._ensure_open()
        return AuthorizationScope.create(
            authorization_id, account, hmac_key=bytes(self._scope_key)
        )

    def create_authorization_binding(
        self, authorization_id: str, account: str
    ) -> AuthorizationScope:
        scope = self.authorization_scope(authorization_id, account)
        try:
            self.control.create(
                "authorization-binding",
                {"schema_version": 1, "opaque_scope_id": scope.opaque_scope_id},
            )
            self._verify_binding(scope)
        except (ControlStoreError, AuthorizationError):
            raise AuthorizationError() from None
        return scope

    def require_authorization_scope(
        self, authorization_id: str, account: str
    ) -> AuthorizationScope:
        scope = self.authorization_scope(authorization_id, account)
        self._verify_binding(scope)
        return scope

    def _verify_binding(self, scope: AuthorizationScope) -> None:
        try:
            payload = self.control.read("authorization-binding")
        except ControlStoreError:
            raise AuthorizationError() from None
        stored = payload.get("opaque_scope_id") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or set(payload) != {"schema_version", "opaque_scope_id"}
            or payload.get("schema_version") != 1
            or not isinstance(stored, str)
            or len(stored) != 64
            or any(character not in "0123456789abcdef" for character in stored)
            or not hmac.compare_digest(stored, scope.opaque_scope_id)
        ):
            raise AuthorizationError()

    def select_folders(
        self, folders: tuple[RawFolder, ...]
    ) -> tuple[SelectedFolder, ...]:
        self._ensure_open()
        return select_mail_folders(folders, hmac_key=bytes(self._folder_key))

    def inventory(
        self,
        session: object,
        *,
        scope: AuthorizationScope,
        folders: tuple[SelectedFolder, ...],
        window: DateWindow,
    ) -> InventoryBundle:
        self._ensure_open()
        return build_inventory(
            session,
            scope=scope,
            folders=folders,
            window=window,
            fingerprint_key=bytes(self._fingerprint_key),
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise VaultError("vault_revoked")

    def __enter__(self) -> "OpenedMailboxVault":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def __repr__(self) -> str:
        return "OpenedMailboxVault(<redacted>)"


def open_mailbox_vault(
    vault_root: Path,
    *,
    dpapi: DpapiProtector | object,
    clock: Callable[[], int],
    identity_loader: Callable[[Path], object] = load_vault_identity,
    master_key_loader: Callable[[Path, object], SecretBuffer] = open_master_key,
    rng: Callable[[int], bytes] = os.urandom,
) -> OpenedMailboxVault:
    """Construct one vault/control pair and wipe the temporary master key."""

    root = Path(vault_root)
    master: SecretBuffer | None = None
    try:
        identity = _load_identity(root, identity_loader)
        master = master_key_loader(root, dpapi)
        if not isinstance(master, SecretBuffer):
            raise VaultError("invalid_master_key")
        return _open_from_master(root, identity, master, clock, rng)
    except VaultError:
        raise
    except Exception:
        raise VaultError("internal_error") from None
    finally:
        if master is not None:
            master.wipe()


def _load_identity(
    root: Path,
    identity_loader: Callable[[Path], object],
) -> VaultIdentity:
    raw = identity_loader(root)
    return VaultIdentity(
        str(getattr(raw, "vault_id")),
        int(getattr(raw, "key_version")),
    )


def _open_from_master(
    root: Path,
    identity: VaultIdentity,
    master: SecretBuffer,
    clock: Callable[[], int],
    rng: Callable[[int], bytes],
) -> OpenedMailboxVault:
    resources = _OpeningResources()
    try:
        resources.crypto = VaultCrypto(
            master, vault_id=identity.vault_id,
            key_version=identity.key_version, rng=rng,
        )
        resources.control = EncryptedControlStore(
            root, vault_id=identity.vault_id, master_key=master, rng=rng,
        )
        for purpose in (b"scope", b"folder", b"inventory-fingerprint"):
            resources.keys.append(
                _derive_opaque_key(master, identity.vault_id, purpose)
            )
        index = VaultIndex(root / "vault-index.sqlite3", vault_id=identity.vault_id)
        index.validate()
        vault = MailboxVault(
            root, vault_id=identity.vault_id, crypto=resources.crypto,
            index=index, clock=clock,
        )
        return OpenedMailboxVault(
            identity, vault, resources.control, root,
            resources.keys[0], resources.keys[1], resources.keys[2],
        )
    except Exception:
        resources.close()
        raise


def _derive_opaque_key(
    master_key: bytes | bytearray,
    vault_id: str,
    purpose: bytes,
) -> SecretBuffer:
    return SecretBuffer(
        HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=vault_id.encode("ascii"),
            info=b"mailbox-vault/opaque/v1/" + purpose,
        ).derive(bytes(master_key))
    )


__all__ = [
    "OpenedMailboxVault",
    "VaultIdentity",
    "open_mailbox_vault",
]
