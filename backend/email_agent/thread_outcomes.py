"""Outcome polarity and request-state transitions for thread evidence."""

from __future__ import annotations

import re


_OUTCOME_RE = re.compile(
    r"\b(resolved|completed|closed|has been sent|delivered)\b|已(?:解决|完成|关闭|发送|处理完成)",
    re.IGNORECASE,
)
_BLOCKER_RE = re.compile(
    r"\b(blocked|pending|unable|missing)\b|无法|缺少|待确认|阻塞",
    re.IGNORECASE,
)
_NEGATED_OUTCOME_RE = re.compile(
    r"\b(?:cannot|can\s+not|can't|could\s+not|couldn't)\s+"
    r"(?:be\s+)?(?:resolved|completed|closed|sent|delivered)\b|"
    r"\b(?:not|never)(?:\s+(?:not|yet|fully|been))*\s+"
    r"(?:resolved|completed|closed|sent|delivered)\b|"
    r"\b(?:isn't|aren't|wasn't|weren't|hasn't|haven't)\s+"
    r"(?:yet\s+|fully\s+|been\s+)?(?:resolved|completed|closed|sent|delivered)\b|"
    r"(?:未|尚未|没有|并未|并非)(?:已经|已)?(?:解决|完成|关闭|发送|处理完成)|"
    r"(?:无法|不能|不可)(?:被)?(?:解决|完成|关闭|发送|处理完成)",
    re.IGNORECASE,
)


def evidence_flags(text: str) -> tuple[bool, bool]:
    negated = _NEGATED_OUTCOME_RE.search(text) is not None
    outcome = _OUTCOME_RE.search(text) is not None and not negated
    blocker = _BLOCKER_RE.search(text) is not None or negated
    return outcome, blocker


def has_outcome_evidence(text: str) -> bool:
    outcome, blocker = evidence_flags(text)
    return outcome or blocker


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
                _apply_evidence(states[matching_index], outcome_atom)
        for atom in event["request_atoms"]:
            states.append({"event": atom, "resolved": False, "blocked": False})
    return states, coverage_complete


def _apply_evidence(state: dict[str, object], evidence: dict[str, object]) -> None:
    if evidence["blocker"]:
        state["resolved"] = False
        state["blocked"] = True
    elif evidence["outcome"]:
        state["resolved"] = True
        state["blocked"] = False


def _matching_request_index(
    states: list[dict[str, object]], evidence: dict[str, object]
) -> int | None:
    identifiers = set(evidence["identifiers"])
    if identifiers:
        matches = [
            index
            for index, state in enumerate(states)
            if identifiers.intersection(_request_event(state)["identifiers"])
        ]
        return matches[0] if len(matches) == 1 else None
    positions = set(evidence["positions"])
    if positions:
        matches = [
            index
            for index, state in enumerate(states)
            if positions.intersection(_request_event(state)["positions"])
        ]
        return matches[0] if len(matches) == 1 else None
    topics = set(evidence["topics"])
    matches = [
        index
        for index, state in enumerate(states)
        if topics.intersection(_request_event(state)["topics"])
    ]
    return matches[0] if topics and len(matches) == 1 else None


def _request_event(state: dict[str, object]) -> dict[str, object]:
    event = state["event"]
    return event if isinstance(event, dict) else {}
