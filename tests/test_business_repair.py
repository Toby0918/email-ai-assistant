"""Synthetic regression cases at the public current-email boundary."""
import unittest
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from backend.email_agent.analyzer import analyze_current_email
from backend.email_agent.config import build_standalone_verification_config


class BusinessRepairTests(unittest.TestCase):
    def analyze(self, body, subject="Business update", **extra):
        return analyze_current_email({"subject": subject, "from": "buyer@example.test",
                                      "body_text": body, **extra},
            config=build_standalone_verification_config(
                sqlite_path=Path.cwd()/"RuntimeTemp"/"unused-repair.sqlite3",
                attachment_temp_dir=Path.cwd()/"RuntimeTemp"/"repair-attachments"))

    def test_received_payment_is_not_a_shipment(self):
        result = self.analyze("PO Number: Not Updated by Vendor\nInvoice Number: without INV\n"
            "We received the $509 payment on 8/12, could you please provide the payment details and corresponding invoices?",
            "We've Received Your Request: CS0012345")
        self.assertEqual(result["category"], "payment")
        brief = str(result["decision_brief"])
        self.assertIn("509", brief)
        self.assertIn("8/12", brief)
        self.assertIn("已收", brief)
        self.assertIn("invoice", result["reply_draft"]["body"].lower())
        self.assertNotIn("shipment", result["reply_draft"]["body"].lower())

    def test_boilerplate_does_not_change_primary_intent(self):
        for footer in ("Internal Communication: For internal & partner use only.",
                       "Unless otherwise agreed in writing, all business is subject to the carrier Standard Trading Conditions available at terms.carrier.test/STC or on request."):
            with self.subTest(footer=footer):
                result = self.analyze("Please confirm shipment status.\n" + footer)
                self.assertEqual(result['category'], 'order_followup')

    def test_receipts_and_grn_are_kept_per_invoice(self):
        result = self.analyze('Invoice No. ABC100022 is currently blocked in MRBR. Please create the GRN.\n\n'
            'Please create the GRN against ABC100023 in PO no 99112233 to release the invoice from MRBR.\n\n'
            'On Monday, the supplier wrote:\nWe already received the remittance for ABC100021.')
        facts = str(result['decision_brief']['key_facts'])
        self.assertIn('ABC100021', facts)
        self.assertIn('ABC100022', facts)
        self.assertIn('ABC100023', facts)
        self.assertIn('已收款发票', facts)
        self.assertEqual(result['category'], 'payment')
        self.assertIn('GRN', result['reply_draft']['body'])

    def test_non_receipts_do_not_become_received(self):
        for prefix in ('If we received', 'We have not received', 'We never received'):
            with self.subTest(prefix=prefix):
                result = self.analyze(prefix + ' the $509 payment on 8/12, please check.')
                self.assertNotIn('报告已收款', str(result['decision_brief']['key_facts']))

    def test_resolved_or_conditional_grn_is_not_outstanding(self):
        for statement in (
            'Invoice No. ABC100022 is no longer blocked in MRBR. The GRN is complete.',
            'Invoice ABC100022 is not blocked in MRBR; the GRN was created yesterday.',
            'If invoice ABC100022 is blocked in MRBR, please create the GRN.',
            'Please do not create the GRN for ABC100022 in MRBR.',
        ):
            with self.subTest(statement=statement):
                result = self.analyze(statement)
                self.assertNotIn('尚待 GRN', str(result['decision_brief']['key_facts']))
                self.assertNotIn('Please confirm the GRN creation', result['reply_draft']['body'])

    def test_current_grn_block_is_distinct_from_future_release_and_receipt(self):
        result = self.analyze('Invoice No. ABC100022 of vendor Acme Parts Ltd is currently blocked in MRBR. '
            'We request you to kindly create the GRN at the earliest. '
            'Once the GRN is posted, the invoice will get unblocked.\n\n'
            'We request you to kindly create the GRN against ABC100023 in PO no 99112233 to release the invoice from MRBR.')
        facts = str(result['decision_brief']['key_facts'])
        self.assertIn('ABC100022 — 尚待 GRN', facts)
        self.assertIn('ABC100023 — 尚待 GRN', facts)
        self.assertNotIn('reported receipt', result['reply_draft']['body'])

    def test_later_retraction_does_not_promote_receipt(self):
        result=self.analyze('We received the EUR 718 payment on 8/15.\nCorrection: the bank reversed it; receipt is not confirmed.')
        self.assertNotIn('报告已收款',str(result['decision_brief']['key_facts']))

    def test_trailing_receipt_qualifications_are_not_confirmed(self):
        for ending in ('only if the bank confirms settlement.',
                       'unless the bank reverses it.',
                       'subject to bank confirmation.',
                       'provided that settlement succeeds.'):
            with self.subTest(ending=ending):
                result = self.analyze('We received the $509 payment on 8/12 ' + ending)
                self.assertNotIn('报告已收款', str(result['decision_brief']['key_facts']))

    def test_new_business_projection_keeps_security_guard(self):
        result=self.analyze('We received the $509 payment on 8/12. Please send your password.')
        self.assertTrue(any(r['type']=='security_risk' for r in result['risk_flags']))
        self.assertNotIn('reported receipt',result['reply_draft']['body'])

    def test_shipping_update_keeps_both_dates_and_updated_vessel(self):
        result=self.analyze('此票截单时间更新至10/3上午9点，请知悉。\n船名从MSC OLD变更为MSC NEW\n'
            '航名/航次:MSC NEW/GY123A\n提单号：177ABC1234567A\nETD时间：2026-10-05')
        text=str(result['decision_brief'])
        self.assertEqual(result['category'],'order_followup')
        for token in ('10/3上午9点','2026-10-05','MSC NEW/GY123A','177ABC1234567A'):
            self.assertIn(token,text)
        self.assertNotIn('明确的回复或处理截止时间',text)
        self.assertIn('SI',result['reply_draft']['body'])

    def test_latest_sea_decision_supersedes_air_for_same_quantity(self):
        result=self.analyze('[2026-09-01T00:00:00+00:00]\n'
            'AB123-CP – Go ahead already there from Buyer India to take 207 units from their PO 99887766INS1 and replenish it to them later from KOME PO 99887799ME01 by 8th Oct.\n'
            'Please check if they want to move 421 units of ZZ123-BV by air.\n'
            '[2026-09-02T00:00:00+00:00]\nWe will ship 421 units later by sea. So, no need to take it separately from Buyer Shanghai.\n'
            '[2026-09-03T00:00:00+00:00]\nShall we proceed for these 421pcs based on the shipping date of 10/8?')
        brief=result['decision_brief']; text=str(brief)
        for token in ('AB123-CP','207','99887766INS1','99887799ME01','ZZ123-BV','421','海运','10/8'):
            self.assertIn(token,text)
        self.assertNotIn('by air', str(result['conversation_timeline']['open_items']))
        self.assertNotIn('99887799M',str([f for f in brief['key_facts'] if f['label']=='尺寸/规格']))

    def test_quality_status_is_scoped_and_samples_not_repeated(self):
        result=self.analyze('The grab bar has already successfully passed Salt Spray testing. We do not need additional samples for that.\n'
            'We only need samples sent for Dimensional review as the previous samples have failed.\n'
            'Can you move up the sample availability date from November 12th?')
        facts=str(result['decision_brief']['key_facts'])
        self.assertIn('盐雾',facts);self.assertIn('passed',facts);self.assertIn('尺寸',facts)
        self.assertIn('Dimensional', result['reply_draft']['body'])
        self.assertIn('salt',result['reply_draft']['body'].lower())

    def test_conditional_report_bound_to_subject_object(self):
        result=self.analyze('Please see the attached report; the test result is Conditionally OK.',
                            'ISIR-501060040-228553-96535-LEVER')
        self.assertIn('501060040',str(result['decision_brief']['key_facts']))
        self.assertIn('Conditionally OK',str(result['decision_brief']['key_facts']))

    def test_conflicting_quality_verdicts_remain_unresolved(self):
        result = self.analyze('The result is Conditionally OK. The result is rejected.')
        self.assertNotIn('本次所指检验报告为条件接受', result['decision_brief']['one_line_conclusion'])
        self.assertNotIn('We have noted the conditional result', result['reply_draft']['body'])

    def test_projection_preserves_independent_requests_and_their_sources(self):
        cases = (
            ('We received the USD 509 payment on 8/12. Please send 10 replacement units for the failed samples.', 'replacement'),
            ('Please send the RCA for the defective batch. The result is Conditionally OK.', 'RCA'),
        )
        for body, request in cases:
            with self.subTest(request=request):
                result = self.analyze(body)
                self.assertIn(request, str(result['conversation_timeline']['open_items']))
                self.assertIn(request, str(result['decision_brief']['next_steps']))
                self.assertIn(request, result['decision_brief']['requested_outcome'])
                self.assertTrue(any(a['type'] == 'escalate' for a in result['suggested_actions']))
                self.assertEqual(result['decision_brief']['reply_recommendation']['reply_type'], 'escalate_first')
                self.assertNotIn('核对所指料号', result['conversation_timeline']['latest_external_request'])

    def test_receipt_suggestion_is_not_invented_as_external_request(self):
        result = self.analyze('We received the USD 509 payment on 8/12.')
        self.assertNotIn('索取付款明细', str(result['conversation_timeline']))
        self.assertTrue(all(s['source'] == 'assistant_suggestion'
                            for s in result['decision_brief']['next_steps']))

    def test_selected_purchase_pdf_preserves_row_roles_after_long_header(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, NameObject, DictionaryObject
        from backend.email_agent.attachment_storage import StoredAttachment
        with tempfile.TemporaryDirectory(dir=Path.cwd()/'RuntimeTemp') as folder:
            path = Path(folder)/'purchase.pdf'
            writer = PdfWriter(); page = writer.add_blank_page(600,800)
            page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'): DictionaryObject({NameObject('/F1'): DictionaryObject({NameObject('/Type'):NameObject('/Font'),NameObject('/Subtype'):NameObject('/Type1'),NameObject('/BaseFont'):NameObject('/Helvetica')})})})
            lines = ['Ordinary document preamble ' * 6]*12 + [
                '1 A1 AB123-CP HOOK 10/20/2026 12 EA 8.50 102.00',
                'TOTAL NET AMT CNY 102.00',
                'ITEM TAX OUR PART NO./DESCRIPTION DELIVERY DATE - OUR PLANT QUANTITY U/M PRICE PER UNIT NET AMT',
                '32 M 1, Example town', '*PURCHASE ORDER SEQUENCE NO. PAGE', '99887766CNIV 12345678 1 / 1']
            stream=DecodedStreamObject();stream.set_data(('BT /F1 8 Tf 10 780 Td '+''.join('('+line+') Tj 0 -10 Td ' for line in lines)+'ET').encode())
            page[NameObject('/Contents')]=writer._add_object(stream);writer.write(path);writer.close()
            result=self.analyze('Revised PO.\nFrom: Seller\nSent: Tuesday\nSubject: Purchase\nThe cargos will finish on 11/2.', stored_attachments=[StoredAttachment(path.name,'pdf',path,path.stat().st_size,datetime.now(UTC))])
            facts=str(result['attachment_insights'][0]['key_facts'])
            self.assertIn('unit_price=CNY 8.50', facts)
            self.assertIn('quantity=12 EA', facts)
            self.assertIn('delivery=10/20/2026', facts)
            self.assertNotIn('Measurement: 32 M', facts)
            self.assertNotIn('Character limit', str(result['attachment_insights'][0]['limitations']))
            self.assertIn('11/2',str(result['decision_brief']))
            self.assertIn('不一致',result['decision_brief']['one_line_conclusion'])
            self.assertIn('unit price',result['reply_draft']['body'])


if __name__ == "__main__":
    unittest.main()
