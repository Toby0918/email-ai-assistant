"""Pure synthetic sales-corpus policy contracts."""

from __future__ import annotations

import unittest

from backend.mailbox_ingest.sales_message_policy import (
    SalesMessagePolicyError,
    parse_sales_corpus_policy,
)
from tests.mailbox_sales_corpus_support import policy_payload


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

    def test_policy_rejects_non_integer_schema_versions(self) -> None:
        for version in (True, 1.0):
            payload = policy_payload()
            payload["schema_version"] = version

            with self.subTest(version=version), self.assertRaises(
                SalesMessagePolicyError
            ):
                parse_sales_corpus_policy(payload)


if __name__ == "__main__":
    unittest.main()
