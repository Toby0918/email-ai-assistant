"""Fixed public error for final-master closure contracts."""


class FinalMasterClosureError(ValueError):
    def __init__(self, code: str = "R2_FINAL_MASTER_CLOSURE_INVALID") -> None:
        super().__init__(code)
