"""Tests for the isolated fallback-diagnostic logging sink."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from textwrap import dedent


ROOT = Path(__file__).resolve().parents[1]
EVENT_TEMPLATE = (
    "event=analysis_fallback code=%s stage=%s provider=%s model=%s "
    "output_mode=%s elapsed_ms=%d"
)
CANONICAL_EVENT = (
    "event=analysis_fallback code=provider_timeout stage=provider "
    "provider=deepseek model=deepseek-v4-flash "
    "output_mode=model_led elapsed_ms=123"
)
PRIVATE_MARKERS = (
    "PRIVATE_OPENAI_BODY",
    "PRIVATE_HTTPX_URL",
    "PRIVATE_HTTPCORE",
    "PRIVATE_BACKEND",
    "PRIVATE_DIRECT_DIAGNOSTIC",
    "PRIVATE_SPOOFED_ARGUMENT",
    "PRIVATE_EXCEPTION",
    "PRIVATE_CACHED_EXCEPTION",
)
CACHED_EXCEPTION_RECORD_SCRIPT = dedent(
    """
    cached_record = logging.LogRecord(
        "backend.email_agent.analysis_diagnostics", logging.WARNING,
        "synthetic.py", 1, __TEMPLATE__,
        ("provider_timeout", "provider", "deepseek", "deepseek-v4-flash", "model_led", 123),
        None,
    )
    cached_record.exc_text = "PRIVATE_CACHED_EXCEPTION"
    diagnostic.handle(cached_record)
    """
)
DEBUG_PRIVACY_SCRIPT = dedent(
    """
    import logging

    from backend.email_agent.analysis_diagnostics import log_analysis_fallback
    from backend.email_agent.logging_config import configure_logging

    path = __PATH__
    template = __TEMPLATE__
    configure_logging("DEBUG", log_file=path)
    logging.getLogger("openai._base_client").debug(
        "Request options: %s",
        {"json_data": {"messages": ["PRIVATE_OPENAI_BODY"]}},
    )
    logging.getLogger("httpx").info(
        "HTTP Request: POST https://PRIVATE_HTTPX_URL.invalid"
    )
    logging.getLogger("httpcore").warning("PRIVATE_HTTPCORE")
    logging.getLogger("backend.email_agent.synthetic").error("PRIVATE_BACKEND")
    diagnostic = logging.getLogger("backend.email_agent.analysis_diagnostics")
    class TextSubclass(str):
        pass

    diagnostic.warning("PRIVATE_DIRECT_DIAGNOSTIC")
    diagnostic.warning(
        template,
        "PRIVATE_SPOOFED_ARGUMENT",
        "provider",
        "deepseek",
        "deepseek-v4-flash",
        "model_led",
        123,
    )
    diagnostic.warning(
        template,
        TextSubclass("provider_timeout"),
        "provider",
        "deepseek",
        "deepseek-v4-flash",
        "model_led",
        123,
    )
    diagnostic.warning(
        template,
        "provider_timeout",
        "provider",
        "deepseek",
        "deepseek-v4-flash",
        "model_led",
        True,
    )
    diagnostic.warning(
        TextSubclass(template),
        "provider_timeout",
        "provider",
        "deepseek",
        "deepseek-v4-flash",
        "model_led",
        123,
    )
    diagnostic.error(
        template,
        "provider_timeout",
        "provider",
        "deepseek",
        "deepseek-v4-flash",
        "model_led",
        123,
    )
    try:
        raise RuntimeError("PRIVATE_EXCEPTION")
    except RuntimeError:
        diagnostic.warning(template, "provider_timeout", "provider", "deepseek", "deepseek-v4-flash", "model_led", 123, exc_info=True)
    diagnostic.warning(template, "provider_timeout", "provider", "deepseek", "deepseek-v4-flash", "model_led", 123, stack_info=True)
    diagnostic.warning(template + " ", "provider_timeout", "provider", "deepseek", "deepseek-v4-flash", "model_led", 123)
    log_analysis_fallback(
        code="provider_timeout",
        stage="provider",
        provider="deepseek",
        model="deepseek-v4-flash",
        output_mode="model_led",
        elapsed_ms=123,
    )
    for handler in list(logging.getLogger().handlers) + list(diagnostic.handlers):
        handler.flush()
    """
)


class LoggingConfigTests(unittest.TestCase):
    def test_debug_file_rejects_library_backend_and_direct_private_records(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "service.log"
            code = DEBUG_PRIVACY_SCRIPT.replace("__PATH__", repr(str(path)))
            code = code.replace("__TEMPLATE__", repr(EVENT_TEMPLATE))
            code += CACHED_EXCEPTION_RECORD_SCRIPT.replace("__TEMPLATE__", repr(EVENT_TEMPLATE))
            result = self._run(code)

            self.assertEqual(result.returncode, 0, result.stderr)
            text = path.read_text(encoding="utf-8")
            for marker in PRIVATE_MARKERS:
                with self.subTest(marker=marker):
                    self.assertNotIn(marker, text)
            self.assertEqual(text.count("event=analysis_fallback"), 1, text)
            self.assertIn(CANONICAL_EVENT, text)

    def test_every_configured_level_writes_one_canonical_fallback(self) -> None:
        with TemporaryDirectory() as directory:
            for level in (
                "DEBUG",
                "INFO",
                "WARNING",
                "ERROR",
                "CRITICAL",
                "INVALID_LEVEL",
            ):
                with self.subTest(level=level):
                    path = Path(directory) / f"{level}.log"
                    code = dedent(
                        f"""
                        import logging

                        from backend.email_agent.analysis_diagnostics import (
                            log_analysis_fallback,
                        )
                        from backend.email_agent.logging_config import configure_logging

                        path = {str(path)!r}
                        configure_logging({level!r}, log_file=path)
                        log_analysis_fallback(
                            code="provider_timeout",
                            stage="provider",
                            provider="deepseek",
                            model="deepseek-v4-flash",
                            output_mode="model_led",
                            elapsed_ms=123,
                        )
                        diagnostic = logging.getLogger(
                            "backend.email_agent.analysis_diagnostics"
                        )
                        for handler in diagnostic.handlers:
                            handler.flush()
                        for handler in logging.getLogger().handlers:
                            handler.flush()
                        """
                    )
                    result = self._run(code)

                    self.assertEqual(result.returncode, 0, result.stderr)
                    text = path.read_text(encoding="utf-8")
                    self.assertEqual(text.count(CANONICAL_EVENT), 1, text)
                    self.assertEqual(text.count("event=analysis_fallback"), 1, text)

    def test_reconfiguration_replaces_and_closes_the_diagnostic_handler(self) -> None:
        with TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.log"
            second_path = Path(directory) / "second.log"
            code = dedent(
                f"""
                import codecs
                import logging
                from logging.handlers import RotatingFileHandler
                from backend.email_agent.analysis_diagnostics import log_analysis_fallback
                from backend.email_agent.logging_config import configure_logging
                first_path, second_path = {str(first_path)!r}, {str(second_path)!r}
                configure_logging("DEBUG", log_file=first_path)
                diagnostic = logging.getLogger("backend.email_agent.analysis_diagnostics")
                assert diagnostic.level == logging.WARNING, diagnostic.level
                assert diagnostic.propagate is False
                assert len(diagnostic.handlers) == 1, diagnostic.handlers
                old_handler = diagnostic.handlers[0]
                assert isinstance(old_handler, RotatingFileHandler), type(old_handler)
                assert old_handler not in logging.getLogger().handlers
                assert not any(
                    isinstance(handler, RotatingFileHandler)
                    for handler in logging.getLogger().handlers
                ), logging.getLogger().handlers
                configure_logging("CRITICAL", log_file=second_path)
                assert old_handler.stream is None
                assert len(diagnostic.handlers) == 1, diagnostic.handlers
                handler = diagnostic.handlers[0]
                assert handler is not old_handler and isinstance(handler, RotatingFileHandler)
                assert handler.level == logging.WARNING, handler.level
                assert (handler.maxBytes, handler.backupCount) == (1_000_000, 2)
                assert codecs.lookup(handler.encoding).name == "utf-8", handler.encoding
                assert handler not in logging.getLogger().handlers
                log_analysis_fallback(code="provider_timeout", stage="provider", provider="deepseek", model="deepseek-v4-flash", output_mode="model_led", elapsed_ms=123)
                handler.flush()
                """
            )
            result = self._run(code)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(first_path.read_text(encoding="utf-8"), "")
            text = second_path.read_text(encoding="utf-8")
            self.assertEqual(text.count(CANONICAL_EVENT), 1, text)
            self.assertEqual(text.count("event=analysis_fallback"), 1, text)

    def test_without_file_uses_one_filtered_diagnostic_stream(self) -> None:
        code = dedent(
            f"""
            import logging
            from logging.handlers import RotatingFileHandler

            from backend.email_agent.analysis_diagnostics import log_analysis_fallback
            from backend.email_agent.logging_config import configure_logging

            configure_logging("INFO")
            configure_logging("CRITICAL")
            diagnostic = logging.getLogger("backend.email_agent.analysis_diagnostics")
            assert diagnostic.level == logging.WARNING, diagnostic.level
            assert diagnostic.propagate is False
            assert len(diagnostic.handlers) == 1, diagnostic.handlers
            handler = diagnostic.handlers[0]
            assert type(handler) is logging.StreamHandler, type(handler)
            assert not isinstance(handler, RotatingFileHandler)
            assert handler.level == logging.WARNING, handler.level
            diagnostic.warning("PRIVATE_DIRECT_DIAGNOSTIC")
            log_analysis_fallback(
                code="provider_timeout",
                stage="provider",
                provider="deepseek",
                model="deepseek-v4-flash",
                output_mode="model_led",
                elapsed_ms=123,
            )
            handler.flush()
            """
        )
        code += CACHED_EXCEPTION_RECORD_SCRIPT.replace("__TEMPLATE__", repr(EVENT_TEMPLATE))
        result = self._run(code)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr.count(CANONICAL_EVENT), 1, result.stderr)
        self.assertEqual(result.stderr.count("event=analysis_fallback"), 1)
        self.assertNotIn("PRIVATE_DIRECT_DIAGNOSTIC", result.stderr)
        self.assertNotIn("PRIVATE_CACHED_EXCEPTION", result.stderr)
        self.assertNotIn(CANONICAL_EVENT, result.stdout)

    @staticmethod
    def _run(code: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-B", "-c", code],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )


if __name__ == "__main__":
    unittest.main()
