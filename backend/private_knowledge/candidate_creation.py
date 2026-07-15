"""Crash-recoverable creation from one reviewed imported candidate."""

from __future__ import annotations

import json
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .candidate_imports import ImportedCandidate, ImportedCandidateStore
from .errors import PrivateKnowledgeError
from .repository import AuthorityRepository
from .review import KnowledgeReviewService
from .schema import KnowledgeCardV1, validate_non_verbatim


_PROPOSAL_FIELDS = {
    "schema_version", "rule_type", "language", "applicability",
    "generic_rule", "normalized_signals", "enum_mapping",
    "safe_reply_guidance", "creator_actor_ref", "privacy_checked_at",
}


def create_reviewed_candidate(
    authority: Path,
    master_key: bytes | bytearray,
    *,
    authority_id: str,
    candidate_id: str,
    proposal_path: Path,
    now: datetime,
    clock: Callable[[], datetime],
) -> KnowledgeCardV1:
    proposal = _read_proposal(proposal_path)
    imports = ImportedCandidateStore(
        authority, master_key, authority_id=authority_id
    )
    candidate = imports.get(candidate_id)
    if candidate is None:
        raise PrivateKnowledgeError("candidate_missing")
    if candidate.is_expired(now):
        imports.discard(candidate.candidate_id)
        raise PrivateKnowledgeError("candidate_expired")
    repository = AuthorityRepository(
        authority, master_key, authority_id=authority_id
    )
    existing = repository.get(candidate.candidate_id)
    created_at = now if existing is None else _created_at(existing)
    card = card_from_proposal(candidate, proposal, created_at)
    validate_non_verbatim(
        {
            "generic_rule": card.generic_rule,
            "safe_reply_guidance": card.safe_reply_guidance,
        },
        candidate.support_texts,
    )
    if existing is None:
        KnowledgeReviewService(repository, clock=clock).create_candidate(card)
    elif existing != card:
        raise PrivateKnowledgeError("card_exists")
    imports.delete(candidate.candidate_id)
    return card


def card_from_proposal(
    candidate: ImportedCandidate,
    proposal: dict[str, object],
    now: datetime,
) -> KnowledgeCardV1:
    mapping = {
        "schema_version": "KnowledgeCardV1", "card_id": candidate.candidate_id,
        "version": 1, "rule_type": proposal["rule_type"],
        "language": proposal["language"],
        "applicability": proposal["applicability"],
        "generic_rule": proposal["generic_rule"],
        "normalized_signals": proposal["normalized_signals"],
        "enum_mapping": proposal["enum_mapping"],
        "safe_reply_guidance": proposal["safe_reply_guidance"],
        "evidence": {
            "conversation_bucket": candidate.evidence[0],
            "counterparty_bucket": candidate.evidence[1],
        },
        "privacy_check": {
            "status": "passed", "checked_at": proposal["privacy_checked_at"],
        },
        "review": {
            "creator": {
                "actor_ref": proposal["creator_actor_ref"], "role": "creator",
                "approved_at": _time(now), "card_version": 1,
            },
            "business": None, "privacy": None, "owner": None,
        },
        "lifecycle": {
            "status": "candidate", "created_at": _time(now),
            "expires_at": candidate.expires_at, "review_due_at": None,
        },
    }
    return KnowledgeCardV1.from_mapping(mapping)


def _read_proposal(path: Path) -> dict[str, object]:
    try:
        metadata = path.lstat()
        if (path.is_symlink() or not stat.S_ISREG(metadata.st_mode)
                or not 1 <= metadata.st_size <= 64 * 1024):
            raise ValueError
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or set(value) != _PROPOSAL_FIELDS:
            raise ValueError
        if value["schema_version"] != "KnowledgeProposalV1":
            raise ValueError
        return value
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        raise PrivateKnowledgeError("proposal_invalid") from None


def _created_at(card: KnowledgeCardV1) -> datetime:
    try:
        return datetime.fromisoformat(card.lifecycle[1][:-1] + "+00:00")
    except (TypeError, ValueError):
        raise PrivateKnowledgeError("card_exists") from None


def _time(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
