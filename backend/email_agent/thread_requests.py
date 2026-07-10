"""Extract and track bounded atomic requests from untrusted thread text."""

from __future__ import annotations

import re


MAX_REQUEST_ATOMS_PER_EVENT = 16
MAX_REQUEST_ATOM_CHARS = 240

_REQUEST_RE = re.compile(
    r"\b(please|could you|need|confirm|provide|request)\b|请|麻烦|需要|确认|提供",
    re.IGNORECASE,
)
_SENTENCE_SPLIT_RE = re.compile(r"[.!?。！？；;\n]+")
_CONJUNCTION_SPLIT_RE = re.compile(r"\s+\band\b\s+|同时|并且|以及", re.IGNORECASE)
_OUTCOME_RE = re.compile(
    r"\b(resolved|completed|closed|has been sent|delivered)\b|已(?:解决|完成|关闭|发送|处理完成)",
    re.IGNORECASE,
)
_BLOCKER_RE = re.compile(
    r"\b(blocked|pending|unable|missing)\b|无法|缺少|待确认|阻塞",
    re.IGNORECASE,
)
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
    if _REQUEST_RE.search(text) is None:
        return (), True

    atoms: list[dict[str, object]] = []
    sentences = [sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    for sentence in sentences:
        if _REQUEST_RE.search(sentence) is None:
            continue
        fragments = [part.strip() for part in _CONJUNCTION_SPLIT_RE.split(sentence) if part.strip()]
        intent_seen = False
        for fragment in fragments:
            if _REQUEST_RE.search(fragment) is not None:
                intent_seen = True
            if not intent_seen:
                continue
            fragment_atoms = _atoms_from_clause(fragment, due_hint)
            if not fragment_atoms and _REQUEST_RE.search(fragment) is not None:
                fragment_atoms = [_make_atom(fragment, due_hint, (), ())]
            for atom in fragment_atoms:
                if len(atoms) >= MAX_REQUEST_ATOMS_PER_EVENT:
                    return tuple(atoms), False
                atoms.append(atom)
    return tuple(atoms), True


def extract_outcome_atoms(text: str) -> tuple[dict[str, object], ...]:
    atoms: list[dict[str, object]] = []
    sentences = [sentence.strip() for sentence in _SENTENCE_SPLIT_RE.split(text) if sentence.strip()]
    clauses = [
        clause.strip()
        for sentence in sentences
        for clause in _CONJUNCTION_SPLIT_RE.split(sentence)
        if clause.strip()
    ]
    for clause in clauses:
        outcome = _OUTCOME_RE.search(clause) is not None
        blocker = _BLOCKER_RE.search(clause) is not None
        if not outcome and not blocker:
            continue
        atoms.append(
            {
                "outcome": outcome,
                "blocker": blocker,
                "identifiers": extract_identifiers(clause),
                "topics": extract_topics(clause),
            }
        )
    return tuple(atoms)


def extract_identifiers(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).upper() for match in _IDENTIFIER_RE.finditer(text))


def extract_topics(text: str) -> tuple[str, ...]:
    return tuple(name for name, pattern in _TOPIC_PATTERNS if pattern.search(text))


def track_request_states(
    events: list[dict[str, object]],
) -> tuple[list[dict[str, object]], bool]:
    states: list[dict[str, object]] = []
    coverage_complete = True
    for event in events:
        coverage_complete = coverage_complete and bool(event["request_coverage_complete"])
        for outcome_atom in event["outcome_atoms"]:
            matching_index = _matching_request_index(states, outcome_atom)
            if matching_index is not None:
                if outcome_atom["blocker"]:
                    states[matching_index]["blocked"] = True
                elif outcome_atom["outcome"]:
                    states[matching_index]["resolved"] = True
                    states[matching_index]["blocked"] = False
        for atom in event["request_atoms"]:
            states.append({"event": atom, "resolved": False, "blocked": False})
    return states, coverage_complete


def _atoms_from_clause(clause: str, due_hint: str) -> list[dict[str, object]]:
    identifier_matches = list(_IDENTIFIER_RE.finditer(clause))
    topic_matches = _topic_matches(clause)
    if len(topic_matches) == 1 and len(identifier_matches) <= 1:
        identifiers = tuple(match.group(0).upper() for match in identifier_matches)
        return [_make_atom(clause, due_hint, identifiers, (topic_matches[0][0],))]
    if topic_matches:
        return _topic_atoms(clause, due_hint, topic_matches, identifier_matches)
    return [
        _make_atom(clause, due_hint, (match.group(0).upper(),), ())
        for match in identifier_matches
    ]


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
) -> dict[str, object]:
    bounded_text = display_text[:MAX_REQUEST_ATOM_CHARS].strip()
    return {
        "display_text": bounded_text,
        "signal_text": bounded_text,
        "due_hint": due_hint,
        "identifiers": identifiers,
        "topics": topics,
    }


def _matching_request_index(
    states: list[dict[str, object]], outcome: dict[str, object]
) -> int | None:
    candidates = [index for index, state in enumerate(states) if not state["resolved"]]
    outcome_identifiers = set(outcome["identifiers"])
    if outcome_identifiers:
        matches = [
            index
            for index in candidates
            if outcome_identifiers.intersection(_event(states[index])["identifiers"])
        ]
        return matches[0] if len(matches) == 1 else None
    outcome_topics = set(outcome["topics"])
    matches = [
        index
        for index in candidates
        if outcome_topics.intersection(_event(states[index])["topics"])
    ]
    return matches[0] if outcome_topics and len(matches) == 1 else None


def _event(state: dict[str, object]) -> dict[str, object]:
    event = state["event"]
    return event if isinstance(event, dict) else {}
