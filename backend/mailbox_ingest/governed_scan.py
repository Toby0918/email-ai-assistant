"""Governed request/reply corpus scan behind the administrator fingerprint gate."""

from __future__ import annotations

import hashlib
import hmac

from .attachment_manifest import MAX_FILE_BYTES
from .attachment_types import SUPPORTED_MIME_TYPES
from .authorization import add_calendar_months
from .bodystructure import BodyStructureError, parse_bodystructure
from .first_pass_transfer import (
    FirstPassContentError,
    FirstPassTransportError,
    fetch_first_pass_content,
)
from .scan import ScanError, _require_uidvalidity, _verify_inventory, classify_message
from .scan_record import ScanRecordError, encode_scan_record
from .governed_scan_state import (
    GovernedScanReport,
    advance_scan_state,
    load_or_create_scan_state,
    report_from_state,
)
from .sales_message_policy import evaluate_sales_message
from .text_body_decoder import TextBodyDecodeError, decode_text_body


def scan_governed_mailbox(
    *, session: object, inventory_bundle: object, confirmed_fingerprint: str,
    vault: object, control_store: object, rebuild_inventory: object,
    sales_policy: object, corpus_index: object, identity_key: bytes,
) -> GovernedScanReport:
    _verify_inventory(
        inventory_bundle, confirmed_fingerprint, rebuild_inventory
    )
    policy_fingerprint = _policy_fingerprint(sales_policy, identity_key)
    try:
        corpus_index.bind_policy(policy_fingerprint)
    except Exception:
        raise ScanError("sales_corpus_index_failed") from None
    state = load_or_create_scan_state(
        control_store, inventory_bundle, policy_fingerprint
    )
    for folder in inventory_bundle.evidence:
        _scan_folder(
            session, folder, inventory_bundle.inventory, state, vault,
            control_store, sales_policy, corpus_index, identity_key,
        )
    try:
        summary = corpus_index.summary()
    except Exception:
        raise ScanError("sales_corpus_index_failed") from None
    return report_from_state(state, summary)


def _scan_folder(
    session: object, folder: object, inventory: object, state: dict[str, object],
    vault: object, control: object, policy: object, index: object, key: bytes,
) -> None:
    folder_state = state["folders"].get(folder.opaque_folder_id)
    if not isinstance(folder_state, dict):
        raise ScanError("scan_state_invalid")
    _require_uidvalidity(session, folder.wire_mailbox, folder.uidvalidity)
    cursor = folder_state.get("cursor")
    if type(cursor) is not int or cursor < 0:
        raise ScanError("scan_state_invalid")
    for message in folder.messages:
        if message.uid <= cursor:
            continue
        _require_uidvalidity(session, folder.wire_mailbox, folder.uidvalidity)
        outcome, supported, unsupported = _process_one(
            session, folder, inventory, message, vault, policy, index, key
        )
        advance_scan_state(
            state, folder_state, message.uid, outcome, supported, unsupported
        )
        try:
            control.write("scan-state", state)
        except Exception:
            raise ScanError("scan_state_write_failed") from None


def _process_one(
    session: object, folder: object, inventory: object, message: object,
    vault: object, policy: object, index: object, key: bytes,
) -> tuple[str, int, int]:
    try:
        source = session.uid_fetch_bodystructure(message.uid)
    except Exception:
        raise ScanError("scan_transport_failed") from None
    try:
        plan = parse_bodystructure(source)
    except BodyStructureError:
        return "ambiguous", 0, 0
    supported, unsupported = _attachment_counts(plan.attachments)
    downloaded = _download_content(session, message.uid, plan.body_sections)
    if downloaded is None:
        return "ambiguous", supported, unsupported
    header, bodies = downloaded
    classification = classify_message(header, bodies)
    if classification != "eligible":
        return classification, supported, unsupported
    decision = evaluate_sales_message(
        policy=policy, raw_header=header, raw_body=b"\n".join(bodies),
        trusted_internal_date=message.internal_date, folder_role=folder.role,
        identity_key=key,
    )
    if decision.status != "candidate":
        return decision.status, supported, unsupported
    _persist_candidate(
        decision.candidate, plan.attachments, folder, inventory, message,
        header, bodies, vault, index, key, supported, unsupported,
    )
    return "candidate", 0, 0


def _download_content(
    session: object, uid: int, parts: tuple[object, ...],
) -> tuple[bytes, tuple[bytes, ...]] | None:
    if any(getattr(part, "mime_type", None) != "text/plain" for part in parts):
        return None
    try:
        header, encoded = fetch_first_pass_content(session, uid, parts)
        bodies = tuple(
            decode_text_body(part, payload)
            for part, payload in zip(parts, encoded, strict=True)
        )
        return header, bodies
    except FirstPassTransportError:
        raise ScanError("scan_transport_failed") from None
    except (FirstPassContentError, TextBodyDecodeError):
        return None


def _persist_candidate(
    candidate: object, attachments: tuple[object, ...], folder: object,
    inventory: object, message: object, header: bytes, bodies: tuple[bytes, ...],
    vault: object, index: object, key: bytes, supported: int, unsupported: int,
) -> None:
    try:
        with vault.coordinated_mutation():
            _persist_candidate_locked(
                candidate, attachments, folder, inventory, message, header,
                bodies, vault, index, key, supported, unsupported,
            )
    except ScanError:
        raise
    except Exception:
        raise ScanError("scan_persist_failed") from None


