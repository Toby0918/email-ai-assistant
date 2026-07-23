"""Publish approved cards as an external signed encrypted runtime snapshot."""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .atomic_ciphertext import replace_ciphertext
from .errors import PrivateKnowledgeError
from .runtime_schema import RuntimeKnowledgeCard
from .schema import KnowledgeCardV1
from .snapshot_codec import SnapshotMetadata, encode_snapshot_frame
from .snapshot_path import RepositoryContext, validate_snapshot_path


def publish_runtime_snapshot(
    target: Path,
    cards: tuple[KnowledgeCardV1, ...],
    *,
    authority_id: str,
    snapshot_id: str,
    encryption_key: bytes | bytearray,
    signing_private_key: Ed25519PrivateKey,
    now: datetime,
    project_root: RepositoryContext | None = None,
    forbidden_roots: tuple[Path, ...] = (),
    path_validator: Callable[[Path], object] | None = None,
    rng: Callable[[int], bytes] = os.urandom,
    crash_hook: Callable[[str], None] | None = None,
) -> None:
    current = _validated_now(now)
    path = _validated_path(
        target,
        project_root,
        forbidden_roots,
        path_validator,
    )
    eligible = _eligible_cards(cards, current)
    runtime_cards = tuple(RuntimeKnowledgeCard.from_authority(card) for card in eligible)
    expiry = _snapshot_expiry(eligible, current)
    payload = json.dumps(
        {
            "schema_version": "RuntimeKnowledgeSnapshotV1",
            "snapshot_id": snapshot_id,
            "authority_id": authority_id,
            "cards": [card.to_mapping() for card in runtime_cards],
        },
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")
    metadata = SnapshotMetadata(
        snapshot_id, authority_id, int(current.timestamp()), int(expiry.timestamp()),
        len(runtime_cards),
    )
    frame = encode_snapshot_frame(
        payload, metadata, encryption_key=encryption_key,
        signing_private_key=signing_private_key, rng=rng,
    )
    replace_ciphertext(
        path, frame, error_code="snapshot_write_failed", crash_hook=crash_hook
    )


def _validated_path(
    target: Path,
    project_root: RepositoryContext | None,
    forbidden: tuple[Path, ...],
    validator: Callable[[Path], object] | None,
) -> Path:
    try:
        result = (
            validator(Path(target)) if validator is not None
            else validate_snapshot_path(
                Path(target),
                project_root=project_root,
                forbidden_roots=forbidden,
            )
        )
    except PrivateKnowledgeError:
        raise
    except Exception:
        raise PrivateKnowledgeError("snapshot_path_invalid") from None
    return Path(target) if result is None else Path(result)


def _eligible_cards(
    cards: tuple[KnowledgeCardV1, ...], now: datetime
) -> tuple[KnowledgeCardV1, ...]:
    if not isinstance(cards, tuple) or len(cards) > 1_000:
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    result: list[KnowledgeCardV1] = []
    for card in cards:
        if not isinstance(card, KnowledgeCardV1):
            raise PrivateKnowledgeError("snapshot_schema_invalid")
        try:
            validated = KnowledgeCardV1.from_mapping(card.to_mapping())
            due = validated.lifecycle[3]
            if (validated.lifecycle[0] == "approved" and due is not None
                    and now < _parse_time(due)
                    and now < _parse_time(validated.lifecycle[2])):
                result.append(validated)
        except (PrivateKnowledgeError, AttributeError, IndexError, TypeError, ValueError):
            raise PrivateKnowledgeError("snapshot_schema_invalid") from None
    if len({card.card_id for card in result}) != len(result):
        raise PrivateKnowledgeError("snapshot_schema_invalid")
    return tuple(sorted(result, key=lambda item: item.card_id))


def _snapshot_expiry(cards: tuple[KnowledgeCardV1, ...], now: datetime) -> datetime:
    if not cards:
        return now + timedelta(days=1)
    values = [_parse_time(card.lifecycle[2]) for card in cards]
    values.extend(_parse_time(card.lifecycle[3]) for card in cards if card.lifecycle[3])
    return min(values)


def _validated_now(value: datetime) -> datetime:
    if (not isinstance(value, datetime) or value.utcoffset() != timedelta(0)
            or value.microsecond):
        raise PrivateKnowledgeError("snapshot_clock_invalid")
    return value


def _parse_time(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00")
    except (ValueError, TypeError):
        raise PrivateKnowledgeError("snapshot_schema_invalid") from None
