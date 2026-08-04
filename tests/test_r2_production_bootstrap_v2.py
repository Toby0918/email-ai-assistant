"""Reviewed Adapter reachability for the three executable V2 roots."""

import inspect
import unittest

from backend.r2_evidence_process.bootstrap_v2 import EvidenceProductionBootstrapV2
from backend.r2_evidence_process.production_v2 import main as evidence_main
from backend.r2_final_master_closure import FinalMasterBindingV1
from backend.r2_preflight_process.bootstrap_v2 import PreflightProductionBootstrapV2
from backend.r2_preflight_process.production_v2 import main as preflight_main
from backend.r2_preflight_process.testing import SyntheticPreflightProductionV2
from backend.r2_production_binding import (
    ProductionBindingError,
    reviewed_production_binding_receipt_v2,
)
from backend.r2_production_composition import (
    EvidenceProductionAdapterV1,
    PreflightProductionAdapterV1,
    TransactionProductionAdapterV1,
    bind_production_adapter_v1,
    require_reviewed_bound_production_adapter_v1,
    ProductionAdapterSlotV1,
)
from backend.r2_transaction_process.bootstrap_v2 import (
    TransactionProductionBootstrapV2,
)
from backend.r2_transaction_process.production_v2 import main as transaction_main
from tests.test_r2_production_composition_v1 import (
    _evidence_context,
    _preflight_context,
    _transaction_context,
)


HEAD = "1" * 64
OWNER = "2" * 64
TRANSITION = "3" * 64
PLAN = "0" * 64


