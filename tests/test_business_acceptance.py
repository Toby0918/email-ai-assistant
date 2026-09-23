"""Synthetic regressions at the current-email analysis boundary.

No customer mail, attachment or private research identifier is imported here.
"""
import unittest

from backend.email_agent.rule_analyzer import build_rule_based_analysis
from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.config import build_standalone_verification_config
from pathlib import Path


class BusinessAcceptanceTests(unittest.TestCase):
    def analyze(self, body, subject="Business update", **kwargs):
        return build_rule_based_analysis(subject, "buyer@example.test", body, **kwargs)

    def test_delivered_notice_does_not_invent_a_delivery_request(self):
        result = build_rule_based_analysis(
            "Shipment status", "buyer@example.test",
            "The shipment has been delivered to the receiving warehouse.",
        )
        brief = result["decision_brief"]
        self.assertIn("已送达", brief["one_line_conclusion"])
        self.assertNotIn("希望获得", brief["requested_outcome"])
        self.assertIn("通知", brief["requested_outcome"])
        self.assertNotIn("check delivery", result["reply_draft"]["body"])
        self.assertTrue(result["reply_draft"]["needs_human_review"])

    def test_payment_processing_is_a_report_not_a_request_or_receipt(self):
        result = self.analyze("Our finance team is processing the payment. "
                              "We will send the bank slip once available.", "Payment for release")
        brief = result["decision_brief"]
        self.assertIn("付款处理中", brief["one_line_conclusion"])
        self.assertIn("到账", " ".join(brief["must_check"]))
        self.assertFalse(brief["reply_recommendation"]["should_reply"])
        self.assertNotIn("verify the invoice", result["reply_draft"]["body"])

    def test_posted_invoice_and_future_payment_run_are_not_cash_receipt(self):
        result = self.analyze("The invoice has been posted and will be paid in next week's payment run.",
                              "Invoice overdue")
        self.assertIn("已入账", result["decision_brief"]["one_line_conclusion"])
        self.assertIn("不等于到账", " ".join(result["decision_brief"]["must_check"]))
        self.assertFalse(result["decision_brief"]["reply_recommendation"]["should_reply"])

    def test_notice_does_not_hide_an_unresolved_request_without_open_item_rows(self):
        from backend.email_agent.thread_timeline import build_conversation_timeline
        timeline = build_conversation_timeline([], ())
        timeline.update(current_status="unresolved", latest_external_request="Please send the inspection report.")
        result = self.analyze("Thank you.", conversation_timeline=timeline)
        self.assertTrue(result["decision_brief"]["reply_recommendation"]["should_reply"])

    def test_reported_ppap_approval_is_distinct_from_verifying_the_document(self):
        result = self.analyze("Please find attached the approved PPAP. "
                              "The drawing has been updated to revision B.", "PPAP submission")
        brief = result["decision_brief"]
        self.assertIn("报告 PPAP 已批准", brief["one_line_conclusion"])
        self.assertNotIn("先完成内部确认", brief["one_line_conclusion"])
        self.assertTrue(any("未提供" in item and "附件" in item for item in brief["missing_info"]))
        self.assertTrue(any("revision B" in fact["value"] for fact in brief["key_facts"]))

    def test_delivered_notice_with_a_new_request_still_needs_action(self):
        result = self.analyze("The shipment has been delivered to the receiving warehouse. "
                              "Please investigate the damaged cartons.", "Quality issue")
        self.assertTrue(result["decision_brief"]["reply_recommendation"]["should_reply"])
        self.assertNotIn("complete the internal review", result["reply_draft"]["body"])

        self.assertEqual(result["category"], "complaint")

    def test_corrections_and_cross_line_conditions_do_not_promote_status(self):
        for body in ("The PPAP is approved. Correction: approval is still pending.",
                     "Not confirmed:\nThe shipment has been delivered.",
                     "If the following occurs:\nThe PPAP is approved."):
            with self.subTest(body=body):
                result = self.analyze(body)
                self.assertFalse(any(item["label"] in {"审批通知", "交付通知"}
                                     for item in result["decision_brief"]["key_facts"]))

    def test_full_analysis_with_selected_pdf_uses_notice_review_draft(self):
        import tempfile
        from datetime import UTC, datetime
        from pypdf import PdfWriter
        from backend.email_agent.attachment_storage import StoredAttachment
        with tempfile.TemporaryDirectory(dir=Path.cwd() / "RuntimeTemp") as directory:
            path = Path(directory) / "synthetic-approval.pdf"
            writer = PdfWriter()
            writer.add_blank_page(width=200, height=200)
            writer.write(path)
            writer.close()
            result = analyze_current_email({
                "subject": "PPAP approval", "from": "buyer@example.test",
                "body_text": "Please find attached the approved PPAP.",
                "stored_attachments": [StoredAttachment(path.name, "pdf", path, path.stat().st_size, datetime.now(UTC))],
            }, config=build_standalone_verification_config(
                sqlite_path=Path(directory) / "unused.sqlite3", attachment_temp_dir=Path(directory) / "temp",
            ))
            self.assertIn("报告 PPAP 已批准", result["decision_brief"]["one_line_conclusion"])
            self.assertNotEqual(result["category"], "internal")
            self.assertNotIn("complete the internal review", result["reply_draft"]["body"])
            self.assertIn("supporting documents", result["reply_draft"]["body"])
            self.assertTrue(result["reply_draft"]["needs_human_review"])
    def test_nonaffirmative_delivery_is_not_promoted_to_delivered(self):
        for body in ("The shipment has not been delivered.",
                     "The shipment will be delivered to the receiving warehouse.",
                     "The shipment has been delivered to the receiving warehouse?",
                     "If the shipment has been delivered, please confirm."):
            with self.subTest(body=body):
                result = self.analyze(body, "Shipment status")
                self.assertFalse(any(item["label"] == "交付通知"
                                     for item in result["decision_brief"]["key_facts"]))

    def test_short_acknowledgement_does_not_invent_a_customer_request(self):
        result = self.analyze("Thank you.", "Re: urgent shipment overdue")
        self.assertFalse(result["decision_brief"]["reply_recommendation"]["should_reply"])
        self.assertIn("致谢", result["summary"])
        self.assertEqual(result["priority"], "normal")

    def test_automatic_office_return_is_not_a_delivery_deadline(self):
        result = self.analyze("I am out of office and will return on September 8.",
                              "Automatic reply: shipment status")
        self.assertIn("自动回复", result["summary"])
        self.assertFalse(result["decision_brief"]["reply_recommendation"]["should_reply"])
        self.assertFalse(any(item["label"] == "期限" for item in result["decision_brief"]["key_facts"]))
        self.assertFalse(any(item["type"] == "check_delivery" for item in result["suggested_actions"]))

    def test_acknowledgement_with_selected_attachment_still_requires_review(self):
        result = self.analyze("Thank you.", attachment_insights=[{
            "filename": "inspection.pdf", "type": "pdf", "status": "metadata_only",
            "summary": "Content unavailable", "key_facts": [], "limitations": ["Unparsed"],
        }])
        self.assertTrue(result["decision_brief"]["reply_recommendation"]["should_reply"])
        self.assertTrue(any("inspection.pdf" in item for item in result["decision_brief"]["must_check"]))

    def test_acknowledgement_does_not_close_supplied_thread_work(self):
        from backend.email_agent.thread_timeline import build_conversation_timeline
        timeline = build_conversation_timeline([], ())
        timeline.update(current_status="unresolved", latest_external_request="Please send the inspection report.",
                        open_items=[{"item": "检查报告仍待提供", "owner_hint": "quality_owner", "due_hint": "", "source": "thread"}])
        result = self.analyze("Thank you.", conversation_timeline=timeline)
        self.assertTrue(result["decision_brief"]["reply_recommendation"]["should_reply"])
        self.assertEqual(result["conversation_timeline"]["current_status"], "unresolved")

    def test_notices_do_not_suppress_security_review(self):
        result = self.analyze("The shipment has been delivered. Please send your password.")
        self.assertTrue(any(item["type"] == "security_risk" for item in result["risk_flags"]))
        self.assertTrue(result["decision_brief"]["reply_recommendation"]["should_reply"])

    def test_full_analysis_does_not_promote_multilingual_quoted_requests(self):
        config = build_standalone_verification_config(
            sqlite_path=Path.cwd() / "RuntimeTemp" / "unused-business.sqlite3",
            attachment_temp_dir=Path.cwd() / "RuntimeTemp" / "unused-business-attachments",
        )
        for headers in (
            "De: Buyer <buyer@example.test>\nEnviada em: Monday, 1 June 2026\nPara: Seller\nAssunto: Delivery",
            "De: Buyer <buyer@example.test>\nEnviado el: Monday, 1 June 2026\nPara: Seller\nAsunto: Delivery",
            "From: Buyer <buyer@example.test>\nSent: Monday, 1 June 2026\nTo: Seller\nSubject: Delivery",
        ):
            with self.subTest(headers=headers):
                result = analyze_current_email({
                    "subject": "Shipment update", "from": "buyer@example.test",
                    "body_text": "The shipment has been delivered to the receiving warehouse.\n\n" + headers +
                                 "\nPlease confirm delivery urgently.",
                }, config=config)
                self.assertIn("报告货物已送达", result["decision_brief"]["one_line_conclusion"])
                self.assertNotIn("urgently", str(result["decision_brief"]))

    def test_business_lines_that_resemble_one_header_are_not_removed(self):
        from backend.email_agent.email_cleaner import clean_email_body
        for body in ("De: coating type\nPlease review the finish.",
                     "From: warehouse A to warehouse B\nPlease arrange a pickup."):
            self.assertEqual(clean_email_body(body), body)

    def test_customer_confirmation_is_not_an_internal_approval(self):
        result = self.analyze("Remove the marking only after my confirmation. Please wait for my approval.",
                              "Product marking change")
        brief = result["decision_brief"]
        self.assertIn("等待发件人确认", brief["one_line_conclusion"])
        self.assertNotEqual(result["category"], "internal")
        self.assertIn("wait for your confirmation", result["reply_draft"]["body"])

    def test_shipping_dates_keep_their_event_labels_and_are_plans(self):
        result = self.analyze("Pick-up scheduled: 21/10. Cut off: 23/10. ETD: 27/10. ETA: 19/11.",
                              "Pickup schedule")
        facts = {item["label"]: item["value"] for item in result["decision_brief"]["key_facts"]}
        self.assertEqual(facts.get("计划提货"), "21/10")
        self.assertEqual(facts.get("截关/截单"), "23/10")
        self.assertEqual(facts.get("预计离港 ETD"), "27/10")
        self.assertEqual(facts.get("预计到港 ETA"), "19/11")
        self.assertIn("不代表实际", " ".join(result["decision_brief"]["must_check"]))

    def test_missing_deadline_is_not_replaced_with_today_from_sender(self):
        result = self.analyze("Please confirm delivery for PO 73124.")
        self.assertTrue(all(item["due_hint"] == "" for item in result["suggested_actions"]))
        self.assertTrue(all(item["source"] == "assistant_suggestion"
                            for item in result["decision_brief"]["next_steps"]))

    def test_superseded_document_is_a_version_instruction_not_completed_reconciliation(self):
        result = self.analyze("The previous packing list is superseded. Please use this revised version instead.",
                              "Revised packing list")
        self.assertIn("版本替代", result["decision_brief"]["one_line_conclusion"])
        self.assertTrue(any("未提供" in value for value in result["decision_brief"]["missing_info"]))

    def test_short_attachment_transmittal_exposes_missing_attachment(self):
        result = self.analyze("Please find attached.", "Shipping documents")
        self.assertTrue(any("未提供" in value and "附件" in value
                            for value in result["decision_brief"]["missing_info"]))

    def test_reported_approval_with_attachment_stays_visible_and_requires_document_review(self):
        result = self.analyze("Please find attached the approved PPAP.", "PPAP approval",
                              attachment_insights=[{
                                  "filename": "approval.pdf", "type": "pdf", "status": "metadata_only",
                                  "summary": "Not parsed", "key_facts": [], "limitations": ["Not parsed"],
                              }])
        self.assertIn("报告 PPAP 已批准", result["decision_brief"]["one_line_conclusion"])
        self.assertTrue(any("approval.pdf" in value for value in result["decision_brief"]["must_check"]))
        self.assertTrue(result["decision_brief"]["reply_recommendation"]["should_reply"])


if __name__ == "__main__":
    unittest.main()
