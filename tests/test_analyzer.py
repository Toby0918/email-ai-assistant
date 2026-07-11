"""Business tests for current email analysis orchestration."""

from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from backend.email_agent.analyzer import AnalysisError, analyze_current_email
from backend.email_agent.attachment_storage import StoredAttachment
from backend.email_agent.llm_client import LlmClientError


def _contains_chinese(text: str) -> bool:
    return any("\u4e00" <= char <= "\u9fff" for char in text)


class AnalyzerTests(unittest.TestCase):
    def test_prompt_includes_attachment_metadata_as_untrusted_context(self) -> None:
        captured: dict[str, str] = {}

        def fake_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return json.dumps({
                "summary": "该邮件是新品开发和成本优化请求，需要结合附件项目范围评估可行性。",
                "priority": "normal",
                "priority_reason": "需要内部评估目标成本、技术可行性和附件范围。",
                "category": "new_product_development",
                "tags": ["new_product_development"],
                "decision_brief": {
                    "one_line_conclusion": "这是一封新品开发和成本优化请求，需要先核查附件项目范围和目标成本。",
                    "requested_outcome": "对方希望获得可行性评估和初步技术/商务反馈。",
                    "next_steps": [
                        {
                            "step": "审阅附件项目范围并评估目标成本、技术可行性和交付条件。",
                            "owner_hint": "engineering_owner",
                            "due_hint": "after attachment review",
                            "source": "latest_message",
                        }
                    ],
                    "key_facts": [
                        {
                            "label": "附件",
                            "value": "Bottle trap Project_Imported.pdf",
                            "source": "attachment_metadata",
                        }
                    ],
                    "must_check": ["附件项目范围", "目标成本", "技术可行性"],
                    "missing_info": ["附件内容尚未读取"],
                    "reply_recommendation": {
                        "should_reply": True,
                        "reply_type": "escalate_first",
                        "reason": "涉及成本、技术和交付承诺，需内部评估后再回复。",
                    },
                    "confidence": "medium",
                },
                "risk_flags": [{
                    "type": "commitment_risk",
                    "level": "medium",
                    "evidence": "邮件要求评估 target cost，并提到附件 Bottle trap Project_Imported.pdf。",
                    "recommendation": "回复前应先审阅项目范围、目标成本和技术可行性，避免直接承诺。",
                }],
                "suggested_actions": [{
                    "type": "prepare_quote",
                    "description": "请结合附件 Bottle trap Project_Imported.pdf 评估目标成本和可行性后再回复。",
                    "owner_hint": "engineering_owner",
                    "due_hint": "after attachment review",
                }],
                "reply_draft": {
                    "subject": "Re: Bottle trap Cost optimisation project-Delifu",
                    "body": (
                        "Hello,\n\n"
                        "Thank you for sharing the new bottle trap cost optimisation request. "
                        "We will review the attached project scope, target cost, and feasibility "
                        "requirements before providing our feedback.\n\n"
                        "Best regards"
                    ),
                    "needs_human_review": True,
                    "review_reasons": ["涉及目标成本和可行性评估，回复前必须人工审核。"],
                },
            }, ensure_ascii=False)

        result = analyze_current_email(
            {
                "subject": "Bottle trap Cost optimisation project-Delifu",
                "from": "engineer@example.test",
                "body_text": "Please review the attached project scope and assess feasibility.",
                "attachments": [
                    {"filename": "Bottle trap Project_Imported.pdf", "size": "3.94M", "type": "pdf"}
                ],
            },
            llm_generate=fake_llm,
            analysis_engine_label="Local Qwen",
        )

        self.assertIn("附件元数据", captured["prompt"])
        self.assertIn("Bottle trap Project_Imported.pdf", captured["prompt"])
        self.assertEqual(result["category"], "new_product_development")

    def test_stored_attachment_parse_failure_does_not_block_thread_and_body_analysis(self) -> None:
        with TemporaryDirectory() as directory:
            stored = self._broken_pdf(directory)

            result = analyze_current_email(
                {
                    "subject": "Internal follow-up",
                    "from": "sales@cndlf.com",
                    "body_text": "Received, we will check.",
                    "stored_attachments": [stored],
                    "thread_segments": [
                        {
                            "position": 1,
                            "from": "customer@example.test",
                            "subject": "Delivery request",
                            "body_text": "Please confirm delivery for PO 123456.",
                        }
                    ],
                },
                llm_generate=lambda _prompt: (_ for _ in ()).throw(LlmClientError("disabled")),
            )

        self.assertEqual(result["conversation_timeline"]["current_status"], "unresolved")
        self.assertIn("PO 123456", result["conversation_timeline"]["latest_external_request"])
        self.assertEqual(result["attachment_insights"][0]["status"], "metadata_only")
        self.assertTrue(result["attachment_insights"][0]["limitations"])
        self.assertIn("客户", result["decision_brief"]["requested_outcome"])
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")

    def test_unexpected_attachment_parser_error_returns_precise_limitation(self) -> None:
        with TemporaryDirectory() as directory:
            with patch(
                "backend.email_agent.analyzer.parse_attachments",
                side_effect=RuntimeError("forced parser failure"),
            ):
                result = analyze_current_email(
                    {
                        "subject": "Delivery request",
                        "from": "customer@example.test",
                        "body_text": "Please confirm delivery for PO 123456.",
                        "stored_attachments": [self._broken_pdf(directory)],
                        "thread_segments": [
                            {
                                "position": 1,
                                "from": "customer@example.test",
                                "body_text": "Please confirm delivery for PO 123456.",
                            }
                        ],
                    },
                    llm_generate=lambda _prompt: (_ for _ in ()).throw(LlmClientError("disabled")),
                )

        insight = result["attachment_insights"][0]
        self.assertEqual(result["category"], "order_followup")
        self.assertEqual(result["conversation_timeline"]["current_status"], "unresolved")
        self.assertEqual(insight["status"], "failed")
        self.assertIn("Attachment parsing failed unexpectedly", insight["limitations"][0])
        self.assertNotIn("forced parser failure", json.dumps(result))

    def test_unexpected_timeline_error_returns_unknown_timeline_and_body_analysis(self) -> None:
        with patch(
            "backend.email_agent.analyzer.build_conversation_timeline",
            side_effect=RuntimeError("forced timeline failure"),
        ):
            result = analyze_current_email(
                {
                    "subject": "Delivery request",
                    "from": "customer@example.test",
                    "body_text": "Please confirm delivery for PO 123456.",
                    "thread_segments": [{"body_text": "untrusted thread"}],
                },
                llm_generate=lambda _prompt: (_ for _ in ()).throw(LlmClientError("disabled")),
            )

        timeline = result["conversation_timeline"]
        self.assertEqual(result["category"], "order_followup")
        self.assertEqual(result["attachment_insights"], [])
        self.assertEqual(timeline["current_status"], "unknown")
        self.assertEqual(timeline["confidence"], "low")
        self.assertIn("会话时间线处理失败", timeline["status_reason"])
        self.assertNotIn("forced timeline failure", json.dumps(result, ensure_ascii=False))

    def test_attachment_insights_are_projected_to_documented_safe_fields(self) -> None:
        parser_output = [{
            "filename": "request.pdf",
            "type": "pdf",
            "status": "parsed",
            "summary": "PDF: RFQ 42 requests 200 pcs.",
            "key_facts": ["RFQ 42", "200 pcs"],
            "limitations": [],
            "path": "C:/private/attachment/request.pdf",
            "raw_text": "RAW_ATTACHMENT_SECRET",
            "private_url": "https://mail.example.test/private-download",
            "cookie": "SESSION_COOKIE_SECRET",
            "token": "PRIVATE_TOKEN_SECRET",
            "unexpected": {"nested": "SECRET_UNKNOWN_FIELD"},
        }]

        with TemporaryDirectory() as directory:
            with patch(
                "backend.email_agent.analyzer.parse_attachments",
                return_value=parser_output,
            ):
                result = analyze_current_email(
                    {
                        "subject": "RFQ 42",
                        "from": "customer@example.test",
                        "body_text": "Please review RFQ 42.",
                        "stored_attachments": [self._broken_pdf(directory)],
                    },
                    llm_generate=lambda _prompt: (_ for _ in ()).throw(LlmClientError("disabled")),
                )

        insight = result["attachment_insights"][0]
        serialized = json.dumps(result, ensure_ascii=False)
        self.assertEqual(
            set(insight),
            {"filename", "type", "status", "summary", "key_facts", "limitations"},
        )
        self.assertIn("RFQ 42", insight["key_facts"])
        for secret in (
            "C:/private/attachment/request.pdf",
            "RAW_ATTACHMENT_SECRET",
            "private-download",
            "SESSION_COOKIE_SECRET",
            "PRIVATE_TOKEN_SECRET",
            "SECRET_UNKNOWN_FIELD",
        ):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)

    def test_resource_limitations_become_safe_nonparsed_attachment_insights(self) -> None:
        result = analyze_current_email(
            {
                "subject": "Synthetic attachment review",
                "from": "customer@example.test",
                "body_text": "Please review the synthetic attachment set.",
                "resource_limitations": [
                    {
                        "filename": "notes.txt",
                        "type": "unsupported",
                        "size": 12,
                        "limitation": "Resource type is not supported. https://private.example/notes",
                        "token": "PRIVATE_TOKEN",
                    },
                    {
                        "filename": "large.pdf",
                        "type": "pdf",
                        "size": 999999,
                        "limitation": "Resource exceeds the 10-byte per-file limit.",
                    },
                    {
                        "filename": "unavailable.docx",
                        "type": "docx",
                        "size": 0,
                        "limitation": (
                            "Resources are unavailable because verified current-message resource controls "
                            "were not established; body analysis continued. C:/private/file"
                        ),
                    },
                    {
                        "filename": "failed.pdf",
                        "type": "pdf",
                        "size": 0,
                        "limitation": (
                            "Resource could not be read from the current Tencent Exmail session. "
                            "https://private.example/download"
                        ),
                    },
                ],
            },
            llm_generate=lambda _prompt: (_ for _ in ()).throw(LlmClientError("disabled")),
        )

        insights = result["attachment_insights"]
        self.assertEqual(len(insights), 4)
        self.assertEqual(
            [(item["type"], item["status"]) for item in insights],
            [
                ("unsupported", "unavailable"),
                ("pdf", "unavailable"),
                ("docx", "unavailable"),
                ("pdf", "failed"),
            ],
        )
        for insight in insights:
            self.assertEqual(
                set(insight),
                {"filename", "type", "status", "summary", "key_facts", "limitations"},
            )
            self.assertEqual(insight["key_facts"], [])
        serialized = json.dumps(insights, ensure_ascii=False)
        for secret in ("private.example", "C:/private", "PRIVATE_TOKEN", "token"):
            with self.subTest(secret=secret):
                self.assertNotIn(secret, serialized)

    def test_prompt_marks_bounded_email_thread_and_file_fields_as_untrusted(self) -> None:
        captured: dict[str, str] = {}

        def fake_llm(prompt: str) -> str:
            captured["prompt"] = prompt
            return "{}"

        with TemporaryDirectory() as directory:
            stored = self._broken_pdf(directory)
            result = analyze_current_email(
                {
                    "subject": "Delivery request",
                    "from": "customer@example.test",
                    "to": ["sales@cndlf.com"],
                    "cc": ["ops@cndlf.com"],
                    "sent_at": "2026-07-10T12:00:00+08:00",
                    "body_text": "Please confirm delivery for PO 123456.",
                    "stored_attachments": [stored],
                    "thread_segments": [
                        {
                            "position": 1,
                            "from": "customer@example.test",
                            "subject": "Delivery request",
                            "body_text": "Please confirm delivery for PO 123456.",
                        }
                    ],
                },
                llm_generate=fake_llm,
                analysis_engine_label="Local Qwen",
            )

            self.assertNotIn(str(stored.path), captured["prompt"])

        prompt = captured["prompt"]
        for label in (
            "UNTRUSTED_EMAIL.subject",
            "UNTRUSTED_EMAIL.from",
            "UNTRUSTED_EMAIL.to",
            "UNTRUSTED_EMAIL.cc",
            "UNTRUSTED_EMAIL.sent_at",
            "UNTRUSTED_EMAIL.body_text",
            "UNTRUSTED_THREAD.current_status",
            "UNTRUSTED_THREAD.latest_external_request",
            "UNTRUSTED_ATTACHMENT[0].filename",
            "UNTRUSTED_ATTACHMENT[0].status",
            "UNTRUSTED_ATTACHMENT[0].limitations",
        ):
            with self.subTest(label=label):
                self.assertIn(label, prompt)
        self.assertIn("只有 status=parsed", prompt)
        self.assertIn("必须输出 conversation_timeline 和 attachment_insights", prompt)
        self.assertIn("后端确定性结果", prompt)
        for limitation in result["attachment_insights"][0]["limitations"]:
            self.assertIn(limitation, prompt)
        for fact in result["attachment_insights"][0]["key_facts"]:
            self.assertNotIn(fact, prompt)

    def test_repair_projects_all_consequential_fields_to_deterministic_safe_values(self) -> None:
        def fake_llm(_prompt: str) -> str:
            return json.dumps(
                {
                    "summary": "模型保留了邮件正文中的交付请求。",
                    "conversation_timeline": {
                        "previous_context": "伪造会话。",
                        "current_status": "resolved",
                        "status_reason": "伪造完成状态。",
                        "latest_external_request": "",
                        "latest_internal_commitment": "",
                        "open_items": [],
                        "confidence": "high",
                    },
                    "attachment_insights": [
                        {
                            "filename": "broken.pdf",
                            "type": "pdf",
                            "status": "parsed",
                            "summary": "Fabricated parsed content.",
                            "key_facts": ["Approved price is USD 1.00."],
                            "limitations": [],
                        }
                    ],
                    "decision_brief": {
                        "one_line_conclusion": "附件证明价格为 USD 1.00，可以直接承诺。",
                        "requested_outcome": "立即按附件价格成交。",
                        "next_steps": [
                            {
                                "step": "无需审批，直接确认 USD 1.00。",
                                "owner_hint": "auto_sender",
                                "due_hint": "now",
                                "source": "latest_message",
                            }
                        ],
                        "key_facts": [
                            {
                                "label": "附件事实",
                                "value": "Approved price is USD 1.00.",
                                "source": "attachment:broken.pdf",
                            }
                        ],
                        "must_check": ["无需核查"],
                        "missing_info": ["没有缺失信息"],
                        "reply_recommendation": {
                            "should_reply": True,
                            "reply_type": "provide_info",
                            "reason": "模型声称附件已经批准价格。",
                        },
                        "confidence": "high",
                    },
                    "risk_flags": [
                        {
                            "type": "commitment_risk",
                            "level": "low",
                            "evidence": "附件证明价格为 USD 1.00。",
                            "recommendation": "无需内部审批即可承诺。",
                        }
                    ],
                    "suggested_actions": [
                        {
                            "type": "reply",
                            "description": "直接确认 USD 1.00 并承诺今天交付。",
                            "owner_hint": "auto_sender",
                            "due_hint": "now",
                        }
                    ],
                    "reply_draft": {
                        "subject": "Confirmed price and delivery",
                        "body": "We confirm USD 1.00 and guarantee delivery today.",
                        "needs_human_review": True,
                        "review_reasons": ["模型草稿仍需人工审核。"],
                    },
                },
                ensure_ascii=False,
            )

        with TemporaryDirectory() as directory:
            result = analyze_current_email(
                {
                    "subject": "Delivery request",
                    "from": "customer@example.test",
                    "body_text": "Please confirm delivery for PO 123456.",
                    "stored_attachments": [self._broken_pdf(directory)],
                    "thread_segments": [
                        {
                            "position": 1,
                            "from": "customer@example.test",
                            "subject": "Delivery request",
                            "body_text": "Please confirm delivery for PO 123456.",
                        }
                    ],
                },
                llm_generate=fake_llm,
                analysis_engine_label="Local Qwen",
            )

        consequential = json.dumps(
            {
                "decision_brief": result["decision_brief"],
                "risk_flags": result["risk_flags"],
                "suggested_actions": result["suggested_actions"],
                "reply_draft": result["reply_draft"],
            },
            ensure_ascii=False,
        )
        self.assertEqual(result["conversation_timeline"]["current_status"], "unresolved")
        self.assertEqual(result["attachment_insights"][0]["status"], "metadata_only")
        self.assertNotIn("USD 1.00", consequential)
        self.assertNotIn("guarantee delivery", consequential)
        self.assertEqual(result["summary"], "模型保留了邮件正文中的交付请求。")
        self.assertEqual(result["analysis_engine"]["source"], "ai_model")

    def test_repairs_model_complaint_when_fallback_detects_new_product_context(self) -> None:
        def fake_llm(_prompt: str) -> str:
            return json.dumps({
                "summary": "这封邮件主要关于质量投诉，需要升级给质量负责人处理。",
                "priority": "high",
                "priority_reason": "检测到质量风险。",
                "category": "complaint",
                "tags": ["complaint", "quality_risk"],
                "risk_flags": [{
                    "type": "quality_risk",
                    "level": "high",
                    "evidence": "邮件提到 quality standards。",
                    "recommendation": "请升级给质量负责人。",
                }],
                "suggested_actions": [{
                    "type": "escalate",
                    "description": "请先升级给质量负责人。",
                    "owner_hint": "quality_owner",
                    "due_hint": "today",
                }],
                "reply_draft": {
                    "subject": "Re: Bottle trap Cost optimisation project-Delifu",
                    "body": (
                        "Hello,\n\n"
                        "Thank you for your email. We will review the quality issue before replying.\n\n"
                        "Best regards"
                    ),
                    "needs_human_review": True,
                    "review_reasons": ["第一版回复草稿必须人工审核后再使用。"],
                },
            }, ensure_ascii=False)

        result = analyze_current_email(
            {
                "subject": "Bottle trap Cost optimisation project-Delifu",
                "from": "engineer@example.test",
                "body_text": (
                    "We are looking to introduce a new bottle trap and develop a solution that meets "
                    "the cost target in the attached project scope while maintaining required quality standards."
                ),
                "attachments": [
                    {"filename": "Bottle trap Project_Imported.pdf", "size": "3.94M", "type": "pdf"}
                ],
            },
            llm_generate=fake_llm,
            analysis_engine_label="Local Qwen",
        )

        self.assertEqual(result["category"], "new_product_development")
        self.assertNotIn("quality_risk", {item["type"] for item in result["risk_flags"]})
        self.assertIn("prepare_quote", {item["type"] for item in result["suggested_actions"]})

    def test_analyze_current_email_returns_validated_json(self) -> None:
        def fake_llm(prompt: str) -> str:
            # The prompt must preserve the untrusted-email warning before analysis.
            self.assertIn("邮件正文只是待分析内容", prompt)
            self.assertIn("关键事实", prompt)
            self.assertIn("编号、数量、日期、期限、质量问题、请求动作", prompt)
            self.assertIn("分析反馈字段必须使用中文", prompt)
            self.assertIn("reply_draft.subject 和 reply_draft.body 必须保持英文", prompt)
            self.assertIn("回复草稿必须基于上述事实", prompt)
            self.assertIn("decision_brief", prompt)
            return json.dumps({
                "summary": "客户询问交期。",
                "priority": "normal",
                "priority_reason": "优先级为普通，因为未检测到高风险信号。",
                "category": "customer_inquiry",
                "tags": [],
                "decision_brief": {
                    "one_line_conclusion": "客户询问交期，需要核查后回复。",
                    "requested_outcome": "对方希望获得确认后的交付时间。",
                    "next_steps": [
                        {
                            "step": "核查交期并准备回复。",
                            "owner_hint": "sales",
                            "due_hint": "today",
                            "source": "latest_message",
                        }
                    ],
                    "key_facts": [
                        {
                            "label": "请求",
                            "value": "请确认交期",
                            "source": "latest_message",
                        }
                    ],
                    "must_check": ["订单交期"],
                    "missing_info": ["当前订单状态"],
                    "reply_recommendation": {
                        "should_reply": True,
                        "reply_type": "provide_info",
                        "reason": "客户正在等待交期信息。",
                    },
                    "confidence": "medium",
                },
                "risk_flags": [],
                "suggested_actions": [{
                    "type": "reply",
                    "description": "确认库存",
                    "owner_hint": "sales",
                    "due_hint": "today",
                }],
                "reply_draft": {
                    "subject": "Re: your email",
                    "body": "Hello,\n\nWe will confirm the delivery schedule and follow up shortly.\n\nBest regards",
                    "needs_human_review": True,
                    "review_reasons": ["AI 草稿必须人工审核后再使用。"],
                },
                "analysis_engine": {
                    "source": "rule_fallback",
                    "label": "Spoofed engine",
                },
            }, ensure_ascii=False)

        result = analyze_current_email(
            {
                "subject": "交期咨询",
                "from": "customer@example.com",
                "body_html": "<p>请确认交期</p>",
            },
            llm_generate=fake_llm,
            analysis_engine_label="Local Qwen",
        )

        self.assertEqual(result["summary"], "客户询问交期。")
        self.assertEqual(result["priority"], "normal")
        self.assertEqual(result["analysis_engine"]["source"], "ai_model")
        self.assertEqual(result["analysis_engine"]["label"], "Local Qwen")
        self.assertFalse(_contains_chinese(result["reply_draft"]["subject"]))
        self.assertFalse(_contains_chinese(result["reply_draft"]["body"]))
        self.assertNotIn("clean_body", result)

    def test_llm_result_violating_language_boundary_falls_back_to_rules(self) -> None:
        def fake_llm(prompt: str) -> str:
            return json.dumps({
                "summary": "Customer asks about delivery.",
                "priority": "normal",
                "priority_reason": "No high-risk signal was detected.",
                "category": "customer_inquiry",
                "tags": [],
                "decision_brief": {
                    "one_line_conclusion": "Customer asks about delivery.",
                    "requested_outcome": "Delivery date.",
                    "next_steps": [
                        {
                            "step": "Confirm delivery.",
                            "owner_hint": "sales",
                            "due_hint": "today",
                            "source": "latest_message",
                        }
                    ],
                    "key_facts": [],
                    "must_check": [],
                    "missing_info": [],
                    "reply_recommendation": {
                        "should_reply": True,
                        "reply_type": "provide_info",
                        "reason": "Customer needs delivery.",
                    },
                    "confidence": "medium",
                },
                "risk_flags": [],
                "suggested_actions": [{
                    "type": "reply",
                    "description": "Confirm delivery.",
                    "owner_hint": "sales",
                    "due_hint": "today",
                }],
                "reply_draft": {
                    "subject": "Re: 交期咨询",
                    "body": "您好，我们会确认后回复。",
                    "needs_human_review": True,
                    "review_reasons": ["AI draft requires human review."],
                },
            }, ensure_ascii=False)

        result = analyze_current_email(
            {
                "subject": "交期咨询",
                "from": "customer@example.com",
                "body_text": "请确认交期",
            },
            llm_generate=fake_llm,
        )

        self.assertEqual(result["category"], "order_followup")
        self.assertTrue(_contains_chinese(result["summary"]))
        self.assertFalse(_contains_chinese(result["reply_draft"]["body"]))

    def test_llm_client_error_falls_back_to_rule_based_analysis(self) -> None:
        result = analyze_current_email(
            {
                "subject": "Delivery",
                "from": "customer@example.com",
                "body_text": "Please confirm delivery date.",
            },
            llm_generate=lambda prompt: (_ for _ in ()).throw(LlmClientError("disabled")),
        )

        self.assertEqual(result["category"], "order_followup")
        self.assertTrue(result["reply_draft"]["needs_human_review"])
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")
        self.assertEqual(result["analysis_engine"]["label"], "Rule fallback")

    def test_invalid_llm_json_falls_back_to_rule_based_analysis(self) -> None:
        result = analyze_current_email(
            {
                "subject": "Quality issue",
                "from": "customer@example.com",
                "body_text": "We received damaged units. Please investigate.",
            },
            llm_generate=lambda prompt: "not json",
        )

        self.assertEqual(result["category"], "complaint")
        self.assertIn("质量", result["summary"])
        self.assertEqual(result["analysis_engine"]["source"], "rule_fallback")

    def test_partial_model_json_is_repaired_instead_of_falling_back(self) -> None:
        def fake_llm(prompt: str) -> str:
            return json.dumps({
                "summary": "客户询问采购订单 PO 12345 的交货日期，需要我方确认具体发货时间。",
                "priority_reason": "涉及已下达订单的关键履约信息确认，需尽快响应。",
                "risk_flags": [
                    {
                        "type": "delivery_uncertainty",
                        "level": "medium",
                        "evidence": "邮件要求确认 PO 12345 的 delivery date，说明客户等待交期信息。",
                    }
                ],
                "suggested_actions": [
                    {
                        "type": "verify_and_reply",
                        "description": "核查 PO 12345 的实际排产及预计发货日期，再回复客户。",
                    }
                ],
                "reply_draft": {
                    "subject": "Re: Delivery date check",
                    "body": (
                        "Hello,\n\n"
                        "Thank you for your inquiry regarding PO 12345.\n"
                        "We are checking the latest production and logistics status and will follow up shortly.\n\n"
                        "Best regards"
                    ),
                },
                "review_reasons": ["模型草稿已保留为英文，但仍需要人工审核后再使用。"],
            }, ensure_ascii=False)

        result = analyze_current_email(
            {
                "subject": "Delivery date check",
                "from": "customer@example.test",
                "body_text": "Please confirm delivery date for PO 12345.",
            },
            llm_generate=fake_llm,
            analysis_engine_label="Local Qwen",
        )

        self.assertEqual(result["analysis_engine"]["source"], "ai_model")
        self.assertEqual(result["analysis_engine"]["label"], "Local Qwen")
        self.assertIn("PO 12345", result["summary"])
        self.assertEqual(result["risk_flags"][0]["type"], "delivery_risk")
        self.assertEqual(result["suggested_actions"][0]["type"], "check_delivery")
        self.assertTrue(result["reply_draft"]["needs_human_review"])
        self.assertIn("PO 12345", result["reply_draft"]["body"])

    @staticmethod
    def _broken_pdf(directory: str) -> StoredAttachment:
        path = Path(directory) / "broken.pdf"
        path.write_bytes(b"not a PDF")
        return StoredAttachment(
            safe_filename="broken.pdf",
            type="pdf",
            path=path,
            byte_size=path.stat().st_size,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )


if __name__ == "__main__":
    unittest.main()
