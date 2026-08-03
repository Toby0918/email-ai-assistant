"""Fixed public failure for rollback recovery contracts."""


class RollbackRecoveryError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_ROLLBACK_RECOVERY_INVALID")
