"""Fixed public failure for R2 CI provenance validation."""


class R2CiProvenanceError(ValueError):
    def __init__(self) -> None:
        super().__init__("R2_CI_PROVENANCE_INVALID")
