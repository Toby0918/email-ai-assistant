"""Fixed content-free managed-unit publication failure."""


class ManagedUnitPublicationError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_MANAGED_UNIT_PUBLICATION_INVALID")
