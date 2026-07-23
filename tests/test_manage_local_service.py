"""Tests for the local debug service manager."""

from __future__ import annotations

import inspect
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts import manage_local_service as manager


ROOT = Path(__file__).resolve().parents[1]


class ManageLocalServiceTests(unittest.TestCase):
    def _config(self, pid_file: Path) -> manager.ServiceConfig:
        return manager.ServiceConfig(
            host="127.0.0.1",
            port=8765,
            database=None,
            pid_file=pid_file,
            root=ROOT,
            python_executable="python-test",
            startup_timeout=0.1,
            poll_interval=0.01,
            log_file=pid_file.parent / "service.log",
            attachment_temp_dir=pid_file.parent / "attachment_temp",
        )

    def test_parser_exposes_service_commands(self) -> None:
        parser = manager.build_parser()

        for command in (
            "start",
            "stop",
            "restart",
            "status",
            "health",
            "analysis",
        ):
            with self.subTest(command=command):
                args = parser.parse_args([command])
                self.assertEqual(args.command, command)

    def test_config_rejects_non_loopback_host_before_service_actions(self) -> None:
        args = manager.build_parser().parse_args(["start", "--host", "0.0.0.0"])

        with self.assertRaisesRegex(ValueError, "supported loopback address") as caught:
            manager.config_from_args(args)

        self.assertNotIn("0.0.0.0", str(caught.exception))

    def test_standalone_config_uses_only_explicit_temporary_operational_state(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            args = manager.build_parser().parse_args([
                "start",
                "--standalone-state-root",
                str(state_root),
            ])

            config = manager.config_from_args(args)

        self.assertEqual(
            config.database,
            str(state_root / "LocalData" / "email_agent.sqlite3"),
        )
        self.assertEqual(
            config.attachment_temp_dir,
            state_root / "RuntimeTemp" / "attachment_temp",
        )
        self.assertEqual(
            config.log_file,
            state_root / "Logs" / "local_debug_service.log",
        )
        self.assertEqual(
            config.pid_file,
            state_root / "Logs" / "local_debug_service.pid",
        )
        self.assertEqual(config.standalone_state_root, state_root)
        self.assertTrue(config.database and Path(config.database).is_absolute())
        self.assertTrue(config.attachment_temp_dir.is_absolute())
        self.assertTrue(config.log_file.is_absolute())
        self.assertTrue(config.pid_file.is_absolute())

    def test_standalone_rejects_operational_path_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            conflicting_options = (
                ("--database", str(state_root / "other.sqlite3")),
                ("--pid-file", str(state_root / "other.pid")),
            )
            for option, value in conflicting_options:
                with self.subTest(option=option):
                    args = manager.build_parser().parse_args([
                        "start",
                        "--standalone-state-root",
                        str(state_root),
                        option,
                        value,
                    ])

                    with self.assertRaisesRegex(
                        ValueError,
                        "derived from standalone state root",
                    ):
                        manager.config_from_args(args)

    def test_standalone_lifecycle_commands_share_explicit_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            configs = {
                command: manager.config_from_args(
                    manager.build_parser().parse_args([
                        command,
                        "--standalone-state-root",
                        str(state_root),
                    ])
                )
                for command in (
                    "start",
                    "status",
                    "health",
                    "analysis",
                    "restart",
                    "stop",
                )
            }

        expected = configs["start"]
        for command, config in configs.items():
            with self.subTest(command=command):
                self.assertEqual(config.database, expected.database)
                self.assertEqual(config.attachment_temp_dir, expected.attachment_temp_dir)
                self.assertEqual(config.log_file, expected.log_file)
                self.assertEqual(config.pid_file, expected.pid_file)

    def test_health_command_uses_injected_health_checker(self) -> None:
        config = self._config(Path("service.pid"))

        healthy = manager.health_service(
            config,
            health_checker=lambda host, port, timeout: True,
        )
        unhealthy = manager.health_service(
            config,
            health_checker=lambda host, port, timeout: False,
        )

        self.assertEqual((healthy.exit_code, healthy.status), (0, "healthy"))
        self.assertEqual(
            (unhealthy.exit_code, unhealthy.status),
            (3, "unhealthy"),
        )

    def test_analysis_command_posts_only_fixed_synthetic_current_message(
        self,
    ) -> None:
        requests: list[tuple[str, int, dict[str, object], float]] = []
        config = self._config(Path("service.pid"))

        def request_analysis(
            host: str,
            port: int,
            payload: dict[str, object],
            timeout: float,
        ) -> dict[str, object]:
            requests.append((host, port, payload, timeout))
            return {
                "ok": True,
                "saved_id": 1,
                "analysis": {
                    "analysis_engine": {"source": "rule_fallback"}
                },
            }

        result = manager.analyze_synthetic_email(
            config,
            requester=request_analysis,
        )

        self.assertEqual((result.exit_code, result.status), (0, "ok"))
        self.assertEqual(len(requests), 1)
        host, port, payload, timeout = requests[0]
        self.assertEqual((host, port), ("127.0.0.1", 8765))
        self.assertGreater(timeout, 0)
        self.assertIs(payload["user_confirmed"], True)
        self.assertEqual(payload["from"], "buyer@example.test")
        self.assertNotIn("attachment_files", payload)

    def test_analysis_command_fails_closed_without_rule_result_and_persistence(
        self,
    ) -> None:
        config = self._config(Path("service.pid"))
        invalid_responses = (
            {"ok": False},
            {
                "ok": True,
                "saved_id": 1,
                "analysis": {
                    "analysis_engine": {"source": "ai_model"}
                },
            },
            {
                "ok": True,
                "analysis": {
                    "analysis_engine": {"source": "rule_fallback"}
                },
            },
        )

        for response in invalid_responses:
            with self.subTest(response=response):
                result = manager.analyze_synthetic_email(
                    config,
                    requester=lambda host, port, payload, timeout: response,
                )

                self.assertEqual((result.exit_code, result.status), (6, "error"))
                self.assertEqual(result.message, "synthetic analysis failed")

    def test_standalone_start_passes_state_root_and_uses_explicit_log(
        self,
    ) -> None:
        launch: dict[str, object] = {}

        def fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
            launch["command"] = command
            launch["cwd"] = kwargs["cwd"]
            launch["log_name"] = getattr(kwargs["stdout"], "name", None)
            return SimpleNamespace(pid=12345)

        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            args = manager.build_parser().parse_args([
                "start",
                "--standalone-state-root",
                str(state_root),
            ])
            config = manager.config_from_args(args)
            health_results = iter([False, True])

            with patch.object(
                manager,
                "run_cleanup_before_service_start",
                return_value=manager.CleanupResult(removed_count=0),
            ):
                result = manager.start_service(
                    config,
                    popen=fake_popen,
                    health_checker=lambda host, port, timeout: next(health_results),
                    sleeper=lambda seconds: None,
                )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(launch["cwd"], str(ROOT))
        self.assertEqual(
            launch["log_name"],
            str(state_root / "Logs" / "local_debug_service.log"),
        )
        self.assertIn("--standalone-state-root", launch["command"])
        self.assertIn(str(state_root), launch["command"])
        self.assertNotIn("--database", launch["command"])
        self.assertNotEqual(launch["log_name"], str(manager.DEFAULT_LOG_FILE))

    def test_standalone_cleanup_uses_operational_config_without_env(
        self,
    ) -> None:
        cleanup_configs: list[object] = []
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            args = manager.build_parser().parse_args([
                "start",
                "--standalone-state-root",
                str(state_root),
            ])
            config = manager.config_from_args(args)
            health_results = iter([False, True])

            with (
                patch(
                    "backend.email_agent.config.load_config",
                ) as config_loader,
                patch(
                    "backend.email_agent.attachment_storage.cleanup_expired_attachments",
                    side_effect=lambda app_config: cleanup_configs.append(
                        app_config
                    ) or 0,
                ),
            ):
                result = manager.start_service(
                    config,
                    popen=lambda command, **kwargs: SimpleNamespace(pid=12345),
                    health_checker=lambda host, port, timeout: next(
                        health_results
                    ),
                    sleeper=lambda seconds: None,
                )

        self.assertEqual(result.exit_code, 0)
        config_loader.assert_not_called()
        self.assertEqual(len(cleanup_configs), 1)
        cleanup_config = cleanup_configs[0]
        self.assertEqual(cleanup_config.llm_provider, "disabled")
        self.assertEqual(cleanup_config.text_fallback_provider, "disabled")
        self.assertEqual(cleanup_config.sqlite_path, config.database)
        self.assertEqual(
            cleanup_config.attachment_temp_dir,
            str(config.attachment_temp_dir),
        )

    def test_status_reports_stopped_without_pid_or_health(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(Path(tmpdir) / "service.pid")

            result = manager.status_service(
                config,
                health_checker=lambda host, port, timeout: False,
            )

        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.status, "stopped")

    def test_start_launches_debug_server_and_writes_pid(self) -> None:
        events: list[str] = []
        launched: list[list[str]] = []

        def fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
            events.append("launch")
            launched.append(command)
            return SimpleNamespace(pid=12345)

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "service.pid"
            config = self._config(pid_file)
            health_results = iter([False, True])

            with patch(
                "backend.email_agent.attachment_storage.cleanup_expired_attachments",
                side_effect=lambda backend_config: events.append("cleanup") or 2,
            ) as cleanup:
                result = manager.start_service(
                    config,
                    popen=fake_popen,
                    health_checker=lambda host, port, timeout: next(health_results),
                    sleeper=lambda seconds: None,
                )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(pid_file.read_text(encoding="utf-8"), "12345")
            self.assertIn("attachment cleanup removed=2", result.message)

        cleanup.assert_called_once()
        self.assertEqual(events, ["cleanup", "launch"])
        self.assertEqual(launched[0][0], "python-test")
        self.assertIn("-B", launched[0])
        self.assertIn(str(ROOT / "scripts" / "run_local_debug.py"), launched[0])

    def test_start_rejects_non_loopback_without_launch_or_pid(self) -> None:
        launched: list[list[str]] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "service.pid"
            config = replace(self._config(pid_file), host="0.0.0.0")

            with self.assertRaisesRegex(ValueError, "supported loopback address") as caught:
                manager.start_service(
                    config,
                    popen=lambda command, **kwargs: launched.append(command),
                    health_checker=lambda host, port, timeout: False,
                    sleeper=lambda seconds: None,
                )

            self.assertFalse(pid_file.exists())
            self.assertEqual(launched, [])
            self.assertNotIn("0.0.0.0", str(caught.exception))

    def test_stop_removes_stale_pid_file_without_killing_unknown_process(self) -> None:
        killed: list[int] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "service.pid"
            pid_file.write_text("12345", encoding="utf-8")
            config = self._config(pid_file)

            result = manager.stop_service(
                config,
                health_checker=lambda host, port, timeout: False,
                killer=lambda pid: killed.append(pid),
                sleeper=lambda seconds: None,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertFalse(pid_file.exists())

        self.assertEqual(killed, [])

    def test_restart_public_contract_exposes_only_lower_level_launch_dependencies(self) -> None:
        parameters = inspect.signature(manager.restart_service).parameters

        self.assertNotIn("starter", parameters)
        for name in ("popen", "health_checker", "sleeper"):
            self.assertIn(name, parameters)

    def test_restart_runs_cleanup_stop_then_launch_once_with_lower_level_dependencies(self) -> None:
        calls: list[str] = []
        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(Path(tmpdir) / "service.pid")

            def fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
                calls.append("launch")
                return SimpleNamespace(pid=12345)

            with patch(
                "backend.email_agent.attachment_storage.cleanup_expired_attachments",
                side_effect=lambda backend_config: calls.append("cleanup") or 1,
            ) as cleanup:
                result = manager.restart_service(
                    config,
                    stopper=lambda service_config: calls.append("stop")
                    or manager.CommandResult(0, "stopped"),
                    popen=fake_popen,
                    health_checker=lambda host, port, timeout: True,
                    sleeper=lambda seconds: None,
                )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("attachment cleanup removed=1", result.message)
        cleanup.assert_called_once()
        self.assertEqual(calls, ["cleanup", "stop", "launch"])

    def test_lifecycle_cleanup_uses_loaded_backend_config(self) -> None:
        backend_config = object()
        with (
            patch(
                "backend.email_agent.config.load_config",
                return_value=backend_config,
            ) as load_config,
            patch(
                "backend.email_agent.attachment_storage.cleanup_expired_attachments",
                return_value=3,
            ) as cleanup,
        ):
            result = manager.run_cleanup_before_service_start()

        load_config.assert_called_once_with()
        cleanup.assert_called_once_with(backend_config)
        self.assertEqual(result.removed_count, 3)

    def test_cleanup_failure_is_generic_and_prevents_start(self) -> None:
        launched: list[list[str]] = []
        secret = "private-customer.pdf URL=https://private.invalid token=secret-value"

        with tempfile.TemporaryDirectory() as tmpdir:
            config = self._config(Path(tmpdir) / "service.pid")
            with patch(
                "backend.email_agent.attachment_storage.cleanup_expired_attachments",
                side_effect=RuntimeError(secret),
            ):
                result = manager.start_service(
                    config,
                    popen=lambda command, **kwargs: launched.append(command) or SimpleNamespace(pid=12345),
                    health_checker=lambda host, port, timeout: False,
                    sleeper=lambda seconds: None,
                )

        self.assertEqual(result.exit_code, 5)
        self.assertEqual(
            result.message,
            "Attachment cleanup failed. Check the configured temporary directory and permissions, then retry.",
        )
        self.assertNotIn(secret, result.message)
        self.assertEqual(launched, [])

    def test_cleanup_failure_prevents_restart_stop_and_start(self) -> None:
        calls: list[str] = []
        config = self._config(Path("service.pid"))

        with patch(
            "backend.email_agent.attachment_storage.cleanup_expired_attachments",
            side_effect=OSError("C:/private/customer-quote.pdf"),
        ):
            result = manager.restart_service(
                config,
                stopper=lambda service_config: calls.append("stop") or manager.CommandResult(0, "stopped"),
            )

        self.assertEqual(result.exit_code, 5)
        self.assertNotIn("customer-quote.pdf", result.message)
        self.assertEqual(calls, [])

    def test_status_does_not_echo_attachment_content_or_private_values(self) -> None:
        sensitive_values = (
            "synthetic attachment content",
            "https://private.invalid/download",
            "token=synthetic-secret",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "service.pid"
            pid_file.write_text("\n".join(sensitive_values), encoding="utf-8")
            with patch.object(manager, "run_cleanup_before_service_start") as cleanup:
                result = manager.status_service(
                    self._config(pid_file),
                    health_checker=lambda host, port, timeout: False,
                )

        self.assertEqual(result.status, "stopped")
        cleanup.assert_not_called()
        for value in sensitive_values:
            self.assertNotIn(value, result.message)

    def test_windows_shortcuts_call_service_manager(self) -> None:
        shortcuts = {
            "start_local_service.cmd": "start",
            "stop_local_service.cmd": "stop",
            "restart_local_service.cmd": "restart",
            "status_local_service.cmd": "status",
        }

        for filename, command in shortcuts.items():
            with self.subTest(filename=filename):
                text = (ROOT / filename).read_text(encoding="utf-8")
                self.assertIn("scripts\\manage_local_service.py", text)
                self.assertIn(command, text)

    def test_standalone_lifecycle_is_documented_as_temporary_and_local_only(
        self,
    ) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        deployment = (
            ROOT / "docs" / "operations" / "deployment_notes.md"
        ).read_text(encoding="utf-8")
        checklist = (
            ROOT / "docs" / "operations" / "testing_checklist.md"
        ).read_text(encoding="utf-8")

        for document in (readme, deployment, checklist):
            self.assertIn("--standalone-state-root", document)
            self.assertIn("temporary", document.casefold())
            self.assertIn("provider", document.casefold())
        self.assertIn("synthetic", readme.casefold())
        self.assertIn("Issue #31", readme)


if __name__ == "__main__":
    unittest.main()
