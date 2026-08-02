"""Fixed content-free two-start validation failure."""


class TwoStartValidationError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_TWO_START_VALIDATION_INVALID")
