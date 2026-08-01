"""Complete manifest relocation and eleven-worktree synthetic transaction."""

from __future__ import annotations

from pathlib import Path

from backend.r2_main_publication.host_effects import move_object
from backend.r2_main_publication.windows_dacl import capture_tree, conforms

from .canonical import fingerprint
from .contracts import build_receipt
from .host import (
    build_main,
    conform_main,
    create_directory,
    publish_container,
    reconstruct_worktree,
)
from .journal import ManifestJournal
from .recovery import rollback_transaction
from .types import (
    ManifestBoundary,
    ManifestCrashGap,
    ManifestSelectorV1,
)
from .verification import (
    current_original_identities,
    manifest_exact,
    originals_retained,
    residue_exact,
    topology_fingerprint,
    verify_forward,
)


class SyntheticManifestTransaction:
    def __init__(self, state, journal_path: Path) -> None:
        self._state = state
        self._journal = ManifestJournal(journal_path)
        self._selector = ManifestSelectorV1.none()
        self._executed = False

    def execute(self, selector: ManifestSelectorV1):
        if self._executed or type(selector) is not ManifestSelectorV1:
            raise ValueError("repository_manifest_invocation_invalid")
        self._executed = True
        self._selector = selector
        self._preserve_originals()
        self._effect(
            ManifestBoundary.LEGACY_ANCHOR_RENAME,
            1,
            lambda: move_object(
                self._state, self._state.container, self._state.legacy
            ),
        )
        self._effect(
            ManifestBoundary.CONTAINER_PUBLICATION,
            1,
            lambda: publish_container(
                self._state, self._state.acl_adapter
            ),
        )
        self._effect(
            ManifestBoundary.MAIN_SKELETON,
            1,
            self._build_main_skeleton,
        )
        self._relocate_manifest()
        self._effect(
            ManifestBoundary.ACL_CONFORMANCE,
            1,
            self._conform_main,
        )
        self._reconstruct_worktrees()
        return self._effect(
            ManifestBoundary.FINAL_VERIFICATION,
            1,
            self._final_receipt,
        )

    def rollback(self, selector: ManifestSelectorV1 | None = None):
        self._selector = selector or ManifestSelectorV1.none()
        if type(self._selector) is not ManifestSelectorV1:
            raise ValueError("repository_manifest_invocation_invalid")
        return rollback_transaction(
            self._state,
            self._journal,
            effect=self._reverse_effect,
        )

    def manifest_exact(self) -> bool:
        return manifest_exact(self._state)

    def residue_exact(self) -> bool:
        return residue_exact(self._state)

    def original_worktree_identities_retained(self) -> bool:
        return originals_retained(self._state)

    def current_original_identities(self) -> tuple[str, ...]:
        return current_original_identities(self._state)

    def close(self) -> None:
        self._journal.close()

    def _preserve_originals(self) -> None:
        scenario = self._state.scope.review.scenario
        for index, item in enumerate(
            self._state.scope.review.observations, start=1
        ):
            self._effect(
                ManifestBoundary.WORKTREE_PRESERVATION,
                index,
                lambda item=item: move_object(
                    self._state,
                    item.paths.original,
                    Path(scenario.worktree_preservation) / item.paths.role,
                ),
            )
        for index, item in enumerate(
            self._state.scope.review.observations, start=12
        ):
            self._effect(
                ManifestBoundary.WORKTREE_PRESERVATION,
                index,
                lambda item=item: move_object(
                    self._state,
                    item.admin,
                    Path(scenario.admin_preservation) / item.paths.role,
                ),
            )

    def _build_main_skeleton(self):
        self._state.projection = build_main(self._state)
        observations = []
        for relative in self._state.manifest.skeletons:
            observations.append(
                create_directory(self._state, self._state.main / relative)
            )
        return tuple(observations)

    def _relocate_manifest(self) -> None:
        for index, item in enumerate(self._state.manifest.moves, start=1):
            self._effect(
                ManifestBoundary.MANIFEST_RELOCATION,
                index,
                lambda item=item: move_object(
                    self._state,
                    self._state.legacy / item.relative,
                    self._state.main / item.relative,
                ),
            )

    def _conform_main(self):
        if self._state.projection is None:
            raise ValueError("repository_manifest_acl_invalid")
        conform_main(self._state, self._state.projection)
        if not conforms(
            capture_tree(self._state.main),
            self._state.projection,
        ):
            raise ValueError("repository_manifest_acl_invalid")
        return self._state.projection.contract

    def _reconstruct_worktrees(self) -> None:
        expected_admins = set()
        for index, reviewed in enumerate(
            self._state.scope.review.observations, start=1
        ):
            def effect(reviewed=reviewed):
                value = reconstruct_worktree(
                    self._state, reviewed, expected_admins
                )
                self._state.recreated.append(value)
                expected_admins.add(value.admin.name.casefold())
                return value

            self._effect(
                ManifestBoundary.WORKTREE_RECONSTRUCTION,
                index,
                effect,
            )

    def _final_receipt(self):
        self._state.recreated[:] = verify_forward(self._state)
        return build_receipt(
            status="REPOSITORY_TOPOLOGY_PUBLISHED",
            manifest_fingerprint=(
                self._state.manifest.contract.manifest_fingerprint
            ),
            journal_head_fingerprint=self._journal.head,
            retained_residue_count=len(self._state.manifest.residue),
        )

    def _effect(self, boundary, item_index, callback):
        intent = fingerprint(
            "repository-manifest-intent-v1",
            [boundary.value, item_index],
        )
        self._journal.append(
            boundary, item_index, "forward", "intent", intent
        )
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_INTENT)
        result = callback()
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_EFFECT)
        observed = topology_fingerprint(self._state)
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_SCAN)
        material = _material(result, observed)
        self._journal.append(
            boundary, item_index, "forward", "observed", material
        )
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_OBSERVATION)
        self._journal.append(
            boundary, item_index, "forward", "committed", material
        )
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_COMMIT)
        return result

    def _cut(self, boundary, item_index, gap) -> None:
        if self._selector.matches(boundary, item_index, gap):
            raise RuntimeError("repository_manifest_interrupted")

    def _reverse_effect(self, boundary, item_index, callback):
        intent = fingerprint(
            "repository-manifest-reverse-intent-v1",
            [boundary.value, item_index],
        )
        self._journal.append(
            boundary, item_index, "reverse", "intent", intent
        )
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_INTENT)
        result = callback()
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_EFFECT)
        observed = topology_fingerprint(self._state)
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_SCAN)
        material = _material(result, observed)
        self._journal.append(
            boundary, item_index, "reverse", "observed", material
        )
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_OBSERVATION)
        self._journal.append(
            boundary, item_index, "reverse", "committed", material
        )
        self._cut(boundary, item_index, ManifestCrashGap.AFTER_COMMIT)
        return result


def _material(result, observed: str) -> str:
    value = getattr(result, "receipt_fingerprint", None)
    value = value or getattr(result, "observation_fingerprint", None)
    value = value or getattr(result, "projection_fingerprint", None)
    if type(value) is not str:
        value = fingerprint("repository-manifest-result-v1", str(type(result)))
    return fingerprint("repository-manifest-observed-v1", [value, observed])
