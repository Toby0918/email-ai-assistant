"""Fail-closed, startup-only loading of the private knowledge snapshot."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .dpapi import CurrentUserDpapiProtector
from .key_store import AuthorityKeyMaterial, KeyProtector, open_authority_keys
from .runtime_loader import RuntimeKnowledgeLoad, load_runtime_knowledge
from .runtime_schema import RuntimeKnowledgeCard
from .snapshot_path import validate_snapshot_path
from .storage_policy import validate_private_storage


class _PrivateKeyFactory(Protocol):
    def __call__(self, value: bytes | bytearray) -> Ed25519PrivateKey: ...


def load_configured_runtime_cards(
    *,
    enabled: bool,
    authority_root: str,
    snapshot_path: str,
    project_root: Path,
    protector_factory: Callable[[], KeyProtector] = CurrentUserDpapiProtector,
    storage_validator: Callable[..., None] = validate_private_storage,
    snapshot_path_validator: Callable[..., Path] = validate_snapshot_path,
    key_opener: Callable[[Path, KeyProtector], AuthorityKeyMaterial] = open_authority_keys,
    snapshot_loader: Callable[..., RuntimeKnowledgeLoad] = load_runtime_knowledge,
    private_key_factory: _PrivateKeyFactory = Ed25519PrivateKey.from_private_bytes,
) -> tuple[RuntimeKnowledgeCard, ...]:
    """Return verified cards once, or an immutable empty fallback without detail."""
    configured = _configured_paths(enabled, authority_root, snapshot_path, project_root)
    if configured is None:
        return ()
    project, authority, snapshot = configured
    try:
        storage_validator(project, authority)
        target = snapshot_path_validator(
            snapshot,
            forbidden_roots=(project, authority),
        )
        with key_opener(authority, protector_factory()) as keys:
            verification_key = private_key_factory(keys.signing_seed).public_key()
            loaded = snapshot_loader(
                snapshot,
                prevalidated_target=Path(target),
                encryption_key=keys.snapshot_key,
                verification_public_key=verification_key,
                forbidden_roots=(project, authority),
            )
    except Exception:
        return ()
    return _validated_cards(loaded)


def _validated_cards(loaded: object) -> tuple[RuntimeKnowledgeCard, ...]:
    if not isinstance(loaded, RuntimeKnowledgeLoad) or loaded.code != "snapshot_loaded":
        return ()
    if type(loaded.cards) is not tuple or not all(
        isinstance(card, RuntimeKnowledgeCard) for card in loaded.cards
    ):
        return ()
    try:
        cards = tuple(
            RuntimeKnowledgeCard.from_mapping(card.to_mapping())
            for card in loaded.cards
        )
    except Exception:
        return ()
    if len({card.card_id for card in cards}) != len(cards):
        return ()
    return cards


def _configured_paths(
    enabled: bool,
    authority_root: str,
    snapshot_path: str,
    project_root: Path,
) -> tuple[Path, Path, Path] | None:
    if enabled is not True:
        return None
    if not _exact_nonempty(authority_root) or not _exact_nonempty(snapshot_path):
        return None
    try:
        project = Path(project_root)
        authority = Path(authority_root)
        snapshot = Path(snapshot_path)
    except (TypeError, ValueError):
        return None
    if not project.is_absolute() or not authority.is_absolute() or not snapshot.is_absolute():
        return None
    return project, authority, snapshot


def _exact_nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value) and value == value.strip()
