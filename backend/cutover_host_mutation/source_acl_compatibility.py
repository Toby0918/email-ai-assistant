"""Complete read-only ACL compatibility observation for one source tree."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .acl_contracts import (
    AclCompatibilityObservationV1,
    AclCompatibilityPolicyV1,
)
from .canonical import fingerprint
from .errors import CutoverHostMutationError
from .roles import AclRole
from .windows_security import WindowsSecurityApi


def observe_source_tree(
    root: Path,
    *,
    policy: AclCompatibilityPolicyV1,
) -> tuple[AclCompatibilityObservationV1, bool]:
    """Observe twice so a changing or incomplete tree cannot be accepted."""
    first, compatible = _snapshot(root, policy)
    second, second_compatible = _snapshot(root, policy)
    if first != second:
        raise CutoverHostMutationError("acl_identity_changed")
    inventory = fingerprint(
        "source-acl-inventory-v1",
        {"objects": [list(item) for item in first]},
        code="acl_contract_invalid",
    )
    observation = AclCompatibilityObservationV1.create(
        policy_fingerprint=policy.policy_fingerprint,
        source_root_identity_fingerprint=first[0][1],
        inventory_fingerprint=inventory,
        descriptors_observed=len(first),
        complete=True,
        content_observed=False,
    )
    return observation, compatible and second_compatible


def _snapshot(
    root: Path,
    policy: AclCompatibilityPolicyV1,
) -> tuple[tuple[tuple[str, str, str], ...], bool]:
    security = WindowsSecurityApi()
    pending = [root]
    observed: list[tuple[str, str, str]] = []
    compatible = True
    while pending:
        path = pending.pop()
        descriptor = security.capture(path, role=AclRole.SOURCE_TREE)
        item = descriptor.observation
        relative = "." if path == root else str(path.relative_to(root))
        observed.append(
            (
                hashlib.sha256(relative.casefold().encode("utf-8")).hexdigest(),
                item.object_identity_fingerprint,
                item.canonical_sddl_fingerprint,
            )
        )
        compatible = compatible and (
            not item.dacl_protected
            and item.canonical_sddl_fingerprint
            in policy.allowed_descriptor_fingerprints
        )
        if len(observed) > policy.maximum_objects:
            raise CutoverHostMutationError("acl_compatibility_rejected")
        if path.is_dir():
            try:
                children = [
                    Path(entry.path)
                    for entry in os.scandir(path)
                ]
            except OSError:
                raise CutoverHostMutationError(
                    "acl_compatibility_rejected"
                ) from None
            pending.extend(
                sorted(children, key=lambda item: item.name.casefold(), reverse=True)
            )
    observed.sort()
    if not observed:
        raise CutoverHostMutationError("acl_compatibility_rejected")
    return tuple(observed), compatible
