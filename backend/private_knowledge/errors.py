"""Content-free error type for the private-knowledge domain."""

from __future__ import annotations


class PrivateKnowledgeError(ValueError):
    """Expose only a fixed code, never source text or an underlying exception."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
