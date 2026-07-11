"""Tests for the local debug service manager."""

from __future__ import annotations

import tempfile
import unittest
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
        )

    def test_parser_exposes_service_commands(self) -> None:
        parser = manager.build_parser()

        for command in ("start", "stop", "restart", "status"):
            with self.subTest(command=command):
                args = parser.parse_args([command])
                self.assertEqual(args.command, command)

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

    def test_restart_runs_stop_then_start(self) -> None:
        calls: list[str] = []
        config = self._config(Path("service.pid"))

        with patch(
            "backend.email_agent.attachment_storage.cleanup_expired_attachments",
            side_effect=lambda backend_config: calls.append("cleanup") or 1,
        ) as cleanup:
            result = manager.restart_service(
                config,
                stopper=lambda service_config: calls.append("stop") or manager.CommandResult(0, "stopped"),
                starter=lambda service_config: calls.append("start") or manager.CommandResult(0, "started"),
            )

        self.assertEqual(result.exit_code, 0)
        self.assertIn("attachment cleanup removed=1", result.message)
        cleanup.assert_called_once()
        self.assertEqual(calls, ["cleanup", "stop", "start"])

    def test_default_restart_does_not_repeat_start_cleanup(self) -> None:
        calls: list[str] = []
        config = self._config(Path("service.pid"))

        with (
            patch(
                "backend.email_agent.attachment_storage.cleanup_expired_attachments",
                side_effect=lambda backend_config: calls.append("cleanup") or 1,
            ) as cleanup,
            patch.object(
                manager,
                "_start_after_cleanup",
                side_effect=lambda service_config: calls.append("launch")
                or manager.CommandResult(0, "started"),
            ) as launcher,
        ):
            result = manager.restart_service(
                config,
                stopper=lambda service_config: calls.append("stop") or manager.CommandResult(0, "stopped"),
            )

        self.assertEqual(result.exit_code, 0)
        cleanup.assert_called_once()
        launcher.assert_called_once_with(config)
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
                starter=lambda service_config: calls.append("start") or manager.CommandResult(0, "started"),
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
            result = manager.status_service(
                self._config(pid_file),
                health_checker=lambda host, port, timeout: False,
            )

        self.assertEqual(result.status, "stopped")
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


if __name__ == "__main__":
    unittest.main()
