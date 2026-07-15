"""Administrator-only single-item CLI for reviewed private knowledge."""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

from backend.private_knowledge.cli_models import (
    PrivateCliDependencies,
    PrivateCliResult,
)
from backend.private_knowledge.errors import PrivateKnowledgeError


COMMANDS = (
    "init", "import-candidate", "create", "business-approve",
    "privacy-approve", "owner-approve", "reject", "expire", "approve",
    "deprecate", "revoke", "publish",
)
_APPROVAL_COMMANDS = {"business-approve", "privacy-approve", "owner-approve"}
_CARD_COMMANDS = {"reject", "expire", "approve", "deprecate", "revoke"}
_ACTOR = re.compile(r"^actor-[a-z0-9-]{3,80}$")
_SAFE_ERROR_CODES = {
    "argument_invalid", "internal_error",
    "card_missing", "candidate_missing", "transition_invalid",
    "candidate_expired", "evidence_insufficient", "approval_incomplete",
    "owner_approval_required", "actor_not_distinct", "snapshot_write_failed",
}


class _SafeParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise _ArgumentFailure


class _ArgumentFailure(Exception):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = _SafeParser(prog="manage_private_knowledge.py")
    commands = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        selected = commands.add_parser(command)
        selected.add_argument("--authority-root", type=Path, required=True)
        selected.add_argument("--authority-id", required=True)
        if command == "init":
            selected.add_argument("--candidate-root", type=Path, required=True)
        elif command == "import-candidate":
            selected.add_argument("--batch-root", type=Path, required=True)
            selected.add_argument("--batch-id", required=True)
            selected.add_argument("--candidate-id", required=True)
        elif command == "create":
            selected.add_argument("--candidate-id", required=True)
            selected.add_argument("--reviewed-proposal", type=Path, required=True)
        elif command in _APPROVAL_COMMANDS:
            selected.add_argument("--card-id", required=True)
            selected.add_argument("--actor-ref", required=True)
        elif command in _CARD_COMMANDS:
            selected.add_argument("--card-id", required=True)
        elif command == "publish":
            selected.add_argument("--snapshot", type=Path, required=True)
            selected.add_argument("--snapshot-id", required=True)
    return parser


def run_cli(
    argv: list[str] | None = None,
    *,
    dependencies: PrivateCliDependencies | None = None,
) -> int:
    selected = dependencies if dependencies is not None else _default_dependencies()
    try:
        arguments = build_parser().parse_args(argv)
        _validate_arguments(arguments)
    except _ArgumentFailure:
        selected.emit({"ok": False, "code": "argument_invalid"})
        return 2
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    except (PrivateKnowledgeError, ValueError):
        selected.emit({"ok": False, "code": "argument_invalid"})
        return 2
    try:
        result = selected.dispatch(arguments)
        if not isinstance(result, PrivateCliResult):
            raise ValueError
        selected.emit(result.to_dict())
        return 0
    except Exception as error:
        code = getattr(error, "code", None)
        selected.emit({
            "ok": False,
            "code": code if code in _SAFE_ERROR_CODES else "internal_error",
        })
        return 2


def _validate_arguments(arguments: argparse.Namespace) -> None:
    for name in (
        "authority_root", "candidate_root", "batch_root", "reviewed_proposal",
        "snapshot",
    ):
        value = getattr(arguments, name, None)
        if value is not None and not value.is_absolute():
            raise ValueError
    _uuid4(arguments.authority_id)
    for name in ("batch_id", "candidate_id", "card_id", "snapshot_id"):
        value = getattr(arguments, name, None)
        if value is not None:
            _uuid4(value)
    actor = getattr(arguments, "actor_ref", None)
    if actor is not None and (not isinstance(actor, str) or _ACTOR.fullmatch(actor) is None):
        raise ValueError


def _uuid4(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError):
        raise ValueError from None
    if str(parsed) != value or parsed.version != 4:
        raise ValueError
    return value


def _default_emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    sys.stdout.write("\n")


def _default_dependencies() -> PrivateCliDependencies:
    from backend.private_knowledge.cli_service import (
        PrivateKnowledgeCommandService,
    )
    from backend.private_knowledge.dpapi import CurrentUserDpapiProtector

    service = PrivateKnowledgeCommandService(
        protector=CurrentUserDpapiProtector()
    )
    return PrivateCliDependencies(service.dispatch, _default_emit)


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
