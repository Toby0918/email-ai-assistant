"""Tests for bounded, ephemeral attachment text sent to remote models."""

from __future__ import annotations

import unittest

from backend.email_agent.attachment_model_context import (
    MAX_MODEL_CHARACTERS_PER_ATTACHMENT,
    MAX_MODEL_CHARACTERS_TOTAL,
    AttachmentModelCandidate,
    build_attachment_model_context,
    sanitize_remote_text,
)


class AttachmentModelContextTests(unittest.TestCase):
    def test_remote_text_removes_privacy_and_active_content_canaries(self) -> None:
        cases = (
            ("https", "Visit https://private.example.test/a?q=secret#fragment", "private.example"),
            ("http", "Visit http://private.example.test/a", "private.example"),
            ("www", "Visit www.private.example.test/a", "private.example"),
            ("scheme-relative", "Visit //private.example.test/a", "private.example"),
            ("mailto", "Use mailto:private@example.test", "private@example.test"),
            ("ftp", "Use ftp://private.example.test/a", "private.example"),
            ("file", "Use file:///C:/private/quote.xlsx", "private"),
            ("sftp", "Use sftp://private.example.test/root", "private.example"),
            ("data", "Use data:text/plain,PRIVATE-DATA", "PRIVATE-DATA"),
            ("custom scheme", "Use acme+private://host.example.test/item", "host.example"),
            ("opaque custom scheme", "Use custom:PRIVATE-OPAQUE", "PRIVATE-OPAQUE"),
            ("bare domain", "Portal private.example.test/a?q=secret#fragment", "private.example"),
            ("userinfo", "Visit https://private-user:private-pass@example.test/a", "private-pass"),
            ("authorization", "Authorization: Bearer PRIVATE-AUTH", "PRIVATE-AUTH"),
            ("cookie", "Cookie: session_id=PRIVATE-COOKIE", "PRIVATE-COOKIE"),
            ("password", "password=PRIVATE-PASSWORD", "PRIVATE-PASSWORD"),
            ("api key", "api_key: PRIVATE-API-KEY", "PRIVATE-API-KEY"),
            ("access token", "access_token=PRIVATE-ACCESS-TOKEN", "PRIVATE-ACCESS-TOKEN"),
            ("session", "session: PRIVATE-SESSION", "PRIVATE-SESSION"),
            ("bearer", "Bearer PRIVATE-BEARER", "PRIVATE-BEARER"),
            ("basic", "Basic UHJpdmF0ZVVzZXI6UHJpdmF0ZVBhc3M=", "UHJpdmF0"),
            (
                "jwt",
                "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJwcml2YXRlIn0.c2lnbmF0dXJlMTIzNDU2",
                "eyJhbGci",
            ),
            ("base64", "QWxhZGRpbjpPcGVuU2VzYW1lMTIzNDU2Nzg5MA==", "QWxhZGRp"),
            ("windows path", r"C:\private\quote.xlsx", "private"),
            ("unc path", r"\\fileserver\private\quote.xlsx", "fileserver"),
            ("posix path", "/home/private/quote.xlsx", "/home/private"),
            ("dot relative path", "../private/quote.xlsx", "private/quote"),
            ("relative path", "private/folder/quote.xlsx", "private/folder"),
            ("script", "<script>PRIVATE-SCRIPT</script>", "PRIVATE-SCRIPT"),
            ("macro", "VBA AutoOpen PRIVATE-MACRO", "AutoOpen"),
            ("active content", "ActiveX Workbook_Open PRIVATE-ACTIVE", "ActiveX"),
            ("controls", "safe\x00PRIVATE-CONTROL\x7f", "\x00"),
        )

        for label, raw, forbidden in cases:
            with self.subTest(label=label):
                sanitized = sanitize_remote_text(raw, max_characters=6_000)
                self.assertNotIn(forbidden.casefold(), sanitized.text.casefold())

    def test_remote_text_preserves_business_facts_and_ordinary_identity(self) -> None:
        raw = (
            "Alice Chen | PO 1013970520 | RFQ RFQ-2026-001 | "
            "Invoice INV-7000001 | Part PN-ABC-42 | due 2026-07-20 | "
            "qty 24 pcs | size 12 x 30 mm | USD 1,250 | alice@example.com"
        )

        sanitized = sanitize_remote_text(raw, max_characters=6_000)

        for expected in (
            "Alice Chen",
            "PO 1013970520",
            "RFQ RFQ-2026-001",
            "Invoice INV-7000001",
            "Part PN-ABC-42",
            "due 2026-07-20",
            "qty 24 pcs",
            "size 12 x 30 mm",
            "USD 1,250",
            "alice@example.com",
            "|",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sanitized.text)
        self.assertFalse(sanitized.link_was_present)
        self.assertFalse(sanitized.truncated)

    def test_remote_text_sanitizes_before_final_truncation(self) -> None:
        private_url = "https://private.example.test/" + ("x" * 8_000)

        sanitized = sanitize_remote_text(
            f"{private_url} PO 1013970520 due 2026-07-20",
            max_characters=80,
        )

        self.assertEqual(sanitized.text, "PO 1013970520 due 2026-07-20")
        self.assertTrue(sanitized.link_was_present)
        self.assertFalse(sanitized.truncated)

        truncated = sanitize_remote_text(
            f"{private_url} " + ("ordinary business text " * 20),
            max_characters=60,
        )
        self.assertEqual(len(truncated.text), 60)
        self.assertTrue(truncated.link_was_present)
        self.assertTrue(truncated.truncated)

    def test_link_marker_is_optional_and_attachment_context_omits_it(self) -> None:
        raw = "before https://private.example.test/a after"

        marked = sanitize_remote_text(raw, max_characters=6_000, link_marker="[link]")
        unmarked = sanitize_remote_text(raw, max_characters=6_000)
        context = build_attachment_model_context((AttachmentModelCandidate("attachment:0", raw),))

        self.assertEqual(marked.text, "before [link] after")
        self.assertTrue(marked.link_was_present)
        self.assertEqual(unmarked.text, "before after")
        self.assertEqual(context[0].text, "before after")
        self.assertNotIn("[link]", context[0].text)
        self.assertTrue(context[0].link_was_present)

    def test_attachment_context_obeys_per_item_total_limits_and_input_order(self) -> None:
        raw = "ordinary business detail " * 400
        candidates = tuple(
            AttachmentModelCandidate(f"attachment:{index}", raw)
            for index in range(5)
        )

        items = build_attachment_model_context(candidates)

        self.assertEqual(
            tuple(item.source_id for item in items),
            ("attachment:0", "attachment:1", "attachment:2", "attachment:3"),
        )
        self.assertTrue(
            all(len(item.text) <= MAX_MODEL_CHARACTERS_PER_ATTACHMENT for item in items)
        )
        self.assertLessEqual(
            sum(len(item.text) for item in items),
            MAX_MODEL_CHARACTERS_TOTAL,
        )
        self.assertEqual(sum(len(item.text) for item in items), 24_000)
        self.assertTrue(all(item.truncated for item in items))

    def test_empty_sanitized_candidates_are_not_accepted(self) -> None:
        candidates = (
            AttachmentModelCandidate("attachment:0", "https://private.example.test/a"),
            AttachmentModelCandidate("attachment:1", "PO 1013970520"),
        )

        items = build_attachment_model_context(candidates)

        self.assertEqual(tuple(item.source_id for item in items), ("attachment:1",))
        self.assertEqual(items[0].text, "PO 1013970520")


if __name__ == "__main__":
    unittest.main()
