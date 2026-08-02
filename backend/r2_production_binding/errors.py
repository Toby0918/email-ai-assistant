"""Fixed error for reviewed R2 production binding contracts."""


class ProductionBindingError(ValueError):
    def __init__(self, code: str = "R2_PRODUCTION_BINDING_INVALID") -> None:
        super().__init__(code)


class AuthorityClaimError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_AUTHORITY_CLAIM_INVALID")
