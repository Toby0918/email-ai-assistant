"""Reviewed V3 binding plus fixed local confirmation runtime ports."""

import ctypes
import os
import sys
import time
from dataclasses import dataclass
from threading import Lock

from backend.r2_solo_maintainer_closure.contracts import FinalMasterBindingV1

from ._canonical import fingerprint
from .binding import ApprovedCutoverBindingV3
from .errors import ProductionBindingError


_MAX_VISIBLE_CHARACTERS = 4_096


@dataclass(frozen=True, slots=True)
class _ExecutionConfirmationPorts:
    clock: object
    console: object


@dataclass(frozen=True, slots=True)
class _CandidateRuntime:
    clock: object
    console: object
    prepared_monotonic_ns: int
    state: object


class _LiveState:
    __slots__ = ("_append_binding", "_lock", "_phase")

    def __init__(self, phase):
        self._append_binding = None
        self._lock = Lock()
        self._phase = phase

    @property
    def phase(self):
        return self._phase

    def require(self, accepted):
        with self._lock:
            if self._phase not in accepted:
                raise ProductionBindingError()

    def transition(self, expected, replacement):
        with self._lock:
            if self._phase != expected:
                raise ProductionBindingError()
            self._phase = replacement

    def complete_append(self, claim, journal):
        with self._lock:
            head = _require_exact_journal_append(claim, journal)
            if self._phase != "APPENDING":
                raise ProductionBindingError()
            self._append_binding = (journal, head)
            self._phase = "APPENDED"

    def consume_append(self, claim):
        with self._lock:
            if self._phase != "APPENDED" or self._append_binding is None:
                raise ProductionBindingError()
            journal, head = self._append_binding
            if _require_exact_journal_append(claim, journal) != head:
                raise ProductionBindingError()
            self._phase = "ATTEMPTED"


def _require_exact_journal_append(claim, journal):
    try:
        records = journal.records
        record = records[-1] if records else journal.genesis
        claims = journal.execution_confirmation_claims
        head = journal.current_head_fingerprint
        predecessor = (
            record.predecessor_head_fingerprint
            if records
            else record.pre_genesis_head_fingerprint
        )
        transition = (
            record.transition_instance_fingerprint
            if records
            else record.reviewed_evidence_fingerprint
        )
        valid = (
            (not records or record.record_type.value == "AUTHORITY_CLAIM")
            and record.execution_confirmation_claim is claim
            and record.head_fingerprint == head
            and predecessor == claim.prior_journal_head_fingerprint
            and transition == claim.transition_instance_fingerprint
            and record.journal_owner_fingerprint == claim.journal_owner_fingerprint
            and len(claims) == claim.claim_sequence
            and claims[-1] is claim
        )
    except Exception:
        raise ProductionBindingError() from None
    if not valid:
        raise ProductionBindingError()
    return head


class _SystemExecutionClock:
    @staticmethod
    def wall_epoch():
        return int(time.time())

    @staticmethod
    def monotonic_ns():
        return time.monotonic_ns()


class _WindowsExecutionConsole:
    @staticmethod
    def snapshot():
        if os.name != "nt":
            raise ProductionBindingError()
        return tuple(
            _console_identity(stream)
            for stream in (sys.stdin, sys.stdout, sys.stderr)
        )

    @staticmethod
    def display_confirmation(fingerprint, acknowledgement):
        sys.stdout.write(fingerprint + "\n")
        sys.stdout.write(acknowledgement + "\n")
        sys.stdout.flush()

    @staticmethod
    def read_candidate_fingerprint():
        return _read_exact_console_line(_console_identity(sys.stdin)[2])

    @staticmethod
    def read_acknowledgement():
        return _read_exact_console_line(_console_identity(sys.stdin)[2])

    @staticmethod
    def require_no_pending_input():
        _require_no_pending_console_input(_console_identity(sys.stdin)[2])


def _fixed_execution_confirmation_ports():
    return _ExecutionConfirmationPorts(
        clock=_SystemExecutionClock(),
        console=_WindowsExecutionConsole(),
    )


