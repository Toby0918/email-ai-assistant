"""Fresh Windows sandbox proof for the complete Issue #81 slice."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from backend.r2_validation_lifecycle import (
    FinalDatabaseProofV1,
    PersistedPublicRowEvidenceV1,
    PublicRuleFallbackResultV1,
    ValidationFaultSelectorV1,
    ValidationLifecycle,
    ValidationStatus,
)
from backend.r2_independent_audits.testing import verify_worker_attestation
from backend.r2_independent_audits import AuditKind
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
            adapters = _WindowsAdapters(
                Path(raw),
                approved.slice_fingerprint,
                approved.approved_identities_fingerprint,
            )
            try:
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
            finally:
                adapters.close()

            self.assertIs(result.status, ValidationStatus.VALIDATED)
            self.assertEqual(adapters.row_count(), 1)
            self.assertEqual(adapters.analysis_calls, 1)
            self.assertEqual(adapters.row_writes, 1)
            self.assertEqual(adapters.service_metrics[0], (1, 1))
            self.assertEqual(adapters.service_metrics[1], (0, 0))
            self.assertEqual(len(adapters.audit_process_ids), 2)
            self.assertEqual(len(set(adapters.audit_process_ids)), 2)
            self.assertNotIn(adapters.starts[0].pid, adapters.audit_process_ids)
            self.assertNotIn(adapters.starts[1].pid, adapters.audit_process_ids)
            self.assertFalse(any(item.exists() for item in adapters.sidecars()))

    def test_prebound_audit_sink_rejects_tampered_service_identity(self):
        with tempfile.TemporaryDirectory(prefix="r2-validation-tamper-") as raw:
            approved = approved_slice()
            adapters = _WindowsAdapters(
                Path(raw),
                approved.slice_fingerprint,
                approved.approved_identities_fingerprint,
            )
            adapters.audit_tamper = AuditKind.STOPPED_LAYOUT
            try:
                result = ValidationLifecycle.create(
                    approved=approved,
                    adapters=adapters.bundle(),
                    nonce_factory=iter(
                        ("11111111-1111-4111-8111-111111111111",)
                    ).__next__,
                    now=lambda: NOW,
                    fault=ValidationFaultSelectorV1.none(),
                ).run()
            finally:
                adapters.close()

            self.assertIs(result.status, ValidationStatus.INCIDENT_STOP)
            target = Path(raw) / "audit-stopped_layout.attestation"
            self.assertFalse(target.exists())


class _WindowsAdapters(SyntheticValidationAdapters):
    def __init__(
        self,
        root: Path,
        binding: str,
        approved_identities: str,
        *,
        database_path: Path | None = None,
        service_executable: Path | None = None,
        config_path: Path | None = None,
    ) -> None:
        super().__init__()
        self.root = root
        self.binding = binding
        self.approved_identities = approved_identities
        self.database_path = database_path or root / "managed.sqlite3"
        self.service_executable = service_executable or Path(
            getattr(sys, "_base_executable", sys.executable)
        )
        self.config_path = config_path or root / "managed.env"
        self.audit_process_ids = []
        self.audit_completions = []
        self.service_processes = []
        self.service_metrics = []
        self.service_journals = {}
        self.audit_tamper = None
        if database_path is None:
            with closing(sqlite3.connect(self.database_path)) as connection, connection:
                connection.execute(
                    "CREATE TABLE analyses (result_fingerprint TEXT NOT NULL)"
                )
        if config_path is None:
            self.config_path.write_bytes(
                b"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=example.test,internal.example\n"
                b"EMAIL_AGENT_LOG_LEVEL=WARNING\n"
            )
        if self.row_count() != 0 or not self.service_executable.is_file():
            raise RuntimeError("synthetic published service inputs invalid")

    def start(self, request):
        self.calls.append(f"start_{request.phase}")
        root = Path(__file__).resolve().parents[1]
        journal_path = self.root / f"service-{request.phase}.journal"
        process = subprocess.Popen(
            (
                str(self.service_executable),
                "-B",
                str(root / "tests" / "r2_validation_service_worker.py"),
                str(self.database_path),
                str(journal_path),
                str(self.config_path),
            ),
            cwd=root,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        ready = self._read(process)
        if (
            ready.get("pid") != process.pid
            or ready.get("primary_provider") != "disabled"
            or ready.get("fallback_provider") != "disabled"
        ):
            raise RuntimeError("synthetic service start failed")
        bound = self._exchange(
            process,
            {
                "command": "bind",
                "profile": request.profile_fingerprint,
                "runtime": request.runtime_fingerprint,
                "config": request.config_fingerprint,
                "database": request.database_role_fingerprint,
                "nonce": request.nonce,
                "port": request.port,
            },
        )
        if bound != {"pid": process.pid, "bound": True}:
            raise RuntimeError("synthetic service binding failed")
        from backend.cutover_service_lifecycle import ServiceRole, ServiceStartEvidenceV1

        start = ServiceStartEvidenceV1.create(
            role=ServiceRole.NEW,
            pid=process.pid,
            start_time_ns=ready["start_time_ns"],
            executable_fingerprint=request.runtime_fingerprint,
            port=request.port,
            port_owner_pid=process.pid,
            profile_fingerprint=request.profile_fingerprint,
            runtime_fingerprint=request.runtime_fingerprint,
            config_fingerprint=request.config_fingerprint,
            data_role_fingerprint=request.database_role_fingerprint,
            nonce=request.nonce,
            primary_provider="disabled",
            fallback_provider="disabled",
        )
        self.starts.append(start)
        self.service_processes.append(process)
        self.service_journals[process.pid] = journal_path
        return start

    def health(self, start):
        self.calls.append("health")
        process = self._process(start.pid)
        value = self._exchange(process, {"command": "health"})
        if value.get("pid") != start.pid or value.get("healthy") is not True:
            raise RuntimeError("synthetic service health failed")
        if len(self.starts) == 2 and (
            value.get("analysis_count"), value.get("write_count")
        ) != (0, 0):
            raise RuntimeError("start B performed forbidden work")
        from backend.cutover_service_lifecycle import ServiceHealthEvidenceV1

        return ServiceHealthEvidenceV1.create_from_start(start)

    def analysis(self, request):
        self.calls.append("analysis")
        self.analysis_calls += 1
        process = self.service_processes[-1]
        result_fingerprint = "8120".zfill(64)
        value = self._exchange(
            process,
            {
                "command": "analyze_rule_fallback",
                "request": request.request_fingerprint,
                "result": result_fingerprint,
            },
        )
        if value.get("pid") != process.pid or value.get("write_count") != 1:
            raise RuntimeError("synthetic service analysis failed")
        return PublicRuleFallbackResultV1.create(
            request_fingerprint=value["request"],
            result_fingerprint=value["result"],
            analysis_engine_source=value["analysis_engine_source"],
            provider_attempts=value["provider_attempts"],
            safe=value["safe"],
        )

    def row(self, result, database_role):
        self.calls.append("row")
        self.row_writes += 1
        return PersistedPublicRowEvidenceV1.create(
            result_fingerprint=result.result_fingerprint,
            database_role_fingerprint=database_role,
            matching_rows=self.row_count(),
            write_count=1,
        )

    def stop(self, start):
        self.calls.append("stop")
        process = self._process(start.pid)
        value = self._exchange(process, {"command": "stop"})
        process.wait(timeout=20)
        if process.returncode != 0 or value.get("pid") != start.pid:
            raise RuntimeError("synthetic service stop failed")
        self.service_metrics.append(
            (value["analysis_count"], value["write_count"])
        )
        self._close_streams(process)
        from backend.cutover_service_lifecycle import ServiceStopEvidenceV1

        return ServiceStopEvidenceV1.create_from_start(start)

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
        challenge = secrets.token_hex(32)
        state_path = self.root / f"audit-{request.audit_kind.value}.json"
        attestation_path = self.root / (
            f"audit-{request.audit_kind.value}.attestation"
        )
        state = {
            "operation": OPERATION,
            "binding": self.binding,
            "head": request.journal_head_fingerprint,
            "approved_base": self.approved_identities,
            "identities": request.approved_identities_fingerprint,
            "health": request.health_evidence_fingerprint,
        }
        with state_path.open("x", encoding="ascii", newline="\n") as stream:
            json.dump(state, stream, sort_keys=True, separators=(",", ":"))
            stream.flush()
            os.fsync(stream.fileno())
        if self.audit_tamper is request.audit_kind:
            self._tamper_service_identity(
                self.service_journals[request.service_process_id]
            )
        process = subprocess.Popen(
            (
                getattr(sys, "_base_executable", sys.executable),
                "-B",
                "-m",
                "tests.r2_validation_audit_worker",
                request.audit_kind.value,
                str(state_path),
                str(self.service_journals[request.service_process_id]),
                str(self.database_path),
                str(attestation_path),
                challenge,
            ),
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate(timeout=20)
        if process.returncode != 0 or stderr:
            raise RuntimeError("synthetic independent audit failed")
        self._verify_durable_attestation(
            attestation_path, request.audit_kind.value, json.loads(stdout)
        )
        result = verify_worker_attestation(
            kind=request.audit_kind,
            values=json.loads(stdout),
            challenge=challenge,
            process_id=process.pid,
            journal_head_fingerprint=request.journal_head_fingerprint,
            approved_identities_fingerprint=request.approved_identities_fingerprint,
            health_evidence_fingerprint=request.health_evidence_fingerprint,
            observed_at_epoch=NOW,
        )
        self.audit_process_ids.append(result.process_id)
        self.audit_completions.append(result)
        return result

    @staticmethod
    def _verify_durable_attestation(path, kind, worker):
        first = path.read_bytes()
        second = path.read_bytes()
        if first != second or not first.endswith(b"\n"):
            raise RuntimeError("synthetic audit attestation unstable")
        value = json.loads(first.decode("ascii"))
        expected = {
            "attestation_type",
            "audit_kind",
            "attestation_fingerprint",
            "observed_at_epoch",
            "expires_at_epoch",
        }
        if (
            set(value) != expected
            or value["audit_kind"] != kind
            or value["attestation_fingerprint"]
            != worker["attestation_fingerprint"]
        ):
            raise RuntimeError("synthetic audit attestation invalid")

    @staticmethod
    def _tamper_service_identity(path):
        records = [json.loads(line) for line in path.read_text("ascii").splitlines()]
        started = next(item for item in records if item["event"] == "started")
        started["profile"] = "f" * 64
        with path.open("w", encoding="ascii", newline="\n") as stream:
            for item in records:
                stream.write(json.dumps(item, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def row_count(self):
        with closing(sqlite3.connect(self.database_path)) as connection:
            return connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]

    def sidecars(self):
        return tuple(
            Path(str(self.database_path) + suffix)
            for suffix in ("-wal", "-shm", "-journal")
        )

    def close(self):
        for process in self.service_processes:
            if process.poll() is None:
                value = self._exchange(process, {"command": "stop"})
                process.wait(timeout=20)
                self.service_metrics.append(
                    (value["analysis_count"], value["write_count"])
                )
                self._close_streams(process)

    def _process(self, pid):
        return next(item for item in self.service_processes if item.pid == pid)

    @staticmethod
    def _exchange(process, value):
        process.stdin.write(json.dumps(value, sort_keys=True) + "\n")
        process.stdin.flush()
        return _WindowsAdapters._read(process)

    @staticmethod
    def _read(process):
        raw = process.stdout.readline()
        if raw == "":
            raise RuntimeError("synthetic service exited")
        return json.loads(raw)

    @staticmethod
    def _close_streams(process):
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()


if __name__ == "__main__":
    unittest.main()
