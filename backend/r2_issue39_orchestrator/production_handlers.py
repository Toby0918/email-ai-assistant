"""Code-fixed action handlers behind the production host interface."""

from __future__ import annotations

from dataclasses import dataclass, field

from .action_catalog import Issue39ActionPhaseV1


@dataclass(frozen=True, slots=True, repr=False)
class _FixedActionHandlerV1:
    action_fingerprint: str = field(repr=False)
    apply_callback: object = field(repr=False)
    present_callback: object = field(repr=False)
    partial_callback: object = field(repr=False)

    def apply(self, host, action, direction, attempt_token):
        return self.apply_callback(host, action, direction, attempt_token)

    def present(self, host, action, *, reverse=False):
        return self.present_callback(host, action, reverse)

    def partial(self, host, action, direction):
        return self.partial_callback(host, action, direction)


def build_fixed_action_handlers_v1(catalog):
    handlers = {}
    for action in catalog.actions:
        callback = _definition(action)
        handler = _FixedActionHandlerV1(action.action_fingerprint, *callback)
        if action.action_fingerprint in handlers:
            raise ValueError("R2_ISSUE39_HANDLER_DUPLICATE")
        handlers[action.action_fingerprint] = handler
    if len(handlers) != catalog.action_count:
        raise ValueError("R2_ISSUE39_HANDLER_CATALOG_INVALID")
    return handlers


def _definition(action):
    name = action.action_name
    if action.phase is Issue39ActionPhaseV1.FOUNDATION:
        index = action.sequence - len(_FOUNDATION)
        if 1 <= index <= 16 and name == f"worktree_reconstruction_{index:02d}":
            return (_worktree_apply, _worktree_present, _worktree_partial)
        if name in _FOUNDATION:
            return (_foundation_apply, _foundation_present, _foundation_partial)
    if action.phase is Issue39ActionPhaseV1.MANAGED_PUBLICATION and name in _MANAGED:
        return (_managed_apply, _managed_present, _managed_partial)
    if action.phase is Issue39ActionPhaseV1.VALIDATION and name in _VALIDATION:
        return (_validation_apply, _validation_present, _no_partial)
    raise ValueError("R2_ISSUE39_HANDLER_CATALOG_INVALID")


def _worktree_apply(host, action, direction, _attempt):
    from .production_foundation import mutate_worktree

    return mutate_worktree(host, action, direction)


def _worktree_present(host, action, reverse):
    from .production_foundation import worktree_state

    return worktree_state(host, action, reverse=reverse)


def _worktree_partial(host, action, direction):
    from .production_foundation import worktree_partial

    return worktree_partial(host, action, direction)


def _foundation_apply(host, action, direction, attempt):
    from .production_foundation import mutate_foundation

    return mutate_foundation(host, action, direction, attempt)


def _foundation_present(host, action, reverse):
    from .production_foundation import foundation_state

    return foundation_state(host, action.action_name, reverse=reverse)


def _foundation_partial(host, action, direction):
    from .production_foundation import foundation_partial

    return foundation_partial(host, action, direction)


def _managed_apply(host, action, direction, attempt):
    from .production_managed import mutate_managed

    return mutate_managed(host, action, direction, attempt)


def _managed_present(host, action, reverse):
    from .production_managed import managed_state

    return managed_state(host, action.action_name, reverse=reverse)


def _managed_partial(host, action, direction):
    from .production_managed import managed_partial

    return managed_partial(host, action, direction)


def _validation_apply(host, action, direction, attempt):
    from .production_validation import mutate_validation, run_validation

    if action.action_name == "rule_fallback_analysis":
        if direction == "forward":
            run_validation(host, action.action_name)
        elif direction == "rollback":
            from .production_host_state import seal_action

            seal_action(host, action, direction)
        else:
            raise ValueError("R2_ISSUE39_HOST_DIRECTION_INVALID")
        return None
    if action.host_effect:
        return mutate_validation(host, action, direction, attempt)
    if direction != "forward":
        raise ValueError("R2_ISSUE39_HOST_DIRECTION_INVALID")
    run_validation(host, action.action_name)
    return action.post_state_fingerprint


def _validation_present(host, action, reverse):
    if not action.host_effect:
        return False
    from .production_validation import validation_state

    return validation_state(host, action.action_name, reverse=reverse)


def _no_partial(_host, _action, _direction):
    return None


_FOUNDATION = {
    "legacy_service_quiescence", "legacy_anchor_rename",
    "container_publication", "main_publication",
    "acl_whole_tree_conformance", "repository_relocation",
}
_MANAGED = {
    f"{unit}_{phase}"
    for unit in ("runtime", "database", "crx", "config")
    for phase in ("prepare", "publish")
}
_VALIDATION = {
    "start_a", "rule_fallback_analysis", "stop_a", "database_proof",
    "stopped_layout_audit", "start_b", "final_running_audit",
}