def _console_identity(stream):
    try:
        from msvcrt import get_osfhandle

        if stream.isatty() is not True:
            raise ProductionBindingError()
        descriptor = stream.fileno()
        if type(descriptor) is not int or descriptor < 0:
            raise ProductionBindingError()
        handle = get_osfhandle(descriptor)
        mode = ctypes.c_ulong()
        accepted = ctypes.windll.kernel32.GetConsoleMode(
            ctypes.c_void_p(handle),
            ctypes.byref(mode),
        )
        if type(handle) is not int or handle == -1 or accepted == 0:
            raise ProductionBindingError()
        return id(stream), descriptor, handle
    except ProductionBindingError:
        raise
    except Exception:
        raise ProductionBindingError() from None


def _read_exact_console_line(handle):
    buffer = ctypes.create_unicode_buffer(_MAX_VISIBLE_CHARACTERS + 2)
    read = ctypes.c_ulong()
    accepted = ctypes.windll.kernel32.ReadConsoleW(
        ctypes.c_void_p(handle), buffer, len(buffer), ctypes.byref(read), None
    )
    if accepted != 1:
        raise ProductionBindingError()
    value = buffer[:read.value]
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n"):
        value = value[:-1]
    else:
        raise ProductionBindingError()
    if not value or any(not 32 <= ord(character) <= 126 for character in value):
        raise ProductionBindingError()
    return value


def _require_no_pending_console_input(handle):
    record = ctypes.create_string_buffer(32)
    count = ctypes.c_ulong()
    accepted = ctypes.windll.kernel32.PeekConsoleInputW(
        ctypes.c_void_p(handle), record, 1, ctypes.byref(count)
    )
    if accepted != 1 or count.value != 0:
        raise ProductionBindingError()


def _require_confirmation_observation(
    candidate,
    runtime,
    fingerprint_value,
    acknowledgement_value,
    confirmed_at_epoch,
    confirmed_monotonic_ns,
    before,
    after,
    expected_acknowledgement,
):
    monotonic_limit = runtime.prepared_monotonic_ns + (
        candidate.confirmation_window_seconds * 1_000_000_000
    )
    if (
        not _visible_exact(fingerprint_value, candidate.candidate_fingerprint)
        or not _visible_exact(acknowledgement_value, expected_acknowledgement)
        or before != after
        or type(confirmed_at_epoch) is not int
        or confirmed_at_epoch < candidate.prepared_at_epoch
        or confirmed_at_epoch >= candidate.expires_at_epoch
        or type(confirmed_monotonic_ns) is not int
        or confirmed_monotonic_ns < runtime.prepared_monotonic_ns
        or confirmed_monotonic_ns >= monotonic_limit
    ):
        raise ProductionBindingError()


def _visible_exact(value, expected):
    return (
        type(value) is str
        and value == expected
        and value != ""
        and all(32 <= ord(character) <= 126 for character in value)
    )


def require_reviewed_production_binding_v3(final_master, production_binding):
    if (
        type(final_master) is not FinalMasterBindingV1
        or type(production_binding) is not ApprovedCutoverBindingV3
        or production_binding.final_master_binding_fingerprint
        != final_master.binding_fingerprint
        or production_binding.final_commit_oid != final_master.final_commit_oid
        or production_binding.final_tree_oid != final_master.final_tree_oid
        or production_binding.closure_map_fingerprint
        != final_master.closure_map_fingerprint
        or production_binding.source_package_fingerprint
        != final_master.source_package_fingerprint
        or production_binding.runbook_fingerprint
        != final_master.runbook_fingerprint
        or production_binding.workflow_fingerprint
        != final_master.workflow_fingerprint
    ):
        raise ProductionBindingError()
    return production_binding


def production_composition_evidence_fingerprint_v3(
    final_master,
    production_binding,
):
    value = require_reviewed_production_binding_v3(
        final_master,
        production_binding,
    )
    return fingerprint(
        "r2-reviewed-production-composition-evidence-v3",
        {
            "final_master_binding_fingerprint": final_master.binding_fingerprint,
            "production_binding_fingerprint": value.binding_fingerprint,
            "operator_role_registry_fingerprint": (
                value.operator_role_registry_fingerprint
            ),
            "command_domain_registry_fingerprint": (
                value.command_domain_registry_fingerprint
            ),
            "production_role_registry_fingerprint": (
                value.production_role_registry_fingerprint
            ),
            "execution_confirmation_policy_fingerprint": (
                value.execution_confirmation_policy_fingerprint
            ),
            "assurance_model": value.assurance_model,
            "operator_count": value.operator_count,
            "independent_reviewer_count": value.independent_reviewer_count,
            "external_signer_count": value.external_signer_count,
            "issue39_authority_count": value.issue39_authority_count,
        },
    )
