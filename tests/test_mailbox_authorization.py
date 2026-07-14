"""Authorization, account, date-window, and folder-policy tests."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from backend.mailbox_ingest.authorization import (
    AuthorizationError,
    AuthorizationScope,
    add_calendar_months,
    freeze_window,
)
from backend.mailbox_ingest.folder_policy import (
    FolderPolicyError,
    RawFolder,
    select_mail_folders,
)
from backend.mailbox_ingest.imap_response import parse_list_response


class AuthorizationTests(unittest.TestCase):
    def test_accepts_one_bounded_identifier_and_normalizes_account(self) -> None:
        scope = AuthorizationScope.create(
            "AUTH-2026-0042",
            " Business.Unit@Example.Test ",
            hmac_key=b"K" * 32,
        )

        self.assertEqual(scope.account, "business.unit@example.test")
        self.assertRegex(scope.opaque_scope_id, r"^[0-9a-f]{64}$")
        self.assertNotIn("AUTH-2026-0042", repr(scope))
        self.assertNotIn("example.test", repr(scope))

    def test_rejects_multiple_accounts_or_unsafe_authorization_identifiers(self) -> None:
        invalid_ids = (
            "",
            "contains space",
            "../escape",
            "slash/value",
            "line\nbreak",
            "A" * 65,
            "非ASCII",
        )
        for authorization_id in invalid_ids:
            with self.subTest(authorization_id=authorization_id):
                with self.assertRaises(AuthorizationError):
                    AuthorizationScope.create(
                        authorization_id,
                        "one@example.test",
                        hmac_key=b"K" * 32,
                    )

        for account in (
            "a@example.test,b@example.test",
            "a@example.test b@example.test",
            "not-an-account",
            ["a@example.test", "b@example.test"],
        ):
            with self.subTest(account=account):
                with self.assertRaises(AuthorizationError):
                    AuthorizationScope.create(
                        "AUTH-1", account, hmac_key=b"K" * 32  # type: ignore[arg-type]
                    )

    def test_freezes_twenty_four_calendar_months_with_month_end_clamping(self) -> None:
        leap_end = datetime(2024, 2, 29, 12, 30, tzinfo=timezone.utc)
        window = freeze_window(leap_end)

        self.assertEqual(window.window_end, leap_end)
        self.assertEqual(
            window.window_start,
            datetime(2022, 2, 28, 12, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(
            add_calendar_months(leap_end, 24),
            datetime(2026, 2, 28, 12, 30, tzinfo=timezone.utc),
        )

        with self.assertRaises(AuthorizationError):
            freeze_window(datetime(2024, 1, 1))


class FolderPolicyTests(unittest.TestCase):
    def test_uses_special_use_flags_and_includes_unambiguous_business_custom(self) -> None:
        folders = (
            RawFolder(("\\Inbox",), "INBOX"),
            RawFolder(("\\Sent",), "已发送"),
            RawFolder(("\\Archive",), "Archive"),
            RawFolder((), "Projects/Alpha"),
            RawFolder(("\\Drafts",), "Drafts"),
            RawFolder(("\\Trash",), "Trash"),
            RawFolder(("\\Junk",), "Spam"),
            RawFolder((), "HR/Payroll"),
            RawFolder((), "Security Incidents"),
        )

        selected = select_mail_folders(folders, hmac_key=b"F" * 32)

        self.assertEqual(len(selected), 4)
        self.assertEqual(
            {item.role for item in selected},
            {"inbox", "sent", "archive", "business_custom"},
        )
        self.assertTrue(all(len(item.opaque_folder_id) == 64 for item in selected))
        rendered = repr(selected)
        for canary in ("Projects/Alpha", "Payroll", "已发送"):
            self.assertNotIn(canary, rendered)

    def test_conflicting_duplicate_undecodable_or_ambiguous_folders_fail_closed(self) -> None:
        cases = (
            (RawFolder(("\\Sent", "\\Trash"), "mixed"),),
            (RawFolder(("\\Inbox",), "INBOX"), RawFolder(("\\Inbox",), "Inbox2")),
            (RawFolder((), "Draft Project"),),
            (RawFolder((), "Medical Orders"),),
            (RawFolder((), b"\xff"),),
        )

        for folders in cases:
            with self.subTest(folders=folders):
                with self.assertRaises(FolderPolicyError):
                    select_mail_folders(folders, hmac_key=b"F" * 32)

    def test_modified_utf7_sensitive_folder_is_decoded_then_excluded(self) -> None:
        folders = parse_list_response(
            [
                b'(\\HasNoChildren \\Inbox) "/" "INBOX"',
                b'(\\HasNoChildren) "/" "&haqNRA-"',
            ]
        )

        selected = select_mail_folders(folders, hmac_key=b"F" * 32)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0].role, "inbox")


if __name__ == "__main__":
    unittest.main()
