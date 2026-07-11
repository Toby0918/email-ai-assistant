"""Conservative participant role classification for thread segments."""

from __future__ import annotations

import re
from email.utils import getaddresses


_LOCAL_ATOM = r"[A-Z0-9!#$%&'*+/=?^_`{|}~-]+"
_DOMAIN_LABEL = r"[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?"
_ADDRESS_RE = re.compile(
    rf"(?=[^@]{{1,64}}@){_LOCAL_ATOM}(?:\.{_LOCAL_ATOM})*@"
    rf"(?P<domain>{_DOMAIN_LABEL}(?:\.{_DOMAIN_LABEL})*\.[A-Z]{{2,63}})",
    re.IGNORECASE,
)


def participant_role(sender: str, internal_domains: tuple[str, ...]) -> str:
    addresses = tuple(address.strip() for _, address in getaddresses([sender]) if address.strip())
    if not addresses and "@" not in sender:
        return "unknown"
    if sender.count("@") != len(addresses):
        return "external"
    matches = tuple(_ADDRESS_RE.fullmatch(address) for address in addresses)
    if not matches or any(
        match is None or len(match.group("domain")) > 253 for match in matches
    ):
        return "external"
    domains = tuple(match.group("domain").lower() for match in matches if match is not None)
    internal = {domain.lower() for domain in internal_domains}
    return "internal" if all(domain in internal for domain in domains) else "external"
