"""Convert local-only deidentification tokens to provider-safe semantics."""

from __future__ import annotations

import re

_GENERIC_REFERENCE_BY_KIND = {
    "PROMPT_INJECTION": "untrusted instruction omitted",
    "MESSAGE_ID": "a message reference",
    "UNC_PATH": "a local resource",
    "LOCAL_PATH": "a local resource",
    "URL": "a link reference",
    "EMAIL": "a contact address",
    "SOURCE_HASH": "an internal reference",
    "SOURCE_LOCATOR": "an internal reference",
    "RESTORATION_HINT": "unsafe instruction omitted",
    "ORDER_ID": "a purchase reference",
    "INVOICE_ID": "a billing reference",
    "TRACKING_ID": "a logistics reference",
    "PART_ID": "an item reference",
    "TRANSACTION_ID": "a business reference",
    "AMOUNT": "a stated amount",
    "DATE": "a stated date",
    "PHONE": "a contact number",
    "ADDRESS": "a location",
    "FILENAME": "an attachment",
    "DOMAIN": "a network location",
    "PERSON": "a person",
    "ORGANIZATION": "an organization",
}


def genericize_private_prompt(
    text: object,
    placeholder_pattern: re.Pattern[str],
) -> str | None:
    """Remove internal token syntax without using or exposing the resolver."""
    if type(text) is not str:
        return None

    def generic_reference(match: re.Match[str]) -> str:
        token = match.group(0)
        kind = token[1:token.rfind("_")].upper()
        reference = _GENERIC_REFERENCE_BY_KIND.get(kind)
        if reference is None:
            raise ValueError("unknown_private_placeholder")
        return reference

    try:
        generic = placeholder_pattern.sub(generic_reference, text)
    except Exception:
        return None
    return None if placeholder_pattern.search(generic) else generic
