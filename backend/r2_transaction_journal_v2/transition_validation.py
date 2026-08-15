"""Legal adjacent-frame validation for the R2 journal."""

from backend.r2_production_binding import ProductionCommandV2
from backend.r2_production_binding.claim import (
    validate_reconstructed_execution_confirmation_claim,
)

from .errors import JournalV2Error
from .vocabulary import EffectClassificationV2, JournalRecordTypeV2


def validate_record_kind(journal, record, previous):
    validators = {
        JournalRecordTypeV2.AUTHORITY_CLAIM: _authority,
        JournalRecordTypeV2.INTENT: _intent,
        JournalRecordTypeV2.EFFECT_OBSERVATION: _observation,
        JournalRecordTypeV2.COMMIT: _commit,
        JournalRecordTypeV2.RECOVERY_CLASSIFICATION: _observation,
        JournalRecordTypeV2.TERMINAL_STATE: _terminal,
    }
    try:
        validators[record.record_type](journal, record, previous)
    except KeyError:
        raise JournalV2Error() from None


def _authority(journal, record, previous):
    allowed = {
        JournalRecordTypeV2.COMMIT,
        JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
        JournalRecordTypeV2.EFFECT_OBSERVATION,
    }
    if previous is not None and previous.record_type not in allowed:
        raise JournalV2Error()
    if previous is not None and (
        previous.record_type is JournalRecordTypeV2.EFFECT_OBSERVATION
        and previous.effect_classification
        is not EffectClassificationV2.EFFECT_PRESENT_EXACT
        or previous.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION
        and previous.effect_classification is EffectClassificationV2.EFFECT_AMBIGUOUS
    ):
        raise JournalV2Error()
    validate_reconstructed_execution_confirmation_claim(
        binding=journal._binding,
        candidate=record.execution_confirmation_claim,
        durable_claims=journal.execution_confirmation_claims,
        expected_prior_journal_head_fingerprint=journal.current_head_fingerprint,
    )


def _intent(journal, record, previous):
    if (
        previous is None
        or previous.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM
        or record.transition_instance_fingerprint
        != previous.transition_instance_fingerprint
    ):
        raise JournalV2Error()
    if len(journal.records) >= 2:
        classified = journal.records[-2]
        if (
            classified.record_type is JournalRecordTypeV2.RECOVERY_CLASSIFICATION
            and not _valid_intent_after_classification(
                classified, previous, record
            )
        ):
            raise JournalV2Error()


def _observation(_journal, record, previous):
    expected = JournalRecordTypeV2.INTENT
    if (
        previous is None or previous.record_type is not expected
        or record.transition_instance_fingerprint
        != previous.transition_instance_fingerprint
    ):
        raise JournalV2Error()
    exact = record.observed_state_fingerprint
    classification = record.effect_classification
    if (
        classification is EffectClassificationV2.EFFECT_ABSENT_EXACT
        and exact != previous.pre_state_fingerprint
        or classification is EffectClassificationV2.EFFECT_PRESENT_EXACT
        and exact != previous.post_state_fingerprint
        or classification is EffectClassificationV2.EFFECT_PARTIAL_RESUMABLE
        and exact in {previous.pre_state_fingerprint, previous.post_state_fingerprint}
        or classification is EffectClassificationV2.EFFECT_AMBIGUOUS
        and exact in {previous.pre_state_fingerprint, previous.post_state_fingerprint}
    ):
        raise JournalV2Error()


def _commit(journal, record, previous):
    direct = previous is not None and (
        previous.record_type is JournalRecordTypeV2.EFFECT_OBSERVATION
        and previous.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT
        and record.transition_instance_fingerprint == previous.transition_instance_fingerprint
        and record.observed_state_fingerprint == previous.observed_state_fingerprint
        and record.inspection_receipt_fingerprint
        == previous.inspection_receipt_fingerprint
    )
    recovered = False
    if previous is not None and (
        previous.record_type is JournalRecordTypeV2.AUTHORITY_CLAIM
        and len(journal.records) >= 2
    ):
        classified = journal.records[-2]
        recovered = (
            classified.record_type in {
                JournalRecordTypeV2.RECOVERY_CLASSIFICATION,
                JournalRecordTypeV2.EFFECT_OBSERVATION,
            }
            and classified.effect_classification is EffectClassificationV2.EFFECT_PRESENT_EXACT
            and record.transition_instance_fingerprint == classified.transition_instance_fingerprint
            and record.observed_state_fingerprint == classified.observed_state_fingerprint
            and record.inspection_receipt_fingerprint
            == classified.inspection_receipt_fingerprint
        )
    if not direct and not recovered:
        raise JournalV2Error()


def _terminal(_journal, record, previous):
    if (
        previous is None
        or previous.record_type is not JournalRecordTypeV2.AUTHORITY_CLAIM
        or record.transition_instance_fingerprint
        != previous.transition_instance_fingerprint
    ):
        raise JournalV2Error()


def _valid_intent_after_classification(classified, confirmation, intent):
    return (
        classified.effect_classification in {
            EffectClassificationV2.EFFECT_ABSENT_EXACT,
            EffectClassificationV2.EFFECT_PARTIAL_RESUMABLE,
        }
        and (
            intent.transition_instance_fingerprint
            == classified.transition_instance_fingerprint
            or confirmation.execution_confirmation_claim.command
            is ProductionCommandV2.ROLLBACK
        )
    )
