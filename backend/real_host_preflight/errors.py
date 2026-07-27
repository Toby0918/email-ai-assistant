"""Fixed, content-free failures for real-host preflight observation."""

from __future__ import annotations


SAFE_REAL_HOST_PREFLIGHT_ERROR_CODES = frozenset(
    {
        "host_object_already_present",
        "host_object_alias_forbidden",
        "host_object_identity_changed",
        "host_object_kind_mismatch",
        "host_object_outside_scope",
        "host_object_reparse_forbidden",
        "host_object_unavailable",
        "host_platform_unsupported",
        "host_scope_invalid",
        "host_volume_mismatch",
        "internal_error",
        "sandbox_authorization_expired",
        "sandbox_authorization_invalid",
    }
)


class RealHostPreflightError(Exception):
    """Expose one allowlisted code and no native detail."""

    def __init__(self, code: str) -> None:
        safe_code = (
            code
            if type(code) is str
            and code in SAFE_REAL_HOST_PREFLIGHT_ERROR_CODES
            else "internal_error"
        )
        self.code = safe_code
        super().__init__(safe_code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"RealHostPreflightError(code={self.code!r})"
