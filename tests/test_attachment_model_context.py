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
        self.assertLessEqual(len(truncated.text), 60)
        self.assertEqual(truncated.text.split()[-1], "ordinary")
        self.assertTrue(truncated.link_was_present)
        self.assertTrue(truncated.truncated)

    def test_remote_text_truncation_never_emits_partial_sensitive_tokens(self) -> None:
        limit = 80
        cases = (
            ("email", "alice@acme.example"),
            ("domain", "private.acme.example"),
            ("order", "PO-ABCD1234"),
            ("transaction", "TXN-ABCD1234"),
            ("path", r"C:\private\records\quote.xlsx"),
            ("phone", "+1 202 555 0123"),
        )
        for label, token in cases:
            for offset in (-1, 0, 1):
                token_end = limit + offset
                filler_length = token_end - len("safe ") - 1 - len(token)
                raw = (
                    "safe " + ("甲" * filler_length) + " " + token
                    + " trailing " + ("tail " * 30)
                )

                with self.subTest(label=label, offset=offset):
                    sanitized = sanitize_remote_text(raw, max_characters=limit)
                    self.assertTrue(sanitized.truncated)
                    self.assertLessEqual(len(sanitized.text), limit)
                    if token not in sanitized.text:
                        for prefix_length in range(4, len(token)):
                            fragment = token[:prefix_length].rstrip()
                            if len(fragment) >= 4:
                                self.assertNotIn(fragment, sanitized.text)

    def test_remote_text_drops_unbroken_field_when_no_safe_boundary_exists(self) -> None:
        raw = ("x" * 1_988) + "alice@acme.example"

        sanitized = sanitize_remote_text(raw, max_characters=2_000)

        self.assertTrue(sanitized.truncated)
        self.assertEqual(sanitized.text, "")

    def test_attachment_context_uses_token_safe_truncation_at_its_real_limit(self) -> None:
        token = "alice@acme.example"
        token_end = MAX_MODEL_CHARACTERS_PER_ATTACHMENT + 1
        filler_length = token_end - len("safe ") - 1 - len(token)
        raw = (
            "safe " + ("甲" * filler_length) + " " + token
            + " trailing " + ("tail " * 30)
        )

        context = build_attachment_model_context(
            (AttachmentModelCandidate("attachment:0", raw),)
        )

        self.assertEqual(len(context), 1)
        self.assertTrue(context[0].truncated)
        self.assertNotIn(token[:-1], context[0].text)
        self.assertLessEqual(
            len(context[0].text),
            MAX_MODEL_CHARACTERS_PER_ATTACHMENT,
        )

    def test_normal_long_remote_text_remains_nonempty_and_bounded(self) -> None:
        sanitized = sanitize_remote_text("ordinary word " * 100, max_characters=80)

        self.assertTrue(sanitized.truncated)
        self.assertTrue(sanitized.text)
        self.assertLessEqual(len(sanitized.text), 80)
        self.assertEqual(sanitized.text.split()[-1], "ordinary")

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
        self.assertTrue(all(item.text.endswith("detail") for item in items))
        self.assertTrue(all(item.truncated for item in items))

    def test_empty_sanitized_candidates_are_not_accepted(self) -> None:
        candidates = (
            AttachmentModelCandidate("attachment:0", "https://private.example.test/a"),
            AttachmentModelCandidate("attachment:1", "PO 1013970520"),
        )

        items = build_attachment_model_context(candidates)

        self.assertEqual(tuple(item.source_id for item in items), ("attachment:1",))
        self.assertEqual(items[0].text, "PO 1013970520")

    def test_credential_fields_remove_full_values_through_strong_boundaries(self) -> None:
        cases = (
            (
                "multi-cookie",
                "Cookie: session=COOKIE_ONE; csrftoken=COOKIE_TWO; auth=COOKIE_THREE | PO 1013970520",
                ("COOKIE_ONE", "COOKIE_TWO", "COOKIE_THREE", "csrftoken", "auth="),
            ),
            (
                "multiword password",
                "password: PRIVATE ONE TWO | PO 1013970520",
                ("PRIVATE", "ONE TWO"),
            ),
            ("generic key", "key=PRIVATE-KEY | PO 1013970520", ("PRIVATE-KEY",)),
            (
                "client secret",
                "client_secret=PRIVATE-CLIENT VALUE | PO 1013970520",
                ("PRIVATE-CLIENT", "VALUE"),
            ),
            (
                "private key",
                "private_key: PRIVATE KEY VALUE | PO 1013970520",
                ("PRIVATE KEY VALUE",),
            ),
            (
                "underscored session",
                "session_id=PRIVATE SESSION VALUE | PO 1013970520",
                ("PRIVATE SESSION VALUE",),
            ),
            (
                "generic token",
                "token=PRIVATE TOKEN VALUE | PO 1013970520",
                ("PRIVATE TOKEN VALUE",),
            ),
            ("short bearer", "Bearer abc | PO 1013970520", ("Bearer", "abc")),
            ("short basic", "Basic xyz | PO 1013970520", ("Basic", "xyz")),
            (
                "newline boundary",
                "password: PRIVATE ONE TWO\nPO 1013970520",
                ("PRIVATE", "ONE TWO"),
            ),
            (
                "base64url",
                "QWxhZGRpbjpPcGVuU2VzYW1lX3ByaXZhdGVfMTIzNDU2Nzg5 | PO 1013970520",
                ("QWxhZGRp", "X3ByaXZhdGVf"),
            ),
            (
                "long base64",
                "QWxhZGRpbjpPcGVuU2VzYW1lMTIzNDU2Nzg5MDEyMzQ1Njc4OTA= | PO 1013970520",
                ("QWxhZGRp",),
            ),
        )

        for label, raw, forbidden_values in cases:
            with self.subTest(label=label):
                sanitized = sanitize_remote_text(raw, max_characters=6_000)
                expected_text = "PO 1013970520" if "\n" in raw else "| PO 1013970520"
                self.assertEqual(sanitized.text, expected_text)
                for forbidden in forbidden_values:
                    self.assertNotIn(forbidden.casefold(), sanitized.text.casefold())

    def test_natural_language_secret_labels_are_removed_without_benign_false_positives(self) -> None:
        secrets = (
            "Password is hunter2-secret",
            "API key is ds-secret-12345",
            "session id SESSIONSECRET42",
            'password "quoted-secret"',
            "token 'single-quoted-secret'",
        )
        for raw in secrets:
            with self.subTest(raw=raw):
                self.assertEqual(sanitize_remote_text(raw, 6_000).text, "")

        benign = (
            "Password reset status is complete.",
            "API key rotation policy is under review.",
            "Token expiry is tomorrow.",
            "Cookie policy needs review.",
            "Session ID expiry is 2026-07-20.",
        )
        for raw in benign:
            with self.subTest(raw=raw):
                self.assertEqual(sanitize_remote_text(raw, 6_000).text, raw)

    def test_generic_bare_hosts_and_ip_urls_are_removed_and_flagged(self) -> None:
        cases = (
            (
                "unknown tld",
                "private.example.xyz/path?q=DOMAIN_SECRET#fragment",
                ("private.example.xyz", "DOMAIN_SECRET", "fragment"),
            ),
            (
                "unknown tld userinfo",
                "private-user:private-pass@" + "private.example.xyz/path?q=USER_SECRET#fragment",
                ("private-user", "private-pass", "private.example.xyz", "USER_SECRET"),
            ),
            (
                "bare ipv4",
                "192.0.2.10:8443/path?q=IP_SECRET#fragment",
                ("192.0.2.10", "IP_SECRET", "fragment"),
            ),
            (
                "ipv4 userinfo",
                "private-user:private-pass@192.0.2.10/path?q=IP_USER_SECRET#fragment",
                ("private-user", "private-pass", "192.0.2.10", "IP_USER_SECRET"),
            ),
        )

        for label, link, forbidden_values in cases:
            with self.subTest(label=label):
                sanitized = sanitize_remote_text(
                    f"{link} | buyer@ordinary-mail.example | PO 1013970520",
                    max_characters=6_000,
                )
                self.assertTrue(sanitized.link_was_present)
                self.assertIn("buyer@ordinary-mail.example", sanitized.text)
                self.assertIn("PO 1013970520", sanitized.text)
                for forbidden in forbidden_values:
                    self.assertNotIn(forbidden.casefold(), sanitized.text.casefold())

        email_only = sanitize_remote_text("buyer@private.example", max_characters=6_000)
        self.assertEqual(email_only.text, "buyer@private.example")
        self.assertFalse(email_only.link_was_present)

    def test_active_content_removes_marker_and_payload_through_strong_boundary(self) -> None:
        cases = (
            ("script", "<script>PRIVATE-SCRIPT</script>", ("script", "PRIVATE-SCRIPT")),
            ("object", "<object data=x>PRIVATE-OBJECT</object>", ("object", "PRIVATE-OBJECT")),
            ("iframe", "<iframe>PRIVATE-IFRAME</iframe>", ("iframe", "PRIVATE-IFRAME")),
            ("embed", "<embed>PRIVATE-EMBED</embed>", ("embed", "PRIVATE-EMBED")),
            (
                "powershell",
                "powershell -EncodedCommand PRIVATE-SHELL",
                ("powershell", "EncodedCommand", "PRIVATE-SHELL"),
            ),
            ("vba", "VBA AutoOpen PRIVATE-MACRO", ("VBA", "AutoOpen", "PRIVATE-MACRO")),
            ("activex", "ActiveX PRIVATE-ACTIVE", ("ActiveX", "PRIVATE-ACTIVE")),
        )

        for label, active_value, forbidden_values in cases:
            with self.subTest(label=label):
                sanitized = sanitize_remote_text(
                    f"{active_value} | PO 1013970520",
                    max_characters=6_000,
                )
                self.assertEqual(sanitized.text, "| PO 1013970520")
                for forbidden in forbidden_values:
                    self.assertNotIn(forbidden.casefold(), sanitized.text.casefold())

    def test_explicit_local_paths_include_single_segment_rooted_paths(self) -> None:
        cases = (
            ("rooted", "/secret", "/secret"),
            ("home", "~/secret", "~/secret"),
            ("dot relative", "./secret", "./secret"),
            ("parent relative", "../secret", "../secret"),
            ("relative file", "private/quote.xlsx", "private/quote.xlsx"),
            ("multi-segment", "private/folder/quote", "private/folder/quote"),
        )

        for label, path, forbidden in cases:
            with self.subTest(label=label):
                sanitized = sanitize_remote_text(
                    f"{path} | PO 1013970520",
                    max_characters=6_000,
                )
                self.assertNotIn(forbidden, sanitized.text)
                self.assertIn("PO 1013970520", sanitized.text)

    def test_slash_bearing_business_data_is_not_classified_as_a_path(self) -> None:
        raw = (
            "Part PN/ABC-42 | Currency USD/EUR | A/B table relation | "
            "due 2026/07/20 | quantity 24/48 units"
        )

        sanitized = sanitize_remote_text(raw, max_characters=6_000)

        for expected in (
            "PN/ABC-42",
            "USD/EUR",
            "A/B table relation",
            "2026/07/20",
            "24/48 units",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, sanitized.text)

    def test_all_uppercase_base64_is_removed_without_losing_business_ids(self) -> None:
        raw = (
            "QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB | "
            "PO 1013970520 | Part PN-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456"
        )

        sanitized = sanitize_remote_text(raw, max_characters=6_000)

        self.assertNotIn("QUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFBQUFB", sanitized.text)
        self.assertIn("PO 1013970520", sanitized.text)
        self.assertIn("Part PN-ABCDEFGHIJKLMNOPQRSTUVWXYZ123456", sanitized.text)

    def test_simple_relative_paths_are_removed_with_narrow_slash_business_allowlists(self) -> None:
        path_cases = (
            "private/quote",
            "private/folder",
            "team/private/quote",
            r"private\quote",
        )
        for path in path_cases:
            with self.subTest(path=path):
                sanitized = sanitize_remote_text(
                    f"{path} | PO 1013970520",
                    max_characters=6_000,
                )
                self.assertNotIn(path, sanitized.text)
                self.assertIn("PO 1013970520", sanitized.text)

        business_cases = (
            "PN/ABC-42",
            "USD/EUR",
            "A/B/C relation",
            "2026/07/20",
            "24/48 units",
        )
        for value in business_cases:
            with self.subTest(value=value):
                sanitized = sanitize_remote_text(value, max_characters=6_000)
                self.assertEqual(sanitized.text, value)

    def test_unclosed_active_tags_remove_payload_to_strong_boundary(self) -> None:
        for tag in ("script", "object", "iframe", "embed"):
            with self.subTest(tag=tag, boundary="pipe"):
                sanitized = sanitize_remote_text(
                    f"<{tag}>PRIVATE-{tag.upper()} | PO 1013970520",
                    max_characters=6_000,
                )
                self.assertEqual(sanitized.text, "| PO 1013970520")

            with self.subTest(tag=tag, boundary="newline"):
                sanitized = sanitize_remote_text(
                    f"<{tag}>PRIVATE-{tag.upper()}\nPO 1013970520",
                    max_characters=6_000,
                )
                self.assertEqual(sanitized.text, "PO 1013970520")

            with self.subTest(tag=tag, boundary="end"):
                sanitized = sanitize_remote_text(
                    f"<{tag}>PRIVATE-{tag.upper()}",
                    max_characters=6_000,
                )
                self.assertEqual(sanitized.text, "")

    def test_labeled_secrets_preserve_only_explicit_business_suffixes_after_sentence_boundaries(self) -> None:
        preserved_cases = (
            (
                "password: PRIVATE. PO 1013970520 due 2026-07-20",
                "PO 1013970520 due 2026-07-20",
            ),
            ("password: PRIVATE! RFQ RFQ-2026-001", "RFQ RFQ-2026-001"),
            ("token=PRIVATE? invoice INV-7000001", "invoice INV-7000001"),
            ("client_secret=PRIVATE. Part PN-ABC-42", "Part PN-ABC-42"),
            ("key=PRIVATE. qty 24 pcs", "qty 24 pcs"),
            ("session=PRIVATE. deadline 2026-07-20", "deadline 2026-07-20"),
            ("password: PRIVATE. USD 1,250", "USD 1,250"),
            ("password: PRIVATE. 2026-07-20 delivery", "2026-07-20 delivery"),
        )
        for raw, expected in preserved_cases:
            with self.subTest(raw=raw):
                sanitized = sanitize_remote_text(raw, max_characters=6_000)
                self.assertEqual(sanitized.text, expected)
                self.assertNotIn("PRIVATE", sanitized.text)

        consumed_cases = (
            "password: PRIVATE ONE TWO. ordinary follow-up",
            "Cookie: session=COOKIE_ONE; auth=COOKIE_TWO. ordinary follow-up",
            "token=PRIVATE? ordinary words PO 1013970520",
        )
        for raw in consumed_cases:
            with self.subTest(raw=raw):
                self.assertEqual(sanitize_remote_text(raw, 6_000).text, "")


if __name__ == "__main__":
    unittest.main()
