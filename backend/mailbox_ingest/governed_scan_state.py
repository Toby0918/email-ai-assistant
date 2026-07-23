"""Encrypted checkpoint and aggregate projection for governed corpus scans."""

from __future__ import annotations

from dataclasses import dataclass

from .bodystructure import MAX_PARTS
from .control_store import ControlStoreError
from .scan import ScanError


STATE_COUNTERS = (
    "processed", "excluded_automated", "excluded_non_sales",
    "excluded_forwards", "sensitive", "ambiguous",
    "supported_attachments", "unsupported_attachments",
)
_OUTCOMES = {
    "candidate", "automated", "non_sales", "forward", "sensitive", "ambiguous",
}
_HEX = frozenset("0123456789abcdef")
_MAX_OUTCOME_TOKENS = 20_000


@dataclass(frozen=True)
class GovernedScanReport:
    processed_count: int
    unique_message_count: int
    duplicate_message_count: int
    customer_request_count: int
    sales_reply_count: int
    pair_count: int
    duplicate_quotation_count: int
    excluded_automated_count: int
    excluded_non_sales_count: int
    excluded_forward_count: int
    sensitive_count: int
    ambiguous_count: int
    supported_attachment_count: int
    unsupported_attachment_count: int

    def to_counts(self) -> dict[str, int]:
        return {
            "processed": self.processed_count,
            "unique_messages": self.unique_message_count,
            "duplicate_messages": self.duplicate_message_count,
            "customer_requests": self.customer_request_count,
            "sales_replies": self.sales_reply_count,
            "pairs": self.pair_count,
            "duplicate_quotations": self.duplicate_quotation_count,
            "excluded_automated": self.excluded_automated_count,
            "excluded_non_sales": self.excluded_non_sales_count,
            "excluded_forwards": self.excluded_forward_count,
            "sensitive": self.sensitive_count,
            "ambiguous": self.ambiguous_count,
            "supported_attachments": self.supported_attachment_count,
            "unsupported_attachments": self.unsupported_attachment_count,
        }


def advance_scan_state(
    state: dict[str, object], folder: dict[str, object], uid: int,
    outcome: str, supported: int, unsupported: int,
    outcome_token: str | None,
) -> None:
    counters = state["counts"]
    if outcome_token is None:
        counters["processed"] += 1
        counter = _counter_name(outcome)
        if counter is not None:
            counters[counter] += 1
        counters["supported_attachments"] += supported
        counters["unsupported_attachments"] += unsupported
    else:
        outcomes = state["outcomes"]
        current = outcomes.get(outcome_token)
        if current is None and len(outcomes) >= _MAX_OUTCOME_TOKENS:
            raise ScanError("scan_state_capacity_exceeded")
        if current is None or (
            current[0] != "candidate" and outcome == "candidate"
        ):
            outcomes[outcome_token] = [outcome, supported, unsupported]
    folder["cursor"] = uid
    folder["processed_count"] += 1


def load_or_create_scan_state(
    control: object, bundle: object, policy_fingerprint: str,
) -> dict[str, object]:
    inventory = bundle.inventory
    try:
        state = control.read("scan-state")
    except ControlStoreError as error:
        if error.code != "control_store_missing":
            raise ScanError("scan_state_invalid") from None
        state = _new_state(bundle, policy_fingerprint)
        try:
            control.write("scan-state", state)
        except Exception:
            raise ScanError("scan_state_write_failed") from None
    _validate_state(state, bundle, policy_fingerprint)
    return state


def _new_state(bundle: object, policy: str) -> dict[str, object]:
    inventory = bundle.inventory
    return {
        "schema_version": 3, "scope": inventory.opaque_scope_id,
        "fingerprint": inventory.fingerprint, "policy": policy,
        "window_start": inventory.window_start.isoformat(),
        "window_end": inventory.window_end.isoformat(),
        "counts": {name: 0 for name in STATE_COUNTERS},
        "outcomes": {},
        "folders": {item.opaque_folder_id: {
            "uidvalidity": item.uidvalidity, "cursor": 0, "processed_count": 0,
        } for item in bundle.evidence},
    }


