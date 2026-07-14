"""Synthetic BODYSTRUCTURE parser tests for the read-only importer."""

from __future__ import annotations

import unittest

from backend.mailbox_ingest.bodystructure import (
    BodyStructureError,
    parse_bodystructure,
)


class BodyStructureTests(unittest.TestCase):
    def test_selects_plain_from_alternative_and_collects_attachment_metadata(self) -> None:
        source = (
            '((("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "7BIT" 12 1) '
            '("TEXT" "HTML" ("CHARSET" "UTF-8") NIL NIL "7BIT" 24 1) '
            '"ALTERNATIVE") '
            '("APPLICATION" "PDF" ("NAME" "report.pdf") NIL NIL "BASE64" 99 '
            'NIL ("ATTACHMENT" ("FILENAME" "report.pdf"))) "MIXED")'
        )

        plan = parse_bodystructure(source)

        self.assertEqual(
            [
                (item.section, item.transfer_encoding, item.charset)
                for item in plan.body_sections
            ],
            [("1.1", "7BIT", "utf-8")],
        )
        self.assertEqual(len(plan.attachments), 1)
        attachment = plan.attachments[0]
        self.assertEqual((attachment.section, attachment.mime_type, attachment.size), (
            "2", "application/pdf", 99
        ))
        self.assertEqual(attachment.filename, "report.pdf")

    def test_attachment_disposition_wins_over_text_body_and_decodes_filename(self) -> None:
        source = (
            '(("TEXT" "PLAIN" ("CHARSET" "UTF-8") NIL NIL "7BIT" 10 1) '
            '("TEXT" "PLAIN" ("NAME*" "UTF-8\'\'%E6%B5%8B%E8%AF%95.txt") '
            'NIL NIL "BASE64" 20 1 NIL '
            '("ATTACHMENT" ("FILENAME*" "UTF-8\'\'%E6%B5%8B%E8%AF%95.txt"))) '
            '"MIXED")'
        )

        plan = parse_bodystructure(source)

        self.assertEqual(plan.body_sections[0].section, "1")
        self.assertEqual(plan.body_sections[0].transfer_encoding, "7BIT")
        self.assertEqual(plan.body_sections[0].charset, "utf-8")
        self.assertEqual(plan.attachments[0].filename, "测试.txt")
        self.assertEqual(plan.attachments[0].section, "2")

    def test_nested_message_rfc822_blocks_whole_record(self) -> None:
        source = (
            '(("TEXT" "PLAIN" NIL NIL NIL "7BIT" 10 1) '
            '("MESSAGE" "RFC822" NIL NIL NIL "7BIT" 100 NIL NIL NIL) '
            '"MIXED")'
        )

        with self.assertRaisesRegex(BodyStructureError, "message_rfc822_forbidden"):
            parse_bodystructure(source)

    def test_rfc2231_filename_continuations_are_contiguous_and_decoded(self) -> None:
        source = (
            '("APPLICATION" "PDF" '
            '("NAME*0*" "UTF-8\'\'report%20" '
            '"NAME*1*" "%E6%B5%8B%E8%AF%95.pdf") '
            'NIL NIL "BASE64" 10 NIL '
            '("ATTACHMENT" '
            '("FILENAME*0*" "UTF-8\'\'report%20" '
            '"FILENAME*1*" "%E6%B5%8B%E8%AF%95.pdf")))'
        )

        plan = parse_bodystructure(source)

        self.assertEqual(plan.attachments[0].filename, "report \u6d4b\u8bd5.pdf")

    def test_rfc2231_filename_continuations_fail_closed_on_gap_or_conflict(self) -> None:
        cases = (
            '("APPLICATION" "PDF" '
            '("NAME*0*" "UTF-8\'\'a" "NAME*2*" "c.pdf") '
            'NIL NIL "BASE64" 10)',
            '("APPLICATION" "PDF" '
            '("NAME" "a.pdf" "NAME*0*" "UTF-8\'\'a.pdf") '
            'NIL NIL "BASE64" 10)',
        )

        for source in cases:
            with self.subTest(source=source):
                with self.assertRaises(BodyStructureError):
                    parse_bodystructure(source)

    def test_malformed_ambiguous_or_oversized_input_fails_closed(self) -> None:
        cases = {
            "unbalanced": '("TEXT" "PLAIN" NIL',
            "trailing": '("TEXT" "PLAIN" NIL NIL NIL "7BIT" 10 1) junk',
            "literal": '("TEXT" "PLAIN" {3}\r\nabc NIL NIL "7BIT" 10 1)',
            "unknown encoding": '("TEXT" "PLAIN" NIL NIL NIL "X-ROT" 10 1)',
            "conflicting filename": (
                '("APPLICATION" "PDF" ("NAME" "a.pdf" "NAME" "b.pdf") '
                'NIL NIL "BASE64" 10)'
            ),
            "too deep": "(" * 40 + "NIL" + ")" * 40,
            "too large": "(" + ('"A" ' * 10000) + ")",
        }

        for label, source in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(BodyStructureError):
                    parse_bodystructure(source)


if __name__ == "__main__":
    unittest.main()
