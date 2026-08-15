from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from backend.r2_issue39_orchestrator.production_inputs import (
    Issue39ProductionInputStatusV1,
    _verify_production_inputs_at,
)


class Issue39ProductionInputsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.wheelhouse = self.root / "wheelhouse"
        self.wheelhouse.mkdir()
        self.runtime = self.root / "python.exe"
        self.runtime.write_bytes(b"synthetic-runtime")
        self.database = self.root / "email_agent.sqlite3"
        self.database.write_bytes(b"synthetic-sqlite-source")
        self.crx = self.root / "browser_extension.crx"
        self.crx.write_bytes(b"Cr24synthetic-crx")
        self.lock = self.root / "requirements.lock"
        self.lock.write_bytes(b"synthetic-lock\n")

    def test_exact_manifest_and_historical_source_are_ready(self) -> None:
        manifest_hash = self._write_manifest((b"wheel-a", b"wheel-b"))

        result = _verify_production_inputs_at(
            wheelhouse=self.wheelhouse,
            runtime_executable=self.runtime,
            historical_database=self.database,
            crx_source=self.crx,
            dependency_lock=self.lock,
            expected_manifest_sha256=manifest_hash,
            expected_wheel_count=2,
            expected_runtime_sha256=_sha(self.runtime),
            expected_runtime_size=self.runtime.stat().st_size,
            expected_database_size=self.database.stat().st_size,
            expected_crx_sha256=_sha(self.crx),
            expected_crx_size=self.crx.stat().st_size,
        )

        self.assertEqual(result.status, Issue39ProductionInputStatusV1.READY)
        self.assertEqual(result.wheel_count, 2)
        self.assertEqual(result.historical_database_count, 1)
        self.assertEqual(result.read_operations, 9)
        self.assertEqual(result.runtime_fingerprint, _sha(self.runtime))
        self.assertEqual(result.crx_fingerprint, _sha(self.crx))
        self.assertEqual(len(result.database_identity_fingerprint), 64)
        self.assertEqual(len(result.config_fingerprint), 64)

    def test_missing_historical_source_blocks_migration(self) -> None:
        manifest_hash = self._write_manifest((b"wheel-a",))
        self.database.unlink()

        result = _verify_production_inputs_at(
            wheelhouse=self.wheelhouse,
            runtime_executable=self.runtime,
            historical_database=self.database,
            crx_source=self.crx,
            dependency_lock=self.lock,
            expected_manifest_sha256=manifest_hash,
            expected_wheel_count=1,
            expected_runtime_sha256=_sha(self.runtime),
            expected_runtime_size=self.runtime.stat().st_size,
            expected_database_size=len(b"synthetic-sqlite-source"),
            expected_crx_sha256=_sha(self.crx),
            expected_crx_size=self.crx.stat().st_size,
        )

        self.assertEqual(
            result.status,
            Issue39ProductionInputStatusV1.BLOCKED_HISTORICAL_DATABASE,
        )
        self.assertEqual(result.historical_database_count, 0)

    def test_manifest_or_extra_entry_drift_fails_closed(self) -> None:
        manifest_hash = self._write_manifest((b"wheel-a",))
        (self.wheelhouse / "extra.whl").write_bytes(b"extra")

        result = _verify_production_inputs_at(
            wheelhouse=self.wheelhouse,
            runtime_executable=self.runtime,
            historical_database=self.database,
            crx_source=self.crx,
            dependency_lock=self.lock,
            expected_manifest_sha256=manifest_hash,
            expected_wheel_count=1,
            expected_runtime_sha256=_sha(self.runtime),
            expected_runtime_size=self.runtime.stat().st_size,
            expected_database_size=self.database.stat().st_size,
            expected_crx_sha256=_sha(self.crx),
            expected_crx_size=self.crx.stat().st_size,
        )

        self.assertEqual(
            result.status,
            Issue39ProductionInputStatusV1.BLOCKED_WHEELHOUSE,
        )
        self.assertEqual(result.wheel_count, 0)

    def _write_manifest(self, payloads: tuple[bytes, ...]) -> str:
        wheels = []
        for index, payload in enumerate(payloads, start=1):
            name = f"package_{index}-1.0-py3-none-any.whl"
            (self.wheelhouse / name).write_bytes(payload)
            wheels.append(
                {
                    "name": name,
                    "size_bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
        manifest = {
            "schema": "issue39-wheelhouse-manifest-v1",
            "python_version": "3.12.13",
            "sqlite_version": "3.50.4",
            "platform": "win_amd64",
            "implementation": "cp",
            "abi": "cp312",
            "dependency_lock": "requirements-ci-windows.lock",
            "dependency_lock_sha256": hashlib.sha256(
                self.lock.read_bytes()
            ).hexdigest(),
            "wheel_count": len(wheels),
            "total_bytes": sum(item["size_bytes"] for item in wheels),
            "wheels": wheels,
        }
        payload = (
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        path = self.wheelhouse / "wheelhouse-manifest-v1.json"
        path.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
