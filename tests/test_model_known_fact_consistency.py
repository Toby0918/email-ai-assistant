from __future__ import annotations

import unittest

from backend.email_agent.model_known_fact_consistency import (
    provider_claims_known_moq_unresolved,
)


class ModelKnownFactConsistencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.local_key_facts = [
            {
                "label": "Quantity",
                "value": "MOQ 1200/1400 pcs",
                "source": "thread",
            }
        ]

    def test_pending_moq_claim_conflicts_with_local_final_fact(self) -> None:
        cases = (
            "MOQ remains pending confirmation.",
            "MOQ requires confirmation.",
            "MOQ still needs confirmation.",
            "MOQ needs confirmation.",
            "MOQ 仍需确认。",
            "MOQ 需要确认。",
            "MOQ remains pending but attachment is confirmed.",
            "MOQ remains pending while delivery is final.",
            "MOQ remains pending because final MOQ is absent.",
            "MOQ 1200/1400 pcs requires confirmation.",
        )

        for provider_value in cases:
            with self.subTest(provider_value=provider_value):
                self.assertTrue(
                    provider_claims_known_moq_unresolved(
                        provider_value, self.local_key_facts
                    )
                )

    def test_explicitly_known_moq_does_not_conflict(self) -> None:
        cases = (
            "MOQ is known; attachment details remain pending.",
            "MOQ is confirmed.",
            "MOQ is final.",
        )

        for provider_value in cases:
            with self.subTest(provider_value=provider_value):
                self.assertFalse(
                    provider_claims_known_moq_unresolved(
                        provider_value, self.local_key_facts
                    )
                )
