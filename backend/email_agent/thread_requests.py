"""Extract and track bounded atomic requests from untrusted thread text."""

from __future__ import annotations

import re

from .thread_clauses import (
    COMMA_SPLIT_RE,
    CONJUNCTION_SPLIT_RE,
    SENTENCE_SPLIT_RE,
    split_evidence_clauses,
)
from .thread_intent import (
    has_request_intent,
    has_request_syntax,
    is_coordinated_request_title,
    is_non_request_detail,
)
from .thread_outcomes import evidence_flags, has_outcome_evidence
from .thread_positions import extract_positions


MAX_REQUEST_ATOMS_PER_EVENT = 16
MAX_REQUEST_ATOM_CHARS = 240

_IDENTIFIER_SUFFIX = (
    r"(?=[A-Z0-9-]{2,32}(?![A-Z0-9_-]))"
    r"(?=[A-Z0-9-]{0,31}\d)[A-Z0-9-]{2,32}"
)
_IDENTIFIER_RE = re.compile(
    rf"(?<![A-Z0-9_])(?:RFQ|PO|SO|PART)[#:-]?{_IDENTIFIER_SUFFIX}(?![A-Z0-9_-])|"
    rf"(?:订单号|编号)\s*[:：#-]?\s*{_IDENTIFIER_SUFFIX}(?![A-Z0-9_-])",
    re.IGNORECASE,
)
_TOPIC_PATTERNS = (
    ("quotation", re.compile(r"\b(quote|quotation|pricing)\b|报价|询价|价格", re.IGNORECASE)),
    ("certificate", re.compile(r"\b(certificate|certification)\b|证书|认证", re.IGNORECASE)),
    ("shipment", re.compile(r"\b(shipment|delivery|eta|dispatch)\b|交期|发货|出货", re.IGNORECASE)),
    ("sample", re.compile(r"\bsample\b|样品", re.IGNORECASE)),
    ("quantity", re.compile(r"\b(quantity|qty)\b|数量", re.IGNORECASE)),
    ("invoice", re.compile(r"\binvoice\b|发票", re.IGNORECASE)),
    ("payment", re.compile(r"\bpayment\b|付款|支付", re.IGNORECASE)),
    ("contract", re.compile(r"\bcontract\b|合同", re.IGNORECASE)),
    ("order", re.compile(r"\border\b|订单", re.IGNORECASE)),
)


