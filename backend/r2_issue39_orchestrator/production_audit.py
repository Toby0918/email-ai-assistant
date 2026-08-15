"""Fresh content-free terminal and legacy topology observations."""

from __future__ import annotations

import hashlib
import json
import os
import stat

from backend.cutover_managed_activation.windows_file_handles import WindowsReadHandleApi
from backend.cutover_repository_transaction.windows_identity import directory_identity
from backend.r2_transaction_journal_v2.vocabulary import JournalRecordTypeV2


_TOP = {
    "main", "Runtimes", "LocalData", "RuntimeTemp", "Logs", "Artifacts",
    "Worktrees", "Config", "OperatorPrivate",
}
def terminal_audit_reads(host, catalog, journal_head):
    first_facts = _terminal_facts(host)
    second_facts = _terminal_facts(host)
    first = _fingerprint("r2-issue39-terminal-minimal-state-v2", first_facts)
    second = _fingerprint("r2-issue39-terminal-minimal-state-v2", second_facts)
    journal_facts = _validation_journal_facts(host, catalog, journal_head)
    validation = _fingerprint(
        "r2-issue39-validation-receipt-v2",
        {
            "catalog": catalog.catalog_fingerprint,
            "journal_head": journal_head,
            "analysis": first_facts["analysis"],
            "service": first_facts["service"],
            "provider_attempt_count": first_facts["service"][
                "provider_attempt_count"
            ],
            "database_write_count": first_facts["analysis"]["matching_rows"],
            "journal": journal_facts,
        },
    )
    return validation, first, second


def legacy_audit_reads(host, catalog, journal_head):
    first = _fingerprint(
        "r2-issue39-legacy-minimal-state-v2",
        _legacy_facts(host, catalog, journal_head),
    )
    second = _fingerprint(
        "r2-issue39-legacy-minimal-state-v2",
        _legacy_facts(host, catalog, journal_head),
    )
    return first, second


def _terminal_facts(host):
    return validation_audit_facts(host, {"start_b"})


def validation_audit_facts(host, running_names):
    from .production_acl import fixed_acl_conforms
    from .production_managed import _exact
    from .production_host_state import database_identity_bound
    from .production_repository import repository_exact
    from .production_roster_reverify import terminal_roster_fingerprint
    from .production_service import (
        validation_service_observation,
        validation_service_running,
    )
    from .production_analysis_state import matching_analysis
    from .production_validation import _audit, _database_proof
    _audit(host)
    _database_proof(host)
    if not fixed_acl_conforms(host) or not repository_exact(host):
        raise ValueError("R2_ISSUE39_TERMINAL_AUDIT_INVALID")
    for unit in ("runtime", "crx", "config"):
        if not _exact(unit, getattr(host._layout, unit + "_target"), host):
            raise ValueError("R2_ISSUE39_TERMINAL_AUDIT_INVALID")
    database_action = next(
        item for item in host._catalog.actions if item.action_name == "database_publish"
    )
    if not database_identity_bound(host, database_action):
        raise ValueError("R2_ISSUE39_TERMINAL_AUDIT_INVALID")
    top = _directory_facts(host._layout.container, _TOP)
    service = (
        validation_service_observation(host, running_names)
        if running_names is not None
        else {"stopped": not validation_service_running(host)}
    )
    if running_names is None and service["stopped"] is not True:
        raise ValueError("R2_ISSUE39_TERMINAL_AUDIT_INVALID")
    return {
        "prepare": host._prepared.prepare_fingerprint,
        "repository_manifest": host._repository.manifest_fingerprint,
        "main_git_identity": directory_identity(host._layout.main / ".git"),
        "topology": top,
        "roster": terminal_roster_fingerprint(host),
        "runtime_identity": directory_identity(host._layout.runtime_target),
        "database": _file_fact(
            host._layout.database_target,
            128 * 1024 * 1024,
            deny_write=False,
        ),
        "crx": _file_fact(host._layout.crx_target, 1024 * 1024),
        "config": _file_fact(host._layout.config_target, 16 * 1024),
        "analysis": matching_analysis(host._layout.database_target),
        "service": service,
        "provider_attempt_count": 0,
    }


def _legacy_facts(host, catalog, journal_head):
    from .production_foundation import _legacy_matches_preimage
    from .production_repository import repository_exact
    from .production_roster_reverify import legacy_roster_fingerprint
    from .production_service import legacy_recovery_observation

    layout = host._layout
    if (
        layout.container != layout.source
        or os.path.lexists(layout.legacy)
        or not _plain_directory(layout.source)
        or not _plain_directory(layout.failed)
        or directory_identity(layout.source)
        != host._repository.source_identity_fingerprint
        or not repository_exact(host, reverse=True)
        or not _legacy_matches_preimage(host)
    ):
        raise ValueError("R2_ISSUE39_LEGACY_AUDIT_INVALID")
    failed_names = {item.name for item in layout.failed.iterdir()}
    if failed_names != _TOP:
        raise ValueError("R2_ISSUE39_LEGACY_AUDIT_INVALID")
    recovered_service = legacy_recovery_observation(host)
    return {
        "prepare": host._prepared.prepare_fingerprint,
        "catalog": catalog.catalog_fingerprint,
        "journal_head": journal_head,
        "repository_manifest": host._repository.manifest_fingerprint,
        "source_identity": directory_identity(layout.source),
        "source_git_identity": directory_identity(layout.source / ".git"),
        "roster": legacy_roster_fingerprint(host),
        "failed_container_identity": directory_identity(layout.failed),
        "failed_topology": _directory_facts(layout.failed, _TOP),
        "legacy_service": recovered_service,
        "provider_attempt_count": 0,
        "cleanup_count": 0,
        "deletion_count": 0,
    }


