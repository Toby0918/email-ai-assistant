"""Provider-neutral request values for one remote analysis call."""

from __future__ import annotations

from dataclasses import dataclass, field

from .multimodal_media import PreparedMediaAsset


MAX_MODEL_REQUEST_TEXT_CHARACTERS = 512 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class ModelAnalysisRequest:
    """Carry only locally deidentified text and sanitized request-local media."""

    text: str = field(repr=False)
    media_assets: tuple[PreparedMediaAsset, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if (
            type(self.text) is not str
            or not self.text.strip()
            or len(self.text) > MAX_MODEL_REQUEST_TEXT_CHARACTERS
            or type(self.media_assets) is not tuple
            or any(type(asset) is not PreparedMediaAsset for asset in self.media_assets)
        ):
            raise ValueError("Model analysis request is invalid.")
