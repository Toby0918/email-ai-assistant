"""Fixed, content-free failures for Managed Container Mode."""

from __future__ import annotations


SAFE_MANAGED_RUNTIME_CODES = frozenset(
    {
        "managed_config_invalid",
        "managed_operational_layout_invalid",
    }
)


class ManagedRuntimeError(ValueError):
    """A fixed, content-free Managed runtime failure."""

    def __init__(self, code: str) -> None:
        safe_code = (
            code
            if code in SAFE_MANAGED_RUNTIME_CODES
            else "managed_runtime_invalid"
        )
        self.code = safe_code
        super().__init__(safe_code)

    def __str__(self) -> str:
        return self.code

    def __repr__(self) -> str:
        return f"ManagedRuntimeError(code={self.code!r})"


def managed_failure_code(error: Exception) -> str:
    """Map every Managed launcher exception to a fixed public code."""
    if isinstance(error, ManagedRuntimeError):
        return error.code
    try:
        code = getattr(error, "code", None)
    except Exception:
        return "managed_runtime_invalid"
    if code == "managed_relationship_invalid":
        return "managed_relationship_invalid"
    return "managed_runtime_invalid"
