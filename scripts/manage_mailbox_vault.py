"""Administrator-only entry point for the separately authorized mailbox vault."""

from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from backend.mailbox_ingest.authorization import (
    AuthorizationError,
    AuthorizationScope,
)
from backend.mailbox_ingest.service_models import (
    CliDependencies,
    CliResult,
    PreparedOperation,
)
from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.key_store import open_candidate_key
from backend.private_knowledge.repository import CandidateBatchStore, DetachedCandidate
from backend.private_knowledge.candidate_retention import (
    purge_expired_candidate_batches,
)
from backend.private_knowledge.residual_scanner import scan_residuals
from backend.private_knowledge.staging import stage_knowledge
from backend.private_knowledge.staging_contract import (
    CandidateBatchReceipt,
    StageKnowledgeResult,
    load_stage_selection_manifest,
)
from backend.private_knowledge.storage_policy import validate_stage_storage
from backend.private_evaluation.staging import (
    execute_stage_evaluation_command, load_stage_evaluation_key as _load_stage_evaluation_key,
)
from backend.private_evaluation.staging_contract import (
    StageEvaluationResult,
    public_stage_error_code as _stage_evaluation_error_code,
)
from backend.private_evaluation.staging_repository import (
    _validate_external_stage_path,
    write_encrypted_stage,
)


NETWORK_COMMANDS = frozenset({"inventory", "scan", "attachments"})
COMMANDS = (
    "init", "inventory", "scan", "attachments", "verify", "purge-expired",
    "revoke", "rewrap-recovery",
)
STAGE_COMMAND = "stage-knowledge"
STAGE_EVALUATION_COMMAND = "stage-evaluation"
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
    for command in (*COMMANDS, STAGE_COMMAND, STAGE_EVALUATION_COMMAND):
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
        elif command == STAGE_COMMAND:
            subparser.add_argument("--selection-manifest", type=Path, required=True)
            subparser.add_argument("--candidate-batch-root", type=Path, required=True)
        elif command == STAGE_EVALUATION_COMMAND:
            subparser.add_argument("--selection-manifest", type=Path, required=True)
            subparser.add_argument("--staging-dataset", type=Path, required=True)
    return parser


def _add_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--vault", type=Path, required=True)
    parser.add_argument("--authorization-id", required=True)
    parser.add_argument("--account", required=True)


def run_cli(
    argv: list[str] | None = None,
    *,
    dependencies: CliDependencies | None = None,
    stage_runner: Callable[[argparse.Namespace], StageKnowledgeResult] | None = None,
    stage_evaluation_runner: Callable[[argparse.Namespace], StageEvaluationResult] | None = None,
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
    if arguments.command == STAGE_COMMAND:
        emit = dependencies.emit if dependencies is not None else _default_emit
        try:
            result = (stage_runner or _default_stage_runner)(arguments)
            if not isinstance(result, StageKnowledgeResult):
                raise ValueError
            emit(result.to_dict())
            return 0 if result.code == "stage_complete" else 2
        except Exception:
            emit({"ok": False, "code": "internal_error"})
            return 2
    if arguments.command == STAGE_EVALUATION_COMMAND:
        emit = dependencies.emit if dependencies is not None else _default_emit
        try:
            result = (stage_evaluation_runner or _default_stage_evaluation_runner)(arguments)
            if not isinstance(result, StageEvaluationResult):
                raise ValueError
            emit(result.to_dict())
            return 0 if result.code == "evaluation_stage_complete" else 2
        except Exception as error:
            emit({"ok": False, "code": _stage_evaluation_error_code(error)})
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
        "recovery_key", "manifest", "current_recovery_key", "new_recovery_key",
        "selection_manifest", "candidate_batch_root",
        "staging_dataset",
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


def execute_stage_knowledge_command(
    arguments: argparse.Namespace,
    *,
    source_factory: Callable[..., object],
    protector_factory: Callable[[], object],
    current_time: Callable[[], datetime],
    epoch_clock: Callable[[], int],
    project_root: Path,
    candidate_key_loader: Callable[..., object] = open_candidate_key,
    path_validator: Callable[..., object] = validate_stage_storage,
    batch_id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
) -> StageKnowledgeResult:
    selected = load_stage_selection_manifest(
        Path(arguments.selection_manifest), now=current_time()
    )
    path_validator(
        Path(arguments.candidate_batch_root), Path(arguments.vault), project_root
    )
    batch_id = batch_id_factory()
    with candidate_key_loader(
        Path(arguments.candidate_batch_root), protector_factory()
    ) as candidate_key:
        purge_expired_candidate_batches(
            Path(arguments.candidate_batch_root), candidate_key,
            clock=current_time,
        )
        with source_factory(
            Path(arguments.vault),
            authorization_id=arguments.authorization_id,
            account=arguments.account,
            expected_vault_id=selected.vault_id,
            expected_scope=selected.scope_fingerprint,
            window_start=selected.window_start,
            window_end=selected.window_end,
            project_root=project_root,
            clock=epoch_clock,
        ) as source:
            def read(record_id: str) -> object:
                selected.require_current(current_time())
                return source.read_one_record(record_id)

            def write(candidates: tuple[object, ...]) -> object:
                bound = tuple(
                    DetachedCandidate(
                        item.candidate_id, item.support_texts, source.evidence
                    )
                    for item in candidates
                )
                selected.require_current(current_time())
                candidate_ids = CandidateBatchStore(
                    Path(arguments.candidate_batch_root), candidate_key,
                    batch_id=batch_id, clock=current_time,
                ).write(bound)
                return CandidateBatchReceipt(batch_id, candidate_ids)

            return stage_knowledge(
                selected,
                read_one_record=read,
                deidentify=deidentify_private_text,
                scan_residuals=scan_residuals,
                write_encrypted_candidate_batch=write,
            )


def _default_stage_runner(arguments: argparse.Namespace) -> StageKnowledgeResult:
    from backend.mailbox_ingest.knowledge_stage_source import (
        open_knowledge_stage_source,
    )
    from backend.private_knowledge.dpapi import CurrentUserDpapiProtector

    return execute_stage_knowledge_command(
        arguments,
        source_factory=open_knowledge_stage_source,
        protector_factory=CurrentUserDpapiProtector,
        current_time=lambda: datetime.now(timezone.utc).replace(microsecond=0),
        epoch_clock=lambda: int(time.time()),
        project_root=Path(__file__).resolve().parents[1],
    )


def _default_stage_evaluation_runner(arguments: argparse.Namespace) -> StageEvaluationResult:
    from backend.mailbox_ingest.knowledge_stage_source import open_knowledge_stage_source

    return execute_stage_evaluation_command(
        arguments,
        source_factory=open_knowledge_stage_source,
        key_loader=_load_stage_evaluation_key,
        stage_writer=write_encrypted_stage,
        path_validator=_validate_external_stage_path,
        current_time=lambda: datetime.now(timezone.utc).replace(microsecond=0),
        epoch_clock=lambda: int(time.time()),
        project_root=Path(__file__).resolve().parents[1],
    )


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
