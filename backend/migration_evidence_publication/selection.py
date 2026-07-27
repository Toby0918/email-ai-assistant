"""Package-private synthetic selection binding for Issue #54."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .contracts_bridge import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)

from .host_baseline_bridge import RealHostBaselineCollector
from .profile_binding import _ProfileBindings
from .review_bridge import MigrationEvidenceReview
from .selection_state import (
    ProfileBoundEvidenceSelectionV1,
    _ClaimedEvidenceSelection,
    _SelectionInputs,
    _SelectionState,
    _SELECTION_STATES,
    _SELECTION_STATES_LOCK,
)
from .synthetic_scope import (
    create_target_parent_anchor,
    inside_absent_target,
    inside_directory,
    require_test_authorization,
    revalidate_synthetic_scope,
    synthetic_root,
)


_SELECTION_ERROR = "MIGRATION_EVIDENCE_SELECTION_REJECTED"


def _bind_test_profile_bound_selection(
    *,
    temporary_directory: tempfile.TemporaryDirectory,
    profile: CutoverProfileV1,
    authorization: TestSandboxAuthorizationV1,
    operation_fingerprint: str,
    observed_at_epoch: int,
    repository_root: Path,
    target: Path,
    approved_dirty_paths: tuple[str, ...],
    reviewed_refs: tuple[str, ...],
    approved_worktrees: tuple[Path, ...],
    baseline_collector: RealHostBaselineCollector,
    baseline_authorization: TestSandboxAuthorizationV1,
) -> ProfileBoundEvidenceSelectionV1:
    try:
        return _bind_validated_selection(
            temporary_directory=temporary_directory,
            profile=profile,
            authorization=authorization,
            operation_fingerprint=operation_fingerprint,
            observed_at_epoch=observed_at_epoch,
            repository_root=repository_root,
            target=target,
            approved_dirty_paths=approved_dirty_paths,
            reviewed_refs=reviewed_refs,
            approved_worktrees=approved_worktrees,
            baseline_collector=baseline_collector,
            baseline_authorization=baseline_authorization,
        )
    except Exception:
        raise ValueError(_SELECTION_ERROR) from None


def _bind_validated_selection(**values: object):
    profile = CutoverProfileV1.from_mapping(
        values["profile"].to_mapping()
    )
    _require_selection_authorizations(profile, values)
    collector = values["baseline_collector"]
    if type(collector) is not RealHostBaselineCollector:
        raise ValueError(_SELECTION_ERROR)
    sandbox, marker = synthetic_root(values["temporary_directory"])
    root = inside_directory(sandbox, values["repository_root"])
    original_worktrees = values["approved_worktrees"]
    worktrees = tuple(
        inside_directory(sandbox, path)
        for path in original_worktrees
    )
    _require_selection_values(
        root,
        worktrees,
        original_worktrees,
        values["approved_dirty_paths"],
        values["reviewed_refs"],
    )
    target = inside_absent_target(sandbox, values["target"])
    state = _new_selection_state(
        selection_context=(
            values["temporary_directory"],
            sandbox,
            marker,
            profile.profile_fingerprint,
            values["operation_fingerprint"],
        ),
        paths=(root, target, worktrees),
        selections=(
            values["approved_dirty_paths"],
            values["reviewed_refs"],
        ),
        baseline=(collector, values["baseline_authorization"]),
    )
    selection = object.__new__(ProfileBoundEvidenceSelectionV1)
    with _SELECTION_STATES_LOCK:
        _SELECTION_STATES[selection] = state
    return selection


def _require_selection_authorizations(
    profile: CutoverProfileV1,
    values: dict[str, object],
) -> None:
    for authorization_name, phase in (
        ("authorization", "evidence_review"),
        ("baseline_authorization", "host_baseline"),
    ):
        require_test_authorization(
            values[authorization_name],
            profile=profile,
            operation_fingerprint=values["operation_fingerprint"],
            phase=phase,
            observed_at_epoch=values["observed_at_epoch"],
        )


def _new_selection_state(
    *,
    selection_context: tuple[object, ...],
    paths: tuple[object, ...],
    selections: tuple[object, ...],
    baseline: tuple[object, ...],
) -> _SelectionState:
    temporary, sandbox, marker, profile, operation = selection_context
    root, target, worktrees = paths
    dirty_paths, refs = selections
    collector, authorization = baseline
    return _SelectionState(
        temporary_directory=temporary,
        sandbox_root=sandbox,
        marker_fingerprint=marker,
        profile_fingerprint=profile,
        operation_fingerprint=operation,
        repository_root=root,
        target=target,
        target_parent_anchor_fingerprint=(
            create_target_parent_anchor(sandbox, target.parent)
        ),
        approved_dirty_paths=dirty_paths,
        reviewed_refs=refs,
        approved_worktrees=worktrees,
        baseline_collector=collector,
        baseline_authorization=authorization,
    )


def _require_selection_values(
    root: Path,
    worktrees: tuple[Path, ...],
    original_worktrees: object,
    dirty_paths: object,
    refs: object,
) -> None:
    if (
        type(original_worktrees) is not tuple
        or len(worktrees) != 11
        or len(set(worktrees)) != 11
        or worktrees[0] != root
        or type(dirty_paths) is not tuple
        or any(type(item) is not str for item in dirty_paths)
        or type(refs) is not tuple
        or any(type(item) is not str for item in refs)
    ):
        raise ValueError(_SELECTION_ERROR)


def _begin_selection_review(
    selection: ProfileBoundEvidenceSelectionV1,
    *,
    profile: CutoverProfileV1,
    operation_fingerprint: str,
) -> _SelectionInputs:
    if type(selection) is not ProfileBoundEvidenceSelectionV1:
        raise ValueError(_SELECTION_ERROR)
    with _SELECTION_STATES_LOCK:
        state = _SELECTION_STATES.get(selection)
        if (
            state is None
            or state.reviewing
            or state.claimed
            or state.profile_fingerprint != profile.profile_fingerprint
            or state.operation_fingerprint != operation_fingerprint
        ):
            raise ValueError(_SELECTION_ERROR)
        _revalidate_sandbox(state)
        state.reviewing = True
        return _selection_inputs(state)


def _complete_selection_review(
    selection: ProfileBoundEvidenceSelectionV1,
    *,
    review: MigrationEvidenceReview,
    bindings: _ProfileBindings,
    receipt_fingerprint: str,
) -> None:
    with _SELECTION_STATES_LOCK:
        state = _SELECTION_STATES.get(selection)
        if state is None or not state.reviewing or state.claimed:
            raise ValueError(_SELECTION_ERROR)
        state.review = review
        state.bindings = bindings
        state.receipt_fingerprint = receipt_fingerprint
        state.reviewing = False


def _cancel_selection_review(
    selection: object,
) -> None:
    if type(selection) is not ProfileBoundEvidenceSelectionV1:
        return
    with _SELECTION_STATES_LOCK:
        state = _SELECTION_STATES.get(selection)
        if state is not None:
            state.reviewing = False


def _claim_selection_for_publication(
    *,
    selection: ProfileBoundEvidenceSelectionV1,
    receipt: object,
) -> _ClaimedEvidenceSelection:
    from .receipts import _receipt_binding

    try:
        receipt_state = _receipt_binding(receipt)
        with _SELECTION_STATES_LOCK:
            state = _SELECTION_STATES.get(selection)
            if (
                state is None
                or state.reviewing
                or state.claimed
                or state.review is None
                or state.bindings is None
                or state.receipt_fingerprint
                != receipt_state.receipt_fingerprint
                or state.profile_fingerprint
                != receipt_state.profile_fingerprint
                or state.operation_fingerprint
                != receipt_state.operation_fingerprint
                or state.review.review_fingerprint
                != receipt_state.review_fingerprint
                or state.bindings.selection_fingerprint
                != receipt_state.selection_fingerprint
            ):
                raise ValueError(_SELECTION_ERROR)
            _revalidate_sandbox(state)
            state.claimed = True
            claimed = _ClaimedEvidenceSelection(
                inputs=_selection_inputs(state),
                confirmed_review=state.review,
                bindings=state.bindings,
            )
            state.review = None
            state.bindings = None
            state.receipt_fingerprint = None
            return claimed
    except Exception:
        raise ValueError(_SELECTION_ERROR) from None


def _selection_inputs(state: _SelectionState) -> _SelectionInputs:
    return _SelectionInputs(
        repository_root=state.repository_root,
        target=state.target,
        approved_dirty_paths=state.approved_dirty_paths,
        reviewed_refs=state.reviewed_refs,
        approved_worktrees=state.approved_worktrees,
        baseline_collector=state.baseline_collector,
        baseline_authorization=state.baseline_authorization,
    )


def _revalidate_sandbox(state: _SelectionState) -> None:
    revalidate_synthetic_scope(
        temporary_directory=state.temporary_directory,
        sandbox_root=state.sandbox_root,
        marker=state.marker_fingerprint,
        repository_root=state.repository_root,
        worktrees=state.approved_worktrees,
        target=state.target,
        target_parent_anchor=(
            state.target_parent_anchor_fingerprint
        ),
    )
