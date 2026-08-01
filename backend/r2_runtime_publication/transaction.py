"""Independent Runtime PREPARE/PUBLISH transaction and classification."""

from __future__ import annotations

import os
from pathlib import Path

from .builder import (
    PreparedRuntime,
    RuntimeInputPaths,
    observe_tree,
    prepare_runtime,
    verify_published,
)
from .canonical import fingerprint
from .contracts import (
    RuntimeCrashGap,
    RuntimeFaultSelectorV1,
    RuntimePublicationPrerequisiteV1,
    RuntimePendingClassification,
    RuntimePublicationStatus,
    build_receipt,
)
from .journal import RuntimeJournal


class SyntheticRuntimePublicationTransaction:
    def __init__(
        self,
        *,
        paths: RuntimeInputPaths,
        staging: Path,
        target: Path,
        journal: Path,
        prerequisite: RuntimePublicationPrerequisiteV1,
        review: object,
    ) -> None:
        self._paths = paths
        self._staging = staging
        self._target = target
        self._prerequisite = prerequisite
        self._review = review
        self._journal = RuntimeJournal(journal)
        self._selector = RuntimeFaultSelectorV1.none()
        self._prepared: PreparedRuntime | None = None
        self._classification = RuntimePendingClassification.EFFECT_ABSENT_EXACT
        self._executed = False

    @property
    def records(self):
        return self._journal.records

    def execute(self, selector: RuntimeFaultSelectorV1):
        if self._executed or type(selector) is not RuntimeFaultSelectorV1:
            raise ValueError("runtime_transaction_invocation_invalid")
        self._executed = True
        self._selector = selector
        if type(self._prerequisite) is not RuntimePublicationPrerequisiteV1:
            raise ValueError("runtime_prerequisite_invalid")
        self._boundary("runtime_prepare", self._prepare)
        self._boundary("runtime_publish", self._publish)
        self._classification = RuntimePendingClassification.PUBLISHED_EXACT
        return self._receipt(RuntimePublicationStatus.PUBLISHED)

    def recover(self):
        target = observe_tree(self._target)
        staging = observe_tree(self._staging)
        expected = (
            None if self._prepared is None else self._prepared.tree_fingerprint
        )
        state = _classify(
            target,
            staging,
            expected,
            target_exists=self._target.exists(),
            staging_exists=self._staging.exists(),
        )
        self._classification = state
        material = fingerprint("runtime-recovery-class-v1", state)
        self._journal.append("runtime_recovery", "classified", material)
        if state is RuntimePendingClassification.PUBLISHED_EXACT:
            os.rename(self._target, self._staging)
            state = RuntimePendingClassification.STAGING_EXACT
            self._classification = state
        status = (
            RuntimePublicationStatus.INCIDENT_STOP
            if state is RuntimePendingClassification.EFFECT_AMBIGUOUS
            else RuntimePublicationStatus.RECOVERED
        )
        self._journal.append(
            "runtime_recovery",
            "committed",
            fingerprint("runtime-recovery-result-v1", status.value),
        )
        return self._receipt(status)

    def close(self) -> None:
        self._journal.close()

    def _prepare(self) -> str:
        self._prepared = prepare_runtime(
            self._paths,
            self._staging,
            self._review,
            self._selector,
        )
        return fingerprint(
            "runtime-prepare-result-v1",
            [
                self._prepared.tree_fingerprint,
                self._prepared.verification_fingerprint,
                self._prepared.staging_identity_fingerprint,
            ],
        )

    def _publish(self) -> str:
        if self._prepared is None:
            raise ValueError("runtime_prepare_missing")
        if self._selector.kind == "collision":
            self._target.mkdir()
        if self._target.exists():
            raise ValueError("runtime_target_collision")
        os.rename(self._staging, self._target)
        verify_published(self._target, self._prepared)
        observed = observe_tree(self._target)
        if observed != self._prepared.tree_fingerprint:
            raise ValueError("runtime_publish_verification_failed")
        return fingerprint(
            "runtime-publish-result-v1",
            [observed, self._prepared.verification_fingerprint],
        )

    def _boundary(self, boundary: str, callback) -> None:
        material = fingerprint(
            "runtime-boundary-intent-v1",
            [boundary, self._prerequisite.contract_fingerprint],
        )
        self._journal.append(boundary, "intent", material)
        self._cut(boundary, RuntimeCrashGap.AFTER_INTENT)
        observed = callback()
        self._cut(boundary, RuntimeCrashGap.AFTER_EFFECT)
        self._journal.append(boundary, "effect_observed", observed)
        self._cut(boundary, RuntimeCrashGap.AFTER_STABLE_VERIFY)
        self._journal.append(boundary, "stable_verified", observed)
        self._journal.append(boundary, "committed", observed)
        self._cut(boundary, RuntimeCrashGap.AFTER_COMMIT)

    def _cut(self, boundary: str, gap: RuntimeCrashGap) -> None:
        if (
            self._selector.kind == "crash"
            and self._selector.boundary == boundary
            and self._selector.gap is gap
        ):
            raise RuntimeError("runtime_transaction_interrupted")

    def _receipt(self, status: RuntimePublicationStatus):
        retained = sum(path.exists() for path in (self._staging, self._target))
        tree = "0" * 64
        verification = "0" * 64
        if self._prepared is not None:
            tree = self._prepared.tree_fingerprint
            verification = self._prepared.verification_fingerprint
        return build_receipt(
            status=status,
            dependency_count=len(self._review.wheels),
            retained=retained,
            tree=tree,
            verification=verification,
            classification=self._classification,
        )


def _classify(
    target: str | None,
    staging: str | None,
    expected: str | None,
    *,
    target_exists: bool,
    staging_exists: bool,
):
    if expected is None:
        if not target_exists and not staging_exists:
            return RuntimePendingClassification.EFFECT_ABSENT_EXACT
        if not target_exists and staging_exists:
            return RuntimePendingClassification.STAGING_PARTIAL_RETAINED
        return RuntimePendingClassification.EFFECT_AMBIGUOUS
    if target == expected and staging is None:
        return RuntimePendingClassification.PUBLISHED_EXACT
    if not target_exists and staging == expected:
        return RuntimePendingClassification.STAGING_EXACT
    if not target_exists and staging_exists:
        return RuntimePendingClassification.STAGING_PARTIAL_RETAINED
    return RuntimePendingClassification.EFFECT_AMBIGUOUS
