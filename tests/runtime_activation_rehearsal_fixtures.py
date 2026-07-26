"""Caller-owned temporary synthetic state for Issue #37 tests."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from types import TracebackType
from typing import Self
import unittest

from backend.runtime_activation_rehearsal import ManagedActivationAdapters
from backend.runtime_activation_rehearsal.policy import (
    LOCKED_DEPENDENCIES,
    ManagedResourceRole,
)


@dataclass(frozen=True, slots=True, repr=False)
class SyntheticFileState:
    """Stable identity, digest and optional aggregate count."""

    present: bool
    identity: str
    size_bytes: int
    sha256: str
    aggregate_count: int | None


class SyntheticActivationWorld:
    """Own all mutable sources and destinations used by one rehearsal."""

    def __init__(self, *, failure: str | None = None) -> None:
        self.failure = failure
        self.events: list[str] = []
        self.running = True
        self.stop_token = ""
        self.stop_count = 0
        self.legacy_reads = 0
        self.signing_reads = 0
        self.network_installs = 0
        self.provider_calls = 0
        self.mailbox_accesses = 0
        self.vault_accesses = 0
        self.private_store_accesses = 0
        self.credential_accesses = 0
        self._temporary: TemporaryDirectory[str] | None = None

    def __enter__(self) -> Self:
        self._temporary = TemporaryDirectory(
            prefix="issue37-synthetic-"
        )
        self.root = Path(self._temporary.name)
        self._create_layout()
        self._create_sources()
        self._create_source_database()
        self._create_initial_service_state()
        self._create_competitor()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()

    def adapters(self) -> ManagedActivationAdapters:
        """Build exact injected adapters bound to this temporary world."""
        from tests.runtime_activation_rehearsal_fixture_adapters import (
            build_synthetic_adapters,
        )

        return build_synthetic_adapters(self)

    def source_state(self) -> SyntheticFileState:
        return self._file_state(self.source_database, database=True)

    def legacy_state(self) -> SyntheticFileState:
        return self._file_state(self.legacy_venv)

    def runtime_source_state(self) -> SyntheticFileState:
        return self._file_state(self.runtime_source)

    def competitor_state(self) -> SyntheticFileState | None:
        target = self._competitor_target()
        if target is None or not target.exists() or target.is_dir():
            if target is not None and target.is_dir():
                target = target / "competitor.txt"
            else:
                return None
        return self._file_state(target)

    def assert_source_preserved(
        self,
        before: SyntheticFileState,
    ) -> None:
        unittest.TestCase().assertEqual(self.source_state(), before)

    def assert_legacy_preserved(
        self,
        before: SyntheticFileState,
    ) -> None:
        unittest.TestCase().assertEqual(self.legacy_state(), before)
        unittest.TestCase().assertEqual(self.legacy_reads, 0)

    def assert_runtime_source_preserved(
        self,
        before: SyntheticFileState,
    ) -> None:
        unittest.TestCase().assertEqual(
            self.runtime_source_state(),
            before,
        )

    def assert_competitor_preserved(
        self,
        before: SyntheticFileState | None,
    ) -> None:
        case = unittest.TestCase()
        if before is not None:
            case.assertEqual(self.competitor_state(), before)
        elif self.failure == "database_race":
            case.assertEqual(
                self.database_target.read_bytes(),
                b"synthetic database competitor",
            )

    def assert_successful_activation(self) -> None:
        case = unittest.TestCase()
        destination = self._file_state(
            self.database_target,
            database=True,
        )
        artifact = self._file_state(self.artifact_target)
        case.assertEqual(destination.aggregate_count, 3)
        case.assertEqual(
            artifact.sha256,
            self._file_state(self.artifact_source).sha256,
        )
        case.assertTrue(self.runtime_target.is_dir())
        case.assertTrue(self.venv_target.is_dir())
        case.assertEqual(
            self.venv_target,
            self.zones["runtimes"] / "venv",
        )
        case.assertEqual(
            self.venv_executable,
            self.venv_target / "Scripts" / "python.exe",
        )
        case.assertTrue(self.venv_executable.is_file())
        case.assertEqual(
            self.database_target.parent,
            self.zones["local_data"],
        )
        case.assertEqual(
            self.artifact_target.parent,
            self.browser_extension_dir,
        )
        case.assertTrue(self.log_file.is_file())
        case.assertFalse(self.pid_file.exists())
        case.assertFalse(self.running)
        case.assertEqual(self.events.count("probe.analyze"), 1)
        case.assertFalse(
            tuple(self.root.rglob("*.migration-evidence.zip"))
        )

    def assert_failure_stopped(self) -> None:
        if "lifecycle.start" in self.events:
            unittest.TestCase().assertFalse(self.running)
            unittest.TestCase().assertFalse(self.pid_file.exists())

    def assert_no_forbidden_access(self) -> None:
        case = unittest.TestCase()
        case.assertEqual(self.signing_reads, 0)
        case.assertEqual(self.network_installs, 0)
        case.assertEqual(self.provider_calls, 0)
        case.assertEqual(self.mailbox_accesses, 0)
        case.assertEqual(self.vault_accesses, 0)
        case.assertEqual(self.private_store_accesses, 0)
        case.assertEqual(self.credential_accesses, 0)

    def _create_layout(self) -> None:
        self.container = self.root / "email_ai_assistant"
        self.main = self.container / "main"
        zone_names = {
            "runtimes": "Runtimes",
            "local_data": "LocalData",
            "runtime_temp": "RuntimeTemp",
            "logs": "Logs",
            "artifacts": "Artifacts",
            "worktrees": "Worktrees",
            "config": "Config",
        }
        self.zones = {
            key: self.container / name
            for key, name in zone_names.items()
        }
        self.main.mkdir(parents=True)
        for zone in self.zones.values():
            zone.mkdir(parents=True)
        self.attachment_temp = (
            self.zones["runtime_temp"] / "attachment_temp"
        )
        self.attachment_temp.mkdir()
        self.log_file = self.zones["logs"] / "local_debug_service.log"
        self.pid_file = self.zones["logs"] / "local_debug_service.pid"
        self.config_file = self.zones["config"] / "settings.env"
        self.config_file.write_text(
            "EMAIL_AGENT_LOG_LEVEL=INFO\n"
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=example.test\n",
            encoding="utf-8",
        )
        self.log_file.write_text("synthetic log\n", encoding="utf-8")
        self.browser_extension_dir = (
            self.zones["artifacts"] / "BrowserExtension"
        )
        self.browser_extension_dir.mkdir()
        self.resources = {
            ManagedResourceRole.ATTACHMENT_TEMP: self.attachment_temp,
            ManagedResourceRole.SERVICE_LOG: self.log_file,
            ManagedResourceRole.PID_STATE: self.pid_file,
            ManagedResourceRole.NON_SECRET_CONFIG: self.config_file,
            ManagedResourceRole.BROWSER_EXTENSION: (
                self.browser_extension_dir
            ),
        }

    def _create_sources(self) -> None:
        sources = self.root / "synthetic_sources"
        sources.mkdir()
        self.runtime_source = sources / "runtime-source.bin"
        self.runtime_source.write_bytes(b"synthetic pinned runtime")
        self.dependency_lock = sources / "requirements.lock"
        self.dependency_lock.write_bytes(
            ("\n".join(LOCKED_DEPENDENCIES) + "\n").encode("utf-8")
        )
        self.legacy_venv = sources / "legacy-venv.bin"
        self.legacy_venv.write_bytes(b"legacy venv must stay untouched")
        self.artifact_source = sources / "browser_extension.crx"
        self.artifact_source.write_bytes(b"synthetic reviewed extension")
        self.reviewed_artifact_state = self._file_state(
            self.artifact_source
        )
        self.signing_canary = sources / "browser_extension.pem"
        self.signing_canary.write_bytes(b"must never be read")
        self.runtime_target = (
            self.zones["runtimes"] / "python-3.12.13-sqlite-3.50.4"
        )
        self.venv_target = self.zones["runtimes"] / "venv"
        self.scripts_target = self.venv_target / "Scripts"
        self.venv_executable = self.scripts_target / "python.exe"
        self.database_target = (
            self.zones["local_data"] / "email_agent.sqlite3"
        )
        self.artifact_target = (
            self.browser_extension_dir / "browser_extension.crx"
        )

    def _create_source_database(self) -> None:
        self.source_database = (
            self.root / "synthetic_sources" / "email_agent.sqlite3"
        )
        connection = sqlite3.connect(self.source_database)
        try:
            connection.execute(
                "CREATE TABLE email_analysis "
                "(id INTEGER PRIMARY KEY, subject TEXT NOT NULL)"
            )
            connection.executemany(
                "INSERT INTO email_analysis(subject) VALUES (?)",
                (("synthetic one",), ("synthetic two",)),
            )
            connection.commit()
        finally:
            connection.close()

    def _create_initial_service_state(self) -> None:
        self.pid_file.write_text("synthetic-initial", encoding="ascii")

    def _create_competitor(self) -> None:
        if self.failure == "runtime_existing":
            self.runtime_target.mkdir()
            (self.runtime_target / "competitor.txt").write_bytes(
                b"synthetic runtime competitor"
            )
        elif self.failure == "artifact_existing":
            self.artifact_target.write_bytes(
                b"synthetic artifact competitor"
            )

    def _competitor_target(self) -> Path | None:
        if self.failure == "runtime_existing":
            return self.runtime_target
        if self.failure in {"artifact_existing", "database_race"}:
            return (
                self.artifact_target
                if self.failure == "artifact_existing"
                else self.database_target
            )
        return None

    def _file_state(
        self,
        path: Path,
        *,
        database: bool = False,
    ) -> SyntheticFileState:
        data = path.read_bytes()
        count = self._database_count(path) if database else None
        return SyntheticFileState(
            present=True,
            identity=self.identity(path),
            size_bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),
            aggregate_count=count,
        )

    @staticmethod
    def identity(path: Path) -> str:
        stat = path.stat()
        return f"synthetic-{stat.st_dev:x}-{stat.st_ino:x}"

    def path_identity(self, path: Path) -> str:
        relative = path.relative_to(self.root).as_posix().encode("utf-8")
        return "resource-" + hashlib.sha256(relative).hexdigest()[:24]

    def read_bytes(self, path: Path) -> bytes:
        if path == self.signing_canary:
            self.signing_reads += 1
            raise AssertionError("signing material read")
        return path.read_bytes()

    @staticmethod
    def _database_count(path: Path) -> int:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA query_only = ON")
            row = connection.execute(
                "SELECT COUNT(*) FROM email_analysis"
            ).fetchone()
            return int(row[0])
        finally:
            connection.close()
