"""Shared synthetic fixtures for governed sales-message policy tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.mailbox_ingest.sales_message_policy import (
    parse_sales_corpus_policy,
)


def policy_payload() -> dict[str, object]:
    return {
        "schema_version": 1,
        "company_domain": "seller.example.test",
        "salesperson_allowlist": ["agent@seller.example.test"],
    }


class SalesMessageCandidateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = parse_sales_corpus_policy(policy_payload())
        self.now = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
        self.key = b"K" * 32
