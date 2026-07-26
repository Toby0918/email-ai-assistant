"""Fixed public failures for Project Container cutover contracts."""


class CutoverContractError(ValueError):
    """A content-free contract failure with one allowlisted code."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)
