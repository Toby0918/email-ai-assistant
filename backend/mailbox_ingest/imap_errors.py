"""Representation-safe read-only IMAP error."""


class ImapReadOnlyError(ValueError):
    def __init__(self, code: str = "imap_response_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"ImapReadOnlyError(code={self.code!r})"


__all__ = ["ImapReadOnlyError"]
