"""Strict reviewed-manifest and encrypted source-record preparation."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from .attachment_types import SUPPORTED_MIME_TYPES
from .models import SecretBuffer


MAX_SELECTIONS = 50
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_CONVERSATION_BYTES = 25 * 1024 * 1024
_HEX32 = re.compile(r"^[0-9a-f]{32}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MIME = re.compile(r"^[a-z0-9.+-]+/[a-z0-9.+-]+$")


class AttachmentScanError(ValueError):
    def __init__(self, code: str = "attachment_manifest_invalid") -> None:
        self.code = code
        super().__init__(code)

    def __repr__(self) -> str:
        return f"AttachmentScanError(code={self.code!r})"


@dataclass(frozen=True)
class ManifestSelection:
    source_record_id: str = field(repr=False)
    candidate_id: str = field(repr=False)
    expected_size: int
    mime_type: str


@dataclass(frozen=True)
class ReviewedManifest:
    scope: str
    fingerprint: str
    approval_id: str
    issued_at_utc: int
    expires_at_utc: int
    selections: tuple[ManifestSelection, ...] = field(repr=False)

    def __repr__(self) -> str:
        return (
            "ReviewedManifest("
            f"selection_count={len(self.selections)}, approval_id={self.approval_id!r})"
        )


@dataclass(frozen=True)
class PreparedAttachment:
    source_record_id: str = field(repr=False)
    candidate_id: str = field(repr=False)
    mailbox: str = field(repr=False)
    uid: int = field(repr=False)
    uidvalidity: int
    section: str = field(repr=False)
    mime_type: str
    expected_size: int
    expires_at_utc: int

    def __repr__(self) -> str:
        return (
            "PreparedAttachment("
            f"mime_type={self.mime_type!r}, expected_size={self.expected_size}, "
            f"uidvalidity={self.uidvalidity})"
        )


@dataclass(frozen=True)
class PreparedAttachments:
    scope: str
    fingerprint: str
    approval_id: str
    expires_at_utc: int
    items: tuple[PreparedAttachment, ...] = field(repr=False)

    def __repr__(self) -> str:
        return f"PreparedAttachments(item_count={len(self.items)})"


def parse_reviewed_manifest(
    payload: object,
    *,
    expected_scope: str,
    expected_fingerprint: str,
    now_utc: int,
) -> ReviewedManifest:
    issued, expires = _validate_manifest_header(
        payload, expected_scope, expected_fingerprint, now_utc
    )
    selections = _parse_manifest_selections(payload["selections"])
    return ReviewedManifest(
        expected_scope,
        expected_fingerprint,
        payload["approval_id"],
        issued,
        expires,
        selections,
    )


def _validate_manifest_header(
    payload: object,
    expected_scope: str,
    expected_fingerprint: str,
    now_utc: int,
) -> tuple[int, int]:
    keys = {
        "schema_version", "scope", "fingerprint", "issued_at_utc",
        "expires_at_utc", "approval_id", "selections",
    }
    if not isinstance(payload, dict) or set(payload) != keys:
        raise AttachmentScanError()
    if (
        payload["schema_version"] != 1
        or payload["scope"] != expected_scope
        or payload["fingerprint"] != expected_fingerprint
        or _HEX64.fullmatch(expected_scope) is None
        or _HEX64.fullmatch(expected_fingerprint) is None
        or not isinstance(payload["approval_id"], str)
        or _HEX32.fullmatch(payload["approval_id"]) is None
    ):
        raise AttachmentScanError()
    issued = payload["issued_at_utc"]
    expires = payload["expires_at_utc"]
    if (
        type(now_utc) is not int
        or type(issued) is not int
        or type(expires) is not int
        or issued > now_utc
        or expires <= now_utc
        or expires <= issued
        or expires - issued > 7 * 24 * 60 * 60
    ):
        raise AttachmentScanError("attachment_manifest_expired")
    return issued, expires


def _parse_manifest_selections(
    raw_selections: object,
) -> tuple[ManifestSelection, ...]:
    if not isinstance(raw_selections, list) or not 1 <= len(raw_selections) <= MAX_SELECTIONS:
        raise AttachmentScanError("attachment_selection_limit")
    selections = tuple(_selection(item) for item in raw_selections)
    identities = {(item.source_record_id, item.candidate_id) for item in selections}
    if len(identities) != len(selections):
        raise AttachmentScanError("attachment_selection_duplicate")
    totals: dict[str, int] = {}
    for item in selections:
        totals[item.source_record_id] = totals.get(item.source_record_id, 0) + item.expected_size
        if totals[item.source_record_id] > MAX_CONVERSATION_BYTES:
            raise AttachmentScanError("attachment_conversation_limit")
    return selections


def _selection(value: object) -> ManifestSelection:
    keys = {
        "source_record_id", "candidate_id", "expected_size", "mime_type",
        "business_approved", "privacy_approved",
    }
    if not isinstance(value, dict) or set(value) != keys:
        raise AttachmentScanError()
    source = value["source_record_id"]
    candidate = value["candidate_id"]
    size = value["expected_size"]
    mime = value["mime_type"]
    if (
        not isinstance(source, str) or _HEX32.fullmatch(source) is None
        or not isinstance(candidate, str) or _HEX32.fullmatch(candidate) is None
        or type(size) is not int or not 1 <= size <= MAX_FILE_BYTES
        or not isinstance(mime, str) or _MIME.fullmatch(mime) is None
        or value["business_approved"] is not True
        or value["privacy_approved"] is not True
    ):
        raise AttachmentScanError()
    if mime not in SUPPORTED_MIME_TYPES:
        raise AttachmentScanError("attachment_type_unsupported")
    return ManifestSelection(source, candidate, size, mime)


def prepare_attachments(
    manifest: ReviewedManifest,
    *,
    read_source_record: Callable[[str], SecretBuffer],
    source_is_paired: Callable[[str], bool],
) -> PreparedAttachments:
    items: list[PreparedAttachment] = []
    for selection in manifest.selections:
        secret: SecretBuffer | None = None
        try:
            if source_is_paired(selection.source_record_id) is not True:
                raise AttachmentScanError("attachment_source_not_paired")
            secret = read_source_record(selection.source_record_id)
            if not isinstance(secret, SecretBuffer):
                raise AttachmentScanError("attachment_source_invalid")
            source = json.loads(bytes(secret))
            items.append(_match_source(source, manifest, selection))
        except AttachmentScanError:
            raise
        except Exception:
            raise AttachmentScanError("attachment_source_invalid") from None
        finally:
            if secret is not None:
                secret.wipe()
    return PreparedAttachments(
        manifest.scope,
        manifest.fingerprint,
        manifest.approval_id,
        manifest.expires_at_utc,
        tuple(items),
    )


def _match_source(
    source: object,
    manifest: ReviewedManifest,
    selection: ManifestSelection,
) -> PreparedAttachment:
    required = {
        "schema_version", "scope", "fingerprint", "opaque_folder_id",
        "mailbox", "uidvalidity", "uid", "expires_at_utc", "attachments",
    }
    if not isinstance(source, dict) or not required.issubset(source):
        raise AttachmentScanError("attachment_source_invalid")
    uid = source["uid"]
    validity = source["uidvalidity"]
    expiry = source["expires_at_utc"]
    if (
        source["schema_version"] != 1
        or source["scope"] != manifest.scope
        or source["fingerprint"] != manifest.fingerprint
        or not isinstance(source["mailbox"], str)
        or type(uid) is not int or not 1 <= uid <= 4_294_967_295
        or type(validity) is not int or validity < 1
        or type(expiry) is not int
        or not isinstance(source["attachments"], list)
    ):
        raise AttachmentScanError("attachment_source_invalid")
    matches = [
        item for item in source["attachments"]
        if isinstance(item, dict) and item.get("candidate_id") == selection.candidate_id
    ]
    if len(matches) != 1:
        raise AttachmentScanError("attachment_candidate_invalid")
    item = matches[0]
    if (
        item.get("size") != selection.expected_size
        or item.get("mime_type") != selection.mime_type
        or not isinstance(item.get("section"), str)
    ):
        raise AttachmentScanError("attachment_candidate_invalid")
    return PreparedAttachment(
        selection.source_record_id,
        selection.candidate_id,
        source["mailbox"],
        uid,
        validity,
        item["section"],
        selection.mime_type,
        selection.expected_size,
        expiry,
    )


__all__ = [
    "AttachmentScanError",
    "PreparedAttachments",
    "ReviewedManifest",
    "parse_reviewed_manifest",
    "prepare_attachments",
]