def _validation_journal_facts(host, catalog, journal_head):
    from .durable_ledger import (
        Issue39LedgerStatusV1,
        _Issue39LedgerLocationV1,
        _reopen_issue39_ledger_v1,
    )
    from .production_bootstrap import _LEDGER_PARENT

    location = _Issue39LedgerLocationV1(
        _LEDGER_PARENT / (
            ".issue39-ledger-" + host._closure.production.binding_fingerprint
        )
    )
    reopened = _reopen_issue39_ledger_v1(
        location=location, binding=host._closure.production
    )
    if reopened.status is not Issue39LedgerStatusV1.VERIFIED:
        raise ValueError("R2_ISSUE39_VALIDATION_RECEIPT_INVALID")
    durable = reopened.journal
    if not _journal_at_head(durable, journal_head):
        raise ValueError("R2_ISSUE39_VALIDATION_RECEIPT_INVALID")
    commit_records = _catalog_commits(durable, catalog)
    expected = tuple(action.action_fingerprint for action in catalog.actions)
    committed = tuple(
        record.transition_instance_fingerprint for record in commit_records
    )
    if committed != expected:
        raise ValueError("R2_ISSUE39_VALIDATION_RECEIPT_INVALID")
    _require_live_validation_evidence(host, catalog, commit_records)
    evidence = tuple(
        record.inspection_receipt_fingerprint for record in commit_records
    )
    validation_evidence = tuple(
        (action.action_name, record.inspection_receipt_fingerprint)
        for action, record in zip(catalog.actions, commit_records)
        if action.phase.value == "validation"
    )
    return {
        "ordered_commit_count": len(committed),
        "ordered_commit_fingerprint": _fingerprint(
            "r2-issue39-ordered-action-commits-v1", committed
        ),
        "ordered_evidence_fingerprint": _fingerprint(
            "r2-issue39-ordered-action-evidence-v1", evidence
        ),
        "validation_evidence": validation_evidence,
    }


def _journal_at_head(journal, expected):
    pending = (
        journal.records
        and journal.records[-1].record_type is JournalRecordTypeV2.AUTHORITY_CLAIM
        and journal.records[-1].predecessor_head_fingerprint == expected
    )
    sealed = (
        len(journal.records) >= 2
        and journal.records[-1].record_type is JournalRecordTypeV2.TERMINAL_STATE
        and journal.records[-2].record_type is JournalRecordTypeV2.AUTHORITY_CLAIM
        and journal.records[-2].predecessor_head_fingerprint == expected
    )
    return journal.current_head_fingerprint == expected or pending or sealed


def _catalog_commits(journal, catalog):
    known = {action.action_fingerprint for action in catalog.actions}
    return tuple(
        record for record in journal.records
        if record.record_type is JournalRecordTypeV2.COMMIT
        and record.transition_instance_fingerprint in known
    )


def _require_live_validation_evidence(host, catalog, records):
    from .production_action_evidence import action_evidence

    by_transition = {
        record.transition_instance_fingerprint: record for record in records
    }
    for action in catalog.actions:
        if action.action_name not in {
            "rule_fallback_analysis", "database_proof", "start_b",
            "final_running_audit",
        }:
            continue
        current = action_evidence(
            host, action, "forward", action.post_state_fingerprint
        )
        if current != by_transition[
            action.action_fingerprint
        ].inspection_receipt_fingerprint:
            raise ValueError("R2_ISSUE39_VALIDATION_RECEIPT_INVALID")


def _directory_facts(root, expected_names):
    children = tuple(sorted(root.iterdir(), key=lambda item: item.name))
    if {item.name for item in children} != expected_names:
        raise ValueError("R2_ISSUE39_TOPOLOGY_INVALID")
    facts = []
    for item in children:
        if not _plain_directory(item):
            raise ValueError("R2_ISSUE39_TOPOLOGY_INVALID")
        facts.append((item.name, directory_identity(item)))
    return facts


def _file_fact(path, limit, *, deny_write=True):
    api = WindowsReadHandleApi()
    handle = api.open_existing(path, deny_write=deny_write)
    try:
        observed = api.observe(handle)
        first = api.hash_bounded(handle, limit=limit)
        api.require_stable(handle, observed, path)
        second = api.hash_bounded(handle, limit=limit)
        api.require_stable(handle, observed, path)
        if first != second:
            raise ValueError("R2_ISSUE39_TERMINAL_FILE_DRIFT")
        size, digest = first
        return {
            "identity": observed.object_identity_fingerprint,
            "size": size,
            "sha256": digest,
        }
    finally:
        api.close(handle)


def _plain_directory(path):
    try:
        value = path.lstat()
        return stat.S_ISDIR(value.st_mode) and not (
            getattr(value, "st_file_attributes", 0) & 0x400
        ) and not path.is_symlink() and not path.is_junction()
    except OSError:
        return False


def _fingerprint(domain, value):
    payload = json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(domain.encode("ascii") + b"\0" + payload).hexdigest()
