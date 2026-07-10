"""Business tests for email body cleaning."""

from __future__ import annotations

import unittest

from backend.email_agent.email_cleaner import clean_email_body, clean_thread_segment_text


class _TrackingText(str):
    def __new__(cls, value: str) -> "_TrackingText":
        instance = super().__new__(cls, value)
        instance.slice_stops: list[int | None] = []
        return instance

    def __getitem__(self, key: object) -> str:
        if isinstance(key, slice):
            self.slice_stops.append(key.stop)
        return super().__getitem__(key)


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

    def test_thread_segment_text_removes_signature_banner_and_bounds_content(self) -> None:
        body = (
            "[EXTERNAL EMAIL] Please provide a quote.\n"
            "-- \n"
            "Synthetic Sender\n"
            "Quoted content must not remain."
        )

        result = clean_thread_segment_text(body_text=body, max_chars=12)

        self.assertEqual(result, "Please provi")

    def test_thread_segment_text_stops_before_angle_bracket_quote_history(self) -> None:
        result = clean_thread_segment_text(
            body_text="Please confirm the sample.\n> Earlier quoted thread text"
        )

        self.assertEqual(result, "Please confirm the sample.")

    def test_thread_sources_are_sliced_before_text_or_html_cleaning(self) -> None:
        body_text = _TrackingText("Text " + ("x" * 25_000))
        body_html = _TrackingText("<p>Visible</p>" + ("x" * 25_000))

        result = clean_thread_segment_text(body_text=body_text, body_html=body_html)

        self.assertLessEqual(len(result), 2_000)
        self.assertTrue(body_text.slice_stops)
        self.assertTrue(body_html.slice_stops)
        self.assertLessEqual(max(stop for stop in body_text.slice_stops if stop is not None), 20_000)
        self.assertLessEqual(max(stop for stop in body_html.slice_stops if stop is not None), 20_000)


if __name__ == "__main__":
    unittest.main()
