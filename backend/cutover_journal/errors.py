"""Fixed public failures for synthetic cutover journal contracts."""


class JournalContractError(ValueError):
    """A content-free journal contract failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
