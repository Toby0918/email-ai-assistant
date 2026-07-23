"""Tests for provider-disabled Managed Container Mode."""

from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from backend.email_agent.managed_runtime import (
    ManagedRuntimeError,
    managed_failure_code,
    prepare_managed_runtime,
)
from backend.email_agent.server import create_server
from backend.project_layout import PlacementError
from scripts import manage_local_service as manager


MANAGED_ZONE_NAMES = (
    "Runtimes",
    "LocalData",
    "RuntimeTemp",
    "Logs",
    "Artifacts",
    "Worktrees",
    "Config",
)


class ManagedContainerModeTests(unittest.TestCase):
    def test_managed_failure_mapping_never_echoes_unreviewed_exception(
        self,
    ) -> None:
        class HostileError(RuntimeError):
            @property
            def code(self) -> str:
                raise RuntimeError("D:/private/credential.txt")

        class CodedError(RuntimeError):
            def __init__(self, code: str) -> None:
                self.code = code
                super().__init__("untrusted native detail")

        self.assertEqual(
            managed_failure_code(HostileError("D:/private/secret")),
            "managed_runtime_invalid",
        )
        self.assertEqual(
            managed_failure_code(CodedError("managed_relationship_invalid")),
            "managed_relationship_invalid",
        )
        self.assertEqual(
            managed_failure_code(CodedError("D:/private/credential.txt")),
            "managed_runtime_invalid",
        )

    def test_invalid_placement_fails_before_managed_config_is_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container = Path(temporary_directory) / "wrong_container"
            repository_root = project_container / "main"
            configuration_root = project_container / "Config"
            repository_root.mkdir(parents=True)
            configuration_root.mkdir()
            (configuration_root / "settings.env").write_text(
                "OPENAI_API_KEY=your_api_key_here\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                PlacementError,
                "^managed_relationship_invalid$",
            ):
                prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )


    def test_prepared_runtime_routes_every_ordinary_path_to_approved_zone(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )

            runtime = prepare_managed_runtime(
                repository_root=repository_root,
                project_container=project_container,
            )

            self.assertEqual(
                runtime.database_path,
                project_container / "LocalData" / "email_agent.sqlite3",
            )
            self.assertEqual(
                runtime.attachment_temp_dir,
                project_container / "RuntimeTemp" / "attachment_temp",
            )
            self.assertEqual(
                runtime.log_file,
                project_container / "Logs" / "local_debug_service.log",
            )
            self.assertEqual(
                runtime.pid_file,
                project_container / "Logs" / "local_debug_service.pid",
            )
            self.assertEqual(
                runtime.python_executable,
                project_container
                / "Runtimes"
                / "venv"
                / "Scripts"
                / "python.exe",
            )
            self.assertEqual(
                runtime.layout.artifact_root,
                project_container / "Artifacts",
            )
            self.assertEqual(
                runtime.layout.worktree_root,
                project_container / "Worktrees",
            )
            self.assertEqual(
                runtime.layout.configuration_root,
                project_container / "Config",
            )
            self.assertTrue(runtime.attachment_temp_dir.is_dir())

    def test_managed_runtime_can_be_resolved_again_after_first_startup(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )

            first = prepare_managed_runtime(
                repository_root=repository_root,
                project_container=project_container,
            )
            second = prepare_managed_runtime(
                repository_root=repository_root,
                project_container=project_container,
            )

            self.assertEqual(second, first)
            self.assertTrue(second.attachment_temp_dir.is_dir())

    def test_managed_config_accepts_only_allowlisted_non_secret_settings(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            (project_container / "Config" / "settings.env").write_text(
                "\n".join(
                    (
                        "EMAIL_AGENT_LOG_LEVEL=WARNING",
                        (
                            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS="
                            "Example.Test, Internal.Example"
                        ),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            hostile_environment = {
                "OPENAI_API_KEY": "your_api_key_here",
                "DEEPSEEK_API_KEY": "your_deepseek_api_key_here",
                "EMAIL_AGENT_LLM_PROVIDER": "openai",
                "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "deepseek",
                "EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": "true",
                "EMAIL_AGENT_SQLITE_PATH": "outside.sqlite3",
                "EMAIL_AGENT_ATTACHMENT_TEMP_DIR": "outside-temp",
            }

            with mock.patch.dict(
                "os.environ",
                hostile_environment,
                clear=False,
            ):
                runtime = prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )

            config = runtime.config
            self.assertEqual(config.log_level, "WARNING")
            self.assertEqual(
                config.internal_email_domains,
                ("example.test", "internal.example"),
            )
            self.assertEqual(config.sqlite_path, str(runtime.database_path))
            self.assertEqual(
                config.attachment_temp_dir,
                str(runtime.attachment_temp_dir),
            )
            self.assertIsNone(config.openai_api_key)
            self.assertIsNone(config.deepseek_api_key)
            self.assertEqual(config.llm_provider, "disabled")
            self.assertEqual(config.text_fallback_provider, "disabled")
            self.assertFalse(config.private_knowledge_enabled)
            self.assertEqual(config.private_knowledge_authority_root, "")
            self.assertEqual(config.private_knowledge_snapshot_path, "")
            self.assertEqual(config.attachment_retention_hours, 24)
            self.assertEqual(config.attachment_max_files, 5)
            self.assertEqual(
                config.attachment_max_file_bytes,
                10 * 1024 * 1024,
            )
            self.assertEqual(
                config.attachment_max_total_bytes,
                25 * 1024 * 1024,
            )

    def test_oversized_managed_config_fails_before_runtime_state_is_created(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            settings_file = project_container / "Config" / "settings.env"
            settings_file.write_bytes(b"#" + (b"x" * (16 * 1024)))
            attachment_temp_dir = (
                project_container / "RuntimeTemp" / "attachment_temp"
            )

            with self.assertRaisesRegex(
                ManagedRuntimeError,
                "^managed_config_invalid$",
            ):
                prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )

            self.assertFalse(attachment_temp_dir.exists())

    def test_managed_config_rejects_every_non_allowlisted_or_malformed_setting(
        self,
    ) -> None:
        invalid_settings = {
            "credential": "OPENAI_API_KEY=your_api_key_here\n",
            "provider": "EMAIL_AGENT_LLM_PROVIDER=openai\n",
            "operational_path": "EMAIL_AGENT_SQLITE_PATH=outside.sqlite3\n",
            "duplicate": (
                "EMAIL_AGENT_LOG_LEVEL=INFO\n"
                "EMAIL_AGENT_LOG_LEVEL=WARNING\n"
            ),
            "malformed": "EMAIL_AGENT_LOG_LEVEL\n",
            "invalid_domain": (
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=bad/domain\n"
            ),
        }
        for case_name, contents in invalid_settings.items():
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    project_container, repository_root = _create_managed_layout(
                        Path(temporary_directory)
                    )
                    settings_file = (
                        project_container / "Config" / "settings.env"
                    )
                    settings_file.write_text(contents, encoding="utf-8")

                    with self.assertRaises(ManagedRuntimeError) as context:
                        prepare_managed_runtime(
                            repository_root=repository_root,
                            project_container=project_container,
                        )

                    self.assertEqual(
                        str(context.exception),
                        "managed_config_invalid",
                    )
                    self.assertEqual(
                        repr(context.exception),
                        (
                            "ManagedRuntimeError("
                            "code='managed_config_invalid')"
                        ),
                    )
                    self.assertNotIn(case_name, str(context.exception))
                    self.assertNotIn(contents.strip(), repr(context.exception))

    def test_missing_managed_zone_fails_closed_without_creating_it(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory),
                excluded_zone="Logs",
            )
            missing_log_root = project_container / "Logs"

            with self.assertRaisesRegex(
                ManagedRuntimeError,
                "^managed_operational_layout_invalid$",
            ):
                prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )

            self.assertFalse(missing_log_root.exists())

    def test_managed_zone_reparse_target_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            base = Path(temporary_directory)
            project_container, repository_root = _create_managed_layout(base)
            artifact_root = project_container / "Artifacts"
            external_artifacts = base / "external-artifacts"
            external_artifacts.mkdir()
            artifact_root.rmdir()
            try:
                artifact_root.symlink_to(
                    external_artifacts,
                    target_is_directory=True,
                )
            except OSError:
                self.skipTest("directory symlink creation is unavailable")

            with self.assertRaisesRegex(
                ManagedRuntimeError,
                "^managed_operational_layout_invalid$",
            ):
                prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )

    def test_injected_windows_reparse_zone_evidence_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            artifact_root = project_container / "Artifacts"
            original_lstat = Path.lstat

            def lstat_with_reparse(path: Path) -> object:
                metadata = original_lstat(path)
                if path == artifact_root:
                    return mock.Mock(
                        st_mode=metadata.st_mode,
                        st_dev=metadata.st_dev,
                        st_ino=metadata.st_ino,
                        st_file_attributes=0x400,
                    )
                return metadata

            with mock.patch.object(
                Path,
                "lstat",
                autospec=True,
                side_effect=lstat_with_reparse,
            ):
                with self.assertRaisesRegex(
                    ManagedRuntimeError,
                    "^managed_operational_layout_invalid$",
                ):
                    prepare_managed_runtime(
                        repository_root=repository_root,
                        project_container=project_container,
                    )

    def test_managed_zone_identity_drift_during_preflight_fails_closed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            artifact_root = project_container / "Artifacts"
            original_lstat = Path.lstat
            artifact_lstat_count = 0

            def lstat_with_identity_drift(path: Path) -> object:
                nonlocal artifact_lstat_count
                metadata = original_lstat(path)
                if path != artifact_root:
                    return metadata
                artifact_lstat_count += 1
                inode_offset = 0 if artifact_lstat_count <= 2 else 1
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_dev=metadata.st_dev,
                    st_ino=metadata.st_ino + inode_offset,
                    st_file_attributes=int(
                        getattr(metadata, "st_file_attributes", 0)
                    ),
                )

            with mock.patch.object(
                Path,
                "lstat",
                autospec=True,
                side_effect=lstat_with_identity_drift,
            ):
                with self.assertRaisesRegex(
                    ManagedRuntimeError,
                    "^managed_operational_layout_invalid$",
                ):
                    prepare_managed_runtime(
                        repository_root=repository_root,
                        project_container=project_container,
                    )

    def test_missing_managed_runtime_executable_does_not_fall_back(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory),
                create_runtime_executable=False,
            )

            with self.assertRaisesRegex(
                ManagedRuntimeError,
                "^managed_runtime_invalid$",
            ):
                prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )

    def test_managed_writable_file_target_reparse_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            database_path = (
                project_container / "LocalData" / "email_agent.sqlite3"
            )
            database_path.write_bytes(b"synthetic")
            original_lstat = Path.lstat

            def lstat_with_reparse(path: Path) -> object:
                metadata = original_lstat(path)
                if path == database_path:
                    return mock.Mock(
                        st_mode=metadata.st_mode,
                        st_dev=metadata.st_dev,
                        st_ino=metadata.st_ino,
                        st_size=metadata.st_size,
                        st_mtime_ns=metadata.st_mtime_ns,
                        st_file_attributes=0x400,
                    )
                return metadata

            with mock.patch.object(
                Path,
                "lstat",
                autospec=True,
                side_effect=lstat_with_reparse,
            ):
                with self.assertRaisesRegex(
                    ManagedRuntimeError,
                    "^managed_operational_layout_invalid$",
                ):
                    prepare_managed_runtime(
                        repository_root=repository_root,
                        project_container=project_container,
                    )

    def test_managed_unwritable_file_target_fails_before_config_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            database_path = (
                project_container / "LocalData" / "email_agent.sqlite3"
            )
            database_path.write_bytes(b"synthetic")
            settings_file = project_container / "Config" / "settings.env"
            settings_file.write_text(
                "EMAIL_AGENT_LOG_LEVEL=INFO\n",
                encoding="utf-8",
            )
            original_access = __import__("os").access

            def access_with_unwritable_database(
                path: object,
                mode: int,
            ) -> bool:
                if Path(path) == database_path:
                    return False
                return original_access(path, mode)

            with (
                mock.patch(
                    (
                        "backend.email_agent."
                        "managed_runtime_validation.os.access"
                    ),
                    side_effect=access_with_unwritable_database,
                ),
                mock.patch.object(
                    Path,
                    "open",
                    autospec=True,
                    side_effect=AssertionError("Config was read"),
                ),
                self.assertRaisesRegex(
                    ManagedRuntimeError,
                    "^managed_operational_layout_invalid$",
                ),
            ):
                prepare_managed_runtime(
                    repository_root=repository_root,
                    project_container=project_container,
                )

    def test_managed_settings_reparse_file_fails_before_read(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            settings_file = project_container / "Config" / "settings.env"
            settings_file.write_text(
                "EMAIL_AGENT_LOG_LEVEL=INFO\n",
                encoding="utf-8",
            )
            original_lstat = Path.lstat

            def lstat_with_reparse(path: Path) -> object:
                metadata = original_lstat(path)
                if path == settings_file:
                    return mock.Mock(
                        st_mode=metadata.st_mode,
                        st_dev=metadata.st_dev,
                        st_ino=metadata.st_ino,
                        st_size=metadata.st_size,
                        st_file_attributes=0x400,
                    )
                return metadata

            with mock.patch.object(
                Path,
                "lstat",
                autospec=True,
                side_effect=lstat_with_reparse,
            ):
                with self.assertRaisesRegex(
                    ManagedRuntimeError,
                    "^managed_config_invalid$",
                ):
                    prepare_managed_runtime(
                        repository_root=repository_root,
                        project_container=project_container,
                    )

    def test_managed_settings_identity_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            settings_file = project_container / "Config" / "settings.env"
            settings_file.write_text(
                "EMAIL_AGENT_LOG_LEVEL=INFO\n",
                encoding="utf-8",
            )
            original_lstat = Path.lstat
            settings_lstat_count = 0

            def lstat_with_identity_drift(path: Path) -> object:
                nonlocal settings_lstat_count
                metadata = original_lstat(path)
                if path != settings_file:
                    return metadata
                settings_lstat_count += 1
                inode_offset = 0 if settings_lstat_count <= 2 else 1
                return SimpleNamespace(
                    st_mode=metadata.st_mode,
                    st_dev=metadata.st_dev,
                    st_ino=metadata.st_ino + inode_offset,
                    st_size=metadata.st_size,
                    st_mtime_ns=metadata.st_mtime_ns,
                    st_file_attributes=int(
                        getattr(metadata, "st_file_attributes", 0)
                    ),
                )

            with mock.patch.object(
                Path,
                "lstat",
                autospec=True,
                side_effect=lstat_with_identity_drift,
            ):
                with self.assertRaisesRegex(
                    ManagedRuntimeError,
                    "^managed_config_invalid$",
                ):
                    prepare_managed_runtime(
                        repository_root=repository_root,
                        project_container=project_container,
                    )

    def test_lifecycle_manager_derives_managed_state_from_its_repository_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            args = manager.build_parser().parse_args(
                ["start", "--managed-container"]
            )

            with mock.patch.object(manager, "ROOT", repository_root):
                config = manager.config_from_args(args)

            self.assertTrue(config.managed_container)
            self.assertEqual(config.root, repository_root)
            self.assertEqual(
                config.database,
                str(
                    project_container
                    / "LocalData"
                    / "email_agent.sqlite3"
                ),
            )
            self.assertEqual(
                config.attachment_temp_dir,
                project_container / "RuntimeTemp" / "attachment_temp",
            )
            self.assertEqual(
                config.log_file,
                project_container / "Logs" / "local_debug_service.log",
            )
            self.assertEqual(
                config.pid_file,
                project_container / "Logs" / "local_debug_service.pid",
            )
            self.assertEqual(
                config.python_executable,
                str(
                    project_container
                    / "Runtimes"
                    / "venv"
                    / "Scripts"
                    / "python.exe"
                ),
            )
            self.assertEqual(
                config.operational_config.llm_provider,
                "disabled",
            )

    def test_managed_start_uses_resolved_config_runtime_and_main_cwd(
        self,
    ) -> None:
        launches: list[dict[str, object]] = []
        cleanup_configs: list[object] = []

        def fake_popen(
            command: list[str],
            **kwargs: object,
        ) -> SimpleNamespace:
            launches.append(
                {
                    "command": command,
                    "cwd": kwargs["cwd"],
                    "log_name": getattr(kwargs["stdout"], "name", None),
                }
            )
            return SimpleNamespace(pid=12345)

        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            args = manager.build_parser().parse_args(
                ["start", "--managed-container"]
            )
            with mock.patch.object(manager, "ROOT", repository_root):
                config = manager.config_from_args(args)
            health_results = iter((False, True))

            with (
                mock.patch.object(
                    manager.backend_config,
                    "load_config",
                    side_effect=AssertionError("environment config loaded"),
                ) as config_loader,
                mock.patch.object(
                    manager.attachment_storage,
                    "cleanup_expired_attachments",
                    side_effect=lambda app_config: cleanup_configs.append(
                        app_config
                    )
                    or 0,
                ),
            ):
                result = manager.start_service(
                    config,
                    popen=fake_popen,
                    health_checker=lambda host, port, timeout: next(
                        health_results
                    ),
                    sleeper=lambda seconds: None,
                )

            self.assertEqual(result.exit_code, 0)
            config_loader.assert_not_called()
            self.assertEqual(cleanup_configs, [config.operational_config])
            self.assertEqual(len(launches), 1)
            launch = launches[0]
            command = launch["command"]
            self.assertEqual(command[0], config.python_executable)
            self.assertIn("--managed-container", command)
            self.assertNotIn("--database", command)
            self.assertNotIn("--standalone-state-root", command)
            self.assertEqual(
                command[2],
                str(repository_root / "scripts" / "run_local_debug.py"),
            )
            self.assertEqual(launch["cwd"], str(repository_root))
            self.assertEqual(launch["log_name"], str(config.log_file))
            self.assertEqual(config.pid_file.parent, project_container / "Logs")

    def test_synthetic_managed_layout_completes_full_local_lifecycle(
        self,
    ) -> None:
        process_id = 43210
        server_thread: threading.Thread | None = None
        server = None
        with tempfile.TemporaryDirectory() as temporary_directory:
            project_container, repository_root = _create_managed_layout(
                Path(temporary_directory)
            )
            args = manager.build_parser().parse_args(
                [
                    "start",
                    "--managed-container",
                    "--port",
                    "0",
                    "--startup-timeout",
                    "2",
                    "--poll-interval",
                    "0.01",
                ]
            )
            with mock.patch.object(manager, "ROOT", repository_root):
                config = manager.config_from_args(args)
            server = create_server(
                host=config.host,
                port=0,
                database_path=config.database,
                config=config.operational_config,
                runtime_cards=(),
            )
            server.handle_error = lambda request, client_address: None
            config = manager.ServiceConfig(
                **{
                    **config.__dict__,
                    "port": server.server_port,
                }
            )

            def read_health(host: str, port: int, timeout: float) -> bool:
                try:
                    with manager.urllib.request.urlopen(
                        f"http://{host}:{port}/api/health",
                        timeout=timeout,
                    ) as response:
                        response.read()
                        return response.status == 200
                except (OSError, manager.urllib.error.URLError):
                    return False

            def fake_popen(
                command: list[str],
                **kwargs: object,
            ) -> SimpleNamespace:
                nonlocal server_thread
                self.assertIn("--managed-container", command)
                self.assertEqual(kwargs["cwd"], str(repository_root))
                server_thread = threading.Thread(
                    target=server.serve_forever,
                    daemon=True,
                )
                server_thread.start()
                for _ in range(100):
                    if read_health(config.host, config.port, 1.0):
                        break
                    time.sleep(0.01)
                return SimpleNamespace(pid=process_id)

            def stop_server(pid: int) -> None:
                self.assertEqual(pid, process_id)
                server.shutdown()
                server.server_close()
                if server_thread is not None:
                    server_thread.join(timeout=2)

            try:
                start_result = manager.start_service(
                    config,
                    popen=fake_popen,
                    health_checker=read_health,
                    sleeper=lambda seconds: None,
                )
                self.assertEqual(start_result.exit_code, 0)
                self.assertEqual(
                    manager.status_service(
                        config,
                        health_checker=read_health,
                    ).status,
                    "running",
                )
                self.assertEqual(
                    manager.health_service(
                        config,
                        health_checker=read_health,
                    ).status,
                    "healthy",
                )

                analysis_result = manager.analyze_synthetic_email(config)

                self.assertEqual(analysis_result.exit_code, 0)
                self.assertEqual(analysis_result.status, "ok")
                connection = sqlite3.connect(config.database)
                try:
                    persisted = connection.execute(
                        (
                            "SELECT subject, sender "
                            "FROM email_analysis ORDER BY id"
                        )
                    ).fetchall()
                finally:
                    connection.close()
                self.assertEqual(
                    persisted,
                    [
                        (
                            "Synthetic delivery question",
                            "buyer@example.test",
                        )
                    ],
                )
                self.assertEqual(
                    Path(config.database).parent,
                    project_container / "LocalData",
                )
                self.assertTrue(config.log_file.is_file())
                self.assertEqual(
                    config.pid_file.read_text(encoding="utf-8"),
                    str(process_id),
                )
                self.assertFalse((repository_root / "outputs").exists())

                stop_result = manager.stop_service(
                    config,
                    health_checker=read_health,
                    killer=stop_server,
                    sleeper=lambda seconds: None,
                )

                self.assertEqual(stop_result.exit_code, 0)
                self.assertEqual(stop_result.status, "stopped")
                self.assertFalse(config.pid_file.exists())
                self.assertFalse(read_health(config.host, config.port, 0.1))
            finally:
                if server_thread is not None and server_thread.is_alive():
                    server.shutdown()
                    server.server_close()
                    server_thread.join(timeout=2)
                if server.database is not None:
                    server.database.close()


def _create_managed_layout(
    base: Path,
    *,
    excluded_zone: str | None = None,
    create_runtime_executable: bool = True,
) -> tuple[Path, Path]:
    project_container = base / "email_ai_assistant"
    repository_root = project_container / "main"
    repository_root.mkdir(parents=True)
    for zone_name in MANAGED_ZONE_NAMES:
        if zone_name == excluded_zone:
            continue
        (project_container / zone_name).mkdir()
    python_executable = (
        project_container
        / "Runtimes"
        / "venv"
        / "Scripts"
        / "python.exe"
    )
    python_executable.parent.mkdir(parents=True)
    if create_runtime_executable:
        python_executable.write_bytes(b"synthetic runtime")
    return project_container, repository_root


if __name__ == "__main__":
    unittest.main()
