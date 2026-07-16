"""Conservative participant aliases for the remote deidentification gate."""

from __future__ import annotations

import re
from email.utils import getaddresses


MAX_HEADER_VALUES = 117
MAX_HEADER_CHARACTERS = 512
MAX_IDENTITY_NAMES = 100
_HEADER_EMAIL = re.compile(
    r"(?i)[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9.-]+\.[a-z]{2,}\Z"
)
_GENERIC_ORGANIZATION_LABELS = frozenset({
    "business", "buyer", "co", "com", "company", "customer", "email",
    "example", "external", "imap", "internal", "localhost", "mail", "net",
    "org", "portal", "pop", "sales", "smtp", "supplier", "test", "untrusted",
    "untrusted-attachment", "untrusted-email", "untrusted-thread", "vendor", "www",
})
_PUBLIC_SUFFIX_LABELS = frozenset({"co", "com", "net", "org"})


def header_identity_context(values: object) -> dict[str, list[str]] | None:
    """Return bounded people and safe organization aliases from mail headers."""
    if type(values) is not tuple or len(values) > MAX_HEADER_VALUES:
        return None
    if any(
        not isinstance(value, str)
        or len(value) >= MAX_HEADER_CHARACTERS
        or "\r" in value
        or "\n" in value
        for value in values
    ):
        return None
    people: set[str] = set()
    organizations: set[str] = set()
    for value in values:
        parsed = _parse_header_value(value)
        if parsed is None:
            return None
        for display, mailbox in parsed:
            if display:
                people.add(display)
            organization = _domain_organization(mailbox)
            if organization:
                organizations.add(organization)
    if len(people) + len(organizations) > MAX_IDENTITY_NAMES:
        return None
    return {
        "people": sorted(people),
        "organizations": sorted(organizations),
    }


def _parse_header_value(value: str) -> tuple[tuple[str, str], ...] | None:
    candidate = value.strip()
    if not candidate:
        return ()
    bracketed = "<" in candidate or ">" in candidate
    if candidate.count("<") != candidate.count(">"):
        return None
    try:
        parsed = getaddresses([candidate])
    except Exception:
        return None
    if not parsed or any(not name.strip() and not address.strip() for name, address in parsed):
        return None
    result: list[tuple[str, str]] = []
    for name, address in parsed:
        display = name.strip()
        mailbox = address.strip()
        if bracketed and _HEADER_EMAIL.fullmatch(mailbox) is None:
            return None
        if "@" in mailbox and _HEADER_EMAIL.fullmatch(mailbox) is None:
            return None
        if not display and mailbox and "@" not in mailbox:
            display = mailbox
        if display and not 1 <= len(display) <= 200:
            return None
        result.append((display, mailbox))
    return tuple(result)


def _domain_organization(mailbox: str) -> str:
    if _HEADER_EMAIL.fullmatch(mailbox) is None:
        return ""
    labels = mailbox.rpartition("@")[2].casefold().split(".")
    if len(labels) < 2:
        return ""
    candidate = labels[-2]
    if candidate in _PUBLIC_SUFFIX_LABELS and len(labels) >= 3:
        candidate = labels[-3]
    if (
        not re.fullmatch(r"[a-z][a-z0-9-]{2,62}", candidate)
        or candidate in _GENERIC_ORGANIZATION_LABELS
    ):
        return ""
    return candidate.replace("-", " ").title()
