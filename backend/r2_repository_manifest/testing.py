"""Validated test-only binder for the Issue #75 transaction."""

from __future__ import annotations

from pathlib import Path

from backend.cutover_host_mutation.acl_contracts import AclCompatibilityPolicyV1
from backend.cutover_repository_transaction.scope_models import (
    _SyntheticTransactionScope,
)
from backend.r2_main_publication.windows_dacl import capture_tree

from .host import build_acl_adapter
from .models import ManifestTransactionState
from .review import review_manifest
from .transaction import SyntheticManifestTransaction


def bind_test_manifest_transaction(
    *,
    scope: object,
    policy: object,
    approved_untracked: tuple[str, ...],
    observed_at_epoch: int,
) -> SyntheticManifestTransaction:
    if (
        type(scope) is not _SyntheticTransactionScope
        or type(policy) is not AclCompatibilityPolicyV1
        or type(observed_at_epoch) is not int
        or observed_at_epoch >= scope.authorization.expires_at_epoch
        or policy.policy_fingerprint
        != scope.profile.to_mapping()["acl_policy"]["policy_fingerprint"]
    ):
        raise ValueError("repository_manifest_scope_invalid")
    scenario = scope.review.scenario
    container = Path(scenario.source)
    if container.name != "Container":
        raise ValueError("repository_manifest_scope_invalid")
    manifest = review_manifest(scope, approved_untracked)
    state = ManifestTransactionState(
        scope=scope,
        policy=policy,
        manifest=manifest,
        baseline=capture_tree(container),
        root=Path(scenario.root),
        marker=Path(scenario.marker),
        marker_identity=scope.review.marker_identity,
        container=container,
        legacy=Path(scenario.legacy),
        failed_container=Path(scenario.failed_container),
        main=container / "main",
        profile=scope.profile,
        authorization=scope.authorization,
        observed_at_epoch=observed_at_epoch,
        acl_adapter=None,
    )
    state.acl_adapter = build_acl_adapter(state)
    journal = Path(scenario.journal_root) / "r2-manifest.journal"
    return SyntheticManifestTransaction(state, journal)
