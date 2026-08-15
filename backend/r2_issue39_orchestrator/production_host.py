"""Code-fixed Windows host behind the Issue #39 production binder."""

from __future__ import annotations

import os

from .action_catalog import Issue39ProductionActionCatalogV1
from .closure_binding import _Issue39ClosureBindingV1
from .preparation import Issue39PrepareStatusV1, Issue39PreparedExecutionV1
from .production_evidence import Issue39EvidencePackageV1
from .production_layout import fixed_layout_v1
from .production_preflight import (
    Issue39PreflightReceiptV1,
    run_fixed_issue39_preflight_v1,
)


class FixedIssue39WindowsHostV1:
    __slots__ = (
        "_prepared", "_closure", "_catalog", "_package", "_preflight",
        "_layout",
        "_repository",
        "_legacy_service",
        "_handlers",
    )

    def __init__(self, *args, **kwargs):
        raise TypeError("FixedIssue39WindowsHostV1 requires create()")

    @classmethod
    def create(cls, *, prepared, closure, catalog, package, preflight):
        if (
            os.name != "nt"
            or type(prepared) is not Issue39PreparedExecutionV1
            or prepared.status is not Issue39PrepareStatusV1.VERIFIED
            or type(closure) is not _Issue39ClosureBindingV1
            or type(catalog) is not Issue39ProductionActionCatalogV1
            or type(package) is not Issue39EvidencePackageV1
            or type(preflight) is not Issue39PreflightReceiptV1
            or len(preflight.observation_fingerprints) != 5
        ):
            raise TypeError("R2_ISSUE39_PRODUCTION_HOST_INVALID")
        value = object.__new__(cls)
        from .production_repository import repository_manifest_from_mapping
        import json

        repository = repository_manifest_from_mapping(
            json.loads(package.payload)["repository_manifest"]
        )
        legacy_service = json.loads(package.payload)["legacy_service"]
        if set(legacy_service) != {
            "status", "image", "command_hash", "creation_time"
        } or legacy_service["status"] not in {"RUNNING", "STOPPED"}:
            raise TypeError("R2_ISSUE39_LEGACY_SERVICE_INVALID")
        for name, item in (
            ("_prepared", prepared), ("_closure", closure),
            ("_catalog", catalog), ("_package", package),
            ("_preflight", preflight), ("_layout", fixed_layout_v1()),
            ("_repository", repository),
            ("_legacy_service", legacy_service),
        ):
            object.__setattr__(value, name, item)
        from .production_handlers import build_fixed_action_handlers_v1

        object.__setattr__(value, "_handlers", build_fixed_action_handlers_v1(catalog))
        return value

    def observe(self, action):
        from .production_host_state import observe_action

        return observe_action(self, action)

    def apply(self, action, direction, attempt_token):
        if direction not in {"forward", "rollback"}:
            raise ValueError("R2_ISSUE39_HOST_DIRECTION_INVALID")
        handler = self._handler(action)
        applied = handler.apply(self, action, direction, attempt_token)
        if action.host_effect:
            retained_reverse = (
                direction == "rollback"
                and action.action_name in {
                    "main_publication", "rule_fallback_analysis"
                }
            )
            valid = handler.present(
                self, action, reverse=(direction == "rollback")
            )
            if retained_reverse:
                from .production_host_state import observe_action

                valid = observe_action(self, action) == action.pre_state_fingerprint
            if not valid:
                raise ValueError("R2_ISSUE39_HOST_EFFECT_INVALID")
            from .production_host_state import seal_action

            seal_action(self, action, direction)
            return None
        if direction != "forward" or applied != action.post_state_fingerprint:
            raise ValueError("R2_ISSUE39_HOST_EFFECT_INVALID")
        return applied

    def reverify(self, action, direction):
        from .production_host_state import reverify_host

        return reverify_host(self, action, direction)

    def recovery_inspect(self, _journal):
        self._preflight = run_fixed_issue39_preflight_v1(
            self._prepared, self._closure, self._catalog, self._package,
            "recovery", self._preflight,
        )
        return True

    def terminal_audit(self, catalog, journal_head_fingerprint):
        from .production_validation import build_terminal_audit

        return build_terminal_audit(self, catalog, journal_head_fingerprint)

    def legacy_audit(self, catalog, journal_head_fingerprint):
        from .production_validation import build_legacy_audit

        return build_legacy_audit(self, catalog, journal_head_fingerprint)

    def partial(self, action, direction, observed_state_fingerprint):
        return self._handler(action).partial(
            self, action, direction
        ) == observed_state_fingerprint

    def evidence(self, action, direction, observed_state_fingerprint):
        from .production_action_evidence import action_evidence

        return action_evidence(
            self, action, direction, observed_state_fingerprint
        )

    def _handler(self, action):
        handler = self._handlers.get(action.action_fingerprint)
        if handler is None or handler.action_fingerprint != action.action_fingerprint:
            raise ValueError("R2_ISSUE39_HANDLER_CATALOG_INVALID")
        return handler
