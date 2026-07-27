"""Independent canonical snapshots for callback-spanning profile use."""

from __future__ import annotations

from .contracts_bridge import CutoverProfileV1


def snapshot_cutover_profile(value: object) -> CutoverProfileV1:
    """Revalidate and detach one caller-owned profile before callbacks."""

    if type(value) is not CutoverProfileV1:
        raise ValueError("REAL_HOST_PROFILE_INVALID")
    try:
        return CutoverProfileV1.from_mapping(value.to_mapping())
    except Exception:
        raise ValueError("REAL_HOST_PROFILE_INVALID") from None