def _persist_candidate_locked(
    candidate: object, attachments: tuple[object, ...], folder: object,
    inventory: object, message: object, header: bytes, bodies: tuple[bytes, ...],
    vault: object, index: object, key: bytes, supported: int, unsupported: int,
) -> None:
    attachment_material = _attachment_material(attachments)
    content_token = hashlib.sha256(
        b"sales-content/v1\0" + candidate.dedupe_material + attachment_material
    ).hexdigest()
    source_token = _source_token(folder, message, key)
    message_token = candidate.message_identity.hex()
    try:
        found = index.find_message_record(
            message_id_token=message_token, content_token=content_token,
            source_token=source_token,
        )
    except Exception:
        raise ScanError("sales_corpus_index_failed") from None
    expires = int(add_calendar_months(message.internal_date, 24).timestamp())
    if found is not None:
        try:
            vault.constrain_record_expiry(found.vault_record_id, expires)
        except Exception:
            raise ScanError("scan_persist_failed") from None
    record_id = (
        found.vault_record_id if found is not None else _write_raw_record(
            candidate, attachments, folder, inventory, message, header, bodies,
            vault, key, expires,
        )
    )
    _upsert_candidate(
        index, candidate, record_id, source_token, content_token,
        supported, unsupported,
    )


def _write_raw_record(
    candidate: object, attachments: tuple[object, ...], folder: object,
    inventory: object, message: object, header: bytes, bodies: tuple[bytes, ...],
    vault: object, key: bytes, expires: int,
) -> str:
    identity = lambda material: hmac.new(
        key, b"attachment-candidate/v1\0" + candidate.dedupe_material + material,
        hashlib.sha256,
    ).hexdigest()[:32]
    try:
        record = encode_scan_record(
            scope=inventory.opaque_scope_id, fingerprint=inventory.fingerprint,
            opaque_folder_id=folder.opaque_folder_id, mailbox=folder.mailbox,
            uidvalidity=folder.uidvalidity, uid=message.uid,
            internal_date=message.internal_date, expires_at_utc=expires,
            header=header, bodies=bodies, attachments=attachments,
            candidate_id_factory=lambda: "0" * 32,
            deterministic_candidate_id_factory=identity,
        )
        return vault.put_record_if_absent(
            record, expires_at_utc=expires
        ).record_id
    except ScanRecordError as error:
        raise ScanError(str(error)) from None
    except Exception:
        raise ScanError("scan_persist_failed") from None


def _upsert_candidate(
    index: object, candidate: object, record_id: str, source_token: str,
    content_token: str, supported: int, unsupported: int,
) -> None:
    quotation = hashlib.sha256(
        b"sales-quotation/v1\0" + candidate.quotation_material
    ).hexdigest()
    try:
        index.upsert_message(
            kind="request" if candidate.role == "customer_request" else "reply",
            message_id_token=candidate.message_identity.hex(),
            reference_tokens=tuple(
                item.hex() for item in candidate.reference_identities
            ),
            trusted_timestamp=int(candidate.trusted_internal_date.timestamp()),
            vault_record_id=record_id, source_token=source_token,
            content_token=content_token,
            quotation_tokens=() if candidate.role == "customer_request" else (quotation,),
            supported_attachment_count=supported,
            unsupported_attachment_count=unsupported,
        )
    except Exception:
        raise ScanError("sales_corpus_index_failed") from None


def _attachment_material(attachments: tuple[object, ...]) -> bytes:
    digest = hashlib.sha256(b"sales-attachment-set/v1\0")
    for item in sorted(
        attachments, key=lambda value: (value.section, value.mime_type, value.size)
    ):
        filename = "" if item.filename is None else item.filename
        value = f"{item.section}\0{item.mime_type}\0{item.size}\0{filename}"
        digest.update(len(value.encode("utf-8")).to_bytes(8, "big"))
        digest.update(value.encode("utf-8"))
    return digest.digest()


def _attachment_counts(attachments: tuple[object, ...]) -> tuple[int, int]:
    supported = sum(
        item.mime_type in SUPPORTED_MIME_TYPES and 1 <= item.size <= MAX_FILE_BYTES
        for item in attachments
    )
    return supported, len(attachments) - supported


def _source_token(folder: object, message: object, key: bytes) -> str:
    material = (
        f"{folder.opaque_folder_id}\0{folder.uidvalidity}\0{message.uid}"
    ).encode("ascii")
    return hmac.new(
        key, b"sales-source/v1\0" + material, hashlib.sha256
    ).hexdigest()


def _policy_fingerprint(policy: object, key: bytes) -> str:
    try:
        material = policy.fingerprint_material()
        if type(key) is not bytes or len(key) != 32 or type(material) is not bytes:
            raise ValueError
        return hmac.new(
            key, b"sales-policy-binding/v1\0" + material, hashlib.sha256
        ).hexdigest()
    except Exception:
        raise ScanError("sales_policy_invalid") from None


__all__ = ["GovernedScanReport", "scan_governed_mailbox"]
