"""Architecture guards for the dormant pure confirmation primitive."""

import ast
import inspect
import unittest
from pathlib import Path

import backend.r2_production_binding as production_binding


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_production_binding"


class R2ExecutionConfirmationArchitectureTests(unittest.TestCase):
    def test_only_reviewed_confirmation_runtime_owns_console_and_clock_io(self):
        source = ""
        forbidden_imports = {
            "cryptography",
            "getpass",
            "os",
            "pathlib",
            "requests",
            "socket",
            "subprocess",
            "sys",
            "urllib",
        }
        contract_files = (
            "__init__.py",
            "_binding_body.py",
            "_canonical.py",
            "_claim_body.py",
            "binding.py",
            "claim.py",
            "errors.py",
            "execution_confirmation.py",
            "review.py",
            "vocabulary.py",
        )
        for name in contract_files:
            path = PACKAGE / name
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            source += text
            tree = ast.parse(text, filename=str(path))
            imports = {
                node.module.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
            }
            imports.update(
                alias.name.split(".")[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            )
            if name != "review.py":
                self.assertTrue(imports.isdisjoint(forbidden_imports), path.name)
        confirmation_source = (
            PACKAGE / "review.py"
        ).read_text(encoding="utf-8")
        for required in (
            "isatty",
            "fileno",
            "get_osfhandle",
            "GetConsoleMode",
            "ReadConsoleW",
            "PeekConsoleInputW",
            "monotonic_ns",
            "stdin",
            "stdout",
            "stderr",
        ):
            self.assertIn(required, confirmation_source)
        for forbidden in (
            "ApprovedCutoverBindingV2",
            "DurableAuthorityClaimV2",
            "PublicKeyRoleV2",
            "verification_public_keys",
            "public_key_registry_fingerprint",
            "Ed25519",
            ".sign(",
            "open(",
            "clipboard",
            "pyperclip",
            "os.environ",
            "getenv(",
        ):
            self.assertNotIn(forbidden, source)

    def test_public_confirmation_seams_accept_no_io_or_authority_input(self):
        names = (
            "prepare_execution_confirmation_v1",
            "confirm_execution_confirmation_v1",
            "validate_new_execution_confirmation_claim",
        )
        forbidden = {
            "path",
            "root",
            "argv",
            "stdin",
            "stdout",
            "stderr",
            "terminal",
            "private_key",
            "signature",
            "issue39_approval",
        }
        for name in names:
            parameters = inspect.signature(
                getattr(production_binding, name)
            ).parameters
            self.assertTrue(set(parameters).isdisjoint(forbidden), name)
        self.assertEqual(
            set(
                inspect.signature(
                    production_binding.confirm_execution_confirmation_v1
                ).parameters
            ),
            {"candidate"},
        )
        self.assertNotIn(
            "prepared_at_epoch",
            inspect.signature(
                production_binding.prepare_execution_confirmation_v1
            ).parameters,
        )
        self.assertIn(
            "observed_monotonic_ns",
            inspect.signature(
                production_binding.validate_new_execution_confirmation_claim
            ).parameters,
        )

    def test_production_roots_cannot_reach_confirmation_primitive(self):
        for root in ("preflight", "evidence", "transaction"):
            source = (
                ROOT / "backend" / f"r2_{root}_process" / "production_v2.py"
            ).read_text(encoding="utf-8")
            with self.subTest(root=root):
                self.assertIn("DORMANT_NO_ISSUE39_APPROVAL", source)
                self.assertNotIn("prepare_execution_confirmation_v1", source)
                self.assertNotIn("confirm_execution_confirmation_v1", source)
                self.assertNotIn("ExecutionConfirmationCandidateV1", source)

    def test_live_journal_append_requires_observed_dual_clock(self):
        source = (
            ROOT / "backend" / "r2_transaction_journal_v2" / "journal.py"
        ).read_text(encoding="utf-8")
        method = inspect.signature(
            __import__(
                "backend.r2_transaction_journal_v2",
                fromlist=["R2TransactionJournalV2"],
            ).R2TransactionJournalV2.append_execution_confirmation_claim
        )
        self.assertIn("observed_at_epoch", method.parameters)
        self.assertIn("observed_monotonic_ns", method.parameters)
        create = inspect.signature(
            __import__(
                "backend.r2_transaction_journal_v2",
                fromlist=["R2TransactionJournalV2"],
            ).R2TransactionJournalV2.create
        )
        self.assertIn("observed_at_epoch", create.parameters)
        self.assertIn("observed_monotonic_ns", create.parameters)
        self.assertNotIn(
            "observed_at_epoch=claim.confirmed_at_epoch",
            source,
        )

    def test_adapter_attempt_requires_the_exact_returned_journal_append(self):
        state = (
            ROOT / "backend" / "r2_production_binding" / "review.py"
        ).read_text(encoding="utf-8")
        claim = (
            ROOT / "backend" / "r2_production_binding" / "claim.py"
        ).read_text(encoding="utf-8")
        fixture = (ROOT / "tests" / "r2_execution_confirmation_fixture.py").read_text(
            encoding="utf-8"
        )

        self.assertIn('record.record_type.value == "AUTHORITY_CLAIM"', state)
        self.assertIn("record.execution_confirmation_claim is claim", state)
        self.assertIn("record.predecessor_head_fingerprint", state)
        self.assertIn("len(claims) == claim.claim_sequence", state)
        self.assertIn("claims[-1] is claim", state)
        self.assertIn("current_head_fingerprint", state)
        self.assertIn("complete_append(claim, journal)", claim)
        self.assertIn("consume_append(claim)", claim)
        self.assertNotIn('phase = "APPENDED"', fixture)


if __name__ == "__main__":
    unittest.main()