def extract_request_atoms(
    text: str, due_hint: str
) -> tuple[tuple[dict[str, object], ...], bool]:
    if not has_request_syntax(text):
        return (), True

    atoms: list[dict[str, object]] = []
    sentences = [sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    for sentence in sentences:
        comma_intent = is_coordinated_request_title(sentence)
        clauses = [part.strip() for part in COMMA_SPLIT_RE.split(sentence) if part.strip()]
        for clause in clauses:
            fragments = [part.strip() for part in CONJUNCTION_SPLIT_RE.split(clause) if part.strip()]
            fragment_intents = tuple(has_request_intent(fragment) for fragment in fragments)
            explicit_intent = any(fragment_intents)
            inherited_intent = comma_intent and _is_bare_requested_item(clause)
            if not explicit_intent and not inherited_intent:
                comma_intent = False
                continue
            intent_seen = inherited_intent or is_coordinated_request_title(clause)
            for fragment, fragment_has_intent in zip(fragments, fragment_intents):
                if fragment_has_intent:
                    intent_seen = True
                elif intent_seen and not _is_bare_requested_item(fragment):
                    intent_seen = False
                if not intent_seen:
                    continue
                fragment_atoms = _atoms_from_clause(fragment, due_hint)
                if not fragment_atoms and fragment_has_intent:
                    fragment_atoms = [_make_atom(fragment, due_hint, (), ())]
                for atom in fragment_atoms:
                    if len(atoms) >= MAX_REQUEST_ATOMS_PER_EVENT:
                        return tuple(atoms), False
                    atoms.append(atom)
            comma_intent = explicit_intent or inherited_intent
    return tuple(atoms), True


def _is_bare_requested_item(text: str) -> bool:
    if is_non_request_detail(text):
        return False
    return bool(
        _IDENTIFIER_RE.search(text) or extract_topics(text) or extract_positions(text)
    )


def merge_request_atom_sources(
    subject_atoms: tuple[dict[str, object], ...],
    body_atoms: tuple[dict[str, object], ...],
) -> tuple[tuple[dict[str, object], ...], bool]:
    merged = list(subject_atoms)
    subject_identities = [
        identity
        for atom in subject_atoms
        if (identity := _request_identity(atom)) is not None
    ]
    for atom in body_atoms:
        identity = _request_identity(atom)
        if identity is not None and identity in subject_identities:
            subject_identities.remove(identity)
            continue
        if len(merged) >= MAX_REQUEST_ATOMS_PER_EVENT:
            return tuple(merged), False
        merged.append(atom)
    return tuple(merged), True


def _request_identity(
    atom: dict[str, object],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None:
    identifiers = tuple(str(value) for value in atom["identifiers"])
    topics = tuple(str(value) for value in atom["topics"])
    positions = tuple(str(value) for value in atom["positions"])
    return (identifiers, topics, positions) if identifiers or topics or positions else None


def extract_outcome_atoms(text: str) -> tuple[dict[str, object], ...]:
    atoms: list[dict[str, object]] = []
    clauses = split_evidence_clauses(text, has_outcome_evidence, _has_atomic_context)
    for clause in clauses:
        outcome, blocker = evidence_flags(clause)
        if not outcome and not blocker:
            continue
        atoms.append(
            {
                "outcome": outcome,
                "blocker": blocker,
                "identifiers": extract_identifiers(clause),
                "topics": extract_topics(clause),
                "positions": extract_positions(clause),
            }
        )
    return tuple(atoms)


def _has_atomic_context(text: str) -> bool:
    return bool(
        _IDENTIFIER_RE.search(text) or extract_topics(text) or extract_positions(text)
    )


def extract_identifiers(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).upper() for match in _IDENTIFIER_RE.finditer(text))


def extract_topics(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _TOPIC_PATTERNS if pattern.search(text))


def _atoms_from_clause(clause: str, due_hint: str) -> list[dict[str, object]]:
    identifier_matches = list(_IDENTIFIER_RE.finditer(clause))
    topic_matches = _topic_matches(clause)
    positions = extract_positions(clause)
    if len(topic_matches) == 1 and len(identifier_matches) <= 1 and len(positions) <= 1:
        identifiers = tuple(match.group(0).upper() for match in identifier_matches)
        return [_make_atom(clause, due_hint, identifiers, (topic_matches[0][0],), positions)]
    if topic_matches:
        return _topic_atoms(clause, due_hint, topic_matches, identifier_matches)
    if len(identifier_matches) == 1 and len(positions) <= 1:
        identifiers = (identifier_matches[0].group(0).upper(),)
        return [_make_atom(clause, due_hint, identifiers, (), positions)]
    atoms = [_make_atom(clause, due_hint, (match.group(0).upper(),), ()) for match in identifier_matches]
    atoms.extend(_make_atom(clause, due_hint, (), (), (position,)) for position in positions)
    return atoms


def _topic_atoms(
    clause: str,
    due_hint: str,
    topic_matches: list[tuple[str, re.Match[str]]],
    identifier_matches: list[re.Match[str]],
) -> list[dict[str, object]]:
    atoms: list[dict[str, object]] = []
    remaining = list(identifier_matches)
    for topic_name, topic_match in topic_matches:
        identifier_match = _nearest_identifier(topic_match, remaining)
        identifiers = (identifier_match.group(0).upper(),) if identifier_match is not None else ()
        if identifier_match is not None:
            remaining.remove(identifier_match)
        display = " ".join(part for part in (topic_match.group(0), *identifiers) if part)
        atoms.append(_make_atom(display or clause, due_hint, identifiers, (topic_name,)))
    atoms.extend(
        _make_atom(match.group(0), due_hint, (match.group(0).upper(),), ())
        for match in remaining
    )
    return atoms


def _topic_matches(text: str) -> list[tuple[str, re.Match[str]]]:
    matches: list[tuple[str, re.Match[str]]] = []
    for name, pattern in _TOPIC_PATTERNS:
        topic_matches = list(pattern.finditer(text))
        if topic_matches:
            matches.append((name, topic_matches[-1]))
    return sorted(matches, key=lambda item: item[1].start())


def _nearest_identifier(
    topic_match: re.Match[str], identifiers: list[re.Match[str]]
) -> re.Match[str] | None:
    if not identifiers:
        return None
    return min(identifiers, key=lambda match: abs(match.start() - topic_match.start()))


def _make_atom(
    display_text: str,
    due_hint: str,
    identifiers: tuple[str, ...],
    topics: tuple[str, ...],
    positions: tuple[str, ...] = (),
) -> dict[str, object]:
    bounded_text = display_text[:MAX_REQUEST_ATOM_CHARS].strip()
    return {
        "display_text": bounded_text,
        "signal_text": bounded_text,
        "due_hint": due_hint,
        "identifiers": identifiers,
        "topics": topics,
        "positions": positions,
    }
