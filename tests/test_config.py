"""Tests for backend configuration names and defaults."""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.email_agent.config import load_config


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_load_config_reads_email_agent_environment_names(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-key",
                "EMAIL_AGENT_SQLITE_PATH": "outputs/test.sqlite3",
                "EMAIL_AGENT_LOG_LEVEL": "DEBUG",
                "EMAIL_AGENT_LLM_PROVIDER": "ollama",
                "EMAIL_AGENT_OLLAMA_BASE_URL": "http://127.0.0.1:11434/",
                "EMAIL_AGENT_OLLAMA_MODEL": "qwen3.6:latest",
                "EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS": "12",
            },
            clear=True,
        ):
            config = load_config()

        self.assertEqual(config.openai_api_key, "test-key")
        self.assertEqual(config.sqlite_path, "outputs/test.sqlite3")
        self.assertEqual(config.log_level, "DEBUG")
        self.assertEqual(config.llm_provider, "ollama")
        self.assertEqual(config.ollama_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.ollama_model, "qwen3.6:latest")
        self.assertEqual(config.ollama_timeout_seconds, 12)

    def test_load_config_defaults_local_llm_to_disabled_backend_only(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config()

        self.assertEqual(config.llm_provider, "disabled")
        self.assertEqual(config.ollama_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.ollama_model, "qwen3.6:latest")
        self.assertEqual(config.ollama_timeout_seconds, 30)

    def test_env_example_uses_backend_configuration_names(self) -> None:
        sample = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("EMAIL_AGENT_SQLITE_PATH=", sample)
        self.assertIn("EMAIL_AGENT_LOG_LEVEL=", sample)
        self.assertIn("EMAIL_AGENT_LLM_PROVIDER=", sample)
        self.assertIn("EMAIL_AGENT_OLLAMA_MODEL=", sample)
        self.assertNotIn("EMAIL_AI_DB_PATH", sample)
        self.assertNotIn("EMAIL_AI_LOG_LEVEL", sample)


if __name__ == "__main__":
    unittest.main()
