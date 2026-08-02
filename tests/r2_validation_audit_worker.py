"""Fresh process that independently observes the Issue #81 sandbox."""

from __future__ import annotations

import json
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from backend.cutover_composition_contracts.canonical import fingerprint
from backend.cutover_service_lifecycle import (
    ServiceHealthEvidenceV1,
    ServiceRole,
    ServiceStartEvidenceV1,
    ServiceStopEvidenceV1,
)
from backend.r2_independent_audits import (
    AuditKind,
    IndependentAuditObservationV1,
)
from backend.r2_independent_audits.testing import SyntheticIndependentAudit


def main() -> int:
    kind_raw, binding_raw, service_raw, database_raw, target_raw, challenge = (
        sys.argv[1:]
    )
    binding = _stable_json(Path(binding_raw))
    kind = AuditKind(kind_raw)
    audit, entries = _bind_audit(kind, binding, Path(target_raw))
    events = _stable_events(Path(service_raw))
    start, evidence = _observe_service(kind, events)
    _observe_database(Path(database_raw))
    identities = fingerprint(
        "r2-validation-audit-identities-v1",
        {
            "approved": binding["approved_base"],
            "start": start.to_mapping(),
            "evidence": evidence.to_mapping(),
        },
    )
    health = fingerprint(
        "r2-validation-audit-health-v1", evidence.to_mapping()
    )
    output = _attest(
        audit,
        entries,
        kind,
        binding,
        identities,
        health,
        challenge,
    )
    sys.stdout.write(json.dumps(output, sort_keys=True))
    return 0


def _stable_json(path):
    first = path.read_bytes()
    second = path.read_bytes()
    if first != second:
        raise RuntimeError("R2_AUDIT_BINDING_UNSTABLE")
    value = json.loads(first.decode("ascii"))
    expected = {
        "operation",
        "binding",
        "head",
        "approved_base",
        "identities",
        "health",
    }
    if type(value) is not dict or set(value) != expected:
        raise RuntimeError("R2_AUDIT_BINDING_INVALID")
    return value


def _stable_events(path):
    first = path.read_bytes()
    second = path.read_bytes()
    if first != second or not first.endswith(b"\n"):
        raise RuntimeError("R2_AUDIT_SERVICE_JOURNAL_UNSTABLE")
    return tuple(json.loads(line) for line in first.decode("ascii").splitlines())


def _observe_service(kind, events):
    started = tuple(item for item in events if item.get("event") == "started")
    if len(started) != 1:
        raise RuntimeError("R2_AUDIT_SERVICE_START_INVALID")
    item = started[0]
    start = ServiceStartEvidenceV1.create(
        role=ServiceRole.NEW,
        pid=item["pid"],
        start_time_ns=item["start_time_ns"],
        executable_fingerprint=item["runtime"],
        port=item["port"],
        port_owner_pid=item["pid"],
        profile_fingerprint=item["profile"],
        runtime_fingerprint=item["runtime"],
        config_fingerprint=item["config"],
        data_role_fingerprint=item["database"],
        nonce=item["nonce"],
        primary_provider=item["primary_provider"],
        fallback_provider=item["fallback_provider"],
    )
    expected = "stopped" if kind is AuditKind.STOPPED_LAYOUT else "health"
    observed = tuple(item for item in events if item.get("event") == expected)
    if len(observed) != 1 or observed[0]["pid"] != start.pid:
        raise RuntimeError("R2_AUDIT_SERVICE_EVIDENCE_INVALID")
    evidence = (
        ServiceStopEvidenceV1.create_from_start(start)
        if kind is AuditKind.STOPPED_LAYOUT
        else ServiceHealthEvidenceV1.create_from_start(start)
    )
    return start, evidence


def _observe_database(path):
    sidecars = tuple(
        Path(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal")
    )
    with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as connection:
        rows = connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
    if rows != 1 or any(item.exists() for item in sidecars):
        raise RuntimeError("R2_AUDIT_DATABASE_LAYOUT_INVALID")


def _bind_audit(kind, binding, target):
    now = 1_900_000_000
    entries = []

    def append(value):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with target.open("x", encoding="ascii", newline="\n") as stream:
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        entries.append(value)

    audit = SyntheticIndependentAudit.create(
        kind=kind,
        operation_fingerprint=binding["operation"],
        approved_binding_fingerprint=binding["binding"],
        journal_head_fingerprint=binding["head"],
        approved_identities_fingerprint=binding["identities"],
        health_evidence_fingerprint=binding["health"],
        observed_at_epoch=now,
        now=lambda: now,
        append_attestation=append,
    )
    return audit, entries


def _attest(audit, entries, kind, binding, identities, health, challenge):
    now = 1_900_000_000
    result = audit.run(
        IndependentAuditObservationV1(
            audit_kind=kind,
            operation_fingerprint=binding["operation"],
            approved_binding_fingerprint=binding["binding"],
            journal_head_fingerprint=binding["head"],
            approved_identities_fingerprint=identities,
            health_evidence_fingerprint=health,
            observed_at_epoch=now,
            unambiguous=True,
        )
    )
    return _output(result.receipt, challenge, len(entries))


def _output(receipt, challenge, journal_entries):
    if receipt is None or journal_entries != 1:
        raise RuntimeError("R2_AUDIT_ATTESTATION_FAILED")
    return {
        "attestation_fingerprint": receipt.attestation_fingerprint,
        "journal_head_fingerprint": receipt.journal_head_fingerprint,
        "approved_identities_fingerprint": receipt.approved_identities_fingerprint,
        "health_evidence_fingerprint": receipt.health_evidence_fingerprint,
        "observed_at_epoch": receipt.observed_at_epoch,
        "expires_at_epoch": receipt.expires_at_epoch,
        "process_id": os.getpid(),
        "challenge_response": fingerprint(
            "r2-audit-process-challenge-v1",
            [challenge, receipt.attestation_fingerprint, os.getpid()],
        ),
        "journal_entries": journal_entries,
    }


if __name__ == "__main__":
    raise SystemExit(main())
