"""Fail-closed routing after an Issue #39 runner exception."""

from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2


def recover_after_failure(catalog, binding, location, ports):
    from .action_runner import (
        Issue39ActionRunStatusV1,
        _committed_actions,
        _result,
    )
    from .durable_ledger import Issue39LedgerStatusV1, _reopen_issue39_ledger_v1

    try:
        reopened = _reopen_issue39_ledger_v1(location=location, binding=binding)
        if reopened.status is not Issue39LedgerStatusV1.VERIFIED:
            raise ValueError
        journal = reopened.journal
        if journal.records and (
            journal.records[-1].record_type is JournalRecordTypeV2.TERMINAL_STATE
        ):
            return _result(
                Issue39ActionRunStatusV1.INCIDENT_STOP,
                _committed_actions(catalog, journal), (), journal,
            )
        from .action_recovery import _recover

        return _recover(catalog, binding, location, ports, journal)
    except Exception:
        return _result(Issue39ActionRunStatusV1.INCIDENT_STOP, (), (), None)
