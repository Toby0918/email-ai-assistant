"""Live append and historical replay checks for confirmation claims."""

from ._canonical import is_fingerprint
from .binding import ApprovedCutoverBindingV3
from .errors import ExecutionConfirmationError
from .execution_confirmation import (
    ExecutionConfirmationClaimV1,
    candidate_fingerprint_for_claim,
)


def validate_new_execution_confirmation_claim(
    *,
    binding,
    candidate,
    durable_claims,
    observed_at_epoch,
    observed_monotonic_ns,
    expected_prior_journal_head_fingerprint,
):
    try:
        _require_live_observation(
            candidate,
            observed_at_epoch,
            observed_monotonic_ns,
        )
        _require_claim_chain(
            binding,
            candidate,
            durable_claims,
            expected_prior_journal_head_fingerprint,
        )
        return candidate
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None


def validate_reconstructed_execution_confirmation_claim(
    *,
    binding,
    candidate,
    durable_claims,
    expected_prior_journal_head_fingerprint,
):
    try:
        _require_claim_chain(
            binding,
            candidate,
            durable_claims,
            expected_prior_journal_head_fingerprint,
        )
        return candidate
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None


def _begin_execution_confirmation_append_v1(claim):
    try:
        if type(claim) is not ExecutionConfirmationClaimV1:
            raise ExecutionConfirmationError()
        claim._attempt_state.transition("CONFIRMED", "APPENDING")
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None


def _complete_execution_confirmation_append_v1(claim, journal):
    try:
        claim._attempt_state.complete_append(claim, journal)
    except Exception:
        raise ExecutionConfirmationError() from None


def _consume_execution_confirmation_attempt_v1(claim):
    try:
        if type(claim) is not ExecutionConfirmationClaimV1:
            raise ExecutionConfirmationError()
        claim._attempt_state.consume_append(claim)
    except ExecutionConfirmationError:
        raise
    except Exception:
        raise ExecutionConfirmationError() from None


def _require_live_observation(claim, observed_wall, observed_monotonic):
    if type(claim) is not ExecutionConfirmationClaimV1:
        raise ExecutionConfirmationError()
    try:
        claim._attempt_state.require({"CONFIRMED", "APPENDING"})
    except Exception:
        raise ExecutionConfirmationError() from None
    if (
        type(observed_wall) is not int
        or observed_wall < claim.confirmed_at_epoch
        or observed_wall >= claim.expires_at_epoch
        or type(observed_monotonic) is not int
        or type(claim._confirmed_monotonic_ns) is not int
        or type(claim._expires_monotonic_ns) is not int
        or observed_monotonic < claim._confirmed_monotonic_ns
        or observed_monotonic >= claim._expires_monotonic_ns
    ):
        raise ExecutionConfirmationError()


def _require_claim_chain(binding, candidate, durable, expected_head):
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(candidate) is not ExecutionConfirmationClaimV1
        or type(durable) is not tuple
        or not is_fingerprint(expected_head)
        or candidate.prior_journal_head_fingerprint != expected_head
        or candidate.claim_sequence != len(durable) + 1
    ):
        raise ExecutionConfirmationError()
    _require_intact(binding, candidate)
    prior = _require_prior_claims(binding, durable)
    candidate_id = candidate_fingerprint_for_claim(binding, candidate)
    if (
        candidate_id in {item[1] for item in prior}
        or candidate.claim_fingerprint
        in {item[0].claim_fingerprint for item in prior}
        or candidate.action_fingerprint
        in {item[0].action_fingerprint for item in prior}
    ):
        raise ExecutionConfirmationError()


def _require_prior_claims(binding, durable):
    values = []
    for sequence, claim in enumerate(durable, start=1):
        if (
            type(claim) is not ExecutionConfirmationClaimV1
            or claim.production_binding_fingerprint != binding.binding_fingerprint
            or claim.claim_sequence != sequence
        ):
            raise ExecutionConfirmationError()
        _require_intact(binding, claim)
        values.append((claim, candidate_fingerprint_for_claim(binding, claim)))
    if len({claim.claim_fingerprint for claim, _identity in values}) != len(values):
        raise ExecutionConfirmationError()
    return values


def _require_intact(binding, claim):
    if (
        claim.production_binding_fingerprint != binding.binding_fingerprint
        or ExecutionConfirmationClaimV1.from_json(
            claim.to_canonical_json(), binding=binding
        )
        != claim
    ):
        raise ExecutionConfirmationError()
