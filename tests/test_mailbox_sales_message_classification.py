"""Synthetic sales-message classification and learning-projection tests."""

from __future__ import annotations

import unittest
from datetime import timedelta

from backend.mailbox_ingest.sales_message_policy import (
    evaluate_sales_message,
    pair_sales_messages,
    parse_sales_message_candidate,
)
from tests import mailbox_sales_corpus_support as corpus_support


class SalesMessageCandidateTests(
    corpus_support.SalesMessageCandidateTestCase,
):
    def test_external_request_pairs_with_exact_allowlisted_later_reply(self) -> None:
        request_decision = evaluate_sales_message(
            policy=self.policy,
            raw_header=(
                b"From: Buyer <buyer@customer.example.test>\r\n"
                b"To: Agent <agent@seller.example.test>\r\n"
                b"Message-ID: <request-1@customer.example.test>\r\n"
                b"Subject: Synthetic request\r\n\r\n"
            ),
            raw_body=b"Please quote 40 synthetic valves.",
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )
        request = request_decision.candidate
        reply = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"From: Agent <agent@seller.example.test>\r\n"
                b"To: Buyer <buyer@customer.example.test>\r\n"
                b"Message-ID: <reply-1@seller.example.test>\r\n"
                b"In-Reply-To: <request-1@customer.example.test>\r\n"
                b"References: <request-1@customer.example.test>\r\n"
                b"Subject: Re: Synthetic request\r\n\r\n"
            ),
            raw_body=b"The synthetic lead-time range is four to six weeks.",
            trusted_internal_date=self.now + timedelta(minutes=5),
            folder_role="sent",
            identity_key=self.key,
        )

        pair = pair_sales_messages(request, reply)

        self.assertEqual(request_decision.status, "candidate")
        self.assertEqual((request.role, reply.role), ("customer_request", "sales_reply"))
        self.assertIsNotNone(pair)
        self.assertEqual(len(request.dedupe_material), 32)
        self.assertEqual(len(pair.dedupe_material), 32)
        rendered = repr((request, reply, pair))
        for private in ("buyer@", "agent@", "request-1", "lead-time"):
            self.assertNotIn(private, rendered)

    def test_message_id_domain_is_normalized_but_local_part_is_exact(self) -> None:
        request = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=(
                b"From: buyer@customer.example.test\r\n"
                b"To: agent@seller.example.test\r\n"
                b"Message-ID: <CaseSensitive@CUSTOMER.EXAMPLE.TEST>\r\n\r\n"
            ),
            raw_body=b"Please quote the synthetic valve.",
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )

        def reply(reference: str, sequence: str):
            return parse_sales_message_candidate(
                policy=self.policy,
                raw_header=(
                    b"From: agent@seller.example.test\r\n"
                    b"To: buyer@customer.example.test\r\n"
                    + f"Message-ID: <reply-{sequence}@seller.example.test>\r\n"
                    f"In-Reply-To: <{reference}>\r\n\r\n".encode("ascii")
                ),
                raw_body=b"Here is the synthetic quotation.",
                trusted_internal_date=self.now + timedelta(minutes=1),
                folder_role="sent",
                identity_key=self.key,
            )

        domain_case_only = reply(
            "CaseSensitive@customer.example.test", "domain-case"
        )
        local_case_changed = reply(
            "casesensitive@customer.example.test", "local-case"
        )

        self.assertIsNotNone(pair_sales_messages(request, domain_case_only))
        self.assertIsNone(pair_sales_messages(request, local_case_changed))

    def test_automated_list_bulk_and_exact_notification_markers_are_excluded(self) -> None:
        variants = (
            b"Auto-Submitted: auto-generated\r\n",
            b"List-ID: <synthetic.list.example.test>\r\n",
            b"Precedence: bulk\r\n",
            b"X-Auto-Response-Suppress: All\r\n",
            b"Subject: Automatic notification\r\n",
        )
        for extra in variants:
            header = (
                b"From: buyer@customer.example.test\r\n"
                b"To: agent@seller.example.test\r\n"
                b"Message-ID: <automated-1@customer.example.test>\r\n"
                + extra
                + b"\r\n"
            )
            with self.subTest(extra=extra):
                decision = evaluate_sales_message(
                    policy=self.policy,
                    raw_header=header,
                    raw_body=b"Synthetic notification body.",
                    trusted_internal_date=self.now,
                    folder_role="inbox",
                    identity_key=self.key,
                )
                self.assertEqual((decision.status, decision.candidate), ("automated", None))

    def test_learning_projection_removes_noise_and_rejects_pure_forward(self) -> None:
        header = (
            b"From: buyer@customer.example.test\r\n"
            b"To: agent@seller.example.test\r\n"
            b"Message-ID: <clean-1@customer.example.test>\r\n\r\n"
        )
        candidate = parse_sales_message_candidate(
            policy=self.policy,
            raw_header=header,
            raw_body=(
                b"Please quote the synthetic valve.\r\n"
                b"> prior private request\r\n"
                b"--\r\n"
                b"Confidentiality notice"
            ),
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )
        pure_forward = evaluate_sales_message(
            policy=self.policy,
            raw_header=header.replace(b"clean-1", b"forward-1"),
            raw_body=(
                b"----- Forwarded message -----\r\n"
                b"From: prior@customer.example.test\r\n"
                b"Private forwarded content"
            ),
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )

        self.assertEqual(candidate.learning_projection(), "Please quote the synthetic valve.")
        self.assertEqual((pure_forward.status, pure_forward.candidate), ("forward", None))
        self.assertNotIn("prior private", repr(candidate))

    def test_learning_projection_stops_before_multiline_quoted_headers(self) -> None:
        variants = (
            (
                "outlook",
                "From: buyer@customer.example.test\n"
                "Sent: Monday, July 1, 2026 9:00 AM\n"
                "To: agent@seller.example.test\n"
                "Subject: Prior synthetic request\n"
                "Prior private request",
            ),
            (
                "chinese",
                "发件人：buyer@customer.example.test\n"
                "发送时间：2026年7月1日 9:00\n"
                "收件人：agent@seller.example.test\n"
                "主题：之前的合成请求\n"
                "之前的私有请求",
            ),
        )
        for label, quoted in variants:
            with self.subTest(label=label):
                candidate = parse_sales_message_candidate(
                    policy=self.policy,
                    raw_header=(
                        b"From: agent@seller.example.test\r\n"
                        b"To: buyer@customer.example.test\r\n"
                        + f"Message-ID: <quoted-{label}@seller.example.test>\r\n"
                        .encode("ascii")
                        + b"\r\n"
                    ),
                    raw_body=("New synthetic answer.\n" + quoted).encode("utf-8"),
                    trusted_internal_date=self.now,
                    folder_role="sent",
                    identity_key=self.key,
                )

                self.assertEqual(
                    candidate.learning_projection(), "New synthetic answer."
                )

    def test_pure_multiline_quoted_headers_are_excluded(self) -> None:
        variants = (
            (
                "outlook",
                "From: buyer@customer.example.test\n"
                "Sent: Monday, July 1, 2026 9:00 AM\n"
                "To: agent@seller.example.test\n"
                "Cc: observer@customer.example.test\n"
                "Subject: Prior synthetic request\n"
                "Prior private request",
            ),
            (
                "chinese",
                "发件人：buyer@customer.example.test\n"
                "发送时间：2026年7月1日 9:00\n"
                "收件人：agent@seller.example.test\n"
                "抄送：observer@customer.example.test\n"
                "主题：之前的合成请求\n"
                "之前的私有请求",
            ),
        )
        for label, body in variants:
            with self.subTest(label=label):
                decision = evaluate_sales_message(
                    policy=self.policy,
                    raw_header=(
                        b"From: buyer@customer.example.test\r\n"
                        b"To: agent@seller.example.test\r\n"
                        + f"Message-ID: <pure-quoted-{label}@customer.example.test>\r\n"
                        .encode("ascii")
                        + b"\r\n"
                    ),
                    raw_body=body.encode("utf-8"),
                    trusted_internal_date=self.now,
                    folder_role="inbox",
                    identity_key=self.key,
                )

                self.assertEqual((decision.status, decision.candidate), ("forward", None))

    def test_common_confidentiality_notice_alone_is_excluded(self) -> None:
        decision = evaluate_sales_message(
            policy=self.policy,
            raw_header=(
                b"From: buyer@customer.example.test\r\n"
                b"To: agent@seller.example.test\r\n"
                b"Message-ID: <notice-only@customer.example.test>\r\n\r\n"
            ),
            raw_body=b"CONFIDENTIALITY NOTICE: This message is confidential.",
            trusted_internal_date=self.now,
            folder_role="inbox",
            identity_key=self.key,
        )

        self.assertEqual((decision.status, decision.candidate), ("forward", None))


if __name__ == "__main__":
    unittest.main()
