"""Exact-wire synthetic tests for the narrow read-only IMAP wrapper."""

from __future__ import annotations

import ssl
import unittest
from datetime import datetime, timezone

from backend.mailbox_ingest.imap_readonly import (
    IMAP_HOST,
    IMAP_PORT,
    ImapReadOnlyError,
    ReadOnlyImapSession,
    validate_fetch_selector,
    validate_single_uid_fetch_target,
)
from backend.mailbox_ingest.folder_policy import select_mail_folders
from backend.mailbox_ingest.imap_response import parse_list_response


class FakeRawImap:
    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.flags = {7: frozenset({"\\Seen"})}
        self.uidvalidity = b"42"
        self.fetch_responses = {
            "(RFC822.SIZE INTERNALDATE)": [
                b'1 (UID 7 RFC822.SIZE 123 '
                b'INTERNALDATE "01-Jan-2024 01:02:03 +0000")'
            ],
            "(BODYSTRUCTURE)": [
                b'1 (UID 7 BODYSTRUCTURE '
                b'("TEXT" "PLAIN" NIL NIL NIL "7BIT" 3 1))'
            ],
            "(BODY.PEEK[HEADER])": [
                (b"1 (UID 7 BODY[HEADER] {3}", b"abc"),
                b")",
            ],
        }

    def login(self, account: str, password: str):
        self.calls.append(("login", account, password))
        return "OK", [b"logged in"]

    def logout(self):
        self.calls.append(("logout",))
        return "BYE", [b"logout"]

    def list(self):
        self.calls.append(("list",))
        return "OK", [
            b'(\\HasNoChildren \\Inbox) "/" "INBOX"',
            b'(\\HasNoChildren \\Sent) "/" "Sent"',
        ]

    def select(self, mailbox=None, readonly=False):
        self.calls.append(("select", mailbox, readonly))
        return "OK", [b"2"]

    def response(self, code: str):
        self.calls.append(("response", code))
        return "UIDVALIDITY", [self.uidvalidity]

    def uid(self, command: str, *args: object):
        self.calls.append(("uid", command, *args))
        if command == "SEARCH":
            return "OK", [b"2 7"]
        if command == "FETCH":
            return "OK", self.fetch_responses[str(args[1])]
        raise AssertionError("unexpected command")


