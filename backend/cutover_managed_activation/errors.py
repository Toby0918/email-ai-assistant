"""Fixed content-free Issue #57 failures."""


class ManagedActivationError(ValueError):
    """Reject publication without exposing native or content-bearing detail."""

    def __repr__(self) -> str:
        return "ManagedActivationError()"
