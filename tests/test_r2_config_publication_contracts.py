"""Public contracts for the Issue #79 Managed Config unit."""

from __future__ import annotations

import unittest

from backend.r2_config_publication import (
    ConfigCrashGap,
    ConfigFaultSelectorV1,
    ConfigPendingState,
    ManagedConfigSelectionV1,
)


class R2ConfigPublicationContractTests(unittest.TestCase):
    def test_only_exact_non_secret_selection_and_tri_state_are_accepted(self) -> None:
        selection = ManagedConfigSelectionV1.create(
            {
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": [
                    "example.test",
                    "internal.example",
                ],
                "EMAIL_AGENT_LOG_LEVEL": "WARNING",
            }
        )
        self.assertEqual(selection.setting_count, 2)
        self.assertNotIn("example.test", repr(selection))
        invalid = (
            '{"EMAIL_AGENT_LOG_LEVEL":"INFO"}',
            [("EMAIL_AGENT_LOG_LEVEL", "INFO"), ("EMAIL_AGENT_LOG_LEVEL", "WARNING")],
            {"OPENAI_API_KEY": "synthetic-secret"},
            {"EMAIL_AGENT_LLM_PROVIDER": "openai"},
            {"EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED": "true"},
        )
        for value in invalid:
            with self.subTest(value=type(value).__name__):
                with self.assertRaisesRegex(ValueError, "config_selection_invalid"):
                    ManagedConfigSelectionV1.create(value)
        self.assertEqual(
            {state.value for state in ConfigPendingState},
            {
                "EFFECT_ABSENT_EXACT",
                "EFFECT_PRESENT_EXACT",
                "EFFECT_AMBIGUOUS",
            },
        )

    def test_fault_selector_has_only_fixed_factories(self) -> None:
        with self.assertRaises(TypeError):
            ConfigFaultSelectorV1()
        for boundary in ("config_prepare", "config_publish"):
            for gap in ConfigCrashGap:
                self.assertEqual(
                    ConfigFaultSelectorV1.crash(boundary, gap).gap,
                    gap,
                )


if __name__ == "__main__":
    unittest.main()
