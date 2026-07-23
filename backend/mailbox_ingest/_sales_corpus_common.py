"""Shared validation and keyed-token primitives for the sales corpus index."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass, field


POLICY_PURPOSE = b"sales-corpus-index/policy/v1\0"
KEY_CHECK_PURPOSE = b"sales-corpus-index/key-check/v1\0"
MESSAGE_PURPOSE = b"sales-corpus-index/message-id/v1\0"
CONTENT_PURPOSE = b"sales-corpus-index/content/v1\0"
SOURCE_PURPOSE = b"sales-corpus-index/source/v1\0"
QUOTATION_PURPOSE = b"sales-corpus-index/quotation/v1\0"
ATTACHMENT_CANDIDATE_PURPOSE = b"sales-corpus-index/attachment-candidate/v1\0"
ATTACHMENT_CONTENT_PURPOSE = b"sales-corpus-index/attachment-content/v1\0"
_HEX = frozenset("0123456789abcdef")


class SalesCorpusIndexError(ValueError):
    """Fixed-code failure with no native SQLite or input detail."""

    def __init__(self, code: str = "sales_corpus_index_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"SalesCorpusIndexError(code={self.code!r})"


@dataclass(frozen=True)
class CorpusSummary:
    canonical_message_count: int
    request_count: int
    reply_count: int
    source_record_count: int
    duplicate_message_count: int
    pair_count: int
    paired_message_count: int
    quotation_count: int
    duplicate_quotation_count: int
    supported_attachment_count: int
    unsupported_attachment_count: int

    def to_dict(self) -> dict[str, int]:
        return dict(vars(self))


@dataclass(frozen=True)
class MessageUpsertResult:
    status: str
    belongs_to_pair: bool

    def __post_init__(self) -> None:
        if self.status not in {"created", "duplicate"}:
            raise SalesCorpusIndexError()


@dataclass(frozen=True)
class MessageLookupResult:
    vault_record_id: str = field(repr=False)
    source_seen: bool


@dataclass(frozen=True)
class AttachmentBindResult:
    status: str
    blob_record_id: str = field(repr=False)

    def __post_init__(self) -> None:
        if self.status not in {"new", "duplicate"}:
            raise SalesCorpusIndexError()


@dataclass(frozen=True)
class AttachmentSummary:
    new_count: int
    duplicate_count: int
    blob_count: int
    binding_count: int
    parsed_count: int
    unreviewed_count: int

    def to_dict(self) -> dict[str, int]:
        return dict(vars(self))


def keyed_token(
    key: bytes | bytearray, purpose: bytes, value: object, *, code: str,
) -> bytes:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 4096
        or any(ord(character) < 32 for character in value)
    ):
        raise SalesCorpusIndexError(code)
    try:
        encoded = value.encode("utf-8", errors="strict")
        return hmac.new(key, purpose + encoded, hashlib.sha256).digest()
    except (UnicodeError, TypeError, ValueError):
        raise SalesCorpusIndexError(code) from None


def keyed_tokens(
    key: bytes | bytearray,
    purpose: bytes,
    values: object,
    *,
    code: str,
) -> tuple[bytes, ...]:
    if not isinstance(values, tuple) or len(values) > 100:
        raise SalesCorpusIndexError(code)
    return tuple(dict.fromkeys(
        keyed_token(key, purpose, value, code=code) for value in values
    ))


def is_hex(value: object, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and set(value).issubset(_HEX)
    )


__all__ = [
    "ATTACHMENT_CANDIDATE_PURPOSE",
    "ATTACHMENT_CONTENT_PURPOSE",
    "AttachmentBindResult",
    "AttachmentSummary",
    "CONTENT_PURPOSE",
    "CorpusSummary",
    "KEY_CHECK_PURPOSE",
    "MESSAGE_PURPOSE",
    "MessageLookupResult",
    "MessageUpsertResult",
    "POLICY_PURPOSE",
    "QUOTATION_PURPOSE",
    "SOURCE_PURPOSE",
    "SalesCorpusIndexError",
    "is_hex",
    "keyed_token",
    "keyed_tokens",
]
