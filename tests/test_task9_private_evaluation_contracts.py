"""Documentation contracts for Task 9 private real-mail evaluation V2."""

from __future__ import annotations

import unittest
from pathlib import Path

from backend.private_evaluation import EvaluationDatasetV1, PrivateEvaluationError


ROOT = Path(__file__).resolve().parents[1]

GOVERNANCE_DOCS = (
    "docs/operations/private_deepseek_evaluation.md",
    "docs/operations/authorized_mailbox_ingest_task_brief.md",
    "docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md",
)

CONSTRAINT_DOCS = (
    "docs/constraints/architecture_constraints.md",
    "docs/constraints/tooling_constraints.md",
    "docs/constraints/linter_constraints.md",
)


class Task9PrivateEvaluationContractTests(unittest.TestCase):
    def _read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_v2_binds_an_ordered_thread_and_reviewed_attachments(self) -> None:
        contract = self._read("docs/operations/private_deepseek_evaluation.md")
        for marker in (
            "PrivateEvaluationCaseV2",
            "DeidentifiedThreadSegmentV2",
            "ReviewedAttachmentBindingV2",
            "oldest-to-newest",
            "current_message",
            "reviewed attachment bindings",
            "V1 datasets remain valid and readable",
            "no in-place V1-to-V2 migration",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, contract)

    def test_v2_uses_a_sealed_independent_human_reference(self) -> None:
        markers = (
            "StructuredHumanReferenceV2",
            "candidate/reference separation",
            "before candidate generation",
            "independent business and privacy_security approvals",
            "distinct actors",
            "blinded human judge",
            "provider and model identity",
            "aggregate-only reporting",
            "Candidate generation receives only the approved deidentified evidence",
            "cannot access or decrypt the reference, approvals, rubric, or prior verdict",
        )
        for relative in GOVERNANCE_DOCS:
            text = self._read(relative)
            with self.subTest(path=relative):
                for marker in markers:
                    self.assertIn(marker, text)

    def test_v2_exact_current_and_attachment_revisions_fail_closed(self) -> None:
        contract = self._read("docs/operations/private_deepseek_evaluation.md")
        for marker in (
            "selected exact current raw record",
            "appears exactly once",
            "must not reappear as historical_message",
            "current request must bind to that current_message segment",
            "immutable attachment evidence-and-association revision",
            "any evidence, truncation state, limitation, or segment association changes",
            "invalidates both approvals",
            "fail closed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, contract)

    def test_v2_prohibits_transcript_training_upload_and_self_grading(self) -> None:
        for relative in GOVERNANCE_DOCS:
            text = self._read(relative)
            with self.subTest(path=relative):
                for marker in (
                    "raw ChatGPT transcripts",
                    "automatic training",
                    "automatic upload",
                    "model self-grading",
                    "automatic production model switch",
                ):
                    self.assertIn(marker, text)

    def test_v2_is_documentation_only_and_v1_stays_compatible(self) -> None:
        combined = "\n".join(self._read(path) for path in GOVERNANCE_DOCS)
        for marker in (
            "documentation-only V2 contract",
            "does not implement V2",
            "does not open a real V2 dataset",
            "V1 compatibility",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, combined)

    def test_constraints_pin_the_future_v2_boundary(self) -> None:
        markers = (
            "PrivateEvaluationCaseV2",
            "ordered deidentified thread segments",
            "reviewed attachment bindings",
            "StructuredHumanReferenceV2",
            "candidate/reference separation",
            "blinded human judge",
            "aggregate-only reporting",
            "V1 compatibility",
            "documentation-only",
            "raw ChatGPT transcripts",
            "automatic training",
            "automatic upload",
            "model self-grading",
            "automatic production model switch",
        )
        for relative in CONSTRAINT_DOCS:
            text = self._read(relative)
            with self.subTest(path=relative):
                for marker in markers:
                    self.assertIn(marker, text)

    def test_current_v1_runtime_has_no_v2_surface_and_rejects_v2_schema(self) -> None:
        runtime_roots = (
            ROOT / "backend" / "private_evaluation",
            ROOT / "scripts" / "evaluate_private_deepseek.py",
            ROOT / "scripts" / "manage_mailbox_vault.py",
        )
        runtime_files: list[Path] = []
        for root in runtime_roots:
            runtime_files.extend(root.rglob("*.py") if root.is_dir() else (root,))
        for path in runtime_files:
            with self.subTest(path=path.relative_to(ROOT)):
                runtime_text = path.read_text(encoding="utf-8")
                for marker in (
                    "PrivateEvaluationCaseV2",
                    "PrivateEvaluationDatasetV2",
                    "EvaluationDatasetV2",
                    "EvaluationStageV2",
                    "StructuredHumanReferenceV2",
                    "--migrate-v2",
                ):
                    self.assertNotIn(marker, runtime_text)

        with self.assertRaises(PrivateEvaluationError) as caught:
            EvaluationDatasetV1.from_mapping({
                "schema_version": "PrivateEvaluationDatasetV2",
                "dataset_namespace": "00000000-0000-4000-8000-000000000000",
                "cases": [],
            })
        self.assertEqual("dataset_schema_invalid", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
