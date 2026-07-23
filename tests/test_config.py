"""Tests for backend configuration names and defaults."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.email_agent.config import (
    build_standalone_verification_config,
    load_config,
)


ROOT = Path(__file__).resolve().parents[1]


class ConfigTests(unittest.TestCase):
    def test_standalone_verification_config_ignores_credentials_and_providers(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sqlite_path = root / "LocalData" / "email_agent.sqlite3"
            attachment_temp_dir = root / "RuntimeTemp" / "attachment_temp"
            hostile_environment = {
                "OPENAI_API_KEY": "ignored-openai-secret",
                "DEEPSEEK_API_KEY": "ignored-deepseek-secret",
                "EMAIL_AGENT_LLM_PROVIDER": "openai",
                "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "deepseek",
                "EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": "true",
                "EMAIL_AGENT_SQLITE_PATH": "D:/ignored.sqlite3",
                "EMAIL_AGENT_ATTACHMENT_TEMP_DIR": "D:/ignored-attachments",
            }

            with patch.dict(os.environ, hostile_environment, clear=True):
                config = build_standalone_verification_config(
                    sqlite_path=sqlite_path,
                    attachment_temp_dir=attachment_temp_dir,
                )

        self.assertIsNone(config.openai_api_key)
        self.assertIsNone(config.deepseek_api_key)
        self.assertEqual(config.llm_provider, "disabled")
        self.assertEqual(config.text_fallback_provider, "disabled")
        self.assertFalse(config.private_knowledge_enabled)
        self.assertEqual(config.private_knowledge_authority_root, "")
        self.assertEqual(config.private_knowledge_snapshot_path, "")
        self.assertEqual(config.sqlite_path, str(sqlite_path))
        self.assertEqual(config.attachment_temp_dir, str(attachment_temp_dir))
        self.assertTrue(Path(config.sqlite_path).is_absolute())
        self.assertTrue(Path(config.attachment_temp_dir).is_absolute())
        self.assertEqual(config.attachment_max_files, 5)
        self.assertEqual(config.attachment_max_file_bytes, 10 * 1024 * 1024)
        self.assertEqual(config.attachment_max_total_bytes, 25 * 1024 * 1024)

    def test_load_config_has_safe_openai_and_text_fallback_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(dotenv_path=None)

        self.assertEqual(getattr(config, "openai_model", None), "gpt-5.6-sol")
        self.assertEqual(getattr(config, "openai_timeout_seconds", None), 35)
        self.assertEqual(getattr(config, "text_fallback_provider", None), "disabled")

    def test_load_config_normalizes_allowlisted_multimodal_overrides(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EMAIL_AGENT_LLM_PROVIDER": " OpenAI ",
                "EMAIL_AGENT_OPENAI_MODEL": " GPT-5.6-SOL ",
                "EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS": "999",
                "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": " DeepSeek ",
            },
            clear=True,
        ):
            config = load_config(dotenv_path=None)

        self.assertEqual(config.llm_provider, "openai")
        self.assertEqual(getattr(config, "openai_model", None), "gpt-5.6-sol")
        self.assertEqual(getattr(config, "openai_timeout_seconds", None), 35)
        self.assertEqual(getattr(config, "text_fallback_provider", None), "deepseek")

    def test_load_config_rejects_unallowlisted_multimodal_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "EMAIL_AGENT_OPENAI_MODEL": "gpt-5.6-sol-preview",
                "EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS": "invalid",
                "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "openai",
                "EMAIL_AGENT_OPENAI_BASE_URL": "https://override.example.test/v1",
            },
            clear=True,
        ):
            config = load_config(dotenv_path=None)

        self.assertEqual(getattr(config, "openai_model", None), "gpt-5.6-sol")
        self.assertEqual(getattr(config, "openai_timeout_seconds", None), 35)
        self.assertEqual(getattr(config, "text_fallback_provider", None), "disabled")
        self.assertFalse(hasattr(config, "openai_base_url"))

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
        self.assertEqual(config.deepseek_timeout_seconds, 10)
        self.assertEqual(config.deepseek_output_mode, "model_led")

    def test_load_config_caps_deepseek_timeout_at_10_seconds(self) -> None:
        with patch.dict(
            os.environ,
            {"EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS": "999"},
            clear=True,
        ):
            config = load_config(dotenv_path=None)

        self.assertEqual(config.deepseek_timeout_seconds, 10)

    def test_load_config_has_safe_deepseek_defaults(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            config = load_config(dotenv_path=None)

        self.assertIsNone(config.deepseek_api_key)
        self.assertEqual(config.deepseek_model, "deepseek-v4-flash")
        self.assertEqual(config.deepseek_timeout_seconds, 10)
        self.assertEqual(config.deepseek_output_mode, "conservative")

    def test_private_knowledge_defaults_disabled_and_only_explicit_true_enables(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            default = load_config(dotenv_path=None)
        self.assertFalse(default.private_knowledge_enabled)
        self.assertEqual(default.private_knowledge_authority_root, "")
        self.assertEqual(default.private_knowledge_snapshot_path, "")

        for raw, expected in (
            ("true", True), (" TRUE ", True), ("false", False),
            ("1", False), ("yes", False), ("on", False), ("", False),
        ):
            with self.subTest(raw=raw), patch.dict(
                os.environ,
                {"EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": raw},
                clear=True,
            ):
                self.assertIs(load_config(dotenv_path=None).private_knowledge_enabled, expected)

    def test_private_knowledge_paths_are_backend_only_and_hidden_from_repr(self) -> None:
        authority = "D:/Private/Authority"
        snapshot = "E:/Private/Runtime/knowledge.pksnap"
        with patch.dict(
            os.environ,
            {
                "EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": "true",
                "EMAIL_AGENT_PRIVATE_KNOWLEDGE_AUTHORITY_ROOT": authority,
                "EMAIL_AGENT_PRIVATE_KNOWLEDGE_SNAPSHOT_PATH": snapshot,
            },
            clear=True,
        ):
            config = load_config(dotenv_path=None)

        self.assertTrue(config.private_knowledge_enabled)
        self.assertEqual(config.private_knowledge_authority_root, authority)
        self.assertEqual(config.private_knowledge_snapshot_path, snapshot)
        rendered = repr(config)
        self.assertNotIn(authority, rendered)
        self.assertNotIn(snapshot, rendered)
        self.assertNotIn("private_knowledge_authority_root", rendered)
        self.assertNotIn("private_knowledge_snapshot_path", rendered)

    def test_deepseek_key_does_not_fall_back_to_openai_key(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-openai"}, clear=True):
            config = load_config(dotenv_path=None)

        self.assertIsNone(config.deepseek_api_key)

    def test_env_example_has_no_configurable_deepseek_base_url(self) -> None:
        sample = (ROOT / ".env.example").read_text(encoding="utf-8")

        self.assertIn("DEEPSEEK_API_KEY=", sample)
        self.assertIn("EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS=10", sample)
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
        self.assertIn("EMAIL_AGENT_OPENAI_MODEL=gpt-5.6-sol", sample)
        self.assertIn("EMAIL_AGENT_OPENAI_TIMEOUT_SECONDS=35", sample)
        self.assertIn("EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled", sample)
        self.assertIn("EMAIL_AGENT_OLLAMA_MODEL=", sample)
        self.assertIn("EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED=false", sample)
        self.assertIn("EMAIL_AGENT_PRIVATE_KNOWLEDGE_AUTHORITY_ROOT=", sample)
        self.assertIn("EMAIL_AGENT_PRIVATE_KNOWLEDGE_SNAPSHOT_PATH=", sample)
        self.assertNotIn("EMAIL_AI_DB_PATH", sample)
        self.assertNotIn("EMAIL_AI_LOG_LEVEL", sample)
        self.assertNotIn("EMAIL_AGENT_OPENAI_BASE_URL", sample)

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
