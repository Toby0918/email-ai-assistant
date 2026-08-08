"""Static guards for dormant transaction production and pure helpers."""

import ast
import inspect
import unittest
from pathlib import Path

from backend.r2_transaction_process.production_v2 import (
    TransactionActionCompletionV2,
    TransactionProductionStatusV2,
    dormant_transaction_production_v2,
    main,
    run_transaction_production_v2,
)


ROOT = Path(__file__).resolve().parents[1]
PRODUCTION = ROOT / "backend" / "r2_transaction_process" / "production_v2.py"


class R2TransactionProductionV2ArchitectureTests(unittest.TestCase):
    def test_status_migration_has_no_envelope_or_authority_status(self):
        names = set(TransactionProductionStatusV2.__members__)
        self.assertIn("DORMANT_NO_ISSUE39_APPROVAL", names)
        self.assertTrue(
            {
                "BLOCKED_TTY",
                "BLOCKED_ACKNOWLEDGEMENT",
                "BLOCKED_EXECUTION_CONFIRMATION",
                "BLOCKED_FINGERPRINT",
                "BLOCKED_REPLAY",
                "BLOCKED_ACTION",
            }
            <= names
        )
        self.assertTrue({"BLOCKED_ENVELOPE", "BLOCKED_AUTHORITY"}.isdisjoint(names))

    def test_public_roots_have_no_confirmation_or_adapter_selector(self):
        self.assertEqual(
            set(inspect.signature(dormant_transaction_production_v2).parameters),
            {"argv"},
        )
        self.assertEqual(set(inspect.signature(main).parameters), {"argv", "bootstrap"})
        parameters = set(inspect.signature(run_transaction_production_v2).parameters)
        self.assertTrue(
            parameters.isdisjoint(
                {
                    "candidate",
                    "claim",
                    "path",
                    "root",
                    "target",
                    "issuer",
                    "payload",
                    "retry",
                    "cleanup",
                }
            )
        )

    def test_completion_is_pure_and_not_an_authorization_type(self):
        self.assertEqual(
            TransactionActionCompletionV2.__module__,
            "backend.r2_transaction_process.production_v2",
        )
        tree = ast.parse(PRODUCTION.read_text(encoding="utf-8"))
        imports = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        self.assertNotIn("backend.cutover_contracts.authorization", imports)


if __name__ == "__main__":
    unittest.main()