def _validate_state(state: object, bundle: object, policy: str) -> None:
    inventory = bundle.inventory
    keys = {
        "schema_version", "scope", "fingerprint", "policy", "window_start",
        "window_end", "counts", "outcomes", "folders",
    }
    if not isinstance(state, dict) or set(state) != keys:
        raise ScanError("scan_state_invalid")
    expected = {item.opaque_folder_id: item.uidvalidity for item in bundle.evidence}
    if (
        type(state["schema_version"]) is not int or state["schema_version"] != 3
        or state["scope"] != inventory.opaque_scope_id
        or state["fingerprint"] != inventory.fingerprint or state["policy"] != policy
        or state["window_start"] != inventory.window_start.isoformat()
        or state["window_end"] != inventory.window_end.isoformat()
        or not isinstance(state["counts"], dict)
        or set(state["counts"]) != set(STATE_COUNTERS)
        or any(type(value) is not int or value < 0 for value in state["counts"].values())
        or not _valid_outcomes(state["outcomes"])
        or not isinstance(state["folders"], dict) or set(state["folders"]) != set(expected)
    ):
        raise ScanError("scan_state_invalid")
    for folder_id, value in state["folders"].items():
        if not _valid_folder_state(value, expected[folder_id]):
            raise ScanError("scan_state_invalid")


def _valid_folder_state(value: object, uidvalidity: int) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"uidvalidity", "cursor", "processed_count"}
        and value["uidvalidity"] == uidvalidity
        and all(type(value[name]) is int and value[name] >= 0
                for name in ("cursor", "processed_count"))
    )


def report_from_state(
    state: dict[str, object], summary: object,
) -> GovernedScanReport:
    counts = state["counts"]
    outcomes = _outcome_counts(state["outcomes"])
    processed = counts["processed"] + len(state["outcomes"])
    return GovernedScanReport(
        processed, summary.canonical_message_count,
        summary.duplicate_message_count, summary.request_count,
        summary.reply_count, summary.pair_count,
        summary.duplicate_quotation_count,
        counts["excluded_automated"] + outcomes["automated"],
        counts["excluded_non_sales"] + outcomes["non_sales"],
        counts["excluded_forwards"] + outcomes["forward"],
        counts["sensitive"] + outcomes["sensitive"],
        counts["ambiguous"] + outcomes["ambiguous"],
        counts["supported_attachments"] + outcomes["supported"]
        + summary.supported_attachment_count,
        counts["unsupported_attachments"] + outcomes["unsupported"]
        + summary.unsupported_attachment_count,
    )


def _counter_name(outcome: str) -> str | None:
    return {
        "automated": "excluded_automated", "non_sales": "excluded_non_sales",
        "forward": "excluded_forwards", "sensitive": "sensitive",
        "ambiguous": "ambiguous",
    }.get(outcome)


def _valid_outcomes(value: object) -> bool:
    return (
        isinstance(value, dict)
        and len(value) <= _MAX_OUTCOME_TOKENS
        and all(
            isinstance(token, str)
            and len(token) == 64
            and set(token).issubset(_HEX)
            and isinstance(selected, list)
            and len(selected) == 3
            and isinstance(selected[0], str)
            and selected[0] in _OUTCOMES
            and all(
                type(count) is int and 0 <= count <= MAX_PARTS
                for count in selected[1:]
            )
            and selected[1] + selected[2] <= MAX_PARTS
            for token, selected in value.items()
        )
    )


def _outcome_counts(value: dict[str, list[object]]) -> dict[str, int]:
    result = {name: 0 for name in _OUTCOMES}
    result.update({"supported": 0, "unsupported": 0})
    for outcome, supported, unsupported in value.values():
        result[outcome] += 1
        if outcome != "candidate":
            result["supported"] += supported
            result["unsupported"] += unsupported
    return result


__all__ = [
    "GovernedScanReport", "advance_scan_state", "load_or_create_scan_state",
    "report_from_state",
]
