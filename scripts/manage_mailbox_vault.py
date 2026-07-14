"""Administrator-only entry point for the separately authorized mailbox vault."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path

from backend.mailbox_ingest.authorization import (
    AuthorizationError,
    AuthorizationScope,
)
from backend.mailbox_ingest.service_models import (
    CliDependencies,
    CliResult,
    PreparedOperation,
)


NETWORK_COMMANDS = frozenset({"inventory", "scan", "attachments"})
COMMANDS = (
    "init", "inventory", "scan", "attachments", "verify", "purge-expired",
    "revoke", "rewrap-recovery",
)
_FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
_SAFE_CODES = frozenset(
    {
        "argument_invalid", "internal_error", "authorization_invalid",
        "account_invalid", "path_not_absolute", "inventory_fingerprint_mismatch",
        "attachment_manifest_invalid", "revoke_confirmation_required",
        "rewrap_confirmation_required",
    }
)


class _SafeParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise _ArgumentFailure


class _ArgumentFailure(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeParser(prog="manage_mailbox_vault.py")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparser = commands.add_parser(command)
        _add_common_arguments(subparser)
        if command == "init":
            subparser.add_argument("--recovery-key", type=Path, required=True)
        elif command == "scan":
            subparser.add_argument(
                "--confirm-inventory-fingerprint", required=True
            )
        elif command == "attachments":
            subparser.add_argument("--manifest", type=Path, required=True)
        elif command == "purge-expired":
            subparser.add_argument("--limit", type=int, default=100)
        elif command == "revoke":
            subparser.add_argument("--confirm", required=True)
        elif command == "rewrap-recovery":
            subparser.add_argument(
                "--current-recovery-key", type=Path, required=True
            )
            subparser.add_argument("--new-recovery-key", type=Path, required=True)
            subparser.add_argument("--confirm", required=True)
    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--account", required=True)


def run_cli(
    argv: list[str] | None = None,
    *,
    dependencies: CliDependencies | None = None,
) -> int:
    try:
        arguments = build_parser().parse_args(argv)
    except _ArgumentFailure:
        if dependencies is not None:
            dependencies.emit({"ok": False, "code": "argument_invalid"})
        return 2
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    try:
        _validate_local_arguments(arguments)
    except (AuthorizationError, ValueError):
        if dependencies is not None:
            dependencies.emit({"ok": False, "code": "argument_invalid"})
        return 2
    selected = dependencies if dependencies is not None else _default_dependencies()
    operation: PreparedOperation | None = None
    try:
        local = selected.preflight(arguments)
        operation = selected.prepare(arguments, local)
        if arguments.command in NETWORK_COMMANDS:
            password = selected.getpass("Mailbox app password: ")
            if not isinstance(password, str) or not password:
                raise ValueError
            with selected.session_factory(arguments.account.strip().lower(), password) as session:
                result = operation.execute(session)
        else:
            result = operation.execute(None)
        if not isinstance(result, CliResult):
            raise ValueError
        _close_operation(operation)
        operation = None
        selected.emit(result.to_dict())
        return 0
    except Exception as error:
        if operation is not None:
            try:
                _close_operation(operation)
            except Exception:
                error = ValueError()
        selected.emit({"ok": False, "code": _error_code(error)})
        return 2


def _validate_local_arguments(arguments: argparse.Namespace) -> None:
    AuthorizationScope.create(
        arguments.authorization_id,
        arguments.account,
        hmac_key=bytes(32),
    )
    if not arguments.vault.is_absolute():
        raise ValueError
    for name in (
        "recovery_key", "manifest", "current_recovery_key", "new_recovery_key"
    ):
        value = getattr(arguments, name, None)
        if value is not None and not value.is_absolute():
            raise ValueError
    fingerprint = getattr(arguments, "confirm_inventory_fingerprint", None)
    if fingerprint is not None and _FINGERPRINT.fullmatch(fingerprint) is None:
        raise ValueError
    limit = getattr(arguments, "limit", 100)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return code if code in _SAFE_CODES else "internal_error"


def _close_operation(operation: PreparedOperation) -> None:
    close = getattr(operation, "close", None)
    if close is not None:
        close()


def _default_emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")


def _default_dependencies() -> CliDependencies:
    from backend.mailbox_ingest.service import build_cli_dependencies

    return build_cli_dependencies(
        getpass_function=getpass.getpass,
        emit=_default_emit,
    )


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
