"""Tests for backend configuration names and defaults."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.email_agent.config import load_config


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_load_config_reads_and_normalizes_deepseek_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "synthetic-deepseek-key",
                "EMAIL_AGENT_LLM_PROVIDER": " DeepSeek ",
                "EMAIL_AGENT_DEEPSEEK_MODEL": " deepseek-v4-pro ",
                "EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS": "17",
                "EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE": " MODEL_LED ",
            },
            clear=True,
        ):
            config = load_config(dotenv_path=None)

        self.assertEqual(config.deepseek_api_key, "synthetic-deepseek-key")
        self.assertEqual(config.llm_provider, "deepseek")
        self.assertEqual(config.deepseek_model, "deepseek-v4-pro")
        self.assertEqual(config.deepseek_timeout_seconds, 17)
        self.assertEqual(config.deepseek_output_mode, "model_led")

    def test_load_config_caps_deepseek_timeout_at_25_seconds(self) -> None:
        with patch.dict(
            os.environ,
            {"EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS": "999"},
            clear=True,
        ):
            config = load_config(dotenv_path=None)

        self.assertEqual(config.deepseek_timeout_seconds, 25)

    def test_load_config_has_safe_deepseek_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(dotenv_path=None)

        self.assertIsNone(config.deepseek_api_key)
        self.assertEqual(config.deepseek_model, "deepseek-v4-flash")
        self.assertEqual(config.deepseek_timeout_seconds, 25)
        self.assertEqual(config.deepseek_output_mode, "conservative")

    def test_deepseek_key_does_not_fall_back_to_openai_key(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-openai"}, clear=True):
            config = load_config(dotenv_path=None)

        self.assertIsNone(config.deepseek_api_key)

    def test_env_example_has_no_configurable_deepseek_base_url(self) -> None:
        sample = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("DEEPSEEK_API_KEY=", sample)
        self.assertIn("EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative", sample)
        self.assertNotIn("EMAIL_AGENT_DEEPSEEK_BASE_URL", sample)

    def test_load_config_has_phase_two_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(dotenv_path=None)

        self.assertEqual(config.ollama_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.ollama_model, "qwen3.6:latest")
        self.assertEqual(config.attachment_temp_dir, "outputs/attachment_temp")
        self.assertEqual(config.attachment_retention_hours, 24)
        self.assertEqual(config.attachment_max_files, 5)
        self.assertEqual(config.attachment_max_file_bytes, 10 * 1024 * 1024)
        self.assertEqual(config.attachment_max_total_bytes, 25 * 1024 * 1024)
        self.assertIn("cndlf.com", config.internal_email_domains)

    def test_load_config_normalizes_internal_email_domains_and_falls_back_when_blank(self) -> None:
        with patch.dict(
            os.environ,
            {"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": "CNDLF.COM, Sales.Example.COM,  PARTNER.ORG "},
            clear=True,
        ):
            configured = load_config(dotenv_path=None)

        with patch.dict(os.environ, {"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": " , , "}, clear=True):
            blank = load_config(dotenv_path=None)

        self.assertEqual(configured.internal_email_domains, ("cndlf.com", "sales.example.com", "partner.org"))
        self.assertEqual(blank.internal_email_domains, ("cndlf.com",))

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
            config = load_config(dotenv_path=None)

        self.assertEqual(config.openai_api_key, "test-key")
        self.assertEqual(config.sqlite_path, "outputs/test.sqlite3")
        self.assertEqual(config.log_level, "DEBUG")
        self.assertEqual(config.llm_provider, "ollama")
        self.assertEqual(config.ollama_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.ollama_model, "qwen3.6:latest")
        self.assertEqual(config.ollama_timeout_seconds, 12)

    def test_load_config_defaults_local_llm_to_disabled_backend_only(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(dotenv_path=None)

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

    def test_load_config_reads_backend_dotenv_when_environment_is_unset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dotenv_path = Path(directory) / ".env"
            dotenv_path.write_text(
                "\n".join([
                    "EMAIL_AGENT_SQLITE_PATH=outputs/from-dotenv.sqlite3",
                    "EMAIL_AGENT_LOG_LEVEL=DEBUG",
                    "EMAIL_AGENT_LLM_PROVIDER=ollama",
                    "EMAIL_AGENT_OLLAMA_BASE_URL=http://127.0.0.1:11434/",
                    "EMAIL_AGENT_OLLAMA_MODEL=qwen3.6:latest",
                    "EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS=90",
                ]),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {}, clear=True):
                config = load_config(dotenv_path=dotenv_path)

        self.assertEqual(config.sqlite_path, "outputs/from-dotenv.sqlite3")
        self.assertEqual(config.log_level, "DEBUG")
        self.assertEqual(config.llm_provider, "ollama")
        self.assertEqual(config.ollama_base_url, "http://127.0.0.1:11434")
        self.assertEqual(config.ollama_model, "qwen3.6:latest")
        self.assertEqual(config.ollama_timeout_seconds, 90)

    def test_environment_values_override_backend_dotenv(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            dotenv_path = Path(directory) / ".env"
            dotenv_path.write_text(
                "\n".join([
                    "EMAIL_AGENT_LLM_PROVIDER=disabled",
                    "EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS=10",
                ]),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "EMAIL_AGENT_LLM_PROVIDER": "ollama",
                    "EMAIL_AGENT_OLLAMA_TIMEOUT_SECONDS": "90",
                },
                clear=True,
            ):
                config = load_config(dotenv_path=dotenv_path)

        self.assertEqual(config.llm_provider, "ollama")
        self.assertEqual(config.ollama_timeout_seconds, 90)


if __name__ == "__main__":
    unittest.main()
