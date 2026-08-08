"""Fixed content-free production-binding contract failures."""


class ProductionBindingError(ValueError):
    def __init__(self, code: str = "R2_PRODUCTION_BINDING_INVALID") -> None:
        super().__init__(code)


class ExecutionConfirmationError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_EXECUTION_CONFIRMATION_INVALID")
