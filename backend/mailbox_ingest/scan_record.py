"""Encrypted raw-record payload codec for the two-pass importer."""

from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from typing import Callable


class ScanRecordError(ValueError):
    pass


def encode_scan_record(
    *,
    scope: str,
    fingerprint: str,
    opaque_folder_id: str,
    mailbox: str,
    uidvalidity: int,
    uid: int,
    internal_date: datetime,
    expires_at_utc: int,
    header: bytes,
    bodies: tuple[bytes, ...],
    attachments: tuple[object, ...],
    candidate_id_factory: Callable[[], str],
) -> bytes:
    attachment_payload = _encode_attachments(attachments, candidate_id_factory)
    payload = {
        "schema_version": 1,
        "scope": scope,
        "fingerprint": fingerprint,
        "opaque_folder_id": opaque_folder_id,
        "mailbox": mailbox,
        "uidvalidity": uidvalidity,
        "uid": uid,
        "internal_date": internal_date.astimezone(timezone.utc).isoformat(),
        "expires_at_utc": expires_at_utc,
        "header_b64": base64.b64encode(header).decode("ascii"),
        "bodies_b64": [base64.b64encode(item).decode("ascii") for item in bodies],
        "attachments": attachment_payload,
    }
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")


def _encode_attachments(
    attachments: tuple[object, ...],
    candidate_id_factory: Callable[[], str],
) -> list[dict[str, object]]:
    attachment_payload: list[dict[str, object]] = []
    for attachment in attachments:
        try:
            candidate_id = candidate_id_factory()
        except Exception:
            raise ScanRecordError("candidate_id_invalid") from None
        if (
            not isinstance(candidate_id, str)
            or len(candidate_id) != 32
            or any(char not in "0123456789abcdef" for char in candidate_id)
        ):
            raise ScanRecordError("candidate_id_invalid")
        attachment_payload.append(
            {
                "candidate_id": candidate_id,
                "section": attachment.section,
                "mime_type": attachment.mime_type,
                "size": attachment.size,
                "filename": attachment.filename,
            }
        )
    return attachment_payload


__all__ = ["ScanRecordError", "encode_scan_record"]
