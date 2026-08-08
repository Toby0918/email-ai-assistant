"""Issue #110 evidence production root is unconditionally dormant."""

from __future__ import annotations

import unittest

from backend.r2_evidence_process.production_v2 import (
    EVIDENCE_PRODUCTION_VERBS_V2,
    EvidenceProductionStatusV2,
    dormant_evidence_production_v2,
    run_evidence_production_v2,
)
from backend.r2_production_binding import ProductionCommandV2


class _Poison:
    def __getattribute__(self, name):
        raise AssertionError(f"dormant root inspected {name}")

    def __call__(self, *args, **kwargs):
        raise AssertionError("dormant root invoked a callback")


class R2EvidenceProductionV2Tests(unittest.TestCase):
    def test_single_publish_verb_is_catalogued_but_remains_dormant(self):
        self.assertEqual(
            EVIDENCE_PRODUCTION_VERBS_V2,
            {"publish": ProductionCommandV2.EVIDENCE_PUBLICATION},
        )
        result = run_evidence_production_v2(
            argv=("publish",),
            terminal=_Poison(),
            binding=_Poison(),
            adapter=_Poison(),
            reviewed_evidence_fingerprint=_Poison(),
            execution_confirmation_claims=_Poison(),
            expected_prior_journal_head_fingerprint=_Poison(),
            observed_at_epoch=_Poison(),
            journal_owner_fingerprint=_Poison(),
            genesis_nonce=_Poison(),
        )
        self.assertIs(
            result.status,
            EvidenceProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
        )
        self.assertEqual(result.counts(), (0, 0, 0))

    def test_no_argv_or_object_can_change_dormancy(self):
        for argv in (None, (), ("unknown",), _Poison()):
            with self.subTest(argv_type=type(argv).__name__):
                result = dormant_evidence_production_v2(argv=argv)
                self.assertEqual(
                    result.to_mapping(),
                    {
                        "status": "DORMANT_NO_ISSUE39_APPROVAL",
                        "accepted": 0,
                        "rejected": 0,
                        "published": 0,
                    },
                )


if __name__ == "__main__":
    unittest.main()
