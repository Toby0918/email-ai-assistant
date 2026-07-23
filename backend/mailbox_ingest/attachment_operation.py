"""Prepared governed attachment operation for the administrator service."""

from __future__ import annotations

import hashlib
import hmac

from .attachment_scan import fetch_prepared_attachments
from .private_attachment_parser import parse_private_attachment
from .service_models import CliResult


class AttachmentOperation:
    def __init__(self, opened: object, prepared: object) -> None:
        self.opened = opened
        self.prepared = prepared

    def close(self) -> None:
        self.opened.close()

    def execute(self, session: object | None) -> CliResult:
        if session is None:
            raise ValueError
        with self.opened.sales_identity_key() as identity_key:
            key = bytes(identity_key)
            report = fetch_prepared_attachments(
                self.prepared,
                session=session,
                vault=self.opened.vault,
                vault_root=self.opened.vault_root,
                parser=parse_private_attachment,
                content_token_factory=lambda content: _content_token(key, content),
                find_existing_blob=self.opened.corpus_index.find_attachment_blob,
                bind_blob=self._bind_blob,
            )
        return CliResult(
            "attachments_complete",
            count=report.parsed_count,
            aggregate_counts=report.to_counts(),
        )

    def _bind_blob(self, item: object, blob_id: str, token: str) -> object:
        return self.opened.corpus_index.bind_attachment(
            source_record_id=item.source_record_id,
            candidate_token=item.candidate_id,
            blob_record_id=blob_id,
            content_token=token,
        )


def _content_token(key: bytes, content: bytes) -> str:
    return hmac.new(
        key, b"sales-attachment-content/v1\0" + content, hashlib.sha256
    ).hexdigest()


__all__ = ["AttachmentOperation"]
