"""Regressions from the operator's synthetic desktop acceptance screenshot."""
import unittest
import json
from dataclasses import replace
from pathlib import Path

from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.config import build_standalone_verification_config
from backend.email_agent.rule_analyzer import build_rule_based_analysis
from desktop_app.presentation import engine_text


class DeliveryAcceptanceTests(unittest.TestCase):
    def analyze(self, body):
        return build_rule_based_analysis("Delivery date confirmation", "buyer@example.test", body)

    def test_unagreed_price_does_not_turn_delivery_request_into_quote(self):
        result = self.analyze(
            "Please review the attached synthetic order specification and confirm the delivery date. "
            "The quantity is stated in the attachment. The production schedule has not been confirmed. "
            "Please check with production before promising any delivery date. No price has been agreed."
        )
        self.assertEqual(result["category"], "order_followup")
        self.assertNotIn("主要关于报价或询价", result["decision_brief"]["one_line_conclusion"])

    def test_before_an_action_is_not_a_deadline(self):
        result = self.analyze("Please check with production before promising any delivery date.")
        deadlines = [fact for fact in result["decision_brief"]["key_facts"] if fact["label"] == "期限"]
        self.assertEqual(deadlines, [])

    def test_delivery_draft_keeps_attachment_quantity_without_echoing_customer_request(self):
        result = build_rule_based_analysis(
            "Delivery date confirmation", "buyer@example.test",
            "Please review the attached synthetic order specification and confirm the delivery date. "
            "The production schedule has not been confirmed. No price has been agreed.",
            attachment_insights=[{"filename": "synthetic-order.xlsx", "type": "xlsx", "status": "parsed",
                                  "summary": "XLSX content parsed.", "key_facts": ["Quantity: 1200 pcs"], "limitations": []}],
        )
        draft = result["reply_draft"]["body"]
        self.assertIn("1200 pcs", draft)
        self.assertIn("before confirming any timing", draft)
        self.assertNotIn("Please review", draft)
        self.assertNotIn("confirm the delivery date", draft)
        self.assertTrue(result["reply_draft"]["needs_human_review"])

    def test_draft_target_contains_structured_facts_not_customer_narrative(self):
        result = build_rule_based_analysis(
            "Quality issue after delivery", "buyer@example.test",
            "We received 200 pcs with damaged surfaces for PO 123456. Please investigate the quality issue.",
        )
        draft = result["reply_draft"]["body"]
        self.assertIn("200 pcs", draft)
        self.assertIn("PO 123456", draft)
        self.assertIn("escalate the quality issue", draft)
        self.assertNotIn("We received", draft)
        self.assertNotIn("Please investigate", draft)

    def test_real_weekday_deadline_and_explicit_quote_are_retained(self):
        result = self.analyze("Please provide a quote and confirm delivery before Friday.")
        self.assertEqual(result["category"], "customer_inquiry")
        self.assertIn("before Friday", [fact["value"] for fact in result["decision_brief"]["key_facts"] if fact["label"] == "期限"])

    def test_month_only_delivery_deadline_is_retained(self):
        result = self.analyze("Please deliver before December.")
        self.assertIn("before December", [fact["value"] for fact in result["decision_brief"]["key_facts"] if fact["label"] == "期限"])

    def test_unset_price_variants_preserve_a_separate_quote_request(self):
        for absence in ("No price has been agreed.", "The price is not yet confirmed.",
                        "The price has not been agreed.", "价格尚未确定。"):
            with self.subTest(absence=absence):
                self.assertEqual(self.analyze("Please confirm delivery. " + absence)["category"], "order_followup")
                self.assertEqual(self.analyze("Please confirm delivery. " + absence +
                                             " Please provide a price.")["category"], "customer_inquiry")

    def test_conservative_deepseek_result_retains_correct_delivery_brief(self):
        config = replace(build_standalone_verification_config(
            sqlite_path=Path.cwd() / "unused.sqlite3", attachment_temp_dir=Path.cwd() / "unused-temp",
        ), llm_provider="deepseek", deepseek_api_key="synthetic-not-a-live-key", internal_email_domains=())
        result = analyze_current_email({
            "subject": "Delivery date confirmation", "from": "buyer@example.test",
            "body_text": "Please confirm delivery. Please check with production before promising any delivery date. No price has been agreed.",
        }, llm_generate=lambda _request: json.dumps({
            "summary": "客户询问交期，需要核查生产安排后回复。",
            "category": "order_followup", "priority": "normal",
            "priority_reason": "生产安排需要确认。",
        }), config=config)
        self.assertEqual(result["analysis_engine"]["source"], "ai_model")
        self.assertEqual(result["analysis_engine"]["label"], "DeepSeek Flash")
        self.assertIn("主要关于交付", result["decision_brief"]["one_line_conclusion"])
        self.assertFalse([fact for fact in result["decision_brief"]["key_facts"] if fact["label"] == "期限"])
        self.assertIn("本地规则生成", engine_text(result["analysis_engine"]))

    def test_engine_display_distinguishes_contribution_fallback_and_unknown(self):
        self.assertIn("未采用远程", engine_text({"source": "rule_fallback", "label": "Rule fallback"}))
        self.assertEqual(engine_text({"source": "ai_model", "label": "OpenAI GPT-5.6 Sol"}), "OpenAI GPT-5.6 Sol")
        self.assertEqual(engine_text({"source": "ai_model", "label": "DeepSeek Flash text fallback"}), "DeepSeek 文本回退分析")
        self.assertEqual(engine_text({"source": "ai_model", "label": ["untrusted"]}), "未确认分析引擎")


if __name__ == "__main__":
    unittest.main()
