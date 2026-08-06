"""Fresh Windows sandbox tests for the Issue #79 Config unit."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.r2_config_publication import (
    ConfigCrashGap,
    ConfigFaultSelectorV1,
    ConfigPendingState,
    ConfigPublicationStatus,
    ManagedConfigSelectionV1,
)
from backend.r2_config_publication.testing import bind_test_config_transaction


@unittest.skipUnless(sys.platform == "win32", "physical Windows claim")
class R2ConfigPublicationWindowsTests(unittest.TestCase):
    def test_exact_lf_utf8_dotenv_is_loader_compatible_and_provider_disabled(self) -> None:
        with _world() as world:
            hostile = {
                "OPENAI_API_KEY": "synthetic-hostile",
                "EMAIL_AGENT_LLM_PROVIDER": "openai",
                "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "deepseek",
                "EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": "true",
            }
            with mock.patch.dict(os.environ, hostile, clear=False):
                transaction = world.transaction()
                receipt = transaction.execute(ConfigFaultSelectorV1.none())
            self.assertEqual(receipt.status, ConfigPublicationStatus.PUBLISHED)
            self.assertEqual(receipt.setting_count, 2)
            self.assertTrue(receipt.provider_disabled)
            self.assertTrue(receipt.loader_verified)
            self.assertEqual(receipt.pending_state, ConfigPendingState.EFFECT_PRESENT_EXACT)
            self.assertEqual(
                world.target.read_bytes(),
                b"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=example.test,internal.example\n"
                b"EMAIL_AGENT_LOG_LEVEL=WARNING\n",
            )
            for boundary in ("config_prepare", "config_publish"):
                self.assertEqual(
                    [record.fact for record in transaction.records if record.boundary == boundary],
                    ["intent", "effect_observed", "stable_verified", "committed"],
                )

    def test_all_crash_gaps_classify_without_cleanup(self) -> None:
        for boundary in ("config_prepare", "config_publish"):
            for gap in ConfigCrashGap:
                with self.subTest(boundary=boundary, gap=gap.value), _world() as world:
                    transaction = world.transaction()
                    with self.assertRaisesRegex(RuntimeError, "config_transaction_interrupted"):
                        transaction.execute(ConfigFaultSelectorV1.crash(boundary, gap))
                    recovery = transaction.recover()
                    self.assertIn(recovery.pending_state, set(ConfigPendingState))
                    if recovery.status is ConfigPublicationStatus.RECOVERED:
                        self.assertFalse(world.target.exists())

    def test_collision_partial_replacement_encoding_line_loader_faults_retain(self) -> None:
        selectors = (
            ConfigFaultSelectorV1.collision(),
            ConfigFaultSelectorV1.partial_staging(),
            ConfigFaultSelectorV1.target_replacement(),
            ConfigFaultSelectorV1.encoding_drift(),
            ConfigFaultSelectorV1.line_ending_drift(),
            ConfigFaultSelectorV1.loader_mismatch(),
        )
        for selector in selectors:
            with self.subTest(fault=selector.kind), _world() as world:
                transaction = world.transaction()
                with self.assertRaises((ValueError, RuntimeError)):
                    transaction.execute(selector)
                recovery = transaction.recover()
                self.assertGreaterEqual(recovery.retained_artifact_count, 1)

    def test_pending_staging_blocks_second_generation(self) -> None:
        with _world() as world:
            world.staging.write_bytes(b"pending")
            with self.assertRaisesRegex(ValueError, "config_pending_generation"):
                world.transaction()
            self.assertEqual(world.staging.read_bytes(), b"pending")


class _World:
    def __init__(
        self, directory: Path | None = None, quiescence: str = "a" * 64
    ) -> None:
        self.owner = tempfile.TemporaryDirectory(
            prefix="issue79-synthetic-",
            dir=str(directory) if directory is not None else Path(sys.executable).anchor,
        )
        self.root = Path(self.owner.name).resolve(strict=True)
        config = self.root / "Config"
        config.mkdir()
        self.staging = config / "settings.env.prepare"
        self.target = config / "settings.env"
        self.journal = self.root / "config-unit.journal"
        self.sqlite_path = self.root / "LocalData" / "analysis.sqlite3"
        self.sqlite_path.parent.mkdir()
        self.attachment_temp = self.root / "RuntimeTemp" / "attachments"
        self.attachment_temp.parent.mkdir()
        self.selection = ManagedConfigSelectionV1.create(
            {
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": [
                    "example.test",
                    "internal.example",
                ],
                "EMAIL_AGENT_LOG_LEVEL": "WARNING",
            }
        )
        self._transactions = []
        self.quiescence = quiescence

    def transaction(self):
        value = bind_test_config_transaction(
            selection=self.selection,
            staging=self.staging,
            target=self.target,
            journal=self.journal,
            sqlite_path=self.sqlite_path,
            attachment_temp_dir=self.attachment_temp,
            quiescence_receipt_fingerprint=self.quiescence,
        )
        self._transactions.append(value)
        return value

    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        for transaction in self._transactions:
            transaction.close()
        self.owner.cleanup()


def _world() -> _World:
    return _World()


if __name__ == "__main__":
    unittest.main()
