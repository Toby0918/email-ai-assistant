"""Private nominal values and state registry for evidence selection."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from weakref import WeakKeyDictionary

from .contracts_bridge import TestSandboxAuthorizationV1
from .host_baseline_bridge import RealHostBaselineCollector
from .profile_binding import _ProfileBindings
from .review_bridge import MigrationEvidenceReview


_SELECTION_ERROR = "MIGRATION_EVIDENCE_SELECTION_REJECTED"


@dataclass(slots=True, repr=False)
class _SelectionState:
    temporary_directory: tempfile.TemporaryDirectory
    sandbox_root: Path
    marker_fingerprint: str
    profile_fingerprint: str
    operation_fingerprint: str
    repository_root: Path
    target: Path
    target_parent_identity_fingerprint: str
    approved_dirty_paths: tuple[str, ...]
    reviewed_refs: tuple[str, ...]
    approved_worktrees: tuple[Path, ...]
    baseline_collector: RealHostBaselineCollector
    baseline_authorization: TestSandboxAuthorizationV1
    review: MigrationEvidenceReview | None = None
    bindings: _ProfileBindings | None = None
    receipt_fingerprint: str | None = None
    reviewing: bool = False
    claimed: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class _SelectionInputs:
    repository_root: Path
    target: Path
    approved_dirty_paths: tuple[str, ...]
    reviewed_refs: tuple[str, ...]
    approved_worktrees: tuple[Path, ...]
    baseline_collector: RealHostBaselineCollector
    baseline_authorization: TestSandboxAuthorizationV1


@dataclass(frozen=True, slots=True, repr=False)
class _ClaimedEvidenceSelection:
    inputs: _SelectionInputs
    confirmed_review: MigrationEvidenceReview
    bindings: _ProfileBindings


_SELECTION_STATES: WeakKeyDictionary[
    object,
    _SelectionState,
] = WeakKeyDictionary()
_SELECTION_STATES_LOCK = Lock()


class ProfileBoundEvidenceSelectionV1:
    """Opaque raw selection available only from the synthetic binder."""

    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated evidence selection binding required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError(_SELECTION_ERROR)

    def __delattr__(self, _name: str) -> None:
        raise ValueError(_SELECTION_ERROR)

    def __copy__(self) -> object:
        raise ValueError(_SELECTION_ERROR)

    def __deepcopy__(self, _memo: object) -> object:
        raise ValueError(_SELECTION_ERROR)

    def __reduce__(self) -> object:
        raise ValueError(_SELECTION_ERROR)

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError(_SELECTION_ERROR)

    def __getstate__(self) -> object:
        raise ValueError(_SELECTION_ERROR)
