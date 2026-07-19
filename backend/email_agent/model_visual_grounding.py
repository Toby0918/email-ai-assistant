"""Closed qualitative claim contract for sanitized visual observations."""

from __future__ import annotations

import unicodedata


_CANONICAL_VISUAL_OBSERVATIONS = (
    "Damage is visible.",
    "Denting is visible.",
    "Tearing is visible.",
    "Cracking is visible.",
    "Scratching is visible.",
    "Scuffing is visible.",
    "Wetness is visible.",
    "A label is present.",
    "A label is absent.",
    "The label is on the left.",
    "The label is on the right.",
    "The label is on the upper.",
    "The label is on the lower.",
    "Components are present.",
    "Components are missing.",
    "Packing layout is separate.",
    "Packing layout is shared.",
)
_NORMALIZED_VISUAL_OBSERVATIONS = frozenset(
    " ".join(value.casefold().split())
    for value in _CANONICAL_VISUAL_OBSERVATIONS
)


def canonical_visual_observations() -> tuple[str, ...]:
    """Return the finite complete-sentence visual output vocabulary."""
    return _CANONICAL_VISUAL_OBSERVATIONS


def render_visual_observation_contract() -> str:
    """Render the exact validator vocabulary for the provider system prompt."""
    return "|".join(_CANONICAL_VISUAL_OBSERVATIONS)


def visual_claim_is_allowed(text: str, *, has_critical_signatures: bool) -> bool:
    """Return whether the complete source-bound leaf is one canonical sentence."""
    if has_critical_signatures or type(text) is not str:
        return False
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(normalized.split()) in _NORMALIZED_VISUAL_OBSERVATIONS
