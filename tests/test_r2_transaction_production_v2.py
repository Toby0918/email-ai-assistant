"""Issue #110 transaction root dormancy and pure completion contracts."""

from __future__ import annotations

import unittest

from backend.r2_production_binding import ProductionCommandV2
from backend.r2_transaction_process.production_v2 import (
    TRANSACTION_PRODUCTION_VERBS_V2,
    TransactionProductionStatusV2,
    complete_transaction_action_v2,
    dormant_transaction_production_v2,
    run_transaction_production_v2,
    transaction_action_fingerprint_v2,
)
from tests.test_r2_transaction_journal_v2 import (
    NOW,
    OWNER,
    PRE_HEAD,
    TRANSITION,
    _binding,
    _confirmed_claim,
)


class _Poison:
    def __getattribute__(self, name):
        raise AssertionError(f"dormant root inspected {name}")

    def __call__(self, *args, **kwargs):
        raise AssertionError("dormant root invoked a callback")


class R2TransactionProductionV2Tests(unittest.TestCase):
    def test_three_transaction_verbs_are_catalogued_but_all_remain_dormant(self):
        self.assertEqual(
            TRANSACTION_PRODUCTION_VERBS_V2,
            {
                "execute": ProductionCommandV2.EXECUTE,
                "resume": ProductionCommandV2.RESUME,
                "rollback": ProductionCommandV2.ROLLBACK,
            },
        )
        for verb in TRANSACTION_PRODUCTION_VERBS_V2:
            result = run_transaction_production_v2(
                argv=(verb,),
                terminal=_Poison(),
                binding=_Poison(),
                adapter=_Poison(),
                execution_confirmation_claims=_Poison(),
                current_journal_head_fingerprint=_Poison(),
                transition_instance_fingerprint=_Poison(),
                remaining_reverse_plan_fingerprint=_Poison(),
                observed_at_epoch=_Poison(),
            )
            with self.subTest(verb=verb):
                self.assertIs(
                    result.status,
                    TransactionProductionStatusV2.DORMANT_NO_ISSUE39_APPROVAL,
                )
                self.assertEqual(result.counts(), (0, 0, 0))

    def test_no_argv_can_change_dormancy(self):
        for argv in (None, (), ("unknown",), _Poison()):
            result = dormant_transaction_production_v2(argv=argv)
            self.assertEqual(
                result.to_mapping(),
                {
                    "status": "DORMANT_NO_ISSUE39_APPROVAL",
                    "accepted": 0,
                    "rejected": 0,
                    "mutations": 0,
                },
            )

    def test_pure_completion_accepts_only_exact_v3_confirmation_binding(self):
        binding = _binding()
        action = transaction_action_fingerprint_v2(
            binding,
            ProductionCommandV2.EXECUTE,
            journal_head_fingerprint=PRE_HEAD,
            transition_instance_fingerprint=TRANSITION,
            remaining_reverse_plan_fingerprint="0" * 64,
        )
        claim = _confirmed_claim(
            binding=binding,
            command=ProductionCommandV2.EXECUTE,
            action_fingerprint=action,
            head=PRE_HEAD,
            transition=TRANSITION,
            remaining_reverse_plan_fingerprint="0" * 64,
            claim_sequence=1,
            confirmed_at_epoch=NOW,
        )
        completion = complete_transaction_action_v2(
            binding,
            claim,
            PRE_HEAD,
            TRANSITION,
            "0" * 64,
        )
        self.assertEqual(completion.claim_fingerprint, claim.claim_fingerprint)
        self.assertEqual(completion.mutations, 1)
        with self.assertRaisesRegex(
            TypeError, "R2_TRANSACTION_ACTION_COMPLETION_INVALID"
        ):
            complete_transaction_action_v2(
                binding, claim, "f" * 64, TRANSITION, "0" * 64
            )


if __name__ == "__main__":
    unittest.main()
