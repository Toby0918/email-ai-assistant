"""Administrator-only CLI parser, ordering, and output-safety tests."""

from __future__ import annotations

import tempfile
import unittest
import argparse
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts.manage_mailbox_vault import CliDependencies, CliResult, run_cli
from backend.mailbox_ingest.authorization import AuthorizationScope, freeze_window
from backend.mailbox_ingest.control_store import ControlStoreError
from backend.mailbox_ingest.folder_policy import RawFolder, select_mail_folders
from backend.mailbox_ingest.inventory import build_inventory
from backend.mailbox_ingest.inventory_codec import encode_inventory_bundle
from backend.mailbox_ingest.models import PutRecordResult
from backend.mailbox_ingest.service import MailboxVaultService, build_cli_dependencies


COMMANDS = {
    "init", "inventory", "scan", "attachments", "verify", "purge-expired",
    "revoke", "rewrap-recovery",
}
NETWORK_COMMANDS = {"inventory", "scan", "attachments"}


class FakeSessionContext(AbstractContextManager):
    def __init__(self, events: list[object]) -> None:
        self.events = events

    def __enter__(self):
        self.events.append("session-enter")
        return object()

    def __exit__(self, *_args):
        self.events.append("session-exit")


class FakeOperation:
    def __init__(self, events: list[object], command: str, *, failure=False) -> None:
        self.events = events
        self.command = command
        self.failure = failure

    def execute(self, session):
        self.events.append(("execute", self.command, session is not None))
        if self.failure:
            raise RuntimeError("SECRET-CANARY-FAILURE")
        return CliResult(code=f"{self.command}_complete", count=1)

    def close(self):
        self.events.append(("operation-close", self.command))


def fake_dependencies(events: list[object], *, failure=False) -> CliDependencies:
    def preflight(arguments):
        events.append(("preflight", arguments.command))
        return object()

    def prepare(arguments, _local):
        events.append(("prepare", arguments.command))
        return FakeOperation(events, arguments.command, failure=failure)

    def getpass(prompt: str):
        events.append(("getpass", prompt))
        return "SYNTHETIC-PASSWORD"

    def session_factory(account: str, password: str):
        events.append(("session-factory", account, password == "SYNTHETIC-PASSWORD"))
        return FakeSessionContext(events)

    def emit(payload: dict[str, object]):
        events.append(("emit", payload))

    return CliDependencies(preflight, prepare, getpass, session_factory, emit)


class ManageMailboxVaultCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.recovery = self.root / "offline" / "recovery.key"
        self.recovery.parent.mkdir()
        self.manifest = self.root / "reviewed.json"
        self.manifest.write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _argv(self, command: str) -> list[str]:
        argv = [
            command,
            "--vault", str(self.vault),
            "--authorization-id", "AUTH-CLI-1",
            "--account", "one@example.test",
        ]
        if command == "init":
            argv += ["--recovery-key", str(self.recovery)]
        elif command == "scan":
            argv += ["--confirm-inventory-fingerprint", "a" * 64]
        elif command == "attachments":
            argv += ["--manifest", str(self.manifest)]
        elif command == "revoke":
            argv += ["--confirm", "REVOKE:opaque"]
        elif command == "rewrap-recovery":
            argv += [
                "--current-recovery-key", str(self.recovery),
                "--new-recovery-key", str(self.root / "offline-2" / "new.key"),
                "--confirm", "REWRAP:opaque",
            ]
        return argv

    def test_exact_eight_commands_parse_and_all_require_common_scope(self) -> None:
        for command in COMMANDS:
            with self.subTest(command=command):
                events: list[object] = []
                code = run_cli(self._argv(command), dependencies=fake_dependencies(events))
                self.assertEqual(code, 0)
                self.assertEqual(events[0], ("preflight", command))

        for command in COMMANDS:
            with self.subTest(command=command, missing="authorization"):
                argv = self._argv(command)
                index = argv.index("--authorization-id")
                del argv[index:index + 2]
                events = []
                self.assertEqual(
                    run_cli(argv, dependencies=fake_dependencies(events)), 2
                )
                self.assertFalse(any(
                    isinstance(event, tuple) and event[0] == "preflight"
                    for event in events
                ))

    def test_network_order_has_local_prepare_then_one_getpass_and_verified_session(self) -> None:
        for command in NETWORK_COMMANDS:
            with self.subTest(command=command):
                events: list[object] = []

                code = run_cli(self._argv(command), dependencies=fake_dependencies(events))

                self.assertEqual(code, 0)
                labels = [event[0] if isinstance(event, tuple) else event for event in events]
                self.assertEqual(
                    labels,
                    [
                        "preflight", "prepare", "getpass", "session-factory",
                        "session-enter", "execute", "session-exit", "operation-close",
                        "emit",
                    ],
                )
                self.assertEqual(labels.count("getpass"), 1)

    def test_local_commands_never_getpass_or_construct_imap(self) -> None:
        for command in COMMANDS - NETWORK_COMMANDS:
            with self.subTest(command=command):
                events: list[object] = []
                self.assertEqual(
                    run_cli(self._argv(command), dependencies=fake_dependencies(events)),
                    0,
                )
                labels = [event[0] if isinstance(event, tuple) else event for event in events]
                self.assertNotIn("getpass", labels)
                self.assertNotIn("session-factory", labels)
                self.assertIn(("execute", command, False), events)
                self.assertIn(("operation-close", command), events)

    def test_forbidden_transport_password_range_schedule_and_retry_options_fail_parse(self) -> None:
        options = (
            ["--host", "other.test"], ["--port", "143"],
            ["--password", "secret"], ["--password-file", "secret.txt"],
            ["--start-date", "2020-01-01"], ["--folder", "INBOX"],
            ["--uid", "7"], ["--command", "STORE"], ["--retry", "1"],
            ["--schedule", "daily"],
        )
        for extra in options:
            with self.subTest(extra=extra):
                events: list[object] = []
                code = run_cli(
                    self._argv("inventory") + extra,
                    dependencies=fake_dependencies(events),
                )
                self.assertEqual(code, 2)
                self.assertFalse(any(
                    isinstance(event, tuple) and event[0] in {"preflight", "getpass"}
                    for event in events
                ))

    def test_invalid_account_or_relative_vault_stops_before_preflight(self) -> None:
        cases = (
            ["inventory", "--vault", str(self.vault), "--authorization-id", "AUTH-1",
             "--account", "one@example.test,two@example.test"],
            ["inventory", "--vault", "relative", "--authorization-id", "AUTH-1",
             "--account", "one@example.test"],
        )
        for argv in cases:
            events: list[object] = []
            with self.subTest(argv=argv):
                self.assertEqual(run_cli(argv, dependencies=fake_dependencies(events)), 2)
                self.assertFalse(any(
                    isinstance(event, tuple) and event[0] == "preflight"
                    for event in events
                ))

    def test_failure_output_is_fixed_and_never_contains_exception_or_password(self) -> None:
        events: list[object] = []

        code = run_cli(
            self._argv("inventory"),
            dependencies=fake_dependencies(events, failure=True),
        )

        self.assertEqual(code, 2)
        rendered = repr(events)
        self.assertNotIn("SECRET-CANARY-FAILURE", rendered)
        self.assertNotIn("SYNTHETIC-PASSWORD", rendered)
        self.assertIn("internal_error", rendered)

    def test_help_and_parser_do_not_construct_default_host_probes_or_socket(self) -> None:
        with mock.patch("imaplib.IMAP4_SSL") as imap, mock.patch(
            "subprocess.run"
        ) as process:
            code = run_cli(["--help"])
        self.assertEqual(code, 0)
        imap.assert_not_called()
        process.assert_not_called()


class _FacadeSession:
    def __init__(self, events: list[str]) -> None:
        self.events = events

    def examine(self, _mailbox: str) -> int:
        self.events.append("examine")
        return 77

    def uid_search(self, _since):
        return (7,)

    def uid_fetch_size(self, uid: int):
        return type(
            "Size", (), {
                "uid": uid,
                "size": 10,
                "internal_date": datetime(2023, 6, 1, tzinfo=timezone.utc),
            }
        )()

    def uid_fetch_bodystructure(self, _uid: int) -> str:
        self.events.append("bodystructure")
        return '("TEXT" "PLAIN" NIL NIL NIL "7BIT" 4 1)'

    def uid_fetch_peek(self, _uid: int, section: str) -> bytes:
        self.events.append(f"peek:{section}")
        return b"head" if section == "HEADER" else b"body"


class _FacadeControl:
    def __init__(self, inventory_payload: dict[str, object]) -> None:
        self.inventory_payload = inventory_payload
        self.scan_state = None

    def read(self, name: str):
        if name == "inventory":
            return self.inventory_payload
        if self.scan_state is None:
            raise ControlStoreError("control_store_missing")
        return self.scan_state

    def write(self, name: str, payload: dict[str, object]) -> None:
        if name == "scan-state":
            self.scan_state = payload