class ImapReadOnlyTests(unittest.TestCase):
    def _session(self, raw: FakeRawImap | None = None):
        raw = raw or FakeRawImap()
        factory_calls: list[tuple[object, ...]] = []

        def factory(host, port, *, ssl_context, timeout):
            factory_calls.append((host, port, ssl_context, timeout))
            return raw

        session = ReadOnlyImapSession(
            "one@example.test",
            "SYNTHETIC-APP-PASSWORD",
            client_factory=factory,
        )
        return session, raw, factory_calls

    def test_fixed_tls_endpoint_login_and_logout_lifecycle(self) -> None:
        session, raw, factory_calls = self._session()

        with session:
            pass

        self.assertEqual((IMAP_HOST, IMAP_PORT), ("imap.exmail.qq.com", 993))
        host, port, context, timeout = factory_calls[0]
        self.assertEqual((host, port, timeout), (IMAP_HOST, IMAP_PORT, 10))
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertEqual(raw.calls[0][0], "login")
        self.assertEqual(raw.calls[-1], ("logout",))
        self.assertNotIn("SYNTHETIC-APP-PASSWORD", repr(session))

    def test_login_exception_or_rejection_cleans_created_client_safely(self) -> None:
        for mode in ("exception", "rejected"):
            raw = FakeRawImap()
            raw.shutdown_calls = 0

            def login(_account: str, _password: str, *, _mode=mode):
                raw.calls.append(("login", "ACCOUNT-CANARY", "PASSWORD-CANARY"))
                if _mode == "exception":
                    raise RuntimeError("SERVER-CANARY")
                return "NO", [b"SERVER-CANARY"]

            def logout(*, _mode=mode):
                raw.calls.append(("logout",))
                if _mode == "exception":
                    raise RuntimeError("LOGOUT-CANARY")
                return "BYE", [b"closed"]

            def shutdown():
                raw.shutdown_calls += 1

            raw.login = login  # type: ignore[method-assign]
            raw.logout = logout  # type: ignore[method-assign]
            raw.shutdown = shutdown  # type: ignore[attr-defined]

            with self.subTest(mode=mode), self.assertRaises(
                ImapReadOnlyError
            ) as caught:
                self._session(raw)

            self.assertIn(("logout",), raw.calls)
            if mode == "exception":
                self.assertEqual(raw.shutdown_calls, 1)
            self.assertNotIn("SERVER-CANARY", repr(caught.exception))
            self.assertNotIn("PASSWORD-CANARY", repr(caught.exception))

    def test_exposes_exact_six_public_operations_and_never_close(self) -> None:
        methods = {
            name
            for name, value in ReadOnlyImapSession.__dict__.items()
            if callable(value) and not name.startswith("_")
        }
        self.assertEqual(
            methods,
            {
                "list_folders", "examine", "uid_search", "uid_fetch_size",
                "uid_fetch_bodystructure", "uid_fetch_peek",
            },
        )

    def test_list_examine_search_and_fetch_shapes_are_exact_and_read_only(self) -> None:
        session, raw, _factory_calls = self._session()
        before_flags = dict(raw.flags)

        folders = session.list_folders()
        uidvalidity = session.examine("INBOX")
        uids = session.uid_search(datetime(2022, 2, 28, tzinfo=timezone.utc))
        size = session.uid_fetch_size(7)
        bodystructure = session.uid_fetch_bodystructure(7)
        header = session.uid_fetch_peek(7, "HEADER")

        self.assertEqual(folders[0].mailbox, "INBOX")
        self.assertEqual(uidvalidity, 42)
        self.assertEqual(uids, (2, 7))
        self.assertEqual(
            (size.uid, size.size, size.internal_date),
            (7, 123, datetime(2024, 1, 1, 1, 2, 3, tzinfo=timezone.utc)),
        )
        self.assertIn('"TEXT" "PLAIN"', bodystructure)
        self.assertEqual(header, b"abc")
        self.assertEqual(raw.flags, before_flags)
        self.assertIn(("select", b'"INBOX"', True), raw.calls)
        self.assertIn(("uid", "SEARCH", None, "SINCE", "28-Feb-2022"), raw.calls)
        self.assertIn(("uid", "FETCH", "7", "(RFC822.SIZE INTERNALDATE)"), raw.calls)
        self.assertIn(("uid", "FETCH", "7", "(BODYSTRUCTURE)"), raw.calls)
        self.assertIn(("uid", "FETCH", "7", "(BODY.PEEK[HEADER])"), raw.calls)

    def test_runtime_uid_and_selector_validators_fail_closed(self) -> None:
        self.assertEqual(validate_single_uid_fetch_target(1), "1")
        self.assertEqual(validate_single_uid_fetch_target(4_294_967_295), "4294967295")
        for invalid in (True, 0, -1, 4_294_967_296, "7", [7], (7, 8)):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ImapReadOnlyError):
                    validate_single_uid_fetch_target(invalid)  # type: ignore[arg-type]

        allowed = (
            "(RFC822.SIZE INTERNALDATE)", "(BODYSTRUCTURE)",
            "(BODY.PEEK[HEADER])", "(BODY.PEEK[1])", "(BODY.PEEK[2.1])",
            "(BODY.PEEK[2.1]<0.1048576>)",
            "(BODY.PEEK[HEADER]<0.65536>)",
        )
        self.assertEqual([validate_fetch_selector(item) for item in allowed], list(allowed))
        rejected = (
            "BODY[]", "(BODY[1])", "(BODY.PEEK[0])", "(BODY.PEEK[01])",
            "(BODY.PEEK[1.0])", "(BODY.PEEK[1.MIME])", "(BODY.PEEK[1.TEXT])",
            "(BODY.PEEK[1:*])", "(BODY.PEEK[1,2])", "(FLAGS)", "RFC822",
            "(BODY.PEEK[1]<0.0>)", "(BODY.PEEK[1]<0.99999999>)", "\n",
        )
        for selector in rejected:
            with self.subTest(selector=selector):
                with self.assertRaises(ImapReadOnlyError):
                    validate_fetch_selector(selector)

    def test_malformed_status_extra_records_wrong_uid_or_literal_length_are_safe(self) -> None:
        cases = {
            "non-ok": ("NO", [b"SERVER-CANARY"]),
            "extra record": (
                "OK",
                [
                    (b"1 (UID 7 BODY[HEADER] {3}", b"abc"), b")",
                    (b"2 (UID 8 BODY[HEADER] {3}", b"def"), b")",
                ],
            ),
            "wrong uid": (
                "OK", [(b"1 (UID 8 BODY[HEADER] {3}", b"abc"), b")"]
            ),
            "wrong literal": (
                "OK", [(b"1 (UID 7 BODY[HEADER] {4}", b"abc"), b")"]
            ),
        }
        for label, response in cases.items():
            raw = FakeRawImap()
            raw.fetch_responses["(BODY.PEEK[HEADER])"] = response[1]
            original_uid = raw.uid

            def uid(command: str, *args: object, _response=response):
                if command == "FETCH":
                    return _response
                return original_uid(command, *args)

            raw.uid = uid  # type: ignore[method-assign]
            session, _raw, _factory = self._session(raw)
            with self.subTest(label=label):
                with self.assertRaises(ImapReadOnlyError) as caught:
                    session.uid_fetch_peek(7, "HEADER")
                self.assertNotIn("SERVER-CANARY", repr(caught.exception))

    def test_fetch_rejects_missing_duplicate_or_extra_requested_data_items(self) -> None:
        cases = {
            "missing UID": [
                b'1 (RFC822.SIZE 123 '
                b'INTERNALDATE "01-Jan-2024 01:02:03 +0000")'
            ],
            "duplicate UID": [
                b'1 (UID 7 UID 7 RFC822.SIZE 123 '
                b'INTERNALDATE "01-Jan-2024 01:02:03 +0000")'
            ],
            "extra FLAGS": [
                b'1 (UID 7 RFC822.SIZE 123 '
                b'INTERNALDATE "01-Jan-2024 01:02:03 +0000" FLAGS (\\Seen))'
            ],
            "wrong UID": [
                b'1 (UID 8 RFC822.SIZE 123 '
                b'INTERNALDATE "01-Jan-2024 01:02:03 +0000")'
            ],
        }
        for label, response in cases.items():
            raw = FakeRawImap()
            raw.fetch_responses["(RFC822.SIZE INTERNALDATE)"] = response
            session, _raw, _factory = self._session(raw)
            with self.subTest(label=label), self.assertRaises(ImapReadOnlyError):
                session.uid_fetch_size(7)

        raw = FakeRawImap()
        raw.fetch_responses["(BODYSTRUCTURE)"] = [
            b'1 (UID 7 BODYSTRUCTURE '
            b'("TEXT" "PLAIN" NIL NIL NIL "7BIT" 3 1) RFC822.SIZE 3)'
        ]
        session, _raw, _factory = self._session(raw)
        with self.assertRaises(ImapReadOnlyError):
            session.uid_fetch_bodystructure(7)

    def test_list_strictly_decodes_modified_utf7_and_literal_ampersand(self) -> None:
        folders = parse_list_response(
            [
                b'(\\HasNoChildren) "/" "&haqNRA-"',
                b'(\\HasNoChildren) "/" "Sales&-Ops"',
            ]
        )

        self.assertEqual([item.mailbox for item in folders], ["\u85aa\u8d44", "Sales&Ops"])

    def test_non_ascii_folder_policy_name_preserves_exact_select_wire_token(self) -> None:
        raw = FakeRawImap()
        raw.list = lambda: (  # type: ignore[method-assign]
            "OK", [b'(\\HasNoChildren) "/" "&W6JiNw-"']
        )
        session, _raw, _factory = self._session(raw)

        selected = select_mail_folders(
            session.list_folders(), hmac_key=b"F" * 32
        )
        uidvalidity = session.examine(selected[0].wire_mailbox)

        self.assertEqual(selected[0].mailbox, "\u5ba2\u6237")
        self.assertEqual(uidvalidity, 42)
        self.assertIn(("select", b'"&W6JiNw-"', True), raw.calls)

        session.examine("Sales Team")
        self.assertIn(("select", b'"Sales Team"', True), raw.calls)

    def test_list_rejects_invalid_or_canonically_duplicate_modified_utf7(self) -> None:
        invalid = (b"&broken", b"&A-", b"&AGE-")
        for mailbox in invalid:
            response = b'(\\HasNoChildren) "/" "' + mailbox + b'"'
            with self.subTest(mailbox=mailbox), self.assertRaises(ImapReadOnlyError):
                parse_list_response([response])

        with self.assertRaises(ImapReadOnlyError):
            parse_list_response(
                [
                    b'(\\HasNoChildren) "/" "&AOk-"',
                    b'(\\HasNoChildren) "/" "e&AwE-"',
                ]
            )


if __name__ == "__main__":
    unittest.main()
