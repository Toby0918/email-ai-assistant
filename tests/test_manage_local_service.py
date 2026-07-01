"""Tests for the local debug service manager."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

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
        launched: list[list[str]] = []

        def fake_popen(command: list[str], **kwargs: object) -> SimpleNamespace:
            launched.append(command)
            return SimpleNamespace(pid=12345)

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = Path(tmpdir) / "service.pid"
            config = self._config(pid_file)
            health_results = iter([False, True])

            result = manager.start_service(
                config,
                popen=fake_popen,
                health_checker=lambda host, port, timeout: next(health_results),
                sleeper=lambda seconds: None,
            )

            self.assertEqual(result.exit_code, 0)
            self.assertEqual(pid_file.read_text(encoding="utf-8"), "12345")

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

        result = manager.restart_service(
            config,
            stopper=lambda service_config: calls.append("stop") or manager.CommandResult(0, "stopped"),
            starter=lambda service_config: calls.append("start") or manager.CommandResult(0, "started"),
        )

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(calls, ["stop", "start"])

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
