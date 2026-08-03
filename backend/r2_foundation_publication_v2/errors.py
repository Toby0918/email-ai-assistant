"""Fixed content-free foundation publication failure."""


class FoundationPublicationError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_FOUNDATION_PUBLICATION_INVALID")
