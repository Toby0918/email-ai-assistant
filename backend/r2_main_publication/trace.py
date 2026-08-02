"""One fixed, synthetic-only main-publication state machine."""

from __future__ import annotations

from .canonical import fingerprint
from .contracts import _readiness, _receipt
from .host_effects import build_projection, create_main, move_object
from .journal import MainPublicationJournal
from .observations import (
    UNITS,
    double_stable_readiness,
    material_fingerprint,
    owner_group_equal,
    selected,
)
from .recovery import classify_topology
from .types import (
    MainPublicationBoundary,
    MainPublicationCrashGap,
    MainPublicationRestartOutcome,
    MainPublicationSelectorV1,
)
from .windows_dacl import (
    BoundDaclProjection,
    CapturedTree,
    apply_projection,
    capture_tree,
    conforms,
    restore_tree_dacls,
)


class SyntheticMainPublicationTrace:
    """Bound only by the test factory; no real entry imports this class."""

    def __init__(self, state) -> None:
        self._state = state
        self._journal = MainPublicationJournal(state.journal)
        self._selector = MainPublicationSelectorV1.none()
        self._projection: BoundDaclProjection | None = None
        self._receipt = None
        self._readiness_used = False
        self._mismatch_detected = False
        self._followed_reparse = False
        self._baseline = double_stable_readiness(state)
        self.readiness = _readiness(
            source_root_identity_fingerprint=(
                self._baseline.items[0].observation.identity_fingerprint
            ),
            inventory_fingerprint=self._baseline.inventory_fingerprint,
            object_count=len(self._baseline.items),
            observed_at_epoch=state.observed_at_epoch,
            expires_at_epoch=state.observed_at_epoch + 20,
        )

    @property
    def original_anchor_identity(self) -> str:
        return self._baseline.items[0].observation.identity_fingerprint

    @property
    def original_selected_security(self):
        return selected(self._baseline)

    @property
    def main_identity(self) -> str:
        return capture_tree(self._state.main).items[0].observation.identity_fingerprint

    @property
    def preserved_descriptor_mismatch_detected(self) -> bool:
        return self._mismatch_detected

    @property
    def followed_reparse_point(self) -> bool:
        return self._followed_reparse

    @property
    def last_committed_boundary(self) -> str | None:
        records = self._journal.records
        if records and records[-1].fact == "committed":
            return records[-1].boundary.value.upper()
        return None

    def execute(self, selector: MainPublicationSelectorV1):
        self._consume_readiness(selector)
        self._effect(
            MainPublicationBoundary.LEGACY_ANCHOR_RENAME,
            lambda: move_object(
                self._state, self._state.source, self._state.legacy
            ),
            lambda: capture_tree(self._state.legacy).inventory_fingerprint,
        )
        self._effect(
            MainPublicationBoundary.MAIN_CREATE,
            lambda: create_main(self._state),
            lambda: capture_tree(self._state.main).inventory_fingerprint,
        )
        self._effect(
            MainPublicationBoundary.PROJECTION_BUILD,
            self._build_projection,
            self._projection_scan,
        )
        self._relocate_units()
        self._effect(
            MainPublicationBoundary.PRESERVED_DACL_SCAN,
            self._detect_preserved_descriptors,
            self._managed_scan,
        )
        self._effect(
            MainPublicationBoundary.ACL_WHOLE_TREE_CONFORMANCE,
            self._apply_whole_tree_projection,
            self._authoritative_scan,
        )
        return self._effect(
            MainPublicationBoundary.MAIN_PUBLISHED,
            self._build_receipt,
            self._receipt_scan,
        )

    def classify_restart(self) -> MainPublicationRestartOutcome:
        try:
            self._journal.verified_records()
            topology = classify_topology(
                self._state, self.original_anchor_identity
            )
        except Exception:
            return MainPublicationRestartOutcome.INCIDENT_STOP
        if topology == "initial":
            return MainPublicationRestartOutcome.SAFE_ABORT
        if topology == "partial":
            return MainPublicationRestartOutcome.ROLLBACK_REQUIRED
        return MainPublicationRestartOutcome.INCIDENT_STOP

    def rollback(self) -> None:
        classification = self.classify_restart()
        if classification is MainPublicationRestartOutcome.INCIDENT_STOP:
            raise ValueError("main_publication_rollback_ambiguous")
        if classification is MainPublicationRestartOutcome.SAFE_ABORT:
            return
        self._restore_units()
        if self._state.main.exists():
            move_object(self._state, self._state.main, self._state.failed_main)
        if self._state.legacy.exists():
            move_object(self._state, self._state.legacy, self._state.source)
        current = capture_tree(self._state.source)
        restore_tree_dacls(current, self._baseline)
        if capture_tree(self._state.source).observations != self._baseline.observations:
            raise ValueError("main_publication_rollback_ambiguous")

    def whole_tree_conforms(self) -> bool:
        return self._projection is not None and conforms(
            capture_tree(self._state.main), self._projection
        )

    def owner_group_exact(self) -> bool:
        return owner_group_equal(
            self.original_selected_security,
            self.current_managed_selected_security(),
        )

    def current_source_identity(self) -> str:
        return capture_tree(self._state.source).items[0].observation.identity_fingerprint

    def current_selected_security(self):
        return selected(capture_tree(self._state.source))

    def current_managed_selected_security(self):
        return selected(capture_tree(self._state.main))

    def close(self) -> None:
        self._journal.close()

    def _consume_readiness(self, selector) -> None:
        if type(selector) is not MainPublicationSelectorV1:
            raise ValueError("main_publication_selector_invalid")
        if self._readiness_used:
            raise ValueError("main_acl_readiness_consumed")
        current = self._state.clock()
        if type(current) is not int:
            raise ValueError("main_acl_readiness_invalid_clock")
        if current >= self.readiness.expires_at_epoch:
            raise ValueError("main_acl_readiness_expired")
        self._readiness_used = True
        self._selector = selector

    def _effect(self, boundary, effect, scan):
        intent = fingerprint("main-publication-intent-v1", boundary.value)
        self._journal.append(boundary, "intent", intent)
        self._cut(boundary, MainPublicationCrashGap.AFTER_INTENT)
        result = effect()
        self._cut(boundary, MainPublicationCrashGap.AFTER_EFFECT)
        observed = scan()
        self._cut(boundary, MainPublicationCrashGap.AFTER_SCAN)
        material = material_fingerprint(result, observed)
        self._journal.append(boundary, "observed", material)
        self._cut(boundary, MainPublicationCrashGap.AFTER_OBSERVATION)
        self._journal.append(boundary, "committed", material)
        self._cut(boundary, MainPublicationCrashGap.AFTER_COMMIT)
        return result

    def _cut(self, boundary, gap) -> None:
        if self._selector.matches(boundary, gap):
            raise RuntimeError("main_publication_interrupted")

    def _build_projection(self):
        self._projection = build_projection(self._state)
        return self._projection.contract

    def _relocate_units(self) -> None:
        boundaries = (
            MainPublicationBoundary.DIRECTORY_RELOCATION,
            MainPublicationBoundary.FILE_RELOCATION,
            MainPublicationBoundary.REPOSITORY_RELOCATION,
        )
        for name, boundary in zip(UNITS, boundaries):
            self._effect(
                boundary,
                lambda name=name: move_object(
                    self._state,
                    self._state.legacy / name,
                    self._state.main / name,
                ),
                self._managed_scan,
            )

    def _detect_preserved_descriptors(self):
        if self._projection is None:
            raise ValueError("main_acl_projection_invalid")
        self._mismatch_detected = not conforms(
            capture_tree(self._state.main), self._projection
        )
        if not self._mismatch_detected:
            raise ValueError("preserved_dacl_not_detected")
        return self._mismatch_detected

    def _apply_whole_tree_projection(self):
        if self._projection is None:
            raise ValueError("main_acl_projection_invalid")
        apply_projection(capture_tree(self._state.main), self._projection)
        return self._projection.contract

    def _build_receipt(self):
        tree = capture_tree(self._state.main)
        if self._projection is None or not conforms(tree, self._projection):
            raise ValueError("main_acl_conformance_rejected")
        if not owner_group_equal(self.original_selected_security, selected(tree)):
            raise ValueError("main_owner_group_changed")
        self._receipt = _receipt(
            projection_fingerprint=self._projection.contract.projection_fingerprint,
            main_identity_fingerprint=tree.items[0].observation.identity_fingerprint,
            inventory_fingerprint=tree.inventory_fingerprint,
            journal_head_fingerprint=self._journal.head,
            object_count=len(tree.items),
        )
        return self._receipt

    def _projection_scan(self) -> str:
        if self._projection is None:
            raise ValueError("main_acl_projection_invalid")
        return self._projection.contract.projection_fingerprint

    def _managed_scan(self) -> str:
        return capture_tree(self._state.main).inventory_fingerprint

    def _authoritative_scan(self) -> str:
        if not self.whole_tree_conforms() or not self.owner_group_exact():
            raise ValueError("main_acl_conformance_rejected")
        return capture_tree(self._state.main).inventory_fingerprint

    def _receipt_scan(self) -> str:
        if self._receipt is None:
            raise ValueError("main_acl_receipt_invalid")
        return self._receipt.receipt_fingerprint

    def _restore_units(self) -> None:
        if not self._state.legacy.exists():
            return
        for name in UNITS:
            managed = self._state.main / name
            legacy = self._state.legacy / name
            if managed.exists() and not legacy.exists():
                move_object(self._state, managed, legacy)
