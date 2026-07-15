"""Read-only fail-safe loader for the external private-knowledge snapshot."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .errors import PrivateKnowledgeError
from .read_only_file import read_snapshot_file
from .runtime_schema import RuntimeKnowledgeCard
from .snapshot_codec import decode_snapshot_frame
from .snapshot_path import validate_snapshot_path


@dataclass(frozen=True, slots=True)
class RuntimeKnowledgeLoad:
    cards: tuple[RuntimeKnowledgeCard, ...]
    code: str


def load_runtime_knowledge(
    path: Path,
    *,
    encryption_key: bytes | bytearray,
    verification_public_key: Ed25519PublicKey,
    clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    forbidden_roots: tuple[Path, ...] = (),
    path_validator: Callable[[Path], object] | None = None,
) -> RuntimeKnowledgeLoad:
    target = _runtime_path(path, forbidden_roots, path_validator)
    if target is None:
        return _fallback("snapshot_path_invalid")
    try:
        frame = read_snapshot_file(target)
        metadata, plaintext = decode_snapshot_frame(
            frame, encryption_key=encryption_key,
            verification_public_key=verification_public_key,
        )
    except PrivateKnowledgeError as error:
        return _fallback(error.code)
    now = _runtime_now(clock)
    if now is None:
        return _fallback("snapshot_clock_invalid")
    if int(now.timestamp()) >= metadata.expires_epoch:
        return _fallback("snapshot_expired")
    if int(now.timestamp()) < metadata.created_epoch:
        return _fallback("snapshot_schema_invalid")
    try:
        value = json.loads(plaintext.decode("utf-8"))
        cards = _parse_payload(value, metadata.snapshot_id, metadata.authority_id)
    except (UnicodeDecodeError, json.JSONDecodeError, PrivateKnowledgeError):
        return _fallback("snapshot_schema_invalid")
    if len(cards) != metadata.card_count:
        return _fallback("snapshot_schema_invalid")
    return RuntimeKnowledgeLoad(cards, "snapshot_loaded")


def _parse_payload(value: object, snapshot_id: str, authority_id: str) -> tuple[RuntimeKnowledgeCard, ...]:
    fields = {"schema_version", "snapshot_id", "authority_id", "cards"}
    if not isinstance(value, dict) or set(value) != fields:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    if (value["schema_version"] != "RuntimeKnowledgeSnapshotV1"
            or value["snapshot_id"] != snapshot_id or value["authority_id"] != authority_id
            or not isinstance(value["cards"], list) or len(value["cards"]) > 1_000):
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    cards = tuple(RuntimeKnowledgeCard.from_mapping(item) for item in value["cards"])
    if len({card.card_id for card in cards}) != len(cards):
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return cards


def _runtime_path(
    path: Path,
    forbidden: tuple[Path, ...],
    validator: Callable[[Path], object] | None,
) -> Path | None:
    try:
        result = (
            validator(Path(path)) if validator is not None
            else validate_snapshot_path(Path(path), forbidden_roots=forbidden)
        )
        return Path(path) if result is None else Path(result)
    except Exception:
        return None


def _runtime_now(clock: Callable[[], datetime]) -> datetime | None:
    try:
        value = clock()
    except Exception:
        return None
    if (not isinstance(value, datetime) or value.utcoffset() != timedelta(0)
            or value.microsecond):
        return None
    return value


def _fallback(code: str) -> RuntimeKnowledgeLoad:
    allowed = {
        "snapshot_path_invalid", "snapshot_missing", "snapshot_unavailable",
        "snapshot_signature_invalid", "snapshot_decrypt_invalid",
        "snapshot_schema_invalid", "snapshot_expired", "snapshot_clock_invalid",
        "snapshot_key_invalid",
    }
    return RuntimeKnowledgeLoad((), code if code in allowed else "snapshot_unavailable")
