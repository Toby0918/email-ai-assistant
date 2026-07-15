"""Injected, single-item command service behind the private-knowledge CLI."""

from __future__ import annotations

import argparse
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .candidate_creation import (
    card_from_proposal as _card_from_proposal,
    create_reviewed_candidate,
)
from .candidate_imports import ImportedCandidate, ImportedCandidateStore
from .cli_models import PrivateCliResult
from .errors import PrivateKnowledgeError
from .key_store import (
    KeyProtector,
    initialize_private_keys,
    open_authority_keys,
    open_candidate_key,
)
from .repository import AuthorityRepository, CandidateBatchStore
from .review import KnowledgeReviewService
from .snapshot import publish_runtime_snapshot
from .storage_policy import validate_private_storage


class PrivateKnowledgeCommandService:
    def __init__(
        self,
        *,
        protector: KeyProtector,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        project_root: Path | None = None,
        snapshot_path_validator: Callable[[Path], object] | None = None,
        storage_path_validator: Callable[..., object] | None = None,
    ) -> None:
        self._protector = protector
        self._clock = clock
        self._project = (
            Path(__file__).resolve().parents[2]
            if project_root is None else Path(project_root)
        )
        self._snapshot_path_validator = snapshot_path_validator
        self._storage_path_validator = storage_path_validator

    def dispatch(self, arguments: argparse.Namespace) -> PrivateCliResult:
        handlers = {
            "init": self._initialize,
            "import-candidate": self._import_candidate,
            "create": self._create,
            "business-approve": self._business,
            "privacy-approve": self._privacy,
            "owner-approve": self._owner,
            "reject": self._reject,
            "expire": self._expire,
            "approve": self._approve,
            "deprecate": self._deprecate,
            "revoke": self._revoke,
            "publish": self._publish,
        }
        handler = handlers.get(getattr(arguments, "command", None))
        if handler is None:
            raise PrivateKnowledgeError("argument_invalid")
        return handler(arguments)

    def _initialize(self, arguments: argparse.Namespace) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        candidate = Path(arguments.candidate_root)
        self._validate_storage(authority, candidate)
        initialize_private_keys(authority, candidate, self._protector)
        with open_authority_keys(authority, self._protector) as keys:
            AuthorityRepository(
                authority, keys.authority_key, authority_id=arguments.authority_id
            ).initialize()
            ImportedCandidateStore(
                authority, keys.authority_key, authority_id=arguments.authority_id
            ).initialize()
        return PrivateCliResult("private_knowledge_initialized")

    def _import_candidate(self, arguments: argparse.Namespace) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        batch_root = Path(arguments.batch_root)
        self._validate_storage(authority, batch_root)
        with open_candidate_key(batch_root, self._protector) as candidate_key:
            batch = CandidateBatchStore(
                batch_root, candidate_key, batch_id=arguments.batch_id,
                clock=self._clock,
            )
            expires_at, candidates = batch.read_with_expiry()
            selected = next(
                (item for item in candidates
                 if item.candidate_id == arguments.candidate_id),
                None,
            )
            if selected is None or selected.evidence is None:
                raise PrivateKnowledgeError("candidate_missing")
            with open_authority_keys(authority, self._protector) as keys:
                ImportedCandidateStore(
                    authority, keys.authority_key,
                    authority_id=arguments.authority_id,
                ).add(ImportedCandidate(
                    selected.candidate_id, selected.support_texts,
                    selected.evidence, expires_at,
                ))
            batch.discard(selected.candidate_id)
        return PrivateCliResult("candidate_imported", selected.candidate_id, 1)

    def _create(self, arguments: argparse.Namespace) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        self._validate_storage(authority)
        with open_authority_keys(authority, self._protector) as keys:
            card = create_reviewed_candidate(
                authority, keys.authority_key,
                authority_id=arguments.authority_id,
                candidate_id=arguments.candidate_id,
                proposal_path=Path(arguments.reviewed_proposal),
                now=self._now(), clock=self._clock,
            )
        return PrivateCliResult("candidate_created", card.card_id, 1)

    def _business(self, arguments: argparse.Namespace) -> PrivateCliResult:
        return self._review_action(arguments, "business")

    def _privacy(self, arguments: argparse.Namespace) -> PrivateCliResult:
        return self._review_action(arguments, "privacy")

    def _owner(self, arguments: argparse.Namespace) -> PrivateCliResult:
        return self._review_action(arguments, "owner")

    def _approve(self, arguments: argparse.Namespace) -> PrivateCliResult:
        return self._review_action(arguments, "approve")

    def _reject(self, arguments: argparse.Namespace) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        self._validate_storage(authority)
        with open_authority_keys(authority, self._protector) as keys:
            ImportedCandidateStore(
                authority, keys.authority_key, authority_id=arguments.authority_id
            ).discard(arguments.card_id)
            self._review(
                authority, arguments.authority_id, keys.authority_key
            ).reject(arguments.card_id)
        return PrivateCliResult("reject_complete", arguments.card_id, 1)

    def _deprecate(self, arguments: argparse.Namespace) -> PrivateCliResult:
        return self._review_action(arguments, "deprecate")

    def _revoke(self, arguments: argparse.Namespace) -> PrivateCliResult:
        return self._review_action(arguments, "revoke")

    def _expire(self, arguments: argparse.Namespace) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        self._validate_storage(authority)
        with open_authority_keys(authority, self._protector) as keys:
            imports = ImportedCandidateStore(
                authority, keys.authority_key, authority_id=arguments.authority_id
            )
            imported = imports.get(arguments.card_id)
            if imported is not None:
                if not imported.is_expired(self._now()):
                    raise PrivateKnowledgeError("candidate_not_expired")
                imports.discard(arguments.card_id)
            review = self._review(authority, arguments.authority_id, keys.authority_key)
            review.expire_candidate(arguments.card_id)
        return PrivateCliResult("candidate_expired", arguments.card_id, 1)

    def _review_action(self, arguments: argparse.Namespace, action: str) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        self._validate_storage(authority)
        with open_authority_keys(authority, self._protector) as keys:
            review = self._review(authority, arguments.authority_id, keys.authority_key)
            methods = {
                "business": lambda: review.record_business_approval(arguments.card_id, arguments.actor_ref),
                "privacy": lambda: review.record_privacy_approval(arguments.card_id, arguments.actor_ref),
                "owner": lambda: review.record_owner_approval(arguments.card_id, arguments.actor_ref),
                "approve": lambda: review.approve(arguments.card_id),
                "reject": lambda: review.reject(arguments.card_id),
                "deprecate": lambda: review.deprecate(arguments.card_id),
                "revoke": lambda: review.revoke(arguments.card_id),
            }
            methods[action]()
        return PrivateCliResult(f"{action}_complete", arguments.card_id, 1)

    def _publish(self, arguments: argparse.Namespace) -> PrivateCliResult:
        authority = Path(arguments.authority_root)
        self._validate_storage(authority)
        with open_authority_keys(authority, self._protector) as keys:
            review = self._review(authority, arguments.authority_id, keys.authority_key)
            cards = review.publication_candidates()
            publish_runtime_snapshot(
                Path(arguments.snapshot), cards,
                authority_id=arguments.authority_id,
                snapshot_id=arguments.snapshot_id,
                encryption_key=keys.snapshot_key,
                signing_private_key=Ed25519PrivateKey.from_private_bytes(
                    bytes(keys.signing_seed)
                ),
                now=self._now(),
                forbidden_roots=_forbidden_roots(self._project, authority),
                path_validator=self._snapshot_path_validator,
            )
        return PrivateCliResult("snapshot_published", arguments.snapshot_id, len(cards))

    def _review(self, root: Path, authority_id: str, key: bytes | bytearray) -> KnowledgeReviewService:
        repository = AuthorityRepository(root, key, authority_id=authority_id)
        return KnowledgeReviewService(repository, clock=self._clock)

    def _validate_storage(self, *paths: Path) -> None:
        if self._storage_path_validator is not None:
            try:
                self._storage_path_validator(*paths)
                return
            except Exception:
                raise PrivateKnowledgeError("private_storage_path_invalid") from None
        validate_private_storage(self._project, *paths)

    def _now(self) -> datetime:
        value = self._clock()
        if (not isinstance(value, datetime) or value.utcoffset() != timedelta(0)
                or value.microsecond):
            raise PrivateKnowledgeError("clock_invalid")
        return value


def _forbidden_roots(*roots: Path) -> tuple[Path, ...]:
    values = [Path(root).resolve() for root in roots]
    values.append(Path(tempfile.gettempdir()).resolve())
    one_drive = os.environ.get("OneDrive")
    if one_drive:
        values.append(Path(one_drive).resolve())
    return tuple(values)
