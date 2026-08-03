"""Fixed public runbook verification failure."""


class OperatorRunbookError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_OPERATOR_RUNBOOK_INVALID")
