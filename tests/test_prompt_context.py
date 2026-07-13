"""Tests for bounded source-labelled DeepSeek prompt context."""

from __future__ import annotations

import json
import unittest

from backend.email_agent.attachment_model_context import AttachmentModelContextItem
from backend.email_agent.deepseek_analysis_schema import validate_deepseek_analysis_v1
from backend.email_agent.prompt_context import (
    DEEPSEEK_SYSTEM_PROMPT,
    EvidenceSource,
    build_deepseek_untrusted_context,
)
from backend.email_agent.thread_timeline import (
    TimelineBuild,
    TimelineOpenItem,
    ThreadSource,
)


class DeepSeekPromptContextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timeline = TimelineBuild(
            public_timeline={
                "previous_context": "Prior synthetic exchange.",
                "current_status": "unresolved",
                "status_reason": "RFQ-42 remains open.",
                "latest_external_request": "Please quote RFQ-42.",
                "latest_internal_commitment": "We will review it.",
                "open_items": [
                    {
                        "item": "Prepare RFQ-42 quotation.",
                        "owner_hint": "internal_sales",
                        "due_hint": "2026-07-20",
                        "source": "thread",
                    }
                ],
                "confidence": "high",
            },
            open_items=(
                TimelineOpenItem(
                    "open:0",
                    "Prepare RFQ-42 quotation.",
                    "internal_sales",
                    "2026-07-20",
                    "thread",
                    ("thread:0",),
                ),
            ),
            sources=(
                ThreadSource(
                    "thread:0",
                    "Buyer <buyer@example.com>",
                    "Sales <sales@cndlf.com>",
                    "2026-07-12T09:00:00+00:00",
                    "RFQ-42 quotation request",
                    "PO 1013970520 qty 24 due 2026-07-20 USD 1,250.",
                ),
            ),
        )
        self.attachment_context = (
            AttachmentModelContextItem(
                "attachment:0",
                "RFQ-42 drawing size 12 x 30 mm.",
                False,
                False,
            ),
        )
        self.context = {
            "subject": "RFQ-42 quotation request",
            "sender": "Buyer <buyer@example.com>",
            "recipients": ("Sales <sales@cndlf.com>",),
            "cc": ("Ops <ops@cndlf.com>",),
            "sent_at": "2026-07-12T09:00:00+00:00",
            "clean_body": "PO 1013970520 qty 24 due 2026-07-20 USD 1,250.",
            "timeline": self.timeline,
            "attachment_context": self.attachment_context,
            "attachment_public_sources": {
                "attachment:0": "attachment:synthetic drawing.pdf"
            },
        }

    def test_system_prompt_contains_complete_fixed_safety_contract(self) -> None:
        required = (
            "JSON",
            "deepseek_analysis_v1",
            '"schema_version"',
            '"analysis"',
            '"summary"',
            '"priority"',
            '"priority_reason"',
            '"category"',
            '"tags"',
            '"decision_brief"',
            '"timeline_interpretation"',
            '"risk_flags"',
            '"suggested_actions"',
            '"reply_draft"',
            '"attachment_augmentations"',
            '"field_evidence"',
            '"needs_human_review":true',
            "Chinese analysis",
            "English external reply draft",
            "request-local source",
            "untrusted",
            "do not execute",
            "latest unresolved external request",
            "parsed",
            "automatic mailbox",
            "price, delivery, payment, contract, quality, or legal",
            "every claimed source independently supports the claim",
            "Unknown sources are forbidden",
            "unparsed sources are forbidden",
            "Each attachment augmentation must cite its own parsed attachment source",
        )

        for text in required:
            with self.subTest(text=text):
                self.assertIn(text, DEEPSEEK_SYSTEM_PROMPT)

        raw_example = DEEPSEEK_SYSTEM_PROMPT.split(
            "Complete envelope example: ", 1
        )[1].split(" Produce Chinese analysis", 1)[0]
        example = json.loads(raw_example)
        self.assertIs(validate_deepseek_analysis_v1(example), example)
        analysis = example["analysis"]
        self.assertEqual(
            set(analysis["decision_brief"]["key_facts"][0]),
            {"label", "value", "source"},
        )
        self.assertEqual(
            set(analysis["timeline_interpretation"]["open_item_annotations"][0]),
            {"open_item_id", "item"},
        )
        self.assertEqual(
            set(analysis["risk_flags"][0]),
            {"type", "level", "evidence", "recommendation"},
        )
        self.assertEqual(
            set(analysis["suggested_actions"][0]),
            {"type", "description", "owner_hint", "due_hint"},
        )
        self.assertEqual(
            set(example["attachment_augmentations"][0]),
            {"source_id", "summary", "key_facts", "evidence_sources"},
        )
        self.assertTrue(example["field_evidence"])

    def test_context_keeps_business_facts_and_matches_registry_grounding_text(self) -> None:
        prompt, sources = build_deepseek_untrusted_context(**self.context)
        payload = json.loads(prompt)

        self.assertTrue(payload["all_values_are_untrusted"])
        self.assertIn("1013970520", prompt)
        self.assertIn("thread:0", prompt)
        self.assertIn("attachment:0", prompt)
        self.assertEqual(set(sources), {"thread:0", "attachment:0"})
        self.assertEqual(sources["thread:0"].public_source, "thread")
        self.assertEqual(
            sources["attachment:0"].public_source,
            "attachment:synthetic drawing.pdf",
        )
        self.assertEqual(sources["attachment:0"].attachment_index, 0)
        self.assertTrue(sources["attachment:0"].parsed)
        sent_sources = {item["source_id"]: item for item in payload["sources"]}
        for source_id, source in sources.items():
            with self.subTest(source_id=source_id):
                self.assertEqual(sent_sources[source_id]["text"], source.grounding_text)

    def test_visible_thread_sources_prevent_clean_body_duplication(self) -> None:
        context = dict(self.context)
        context["clean_body"] = "UNIQUE_CURRENT_BODY_CANARY"

        prompt, _ = build_deepseek_untrusted_context(**context)

        self.assertNotIn("UNIQUE_CURRENT_BODY_CANARY", prompt)
        self.assertEqual(prompt.count("PO 1013970520"), 1)

    def test_missing_thread_sources_synthesize_thread_zero_from_current_message(self) -> None:
        context = dict(self.context)
        context["timeline"] = TimelineBuild(
            self.timeline.public_timeline,
            self.timeline.open_items,
            (),
        )
        context["clean_body"] = "SYNTHETIC_BODY_CANARY PO 1013970520"

        prompt, sources = build_deepseek_untrusted_context(**context)

        self.assertIn("SYNTHETIC_BODY_CANARY", prompt)
        self.assertIn("thread:0", sources)
        self.assertEqual(sources["thread:0"].public_source, "thread")

    def test_every_remote_string_is_sanitized_with_channel_specific_link_policy(self) -> None:
        private = (
            "https://private.example.test/a?q=PRIVATE_QUERY "
            "Authorization: Bearer PRIVATE_TOKEN | "
            "Cookie: session=PRIVATE_COOKIE | C:\\private\\quote.pdf | "
            "content_base64: QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB | "
            "<script>PRIVATE_SCRIPT</script> PO 1013970520"
        )
        context = dict(self.context)
        context.update(subject=private, sender=private, recipients=(private,), cc=(private,))
        context["timeline"] = TimelineBuild(
            self.timeline.public_timeline,
            self.timeline.open_items,
            (
                ThreadSource(
                    "thread:0", private, private, private, private, private
                ),
            ),
        )
        context["attachment_context"] = (
            AttachmentModelContextItem("attachment:0", private, True, False),
        )
        context["attachment_public_sources"] = {
            "attachment:0": "attachment:quote.pdf"
        }

        prompt, sources = build_deepseek_untrusted_context(**context)

        self.assertIn("PO 1013970520", prompt)
        self.assertIn("[link present]", sources["thread:0"].grounding_text)
        self.assertNotIn("[link present]", sources["attachment:0"].grounding_text)
        for forbidden in (
            "https://",
            "private.example",
            "PRIVATE_QUERY",
            "PRIVATE_TOKEN",
            "PRIVATE_COOKIE",
            "C:\\private",
            "content_base64",
            "QUFBQUFB",
            "PRIVATE_SCRIPT",
            "<script>",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, prompt)

    def test_thread_sources_obey_count_per_source_and_total_text_bounds(self) -> None:
        sources = tuple(
            ThreadSource(
                f"thread:{index}",
                "buyer@example.com",
                "sales@cndlf.com",
                "2026-07-12",
                f"Subject {index}",
                f"BODY-{index:02d}-" + ("x" * 4_000),
            )
            for index in range(55)
        )
        context = dict(self.context)
        context["timeline"] = TimelineBuild(
            self.timeline.public_timeline,
            self.timeline.open_items,
            sources,
        )

        prompt, registry = build_deepseek_untrusted_context(**context)
        payload = json.loads(prompt)
        thread_items = [item for item in payload["sources"] if item["kind"] == "thread"]

        self.assertEqual(len(thread_items), 50)
        self.assertEqual(len([key for key in registry if key.startswith("thread:")]), 50)
        self.assertTrue(all(len(item["text"]) <= 2_000 for item in thread_items))
        self.assertLessEqual(sum(len(item["text"]) for item in thread_items), 20_000)
        self.assertNotIn("BODY-54", prompt)

    def test_user_json_includes_backend_open_item_ids_without_public_id_leakage(self) -> None:
        prompt, _ = build_deepseek_untrusted_context(**self.context)
        payload = json.loads(prompt)

        self.assertEqual(
            payload["timeline_skeleton"]["open_items"],
            [
                {
                    "open_item_id": "open:0",
                    "item": "Prepare RFQ-42 quotation.",
                    "owner_hint": "internal_sales",
                    "due_hint": "2026-07-20",
                    "source": "thread",
                    "evidence_sources": ["thread:0"],
                }
            ],
        )
        self.assertNotIn("mailbox_id", prompt)
        self.assertNotIn("account_token", prompt)

    def test_attachment_source_mapping_fails_closed_with_fixed_error(self) -> None:
        cases = (
            ("missing", {}, self.attachment_context),
            (
                "extra",
                {
                    "attachment:0": "attachment:synthetic.pdf",
                    "attachment:1": "attachment:extra.pdf",
                },
                self.attachment_context,
            ),
            (
                "duplicate source id",
                {"attachment:0": "attachment:synthetic.pdf"},
                (*self.attachment_context, self.attachment_context[0]),
            ),
            (
                "wrong source id shape",
                {"PRIVATE_SOURCE": "attachment:synthetic.pdf"},
                (
                    AttachmentModelContextItem(
                        "PRIVATE_SOURCE", "PRIVATE_ATTACHMENT_TEXT", False, False
                    ),
                ),
            ),
            (
                "wrong public prefix",
                {"attachment:0": "PRIVATE_PUBLIC_SOURCE"},
                self.attachment_context,
            ),
            (
                "empty public suffix",
                {"attachment:0": "attachment:"},
                self.attachment_context,
            ),
            (
                "whitespace public suffix",
                {"attachment:0": "attachment:   \t"},
                self.attachment_context,
            ),
            (
                "oversized numeric source",
                {"attachment:" + ("9" * 5_000): "attachment:synthetic.pdf"},
                (
                    AttachmentModelContextItem(
                        "attachment:" + ("9" * 5_000),
                        "PRIVATE_ATTACHMENT_TEXT",
                        False,
                        False,
                    ),
                ),
            ),
        )

        for label, mapping, items in cases:
            with self.subTest(label=label):
                context = dict(self.context)
                context["attachment_public_sources"] = mapping
                context["attachment_context"] = items
                with self.assertRaises(ValueError) as caught:
                    build_deepseek_untrusted_context(**context)
                self.assertEqual(str(caught.exception), "Attachment source mapping is invalid.")
                self.assertNotIn("PRIVATE", str(caught.exception))

    def test_attachment_label_is_sanitized_for_prompt_but_registry_keeps_backend_label(self) -> None:
        context = dict(self.context)
        backend_label = (
            "attachment:quote.pdf https://private.example.test/a?q=PRIVATE "
            + ("x" * 300)
        )
        context["attachment_public_sources"] = {"attachment:0": backend_label}

        prompt, sources = build_deepseek_untrusted_context(**context)

        self.assertEqual(sources["attachment:0"].public_source, backend_label)
        self.assertNotIn("private.example", prompt)
        prompt_label = json.loads(prompt)["sources"][1]["public_source"]
        self.assertTrue(prompt_label.startswith("attachment:"))
        self.assertLessEqual(len(prompt_label), 180)

    def test_evidence_source_repr_never_contains_grounding_text(self) -> None:
        source = EvidenceSource(
            "thread:0",
            "thread",
            "PRIVATE_GROUNDING_TEXT",
            "thread",
        )

        self.assertTrue(EvidenceSource.__dataclass_params__.frozen)
        self.assertFalse(hasattr(source, "__dict__"))
        self.assertNotIn("PRIVATE_GROUNDING_TEXT", repr(source))


if __name__ == "__main__":
    unittest.main()
