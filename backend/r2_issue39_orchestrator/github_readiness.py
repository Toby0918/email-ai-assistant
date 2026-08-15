"""Fixed anonymous GET-only Issue #38 readiness observation."""

from __future__ import annotations

import json
import urllib.request


_URL = "https://api.github.com/repos/Toby0918/email-ai-assistant/issues/38"
_MAX_BYTES = 128 * 1024


def read_fixed_issue38_state_v1() -> str:
    """Return only the exact public issue state."""

    request = urllib.request.Request(
        _URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "email-ai-assistant-r2-issue39",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise ValueError("R2_ISSUE39_READINESS_INVALID")
        payload = response.read(_MAX_BYTES + 1)
    if not payload or len(payload) > _MAX_BYTES:
        raise ValueError("R2_ISSUE39_READINESS_INVALID")
    value = json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=_unique_object,
        parse_constant=lambda _value: _reject(),
    )
    if (
        type(value) is not dict
        or value.get("number") != 38
        or value.get("state") not in {"open", "closed"}
    ):
        raise ValueError("R2_ISSUE39_READINESS_INVALID")
    return value["state"].upper()


def _unique_object(items):
    result = {}
    for key, value in items:
        if type(key) is not str or key in result:
            _reject()
        result[key] = value
    return result


def _reject():
    raise ValueError("R2_ISSUE39_READINESS_INVALID")
