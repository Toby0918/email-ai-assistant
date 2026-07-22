"""Synthetic Task 9 attachment completeness contracts."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from backend.email_agent.attachment_docx import collect_docx_text
from backend.email_agent.attachment_model_context import (
    MAX_MODEL_CHARACTERS_PER_ATTACHMENT,
    AttachmentModelCandidate,
    build_attachment_model_context,
)
from backend.email_agent.attachment_storage import StoredAttachment
from backend.email_agent.attachment_text import text_insight
from backend.email_agent.prompt_context import build_deepseek_untrusted_context
from backend.email_agent.thread_timeline import ThreadSource, TimelineBuild


class Task9AttachmentSemanticTests(unittest.TestCase):
    def setUp(self) -> None:
        self.item = StoredAttachment(
            safe_filename="synthetic-document.docx",
            type="docx",
            path=Path("synthetic-document.docx"),
            byte_size=1,
            expires_at=datetime.now(UTC),
        )
        public_timeline = {
            "previous_context": "Synthetic prior request.",
            "current_status": "unresolved",
            "status_reason": "Synthetic review remains open.",
            "latest_external_request": "Please review the document.",
            "latest_internal_commitment": "No commitment recorded.",
            "open_items": [],
            "confidence": "medium",
        }
        self.timeline = TimelineBuild(
            public_timeline,
            (),
            (
                ThreadSource(
                    "thread:0",
                    "External buyer",
                    "Internal sales",
                    "",
                    "Synthetic document review",
                    "Please review the attached document.",
                ),
            ),
        )

    def test_late_structured_docx_fact_remains_in_private_candidate(self) -> None:
        late_fact = "Minimum order quantity is 1024 units."
        document = SimpleNamespace(
            paragraphs=[
                SimpleNamespace(text=(f"Section {index} " + ("detail " * 110)))
                for index in range(7)
            ]
            + [SimpleNamespace(text=late_fact)],
            tables=[],
        )

        text, fact_text, limitations = collect_docx_text(document)
        bundle = text_insight(
            self.item,
            "attachment:0",
            text,
            limitations,
            "DOCX",
            fact_text=fact_text,
        )

        self.assertIsNotNone(bundle.model_candidate)
        self.assertIn(late_fact, bundle.model_candidate.text)

    def test_fixed_parser_limitations_reach_private_prompt_metadata(self) -> None:
        limitation = "Paragraph limit reached; remaining paragraphs were not parsed."
        bundle = text_insight(
            self.item,
            "attachment:0",
            "The reviewed section contains bounded synthetic detail.",
            [limitation],
            "DOCX",
        )
        candidate = bundle.model_candidate
        self.assertIsNotNone(candidate)
        self.assertTrue(getattr(candidate, "parser_truncated", False))
        self.assertEqual(getattr(candidate, "parser_limitations", ()), (limitation,))

        context = build_attachment_model_context((candidate,))
        prompt = self._prompt(context)
        source = self._attachment_source(prompt)

        self.assertTrue(source["parser_truncated"])
        self.assertFalse(source["model_text_truncated"])
        self.assertEqual(source["parser_limitations"], [limitation])

    def test_model_projection_truncation_reaches_private_prompt_metadata(self) -> None:
        raw = "Bounded synthetic detail. " * (
            MAX_MODEL_CHARACTERS_PER_ATTACHMENT // 8
        )
        context = build_attachment_model_context(
            (AttachmentModelCandidate("attachment:0", raw),)
        )

        source = self._attachment_source(self._prompt(context))

        self.assertTrue(source.get("model_text_truncated", False))
        self.assertFalse(source.get("parser_truncated", False))
        self.assertEqual(source.get("parser_limitations", []), [])

    def _prompt(self, context: tuple[object, ...]) -> str:
        prompt, _sources = build_deepseek_untrusted_context(
            subject="Synthetic document review",
            sender="External buyer",
            recipients=("Internal sales",),
            cc=(),
            sent_at="",
            clean_body="Please review the attached document.",
            timeline=self.timeline,
            attachment_context=context,
            attachment_public_sources={
                "attachment:0": "attachment:synthetic-document.docx"
            },
        )
        return prompt

    @staticmethod
    def _attachment_source(prompt: str) -> dict[str, object]:
        payload = json.loads(prompt)
        return next(
            source
            for source in payload["sources"]
            if source["source_id"] == "attachment:0"
        )


if __name__ == "__main__":
    unittest.main()
