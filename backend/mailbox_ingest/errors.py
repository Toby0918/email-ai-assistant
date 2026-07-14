"""Fixed, log-safe errors for isolated mailbox-vault operations."""

from __future__ import annotations


SAFE_ERROR_CODES = frozenset(
    {
        "internal_error",
        "unsupported_platform",
        "invalid_path",
        "path_not_absolute",
        "path_missing",
        "prohibited_vault_location",
        "prohibited_recovery_location",
        "reparse_point_forbidden",
        "volume_probe_failed",
        "vault_filesystem_not_ntfs",
        "vault_not_removable",
        "bitlocker_not_fully_encrypted",
        "bitlocker_protection_off",
        "bitlocker_locked",
        "recovery_volume_not_separate",
        "dpapi_protect_failed",
        "dpapi_unprotect_failed",
        "dpapi_cleanup_failed",
        "invalid_master_key",
        "invalid_vault_id",
        "invalid_record_id",
        "invalid_nonce",
        "nonce_reuse",
        "record_too_large",
        "invalid_frame",
        "invalid_frame_size",
        "unsupported_frame_version",
        "unsupported_algorithm",
        "key_version_mismatch",
        "record_binding_mismatch",
        "record_authentication_failed",
        "crypto_closed",
        "recovery_key_exists",
        "recovery_key_missing",
        "recovery_key_invalid",
        "key_envelopes_exist",
        "key_envelope_missing",
        "invalid_key_envelope",
        "recovery_authentication_failed",
        "key_envelope_write_failed",
        "key_envelope_read_failed",
        "rewrap_state_invalid",
        "rewrap_reconcile_failed",
        "index_initialize_failed",
        "index_read_failed",
        "index_write_failed",
        "index_schema_invalid",
        "invalid_record_metadata",
        "invalid_lifecycle_state",
        "invalid_limit",
        "vault_busy",
        "ciphertext_write_failed",
        "ciphertext_read_failed",
        "ciphertext_delete_failed",
        "ciphertext_path_invalid",
        "ciphertext_missing",
        "expiry_exceeds_retention",
        "invalid_expiry",
        "record_not_found",
        "record_delete_failed",
        "revoke_confirmation_required",
        "revoke_incomplete",
        "vault_revoked",
    }
)


class VaultError(Exception):
    """An error whose string and representation contain only a fixed code."""

    def __init__(self, code: str) -> None:
        safe_code = code if code in SAFE_ERROR_CODES else "internal_error"
        self.code = safe_code
        super().__init__(safe_code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"VaultError(code={self.code!r})"
