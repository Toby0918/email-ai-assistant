"""Fresh real-console confirmation for the one fixed incident disposition."""

from __future__ import annotations

import hashlib
import sys
import time

from .console_gate import require_fixed_windows_console_v1
from .incident_contracts import fixed_incident_stage_contract_v1
from .zero_readiness import Issue39ZeroMutationReadinessV1


_ACKNOWLEDGEMENT = (
    "CONFIRM_ISSUE38_INCIDENT_STAGE_DISPOSITION_V1_"
    "NOT_CLOSURE_OR_CUTOVER"
)
_WINDOW_SECONDS = 300


def confirm_fixed_incident_disposition_v1(readiness) -> bool:
    """Confirm only the fixed retained-stage move; grant no later authority."""

    try:
        if (
            type(readiness) is not Issue39ZeroMutationReadinessV1
            or readiness.incident_state != "SOURCE_VERIFIED"
            or not require_fixed_windows_console_v1()
        ):
            return False
        prepared = int(time.time())
        candidate = _candidate_fingerprint(readiness, prepared)
        sys.stdout.write(candidate + "\n" + _ACKNOWLEDGEMENT + "\n")
        sys.stdout.flush()
        observed_candidate = sys.stdin.readline()
        observed_acknowledgement = sys.stdin.readline()
        confirmed = int(time.time())
        return (
            _line(observed_candidate) == candidate
            and _line(observed_acknowledgement) == _ACKNOWLEDGEMENT
            and prepared <= confirmed < prepared + _WINDOW_SECONDS
            and require_fixed_windows_console_v1()
        )
    except Exception:
        return False


def _candidate_fingerprint(readiness, prepared):
    contract = fixed_incident_stage_contract_v1()
    return hashlib.sha256(
        b"r2-issue39-incident-confirmation-v1\0"
        + bytes.fromhex(readiness.readiness_fingerprint)
        + bytes.fromhex(contract.contract_fingerprint)
        + prepared.to_bytes(8, "big")
    ).hexdigest()


def _line(value):
    if type(value) is not str or not value.endswith("\n"):
        raise ValueError
    value = value[:-1]
    if value.endswith("\r"):
        value = value[:-1]
    if not value or any(not 32 <= ord(character) <= 126 for character in value):
        raise ValueError
    return value
