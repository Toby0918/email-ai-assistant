"""Fixed content-free failures for Issue #55 host mutation primitives."""

from __future__ import annotations


SAFE_ERROR_CODES = frozenset(
    {
        "acl_authorization_rejected",
        "acl_compatibility_rejected",
        "acl_contract_invalid",
        "acl_descriptor_invalid",
        "acl_identity_changed",
        "acl_inheritance_rejected",
        "acl_journal_intent_required",
        "acl_policy_rejected",
        "filesystem_authorization_rejected",
        "filesystem_contract_invalid",
        "filesystem_identity_changed",
        "filesystem_journal_intent_required",
        "filesystem_no_clobber_rejected",
        "filesystem_reparse_rejected",
        "filesystem_scope_invalid",
        "filesystem_volume_mismatch",
        "host_platform_unsupported",
        "internal_error",
    }
)


class CutoverHostMutationError(Exception):
    """Expose only one allowlisted code and no native exception detail."""

    def __init__(self, code: str) -> None:
        safe_code = (
            code
            if type(code) is str and code in SAFE_ERROR_CODES
            else "internal_error"
        )
        self.code = safe_code
        super().__init__(safe_code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"CutoverHostMutationError(code={self.code!r})"
