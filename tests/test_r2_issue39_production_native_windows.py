from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_issue39_orchestrator.production_native import (
    create_directory_no_replace,
    move_no_replace,
)
from backend.r2_issue39_orchestrator.production_repository import (
    relocate_repository,
    repository_exact,
    repository_partial,
    review_repository_manifest,
)
from backend.r2_issue39_orchestrator.roster import (
    Issue39RosterStatusV1,
    _prepare_roster_v1,
    _validated_snapshot,
)
from backend.r2_issue39_orchestrator.roster_windows import production_roster_ports


@unittest.skipUnless(os.name == "nt", "Windows native Issue #39 operations")
class Issue39ProductionNativeWindowsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_native_create_and_move_are_no_replace_and_identity_preserving(self):
        source = self.root / "source"
        identity = create_directory_no_replace(self.root, source)
        target = self.root / "target"

        moved = move_no_replace(source, target)

        self.assertEqual(moved, identity)
        self.assertFalse(source.exists())
        self.assertTrue(target.is_dir())
        collision = self.root / "collision"
        collision.mkdir()
        with self.assertRaises(ValueError):
            move_no_replace(target, collision)
        self.assertTrue(target.is_dir())
        self.assertTrue(collision.is_dir())

    def test_repository_partial_prefix_is_classified_and_resumable(self):
        legacy = self.root / "legacy"
        main = self.root / "container" / "main"
        legacy.mkdir()
        main.mkdir(parents=True)
        (legacy / "docs").mkdir()
        (legacy / "alpha.txt").write_bytes(b"anonymous alpha\n")
        (legacy / "docs" / "beta.txt").write_bytes(b"anonymous beta\n")
        self._git(legacy, "init")
        self._git(legacy, "config", "user.email", "synthetic@example.test")
        self._git(legacy, "config", "user.name", "Synthetic")
        self._git(legacy, "add", "alpha.txt", "docs/beta.txt")
        self._git(legacy, "commit", "-m", "synthetic")
        manifest = review_repository_manifest(legacy)
        action = SimpleNamespace(
            action_name="repository_relocation",
            action_fingerprint="a" * 64,
        )
        host = SimpleNamespace(
            _layout=SimpleNamespace(legacy=legacy, main=main),
            _repository=manifest,
        )
        from backend.r2_issue39_orchestrator import production_repository

        native_move = production_repository.move_no_replace
        calls = {"count": 0}

        def crash_after_first(source, target):
            native_move(source, target)
            calls["count"] += 1
            if calls["count"] == 1:
                raise SystemExit("synthetic durable cut")

        with patch.object(
            production_repository, "move_no_replace", crash_after_first
        ):
            with self.assertRaises(SystemExit):
                relocate_repository(host, "forward")

        partial = repository_partial(host, action, "forward")
        self.assertEqual(len(partial), 64)

        relocate_repository(host, "forward")
        self.assertTrue(repository_exact(host))
        relocate_repository(host, "rollback")
        self.assertTrue(repository_exact(host, reverse=True))

    def test_reparse_source_is_rejected_without_touching_target(self):
        real = self.root / "real"
        real.mkdir()
        link = self.root / "link"
        try:
            os.symlink(real, link, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"symlink privilege unavailable: {error}")
        target = self.root / "target"
        with self.assertRaises(ValueError):
            move_no_replace(link, target)
        self.assertTrue(link.exists())
        self.assertFalse(target.exists())

    def test_real_git_linked_worktrees_relocate_and_restore_exact_roster(self):
        source = self.root / "repository"
        legacy = self.root / "legacy"
        failed = self.root / "failed"
        container = source
        main = container / "main"
        worktrees = container / "Worktrees"
        embedded = source / ".worktrees" / "embedded"
        external = self.root / "external"
        source.mkdir()
        (source / "tracked.txt").write_bytes(b"anonymous tracked\n")
        self._git(source, "init")
        self._git(source, "config", "user.email", "synthetic@example.test")
        self._git(source, "config", "user.name", "Synthetic")
        self._git(source, "config", "core.autocrlf", "false")
        info = source / ".git" / "info" / "exclude"
        with info.open("ab") as stream:
            stream.write(b"/.worktrees/\n")
        self._git(source, "add", "tracked.txt")
        self._git(source, "commit", "-m", "synthetic")
        self._git(source, "worktree", "add", "-b", "embedded-test", str(embedded))
        self._git(source, "worktree", "add", "-b", "external-test", str(external))
        ports = production_roster_ports()
        discovered = ports.discover(source)
        self.assertEqual(len(discovered), 2)
        self.assertEqual(self._git_output(embedded, "status", "--porcelain=v2", "-z", "--untracked-files=all"), b"")
        self.assertEqual(self._git_output(external, "status", "--porcelain=v2", "-z", "--untracked-files=all"), b"")
        self.assertEqual(
            {item.placement: item.clean for item in discovered},
            {"embedded": True, "external": True},
        )
        self.assertEqual(len({item.identity_fingerprint for item in discovered}), 2)
        self.assertEqual(len({item.common_fingerprint for item in discovered}), 1)
        _validated_snapshot(discovered)
        roster = _prepare_roster_v1(root=source, ports=ports)
        self.assertIs(roster.status, Issue39RosterStatusV1.PREPARED)
        self.assertEqual(roster.counts(), (2, 1, 1))
        repository = review_repository_manifest(source)
        from backend.r2_issue39_orchestrator.production_service import (
            observe_legacy_service,
        )

        legacy_service = observe_legacy_service(source)
        layout = SimpleNamespace(
            source=source, legacy=legacy, container=container,
            failed=failed, main=main, worktrees=worktrees,
        )
        prepared = SimpleNamespace(
            _roster=roster, prepare_fingerprint="a" * 64
        )
        host = SimpleNamespace(
            _layout=layout,
            _repository=repository,
            _prepared=prepared,
            _legacy_service=legacy_service,
        )
        move_no_replace(source, legacy)
        create_directory_no_replace(self.root, container)
        create_directory_no_replace(container, main)
        create_directory_no_replace(container, worktrees)
        relocate_repository(host, "forward")
        from backend.r2_issue39_orchestrator.production_foundation import (
            mutate_foundation,
            mutate_worktree,
        )
        from backend.r2_issue39_orchestrator.production_roster_reverify import (
            legacy_roster_fingerprint,
            reverify_evolving_roster,
            terminal_roster_fingerprint,
        )

        actions = tuple(
            SimpleNamespace(
                action_name=f"worktree_reconstruction_{index:02d}",
                action_fingerprint=f"{index:064x}",
            )
            for index in range(1, 3)
        )
        for action in actions:
            mutate_worktree(host, action, "forward")
        self.assertEqual(len(terminal_roster_fingerprint(host)), 64)
        for action in reversed(actions):
            reverify_evolving_roster(host, action, "rollback")
            mutate_worktree(host, action, "rollback")
            reverify_evolving_roster(host, action, "rollback")
        relocate_repository(host, "rollback")
        from backend.r2_issue39_orchestrator.production_audit import (
            _TOP,
            _legacy_facts,
        )

        for name in _TOP:
            (container / name).mkdir(exist_ok=True)
        move_no_replace(container, failed)
        mutate_foundation(
            host,
            SimpleNamespace(action_name="legacy_anchor_rename"),
            "rollback",
            None,
        )
        self.assertEqual(len(legacy_roster_fingerprint(host)), 64)
        from backend.cutover_repository_transaction.windows_identity import (
            directory_identity,
        )
        from backend.r2_issue39_orchestrator.production_audit import (
            _plain_directory,
        )
        from backend.r2_issue39_orchestrator.production_foundation import (
            _legacy_matches_preimage,
        )

        self.assertEqual(layout.container, layout.source)
        self.assertFalse(os.path.lexists(layout.legacy))
        self.assertTrue(_plain_directory(layout.source))
        self.assertTrue(_plain_directory(layout.failed))
        self.assertEqual(
            directory_identity(layout.source),
            host._repository.source_identity_fingerprint,
        )
        self.assertTrue(repository_exact(host, reverse=True))
        self.assertTrue(_legacy_matches_preimage(host))
        facts = _legacy_facts(
            host,
            SimpleNamespace(catalog_fingerprint="b" * 64),
            "c" * 64,
        )
        self.assertEqual(facts["cleanup_count"], 0)

    def test_acl_partial_prefix_is_exactly_classified_and_resumed(self):
        container = self.root / "container"
        main = container / "main"
        archive = self.root / "archive"
        main.mkdir(parents=True)
        archive.mkdir()
        host = SimpleNamespace(
            _layout=SimpleNamespace(container=container, main=main),
            _closure=SimpleNamespace(
                production=SimpleNamespace(binding_fingerprint="b" * 64)
            ),
        )
        action = SimpleNamespace(
            action_name="acl_whole_tree_conformance",
            action_fingerprint="c" * 64,
        )
        from backend.r2_issue39_orchestrator import production_acl

        native_apply = production_acl.apply_exact_dacl
        calls = {"count": 0}

        def crash_after_first(*args, **kwargs):
            result = native_apply(*args, **kwargs)
            calls["count"] += 1
            if calls["count"] == 1:
                raise SystemExit("synthetic ACL durable cut")
            return result

        with patch.object(production_acl, "_ROOT", archive), patch.object(
            production_acl, "apply_exact_dacl", crash_after_first
        ):
            with self.assertRaises(SystemExit):
                production_acl.apply_fixed_acl(host)
            partial = production_acl.acl_partial_state(host, action)
        self.assertEqual(len(partial), 64)

        with patch.object(production_acl, "_ROOT", archive):
            production_acl.apply_fixed_acl(host)
            self.assertTrue(production_acl.fixed_acl_conforms(host))
            production_acl.restore_original_acl(host)
            self.assertTrue(production_acl.original_acl_restored(host))

    def test_validation_process_observer_binds_image_command_and_start_time(self):
        command = [
            sys.executable, "-I", "-B", "-c",
            "import time;time.sleep(20)",
        ]
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            close_fds=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self.addCleanup(self._stop_process, process)
        from backend.r2_issue39_orchestrator.production_service import (
            _command_hash,
            _observe_process,
        )

        observed = _observe_process(process.pid)

        self.assertIsNotNone(observed)
        self.assertEqual(Path(observed.image), Path(sys.executable))
        self.assertEqual(observed.command_hash, _command_hash(command))
        self.assertGreater(observed.creation_time, 0)

    def test_four_managed_publishers_complete_and_reverse_in_synthetic_root(self):
        managed = self.root / "managed"
        runtimes = managed / "Runtimes"
        local_data = managed / "LocalData"
        artifacts = managed / "Artifacts"
        config = managed / "Config"
        legacy = self.root / "legacy"
        crx_source = legacy / "frontend" / "browser_extension.crx"
        for path in (runtimes, local_data, artifacts, config):
            path.mkdir(parents=True, exist_ok=True)
        crx_source.parent.mkdir(parents=True)
        crx_source.write_bytes(b"synthetic crx bytes\n")
        database_source = self.root / "historical.sqlite3"
        connection = sqlite3.connect(database_source)
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
        from backend.r2_issue39_orchestrator.input_identity import (
            file_identity_fingerprint,
        )
        from backend.r2_issue39_orchestrator.production_inputs import (
            verify_fixed_production_inputs_v1,
        )
        inputs = verify_fixed_production_inputs_v1()
        inputs = replace(
            inputs,
            database_identity_fingerprint=file_identity_fingerprint(database_source),
            crx_fingerprint=__import__("hashlib").sha256(
                crx_source.read_bytes()
            ).hexdigest(),
        )
        repository = Path(__file__).resolve().parents[1]
        layout = SimpleNamespace(
            main=repository, legacy=legacy,
            runtime_stage=runtimes / "venv.prepare",
            runtime_target=runtimes / "venv",
            database_stage=local_data / "email_agent.sqlite3.prepare",
            database_target=local_data / "email_agent.sqlite3",
            crx_stage=artifacts / "email-ai-assistant.crx.prepare",
            crx_target=artifacts / "email-ai-assistant.crx",
            config_stage=config / "settings.env.prepare",
            config_target=config / "settings.env",
        )
        actions = tuple(
            SimpleNamespace(
                action_name=f"{unit}_{phase}",
                action_fingerprint=f"{index:064x}",
            )
            for index, (unit, phase) in enumerate(
                (
                    (unit, phase)
                    for unit in ("runtime", "database", "crx", "config")
                    for phase in ("prepare", "publish")
                ),
                start=1,
            )
        )
        host = SimpleNamespace(
            _layout=layout,
            _prepared=SimpleNamespace(_inputs=inputs),
            _catalog=SimpleNamespace(actions=actions),
        )
        from backend.r2_issue39_orchestrator import (
            production_database,
            production_managed,
        )

        with patch.object(
            production_database, "database_source", lambda: database_source
        ):
            for action in actions:
                production_managed.mutate_managed(
                    host, action, "forward", action.action_fingerprint
                )
            for unit in ("runtime", "database", "crx", "config"):
                self.assertTrue(
                    production_managed._exact(
                        unit, getattr(layout, unit + "_target"), host
                    )
                )
            runtime_probe = subprocess.run(
                [str(layout.runtime_target / "Scripts" / "python.exe"),
                 "-X", "frozen_modules=on", "-I", "-B", "-S", "-c",
                 "import sys;print(sys.version.split()[0])"],
                cwd=layout.runtime_target, stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=20, check=False,
            )
            self.assertEqual(
                (runtime_probe.returncode, runtime_probe.stdout),
                (0, b"3.12.13\r\n"),
                runtime_probe.stderr[:2000],
            )
            for action in reversed(actions):
                production_managed.mutate_managed(
                    host, action, "rollback", action.action_fingerprint
                )
            for unit in ("runtime", "database", "crx", "config"):
                self.assertFalse(getattr(layout, unit + "_target").exists())
                self.assertFalse(getattr(layout, unit + "_stage").exists())

    def test_database_identity_marker_survives_activation_write_and_reverse(self):
        from backend.r2_issue39_orchestrator import (
            production_database,
            production_host_state,
            production_managed,
        )
        from backend.r2_issue39_orchestrator.action_catalog import (
            build_fixed_production_action_catalog_v1,
        )
        from backend.r2_issue39_orchestrator.input_identity import (
            file_identity_fingerprint,
        )
        from backend.r2_issue39_orchestrator.production_handlers import (
            build_fixed_action_handlers_v1,
        )
        from backend.r2_issue39_orchestrator.production_inputs import (
            verify_fixed_production_inputs_v1,
        )
        from tests.test_r2_issue39_action_runner_windows import _prepared

        source = self.root / "historical.sqlite3"
        connection = sqlite3.connect(source)
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
        self.assertEqual(source.stat().st_size, 12_288)
        prepared = _prepared()
        object.__setattr__(
            prepared,
            "_inputs",
            replace(
                verify_fixed_production_inputs_v1(),
                database_identity_fingerprint=file_identity_fingerprint(source),
            ),
        )
        catalog = build_fixed_production_action_catalog_v1(prepared)
        prepare = next(
            item for item in catalog.actions if item.action_name == "database_prepare"
        )
        publish = next(
            item for item in catalog.actions if item.action_name == "database_publish"
        )
        stage = self.root / "container" / "LocalData" / "email.sqlite3.prepare"
        target = stage.with_name("email.sqlite3")
        stage.parent.mkdir(parents=True)
        stage.write_bytes(source.read_bytes())
        handlers = build_fixed_action_handlers_v1(catalog)
        host = SimpleNamespace(
            _prepared=prepared,
            _catalog=catalog,
            _layout=SimpleNamespace(database_stage=stage, database_target=target),
            _closure=SimpleNamespace(
                production=SimpleNamespace(binding_fingerprint="b" * 64)
            ),
        )
        host._handler = lambda action: handlers[action.action_fingerprint]
        state_root = self.root / "incident"
        state_root.mkdir()

        with (
            patch.object(production_host_state, "_ROOT", state_root),
            patch.object(production_database, "database_source", lambda: source),
        ):
            production_host_state.seal_action(host, prepare, "forward")
            move_no_replace(stage, target)
            production_host_state.seal_action(host, publish, "forward")
            connection = sqlite3.connect(target)
            try:
                connection.execute(
                    "INSERT INTO email_analysis(subject,sender,analysis_json) "
                    "VALUES('Synthetic delivery question','buyer@example.test','{}')"
                )
                connection.commit()
            finally:
                connection.close()

            self.assertEqual(
                production_host_state.observe_action(host, publish),
                publish.post_state_fingerprint,
            )
            production_managed.mutate_managed(
                host, publish, "rollback", publish.action_fingerprint
            )
            production_host_state.seal_action(host, publish, "rollback")
            self.assertEqual(
                production_host_state.observe_action(host, publish),
                publish.pre_state_fingerprint,
            )
            self.assertEqual(
                production_host_state.observe_action(host, prepare),
                prepare.post_state_fingerprint,
            )
            production_managed.mutate_managed(
                host, prepare, "rollback", prepare.action_fingerprint
            )
            production_host_state.seal_action(host, prepare, "rollback")
            self.assertEqual(
                production_host_state.observe_action(host, prepare),
                prepare.pre_state_fingerprint,
            )

    def test_terminal_database_fact_is_stable_with_live_sqlite_writer(self):
        from backend.r2_issue39_orchestrator.production_audit import _file_fact

        database = self.root / "live.sqlite3"
        connection = sqlite3.connect(database)
        try:
            connection.execute("CREATE TABLE facts(value TEXT NOT NULL)")
            connection.execute("INSERT INTO facts(value) VALUES('anonymous')")
            connection.commit()
            connection.execute("BEGIN IMMEDIATE")

            with self.assertRaises(Exception):
                _file_fact(database, 1024 * 1024)
            fact = _file_fact(database, 1024 * 1024, deny_write=False)
        finally:
            connection.rollback()
            connection.close()

        self.assertEqual(fact["size"], database.stat().st_size)
        self.assertEqual(len(fact["sha256"]), 64)

    def test_legacy_audit_accepts_restored_source_at_container_alias(self):
        from backend.cutover_repository_transaction.windows_identity import (
            directory_identity,
        )
        from backend.r2_issue39_orchestrator.production_audit import (
            _TOP,
            _legacy_facts,
        )

        source = self.root / "email_ai_assistant"
        failed = self.root / "FailedContainerV1"
        (source / ".git").mkdir(parents=True)
        failed.mkdir()
        for name in _TOP:
            (failed / name).mkdir()
        layout = SimpleNamespace(
            source=source,
            container=source,
            legacy=self.root / "LegacySourceAnchorV1",
            failed=failed,
        )
        host = SimpleNamespace(
            _layout=layout,
            _prepared=SimpleNamespace(prepare_fingerprint="a" * 64),
            _repository=SimpleNamespace(
                source_identity_fingerprint=directory_identity(source),
                manifest_fingerprint="b" * 64,
            ),
            _legacy_service={
                "status": "STOPPED",
                "image": "D:/synthetic/python.exe",
                "command_hash": "c" * 64,
            },
        )
        catalog = SimpleNamespace(catalog_fingerprint="d" * 64)

        with (
            patch(
                "backend.r2_issue39_orchestrator.production_foundation._legacy_matches_preimage",
                return_value=True,
            ),
            patch(
                "backend.r2_issue39_orchestrator.production_repository.repository_exact",
                return_value=True,
            ),
            patch(
                "backend.r2_issue39_orchestrator.production_roster_reverify.legacy_roster_fingerprint",
                return_value="e" * 64,
            ),
        ):
            facts = _legacy_facts(host, catalog, "f" * 64)

        self.assertEqual(facts["source_identity"], directory_identity(source))
        self.assertEqual(facts["cleanup_count"], 0)

    def test_main_publication_marker_survives_later_zone_creation(self):
        from backend.r2_issue39_orchestrator import production_host_state
        from backend.r2_issue39_orchestrator.action_catalog import (
            build_fixed_production_action_catalog_v1,
        )
        from backend.r2_issue39_orchestrator.production_handlers import (
            build_fixed_action_handlers_v1,
        )
        from tests.test_r2_issue39_action_runner_windows import _prepared

        container = self.root / "email_ai_assistant"
        main = container / "main"
        main.mkdir(parents=True)
        catalog = build_fixed_production_action_catalog_v1(_prepared())
        action = next(
            item for item in catalog.actions if item.action_name == "main_publication"
        )
        handlers = build_fixed_action_handlers_v1(catalog)
        host = SimpleNamespace(
            _layout=SimpleNamespace(container=container, main=main),
            _closure=SimpleNamespace(
                production=SimpleNamespace(binding_fingerprint="b" * 64)
            ),
        )
        host._handler = lambda item: handlers[item.action_fingerprint]
        state_root = self.root / "incident"
        state_root.mkdir()

        with patch.object(production_host_state, "_ROOT", state_root):
            production_host_state.seal_action(host, action, "forward")
            (container / "Runtimes").mkdir()
            self.assertEqual(
                production_host_state.observe_action(host, action),
                action.post_state_fingerprint,
            )

    def test_container_marker_survives_children_and_failed_retention(self):
        from backend.r2_issue39_orchestrator import production_host_state
        from backend.r2_issue39_orchestrator.action_catalog import (
            build_fixed_production_action_catalog_v1,
        )
        from backend.r2_issue39_orchestrator.production_handlers import (
            build_fixed_action_handlers_v1,
        )
        from tests.test_r2_issue39_action_runner_windows import _prepared

        container = self.root / "email_ai_assistant"
        legacy = self.root / "LegacySourceAnchorV1"
        failed = self.root / "FailedContainerV1"
        container.mkdir()
        legacy.mkdir()
        catalog = build_fixed_production_action_catalog_v1(_prepared())
        action = next(
            item
            for item in catalog.actions
            if item.action_name == "container_publication"
        )
        handlers = build_fixed_action_handlers_v1(catalog)
        host = SimpleNamespace(
            _layout=SimpleNamespace(
                container=container, legacy=legacy, failed=failed
            ),
            _closure=SimpleNamespace(
                production=SimpleNamespace(binding_fingerprint="b" * 64)
            ),
        )
        host._handler = lambda item: handlers[item.action_fingerprint]
        state_root = self.root / "incident"
        state_root.mkdir()

        with patch.object(production_host_state, "_ROOT", state_root):
            production_host_state.seal_action(host, action, "forward")
            (container / "main").mkdir()
            self.assertEqual(
                production_host_state.observe_action(host, action),
                action.post_state_fingerprint,
            )
            move_no_replace(container, failed)
            production_host_state.seal_action(host, action, "rollback")
            self.assertEqual(
                production_host_state.observe_action(host, action),
                action.pre_state_fingerprint,
            )

    @staticmethod
    def _git(cwd, *arguments):
        completed = subprocess.run(
            ["git", *arguments], cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=20, check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.decode("utf-8", "replace"))

    @staticmethod
    def _git_output(cwd, *arguments):
        completed = subprocess.run(
            ["git", *arguments], cwd=cwd, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=20, check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(completed.stderr.decode("utf-8", "replace"))
        return completed.stdout

    @staticmethod
    def _stop_process(process):
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
