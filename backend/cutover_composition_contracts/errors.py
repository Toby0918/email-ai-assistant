"""Fixed composition-contract error."""


class CompositionContractError(ValueError):
    """Expose only one fixed contract code."""

    def __init__(
        self,
        code: str = "PROJECT_CONTAINER_COMPOSITION_INVALID",
    ) -> None:
        super().__init__(code)
