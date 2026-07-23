"""Synthetic sales-message pairing, linkage, and deduplication tests."""

from __future__ import annotations

import unittest
from datetime import timedelta

from backend.mailbox_ingest.sales_message_policy import (
    evaluate_sales_message,
    pair_sales_messages,
    parse_sales_message_candidate,
    SalesMessageDecision,
)
from tests import mailbox_sales_corpus_support as corpus_support


class SalesMessageCandidateTests(
    corpus_support.SalesMessageCandidateTestCase,
):
    def test_raw_copy_identity_and_cleaned_pair_evidence_dedupe_are_distinct(self) -> None:
        def candidate(message_id: str, body: bytes, *, reply_to: str | None = None):
            if reply_to is None:
                sender, recipient, role = (
                    "buyer@customer.example.test", "agent@seller.example.test", "inbox"
                )
                references = ""
            else:
                sender, recipient, role = (
                    "agent@seller.example.test", "buyer@customer.example.test", "sent"
                )
                references = f"In-Reply-To: <{reply_to}>\r\nReferences: <{reply_to}>\r\n"
            header = (
                f"From: {sender}\r\nTo: {recipient}\r\n"
                f"Message-ID: <{message_id}>\r\n{references}\r\n"
            ).encode("ascii")
            return parse_sales_message_candidate(
                policy=self.policy,
                raw_header=header,
                raw_body=body,
                trusted_internal_date=self.now + (timedelta(minutes=5) if reply_to else timedelta()),
                folder_role=role,
                identity_key=self.key,
            )

        request_one = candidate("request-a@customer.example.test", b"Quote 40 valves.\r\n--\r\nA")
        reply_one = candidate("reply-a@seller.example.test", b"Lead time is four weeks.\r\n--\r\nA", reply_to="request-a@customer.example.test")
        request_two = candidate("request-b@customer.example.test", b"Quote 40 valves.\n--\nB")
        reply_two = candidate("reply-b@seller.example.test", b"Lead time is four weeks.\n--\nB", reply_to="request-b@customer.example.test")
        request_copy = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"FROM: BUYER@CUSTOMER.EXAMPLE.TEST\n"
                b"TO: AGENT@SELLER.EXAMPLE.TEST\n"
                b"MESSAGE-ID: <request-a@CUSTOMER.EXAMPLE.TEST>\n\n"
            ),
            raw_body=b"Quote 40 valves.\n--\nA",
            trusted_internal_date=self.now,
            folder_role="archive",
            identity_key=self.key,
        )

        self.assertEqual(request_one.dedupe_material, request_copy.dedupe_material)
        self.assertNotEqual(request_one.dedupe_material, request_two.dedupe_material)
        self.assertEqual(
            pair_sales_messages(request_one, reply_one).dedupe_material,
            pair_sales_messages(request_two, reply_two).dedupe_material,
        )

    def test_subject_only_and_non_direct_reference_links_never_pair(self) -> None:
        request = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"From: buyer@customer.example.test\r\n"
                b"To: agent@seller.example.test\r\n"
                b"Message-ID: <strict-request@customer.example.test>\r\n"
                b"Subject: Same synthetic subject\r\n\r\n"
            ),
            raw_body=b"Synthetic request.",
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )
        common = (
            b"From: agent@seller.example.test\r\n"
            b"To: buyer@customer.example.test\r\n"
            b"Message-ID: <strict-reply@seller.example.test>\r\n"
            b"Subject: Same synthetic subject\r\n"
        )
        subject_only = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=common + b"\r\n",
            raw_body=b"Synthetic reply.",
            trusted_internal_date=self.now + timedelta(minutes=1),
            folder_role="sent",
            identity_key=self.key,
        )
        reference_chain = evaluate_sales_message(
            policy=self.policy,
            raw_header=(
                common
                + b"References: <strict-request@customer.example.test> "
                b"<direct-other@customer.example.test>\r\n\r\n"
            ),
            raw_body=b"Synthetic reply.",
            trusted_internal_date=self.now + timedelta(minutes=1),
            folder_role="sent",
            identity_key=self.key,
        )

        self.assertIsNone(pair_sales_messages(request, subject_only))
        self.assertEqual(reference_chain.status, "candidate")
        self.assertEqual(len(reference_chain.candidate.reference_identities), 1)
        self.assertIsNone(pair_sales_messages(request, reference_chain.candidate))

    def test_customer_follow_up_does_not_project_a_reply_reference(self) -> None:
        follow_up = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"From: buyer@customer.example.test\r\n"
                b"To: agent@seller.example.test\r\n"
                b"Message-ID: <follow-up@customer.example.test>\r\n"
                b"In-Reply-To: <prior-reply@seller.example.test>\r\n\r\n"
            ),
            raw_body=b"Please also confirm the synthetic packing detail.",
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )

        self.assertEqual(follow_up.role, "customer_request")
        self.assertEqual(follow_up.reference_identities, ())

    def test_spoofed_non_allowlisted_and_unlinked_replies_never_pair(self) -> None:
        request = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"From: buyer@customer.example.test\r\n"
                b"To: agent@seller.example.test\r\n"
                b"Message-ID: <gate-request@customer.example.test>\r\n\r\n"
            ),
            raw_body=b"Synthetic request.",
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )
        reply_header = (
            b"To: buyer@customer.example.test\r\n"
            b"Message-ID: <gate-reply@seller.example.test>\r\n"
        )
        excluded_senders = (
            b"From: Agent <agent@seller.example.test.evil.example.test>\r\n",
            b"From: coworker@seller.example.test\r\n",
        )
        for sender in excluded_senders:
            with self.subTest(sender=sender):
                decision = evaluate_sales_message(
                    policy=self.policy,
                    raw_header=sender + reply_header + b"\r\n",
                    raw_body=b"Synthetic reply.",
                    trusted_internal_date=self.now + timedelta(minutes=1),
                    folder_role="sent",
                    identity_key=self.key,
                )
                self.assertEqual((decision.status, decision.candidate), ("non_sales", None))

        unlinked = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"From: agent@seller.example.test\r\n" + reply_header + b"\r\n"
            ),
            raw_body=b"Synthetic reply.",
            trusted_internal_date=self.now + timedelta(minutes=1),
            folder_role="sent",
            identity_key=self.key,
        )
        self.assertEqual(unlinked.reference_identities, ())
        self.assertIsNone(pair_sales_messages(request, unlinked))

    def test_allowlisted_from_is_not_a_reply_outside_the_sent_folder_role(self) -> None:
        header = (
            b"From: agent@seller.example.test\r\n"
            b"To: buyer@customer.example.test\r\n"
            b"Message-ID: <spoofed-reply@seller.example.test>\r\n"
            b"In-Reply-To: <request@customer.example.test>\r\n\r\n"
        )

        for folder_role in ("archive", "business_custom"):
            decision = evaluate_sales_message(
                policy=self.policy,
                raw_header=header,
                raw_body=b"Synthetic reply.",
                trusted_internal_date=self.now + timedelta(minutes=1),
                folder_role=folder_role,
                identity_key=self.key,
            )

            with self.subTest(folder_role=folder_role):
                self.assertEqual(
                    (decision.status, decision.candidate), ("non_sales", None)
                )

    def test_exact_quotation_material_ignores_customer_participants(self) -> None:
        def reply(customer: str, sequence: str):
            return parse_sales_message_candidate(
                policy=self.policy,
                raw_header=(
                    f"From: agent@seller.example.test\r\nTo: {customer}\r\n"
                    f"Message-ID: <reply-{sequence}@seller.example.test>\r\n"
                    f"In-Reply-To: <request-{sequence}@customer.example.test>\r\n\r\n"
                ).encode("ascii"),
                raw_body=b"The synthetic quotation is valid for fourteen days.",
                trusted_internal_date=self.now + timedelta(minutes=1),
                folder_role="sent",
                identity_key=self.key,
            )

        first = reply("buyer-one@customer-one.example.test", "one")
        second = reply("buyer-two@customer-two.example.test", "two")

        self.assertNotEqual(first.evidence_material, second.evidence_material)
        self.assertEqual(first.quotation_material, second.quotation_material)
        self.assertEqual(len(first.quotation_material), 32)

    def test_conflicting_direct_reply_headers_fail_closed(self) -> None:
        decision = evaluate_sales_message(
            policy=self.policy,
            raw_header=(
                b"From: agent@seller.example.test\r\n"
                b"To: buyer@customer.example.test\r\n"
                b"Message-ID: <conflict@seller.example.test>\r\n"
                b"In-Reply-To: <request-a@customer.example.test>\r\n"
                b"References: <request-b@customer.example.test>\r\n\r\n"
            ),
            raw_body=b"Synthetic reply.",
            trusted_internal_date=self.now,
            folder_role="sent",
            identity_key=self.key,
        )

        self.assertEqual((decision.status, decision.candidate), ("ambiguous", None))

    def test_decision_distinguishes_non_sales_from_ambiguous_input(self) -> None:
        def decide(header: bytes):
            return evaluate_sales_message(
                policy=self.policy, raw_header=header, raw_body=b"Synthetic body.",
                trusted_internal_date=self.now, folder_role="archive",
                identity_key=self.key,
            )

        non_sales = decide(
            b"From: coworker@seller.example.test\r\n"
            b"To: agent@seller.example.test\r\n"
            b"Message-ID: <internal@seller.example.test>\r\n\r\n"
        )
        ambiguous = decide(
            b"From: buyer@customer.example.test\r\n"
            b"To: agent@seller.example.test\r\n\r\n"
        )

        self.assertEqual((non_sales.status, ambiguous.status), ("non_sales", "ambiguous"))
        self.assertEqual(repr(non_sales), "SalesMessageDecision(status='non_sales')")
        with self.assertRaises(ValueError):
            SalesMessageDecision("candidate", None)


if __name__ == "__main__":
    unittest.main()
