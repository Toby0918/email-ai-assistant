"""Small canonical fingerprint helpers for content-free preflight values."""

from __future__ import annotations

import hashlib
import json


_ROLE_KEYS = {
    "source_root": "repository_root",
    "target_parent": "projects_parent",
    "finance_root": "finance_project",
    "target_absence": "project_container",
}


def is_fingerprint(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def fingerprint(domain: str, value: object) -> str:
    payload = json.dumps(
        {"domain": domain, "value": value},
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def role_selection_fingerprint(
    role: str,
    normalized_name_fingerprint: str,
) -> str:
    if role not in _ROLE_KEYS or not is_fingerprint(
        normalized_name_fingerprint
    ):
        raise ValueError("REAL_HOST_ROLE_BINDING_INVALID")
    return fingerprint(
        "real-host-role-selection-v1",
        {
            "normalized_name_fingerprint": normalized_name_fingerprint,
            "role": role,
        },
    )


def role_selections_match(
    profile_mapping: object,
    observed_names: object,
) -> bool:
    if (
        type(profile_mapping) is not dict
        or type(observed_names) is not dict
        or not observed_names
        or not set(observed_names).issubset(_ROLE_KEYS)
    ):
        return False
    selections = profile_mapping.get("role_selections")
    if type(selections) is not dict:
        return False
    try:
        return all(
            selections.get(_ROLE_KEYS[role])
            == role_selection_fingerprint(role, name)
            for role, name in observed_names.items()
        )
    except Exception:
        return False
