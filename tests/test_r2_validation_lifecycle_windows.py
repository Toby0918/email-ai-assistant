"""Fresh Windows sandbox proof for the complete Issue #81 slice."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.r2_validation_lifecycle import (
    FinalDatabaseProofV1,
    IndependentAuditCompletionV1,
    PersistedPublicRowEvidenceV1,
    ValidationFaultSelectorV1,
    ValidationLifecycle,
    ValidationStatus,
)
from tests.r2_validation_lifecycle_fixture import (
    NOW,
    OPERATION,
    SyntheticValidationAdapters,
    approved_slice,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class R2ValidationLifecycleWindowsTests(unittest.TestCase):
    def test_full_slice_uses_one_row_two_fresh_audits_and_no_b_write(self):
        with tempfile.TemporaryDirectory(prefix="r2-validation-") as raw:
            approved = approved_slice()
            adapters = _WindowsAdapters(Path(raw), approved.slice_fingerprint)
            result = ValidationLifecycle.create(
                approved=approved,
                adapters=adapters.bundle(),
                nonce_factory=iter(
                    (
                        "11111111-1111-4111-8111-111111111111",
                        "22222222-2222-4222-8222-222222222222",
                    )
                ).__next__,
                now=lambda: NOW,
                fault=ValidationFaultSelectorV1.none(),
            ).run()

            self.assertIs(result.status, ValidationStatus.VALIDATED)
            self.assertEqual(adapters.row_count(), 1)
            self.assertEqual(adapters.analysis_calls, 1)
            self.assertEqual(adapters.row_writes, 1)
            self.assertEqual(len(adapters.audit_process_ids), 2)
            self.assertEqual(len(set(adapters.audit_process_ids)), 2)
            self.assertNotIn(adapters.starts[0].pid, adapters.audit_process_ids)
            self.assertNotIn(adapters.starts[1].pid, adapters.audit_process_ids)
            self.assertFalse(any(item.exists() for item in adapters.sidecars()))


class _WindowsAdapters(SyntheticValidationAdapters):
    def __init__(self, root: Path, binding: str) -> None:
        super().__init__()
        self.root = root
        self.binding = binding
        self.database_path = root / "managed.sqlite3"
        self.audit_process_ids = []
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "CREATE TABLE analyses (result_fingerprint TEXT NOT NULL)"
            )

    def row(self, result, database_role):
        self.calls.append("row")
        self.row_writes += 1
        with closing(sqlite3.connect(self.database_path)) as connection, connection:
            connection.execute(
                "INSERT INTO analyses(result_fingerprint) VALUES (?)",
                (result.result_fingerprint,),
            )
        return PersistedPublicRowEvidenceV1.create(
            result_fingerprint=result.result_fingerprint,
            database_role_fingerprint=database_role,
            matching_rows=self.row_count(),
            write_count=1,
        )

    def database(self, database_role, row):
        self.calls.append("database_proof")
        return FinalDatabaseProofV1.create(
            database_role_fingerprint=database_role,
            matching_rows=self.row_count(),
            sidecar_count=sum(item.exists() for item in self.sidecars()),
            source_unchanged=True,
        )

    def audit(self, request):
        self.calls.append(f"audit_{request.audit_kind.value}")
        root = Path(__file__).resolve().parents[1]
        completed = subprocess.run(
            (
                sys.executable,
                "-B",
                "-m",
                "tests.r2_validation_audit_worker",
                request.audit_kind.value,
                OPERATION,
                self.binding,
                request.journal_head_fingerprint,
                request.approved_identities_fingerprint,
                request.health_evidence_fingerprint,
                request.service_nonce,
                str(request.service_process_id),
            ),
            cwd=root,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if completed.returncode != 0 or completed.stderr:
            raise RuntimeError("synthetic independent audit failed")
        values = json.loads(completed.stdout)
        if values.pop("journal_entries") != 1:
            raise RuntimeError("synthetic audit attestation count invalid")
        values["audit_kind"] = request.audit_kind
        result = IndependentAuditCompletionV1.create(**values)
        self.audit_process_ids.append(result.audit_process_id)
        return result

    def row_count(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]

    def sidecars(self):
        return tuple(
            Path(str(self.database_path) + suffix)
            for suffix in ("-wal", "-shm", "-journal")
        )


if __name__ == "__main__":
    unittest.main()
