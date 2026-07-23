"""Tests for the local debug server entry script."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from backend.email_agent.config import load_config
from scripts import run_local_debug


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_local_debug.py"


class RunLocalDebugTests(unittest.TestCase):
    def test_standalone_main_uses_local_only_operational_config_without_bootstrap(
        self,
    ) -> None:
        manager = MagicMock()
        with tempfile.TemporaryDirectory() as temporary:
            state_root = Path(temporary)
            args = SimpleNamespace(
                host="127.0.0.1",
                port=8765,
                database=None,
                standalone_state_root=str(state_root),
            )
            with (
                patch.object(run_local_debug, "parse_args", return_value=args),
                patch.object(run_local_debug, "load_config") as config_loader,
                patch.object(run_local_debug, "configure_logging") as configure,
                patch.object(
                    run_local_debug,
                    "load_configured_runtime_cards",
                ) as bootstrap,
                patch.object(run_local_debug, "run_server") as run_server,
            ):
                manager.attach_mock(configure, "configure")
                manager.attach_mock(bootstrap, "bootstrap")
                manager.attach_mock(run_server, "run_server")

                result = run_local_debug.main()

            server_config = run_server.call_args.kwargs["config"]

        self.assertEqual(result, 0)
        config_loader.assert_not_called()
        bootstrap.assert_not_called()
        self.assertEqual(
            manager.mock_calls,
            [
                call.configure(
                    "INFO",
                    log_file=state_root / "Logs" / "local_debug_service.log",
                ),
                call.run_server(
                    host="127.0.0.1",
                    port=8765,
                    database_path=str(
                        state_root / "LocalData" / "email_agent.sqlite3"
                    ),
                    config=server_config,
                    runtime_cards=(),
                ),
            ],
        )
        self.assertEqual(server_config.llm_provider, "disabled")
        self.assertEqual(server_config.text_fallback_provider, "disabled")
        self.assertIsNone(server_config.openai_api_key)
        self.assertIsNone(server_config.deepseek_api_key)
        self.assertFalse(server_config.private_knowledge_enabled)
        self.assertEqual(
            server_config.attachment_temp_dir,
            str(state_root / "RuntimeTemp" / "attachment_temp"),
        )

    def test_main_configures_file_logging_before_server_start(self) -> None:
        args = SimpleNamespace(
            host="127.0.0.1",
            port=8765,
            database=None,
            standalone_state_root=None,
        )
        config = load_config(dotenv_path=None)
        runtime_cards = (object(),)
        manager = MagicMock()

        with (
            patch.object(run_local_debug, "parse_args", return_value=args),
            patch.object(
                run_local_debug, "load_config", return_value=config, create=True
            ) as config_loader,
            patch.object(run_local_debug, "configure_logging", create=True) as configure,
            patch.object(
                run_local_debug,
                "load_configured_runtime_cards",
                return_value=runtime_cards,
                create=True,
            ) as bootstrap,
            patch.object(run_local_debug, "run_server") as run_server,
        ):
            manager.attach_mock(configure, "configure")
            manager.attach_mock(bootstrap, "bootstrap")
            manager.attach_mock(run_server, "run_server")
            result = run_local_debug.main()

        self.assertEqual(result, 0)
        config_loader.assert_called_once_with()
        self.assertEqual(
            manager.mock_calls,
            [
                call.configure(
                    config.log_level,
                    log_file=(
                        run_local_debug.ROOT
                        / "outputs"
                        / "local_debug_service.log"
                    ),
                ),
                call.bootstrap(
                    enabled=config.private_knowledge_enabled,
                    authority_root=config.private_knowledge_authority_root,
                    snapshot_path=config.private_knowledge_snapshot_path,
                    project_root=run_local_debug.ROOT,
                ),
                call.run_server(
                    host="127.0.0.1", port=8765, database_path=None,
                    config=config, runtime_cards=runtime_cards,
                ),
            ],
        )

    def test_script_help_runs_from_project_root(self) -> None:
        # The documented command is `python scripts/run_local_debug.py`.
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--help"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--host", result.stdout)
        self.assertIn("--port", result.stdout)

    def test_script_rejects_non_loopback_host_before_bind(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "--host", "0.0.0.0", "--port", "0"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("supported loopback address", result.stderr)
        self.assertNotIn("0.0.0.0", result.stderr)


if __name__ == "__main__":
    unittest.main()
