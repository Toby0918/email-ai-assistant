"""Complete content-free Issue #59 receipt-chain contracts."""

from __future__ import annotations

import hashlib
import json
import unittest

from backend.cutover_composition_contracts import (
    AuthorizationSequenceV1,
    CompositionBindingV1,
    CompositionContractError,
    CompositionStage,
    CompositionStageReceiptV1,
    ProjectContainerReceiptChainV1,
    ReceiptChainState,
    UNBOUND_FINGERPRINT,
)
from backend.cutover_contracts import (
    CutoverExecutionAuthorizationV1,
    CutoverProfileV1,
    EvidencePublicationAuthorizationV1,
    RealPreflightAuthorizationV1,
    RecoveryAuthorizationV1,
)
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)


OBSERVED_AT = 1_900_000_000
OPERATION = opaque_fingerprint(9101)
JOURNAL_OWNER = opaque_fingerprint(9102)

SUCCESS_STAGES = (
    CompositionStage.CURRENT_TOPOLOGY,
    CompositionStage.HOST_BASELINE,
    CompositionStage.EVIDENCE_REVIEW,
    CompositionStage.EVIDENCE_PUBLICATION,
    CompositionStage.EVIDENCE_VERIFICATION,
    CompositionStage.FINAL_AUDIT_READINESS,
    CompositionStage.ACL_BASELINE,
    CompositionStage.PRE_MUTATION_GATE,
    CompositionStage.ACL_PUBLICATION,
    CompositionStage.REPOSITORY_TRANSACTION,
    CompositionStage.RUNTIME_PUBLICATION,
    CompositionStage.DATABASE_PUBLICATION,
    CompositionStage.ARTIFACT_PUBLICATION,
    CompositionStage.CONFIG_PUBLICATION,
    CompositionStage.ACTIVATION,
    CompositionStage.FINAL_AUDIT,
    CompositionStage.CUTOVER_SUCCESS,
)
RECOVERY_STAGES = (
    *SUCCESS_STAGES[:-2],
    CompositionStage.RECOVERY_INSPECTION,
    CompositionStage.FAILED_CONTAINER_PRESERVATION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
)
POST_AUDIT_RECOVERY_STAGES = (
    *SUCCESS_STAGES[:-1],
    CompositionStage.RECOVERY_INSPECTION,
    CompositionStage.FAILED_CONTAINER_PRESERVATION,
    CompositionStage.ROLLBACK_RESTORATION,
    CompositionStage.LEGACY_HEALTH,
)