class R2ProductionBootstrapV2Tests(unittest.TestCase):
    def test_three_bootstraps_accept_only_reviewed_bound_real_adapters(self):
        preflight_binding, preflight_composition, preflight_scope = (
            _preflight_context()
        )
        self.addCleanup(preflight_scope.close)
        preflight_adapter = bind_production_adapter_v1(
            binding=preflight_binding,
            adapter=PreflightProductionAdapterV1.create(
                binding=preflight_binding,
                composition=preflight_composition,
                evidence_publication_receipt=None,
                recovery_receipt=None,
            ),
        )
        preflight = PreflightProductionBootstrapV2.create(
            binding=preflight_binding,
            reviewed_binding_receipt=_review_receipt(preflight_binding),
            adapter=preflight_adapter,
            durable_claims=(),
            expected_prior_journal_head_fingerprint=HEAD,
        )
        self.assertIs(preflight.adapter, preflight_adapter)

        evidence_binding, publication, review, evidence_scope = (
            _evidence_context()
        )
        self.addCleanup(evidence_scope.close)
        evidence_adapter = bind_production_adapter_v1(
            binding=evidence_binding,
            adapter=EvidenceProductionAdapterV1.create(
                binding=evidence_binding,
                composition=publication,
                review_receipt=review,
            ),
        )
        evidence = EvidenceProductionBootstrapV2.create(
            binding=evidence_binding,
            reviewed_binding_receipt=_review_receipt(evidence_binding),
            adapter=evidence_adapter,
            reviewed_evidence_fingerprint=review.observation_fingerprint,
            durable_claims=(),
            expected_prior_journal_head_fingerprint=HEAD,
            journal_owner_fingerprint=OWNER,
            genesis_nonce="4" * 64,
        )
        self.assertIs(evidence.adapter, evidence_adapter)

        transaction_binding, transaction_composition, initial, transaction_scope = (
            _transaction_context()
        )
        self.addCleanup(transaction_scope.close)
        transaction_adapter = bind_production_adapter_v1(
            binding=transaction_binding,
            adapter=TransactionProductionAdapterV1.create(
                binding=transaction_binding,
                composition=transaction_composition,
            ),
        )
        transaction = TransactionProductionBootstrapV2.create(
            binding=transaction_binding,
            reviewed_binding_receipt=_review_receipt(transaction_binding),
            adapter=transaction_adapter,
            durable_claims=(),
            current_journal_head_fingerprint=initial.journal_head_fingerprint,
            transition_instance_fingerprint=TRANSITION,
            remaining_reverse_plan_fingerprint=PLAN,
        )
        self.assertIs(transaction.adapter, transaction_adapter)

    def test_synthetic_adapter_cannot_enter_production_bootstrap(self):
        binding, _composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        synthetic = SyntheticPreflightProductionV2.create(
            binding=binding,
            observed_at_epoch=lambda: 2_300_000_000,
        )

        with self.assertRaises(ProductionBindingError):
            require_reviewed_bound_production_adapter_v1(
                binding=binding,
                slot=ProductionAdapterSlotV1.PREFLIGHT,
                bound=synthetic._adapter,
            )
        with self.assertRaises(TypeError):
            PreflightProductionBootstrapV2.create(
                binding=binding,
                reviewed_binding_receipt=_review_receipt(binding),
                adapter=synthetic._adapter,
                durable_claims=(),
                expected_prior_journal_head_fingerprint=HEAD,
            )

    def test_main_surfaces_remain_default_dormant_and_noninjectable(self):
        cases = (
            (preflight_main, ("current-topology",), "DORMANT_NO_EXTERNAL_ISSUER"),
            (evidence_main, ("publish",), "DORMANT_NO_EXTERNAL_ISSUER"),
            (transaction_main, ("execute",), "DORMANT_NO_EXTERNAL_ISSUER"),
        )
        for main, argv, expected in cases:
            with self.subTest(main=main.__module__):
                self.assertNotIn("terminal", inspect.signature(main).parameters)
                self.assertNotIn(
                    "observed_at_epoch",
                    inspect.signature(main).parameters,
                )
                result = _execute_default(main, argv)
                self.assertIn(expected, result)

    def test_bootstrap_factories_keep_explicit_reviewed_fields(self):
        for bootstrap_type in (
            PreflightProductionBootstrapV2,
            EvidenceProductionBootstrapV2,
            TransactionProductionBootstrapV2,
        ):
            parameters = inspect.signature(bootstrap_type.create).parameters
            with self.subTest(bootstrap=bootstrap_type.__name__):
                self.assertIn("reviewed_binding_receipt", parameters)
                self.assertIn("adapter", parameters)
                self.assertFalse(
                    any(
                        item.kind is inspect.Parameter.VAR_KEYWORD
                        for item in parameters.values()
                    )
                )

    def test_wrong_bootstrap_type_blocks_without_system_tty(self):
        cases = (
            (
                preflight_main,
                ("current-topology",),
                "BLOCKED_COMPOSITION accepted=0 rejected=1 read_operations=0\n",
            ),
            (
                evidence_main,
                ("publish",),
                "BLOCKED_PUBLICATION accepted=0 rejected=1 published=0\n",
            ),
            (
                transaction_main,
                ("execute",),
                "BLOCKED_ACTION accepted=0 rejected=1 mutations=0\n",
            ),
        )
        for main, argv, expected in cases:
            with self.subTest(main=main.__module__):
                self.assertEqual(_execute_with_bootstrap(main, argv, object()), expected)

    def test_tampered_review_receipt_cannot_open_bootstrap(self):
        binding, composition, scope = _preflight_context()
        self.addCleanup(scope.close)
        adapter = bind_production_adapter_v1(
            binding=binding,
            adapter=PreflightProductionAdapterV1.create(
                binding=binding,
                composition=composition,
                evidence_publication_receipt=None,
                recovery_receipt=None,
            ),
        )
        receipt = _review_receipt(binding)
        original = receipt.verified
        try:
            object.__setattr__(receipt, "verified", 0)
            with self.assertRaises((ProductionBindingError, TypeError)):
                PreflightProductionBootstrapV2.create(
                    binding=binding,
                    reviewed_binding_receipt=receipt,
                    adapter=adapter,
                    durable_claims=(),
                    expected_prior_journal_head_fingerprint=HEAD,
                )
        finally:
            object.__setattr__(receipt, "verified", original)


def _review_receipt(binding):
    final = FinalMasterBindingV1.create(
        final_commit_oid=binding.final_commit_oid,
        final_tree_oid=binding.final_tree_oid,
        source_package_fingerprint=binding.source_package_fingerprint,
        runbook_fingerprint=binding.runbook_fingerprint,
        workflow_fingerprint=binding.workflow_fingerprint,
    )
    return reviewed_production_binding_receipt_v2(final, binding)


def _execute_default(main, argv):
    import io
    from contextlib import redirect_stdout

    output = io.StringIO()
    with redirect_stdout(output):
        self_code = main(argv=argv)
    if self_code != 0:
        raise AssertionError(self_code)
    return output.getvalue()


def _execute_with_bootstrap(main, argv, bootstrap):
    import io
    from contextlib import redirect_stdout

    output = io.StringIO()
    with redirect_stdout(output):
        code = main(argv=argv, bootstrap=bootstrap)
    if code != 0:
        raise AssertionError(code)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
