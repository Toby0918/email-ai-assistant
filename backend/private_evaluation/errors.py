"""Content-free failures for the private evaluation domain."""

from __future__ import annotations


class PrivateEvaluationError(ValueError):
    """Expose only an allowlisted code, never private content."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
