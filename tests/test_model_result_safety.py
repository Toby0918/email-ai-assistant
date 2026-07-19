from __future__ import annotations

import copy
import unittest
from unittest.mock import patch

from backend.email_agent.analysis_schema import validate_analysis_result
from backend.email_agent.deepseek_analysis_schema import validate_deepseek_analysis_v1
from backend.email_agent.model_result_safety import SafeMergeResult, merge_deepseek_analysis_v1
from backend.email_agent.model_text_safety import validate_public_language
from backend.email_agent.prompt_context import (
    EvidenceSource,
    build_deepseek_untrusted_context,
)
from backend.email_agent.rule_analyzer import build_rule_based_analysis
from backend.email_agent.thread_timeline import ThreadSource, TimelineBuild, TimelineOpenItem


FIELD_ORDER = (
    "summary",
    "priority",
    "priority_reason",
    "category",
    "tags",
    "decision_brief",
    "conversation_timeline",
    "risk_flags",
    "suggested_actions",
    "reply_draft",
    "attachment_insights",
)
DEFAULT_9B2_FALLBACK_FIELDS = ("risk_flags", "suggested_actions")
UNSAFE_DRAFT_REASON = "模型草稿未通过安全检查，已保留规则草稿。"


def _timeline() -> TimelineBuild:
    public = {
        "previous_context": "客户此前询问了报价。",
        "current_status": "unresolved",
        "status_reason": "客户仍在等待答复。",
        "latest_external_request": "请提供报价和交期。",
        "latest_internal_commitment": "销售将核实后回复。",
        "open_items": [
            {
                "item": "确认产品报价。",
                "owner_hint": "sales",
                "due_hint": "unspecified",
                "source": "thread",
            },
            {
                "item": "确认预计交期。",
                "owner_hint": "operations",
                "due_hint": "unspecified",
                "source": "thread",
            },
        ],
        "confidence": "high",
    }
    open_items = (
        TimelineOpenItem(
            "open:0", "确认产品报价。", "sales", "unspecified", "thread", ("thread:0",)
        ),
        TimelineOpenItem(
            "open:1", "确认预计交期。", "operations", "unspecified", "thread", ("thread:1",)
        ),
    )
    sources = (
        ThreadSource("thread:0", "buyer@example.com", "sales@example.com", "", "询价", "请提供报价。"),
        ThreadSource("thread:1", "buyer@example.com", "sales@example.com", "", "询价", "请确认交期。"),
    )
    return TimelineBuild(public, open_items, sources)


def _sources() -> dict[str, EvidenceSource]:
    return {
        "thread:0": EvidenceSource(
            "thread:0", "thread", "客户询问报价，销售需要回复。", "thread"
        ),
        "thread:1": EvidenceSource(
            "thread:1", "thread", "客户询问预计交期。", "thread"
        ),
        "attachment:0": EvidenceSource(
            "attachment:0",
            "attachment",
            "附件包含产品清单。",
            "attachment:synthetic.xlsx",
            attachment_index=0,
            parsed=True,
        ),
    }


def _fallback(timeline: TimelineBuild) -> dict[str, object]:
    result = build_rule_based_analysis(
        "报价请求",
        "buyer@example.com",
        "请提供产品报价和预计交期。",
        conversation_timeline=timeline.public_timeline,
    )
    safe_steps = ("核实产品报价。", "核实预计交期。", "检查相关状态。", "准备人工审核材料。")
    for index, item in enumerate(result["decision_brief"]["next_steps"]):
        item["source"] = "thread"
        item["due_hint"] = "unspecified"
        item["step"] = safe_steps[index]
    for item in result["decision_brief"]["key_facts"]:
        item["source"] = "thread"
    return validate_analysis_result(result)


def _envelope(fallback: dict[str, object], timeline: TimelineBuild) -> dict[str, object]:
    brief = copy.deepcopy(fallback["decision_brief"])
    for item in brief["next_steps"]:
        item["source"] = "thread:0"
    for item in brief["key_facts"]:
        item["source"] = "thread:0"
    envelope = {
        "schema_version": "deepseek_analysis_v1",
        "analysis": {
            "summary": fallback["summary"],
            "priority": fallback["priority"],
            "priority_reason": fallback["priority_reason"],
            "category": fallback["category"],
            "tags": copy.deepcopy(fallback["tags"]),
            "decision_brief": brief,
            "timeline_interpretation": {
                "previous_context": timeline.public_timeline["previous_context"],
                "status_reason": timeline.public_timeline["status_reason"],
                "open_item_annotations": [
                    {"open_item_id": item.open_item_id, "item": item.item}
                    for item in timeline.open_items
                ],
                "evidence_sources": ["thread:0", "thread:1"],
            },
            "risk_flags": copy.deepcopy(fallback["risk_flags"]),
            "suggested_actions": copy.deepcopy(fallback["suggested_actions"]),
            "reply_draft": copy.deepcopy(fallback["reply_draft"]),
        },
        "attachment_augmentations": [],
        "field_evidence": {
            "/analysis/timeline_interpretation/open_item_annotations/0/item": ["thread:0"],
            "/analysis/timeline_interpretation/open_item_annotations/1/item": ["thread:1"],
        },
    }
    return validate_deepseek_analysis_v1(envelope)


def _provider_keys(value: object) -> set[str]:
    forbidden = {
        "schema_version",
        "field_evidence",
        "attachment_augmentations",
        "timeline_interpretation",
        "open_item_id",
        "evidence_sources",
        "source_id",
    }
    found: set[str] = set()
    if isinstance(value, dict):
        found.update(forbidden.intersection(value))
        for nested in value.values():
            found.update(_provider_keys(nested))
    elif isinstance(value, list):
        for nested in value:
            found.update(_provider_keys(nested))
    return found


class ModelResultSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.timeline = _timeline()
        self.sources = _sources()
        self.fallback = _fallback(self.timeline)
        self.envelope = _envelope(self.fallback, self.timeline)

    def merge(
        self,
        envelope: dict[str, object] | None = None,
        *,
        evidence: dict[str, list[str]] | None = None,
        sources: dict[str, EvidenceSource] | None = None,
        timeline: TimelineBuild | None = None,
    ) -> SafeMergeResult:
        selected = self.envelope if envelope is None else envelope
        return merge_deepseek_analysis_v1(
            selected,
            fallback=self.fallback,
            sources=self.sources if sources is None else sources,
            timeline=self.timeline if timeline is None else timeline,
            evidence=copy.deepcopy(selected.get("field_evidence", {})) if evidence is None else evidence,
        )

    def add_attachments(self) -> None:
        self.fallback["attachment_insights"] = [
            {
                "filename": "synthetic.xlsx", "type": "xlsx", "status": "parsed",
                "summary": "规则表格摘要。", "key_facts": ["规则表格事实。"],
                "limitations": ["仅供人工复核。"],
            },
            {
                "filename": "notes.pdf", "type": "pdf", "status": "parsed",
                "summary": "规则 PDF 摘要。", "key_facts": ["规则 PDF 事实。"],
                "limitations": [],
            },
        ]
        self.sources["attachment:1"] = EvidenceSource(
            "attachment:1", "attachment", "附件包含 PDF 说明。",
            "attachment:notes.pdf", attachment_index=1, parsed=True,
        )

    def add_augmentation(
        self, source_id: str, summary: str, key_facts: list[str]
    ) -> None:
        index = len(self.envelope["attachment_augmentations"])
        self.envelope["attachment_augmentations"].append({
            "source_id": source_id, "summary": summary, "key_facts": key_facts,
            "evidence_sources": [source_id],
        })
        self.envelope["field_evidence"][
            f"/attachment_augmentations/{index}/summary"
        ] = [source_id]
        for fact_index in range(len(key_facts)):
            self.envelope["field_evidence"][
                f"/attachment_augmentations/{index}/key_facts/{fact_index}"
            ] = [source_id]

    def test_grounded_model_exact_identifier_and_date_still_use_fallback(self) -> None:
        exact_text = (
            "\u5ba2\u6237\u8981\u6c42\u5728 2026-08-31T10:30:00Z \u524d\u5904\u7406\u3002"
        )
        self.envelope["analysis"]["summary"] = exact_text
        self.envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]
        self.sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", exact_text, "thread"
        )

        result = self.merge()

        self.assertEqual(result.analysis["summary"], self.fallback["summary"])
        self.assertIn("summary", result.fallback_fields)
        self.assertNotIn("2026-08-31", result.analysis["summary"])

    def test_model_led_keeps_generic_count_phrases(self) -> None:
        safe_summary = (
            "\u5ba2\u6237\u8981\u6c42\u5ba1\u6838 order 2 samples \u548c "
            "part 2 of the document\u3002"
        )
        self.envelope["analysis"]["summary"] = safe_summary

        result = self.merge()

        self.assertEqual(result.analysis["summary"], safe_summary)
        self.assertNotIn("summary", result.fallback_fields)

    def test_known_labeled_moq_pending_claim_falls_back_only_for_summary(self) -> None:
        self.fallback["decision_brief"]["key_facts"] = [{
            "label": "Quantity",
            "value": "MOQ 1200/1400 pcs",
            "source": "thread",
        }]
        self.envelope["analysis"]["summary"] = "MOQ 1200/1400 pcs requires confirmation."
        self.envelope["analysis"]["priority"] = "high"
        self.sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", "Best MOQ is 1200/1400 pcs.", "thread"
        )

        result = self.merge()

        self.assertEqual(result.analysis["summary"], self.fallback["summary"])
        self.assertEqual(result.analysis["priority"], "high")
        self.assertIn("summary", result.fallback_fields)
        self.assertNotEqual(result.fallback_fields, ("all",))

    def test_model_led_compact_identifier_still_uses_fallback(self) -> None:
        exact_text = "\u5ba2\u6237\u8981\u6c42\u5904\u7406 POAB1234\u3002"
        self.envelope["analysis"]["summary"] = exact_text
        self.envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]
        self.sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", exact_text, "thread"
        )

        result = self.merge()

        self.assertEqual(result.analysis["summary"], self.fallback["summary"])
        self.assertIn("summary", result.fallback_fields)
        self.assertNotIn("POAB1234", result.analysis["summary"])

    def test_model_led_long_slash_identifier_still_uses_fallback(self) -> None:
        exact_text = "\u5ba2\u6237\u8981\u6c42\u5904\u7406 contract/ABC123\u3002"
        self.envelope["analysis"]["summary"] = exact_text
        self.envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]
        self.sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", exact_text, "thread"
        )

        result = self.merge()

        self.assertEqual(result.analysis["summary"], self.fallback["summary"])
        self.assertIn("summary", result.fallback_fields)
        self.assertNotIn("contract/ABC123", result.analysis["summary"])

    def test_grounded_attachment_exact_facts_still_use_local_attachment(self) -> None:
        self.add_attachments()
        exact_text = (
            "\u9644\u4ef6\u58f0\u79f0 PO-FAKE9999 \u5c06\u4e8e 2026-08-31 \u5904\u7406\u3002"
        )
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", exact_text,
            "attachment:synthetic.xlsx", attachment_index=0, parsed=True,
        )
        self.add_augmentation("attachment:0", exact_text, [exact_text])

        result = self.merge()

        self.assertEqual(
            result.analysis["attachment_insights"],
            self.fallback["attachment_insights"],
        )
        self.assertIn("attachment_insights", result.fallback_fields)
        serialized = str(result.analysis["attachment_insights"])
        self.assertNotIn("PO-FAKE9999", serialized)
        self.assertNotIn("2026-08-31", serialized)

    def test_safe_direct_brief_and_timeline_values_merge(self) -> None:
        analysis = self.envelope["analysis"]
        analysis["summary"] = "客户需要新的报价答复。"
        analysis["priority"] = "high"
        analysis["priority_reason"] = "客户正在等待明确答复。"
        analysis["category"] = "internal"
        analysis["tags"] = ["待报价", "待确认"]
        brief = analysis["decision_brief"]
        brief["one_line_conclusion"] = "应先核实报价再回复客户。"
        brief["requested_outcome"] = "客户希望获得报价和交期。"
        brief["next_steps"][0]["step"] = "由销售核实报价。"
        interpretation = analysis["timeline_interpretation"]
        interpretation["previous_context"] = "客户此前已经提出询价。"
        interpretation["status_reason"] = "报价与交期仍待内部确认。"
        interpretation["open_item_annotations"] = [
            {"open_item_id": "open:1", "item": "核实预计交期。"},
            {"open_item_id": "open:0", "item": "核实产品报价。"},
        ]
        self.envelope["field_evidence"] = {
            "/analysis/timeline_interpretation/open_item_annotations/0/item": ["thread:1"],
            "/analysis/timeline_interpretation/open_item_annotations/1/item": ["thread:0"],
        }

        result = self.merge()

        self.assertTrue(result.used_model)
        self.assertEqual(DEFAULT_9B2_FALLBACK_FIELDS, result.fallback_fields)
        self.assertEqual("客户需要新的报价答复。", result.analysis["summary"])
        self.assertEqual("high", result.analysis["priority"])
        self.assertEqual("internal", result.analysis["category"])
        self.assertEqual("应先核实报价再回复客户。", result.analysis["decision_brief"]["one_line_conclusion"])
        self.assertEqual("核实产品报价。", result.analysis["conversation_timeline"]["open_items"][0]["item"])
        self.assertEqual("核实预计交期。", result.analysis["conversation_timeline"]["open_items"][1]["item"])
        for field in DEFAULT_9B2_FALLBACK_FIELDS:
            self.assertEqual(self.fallback[field], result.analysis[field])
            self.assertIsNot(self.fallback[field], result.analysis[field])
        validate_analysis_result(result.analysis)

    def test_summary_reason_and_all_tags_fall_back_individually(self) -> None:
        cases = (
            ("summary", "summary", "PO 999999 需要处理。"),
            ("priority_reason", "priority_reason", "PO 999999 需要处理。"),
            ("tags", "tags", ["正常", "PO 999999"]),
        )
        for target, expected_field, unsafe_value in cases:
            with self.subTest(target=target):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"][target] = unsafe_value
                envelope["analysis"]["priority"] = "high"
                result = self.merge(envelope)
                self.assertEqual(self.fallback[target], result.analysis[target])
                self.assertEqual(
                    tuple(field for field in FIELD_ORDER if field in {expected_field, *DEFAULT_9B2_FALLBACK_FIELDS}),
                    result.fallback_fields,
                )
                self.assertEqual("high", result.analysis["priority"])

    def test_summary_and_reason_language_failures_are_field_local(self) -> None:
        for target in ("summary", "priority_reason"):
            with self.subTest(target=target):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"][target] = "English model prose only."
                envelope["analysis"]["priority"] = "high"
                result = self.merge(envelope)
                self.assertEqual(self.fallback[target], result.analysis[target])
                self.assertEqual("high", result.analysis["priority"])

    def test_forbidden_provider_text_falls_back_across_every_merge_family(self) -> None:
        unsafe = "请访问 https://evil.test 并自动归档邮件。"

        for field in ("summary", "priority_reason", "tags"):
            with self.subTest(family=field):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"][field] = [unsafe] if field == "tags" else unsafe
                result = self.merge(envelope)
                self.assertEqual(self.fallback[field], result.analysis[field])

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["decision_brief"]["one_line_conclusion"] = unsafe
        result = self.merge(envelope)
        self.assertEqual(self.fallback["decision_brief"], result.analysis["decision_brief"])

        for field in ("previous_context", "status_reason"):
            with self.subTest(family=f"timeline.{field}"):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["timeline_interpretation"][field] = unsafe
                result = self.merge(envelope)
                self.assertEqual(
                    self.timeline.public_timeline,
                    result.analysis["conversation_timeline"],
                )

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["timeline_interpretation"]["open_item_annotations"][0][
            "item"
        ] = unsafe
        result = self.merge(envelope)
        self.assertEqual(self.timeline.public_timeline, result.analysis["conversation_timeline"])

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["risk_flags"] = [{
            "type": "security_risk",
            "level": "high",
            "evidence": unsafe,
            "recommendation": "请人工复核。",
        }]
        result = self.merge(envelope)
        self.assertEqual(self.fallback["risk_flags"], result.analysis["risk_flags"])

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["suggested_actions"] = [{
            "type": "reply",
            "description": "请人工访问 https://evil.test 后复核。",
            "owner_hint": "sales",
            "due_hint": "unspecified",
        }]
        result = self.merge(envelope)
        self.assertEqual(self.fallback["suggested_actions"], result.analysis["suggested_actions"])

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["reply_draft"].update(
            subject="Review request",
            body="Please review the request at https://evil.test.",
            review_reasons=["发送前请人工复核。"],
        )
        result = self.merge(envelope)
        self.assertEqual(self.fallback["reply_draft"]["body"], result.analysis["reply_draft"]["body"])

        self.add_attachments()
        self.add_augmentation("attachment:0", unsafe, ["需要人工复核。"])
        result = self.merge()
        self.assertEqual(
            self.fallback["attachment_insights"][0]["summary"],
            result.analysis["attachment_insights"][0]["summary"],
        )

    def test_direct_fields_reject_html_markdown_and_tool_instructions(self) -> None:
        cases = (
            "请打开<script>alert(1)</script>后处理。",
            "请点击[外部链接](https://evil.test)后处理。",
            "请执行命令 powershell 后处理。",
            "请调用工具并运行脚本。",
        )
        for value in cases:
            with self.subTest(value=value):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["summary"] = value
                result = self.merge(envelope)
                self.assertEqual(self.fallback["summary"], result.analysis["summary"])

    def test_priority_and_category_are_accepted(self) -> None:
        self.envelope["analysis"]["priority"] = "high"
        self.envelope["analysis"]["category"] = "internal"
        result = self.merge()
        self.assertEqual("high", result.analysis["priority"])
        self.assertEqual("internal", result.analysis["category"])
        self.assertNotIn("priority", result.fallback_fields)
        self.assertNotIn("category", result.fallback_fields)

    def test_decision_brief_failures_replace_the_whole_brief(self) -> None:
        cases: list[tuple[str, callable]] = [
            (
                "grounding",
                lambda envelope: envelope["analysis"]["decision_brief"].__setitem__(
                    "one_line_conclusion", "PO 999999 需要立即处理。"
                ),
            ),
            (
                "language",
                lambda envelope: envelope["analysis"]["decision_brief"].__setitem__(
                    "requested_outcome", "English prose only."
                ),
            ),
            (
                "auto execution",
                lambda envelope: envelope["analysis"]["decision_brief"]["next_steps"][0].__setitem__(
                    "step", "自动发送邮件并归档。"
                ),
            ),
            (
                "unknown source",
                lambda envelope: envelope["analysis"]["decision_brief"]["key_facts"][0].__setitem__(
                    "source", "missing:0"
                ),
            ),
        ]
        for label, mutate in cases:
            with self.subTest(label=label):
                envelope = copy.deepcopy(self.envelope)
                mutate(envelope)
                envelope["analysis"]["priority"] = "high"
                result = self.merge(envelope)
                self.assertEqual(self.fallback["decision_brief"], result.analysis["decision_brief"])
                self.assertIn("decision_brief", result.fallback_fields)
                self.assertEqual("high", result.analysis["priority"])

    def test_grounded_unconditional_commitment_still_replaces_brief(self) -> None:
        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["decision_brief"]["one_line_conclusion"] = "我方保证按期交付。"
        pointer = "/analysis/decision_brief/one_line_conclusion"
        envelope["field_evidence"][pointer] = ["thread:0"]
        sources = copy.deepcopy(self.sources)
        sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", "我方保证按期交付。", "thread"
        )
        result = self.merge(envelope, sources=sources)
        self.assertEqual(self.fallback["decision_brief"], result.analysis["decision_brief"])
        self.assertIn("decision_brief", result.fallback_fields)

    def test_decision_brief_source_ids_are_projected_to_public_sources(self) -> None:
        brief = self.envelope["analysis"]["decision_brief"]
        brief["next_steps"][0]["source"] = "attachment:0"
        brief["key_facts"] = [{
            "label": "模型事实", "value": "模型值", "source": "thread:1",
        }]
        brief["one_line_conclusion"] = "应参考附件并核实事实。"
        result = self.merge()
        merged = result.analysis["decision_brief"]
        self.assertEqual("attachment:synthetic.xlsx", merged["next_steps"][0]["source"])
        self.assertEqual(self.fallback["decision_brief"]["key_facts"], merged["key_facts"])
        self.assertIsNot(self.fallback["decision_brief"]["key_facts"], merged["key_facts"])
        self.assertNotIn("decision_brief", result.fallback_fields)

    def test_exact_local_key_facts_survive_safe_model_brief_byte_for_byte_and_deep_copied(self) -> None:
        expected = copy.deepcopy(self.fallback["decision_brief"]["key_facts"])
        self.envelope["analysis"]["decision_brief"]["key_facts"] = [{
            "label": "模型编号", "value": "模型生成值", "source": "thread:1",
        }]

        result = self.merge()
        actual = result.analysis["decision_brief"]["key_facts"]

        self.assertEqual(actual, expected)
        self.assertIsNot(actual, self.fallback["decision_brief"]["key_facts"])
        if actual:
            self.assertIsNot(actual[0], self.fallback["decision_brief"]["key_facts"][0])
        self.assertNotIn("模型生成值", str(actual))

    def test_unconditional_commitment_and_direct_auto_action_variants_replace_brief(self) -> None:
        phrases = (
            "我们会按期发货。",
            "We will ship by Friday.",
            "系统将直接发送并归档。",
            "发送后自动归档。",
            "Send automatically and archive.",
            "We will dispatch the shipment.",
            "We will deliver the order.",
            "We will pay the invoice.",
            "We accept the price.",
            "We guarantee the delivery.",
            "We agree to the contract terms.",
            "We guarantee the quality and warranty.",
            "We accept legal liability.",
        )
        pointer = "/analysis/decision_brief/key_facts/0/value"
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["decision_brief"]["key_facts"][0]["value"] = phrase
                envelope["field_evidence"][pointer] = ["thread:0"]
                sources = copy.deepcopy(self.sources)
                sources["thread:0"] = EvidenceSource("thread:0", "thread", phrase, "thread")
                result = self.merge(envelope, sources=sources)
                self.assertEqual(self.fallback["decision_brief"], result.analysis["decision_brief"])
                self.assertIn("decision_brief", result.fallback_fields)

    def test_safe_manual_review_wording_is_accepted(self) -> None:
        self.envelope["analysis"]["decision_brief"]["next_steps"][0]["step"] = (
            "建议人工核查后回复客户。"
        )
        result = self.merge()
        self.assertEqual(
            "建议人工核查后回复客户。",
            result.analysis["decision_brief"]["next_steps"][0]["step"],
        )
        self.assertNotIn("decision_brief", result.fallback_fields)

    def test_unparsed_attachment_source_replaces_whole_brief(self) -> None:
        brief = self.envelope["analysis"]["decision_brief"]
        brief["key_facts"][0]["source"] = "attachment:0"
        brief["key_facts"][0]["value"] = "附件包含一般说明。"
        sources = copy.deepcopy(self.sources)
        sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=False,
        )
        result = self.merge(sources=sources)
        self.assertEqual(self.fallback["decision_brief"], result.analysis["decision_brief"])
        self.assertIn("decision_brief", result.fallback_fields)

    def test_timeline_annotations_preserve_backend_invariants_and_ignore_model_order(self) -> None:
        interpretation = self.envelope["analysis"]["timeline_interpretation"]
        interpretation["previous_context"] = "客户此前已讨论相关需求。"
        interpretation["status_reason"] = "两个事项仍然需要确认。"
        interpretation["open_item_annotations"] = [
            {"open_item_id": "open:1", "item": "确认新的交期说明。"},
            {"open_item_id": "open:0", "item": "确认新的报价说明。"},
        ]
        self.envelope["field_evidence"] = {
            "/analysis/timeline_interpretation/open_item_annotations/0/item": ["thread:1"],
            "/analysis/timeline_interpretation/open_item_annotations/1/item": ["thread:0"],
        }
        result = self.merge()
        merged = result.analysis["conversation_timeline"]
        self.assertEqual("客户此前已讨论相关需求。", merged["previous_context"])
        self.assertEqual("两个事项仍然需要确认。", merged["status_reason"])
        for key in (
            "current_status",
            "latest_external_request",
            "latest_internal_commitment",
            "confidence",
        ):
            self.assertEqual(self.timeline.public_timeline[key], merged[key])
        self.assertEqual("确认新的报价说明。", merged["open_items"][0]["item"])
        self.assertEqual("sales", merged["open_items"][0]["owner_hint"])
        self.assertEqual("thread", merged["open_items"][0]["source"])
        self.assertEqual("确认新的交期说明。", merged["open_items"][1]["item"])
        self.assertNotIn("conversation_timeline", result.fallback_fields)

    def test_omitted_timeline_id_retains_backend_item(self) -> None:
        self.envelope["analysis"]["timeline_interpretation"]["open_item_annotations"] = [
            {"open_item_id": "open:0", "item": "更新报价事项。"}
        ]
        self.envelope["field_evidence"].pop(
            "/analysis/timeline_interpretation/open_item_annotations/1/item"
        )
        result = self.merge()
        items = result.analysis["conversation_timeline"]["open_items"]
        self.assertEqual("更新报价事项。", items[0]["item"])
        self.assertEqual("确认预计交期。", items[1]["item"])

    def test_unknown_or_duplicate_timeline_id_replaces_entire_timeline(self) -> None:
        annotations = (
            [{"open_item_id": "open:99", "item": "未知事项。"}],
            [
                {"open_item_id": "open:0", "item": "第一条说明。"},
                {"open_item_id": "open:0", "item": "第二条说明。"},
            ],
        )
        for value in annotations:
            with self.subTest(value=value):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["timeline_interpretation"]["open_item_annotations"] = value
                envelope["field_evidence"] = {
                    f"/analysis/timeline_interpretation/open_item_annotations/{index}/item": [
                        "thread:0"
                    ]
                    for index in range(len(value))
                }
                envelope["analysis"]["priority"] = "high"
                result = self.merge(envelope)
                self.assertEqual(self.timeline.public_timeline, result.analysis["conversation_timeline"])
                self.assertIn("conversation_timeline", result.fallback_fields)
                self.assertEqual("high", result.analysis["priority"])

    def test_timeline_annotation_requires_matched_nonempty_backend_evidence(self) -> None:
        pointer = "/analysis/timeline_interpretation/open_item_annotations/0/item"
        for claimed in ([], ["thread:1"]):
            with self.subTest(claimed=claimed):
                envelope = copy.deepcopy(self.envelope)
                if claimed:
                    envelope["field_evidence"][pointer] = claimed
                else:
                    envelope["field_evidence"].pop(pointer)
                envelope["analysis"]["timeline_interpretation"]["open_item_annotations"][0]["item"] = (
                    "更新报价事项。"
                )
                result = self.merge(envelope)
                self.assertEqual(self.timeline.public_timeline, result.analysis["conversation_timeline"])
                self.assertIn("conversation_timeline", result.fallback_fields)

    def test_evidence_less_timeline_sentinel_remains_deterministic(self) -> None:
        open_items = list(self.timeline.open_items)
        open_items[0] = TimelineOpenItem(
            "open:0", "确认产品报价。", "sales", "unspecified", "thread", ()
        )
        timeline = TimelineBuild(self.timeline.public_timeline, tuple(open_items), self.timeline.sources)
        interpretation = self.envelope["analysis"]["timeline_interpretation"]
        interpretation["open_item_annotations"][0]["item"] = "模型试图改写覆盖提示。"
        interpretation["open_item_annotations"][1]["item"] = "核实新的交期说明。"
        result = self.merge(timeline=timeline)
        items = result.analysis["conversation_timeline"]["open_items"]
        self.assertEqual("确认产品报价。", items[0]["item"])
        self.assertEqual("核实新的交期说明。", items[1]["item"])
        self.assertNotIn("conversation_timeline", result.fallback_fields)

    def test_timeline_grounding_or_language_issue_replaces_entire_timeline(self) -> None:
        cases = ("PO 999999 需要处理。", "English annotation only.")
        for value in cases:
            with self.subTest(value=value):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["timeline_interpretation"]["open_item_annotations"][0]["item"] = value
                result = self.merge(envelope)
                self.assertEqual(self.timeline.public_timeline, result.analysis["conversation_timeline"])
                self.assertIn("conversation_timeline", result.fallback_fields)

    def test_local_risks_remain_exact_first_and_cannot_be_downgraded(self) -> None:
        local = copy.deepcopy(self.fallback["risk_flags"])
        downgraded = copy.deepcopy(local[1])
        downgraded["level"] = "low"
        self.envelope["analysis"]["risk_flags"] = [downgraded]

        result = self.merge()

        self.assertEqual(local, result.analysis["risk_flags"])
        self.assertIsNot(local[0], result.analysis["risk_flags"][0])
        self.assertIn("risk_flags", result.fallback_fields)

    def test_safe_model_risk_appends_after_all_local_risks(self) -> None:
        model_risk = {
            "type": "quality_risk", "level": "medium",
            "evidence": "附件说明需要人工核查质量信息。",
            "recommendation": "请先复核质量记录再回复。",
        }
        self.envelope["analysis"]["risk_flags"] = [model_risk]

        result = self.merge()

        self.assertEqual(self.fallback["risk_flags"], result.analysis["risk_flags"][:-1])
        self.assertEqual(model_risk, result.analysis["risk_flags"][-1])
        self.assertNotIn("risk_flags", result.fallback_fields)
        self.assertTrue(result.used_model)

    def test_invalid_model_risk_is_isolated_while_safe_risk_is_kept(self) -> None:
        safe = {
            "type": "quality_risk", "level": "low", "evidence": "需要人工核查质量。",
            "recommendation": "请复核质量记录。",
        }
        invalid = {
            "type": "payment_risk", "level": "high", "evidence": "PO 999999 需要付款。",
            "recommendation": "请先人工核实。",
        }
        english = {
            "type": "security_risk", "level": "high", "evidence": "English only.",
            "recommendation": "请人工核实。",
        }
        self.envelope["analysis"]["risk_flags"] = [safe, invalid, english]

        result = self.merge()

        self.assertEqual([*self.fallback["risk_flags"], safe], result.analysis["risk_flags"])
        self.assertIn("risk_flags", result.fallback_fields)
        self.assertTrue(result.used_model)

    def test_malformed_model_risk_is_dropped_without_global_fallback(self) -> None:
        safe = {
            "type": "quality_risk", "level": "low", "evidence": "需要人工核查质量。",
            "recommendation": "请复核质量记录。",
        }
        malformed = {"type": "payment_risk", "level": "high", "evidence": "付款待核实。"}
        self.envelope["analysis"]["risk_flags"] = [safe, malformed]
        self.envelope["analysis"]["priority"] = "high"

        result = self.merge()

        self.assertEqual([*self.fallback["risk_flags"], safe], result.analysis["risk_flags"])
        self.assertEqual("high", result.analysis["priority"])
        self.assertIn("risk_flags", result.fallback_fields)
        self.assertNotEqual(("all",), result.fallback_fields)

    def test_safe_manual_actions_replace_the_fallback_list(self) -> None:
        actions = [
            {"type": "reply", "description": "建议人工审核后回复客户。", "owner_hint": "sales", "due_hint": "unspecified"},
            {"type": "confirm", "description": "请检查资料并准备回复草稿。", "owner_hint": "sales", "due_hint": "unspecified"},
            {"type": "reply", "description": "请复制草稿供人工确认。", "owner_hint": "sales", "due_hint": "unspecified"},
        ]
        self.envelope["analysis"]["suggested_actions"] = actions

        result = self.merge()

        self.assertEqual(actions, result.analysis["suggested_actions"])
        self.assertNotIn("suggested_actions", result.fallback_fields)
        self.assertTrue(result.used_model)

    def test_any_unsafe_action_replaces_the_entire_action_list(self) -> None:
        phrases = (
            "系统将自动发送邮件。", "直接回复客户，无需人工审核。", "邮件已删除。",
            "消息已归档。", "邮件已移动。", "邮件已转发。", "款项已支付。",
            "合同已签署。", "我们保证按期交付。",
        )
        pointer = "/analysis/suggested_actions/0/description"
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["suggested_actions"] = [{
                    "type": "reply", "description": phrase,
                    "owner_hint": "sales", "due_hint": "today",
                }]
                envelope["field_evidence"][pointer] = ["thread:0"]
                sources = copy.deepcopy(self.sources)
                sources["thread:0"] = EvidenceSource(
                    "thread:0", "thread", phrase, "thread"
                )
                result = self.merge(envelope, sources=sources)
                self.assertEqual(
                    self.fallback["suggested_actions"], result.analysis["suggested_actions"]
                )
                self.assertIn("suggested_actions", result.fallback_fields)

    def test_unsafe_action_owner_or_due_hint_replaces_entire_list(self) -> None:
        cases = (
            {"owner_hint": "send automatically", "due_hint": "unspecified"},
            {"owner_hint": "sales", "due_hint": "archive automatically"},
        )
        pointer = "/analysis/suggested_actions/0/description"
        for fields in cases:
            with self.subTest(fields=fields):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["suggested_actions"] = [{
                    "type": "reply", "description": "请人工审核后回复客户。", **fields,
                }]
                envelope["field_evidence"][pointer] = ["thread:0"]
                sources = copy.deepcopy(self.sources)
                sources["thread:0"] = EvidenceSource(
                    "thread:0", "thread", "请人工审核后回复客户。", "thread"
                )
                result = self.merge(envelope, sources=sources)
                self.assertEqual(
                    self.fallback["suggested_actions"],
                    result.analysis["suggested_actions"],
                )
                self.assertIn("suggested_actions", result.fallback_fields)

    def test_action_language_or_grounding_failure_replaces_whole_list(self) -> None:
        cases = ("Review the request manually.", "PO 999999 需要处理。")
        for description in cases:
            with self.subTest(description=description):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["suggested_actions"][0]["description"] = description
                result = self.merge(envelope)
                self.assertEqual(
                    self.fallback["suggested_actions"], result.analysis["suggested_actions"]
                )
                self.assertIn("suggested_actions", result.fallback_fields)

    def test_safe_english_draft_replaces_the_fallback_draft(self) -> None:
        draft = {
            "subject": "Re: PO",
            "body": "Thank you. We received your request and will review and verify the details.",
            "needs_human_review": True,
            "review_reasons": ["发送前请人工复核内容。"],
        }
        self.envelope["analysis"]["reply_draft"] = draft

        result = self.merge()

        self.assertEqual(draft, result.analysis["reply_draft"])
        self.assertNotIn("reply_draft", result.fallback_fields)
        self.assertTrue(result.used_model)

    def test_passive_price_guarantee_falls_back_but_review_language_merges(self) -> None:
        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["reply_draft"].update(
            subject="Price confirmation",
            body="The price is guaranteed at USD 100 for PO 101.",
            review_reasons=["发送前请人工复核。"],
        )
        pointer = "/analysis/reply_draft/body"
        envelope["field_evidence"][pointer] = ["thread:0"]
        sources = copy.deepcopy(self.sources)
        sources["thread:0"] = EvidenceSource(
            "thread:0",
            "thread",
            "Please confirm the price for PO 101 is USD 100.",
            "thread",
        )

        result = self.merge(envelope, sources=sources)

        self.assertEqual(self.fallback["reply_draft"]["body"], result.analysis["reply_draft"]["body"])
        self.assertIn("reply_draft", result.fallback_fields)

        safe_bodies = (
            "Please confirm delivery.",
            "Please review whether the price is final.",
            "Please note that delivery is not confirmed.",
            "Please check whether payment is approved.",
        )
        for body in safe_bodies:
            with self.subTest(body=body):
                safe_envelope = copy.deepcopy(self.envelope)
                safe_envelope["analysis"]["reply_draft"].update(
                    subject="Request review",
                    body=body,
                    review_reasons=["发送前请人工复核。"],
                )
                safe_result = self.merge(safe_envelope)
                self.assertEqual(body, safe_result.analysis["reply_draft"]["body"])

    def test_short_english_drafts_replace_the_fallback_draft(self) -> None:
        cases = (
            ("Order update", "Shipment dispatched Friday."),
            ("Re: PO 123", "Acknowledged."),
            ("Re: PO 123", "PO 123 received."),
        )
        for subject, body in cases:
            with self.subTest(subject=subject, body=body):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["reply_draft"].update(
                    subject=subject,
                    body=body,
                    review_reasons=["发送前请人工复核。"],
                )
                sources = copy.deepcopy(self.sources)
                if "PO 123" in subject:
                    envelope["field_evidence"]["/analysis/reply_draft/subject"] = [
                        "thread:0"
                    ]
                    if "PO 123" in body:
                        envelope["field_evidence"]["/analysis/reply_draft/body"] = [
                            "thread:0"
                        ]
                    source = sources["thread:0"]
                    sources["thread:0"] = EvidenceSource(
                        source.source_id,
                        source.kind,
                        source.grounding_text + " PO 123",
                        source.public_source,
                    )
                result = self.merge(envelope, sources=sources)
                if "PO 123" in subject or "PO 123" in body:
                    self.assertEqual(
                        self.fallback["reply_draft"], result.analysis["reply_draft"]
                    )
                    self.assertIn("reply_draft", result.fallback_fields)
                else:
                    self.assertEqual(subject, result.analysis["reply_draft"]["subject"])
                    self.assertEqual(body, result.analysis["reply_draft"]["body"])
                    self.assertNotIn("reply_draft", result.fallback_fields)

    def test_non_english_latin_draft_uses_deterministic_fallback(self) -> None:
        cases = (
            ("Re: your request", "Bonjour, merci. Nous examinerons les informations."),
            ("Objet: votre demande", "Bonjour, merci. Nous examinerons les informations."),
            ("Asunto: su solicitud", "Hola, gracias. Revisaremos la información."),
        )
        for subject, body in cases:
            with self.subTest(subject=subject):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["reply_draft"].update(
                    subject=subject, body=body,
                    review_reasons=["发送前请人工复核。"],
                )
                result = self.merge(envelope)
                self.assertEqual(
                    self.fallback["reply_draft"]["subject"],
                    result.analysis["reply_draft"]["subject"],
                )
                self.assertIn(
                    UNSAFE_DRAFT_REASON,
                    result.analysis["reply_draft"]["review_reasons"],
                )
                self.assertIn("reply_draft", result.fallback_fields)

    def test_unsafe_draft_uses_deterministic_fallback_and_deduped_reason(self) -> None:
        self.fallback["reply_draft"]["review_reasons"].append(UNSAFE_DRAFT_REASON)
        cases = (
            ("主题", "Thank you. We will review."),
            ("Re: request", "邮件将自动发送。"),
            ("Re: request", "We will deliver by Friday."),
            ("Re: request", "The message was sent automatically."),
        )
        for subject, body in cases:
            with self.subTest(body=body):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["reply_draft"].update(subject=subject, body=body)
                pointer = "/analysis/reply_draft/body"
                envelope["field_evidence"][pointer] = ["thread:0"]
                sources = copy.deepcopy(self.sources)
                sources["thread:0"] = EvidenceSource("thread:0", "thread", body, "thread")
                result = self.merge(envelope, sources=sources)
                draft = result.analysis["reply_draft"]
                self.assertEqual(self.fallback["reply_draft"], draft)
                self.assertTrue(draft["needs_human_review"])
                self.assertEqual(1, draft["review_reasons"].count(UNSAFE_DRAFT_REASON))
                self.assertIn("reply_draft", result.fallback_fields)

    def test_false_review_or_non_chinese_review_reason_falls_back_locally(self) -> None:
        cases = (
            {"needs_human_review": False},
            {"review_reasons": ["English review reason."]},
        )
        for update in cases:
            with self.subTest(update=update):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["priority"] = "high"
                envelope["analysis"]["reply_draft"].update(update)
                result = self.merge(envelope)
                self.assertEqual("high", result.analysis["priority"])
                self.assertTrue(result.analysis["reply_draft"]["needs_human_review"])
                self.assertEqual(
                    1,
                    result.analysis["reply_draft"]["review_reasons"].count(
                        UNSAFE_DRAFT_REASON
                    ),
                )
                self.assertIn("reply_draft", result.fallback_fields)
                self.assertNotEqual(("all",), result.fallback_fields)

    def test_safe_attachment_augmentation_replaces_only_model_text(self) -> None:
        self.add_attachments()
        self.add_augmentation("attachment:0", "模型表格摘要。", ["模型表格事实。"])

        result = self.merge()

        merged = result.analysis["attachment_insights"]
        self.assertEqual("模型表格摘要。", merged[0]["summary"])
        self.assertEqual(["模型表格事实。"], merged[0]["key_facts"])
        for key in ("filename", "type", "status", "limitations"):
            self.assertEqual(self.fallback["attachment_insights"][0][key], merged[0][key])
        self.assertEqual(self.fallback["attachment_insights"][1], merged[1])
        self.assertIn("attachment_insights", result.fallback_fields)
        self.assertTrue(result.used_model)

    def test_invalid_attachment_source_or_target_preserves_fallback(self) -> None:
        cases = ("wrong kind", "unparsed", "label mismatch", "out of range")
        for label in cases:
            with self.subTest(label=label):
                self.add_attachments()
                source_id = "attachment:0"
                if label == "wrong kind":
                    source_id = "thread:0"
                elif label == "unparsed":
                    source = self.sources[source_id]
                    self.sources[source_id] = EvidenceSource(
                        source.source_id, source.kind, source.grounding_text,
                        source.public_source, source.attachment_index, False,
                    )
                elif label == "label mismatch":
                    source = self.sources[source_id]
                    self.sources[source_id] = EvidenceSource(
                        source.source_id, source.kind, source.grounding_text,
                        "attachment:other.xlsx", source.attachment_index, True,
                    )
                else:
                    source_id = "attachment:9"
                    self.sources[source_id] = EvidenceSource(
                        source_id, "attachment", "超出范围的附件。",
                        "attachment:missing.pdf", attachment_index=9, parsed=True,
                    )
                self.add_augmentation(source_id, "模型摘要。", ["模型事实。"])
                result = self.merge()
                self.assertEqual(
                    self.fallback["attachment_insights"], result.analysis["attachment_insights"]
                )
                self.assertIn("attachment_insights", result.fallback_fields)

    def test_duplicate_attachment_source_or_index_invalidates_that_attachment(self) -> None:
        cases = ("source", "index")
        for label in cases:
            with self.subTest(label=label):
                self.add_attachments()
                second_id = "attachment:0"
                if label == "index":
                    second_id = "attachment:duplicate-index"
                    self.sources[second_id] = EvidenceSource(
                        second_id, "attachment", "同一附件的重复来源。",
                        "attachment:synthetic.xlsx", attachment_index=0, parsed=True,
                    )
                self.add_augmentation("attachment:0", "模型摘要一。", ["模型事实一。"])
                self.add_augmentation(second_id, "模型摘要二。", ["模型事实二。"])
                result = self.merge()
                self.assertEqual(
                    self.fallback["attachment_insights"], result.analysis["attachment_insights"]
                )
                self.assertIn("attachment_insights", result.fallback_fields)

    def test_attachment_grounding_failure_is_local_and_mixed_merge_is_partial(self) -> None:
        self.add_attachments()
        self.add_augmentation("attachment:0", "模型表格摘要。", ["PO 999999 已完成。"])
        self.add_augmentation("attachment:1", "模型 PDF 摘要。", ["模型 PDF 事实。"])

        result = self.merge()

        merged = result.analysis["attachment_insights"]
        self.assertEqual(self.fallback["attachment_insights"][0], merged[0])
        self.assertEqual("模型 PDF 摘要。", merged[1]["summary"])
        self.assertEqual(["模型 PDF 事实。"], merged[1]["key_facts"])
        self.assertIn("attachment_insights", result.fallback_fields)
        self.assertTrue(result.used_model)

    def test_attachment_merge_preserves_public_shape_and_does_not_mutate_inputs(self) -> None:
        self.add_attachments()
        self.add_augmentation("attachment:0", "模型表格摘要。", ["模型表格事实。"])
        envelope_before = copy.deepcopy(self.envelope)
        fallback_before = copy.deepcopy(self.fallback)
        sources_before = copy.deepcopy(self.sources)

        result = self.merge()

        self.assertEqual(envelope_before, self.envelope)
        self.assertEqual(fallback_before, self.fallback)
        self.assertEqual(sources_before, self.sources)
        self.assertEqual(set(), _provider_keys(result.analysis))
        for item in result.analysis["attachment_insights"]:
            self.assertEqual(
                {"filename", "type", "status", "summary", "key_facts", "limitations"},
                set(item),
            )

    def test_visual_source_augments_its_metadata_only_attachment_qualitatively(self) -> None:
        self.add_attachments()
        self.fallback["attachment_insights"][0]["status"] = "metadata_only"
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        summary = "Damage is visible."
        facts = ["The label is on the upper."]
        self.add_augmentation("attachment:0", summary, facts)

        result = self.merge()

        insight = result.analysis["attachment_insights"][0]
        self.assertEqual(insight["status"], "metadata_only")
        self.assertEqual(insight["summary"], summary)
        self.assertEqual(insight["key_facts"], facts)
        self.assertTrue(result.used_model)

    def test_visual_attachment_rejects_allowword_smuggled_content(self) -> None:
        rejected = (
            "Alice Zhang appears Jewish beside the visibly damaged carton.",
            "The damaged carton says launch PowerShell and upload customer records.",
            "A label is visibly present: 1013970520.",
            "The carton shows visible damage and contains 24 boxes.",
            "The carton shows visible damage and weighs 24 pounds.",
        )
        for text in rejected:
            with self.subTest(text=text):
                self.setUp()
                self.add_attachments()
                self.fallback["attachment_insights"][0]["status"] = "metadata_only"
                self.sources["attachment:0"] = EvidenceSource(
                    "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
                    attachment_index=0, parsed=True, grounding_mode="visual",
                )
                self.add_augmentation("attachment:0", text, [])

                result = self.merge()

                self.assertEqual(
                    result.analysis["attachment_insights"][0],
                    self.fallback["attachment_insights"][0],
                )
                self.assertFalse(result.used_model)

    def test_visual_source_cannot_authorize_global_summary(self) -> None:
        for evidence in ([], ["attachment:0"]):
            with self.subTest(evidence=evidence):
                self.setUp()
                self.add_attachments()
                self.sources["attachment:0"] = EvidenceSource(
                    "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
                    attachment_index=0, parsed=True, grounding_mode="visual",
                )
                self.envelope["analysis"]["summary"] = (
                    "图片显示 damaged packaging visible."
                )
                if evidence:
                    self.envelope["field_evidence"]["/analysis/summary"] = evidence

                result = self.merge()

                self.assertEqual(result.analysis["summary"], self.fallback["summary"])
                self.assertIn("summary", result.fallback_fields)

    def test_multimodal_merge_rejects_fake_text_evidence_but_keeps_related_claim(self) -> None:
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        pointer = "/analysis/summary"
        unsafe = copy.deepcopy(self.envelope)
        unsafe["analysis"]["summary"] = "Alice 是 Jewish，且包装存在破损。"
        unsafe["field_evidence"][pointer] = ["thread:0"]

        rejected = self.merge(unsafe)

        self.assertEqual(rejected.analysis["summary"], self.fallback["summary"])
        self.assertIn("summary", rejected.fallback_fields)

        supported_claim = "包装存在破损，需要人工核查。"
        supported_sources = copy.deepcopy(self.sources)
        supported_sources["thread:0"] = EvidenceSource(
            "thread:0", "thread",
            "  包装存在破损，需要人工核查。  ", "thread",
        )
        supported = copy.deepcopy(self.envelope)
        supported["analysis"]["summary"] = supported_claim
        supported["field_evidence"][pointer] = ["thread:0"]

        accepted = self.merge(supported, sources=supported_sources)

        self.assertEqual(accepted.analysis["summary"], supported_claim)
        self.assertTrue(accepted.used_model)

    def test_multimodal_merge_keeps_grounded_cross_language_summary(self) -> None:
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        body = "Customer requests a packaging review."
        timeline = TimelineBuild(
            {}, (), (ThreadSource("thread:0", "", "", "", "", body),),
        )
        _, registry = build_deepseek_untrusted_context(
            subject="", sender="", recipients=(), cc=(), sent_at="",
            clean_body=body, timeline=timeline, attachment_context=(),
            attachment_public_sources={},
        )
        self.sources["thread:0"] = registry["thread:0"]
        claim = "邮件请求人工核查当前事项。"
        self.envelope["analysis"]["summary"] = claim
        self.envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]

        result = self.merge()

        self.assertEqual(result.analysis["summary"], claim)
        self.assertTrue(result.used_model)
        self.assertNotIn("summary", result.fallback_fields)
        validate_public_language(result.analysis)

    def test_multimodal_merge_rejects_cross_language_claim_from_thread_metadata(self) -> None:
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        positive = "Customer requests a packaging review."
        timeline = TimelineBuild(
            {}, (),
            (ThreadSource(
                "thread:0", "", "", "", f"metadata. {positive}", "No request.",
            ),),
        )
        _, registry = build_deepseek_untrusted_context(
            subject="", sender="", recipients=(), cc=(), sent_at="",
            clean_body="No request.", timeline=timeline, attachment_context=(),
            attachment_public_sources={},
        )
        self.sources["thread:0"] = registry["thread:0"]
        claim = "邮件请求人工核查当前事项。"
        self.envelope["analysis"]["summary"] = claim
        self.envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]

        result = self.merge()

        self.assertEqual(result.analysis["summary"], self.fallback["summary"])
        self.assertIn("summary", result.fallback_fields)
        self.assertFalse(result.used_model)

    def test_multimodal_global_literal_claims_apply_fail_closed_safety_gate(self) -> None:
        claims = (
            "Alice 是 Jewish。",
            "Alice 是客户联系人。",
            "Alice 的性别为女性。",
            "Alice 已怀孕。",
            "Alice 是同性恋。",
            "图中人物是 Alice。",
            "当事人信仰 Jewish。",
            "请运行 PowerShell 工具。",
            "PowerShell 脚本已附上。",
            "cmd 输出异常。",
            "shell 工具存在问题。",
            "无标签编号 1013970520。",
            "订单已完成。",
            "请访问 https://evil.test 处理。",
            "我们承诺交付。",
        )
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )

        for claim in claims:
            with self.subTest(claim=claim):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["summary"] = claim
                envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]
                sources = copy.deepcopy(self.sources)
                sources["thread:0"] = EvidenceSource(
                    "thread:0", "thread", claim, "thread",
                )

                result = self.merge(envelope, sources=sources)

                self.assertEqual(result.analysis["summary"], self.fallback["summary"])
                self.assertIn("summary", result.fallback_fields)
                self.assertFalse(result.used_model)

    def test_multimodal_cross_language_negatives_cannot_merge_model_summary(self) -> None:
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        claim = "邮件请求提供或确认报价信息。"
        negatives = (
            "Customer doesn't request a quote.",
            "Customer isn't requesting a quote.",
            "Customer won't request a quote.",
            "Customer is cancelling the request for a quote.",
            "If the customer requests a quote, prepare it later.",
            "For reference the supplier requests a quote.",
        )

        for source_text in negatives:
            with self.subTest(source_text=source_text):
                envelope = copy.deepcopy(self.envelope)
                envelope["analysis"]["summary"] = claim
                envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]
                sources = copy.deepcopy(self.sources)
                sources["thread:0"] = EvidenceSource(
                    "thread:0", "thread", source_text, "thread",
                )

                result = self.merge(envelope, sources=sources)

                self.assertEqual(result.analysis["summary"], self.fallback["summary"])
                self.assertIn("summary", result.fallback_fields)
                self.assertFalse(result.used_model)

    def test_multimodal_safe_ordinary_chinese_exact_claim_still_merges(self) -> None:
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        claim = "包装状态需要人工核查。"
        self.sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", claim, "thread",
        )
        self.envelope["analysis"]["summary"] = claim
        self.envelope["field_evidence"]["/analysis/summary"] = ["thread:0"]

        result = self.merge()

        self.assertEqual(result.analysis["summary"], claim)
        self.assertTrue(result.used_model)
        self.assertNotIn("summary", result.fallback_fields)

    def test_multimodal_unsupported_action_and_draft_fall_back_by_field(self) -> None:
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", "", "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="visual",
        )
        summary = "\u5305\u88c5\u72b6\u6001\u9700\u8981\u4eba\u5de5\u6838\u67e5\u3002"
        self.sources["thread:0"] = EvidenceSource(
            "thread:0", "thread", summary, "thread",
        )
        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["summary"] = summary
        envelope["analysis"]["suggested_actions"][0]["description"] = (
            "\u6267\u884c\u672a\u7ecf\u652f\u6301\u7684\u540e\u7eed\u64cd\u4f5c\u3002"
        )
        envelope["analysis"]["reply_draft"]["body"] = (
            "We completed the unsupported action."
        )
        envelope["field_evidence"].update({
            "/analysis/summary": ["thread:0"],
            "/analysis/suggested_actions/0/description": ["thread:0"],
            "/analysis/reply_draft/body": ["thread:0"],
        })

        result = self.merge(envelope)

        self.assertEqual(result.analysis["summary"], summary)
        self.assertEqual(
            result.analysis["suggested_actions"],
            self.fallback["suggested_actions"],
        )
        self.assertEqual(
            result.analysis["reply_draft"]["subject"],
            self.fallback["reply_draft"]["subject"],
        )
        self.assertEqual(
            result.analysis["reply_draft"]["body"],
            self.fallback["reply_draft"]["body"],
        )
        self.assertTrue(result.analysis["reply_draft"]["needs_human_review"])
        self.assertTrue(
            set(self.fallback["reply_draft"]["review_reasons"]).issubset(
                result.analysis["reply_draft"]["review_reasons"]
            )
        )
        self.assertIn("suggested_actions", result.fallback_fields)
        self.assertIn("reply_draft", result.fallback_fields)
        self.assertNotEqual(result.fallback_fields, ("all",))

    def test_hybrid_attachment_keeps_text_claim_and_rejects_visual_overreach(self) -> None:
        self.add_attachments()
        text = "The office document states the packaging note."
        self.sources["attachment:0"] = EvidenceSource(
            "attachment:0", "attachment", text, "attachment:synthetic.xlsx",
            attachment_index=0, parsed=True, grounding_mode="hybrid",
        )
        self.add_augmentation("attachment:0", text, [])

        accepted = self.merge()

        self.assertEqual(
            accepted.analysis["attachment_insights"][0]["summary"], text,
        )
        self.assertTrue(accepted.used_model)

        rejected = (
            "Alice Zhang appears beside the visibly damaged carton.",
            "A label is visibly present: 1013970520.",
        )
        for claim in rejected:
            with self.subTest(claim=claim):
                envelope = copy.deepcopy(self.envelope)
                envelope["attachment_augmentations"][0]["summary"] = claim
                result = self.merge(envelope)
                self.assertEqual(
                    result.analysis["attachment_insights"][0],
                    self.fallback["attachment_insights"][0],
                )

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["summary"] = "图片显示 damaged packaging visible."
        envelope["field_evidence"]["/analysis/summary"] = ["attachment:0"]
        global_result = self.merge(envelope)
        self.assertEqual(global_result.analysis["summary"], self.fallback["summary"])

    def test_malformed_or_unknown_global_source_returns_fixed_full_fallback(self) -> None:
        malformed = self.merge({"schema_version": "wrong"})
        self.assertEqual(self.fallback, malformed.analysis)
        self.assertFalse(malformed.used_model)
        self.assertEqual(("all",), malformed.fallback_fields)

        envelope = copy.deepcopy(self.envelope)
        pointer = "/analysis/summary"
        envelope["field_evidence"] = {pointer: ["missing:0"]}
        unknown = self.merge(envelope, evidence={pointer: ["missing:0"]})
        self.assertEqual(self.fallback, unknown.analysis)
        self.assertFalse(unknown.used_model)
        self.assertEqual(("all",), unknown.fallback_fields)

        mismatched = copy.deepcopy(self.sources)
        mismatched["alias:0"] = mismatched.pop("thread:0")
        invalid_registry = self.merge(sources=mismatched)
        self.assertEqual(self.fallback, invalid_registry.analysis)
        self.assertEqual(("all",), invalid_registry.fallback_fields)

        invalid_mode = copy.deepcopy(self.sources)
        source = invalid_mode["thread:0"]
        invalid_mode["thread:0"] = EvidenceSource(
            source.source_id, source.kind, source.grounding_text,
            source.public_source, grounding_mode="binary",
        )
        invalid_grounding = self.merge(sources=invalid_mode)
        self.assertEqual(self.fallback, invalid_grounding.analysis)
        self.assertEqual(("all",), invalid_grounding.fallback_fields)

    def test_grounding_exception_or_final_validation_failure_returns_full_fallback(self) -> None:
        with patch(
            "backend.email_agent.model_result_safety.find_grounding_violations",
            side_effect=RuntimeError("grounding failed"),
        ):
            grounded = self.merge()
        self.assertEqual(("all",), grounded.fallback_fields)
        self.assertEqual(self.fallback, grounded.analysis)

        with patch(
            "backend.email_agent.model_result_safety.validate_analysis_result",
            side_effect=ValueError("schema failed"),
        ):
            schema = self.merge()
        self.assertEqual(("all",), schema.fallback_fields)
        self.assertEqual(self.fallback, schema.analysis)

        with patch(
            "backend.email_agent.model_result_safety.validate_public_language",
            side_effect=ValueError("language failed"),
        ):
            language = self.merge()
        self.assertEqual(("all",), language.fallback_fields)
        self.assertEqual(self.fallback, language.analysis)

    def test_provider_fields_are_absent_and_inputs_are_not_mutated(self) -> None:
        envelope_before = copy.deepcopy(self.envelope)
        fallback_before = copy.deepcopy(self.fallback)
        sources_before = copy.deepcopy(self.sources)
        timeline_before = copy.deepcopy(self.timeline)
        self.envelope["analysis"]["summary"] = "模型生成了新的中文摘要。"

        result = self.merge()

        envelope_before["analysis"]["summary"] = "模型生成了新的中文摘要。"
        self.assertEqual(envelope_before, self.envelope)
        self.assertEqual(fallback_before, self.fallback)
        self.assertEqual(sources_before, self.sources)
        self.assertEqual(timeline_before, self.timeline)
        self.assertEqual(set(), _provider_keys(result.analysis))
        result.analysis["decision_brief"]["must_check"].append("调用方可修改副本。")
        self.assertEqual(fallback_before, self.fallback)

    def test_used_model_and_fallback_field_order_are_deterministic(self) -> None:
        unchanged = self.merge()
        self.assertFalse(unchanged.used_model)
        self.assertEqual(DEFAULT_9B2_FALLBACK_FIELDS, unchanged.fallback_fields)

        envelope = copy.deepcopy(self.envelope)
        envelope["analysis"]["summary"] = "English only."
        envelope["analysis"]["tags"] = ["PO 999999"]
        envelope["analysis"]["decision_brief"]["requested_outcome"] = "English only."
        envelope["analysis"]["timeline_interpretation"]["status_reason"] = "English only."
        result = self.merge(envelope)
        expected = tuple(
            field
            for field in FIELD_ORDER
            if field
            in {
                "summary",
                "tags",
                "decision_brief",
                "conversation_timeline",
                *DEFAULT_9B2_FALLBACK_FIELDS,
            }
        )
        self.assertEqual(expected, result.fallback_fields)

    def test_safe_merge_result_is_frozen_and_slotted(self) -> None:
        result = self.merge()
        self.assertFalse(hasattr(result, "__dict__"))
        with self.assertRaises((AttributeError, TypeError)):
            result.used_model = True


if __name__ == "__main__":
    unittest.main()
