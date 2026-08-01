"""Synthetic durable journal and host observations for Issue #82."""

from __future__ import annotations

from backend.r2_cross_stage_recovery import (
    CrossStageAdaptersV1,
    EffectObservation,
    PendingIntentV1,
    ReceiptPredecessorLinkV1,
    RecoveryBoundary,
    ReverseBoundaryAuthorityV1,
    ReverseEffectEvidenceV1,
    RestartSnapshotV1,
)
from tests.cutover_contract_fixtures import opaque_fingerprint


NOW = 1_900_000_000
HEAD = opaque_fingerprint(8200)
IDENTITIES = opaque_fingerprint(8201)
NONCE_A = "11111111-1111-4111-8111-111111111111"
NONCE_B = "22222222-2222-4222-8222-222222222222"
BOUNDARIES = tuple(RecoveryBoundary)


def snapshot(*, pending=None, remaining=BOUNDARIES, links=None, preserved=False):
    if links is None:
        links = (
            ReceiptPredecessorLinkV1(
                receipt_fingerprint=opaque_fingerprint(8210),
                predecessor_fingerprint=opaque_fingerprint(8211),
                prior_head_fingerprint=opaque_fingerprint(8212),
                journal_head_fingerprint=HEAD,
            ),
        )
    if pending is None:
        pending = tuple(
            PendingIntentV1.create(
                direction="committed",
                boundary=boundary,
                intent_fingerprint=opaque_fingerprint(8280 + index),
            )
            for index, boundary in enumerate(remaining)
        )
    return RestartSnapshotV1.create(
        current_journal_head=HEAD,
        receipt_links=links,
        pending_intents=tuple(pending),
        remaining_reverse_plan=tuple(remaining),
        failed_container_preserved=preserved,
        retained_new_object_count=17,
        approved_identities_fingerprint=IDENTITIES,
    )


class RecoveryAdapters:
    def __init__(self) -> None:
        self.head = HEAD
        self.calls = []
        self.observations = {}
        self.authorities = []
        self.nonce_index = 0
        self.mutations = 0
        self.freshness_reads = 0
        self.success_appends = 0

    def bundle(self):
        return CrossStageAdaptersV1(
            observe_intent=self.observe,
            current_journal_head=self.current_head,
            reverse_boundary=self.reverse,
            minimal_final_freshness=self.freshness,
            append_cutover_success=self.append_success,
        )

    def observe(self, intent):
        self.calls.append(f"observe:{intent.boundary.value}")
        return self.observations.get(
            intent.intent_fingerprint, EffectObservation.PRESENT
        )

    def current_head(self):
        self.calls.append("head")
        return self.head

    def authority(self, boundary, head, plan):
        self.nonce_index += 1
        value = ReverseBoundaryAuthorityV1.create(
            boundary=boundary,
            journal_head_fingerprint=head,
            remaining_plan_fingerprint=plan,
            crash_nonce=opaque_fingerprint(8250 + self.nonce_index),
            issued_at_epoch=NOW - 1,
            expires_at_epoch=NOW + 60,
        )
        self.authorities.append(value)
        return value

    def reverse(self, boundary, authority):
        self.calls.append(f"reverse:{boundary.value}")
        self.mutations += 1
        prior = self.head
        self.head = opaque_fingerprint(8260 + self.mutations)
        return ReverseEffectEvidenceV1.create(
            boundary=boundary,
            prior_head_fingerprint=prior,
            journal_head_fingerprint=self.head,
            effect_fingerprint=opaque_fingerprint(8270 + self.mutations),
            retained_new_objects=17,
            cleanup_operations=0,
        )

    def freshness(self):
        raise AssertionError("set a final freshness callback in seal tests")

    def append_success(self, *args):
        raise AssertionError("set a success callback in seal tests")
