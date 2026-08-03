"""Deterministic object-level projection from plans and one journal."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum

from backend.r2_foundation_publication_v2 import R2FoundationPlanV2
from backend.r2_managed_unit_publication_v2 import R2ManagedUnitPlanV2
from backend.r2_production_binding import ApprovedCutoverBindingV2, ProductionRoleV2
from backend.r2_rollback_recovery_v2 import R2RollbackPlanV2
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2, TerminalStateV2
from backend.r2_transaction_journal_v2._canonical import (
    canonical_json,
    fingerprint,
)
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2
from backend.r2_two_start_validation_v2 import R2TwoStartValidationPlanV2

from .errors import RetentionLedgerError


class RetentionObjectKindV2(str, Enum):
    ORIGINAL_OBJECT = "original_object"
    NEW_OBJECT = "new_object"
    PARTIAL_OBJECT = "partial_object"
    FAILED_CONTAINER = "failed_container"
    EVIDENCE_OBJECT = "evidence_object"
    JOURNAL_ARTIFACT = "journal_artifact"


class RetentionLedgerStageV2(str, Enum):
    FORWARD_COMMITTED = "FORWARD_COMMITTED"
    FORWARD_RECOVERY_REQUIRED = "FORWARD_RECOVERY_REQUIRED"
    ROLLBACK_PENDING = "ROLLBACK_PENDING"
    ROLLBACK_RECOVERY_CLASSIFIED = "ROLLBACK_RECOVERY_CLASSIFIED"
    ROLLBACK_IN_PROGRESS = "ROLLBACK_IN_PROGRESS"
    ROLLBACK_COMPLETE = "ROLLBACK_COMPLETE"
    LEGACY_RESTORED = "LEGACY_RESTORED"


@dataclass(frozen=True, slots=True, repr=False)
class R2RetentionEntryV2:
    kind: RetentionObjectKindV2
    ordinal: int
    owner: ProductionRoleV2
    object_fingerprint: str = field(repr=False)
    source_transition_fingerprint: str = field(repr=False)
    source_record_head_fingerprint: str = field(repr=False)
    retention_basis_fingerprint: str = field(repr=False)
    retention_required: bool
    destructive_capability_count: int
    private_payload_field_count: int
    entry_fingerprint: str = field(repr=False)

    def to_mapping(self):
        return {
            "kind": self.kind.value,
            "ordinal": self.ordinal,
            "owner": self.owner.value,
            "object_fingerprint": self.object_fingerprint,
            "source_transition_fingerprint": self.source_transition_fingerprint,
            "source_record_head_fingerprint": self.source_record_head_fingerprint,
            "retention_basis_fingerprint": self.retention_basis_fingerprint,
            "retention_required": self.retention_required,
            "destructive_capability_count": self.destructive_capability_count,
            "private_payload_field_count": self.private_payload_field_count,
            "entry_fingerprint": self.entry_fingerprint,
        }


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2RetentionLedgerV2:
    ledger_type: str
    binding_fingerprint: str = field(repr=False)
    foundation_plan_fingerprint: str = field(repr=False)
    managed_plan_fingerprint: str = field(repr=False)
    validation_plan_fingerprint: str = field(repr=False)
    rollback_plan_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    stage: RetentionLedgerStageV2
    forward_commit_count: int
    rollback_commit_count: int
    journal_record_count: int
    entry_count: int
    entries: tuple[R2RetentionEntryV2, ...] = field(repr=False)
    _kind_count_items: tuple[tuple[RetentionObjectKindV2, int], ...] = field(repr=False)
    untracked_artifact_count: int
    deletion_capability_count: int
    overwrite_capability_count: int
    prune_capability_count: int
    automatic_expiry_capability_count: int
    private_payload_field_count: int
    ledger_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("R2RetentionLedgerV2 requires project()")

    @property
    def kind_counts(self):
        return dict(self._kind_count_items)

    @classmethod
    def project(cls, **values):
        try:
            required = {"binding", "foundation_plan", "managed_plan", "validation_plan", "rollback_plan", "journal"}
            if set(values) != required:
                raise RetentionLedgerError()
            return _project(**values)
        except RetentionLedgerError:
            raise
        except Exception:
            raise RetentionLedgerError() from None

    @classmethod
    def from_json(cls, payload, **values):
        try:
            source = _strict_ledger_json(payload)
            result = cls.project(**values)
            if canonical_json(source) != payload or source != result.to_mapping():
                raise RetentionLedgerError()
            return result
        except RetentionLedgerError:
            raise
        except Exception:
            raise RetentionLedgerError() from None

    def to_mapping(self):
        body = {
            "ledger_type": self.ledger_type,
            "binding_fingerprint": self.binding_fingerprint,
            "foundation_plan_fingerprint": self.foundation_plan_fingerprint,
            "managed_plan_fingerprint": self.managed_plan_fingerprint,
            "validation_plan_fingerprint": self.validation_plan_fingerprint,
            "rollback_plan_fingerprint": self.rollback_plan_fingerprint,
            "journal_head_fingerprint": self.journal_head_fingerprint,
            "stage": self.stage.value,
            "forward_commit_count": self.forward_commit_count,
            "rollback_commit_count": self.rollback_commit_count,
            "journal_record_count": self.journal_record_count,
            "entry_count": self.entry_count,
            "entries": [item.to_mapping() for item in self.entries],
            "kind_counts": {kind.value: count for kind, count in self._kind_count_items},
            "untracked_artifact_count": self.untracked_artifact_count,
            "deletion_capability_count": self.deletion_capability_count,
            "overwrite_capability_count": self.overwrite_capability_count,
            "prune_capability_count": self.prune_capability_count,
            "automatic_expiry_capability_count": self.automatic_expiry_capability_count,
            "private_payload_field_count": self.private_payload_field_count,
        }
        return {**body, "ledger_fingerprint": self.ledger_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _project(binding, foundation_plan, managed_plan, validation_plan, rollback_plan, journal):
    _require_inputs(binding, foundation_plan, managed_plan, validation_plan, rollback_plan, journal)
    forward = foundation_plan.transitions + managed_plan.transitions + validation_plan.transitions
    base_records = journal.records[:rollback_plan.forward_record_count]
    commits = tuple(record for record in base_records if record.record_type is JournalRecordTypeV2.COMMIT)
    selected = forward[:len(commits)]
    entries = []
    for ordinal, (transition, record) in enumerate(zip(selected, commits)):
        entries.extend(_forward_entries(binding, ordinal, transition, record))
    entries.append(_failed_entry(binding, rollback_plan, len(entries)))
    entries.extend(_evidence_entries(binding, selected, rollback_plan, journal))
    entries.extend(_journal_entries(binding, journal))
    return _construct_ledger(binding, foundation_plan, managed_plan, validation_plan, rollback_plan, journal, tuple(entries), len(commits))


def _require_inputs(binding, foundation, managed, validation, rollback, journal):
    if (
        type(binding) is not ApprovedCutoverBindingV2
        or type(foundation) is not R2FoundationPlanV2
        or type(managed) is not R2ManagedUnitPlanV2
        or type(validation) is not R2TwoStartValidationPlanV2
        or type(rollback) is not R2RollbackPlanV2
        or type(journal) is not R2TransactionJournalV2
        or any(item.binding_fingerprint != binding.binding_fingerprint for item in (foundation, managed, validation, rollback, journal))
        or managed.foundation_plan_fingerprint != foundation.plan_fingerprint
        or validation.managed_plan_fingerprint != managed.plan_fingerprint
        or rollback.completed_prefix_count(journal) > rollback.transition_count
    ):
        raise RetentionLedgerError()


def _forward_entries(binding, ordinal, transition, record):
    definitions = (
        (RetentionObjectKindV2.ORIGINAL_OBJECT, transition.pre_state_fingerprint),
        (RetentionObjectKindV2.NEW_OBJECT, transition.post_state_fingerprint),
        (RetentionObjectKindV2.PARTIAL_OBJECT, fingerprint("r2-partial-retention-object-v2", {"transition": transition.transition_instance_fingerprint, "commit": record.head_fingerprint})),
    )
    return tuple(_entry(binding, kind, ordinal, transition.owner, object_value, transition.transition_instance_fingerprint, record.head_fingerprint) for kind, object_value in definitions)


def _failed_entry(binding, rollback, ordinal):
    transition = rollback.transitions[0]
    return _entry(binding, RetentionObjectKindV2.FAILED_CONTAINER, ordinal, ProductionRoleV2.FAILED_CONTAINER, transition.post_state_fingerprint, transition.transition_instance_fingerprint, transition.source_commit_head_fingerprint)


def _evidence_entries(binding, selected, rollback, journal):
    owners = {item.transition_instance_fingerprint: item.owner for item in selected}
    owners.update({item.transition_instance_fingerprint: item.owner for item in rollback.transitions})
    records = tuple(record for record in journal.records if record.record_type is JournalRecordTypeV2.COMMIT)
    return tuple(_entry(binding, RetentionObjectKindV2.EVIDENCE_OBJECT, ordinal, owners[record.transition_instance_fingerprint], record.head_fingerprint, record.transition_instance_fingerprint, record.head_fingerprint) for ordinal, record in enumerate(records))


def _journal_entries(binding, journal):
    sources = ((journal.genesis.head_fingerprint, binding.binding_fingerprint),) + tuple((record.head_fingerprint, record.transition_instance_fingerprint) for record in journal.records)
    return tuple(_entry(binding, RetentionObjectKindV2.JOURNAL_ARTIFACT, ordinal, ProductionRoleV2.TRANSACTION_JOURNAL, head, transition, head) for ordinal, (head, transition) in enumerate(sources))


def _entry(binding, kind, ordinal, owner, object_value, transition, record_head):
    body = {"kind": kind.value, "ordinal": ordinal, "owner": owner.value, "object_fingerprint": object_value, "source_transition_fingerprint": transition, "source_record_head_fingerprint": record_head, "retention_basis_fingerprint": fingerprint("r2-retention-basis-v2", {"binding": binding.binding_fingerprint, "kind": kind.value, "object": object_value, "source": record_head}), "retention_required": True, "destructive_capability_count": 0, "private_payload_field_count": 0}
    return R2RetentionEntryV2(kind, ordinal, owner, object_value, transition, record_head, body["retention_basis_fingerprint"], True, 0, 0, fingerprint("r2-retention-entry-v2", body))


def _construct_ledger(binding, foundation, managed, validation, rollback, journal, entries, forward_count):
    counts = tuple((kind, sum(item.kind is kind for item in entries)) for kind in RetentionObjectKindV2)
    body = {"ledger_type": "R2RetentionLedgerV2", "binding_fingerprint": binding.binding_fingerprint, "foundation_plan_fingerprint": foundation.plan_fingerprint, "managed_plan_fingerprint": managed.plan_fingerprint, "validation_plan_fingerprint": validation.plan_fingerprint, "rollback_plan_fingerprint": rollback.plan_fingerprint, "journal_head_fingerprint": journal.current_head_fingerprint, "stage": _stage(rollback, journal).value, "forward_commit_count": forward_count, "rollback_commit_count": rollback.completed_prefix_count(journal), "journal_record_count": journal.record_count, "entry_count": len(entries), "entries": [item.to_mapping() for item in entries], "kind_counts": {kind.value: count for kind, count in counts}, "untracked_artifact_count": 0, "deletion_capability_count": 0, "overwrite_capability_count": 0, "prune_capability_count": 0, "automatic_expiry_capability_count": 0, "private_payload_field_count": 0}
    value = object.__new__(R2RetentionLedgerV2)
    for name, item in body.items():
        if name not in {"entries", "kind_counts"}:
            object.__setattr__(value, name, RetentionLedgerStageV2(item) if name == "stage" else item)
    object.__setattr__(value, "entries", entries)
    object.__setattr__(value, "_kind_count_items", counts)
    object.__setattr__(value, "ledger_fingerprint", fingerprint("r2-retention-ledger-v2", body))
    return value


def _stage(rollback, journal):
    tail = journal.records[rollback.forward_record_count:]
    completed = rollback.completed_prefix_count(journal)
    if tail and tail[-1].record_type is JournalRecordTypeV2.TERMINAL_STATE and tail[-1].terminal_state is TerminalStateV2.LEGACY_FLAT_LAYOUT_RESTORED:
        return RetentionLedgerStageV2.LEGACY_RESTORED
    if completed == rollback.transition_count:
        return RetentionLedgerStageV2.ROLLBACK_COMPLETE
    if not tail:
        return RetentionLedgerStageV2.FORWARD_COMMITTED if journal.next_legal_action == "CLAIM_FRESH_AUTHORITY_OR_TERMINAL" else RetentionLedgerStageV2.FORWARD_RECOVERY_REQUIRED
    if tail[-1].record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION:
        return RetentionLedgerStageV2.ROLLBACK_RECOVERY_CLASSIFIED
    return RetentionLedgerStageV2.ROLLBACK_IN_PROGRESS if completed else RetentionLedgerStageV2.ROLLBACK_PENDING


def _strict_ledger_json(payload):
    if type(payload) is not bytes or not 1 <= len(payload) <= 2 * 1024 * 1024:
        raise RetentionLedgerError()
    def pairs_hook(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise RetentionLedgerError()
            value[key] = item
        return value
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda _value: _invalid_json(),
        )
    except RetentionLedgerError:
        raise
    except Exception:
        raise RetentionLedgerError() from None
    if type(value) is not dict:
        raise RetentionLedgerError()
    return value


def _invalid_json():
    raise RetentionLedgerError()
