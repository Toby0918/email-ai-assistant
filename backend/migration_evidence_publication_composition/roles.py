"""Closed create-only evidence role."""

from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True, slots=True, repr=False)
class MigrationEvidencePublicationRolesV1:
    binding_fingerprint: str = field(repr=False)
    publish_confirmed_review: Callable[[object], object] = field(repr=False)
