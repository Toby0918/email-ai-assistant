from __future__ import annotations

import hashlib
import os
import sqlite3
import subprocess
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_issue39_orchestrator.action_catalog import (
    build_fixed_production_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.action_runner import (
    Issue39ActionRunStatusV1,
    _Issue39ActionRunnerPortsV1,
    _run_issue39_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.durable_ledger import (
    Issue39LedgerStatusV1,
    _Issue39LedgerLocationV1,
    _create_issue39_ledger_v1,
    _reopen_issue39_ledger_v1,
)
from backend.r2_issue39_orchestrator.input_identity import (
    file_identity_fingerprint,
)
from backend.r2_issue39_orchestrator.preparation import (
    Issue39PrepareStatusV1,
    _allocate_prepared_execution_v1,
    _prepare_fingerprint,
)
from backend.r2_issue39_orchestrator.production_handlers import (
    build_fixed_action_handlers_v1,
)
from backend.r2_issue39_orchestrator.production_host import (
    FixedIssue39WindowsHostV1,
)
from backend.r2_issue39_orchestrator.production_inputs import (
    verify_fixed_production_inputs_v1,
)
from backend.r2_issue39_orchestrator.production_repository import (
    review_repository_manifest,
)
from backend.r2_issue39_orchestrator.production_service import (
    _port_owner,
    observe_legacy_service,
    stop_validation_service,
)
from backend.r2_issue39_orchestrator.readiness import _observation
from backend.r2_issue39_orchestrator.roster import (
    Issue39BoundRosterV1,
    Issue39RosterStatusV1,
    _prepare_roster_v1,
)
from backend.r2_issue39_orchestrator.roster_windows import production_roster_ports
from backend.r2_transaction_journal_v2 import R2TransactionJournalV2
from tests.test_r2_issue39_action_runner_windows import _Confirmer
from tests.test_r2_transaction_journal_v2 import (
    _binding,
    _genesis,
    _live_append_observation,
)


@unittest.skipUnless(os.name == "nt", "Windows production synthetic flow")
class Issue39ProductionFlowWindowsTest(unittest.TestCase):
    def setUp(self):
        if _port_owner() is not None:
            self.skipTest("fixed validation port is occupied")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.projects = Path(self.temporary.name)

    def test_fixed_production_graph_completes_27_actions_in_test_owned_layout(self):
        source = self.projects / "email_ai_assistant"
        self._git_clone(source)
        self._configure_synthetic_repository(source)
        roster = _prepare_roster_v1(
            root=source, ports=production_roster_ports()
        )
        self.assertIs(roster.status, Issue39RosterStatusV1.PREPARED)
        self.assertEqual(roster.counts(), (6, 2, 4))
        roster = Issue39BoundRosterV1(
            Issue39RosterStatusV1.VERIFIED, roster.worktrees,
            roster.roster_fingerprint, roster._root, roster._snapshot,
        )
        historical = self.projects / "historical.sqlite3"
        self._historical_database(historical)
        crx = source / "frontend" / "browser_extension.crx"
        crx.write_bytes(b"synthetic crx bytes\n")
        inputs = replace(
            verify_fixed_production_inputs_v1(),
            database_identity_fingerprint=file_identity_fingerprint(historical),
            crx_fingerprint=hashlib.sha256(crx.read_bytes()).hexdigest(),
        )
        readiness = _observation(True, True, True, "d" * 64)
        prepared = _allocate_prepared_execution_v1(
            Issue39PrepareStatusV1.VERIFIED, "0" * 64,
            *roster.counts(), readiness, inputs, roster,
        )
        object.__setattr__(
            prepared, "prepare_fingerprint",
            _prepare_fingerprint(readiness, inputs, roster),
        )
        catalog = build_fixed_production_action_catalog_v1(prepared)
        self.assertEqual(catalog.action_count, 27)
        binding = _binding()
        closure = SimpleNamespace(production=binding)
        layout = self._layout(source)
        host = object.__new__(FixedIssue39WindowsHostV1)
        values = {
            "_prepared": prepared,
            "_closure": closure,
            "_catalog": catalog,
            "_package": object(),
            "_preflight": object(),
            "_layout": layout,
            "_repository": review_repository_manifest(source),
            "_legacy_service": observe_legacy_service(source),
            "_handlers": build_fixed_action_handlers_v1(catalog),
        }
        for name, value in values.items():
            object.__setattr__(host, name, value)
        journal = R2TransactionJournalV2.create(
            binding=binding, genesis=_genesis(binding),
            **_live_append_observation(),
        )
        location = _Issue39LedgerLocationV1(
            self.projects / f".issue39-ledger-{binding.binding_fingerprint}"
        )
        created = _create_issue39_ledger_v1(
            location=location, binding=binding, journal=journal
        )
        self.assertIs(created.status, Issue39LedgerStatusV1.CREATED)
        confirmer = _Confirmer(binding, catalog)
        ports = _Issue39ActionRunnerPortsV1(
            confirmer.confirm, host.observe, host.apply, host.reverify,
            host.recovery_inspect, confirmer.clock, confirmer.confirm_terminal,
            host.terminal_audit, host.legacy_audit, host.partial, host.evidence,
        )
        from backend.r2_issue39_orchestrator import (
            production_acl,
            production_database,
            production_host_state,
            production_managed,
            production_bootstrap,
        )
        state_root = self.projects / "incident"
        state_root.mkdir()
        self.addCleanup(self._stop_test_service, host, state_root)
        with (
            patch.object(production_acl, "_ROOT", state_root),
            patch.object(production_host_state, "_ROOT", state_root),
            patch.object(production_database, "database_source", lambda: historical),
            patch.object(production_bootstrap, "_LEDGER_PARENT", self.projects),
        ):
            self.assertTrue(host.reverify(catalog.actions[0], "forward"))
            self.assertEqual(
                host.observe(catalog.actions[0]),
                catalog.actions[0].pre_state_fingerprint,
            )
            result = _run_issue39_action_catalog_v1(
                catalog=catalog, binding=binding,
                location=location, ports=ports,
            )
            reopened = _reopen_issue39_ledger_v1(
                location=location, binding=binding
            )
            if result.status is not Issue39ActionRunStatusV1.SUCCEEDED:
                logs = tuple(
                    (path.name, path.read_bytes()[:4000])
                    for path in sorted(layout.logs.glob("*.log"))
                ) if layout.logs.exists() else ()
                journal_tail = () if reopened.journal is None else tuple(
                    (record.record_sequence, record.record_type.value)
                    for record in reopened.journal.records[-6:]
                )
                self.fail(
                    (
                        result.status,
                        result.committed,
                        reopened.status,
                        journal_tail,
                        logs,
                    )
                )
            self.assertIs(
                result.status, Issue39ActionRunStatusV1.SUCCEEDED,
                (
                    result.committed, result.reversed, result.host_actions,
                    reopened.status,
                    None if reopened.journal is None else (
                        reopened.journal.next_legal_action,
                        tuple(record.record_type.value for record in reopened.journal.records),
                    ),
                ),
            )
            self.assertIsNotNone(_port_owner())
            self.assertTrue((layout.main / ".git").is_dir())
            self.assertTrue(layout.runtime_target.is_dir())
            self.assertTrue(layout.database_target.is_file())
            reversed_names = self._reverse_production_handlers(host, catalog)
            self.assertIsNone(_port_owner())
            legacy_audit = host.legacy_audit(
                catalog, result.journal.current_head_fingerprint
            )

        self.assertIs(result.status, Issue39ActionRunStatusV1.SUCCEEDED)
        self.assertEqual((result.committed, result.reversed), (27, 0))
        self.assertEqual(result.host_actions, 24)
        self.assertEqual(len(reversed_names), 24)
        self.assertEqual(legacy_audit.minimal_read_count, 2)
        self.assertTrue((layout.source / ".git").is_dir())
        self.assertTrue(layout.failed.is_dir())
        self.assertFalse(layout.legacy.exists())

    def _layout(self, source):
        container = source
        runtimes = container / "Runtimes"
        local_data = container / "LocalData"
        artifacts = container / "Artifacts"
        config = container / "Config"
        return SimpleNamespace(
            projects=self.projects, source=source,
            legacy=self.projects / "LegacySourceAnchorV1",
            container=container, failed=self.projects / "FailedContainerV1",
            main=container / "main", runtimes=runtimes,
            local_data=local_data, runtime_temp=container / "RuntimeTemp",
            logs=container / "Logs", artifacts=artifacts,
            worktrees=container / "Worktrees", config=config,
            operator_private=container / "OperatorPrivate",
            runtime_stage=runtimes / "venv.prepare",
            runtime_target=runtimes / "venv",
            database_stage=local_data / "email_agent.sqlite3.prepare",
            database_target=local_data / "email_agent.sqlite3",
            crx_stage=artifacts / "email-ai-assistant.crx.prepare",
            crx_target=artifacts / "email-ai-assistant.crx",
            config_stage=config / "settings.env.prepare",
            config_target=config / "settings.env",
        )

    def _git_clone(self, target):
        repository = Path(__file__).resolve().parents[1]
        self._git(
            self.projects, "-c", "core.autocrlf=false", "clone",
            "--no-hardlinks", str(repository), str(target),
        )
        self._git(target, "config", "user.email", "synthetic@example.test")
        self._git(target, "config", "user.name", "Synthetic")
        self._git(target, "config", "core.autocrlf", "false")

    def _configure_synthetic_repository(self, source):
        repository = Path(__file__).resolve().parents[1]
        shutil.copyfile(
            repository / "scripts" / "run_local_debug.py",
            source / "scripts" / "run_local_debug.py",
        )
        self._git(source, "add", "scripts/run_local_debug.py")
        self._git(source, "commit", "-m", "synthetic issue39 entry")
        info = source / ".git" / "info" / "exclude"
        with info.open("ab") as stream:
            stream.write(b"/.worktrees/\n/frontend/browser_extension.crx\n")
        for index in range(1, 7):
            target = (
                source / ".worktrees" / f"embedded_{index:02d}"
                if index <= 2
                else self.projects / f"external_{index:02d}"
            )
            self._git(
                source, "worktree", "add", "-b", f"synthetic-{index:02d}",
                str(target),
            )

    @staticmethod
    def _historical_database(path):
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "CREATE TABLE email_analysis ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, subject TEXT NOT NULL, "
                "sender TEXT NOT NULL, analysis_json TEXT NOT NULL, "
                "created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            connection.execute(
                "INSERT INTO email_analysis(subject,sender,analysis_json) "
                "VALUES('anonymous','anonymous','{}')"
            )
            connection.commit()
        finally:
            connection.close()
        if path.stat().st_size != 12_288:
            raise AssertionError("synthetic database size drift")

    @staticmethod
    def _git(cwd, *arguments):
        completed = subprocess.run(
            ["git", *arguments], cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=60, check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.decode("utf-8", "replace"))

    @staticmethod
    def _stop_test_service(host, state_root=None):
        try:
            if state_root is None:
                stop_validation_service(host, {"start_a", "stop_a", "start_b"})
                return
            from backend.r2_issue39_orchestrator import production_host_state

            with patch.object(production_host_state, "_ROOT", state_root):
                stop_validation_service(host, {"start_a", "stop_a", "start_b"})
        except Exception:
            pass

    def _reverse_production_handlers(self, host, catalog):
        names = []
        for action in reversed(catalog.actions):
            if not action.host_effect:
                continue
            try:
                host.reverify(action, "rollback")
                self.assertEqual(
                    host.observe(action), action.post_state_fingerprint
                )
                host.apply(action, "rollback", "e" * 64)
                self.assertEqual(
                    host.observe(action), action.pre_state_fingerprint
                )
            except Exception as error:
                raise AssertionError(
                    ("reverse_action_failed", action.action_name)
                ) from error
            names.append(action.action_name)
        return tuple(names)

if __name__ == "__main__":
    unittest.main()