class CutoverCompositionReceiptChainTests(unittest.TestCase):
    def setUp(self) -> None:
        body = valid_profile_body()
        body["governing_master_commit"] = (
            "4dd5183c7cb2731f519b0516516d9c0eb4490804"
        )
        self.profile = CutoverProfileV1.create(body)
        self.sequence = AuthorizationSequenceV1.create(
            profile=self.profile,
            operation_fingerprint=OPERATION,
            authorizations=_authorization_sequence(self.profile),
            observed_at_epoch=OBSERVED_AT,
        )
        self.binding = CompositionBindingV1.create(
            profile=self.profile,
            operation_fingerprint=OPERATION,
            authorization_sequence=self.sequence,
        )

    def test_complete_success_chain_binds_every_required_receipt(self) -> None:
        receipts = _receipt_sequence(self.binding, SUCCESS_STAGES)

        chain = ProjectContainerReceiptChainV1.create(
            receipts=receipts,
            observed_at_epoch=OBSERVED_AT,
        )

        self.assertIs(chain.state, ReceiptChainState.CUTOVER_SUCCEEDED)
        self.assertEqual(chain.receipt_count, len(SUCCESS_STAGES))
        self.assertEqual(
            chain.authorization_sequence_fingerprint,
            self.sequence.sequence_fingerprint,
        )
        self.assertEqual(
            chain.review_fingerprint,
            receipts[2].observation_fingerprint,
        )
        self.assertEqual(
            chain.package_verification_fingerprint,
            receipts[4].observation_fingerprint,
        )
        self.assertEqual(
            chain.acl_baseline_fingerprint,
            receipts[6].observation_fingerprint,
        )
        self.assertEqual(
            chain.pre_mutation_fingerprint,
            receipts[7].receipt_fingerprint,
        )
        self.assertEqual(chain.journal_owner_fingerprint, JOURNAL_OWNER)
        self.assertEqual(
            chain.journal_head_fingerprint,
            receipts[-1].journal_head_fingerprint,
        )
        self.assertEqual(
            chain.activation_fingerprint,
            receipts[14].observation_fingerprint,
        )
        self.assertEqual(
            chain.final_audit_fingerprint,
            receipts[15].observation_fingerprint,
        )
        self.assertEqual(
            chain.recovery_state_fingerprint,
            receipts[-1].observation_fingerprint,
        )

    def test_complete_recovery_chain_binds_failed_state_and_legacy_health(
        self,
    ) -> None:
        receipts = _receipt_sequence(self.binding, RECOVERY_STAGES)

        chain = ProjectContainerReceiptChainV1.create(
            receipts=receipts,
            observed_at_epoch=OBSERVED_AT,
        )

        self.assertIs(chain.state, ReceiptChainState.LEGACY_RECOVERED)
        self.assertEqual(
            chain.activation_fingerprint,
            receipts[14].observation_fingerprint,
        )
        self.assertEqual(
            chain.final_audit_fingerprint,
            UNBOUND_FINGERPRINT,
        )
        self.assertEqual(
            chain.recovery_state_fingerprint,
            receipts[-1].observation_fingerprint,
        )
        self.assertEqual(receipts[-2].worktrees, 11)

    def test_failed_final_audit_can_enter_the_exact_recovery_chain(self) -> None:
        receipts = _receipt_sequence(
            self.binding,
            POST_AUDIT_RECOVERY_STAGES,
        )

        chain = ProjectContainerReceiptChainV1.create(
            receipts=receipts,
            observed_at_epoch=OBSERVED_AT,
        )

        self.assertIs(chain.state, ReceiptChainState.LEGACY_RECOVERED)
        self.assertEqual(
            chain.final_audit_fingerprint,
            receipts[15].observation_fingerprint,
        )

    def test_order_prior_binding_and_freshness_drift_fail_closed(self) -> None:
        receipts = list(_receipt_sequence(self.binding, SUCCESS_STAGES))
        cases: list[tuple[str, tuple[CompositionStageReceiptV1, ...]]] = []
        cases.append(("order", tuple(receipts[:3] + receipts[4:])))
        cases.append(
            (
                "prior",
                tuple(
                    receipts[:4]
                    + [
                        _receipt(
                            self.binding,
                            CompositionStage.EVIDENCE_VERIFICATION,
                            prior=opaque_fingerprint(9991),
                            prior_journal_head=UNBOUND_FINGERPRINT,
                            index=4,
                        )
                    ]
                    + receipts[5:]
                ),
            )
        )
        alternate = _alternate_binding()
        cases.append(
            (
                "binding",
                tuple(
                    receipts[:5]
                    + [
                        _receipt(
                            alternate,
                            CompositionStage.FINAL_AUDIT_READINESS,
                            prior=receipts[4].receipt_fingerprint,
                            prior_journal_head=UNBOUND_FINGERPRINT,
                            index=5,
                        )
                    ]
                    + receipts[6:]
                ),
            )
        )
        stale = _receipt_sequence(
            self.binding,
            SUCCESS_STAGES,
            gate_expiry=OBSERVED_AT,
        )
        cases.append(("freshness", stale))

        for name, candidate in cases:
            with self.subTest(case=name), self.assertRaisesRegex(
                CompositionContractError,
                "^PROJECT_CONTAINER_RECEIPT_CHAIN_INVALID$",
            ):
                ProjectContainerReceiptChainV1.create(
                    receipts=candidate,
                    observed_at_epoch=OBSERVED_AT,
                )

    def test_in_progress_chain_must_start_at_current_topology(self) -> None:
        activation = _receipt(
            self.binding,
            CompositionStage.ACTIVATION,
            prior=UNBOUND_FINGERPRINT,
            prior_journal_head=UNBOUND_FINGERPRINT,
            index=1,
            journal_bound=True,
        )

        with self.assertRaisesRegex(
            CompositionContractError,
            "^PROJECT_CONTAINER_RECEIPT_CHAIN_INVALID$",
        ):
            ProjectContainerReceiptChainV1.create(
                receipts=(activation,),
                observed_at_epoch=OBSERVED_AT,
            )

    def test_chain_fingerprint_commits_every_linked_receipt_and_head(
        self,
    ) -> None:
        original_receipts = _receipt_sequence(
            self.binding,
            RECOVERY_STAGES,
        )
        changed_receipts = _receipt_sequence(
            self.binding,
            RECOVERY_STAGES,
            observation_overrides={
                CompositionStage.FAILED_CONTAINER_PRESERVATION: (
                    opaque_fingerprint(9992)
                )
            },
        )

        original = ProjectContainerReceiptChainV1.create(
            receipts=original_receipts,
            observed_at_epoch=OBSERVED_AT,
        )
        changed = ProjectContainerReceiptChainV1.create(
            receipts=changed_receipts,
            observed_at_epoch=OBSERVED_AT,
        )

        self.assertNotEqual(
            original.terminal_receipt_fingerprint,
            changed.terminal_receipt_fingerprint,
        )
        self.assertNotEqual(
            original.chain_fingerprint,
            changed.chain_fingerprint,
        )

        broken = list(original_receipts)
        broken[-1] = _receipt(
            self.binding,
            CompositionStage.LEGACY_HEALTH,
            prior=broken[-2].receipt_fingerprint,
            prior_journal_head=UNBOUND_FINGERPRINT,
            index=len(broken) - 1,
            journal_bound=True,
        )
        with self.assertRaisesRegex(
            CompositionContractError,
            "^PROJECT_CONTAINER_RECEIPT_CHAIN_INVALID$",
        ):
            ProjectContainerReceiptChainV1.create(
                receipts=tuple(broken),
                observed_at_epoch=OBSERVED_AT,
            )

    def test_receipts_and_chain_are_content_free_closed_values(self) -> None:
        chain = ProjectContainerReceiptChainV1.create(
            receipts=_receipt_sequence(self.binding, SUCCESS_STAGES),
            observed_at_epoch=OBSERVED_AT,
        )
        public = json.dumps(chain.to_mapping(), sort_keys=True)
        for forbidden in (
            self.profile.governing_master_commit,
            "D:\\",
            "S-1-",
            "O:BAG:",
            "refs/heads",
            "worktree_01",
            "git ",
            "PowerShell",
            "credential",
            "mailbox",
            "provider payload",
            "vault",
            "database row",
            "Traceback",
        ):
            self.assertNotIn(forbidden, public)
        self.assertNotIn(OPERATION, repr(chain))
        with self.assertRaises(TypeError):
            CompositionStageReceiptV1.create(
                binding=self.binding,
                stage=CompositionStage.CURRENT_TOPOLOGY,
                prior_receipt_fingerprint=UNBOUND_FINGERPRINT,
                observation_fingerprint=opaque_fingerprint(1),
                journal_owner_fingerprint=UNBOUND_FINGERPRINT,
                prior_journal_head_fingerprint=UNBOUND_FINGERPRINT,
                journal_head_fingerprint=UNBOUND_FINGERPRINT,
                valid_until_epoch=0,
                accepted=1,
                rejected=0,
                worktrees=0,
                provider_attempts=0,
                dynamic_field="forbidden",
            )


