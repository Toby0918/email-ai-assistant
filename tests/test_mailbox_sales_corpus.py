"""Pure synthetic sales-corpus policy and message semantics."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from backend.mailbox_ingest.sales_message_policy import (
    evaluate_sales_message,
    pair_sales_messages,
    parse_sales_message_candidate,
    SalesMessageDecision,
    SalesMessagePolicyError,
    parse_sales_corpus_policy,
)


def policy_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "company_domain": "seller.example.test",
        "salesperson_allowlist": ["agent@seller.example.test"],
    }


class SalesCorpusPolicyTests(unittest.TestCase):
    def test_strict_policy_is_redacted_and_has_stable_private_material(self) -> None:
        first = parse_sales_corpus_policy(policy_payload())
        reordered = policy_payload()
        reordered["company_domain"] = "SELLER.EXAMPLE.TEST"
        reordered["salesperson_allowlist"] = ["AGENT@SELLER.EXAMPLE.TEST"]

        self.assertEqual(first.fingerprint_material(), parse_sales_corpus_policy(reordered).fingerprint_material())
        self.assertEqual(repr(first), "SalesCorpusPolicy(<redacted>)")
        self.assertNotIn("seller", repr(first))

    def test_policy_rejects_unknown_fields_wildcards_and_normalized_duplicates(self) -> None:
        cases: list[dict[str, object]] = []
        unknown = policy_payload()
        unknown["path"] = "C:/private"
        cases.append(unknown)
        wildcard = policy_payload()
        wildcard["company_domain"] = "*.example.test"
        cases.append(wildcard)
        duplicate = policy_payload()
        duplicate["salesperson_allowlist"] = [
            "agent@seller.example.test",
            "AGENT@SELLER.EXAMPLE.TEST",
        ]
        cases.append(duplicate)

        for payload in cases:
            with self.subTest(payload_keys=tuple(payload)), self.assertRaises(SalesMessagePolicyError) as caught:
                parse_sales_corpus_policy(payload)
            self.assertEqual(caught.exception.code, "sales_policy_invalid")
            self.assertNotIn("seller", repr(caught.exception))

    def test_policy_rejects_non_company_allowlist_and_hidden_controls(self) -> None:
        payload = policy_payload()
        payload["salesperson_allowlist"] = ["agent@other.example.test\u202e"]

        with self.assertRaises(SalesMessagePolicyError) as caught:
            parse_sales_corpus_policy(payload)

        self.assertEqual(caught.exception.code, "sales_policy_invalid")
        self.assertNotIn("synthetic", repr(caught.exception))


class SalesMessageCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = parse_sales_corpus_policy(policy_payload())
        self.now = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
        self.key = b"K" * 32

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
