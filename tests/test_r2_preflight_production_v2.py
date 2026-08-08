"""Issue #110 preflight production root is unconditionally dormant."""

from __future__ import annotations

import unittest

from backend.r2_preflight_process.production_v2 import (
    PREFLIGHT_PRODUCTION_VERBS_V2,
    PreflightProductionStatusV2,
    dormant_preflight_production_v2,
    run_preflight_production_v2,
)
from backend.r2_production_binding import ProductionCommandV2


class _Poison:
    def __getattribute__(self, name):
        raise AssertionError(f"dormant root inspected {name}")

    def __call__(self, *args, **kwargs):
        raise AssertionError("dormant root invoked a callback")


class R2PreflightProductionV2Tests(unittest.TestCase):
    def test_exact_six_verbs_are_catalogued_but_all_remain_dormant(self):
        self.assertEqual(
            PREFLIGHT_PRODUCTION_VERBS_V2,
            {
                "current-topology": ProductionCommandV2.CURRENT_TOPOLOGY_PREFLIGHT,
                "host-baseline": ProductionCommandV2.HOST_BASELINE,
                "evidence-review": ProductionCommandV2.EVIDENCE_REVIEW,
                "evidence-verification": ProductionCommandV2.EVIDENCE_VERIFICATION,
                "final-audit-readiness": ProductionCommandV2.FINAL_AUDIT_READINESS,
                "recovery-inspection": ProductionCommandV2.RECOVERY_INSPECTION,
            },
        )
        for verb in PREFLIGHT_PRODUCTION_VERBS_V2:
            result = run_preflight_production_v2(
                argv=(verb,),
                terminal=_Poison(),
                binding=_Poison(),
                adapter=_Poison(),
                execution_confirmation_claims=_Poison(),
                expected_prior_journal_head_fingerprint=_Poison(),
                observed_at_epoch=_Poison(),
            )
            with self.subTest(verb=verb):
                self.assertIs(
                    result.status,
                    PreflightProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
                )
                self.assertEqual(result.counts(), (0, 0, 0))

    def test_no_argv_or_object_can_change_dormancy(self):
        for argv in (None, (), ("unknown",), _Poison()):
            with self.subTest(argv_type=type(argv).__name__):
                result = dormant_preflight_production_v2(argv=argv)
                self.assertIs(
                    result.status,
                    PreflightProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
                )
                self.assertEqual(
                    result.to_mapping(),
                    {
                        "status": "DORMANT_NO_ISSUE39_APPROVAL",
                        "accepted": 0,
                        "rejected": 0,
                        "read_operations": 0,
                    },
                )


if __name__ == "__main__":
    unittest.main()