class _FacadeVault:
    def put_record_if_absent(self, _value: bytes, *, expires_at_utc: int):
        return PutRecordResult("1" * 32, True)

    def verify(self):
        return type(
            "Report", (), {
                "missing_count": 0,
                "orphan_count": 0,
                "integrity_failure_count": 0,
            }
        )()


class _FacadeOpened:
    def __init__(self, bundle, scope, events: list[str]) -> None:
        self.bundle = bundle
        self.scope = scope
        self.events = events
        self.control = _FacadeControl(encode_inventory_bundle(bundle))
        self.vault = _FacadeVault()
        self.vault_root = Path("C:/synthetic-vault")
        self.closed = False

    def authorization_scope(self, _authorization_id: str, _account: str):
        return self.scope

    def inventory(self, _session, *, scope, folders, window):
        self.events.append("rebuild")
        return self.bundle

    def close(self):
        self.closed = True


class ServiceFacadeTests(unittest.TestCase):
    def _fixture(self):
        scope = AuthorizationScope.create(
            "AUTH-SERVICE-1", "one@example.test", hmac_key=b"S" * 32
        )
        folders = select_mail_folders(
            (RawFolder(("\\Inbox",), "INBOX"),), hmac_key=b"F" * 32
        )
        window = freeze_window(datetime(2024, 2, 29, tzinfo=timezone.utc))
        session = _FacadeSession([])
        bundle = build_inventory(
            session,
            scope=scope,
            folders=folders,
            window=window,
            fingerprint_key=b"I" * 32,
        )
        return scope, bundle

    def test_service_construction_is_lazy_until_preflight_and_prepare(self) -> None:
        calls: list[str] = []
        service = MailboxVaultService(
            project_root=Path("C:/project"),
            validate_existing=lambda *_args, **_kwargs: calls.append("validate"),
            open_vault=lambda *_args, **_kwargs: calls.append("open"),
            dpapi_factory=lambda: calls.append("dpapi"),
        )

        dependencies = build_cli_dependencies(
            getpass_function=lambda _prompt: "synthetic",
            emit=lambda _payload: None,
            service=service,
        )

        self.assertEqual(calls, [])
        arguments = argparse.Namespace(command="verify", vault=Path("C:/vault"))
        local = dependencies.preflight(arguments)
        self.assertEqual(calls, ["validate"])
        with self.assertRaises(Exception):
            dependencies.prepare(
                argparse.Namespace(
                    command="verify", vault=Path("C:/vault"),
                    authorization_id="AUTH-1", account="one@example.test",
                ),
                local,
            )
        self.assertEqual(calls, ["validate", "dpapi", "open"])

    def test_scan_operation_rebuilds_frozen_inventory_before_any_content_fetch(self) -> None:
        scope, bundle = self._fixture()
        events: list[str] = []
        opened = _FacadeOpened(bundle, scope, events)
        service = MailboxVaultService(
            project_root=Path("C:/project"),
            validate_existing=lambda *_args, **_kwargs: None,
            open_vault=lambda *_args, **_kwargs: opened,
            dpapi_factory=lambda: object(),
        )
        arguments = argparse.Namespace(
            command="scan",
            vault=Path("C:/vault"),
            authorization_id="AUTH-SERVICE-1",
            account="one@example.test",
            confirm_inventory_fingerprint=bundle.inventory.fingerprint,
        )
        local = service.preflight(arguments)
        operation = service.prepare(arguments, local)
        session = _FacadeSession(events)

        result = operation.execute(session)
        operation.close()

        self.assertEqual(result.code, "scan_complete")
        self.assertLess(events.index("rebuild"), events.index("bodystructure"))
        self.assertTrue(opened.closed)

    def test_local_verify_operation_does_not_construct_or_require_session(self) -> None:
        scope, bundle = self._fixture()
        opened = _FacadeOpened(bundle, scope, [])
        service = MailboxVaultService(
            project_root=Path("C:/project"),
            validate_existing=lambda *_args, **_kwargs: None,
            open_vault=lambda *_args, **_kwargs: opened,
            dpapi_factory=lambda: object(),
            session_builder=lambda *_args: (_ for _ in ()).throw(
                AssertionError("session constructed")
            ),
        )
        arguments = argparse.Namespace(
            command="verify", vault=Path("C:/vault"),
            authorization_id="AUTH-SERVICE-1", account="one@example.test",
        )

        operation = service.prepare(arguments, service.preflight(arguments))
        result = operation.execute(None)
        operation.close()

        self.assertEqual(result.code, "verify_complete")


if __name__ == "__main__":
    unittest.main()