def _receipt_sequence(
    binding: CompositionBindingV1,
    stages: tuple[CompositionStage, ...],
    *,
    gate_expiry: int = OBSERVED_AT + 60,
    observation_overrides: dict[CompositionStage, str] | None = None,
) -> tuple[CompositionStageReceiptV1, ...]:
    receipts: list[CompositionStageReceiptV1] = []
    prior = UNBOUND_FINGERPRINT
    prior_journal_head = UNBOUND_FINGERPRINT
    journal_bound = False
    overrides = observation_overrides or {}
    for index, stage in enumerate(stages):
        if stage is CompositionStage.ACL_PUBLICATION:
            journal_bound = True
        receipt = _receipt(
            binding,
            stage,
            prior=prior,
            prior_journal_head=prior_journal_head,
            index=index,
            journal_bound=journal_bound,
            gate_expiry=gate_expiry,
            observation_fingerprint=overrides.get(stage),
        )
        receipts.append(receipt)
        prior = receipt.receipt_fingerprint
        if journal_bound:
            prior_journal_head = receipt.journal_head_fingerprint
    return tuple(receipts)


def _receipt(
    binding: CompositionBindingV1,
    stage: CompositionStage,
    *,
    prior: str,
    prior_journal_head: str,
    index: int,
    journal_bound: bool | None = None,
    gate_expiry: int = OBSERVED_AT + 60,
    observation_fingerprint: str | None = None,
) -> CompositionStageReceiptV1:
    if journal_bound is None:
        journal_bound = stage.value in {
            item.value for item in SUCCESS_STAGES[8:]
        } | {
            CompositionStage.RECOVERY_INSPECTION.value,
            CompositionStage.FAILED_CONTAINER_PRESERVATION.value,
            CompositionStage.ROLLBACK_RESTORATION.value,
            CompositionStage.LEGACY_HEALTH.value,
        }
    return CompositionStageReceiptV1.create(
        binding=binding,
        stage=stage,
        prior_receipt_fingerprint=prior,
        observation_fingerprint=(
            observation_fingerprint or opaque_fingerprint(9200 + index)
        ),
        journal_owner_fingerprint=(
            JOURNAL_OWNER if journal_bound else UNBOUND_FINGERPRINT
        ),
        prior_journal_head_fingerprint=(
            prior_journal_head if journal_bound else UNBOUND_FINGERPRINT
        ),
        journal_head_fingerprint=(
            opaque_fingerprint(9300 + index)
            if journal_bound
            else UNBOUND_FINGERPRINT
        ),
        valid_until_epoch=(
            gate_expiry
            if stage is CompositionStage.PRE_MUTATION_GATE
            else 0
        ),
        accepted=1,
        rejected=0,
        worktrees=(
            11
            if stage
            in {
                CompositionStage.REPOSITORY_TRANSACTION,
                CompositionStage.ROLLBACK_RESTORATION,
                CompositionStage.LEGACY_HEALTH,
            }
            else 0
        ),
        provider_attempts=0,
    )


