"""Fixed, content-free failures for project-layout validation."""

from __future__ import annotations


SAFE_PLACEMENT_ERROR_CODES = frozenset(
    {
        "internal_error",
        "managed_relationship_invalid",
        "operational_layout_invalid",
        "placement_alias_invalid",
        "placement_identity_changed",
        "placement_identity_unavailable",
        "placement_reparse_forbidden",
        "standalone_state_root_invalid",
    }
)


class PlacementError(Exception):
    """An error whose string and representation contain only a fixed code."""

    def __init__(self, code: str) -> None:
        safe_code = (
            code
            if code in SAFE_PLACEMENT_ERROR_CODES
            else "internal_error"
        )
        self.code = safe_code
        super().__init__(safe_code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"PlacementError(code={self.code!r})"
