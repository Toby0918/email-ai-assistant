"""Fixed public retention-ledger failure."""


class RetentionLedgerError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_RETENTION_LEDGER_INVALID")