def _authorization_sequence(profile):
    phases = (
        (RealPreflightAuthorizationV1, "real_preflight", "current_topology_preflight"),
        (RealPreflightAuthorizationV1, "real_preflight", "host_baseline"),
        (RealPreflightAuthorizationV1, "real_preflight", "evidence_review"),
        (EvidencePublicationAuthorizationV1, "evidence_publication", "evidence_publication"),
        (RealPreflightAuthorizationV1, "real_preflight", "evidence_verification"),
        (RealPreflightAuthorizationV1, "real_preflight", "final_audit_readiness"),
        (RealPreflightAuthorizationV1, "real_preflight", "recovery_inspection"),
        (CutoverExecutionAuthorizationV1, "cutover_execution", "execute"),
        (CutoverExecutionAuthorizationV1, "cutover_execution", "resume"),
        (RecoveryAuthorizationV1, "recovery", "rollback"),
        (RecoveryAuthorizationV1, "recovery", "legacy_recovery"),
    )
    return tuple(
        _authorization(kind, profile, operation, phase, index)
        for index, (kind, operation, phase) in enumerate(phases)
    )


def _authorization(kind, profile, operation, phase, index):
    body = {
        "authorization_type": kind.AUTHORIZATION_TYPE,
        "operation": operation,
        "operation_fingerprint": OPERATION,
        "profile_fingerprint": profile.profile_fingerprint,
        "governing_master_commit": profile.governing_master_commit,
        "operator_fingerprint": profile.operator_fingerprint,
        "phase": phase,
        "issued_at_epoch": OBSERVED_AT - 30 + index,
        "not_before_epoch": OBSERVED_AT - 10,
        "expires_at_epoch": OBSERVED_AT + 300,
    }
    payload = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return kind.from_mapping(
        {
            **body,
            "authorization_fingerprint": hashlib.sha256(payload).hexdigest(),
        }
    )


def _alternate_binding() -> CompositionBindingV1:
    body = valid_profile_body()
    body["governing_master_commit"] = "f" * 40
    profile = CutoverProfileV1.create(body)
    sequence = AuthorizationSequenceV1.create(
        profile=profile,
        operation_fingerprint=OPERATION,
        authorizations=_authorization_sequence(profile),
        observed_at_epoch=OBSERVED_AT,
    )
    return CompositionBindingV1.create(
        profile=profile,
        operation_fingerprint=OPERATION,
        authorization_sequence=sequence,
    )


if __name__ == "__main__":
    unittest.main()
