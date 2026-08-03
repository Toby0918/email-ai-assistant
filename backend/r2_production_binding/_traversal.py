"""Per-fingerprint traversal state for closed semantic frames."""

from __future__ import annotations

import hashlib


_REFERENCE_DOMAIN = b"r2-semantic-frame-reference-v1\0"

class SemanticTraversal(set):
    """Track active nodes and memoize completed policy-specific frames."""

    def __init__(self):
        super().__init__()
        self.frames = {}
        self.attribute_names = set()
        self.module_attributes = {}


def frame_policy(function_frame):
    return getattr(
        function_frame,
        "_semantic_policy",
        (function_frame.__module__, function_frame.__qualname__),
    )


def cached_frame(seen, key):
    frames = getattr(seen, "frames", None)
    if frames is None or key not in frames:
        return None
    return _REFERENCE_DOMAIN + frames[key]


def remember_frame(seen, key, value):
    frames = getattr(seen, "frames", None)
    if frames is not None:
        frames[key] = hashlib.sha256(value).digest()
    return value
