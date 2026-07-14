"""Tests for bounded backend logging configuration."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
MARKER = "event=analysis_fallback code=provider_timeout"


class LoggingConfigTests(unittest.TestCase):
    def test_file_mode_uses_one_bounded_utf8_handler_and_writes_once(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "service.log"
            code = (
                "import codecs, logging; "
                "from logging.handlers import RotatingFileHandler; "
                "from backend.email_agent.logging_config import configure_logging; "
                f"path={str(path)!r}; marker={MARKER!r}; "
                "configure_logging('INFO', log_file=path); "
                "configure_logging('INFO', log_file=path); "
                "root=logging.getLogger(); "
                "assert len(root.handlers) == 1, root.handlers; "
                "handler=root.handlers[0]; "
                "assert isinstance(handler, RotatingFileHandler), type(handler); "
                "assert handler.maxBytes == 1_000_000, handler.maxBytes; "
                "assert handler.backupCount == 2, handler.backupCount; "
                "assert codecs.lookup(handler.encoding).name == 'utf-8', handler.encoding; "
                "logging.getLogger('synthetic').warning(marker)"
            )
            result = subprocess.run(
                [sys.executable, "-B", "-c", code],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(MARKER, result.stderr)
            self.assertEqual(path.read_text(encoding="utf-8").count(MARKER), 1)

    def test_without_file_uses_only_one_stream_handler(self) -> None:
        code = (
            "import logging; "
            "from backend.email_agent.logging_config import configure_logging; "
            f"marker={MARKER!r}; "
            "configure_logging('INFO'); "
            "configure_logging('INFO'); "
            "root=logging.getLogger(); "
            "assert len(root.handlers) == 1, root.handlers; "
            "assert type(root.handlers[0]) is logging.StreamHandler, "
            "type(root.handlers[0]); "
            "logging.getLogger('synthetic').warning(marker)"
        )
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count(MARKER), 1)
        self.assertNotIn(MARKER, result.stdout)


if __name__ == "__main__":
    unittest.main()
