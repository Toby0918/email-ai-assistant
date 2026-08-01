"""Content-free observations shared by the main tracer state machine."""

from __future__ import annotations

from .canonical import fingerprint
from .windows_dacl import CapturedTree, capture_tree

UNITS = ("selected-directory", "selected-file.bin", "repository-like")


def double_stable_readiness(state) -> CapturedTree:
    first = capture_tree(state.source)
    second = capture_tree(state.source)
    if first.observations != second.observations:
        raise ValueError("main_acl_readiness_unstable")
    return first


def selected(tree: CapturedTree):
    keys = {
        fingerprint("main-selected-logical-key-v1", name)
        for name in UNITS
    }
    result = []
    for item in tree.items:
        first = item.relative.split("/", 1)[0]
        if fingerprint("main-selected-logical-key-v1", first) in keys:
            result.append(item.observation)
    return tuple(result)


def owner_group_equal(before, after) -> bool:
    return (
        len(before) == len(after)
        and all(
            left.logical_key_fingerprint == right.logical_key_fingerprint
            and left.identity_fingerprint == right.identity_fingerprint
            and left.owner_fingerprint == right.owner_fingerprint
            and left.group_fingerprint == right.group_fingerprint
            for left, right in zip(before, after)
        )
    )


def material_fingerprint(result, observed: str) -> str:
    value = getattr(result, "receipt_fingerprint", None)
    value = value or getattr(result, "observation_fingerprint", None)
    value = value or getattr(result, "projection_fingerprint", None)
    if type(value) is not str:
        value = fingerprint("main-result-v1", str(result))
    return fingerprint("main-publication-observed-v1", [value, observed])
