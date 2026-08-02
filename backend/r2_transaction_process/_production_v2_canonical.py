"""Internal content-free fingerprints for the V2 transaction dispatcher."""

import hashlib
import json

from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    ProductionCommandV2,
    production_action_fingerprint_v2,
)


UNBOUND_REVERSE_PLAN_V2 = "0" * 64
_TRANSACTION_COMMANDS = {
    ProductionCommandV2.EXECUTE,
    ProductionCommandV2.RESUME,
    ProductionCommandV2.ROLLBACK,
}


def is_fingerprint(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def fingerprint(domain, value):
    payload = json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()


def transaction_action_fingerprint_v2(
    binding,
    command,
    *,
    journal_head_fingerprint,
    transition_instance_fingerprint,
    remaining_reverse_plan_fingerprint,
):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(command) is not ProductionCommandV2
        or command not in _TRANSACTION_COMMANDS
        or not all(
            is_fingerprint(value)
            for value in (
                journal_head_fingerprint,
                transition_instance_fingerprint,
                remaining_reverse_plan_fingerprint,
            )
        )
        or (
            command is ProductionCommandV2.ROLLBACK
            and remaining_reverse_plan_fingerprint == UNBOUND_REVERSE_PLAN_V2
        )
        or (
            command is not ProductionCommandV2.ROLLBACK
            and remaining_reverse_plan_fingerprint != UNBOUND_REVERSE_PLAN_V2
        )
    ):
        raise ValueError("R2_TRANSACTION_ACTION_BINDING_INVALID")
    subject = fingerprint(
        "r2-transaction-action-subject-v2",
        {
            "journal_head_fingerprint": journal_head_fingerprint,
            "transition_instance_fingerprint": transition_instance_fingerprint,
            "remaining_reverse_plan_fingerprint": remaining_reverse_plan_fingerprint,
        },
    )
    return production_action_fingerprint_v2(
        binding,
        command,
        subject_fingerprint=subject,
    )
