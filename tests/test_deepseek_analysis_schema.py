"""Tests for the private versioned DeepSeek analysis envelope."""

from __future__ import annotations

import copy
import json
import sys
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from backend.email_agent import deepseek_analysis_contract as contract
from backend.email_agent import deepseek_analysis_schema as schema
from backend.email_agent.deepseek_analysis_schema import (
    DeepSeekEnvelopeError,
    canonical_json_pointer,
    parse_deepseek_analysis_v1,
    validate_deepseek_analysis_v1,
    validate_envelope_evidence,
)


ERROR_TEXT = "DeepSeek analysis envelope is invalid."


def valid_envelope() -> dict[str, Any]:
    return {
        "schema_version": "deepseek_analysis_v1",
        "analysis": {
            "summary": "Synthetic summary",
            "priority": "high",
            "priority_reason": "A synthetic deadline needs review.",
            "category": "order_followup",
            "tags": ["deadline"],
            "decision_brief": {
                "one_line_conclusion": "Review the synthetic request.",
                "requested_outcome": "Confirm the next step.",
                "next_steps": [
                    {
                        "step": "Review the request.",
                        "owner_hint": "Sales",
                        "due_hint": "Today",
                        "source": "thread",
                    }
                ],
                "key_facts": [
                    {
                        "label": "Reference",
                        "value": "SYNTHETIC-001",
                        "source": "thread",
                    }
                ],
                "must_check": ["Confirm the date."],
                "missing_info": ["Final approval is missing."],
                "reply_recommendation": {
                    "should_reply": True,
                    "reply_type": "acknowledge",
                    "reason": "A response is appropriate.",
                },
                "confidence": "high",
            },
            "timeline_interpretation": {
                "previous_context": "A prior synthetic request exists.",
                "status_reason": "The request remains open.",
                "open_item_annotations": [
                    {"open_item_id": "open:0", "item": "Confirm the date."}
                ],
                "evidence_sources": ["thread:0"],
            },
            "risk_flags": [
                {
                    "type": "delivery_risk",
                    "level": "high",
                    "evidence": "The synthetic deadline is near.",
                    "recommendation": "Confirm feasibility first.",
                }
            ],
            "suggested_actions": [
                {
                    "type": "reply",
                    "description": "Acknowledge the request.",
                    "owner_hint": "Sales",
                    "due_hint": "Today",
                }
            ],
            "reply_draft": {
                "subject": "Re: Synthetic request",
                "body": "Thank you. We will review the request.",
                "needs_human_review": True,
                "review_reasons": ["Confirm the deadline before sending."],
            },
        },
        "attachment_augmentations": [
            {
                "source_id": "attachment:0",
                "summary": "Synthetic attachment summary.",
                "key_facts": ["Synthetic attachment fact."],
                "evidence_sources": ["attachment:0"],
            }
        ],
        "field_evidence": {
            "/analysis/summary": ["thread:0"],
        },
    }


class DuplicateEvidence(dict[str, list[str]]):
    def items(self):  # type: ignore[override]
        return iter(
            (
                ("/analysis/summary", ["thread:0"]),
                ("/analysis/summary", ["thread:0"]),
            )
        )


class DeepSeekAnalysisSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sources = {"thread:0": object(), "attachment:0": object()}

    def assert_invalid(
        self,
        operation: Callable[[], object],
        *,
        detail: str | None = None,
    ) -> None:
        with self.assertRaises(DeepSeekEnvelopeError) as caught:
            operation()
        self.assertEqual(str(caught.exception), ERROR_TEXT)
        self.assertIsNone(caught.exception.__cause__)
        if detail is not None:
            self.assertEqual(getattr(caught.exception, "detail", None), detail)

    def test_exception_detail_is_allowlisted_and_public_message_remains_generic(
        self,
    ) -> None:
        class StringSubclass(str):
            pass

        private_marker = "PRIVATE_FREE_FORM_DETAIL"
        cases: tuple[tuple[object, str], ...] = (
            ("json_syntax", "json_syntax"),
            (private_marker, "not_applicable"),
            (StringSubclass("json_syntax"), "not_applicable"),
        )

        for detail, expected in cases:
            with self.subTest(detail=detail, expected=expected):
                error = DeepSeekEnvelopeError(detail)
                self.assertEqual(getattr(error, "detail", None), expected)
                self.assertEqual(str(error), ERROR_TEXT)
                self.assertNotIn(private_marker, str(error))
                self.assertNotIn("json_syntax", str(error))

    def test_parse_reports_json_syntax_detail(self) -> None:
        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1("{not-json"),
            detail="json_syntax",
        )

    def test_parse_reports_top_level_shape_detail(self) -> None:
        candidate = valid_envelope()
        candidate["unexpected"] = True

        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
            detail="top_level_shape",
        )

    def test_parse_reports_schema_version_detail(self) -> None:
        candidate = valid_envelope()
        candidate["schema_version"] = "other"

        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
            detail="schema_version",
        )

    def test_parse_reports_analysis_shape_detail(self) -> None:
        candidate = valid_envelope()
        candidate["analysis"]["priority"] = "PRIVATE_INVALID"

        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
            detail="analysis_shape",
        )

    def test_parse_reports_attachment_shape_detail(self) -> None:
        candidate = valid_envelope()
        candidate["attachment_augmentations"][0]["source_id"] = 7

        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
            detail="attachment_shape",
        )

    def test_parse_reports_field_evidence_shape_detail(self) -> None:
        candidate = valid_envelope()
        candidate["field_evidence"]["summary"] = "not-a-list"

        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1(json.dumps(candidate)),
            detail="field_evidence_shape",
        )

    def test_private_envelope_modules_stay_within_line_limit(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        relative_paths = (
            Path("backend/email_agent/deepseek_envelope_errors.py"),
            Path("backend/email_agent/deepseek_analysis_schema.py"),
            Path("backend/email_agent/deepseek_analysis_contract.py"),
        )

        for relative_path in relative_paths:
            with self.subTest(path=str(relative_path)):
                module_path = project_root / relative_path
                self.assertTrue(module_path.is_file(), f"missing {relative_path}")
                self.assertLessEqual(
                    len(module_path.read_text(encoding="utf-8").splitlines()),
                    300,
                )

    def test_validator_reexports_the_canonical_immutable_contract(self) -> None:
        names = (
            "SCHEMA_VERSION",
            "ENVELOPE_FIELDS",
            "ANALYSIS_FIELDS",
            "DECISION_FIELDS",
            "NEXT_STEP_FIELDS",
            "KEY_FACT_FIELDS",
            "REPLY_RECOMMENDATION_FIELDS",
            "TIMELINE_FIELDS",
            "OPEN_ANNOTATION_FIELDS",
            "RISK_FIELDS",
            "ACTION_FIELDS",
            "REPLY_FIELDS",
            "ATTACHMENT_FIELDS",
            "APPROVED_EVIDENCE_PATTERNS",
        )

        for name in names:
            with self.subTest(name=name):
                self.assertIs(getattr(schema, name), getattr(contract, name))
        self.assertIsInstance(contract.ENVELOPE_FIELDS, frozenset)
        self.assertIsInstance(contract.APPROVED_EVIDENCE_PATTERNS, frozenset)

    def test_parse_accepts_complete_versioned_envelope(self) -> None:
        raw = json.dumps(valid_envelope())

        parsed = parse_deepseek_analysis_v1(raw)

        self.assertEqual(parsed, valid_envelope())

    def test_duplicate_raw_json_keys_fail_closed_at_multiple_depths(self) -> None:
        top_level = (
            '{"schema_version":"deepseek_analysis_v1",'
            '"schema_version":"other"}'
        )
        nested = json.dumps(valid_envelope()).replace(
            '"summary": "Synthetic summary"',
            '"summary": "Synthetic summary", "summary": "PRIVATE_DUPLICATE"',
            1,
        )

        for raw in (top_level, nested):
            with self.subTest(raw=raw[:40]):
                self.assert_invalid(
                    lambda raw=raw: parse_deepseek_analysis_v1(raw),
                    detail="json_syntax",
                )

    def test_parse_errors_are_generic_and_do_not_expose_raw_json(self) -> None:
        marker = "PRIVATE_RAW_JSON_MARKER"

        with self.assertRaises(DeepSeekEnvelopeError) as caught:
            parse_deepseek_analysis_v1('{"analysis":"' + marker)

        self.assertEqual(str(caught.exception), ERROR_TEXT)
        self.assertNotIn(marker, str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_oversized_json_integer_uses_fixed_generic_error(self) -> None:
        digit_limit = sys.get_int_max_str_digits()
        self.assertGreater(digit_limit, 0)
        oversized_integer = "9" * (digit_limit + 1)

        self.assert_invalid(
            lambda: parse_deepseek_analysis_v1(oversized_integer),
            detail="json_syntax",
        )

    def test_envelope_requires_exact_top_level_keys_and_version(self) -> None:
        cases: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("wrong version", lambda value: value.update(schema_version="other")),
            ("missing key", lambda value: value.pop("attachment_augmentations")),
            ("unknown key", lambda value: value.update(unexpected=True)),
            ("not object", lambda value: value.update(analysis=[])),
        )

        for label, mutate in cases:
            with self.subTest(label=label):
                envelope = valid_envelope()
                mutate(envelope)
                self.assert_invalid(lambda: validate_deepseek_analysis_v1(envelope))

    def test_complete_nested_shape_and_enums_fail_closed(self) -> None:
        cases: tuple[tuple[str, Callable[[dict[str, Any]], None]], ...] = (
            ("analysis extra", lambda e: e["analysis"].update(extra="value")),
            ("summary type", lambda e: e["analysis"].update(summary=[])),
            ("priority enum", lambda e: e["analysis"].update(priority="later")),
            ("category enum", lambda e: e["analysis"].update(category="sales")),
            ("tag item", lambda e: e["analysis"].update(tags=[7])),
            (
                "decision missing",
                lambda e: e["analysis"]["decision_brief"].pop("confidence"),
            ),
            (
                "decision next steps",
                lambda e: e["analysis"]["decision_brief"].update(next_steps=[]),
            ),
            (
                "decision too many next steps",
                lambda e: e["analysis"]["decision_brief"].update(
                    next_steps=e["analysis"]["decision_brief"]["next_steps"] * 5
                ),
            ),
            ("required null", lambda e: e["analysis"].update(summary=None)),
            (
                "decision next step extra",
                lambda e: e["analysis"]["decision_brief"]["next_steps"][0].update(
                    extra="value"
                ),
            ),
            (
                "decision reply type",
                lambda e: e["analysis"]["decision_brief"][
                    "reply_recommendation"
                ].update(reply_type="auto_send"),
            ),
            (
                "timeline source list",
                lambda e: e["analysis"]["timeline_interpretation"].update(
                    evidence_sources="thread:0"
                ),
            ),
            (
                "timeline annotation",
                lambda e: e["analysis"]["timeline_interpretation"][
                    "open_item_annotations"
                ][0].pop("open_item_id"),
            ),
            (
                "risk enum",
                lambda e: e["analysis"]["risk_flags"][0].update(level="urgent"),
            ),
            (
                "action enum",
                lambda e: e["analysis"]["suggested_actions"][0].update(
                    type="send_mail"
                ),
            ),
            (
                "draft review",
                lambda e: e["analysis"]["reply_draft"].update(
                    needs_human_review=False
                ),
            ),
            (
                "attachment source type",
                lambda e: e["attachment_augmentations"][0].update(source_id=7),
            ),
            (
                "attachment fact type",
                lambda e: e["attachment_augmentations"][0].update(
                    key_facts=[{"fact": "nested"}]
                ),
            ),
            ("field evidence type", lambda e: e.update(field_evidence=[])),
        )

        for label, mutate in cases:
            with self.subTest(label=label):
                envelope = valid_envelope()
                mutate(envelope)
                self.assert_invalid(lambda: validate_deepseek_analysis_v1(envelope))

    def test_canonical_json_pointer_handles_root_and_rfc6901_escapes(self) -> None:
        fixture = {"a/b": {"m~n": "synthetic value"}}

        self.assertEqual(canonical_json_pointer(""), ())
        tokens = canonical_json_pointer("/a~1b/m~0n")
        self.assertEqual(tokens, ("a/b", "m~n"))
        self.assertEqual(fixture[tokens[0]][tokens[1]], "synthetic value")

    def test_canonical_json_pointer_rejects_malformed_values(self) -> None:
        for pointer in ("analysis/summary", "/analysis/~", "/analysis/~2bad", 7):
            with self.subTest(pointer=pointer):
                self.assert_invalid(lambda pointer=pointer: canonical_json_pointer(pointer))

    def test_evidence_resolves_root_relative_and_nested_array_text_leaves(self) -> None:
        envelope = valid_envelope()
        pointers = (
            "/analysis/summary",
            "/analysis/tags/0",
            "/analysis/decision_brief/next_steps/0/step",
            "/analysis/decision_brief/key_facts/0/value",
            "/analysis/timeline_interpretation/open_item_annotations/0/item",
            "/analysis/risk_flags/0/recommendation",
            "/analysis/suggested_actions/0/owner_hint",
            "/analysis/reply_draft/review_reasons/0",
            "/attachment_augmentations/0/key_facts/0",
        )
        envelope["field_evidence"] = {
            pointer: ["attachment:0"]
            if pointer.startswith("/attachment_augmentations")
            else ["thread:0"]
            for pointer in pointers
        }

        evidence = validate_envelope_evidence(envelope, self.sources)

        self.assertEqual(set(evidence), set(pointers))
        self.assertEqual(evidence["/analysis/summary"], ("thread:0",))
        self.assertEqual(
            evidence["/attachment_augmentations/0/key_facts/0"],
            ("attachment:0",),
        )

    def test_evidence_rejects_malformed_or_unresolvable_pointers(self) -> None:
        pointers = (
            "",
            "analysis/summary",
            "/analysis/~2bad",
            "/analysis/tags/00",
            "/analysis/tags/-",
            "/analysis/tags/-1",
            "/analysis/tags/one",
            "/analysis/tags/9",
            "/analysis/unknown",
            "/analysis/decision_brief",
        )

        for pointer in pointers:
            with self.subTest(pointer=pointer):
                envelope = valid_envelope()
                envelope["field_evidence"] = {pointer: ["thread:0"]}
                self.assert_invalid(
                    lambda: validate_envelope_evidence(envelope, self.sources)
                )

    def test_oversized_decimal_array_index_uses_fixed_generic_error(self) -> None:
        digit_limit = sys.get_int_max_str_digits()
        self.assertGreater(digit_limit, 0)
        oversized_index = "9" * (digit_limit + 1)
        envelope = valid_envelope()
        envelope["field_evidence"] = {
            f"/analysis/tags/{oversized_index}": ["thread:0"]
        }

        self.assert_invalid(
            lambda: validate_envelope_evidence(envelope, self.sources)
        )

    def test_evidence_rejects_enum_boolean_and_provider_owned_targets(self) -> None:
        pointers = (
            "/schema_version",
            "/analysis/priority",
            "/analysis/category",
            "/analysis/decision_brief/confidence",
            "/analysis/decision_brief/next_steps/0/source",
            "/analysis/decision_brief/key_facts/0/source",
            "/analysis/decision_brief/reply_recommendation/should_reply",
            "/analysis/timeline_interpretation/open_item_annotations/0/open_item_id",
            "/analysis/timeline_interpretation/evidence_sources/0",
            "/analysis/risk_flags/0/type",
            "/analysis/suggested_actions/0/type",
            "/analysis/reply_draft/needs_human_review",
            "/attachment_augmentations/0/source_id",
            "/attachment_augmentations/0/evidence_sources/0",
            "/field_evidence",
        )

        for pointer in pointers:
            with self.subTest(pointer=pointer):
                envelope = valid_envelope()
                envelope["field_evidence"] = {pointer: ["thread:0"]}
                self.assert_invalid(
                    lambda: validate_envelope_evidence(envelope, self.sources)
                )

    def test_field_evidence_lists_must_be_nonempty_unique_strings(self) -> None:
        invalid_lists: tuple[object, ...] = (
            [],
            ["thread:0", "thread:0"],
            ["thread:0", 7],
            ("thread:0",),
        )

        for source_list in invalid_lists:
            with self.subTest(source_list=source_list):
                envelope = valid_envelope()
                envelope["field_evidence"] = {
                    "/analysis/summary": source_list,
                }
                self.assert_invalid(
                    lambda: validate_envelope_evidence(envelope, self.sources)
                )

    def test_field_evidence_rejects_unknown_source_ids(self) -> None:
        envelope = valid_envelope()
        envelope["field_evidence"] = {
            "/analysis/summary": ["PRIVATE_UNKNOWN_SOURCE"]
        }

        self.assert_invalid(
            lambda: validate_envelope_evidence(envelope, self.sources)
        )

    def test_all_provider_source_lists_reject_unknown_ids_globally(self) -> None:
        def unknown_timeline(e: dict[str, Any]) -> None:
            e["analysis"]["timeline_interpretation"]["evidence_sources"] = [
                "unknown:timeline"
            ]

        def unknown_attachment_evidence(e: dict[str, Any]) -> None:
            e["attachment_augmentations"][0]["evidence_sources"] = [
                "unknown:attachment"
            ]

        def unknown_attachment_source(e: dict[str, Any]) -> None:
            e["attachment_augmentations"][0]["source_id"] = "unknown:source"

        for label, mutate in (
            ("timeline", unknown_timeline),
            ("attachment evidence", unknown_attachment_evidence),
            ("attachment source", unknown_attachment_source),
        ):
            with self.subTest(label=label):
                envelope = valid_envelope()
                mutate(envelope)
                self.assert_invalid(
                    lambda: validate_envelope_evidence(envelope, self.sources)
                )

    def test_duplicate_normalized_targets_fail_closed_when_constructible(self) -> None:
        envelope = valid_envelope()
        envelope["field_evidence"] = DuplicateEvidence()

        self.assert_invalid(
            lambda: validate_envelope_evidence(envelope, self.sources)
        )

    def test_validation_returns_original_envelope_without_public_projection(self) -> None:
        envelope = valid_envelope()
        original = copy.deepcopy(envelope)

        validated = validate_deepseek_analysis_v1(envelope)

        self.assertIs(validated, envelope)
        self.assertEqual(validated, original)


if __name__ == "__main__":
    unittest.main()
