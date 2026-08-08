"""Dormant Execution Confirmation V1 values and one live confirmation path."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._binding_body import CONFIRMATION_ACKNOWLEDGEMENT
from ._canonical import canonical_json, strict_json_object
from ._claim_body import (
    CANDIDATE_FIELDS,
    CLAIM_FIELDS,
    allocate_contract,
    build_candidate_body,
    build_claim_body,
    candidate_body_from_source,
    candidate_body_from_claim,
    candidate_fingerprint,
    claim_fingerprint,
    contract_body,
    contract_mapping,
)
from .errors import ExecutionConfirmationError
from .review import (
    _CandidateRuntime,
    _LiveState,
    _fixed_execution_confirmation_ports,
    _require_confirmation_observation,
)
from .vocabulary import AuthorityDomainV2, ProductionCommandV2


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ExecutionConfirmationCandidateV1:
    candidate_type: str
    status: str
    confirmation_policy: str
    production_binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    closure_manifest_fingerprint: str = field(repr=False)
    solo_maintainer_attestation_receipt_fingerprint: str = field(repr=False)
    command: ProductionCommandV2
    command_domain: AuthorityDomainV2
    operator_role_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    action_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    remaining_reverse_plan_fingerprint: str = field(repr=False)
    claim_sequence: int
    confirmation_acknowledgement: str
    prepared_at_epoch: int
    expires_at_epoch: int
    confirmation_window_seconds: int
    single_use: int
    candidate_fingerprint: str = field(repr=False)
    _binding: object = field(repr=False, compare=False)
    _runtime: object = field(repr=False, compare=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError(
            "ExecutionConfirmationCandidateV1 requires prepare function"
        )

    @classmethod
    def from_json(cls, payload: object, *, binding: object):
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise ExecutionConfirmationError()
            if set(source) != {*CANDIDATE_FIELDS, "candidate_fingerprint"}:
                raise ExecutionConfirmationError()
            body = candidate_body_from_source(binding, source)
            if any(source[name] != body[name] for name in CANDIDATE_FIELDS):
                raise ExecutionConfirmationError()
            if source["candidate_fingerprint"] != candidate_fingerprint(body):
                raise ExecutionConfirmationError()
            return _construct_candidate(body, binding, None)
        except ExecutionConfirmationError:
            raise
        except Exception:
            raise ExecutionConfirmationError() from None

    def to_mapping(self):
        return contract_mapping(self, CANDIDATE_FIELDS, "candidate_fingerprint")

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ExecutionConfirmationClaimV1:
    claim_type: str
    status: str
    confirmation_policy: str
    production_binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    closure_manifest_fingerprint: str = field(repr=False)
    solo_maintainer_attestation_receipt_fingerprint: str = field(repr=False)
    command: ProductionCommandV2
    command_domain: AuthorityDomainV2
    operator_role_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    action_fingerprint: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    transition_instance_fingerprint: str = field(repr=False)
    remaining_reverse_plan_fingerprint: str = field(repr=False)
    claim_sequence: int
    prepared_at_epoch: int
    confirmed_at_epoch: int
    expires_at_epoch: int
    confirmation_window_seconds: int
    acknowledgement: str
    acknowledgement_fingerprint: str = field(repr=False)
    assurance_model: str
    operator_count: int
    independent_reviewer_count: int
    external_signer_count: int
    execution_confirmation_count: int
    single_use: int
    replay_count: int
    provider_attempt_count: int
    deletion_operation_count: int
    claim_fingerprint: str = field(repr=False)
    _confirmed_monotonic_ns: object = field(repr=False, compare=False)
    _expires_monotonic_ns: object = field(repr=False, compare=False)
    _attempt_state: object = field(repr=False, compare=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ExecutionConfirmationClaimV1 requires confirm function")

    @classmethod
    def from_json(cls, payload: object, *, binding: object):
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise ExecutionConfirmationError()
            if set(source) != {*CLAIM_FIELDS, "claim_fingerprint"}:
                raise ExecutionConfirmationError()
            candidate_body = candidate_body_from_claim(binding, source)
            body = build_claim_body(candidate_body, source["confirmed_at_epoch"])
            if any(source[name] != body[name] for name in CLAIM_FIELDS):
                raise ExecutionConfirmationError()
            if source["claim_fingerprint"] != claim_fingerprint(body):
                raise ExecutionConfirmationError()
            return _construct_claim(body, None, None, None)
        except ExecutionConfirmationError:
            raise
        except Exception:
            raise ExecutionConfirmationError() from None

    def to_mapping(self):
        return contract_mapping(self, CLAIM_FIELDS, "claim_fingerprint")

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def prepare_execution_confirmation_v1(
    *,
    binding,
    closure_manifest_fingerprint,
    solo_maintainer_attestation_receipt_fingerprint,
    command,
    action_fingerprint,
    journal_owner_fingerprint,
    prior_journal_head_fingerprint,
    transition_instance_fingerprint,
    remaining_reverse_plan_fingerprint,
    claim_sequence,
):
    try:
        ports = _fixed_execution_confirmation_ports()
        prepared_at_epoch = ports.clock.wall_epoch()
        prepared_monotonic_ns = ports.clock.monotonic_ns()
        if (
            type(prepared_at_epoch) is not int
            or prepared_at_epoch < 0
            or type(prepared_monotonic_ns) is not int
            or prepared_monotonic_ns < 0
        ):
            raise ExecutionConfirmationError()
        body = build_candidate_body(**locals())
        runtime = _CandidateRuntime(
            ports.clock,
            ports.console,
            prepared_monotonic_ns,
            _LiveState("PREPARED"),
        )
        return _construct_candidate(body, binding, runtime)
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None

def confirm_execution_confirmation_v1(
    *,
    candidate,
):
    try:
        runtime = _begin_confirmation(candidate)
        before = runtime.console.snapshot()
        runtime.console.display_confirmation(
            candidate.candidate_fingerprint,
            CONFIRMATION_ACKNOWLEDGEMENT,
        )
        observed_candidate_fingerprint = (
            runtime.console.read_candidate_fingerprint()
        )
        observed_acknowledgement = runtime.console.read_acknowledgement()
        runtime.console.require_no_pending_input()
        confirmed_at_epoch = runtime.clock.wall_epoch()
        confirmed_monotonic_ns = runtime.clock.monotonic_ns()
        after = runtime.console.snapshot()
        _require_confirmation_observation(
            candidate,
            runtime,
            observed_candidate_fingerprint,
            observed_acknowledgement,
            confirmed_at_epoch,
            confirmed_monotonic_ns,
            before,
            after,
            CONFIRMATION_ACKNOWLEDGEMENT,
        )
        intact = _candidate_from_value(candidate)
        body = build_claim_body(
            contract_body(intact, CANDIDATE_FIELDS),
            confirmed_at_epoch,
        )
        expires_monotonic_ns = runtime.prepared_monotonic_ns + (
            candidate.confirmation_window_seconds * 1_000_000_000
        )
        return _construct_claim(
            body,
            confirmed_monotonic_ns,
            expires_monotonic_ns,
            _LiveState("CONFIRMED"),
        )
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None


def _begin_confirmation(candidate):
    if (
        type(candidate) is not ExecutionConfirmationCandidateV1
        or type(candidate._runtime) is not _CandidateRuntime
    ):
        raise ExecutionConfirmationError()
    candidate._runtime.state.transition("PREPARED", "CONFIRMING")
    return candidate._runtime


def candidate_fingerprint_for_claim(binding, claim):
    try:
        if type(claim) is not ExecutionConfirmationClaimV1:
            raise ExecutionConfirmationError()
        body = candidate_body_from_claim(binding, claim.to_mapping())
        return candidate_fingerprint(body)
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None


def _candidate_from_value(value):
    try:
        intact = ExecutionConfirmationCandidateV1.from_json(
            value.to_canonical_json(),
            binding=value._binding,
        )
    except Exception:
        raise ExecutionConfirmationError()
    if intact != value:
        raise ExecutionConfirmationError()
    return intact


def _construct_candidate(body, binding, runtime):
    value = allocate_contract(
        ExecutionConfirmationCandidateV1,
        body,
        CANDIDATE_FIELDS,
    )
    object.__setattr__(value, "candidate_fingerprint", candidate_fingerprint(body))
    object.__setattr__(value, "_binding", binding)
    object.__setattr__(value, "_runtime", runtime)
    return value


def _construct_claim(body, confirmed_monotonic, expires_monotonic, state):
    value = allocate_contract(ExecutionConfirmationClaimV1, body, CLAIM_FIELDS)
    object.__setattr__(value, "claim_fingerprint", claim_fingerprint(body))
    object.__setattr__(value, "_confirmed_monotonic_ns", confirmed_monotonic)
    object.__setattr__(value, "_expires_monotonic_ns", expires_monotonic)
    object.__setattr__(value, "_attempt_state", state)
    return value
