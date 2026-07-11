"""Conservative participant role classification for thread segments."""

from __future__ import annotations

import re


_ADDRESS_RE = re.compile(
    r"[A-Z0-9._%+-]+@(?P<domain>[A-Z0-9.-]+\.[A-Z]{2,})",
    re.IGNORECASE,
)


def participant_role(sender: str, internal_domains: tuple[str, ...]) -> str:
    domains = tuple(match.group("domain").lower() for match in _ADDRESS_RE.finditer(sender))
    if not domains:
        return "unknown"
    internal = {domain.lower() for domain in internal_domains}
    return "internal" if all(domain in internal for domain in domains) else "external"
