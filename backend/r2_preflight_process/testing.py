"""Synthetic marker used only to prove production Adapter rejection."""

from backend.r2_production_binding import ApprovedCutoverBindingV3


class _SyntheticAdapterMarker:
    __slots__ = ()


class SyntheticPreflightProductionV2:
    __slots__ = ("_adapter",)

    def __init__(self, *args, **kwargs):
        raise TypeError("SyntheticPreflightProductionV2 requires create()")

    @classmethod
    def create(cls, *, binding, observed_at_epoch):
        if (
            type(binding) is not ApprovedCutoverBindingV3
            or not callable(observed_at_epoch)
        ):
            raise ValueError("R2_PREFLIGHT_SYNTHETIC_MARKER_INVALID")
        value = object.__new__(cls)
        value._adapter = _SyntheticAdapterMarker()
        return value
