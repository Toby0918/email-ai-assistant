"""Fixed content-free journal V2 errors."""


class JournalGenesisError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_JOURNAL_GENESIS_INVALID")

    def __repr__(self) -> str:
        return "JournalGenesisError('R2_JOURNAL_GENESIS_INVALID')"


class JournalV2Error(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_JOURNAL_V2_INVALID")

    def __repr__(self) -> str:
        return "JournalV2Error('R2_JOURNAL_V2_INVALID')"
