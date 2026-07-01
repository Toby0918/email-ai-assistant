"""Business tests for email body cleaning."""

from __future__ import annotations

import unittest

from backend.email_agent.email_cleaner import clean_email_body


class EmailCleanerTests(unittest.TestCase):
    def test_html_body_is_converted_to_readable_text(self) -> None:
        # Script and style blocks should not survive into prompt-ready text.
        html = "<html><body><style>.x{}</style><p>Hello&nbsp;<b>Toby</b></p><script>x()</script></body></html>"

        result = clean_email_body(body_html=html)

        self.assertEqual(result, "Hello Toby")

    def test_plain_text_fallback_is_normalized(self) -> None:
        result = clean_email_body(body_text="  Hello\r\n\r\n\r\nWorld  ")

        self.assertEqual(result, "Hello\n\nWorld")

    def test_html_blockquote_history_is_removed(self) -> None:
        html = "<p>Please confirm shipment ETA.</p><blockquote>Invoice payment overdue.</blockquote>"

        result = clean_email_body(body_html=html)

        self.assertEqual(result, "Please confirm shipment ETA.")

    def test_plain_text_original_message_history_is_removed(self) -> None:
        body = "Please confirm delivery.\n\n-----Original Message-----\nInvoice payment overdue."

        result = clean_email_body(body_text=body)

        self.assertEqual(result, "Please confirm delivery.")

    def test_empty_body_returns_empty_string(self) -> None:
        self.assertEqual(clean_email_body(), "")


if __name__ == "__main__":
    unittest.main()
