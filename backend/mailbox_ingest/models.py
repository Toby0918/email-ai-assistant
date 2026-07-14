"""Small, representation-safe value objects used by the mailbox vault."""

from __future__ import annotations

from dataclasses import dataclass, field


class SecretBuffer(bytearray):
    """Mutable secret bytes with a best-effort explicit wipe operation.

    Python and the operating system may retain copies outside this object.  The
    class narrows avoidable lifetime; it does not promise complete memory erasure.
    """

    def wipe(self) -> None:
        for index in range(len(self)):
            self[index] = 0

    def __enter__(self) -> "SecretBuffer":
        return self

    def __exit__(self, *_args: object) -> None:
        self.wipe()

    def __repr__(self) -> str:
        return "SecretBuffer(<redacted>)"


@dataclass(frozen=True)
class VolumeInfo:
    stable_volume_id: str = field(repr=False)
    filesystem: str
    is_removable: bool
    is_fully_encrypted: bool
    protection_on: bool
    is_locked: bool
    encryption_percentage: int
    is_reparse_point: bool


@dataclass(frozen=True)
class VolumeEvidence:
    vault_volume_id: str = field(repr=False)
    recovery_volume_id: str = field(repr=False)
    verified: bool = True

    def __repr__(self) -> str:
        return f"VolumeEvidence(verified={self.verified!r})"


@dataclass(frozen=True)
class VaultRecord:
    record_id: str = field(repr=False)
    encrypted_relpath: str = field(repr=False)
    dedup_hmac: bytes = field(repr=False)
    created_at_utc: int
    expires_at_utc: int
    ciphertext_size: int
    format_version: int
    key_version: int
    lifecycle_state: str

    def __repr__(self) -> str:
        return (
            "VaultRecord(<redacted>, "
            f"created_at_utc={self.created_at_utc}, "
            f"expires_at_utc={self.expires_at_utc}, "
            f"ciphertext_size={self.ciphertext_size}, "
            f"format_version={self.format_version}, "
            f"key_version={self.key_version}, "
            f"lifecycle_state={self.lifecycle_state!r})"
        )


@dataclass(frozen=True)
class VerifyReport:
    total_count: int
    missing_count: int
    orphan_count: int
    integrity_failure_count: int
    delete_pending_count: int


@dataclass(frozen=True)
class PurgeReport:
    deleted_count: int
    remaining_eligible_count: int
    secure_erase_claimed: bool = False


@dataclass(frozen=True)
class RevokeResult:
    state: str
    secure_erase_claimed: bool = False
