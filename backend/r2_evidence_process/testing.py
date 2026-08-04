"""Synthetic-only binder for the evidence publication process."""

from __future__ import annotations

from backend.cutover_composition_contracts import ApprovedCutoverBindingV1
from backend.cutover_composition_contracts.canonical import (
    fingerprint,
    is_fingerprint,
)
from backend.cutover_contracts import CutoverProfileV1

from .contracts import (
    EvidenceProcessStatus,
    result,
)
from .entry import run_authorization_gate
from .production_v2 import (
    EvidenceProductionStatusV2,
    run_evidence_production_v2,
)
from backend.r2_production_binding import ApprovedCutoverBindingV2, ProductionCommandV2
from backend.r2_production_composition import (
    EvidenceAdapterOutcomeV1,
    ProductionAdapterSlotV1,
)
from backend.r2_production_composition.adapter_binding import (
    _synthetic_bound_adapter_v1,
)
from backend.r2_transaction_journal_v2 import R2JournalGenesisV2


class SyntheticEvidenceProcess:
    __slots__ = (
        "_binding",
        "_claimed",
        "_confirmed_review",
        "_expected_review",
        "_key",
        "_locked",
        "_now",
        "_operation",
        "_profile",
        "_publish",
        "_publication_attempted",
        "_published",
        "publication_acquisitions",
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticEvidenceProcess requires create()")

    @classmethod
    def create(cls, **values) -> SyntheticEvidenceProcess:
        _require_context(values)
        process = object.__new__(cls)
        process._profile = values["profile"]
        process._binding = values["binding"]
        process._operation = values["operation_fingerprint"]
        process._confirmed_review = values["confirmed_review_fingerprint"]
        process._expected_review = values["expected_review_fingerprint"]
        process._key = values["verification_public_key"]
        process._now = values["observed_at_epoch"]
        process._publish = values["publish_confirmed_review"]
        process._locked = values["real_locked"]
        process._claimed = set()
        process._publication_attempted = False
        process._published = False
        process.publication_acquisitions = 0
        return process

    def run(self, *, argv: object, terminal: object):
        authorized = run_authorization_gate(
            argv=argv,
            terminal=terminal,
            profile=self._profile,
            operation_fingerprint=self._operation,
            verification_public_key=self._key,
            observed_at_epoch=self._now,
            claim_nonce=self._claim_nonce,
        )
        if authorized.status is not EvidenceProcessStatus.BLOCKED_NO_APPROVED_COMMAND:
            return authorized
        if self._confirmed_review != self._expected_review:
            return result(EvidenceProcessStatus.BLOCKED_AUTHORIZATION)
        if self._locked:
            return authorized
        return self._publish_once()

    def _publish_once(self):
        if self._publication_attempted:
            return result(EvidenceProcessStatus.BLOCKED_PUBLICATION)
        self._publication_attempted = True
        self.publication_acquisitions += 1
        try:
            published = self._publish()
        except Exception:
            return result(EvidenceProcessStatus.BLOCKED_PUBLICATION)
        if published != 1:
            return result(EvidenceProcessStatus.BLOCKED_PUBLICATION)
        self._published = True
        return result(EvidenceProcessStatus.PUBLISHED)

    def _claim_nonce(self, nonce: str) -> bool:
        if nonce in self._claimed:
            return False
        self._claimed.add(nonce)
        return True


def _require_context(values) -> None:
    expected = {
        "profile",
        "binding",
        "operation_fingerprint",
        "confirmed_review_fingerprint",
        "expected_review_fingerprint",
        "verification_public_key",
        "observed_at_epoch",
        "publish_confirmed_review",
        "real_locked",
    }
    if type(values) is not dict or set(values) != expected:
        raise ValueError("R2_EVIDENCE_SYNTHETIC_BINDING_INVALID")
    profile = values["profile"]
    binding = values["binding"]
    if (
        type(profile) is not CutoverProfileV1
        or type(binding) is not ApprovedCutoverBindingV1
    ):
        raise ValueError("R2_EVIDENCE_SYNTHETIC_BINDING_INVALID")
    master = fingerprint(
        "project-container-governing-master-v1",
        profile.governing_master_commit,
    )
    if (
        binding.profile_fingerprint != profile.profile_fingerprint
        or binding.governing_master_fingerprint != master
        or binding.operation_fingerprint != values["operation_fingerprint"]
        or not is_fingerprint(values["confirmed_review_fingerprint"])
        or not is_fingerprint(values["expected_review_fingerprint"])
        or type(values["verification_public_key"]) is not bytes
        or len(values["verification_public_key"]) != 32
        or not callable(values["observed_at_epoch"])
        or not callable(values["publish_confirmed_review"])
        or type(values["real_locked"]) is not bool
    ):
        raise ValueError("R2_EVIDENCE_SYNTHETIC_BINDING_INVALID")


class _SyntheticEvidenceAdapterV1:
    __slots__ = ("_owner",)

    def __init__(self, owner):
        self._owner = owner

    def invoke(self, *, binding, claim):
        return self._owner._publish_once(binding, claim)


class SyntheticEvidenceProductionV2:
    __slots__ = (
        "_attempted",
        "_binding",
        "_create",
        "_durable_claims",
        "_evidence",
        "_genesis",
        "_head",
        "_manifest",
        "_nonce",
        "_now",
        "_owner",
        "_package",
        "_review",
        "_adapter",
    )

    def __init__(self, *args, **kwargs):
        raise TypeError("SyntheticEvidenceProductionV2 requires create()")

    @classmethod
    def create(cls, **values):
        _require_v2_context(values)
        process = object.__new__(cls)
        for slot, key in (
            ("_binding", "binding"),
            ("_review", "reviewed_evidence_fingerprint"),
            ("_evidence", "evidence_identity_fingerprint"),
            ("_package", "package_fingerprint"),
            ("_manifest", "manifest_fingerprint"),
            ("_owner", "journal_owner_fingerprint"),
            ("_nonce", "genesis_nonce"),
            ("_head", "pre_genesis_head_fingerprint"),
            ("_now", "observed_at_epoch"),
            ("_create", "create_only_publish"),
            ("_genesis", "reconstructed_genesis"),
        ):
            setattr(process, slot, values[key])
        process._attempted = False
        process._durable_claims = (
            ()
            if process._genesis is None
            else (process._genesis.authority_claim,)
        )
        if process._genesis is not None:
            process._head = process._genesis.head_fingerprint
        process._adapter = _synthetic_bound_adapter_v1(
            ProductionAdapterSlotV1.EVIDENCE,
            _SyntheticEvidenceAdapterV1(process),
            process._binding,
        )
        return process

    @property
    def genesis(self):
        return self._genesis

    def run(self, *, argv, terminal):
        result = run_evidence_production_v2(
            argv=argv,
            terminal=terminal,
            binding=self._binding,
            adapter=self._adapter,
            reviewed_evidence_fingerprint=self._review,
            durable_claims=self._durable_claims,
            expected_prior_journal_head_fingerprint=self._head,
            observed_at_epoch=self._now,
            journal_owner_fingerprint=self._owner,
            genesis_nonce=self._nonce,
        )
        if result.status is EvidenceProductionStatusV2.PUBLISHED:
            self._genesis = result.genesis
            self._durable_claims = (self._genesis.authority_claim,)
            self._head = self._genesis.head_fingerprint
        return result

    def _publish_once(self, binding, claim):
        if self._attempted:
            raise ValueError("R2_EVIDENCE_CREATE_ONLY_ALREADY_ATTEMPTED")
        self._attempted = True
        if self._create() != 1:
            raise ValueError("R2_EVIDENCE_CREATE_ONLY_FAILED")
        if (
            binding is not self._binding
            or claim.command is not ProductionCommandV2.EVIDENCE_PUBLICATION
        ):
            raise ValueError("R2_EVIDENCE_SYNTHETIC_V2_COMMAND_INVALID")
        return EvidenceAdapterOutcomeV1(
            reviewed_evidence_fingerprint=self._review,
            evidence_identity_fingerprint=self._evidence,
            package_fingerprint=self._package,
            manifest_fingerprint=self._manifest,
            provider_attempts=0,
            created=1,
        )


def _require_v2_context(values):
    expected = {
        "binding",
        "reviewed_evidence_fingerprint",
        "evidence_identity_fingerprint",
        "package_fingerprint",
        "manifest_fingerprint",
        "journal_owner_fingerprint",
        "genesis_nonce",
        "pre_genesis_head_fingerprint",
        "observed_at_epoch",
        "create_only_publish",
        "reconstructed_genesis",
    }
    fingerprints = tuple(
        values.get(name)
        for name in expected
        if name.endswith("fingerprint")
    ) if type(values) is dict else ()
    genesis = values.get("reconstructed_genesis") if type(values) is dict else None
    if (
        type(values) is not dict
        or set(values) != expected
        or type(values["binding"]) is not ApprovedCutoverBindingV2
        or not all(is_fingerprint(value) for value in fingerprints)
        or not callable(values["observed_at_epoch"])
        or not callable(values["create_only_publish"])
        or not (genesis is None or type(genesis) is R2JournalGenesisV2)
    ):
        raise ValueError("R2_EVIDENCE_SYNTHETIC_V2_BINDING_INVALID")
