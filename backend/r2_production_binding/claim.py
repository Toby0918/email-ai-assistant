"""Durable single-use authority claim reconstructed from journal facts."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_json_object
from ._claim_body import build_claim_body
from .binding import ApprovedCutoverBindingV2
from .errors import AuthorityClaimError
from .vocabulary import (
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    PublicKeyRoleV2,
)


_BODY_FIELDS = (
    "claim_type",
    "binding_fingerprint",
    "final_master_binding_fingerprint",
    "production_role_registry_fingerprint",
    "public_key_registry_fingerprint",
    "command",
    "domain",
    "operator_role",
    "public_key_role",
    "action_fingerprint",
    "authority_fingerprint",
    "envelope_nonce",
    "journal_owner_fingerprint",
    "prior_journal_head_fingerprint",
    "claim_sequence",
    "issued_at_epoch",
    "not_before_epoch",
    "expires_at_epoch",
    "claimed_at_epoch",
    "single_use",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class DurableAuthorityClaimV2:
    claim_type: str = field(repr=False)
    binding_fingerprint: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    production_role_registry_fingerprint: str = field(repr=False)
    public_key_registry_fingerprint: str = field(repr=False)
    command: ProductionCommandV2
    domain: AuthorityDomainV2
    operator_role: OperatorRoleV2
    public_key_role: PublicKeyRoleV2
    action_fingerprint: str = field(repr=False)
    authority_fingerprint: str = field(repr=False)
    envelope_nonce: str = field(repr=False)
    journal_owner_fingerprint: str = field(repr=False)
    prior_journal_head_fingerprint: str = field(repr=False)
    claim_sequence: int
    issued_at_epoch: int = field(repr=False)
    not_before_epoch: int = field(repr=False)
    expires_at_epoch: int = field(repr=False)
    claimed_at_epoch: int = field(repr=False)
    single_use: int
    claim_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("DurableAuthorityClaimV2 requires create()")

    @classmethod
    def create(
        cls,
        *,
        binding: object,
        command: object,
        action_fingerprint: object,
        authority_fingerprint: object,
        envelope_nonce: object,
        journal_owner_fingerprint: object,
        prior_journal_head_fingerprint: object,
        claim_sequence: object,
        issued_at_epoch: object,
        not_before_epoch: object,
        expires_at_epoch: object,
        claimed_at_epoch: object,
    ) -> DurableAuthorityClaimV2:
        body = build_claim_body(
            binding=binding,
            command=command,
            action_fingerprint=action_fingerprint,
            authority_fingerprint=authority_fingerprint,
            envelope_nonce=envelope_nonce,
            journal_owner_fingerprint=journal_owner_fingerprint,
            prior_journal_head_fingerprint=prior_journal_head_fingerprint,
            claim_sequence=claim_sequence,
            issued_at_epoch=issued_at_epoch,
            not_before_epoch=not_before_epoch,
            expires_at_epoch=expires_at_epoch,
            claimed_at_epoch=claimed_at_epoch,
        )
        return _construct(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        binding: object,
    ) -> DurableAuthorityClaimV2:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise AuthorityClaimError()
            if set(source) != {*_BODY_FIELDS, "claim_fingerprint"}:
                raise AuthorityClaimError()
            body = build_claim_body(
                binding=binding,
                command=ProductionCommandV2(source["command"]),
                action_fingerprint=source["action_fingerprint"],
                authority_fingerprint=source["authority_fingerprint"],
                envelope_nonce=source["envelope_nonce"],
                journal_owner_fingerprint=source["journal_owner_fingerprint"],
                prior_journal_head_fingerprint=source[
                    "prior_journal_head_fingerprint"
                ],
                claim_sequence=source["claim_sequence"],
                issued_at_epoch=source["issued_at_epoch"],
                not_before_epoch=source["not_before_epoch"],
                expires_at_epoch=source["expires_at_epoch"],
                claimed_at_epoch=source["claimed_at_epoch"],
            )
            if any(source[name] != body[name] for name in _BODY_FIELDS):
                raise AuthorityClaimError()
            expected = fingerprint("r2-durable-authority-claim-v2", body)
            if source["claim_fingerprint"] != expected:
                raise AuthorityClaimError()
            return _construct(body)
        except AuthorityClaimError:
            raise
        except Exception:
            raise AuthorityClaimError() from None

    def to_mapping(self) -> dict[str, object]:
        body = {name: getattr(self, name) for name in _BODY_FIELDS}
        for name in ("command", "domain", "operator_role", "public_key_role"):
            body[name] = body[name].value
        return {**body, "claim_fingerprint": self.claim_fingerprint}

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def validate_new_authority_claim(
    *,
    binding: object,
    candidate: object,
    durable_claims: object,
    observed_at_epoch: object,
    expected_prior_journal_head_fingerprint: object,
) -> DurableAuthorityClaimV2:
    try:
        _require_new_claim(
            binding,
            candidate,
            durable_claims,
            observed_at_epoch,
            expected_prior_journal_head_fingerprint,
        )
        return candidate
    except AuthorityClaimError:
        raise
    except Exception:
        raise AuthorityClaimError() from None


def _require_new_claim(binding, candidate, durable_claims, observed, expected_head):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(candidate) is not DurableAuthorityClaimV2
        or type(durable_claims) is not tuple
        or type(observed) is not int
        or observed != candidate.claimed_at_epoch
        or not is_fingerprint(expected_head)
        or candidate.prior_journal_head_fingerprint != expected_head
        or candidate.claim_sequence != len(durable_claims) + 1
    ):
        raise AuthorityClaimError()
    _require_intact(candidate, binding)
    prior = []
    for index, claim in enumerate(durable_claims, start=1):
        if (
            type(claim) is not DurableAuthorityClaimV2
            or claim.binding_fingerprint != candidate.binding_fingerprint
            or claim.claim_sequence != index
        ):
            raise AuthorityClaimError()
        _require_intact(claim, binding)
        prior.append(claim)
    if (
        candidate.authority_fingerprint
        in {claim.authority_fingerprint for claim in prior}
        or candidate.envelope_nonce in {claim.envelope_nonce for claim in prior}
        or len({claim.claim_fingerprint for claim in prior}) != len(prior)
    ):
        raise AuthorityClaimError()


def _require_intact(claim, binding) -> None:
    if (
        claim.binding_fingerprint != binding.binding_fingerprint
        or DurableAuthorityClaimV2.from_json(
            claim.to_canonical_json(), binding=binding
        )
        != claim
    ):
        raise AuthorityClaimError()


def _construct(body: dict[str, object]) -> DurableAuthorityClaimV2:
    value = object.__new__(DurableAuthorityClaimV2)
    enum_fields = {
        "command": ProductionCommandV2,
        "domain": AuthorityDomainV2,
        "operator_role": OperatorRoleV2,
        "public_key_role": PublicKeyRoleV2,
    }
    for name in _BODY_FIELDS:
        item = enum_fields[name](body[name]) if name in enum_fields else body[name]
        object.__setattr__(value, name, item)
    object.__setattr__(
        value,
        "claim_fingerprint",
        fingerprint("r2-durable-authority-claim-v2", body),
    )
    return value
