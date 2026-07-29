"""Closed reverse mutation plans for every committed forward stage."""

from __future__ import annotations

from dataclasses import dataclass

from .journal_types import ForwardBoundary


@dataclass(frozen=True, slots=True)
class ReverseStagePlan:
    stage: ForwardBoundary
    preserve_kind: str
    preserve_last: int
    main_index: int | None
    admin_first: int | None
    admin_last: int | None
    physical_first: int | None
    physical_last: int | None
    final_index: int
    boundary_count: int

    @property
    def failed_state_preserved(self) -> bool:
        return self.preserve_kind != "none"

    @property
    def checkpoints(self) -> frozenset[int]:
        values = {
            self.preserve_last,
            self.main_index,
            self.admin_last,
            self.physical_last,
            self.final_index,
        }
        return frozenset(value for value in values if value is not None)


_PLANS = {
    ForwardBoundary.SOURCE_FROZEN: ReverseStagePlan(
        stage=ForwardBoundary.SOURCE_FROZEN,
        preserve_kind="none",
        preserve_last=0,
        main_index=None,
        admin_first=None,
        admin_last=None,
        physical_first=None,
        physical_last=None,
        final_index=1,
        boundary_count=1,
    ),
    ForwardBoundary.WORKTREES_PRESERVED: ReverseStagePlan(
        stage=ForwardBoundary.WORKTREES_PRESERVED,
        preserve_kind="none",
        preserve_last=0,
        main_index=None,
        admin_first=1,
        admin_last=11,
        physical_first=12,
        physical_last=22,
        final_index=23,
        boundary_count=3,
    ),
    ForwardBoundary.LEGACY_RENAMED: ReverseStagePlan(
        stage=ForwardBoundary.LEGACY_RENAMED,
        preserve_kind="none",
        preserve_last=0,
        main_index=1,
        admin_first=2,
        admin_last=12,
        physical_first=13,
        physical_last=23,
        final_index=24,
        boundary_count=4,
    ),
}

for _stage in (
    ForwardBoundary.CONTAINER_PUBLISHED,
    ForwardBoundary.NON_MAIN_ZONES_PUBLISHED,
    ForwardBoundary.MAIN_PUBLISHED,
):
    _PLANS[_stage] = ReverseStagePlan(
        stage=_stage,
        preserve_kind="container",
        preserve_last=2,
        main_index=3,
        admin_first=4,
        admin_last=14,
        physical_first=15,
        physical_last=25,
        final_index=26,
        boundary_count=5,
    )

for _stage in (
    ForwardBoundary.WORKTREES_RECREATED,
    ForwardBoundary.REPOSITORY_FINAL_VERIFIED,
):
    _PLANS[_stage] = ReverseStagePlan(
        stage=_stage,
        preserve_kind="full",
        preserve_last=18,
        main_index=19,
        admin_first=20,
        admin_last=30,
        physical_first=31,
        physical_last=41,
        final_index=42,
        boundary_count=5,
    )


def reverse_stage_plan(stage: ForwardBoundary) -> ReverseStagePlan:
    if type(stage) is not ForwardBoundary:
        raise ValueError("synthetic reverse plan invalid")
    return _PLANS[stage]
