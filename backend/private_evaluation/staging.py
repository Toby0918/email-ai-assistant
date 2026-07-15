"""One-record-at-a-time orchestration for encrypted evaluation staging."""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
from datetime import datetime
from pathlib import Path
from typing import Callable

from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.residual_scanner import scan_residuals

from .errors import PrivateEvaluationError
from .schema import EvaluationCaseV1
from .staging_contract import (
    StageEvaluationCaseSelection,
    StageEvaluationResult,
    StageEvaluationSelection,
    load_stage_evaluation_manifest,
)


def stage_evaluation(
    selection: object,
    *,
    read_one_record: Callable[[str], object],
    deidentify: Callable[[str, object], object],
    scan_residuals: Callable[[object], object],
    write_encrypted_stage: Callable[[tuple[EvaluationCaseV1, ...]], object],
) -> StageEvaluationResult:
    selected = StageEvaluationSelection.from_value(selection)
    cases: list[EvaluationCaseV1] = []
    try:
        for item in selected.cases:
            case = _stage_one_case(
                item,
                read_one_record=read_one_record,
                deidentify=deidentify,
                scan_residuals=scan_residuals,
            )
            if case is None:
                return StageEvaluationResult(
                    "evaluation_stage_residual_blocked", 0, 200
                )
            cases.append(case)
        written = write_encrypted_stage(tuple(cases))
        if written is not None:
            raise ValueError
        return StageEvaluationResult("evaluation_stage_complete", 200, 0)
    except Exception:
        return StageEvaluationResult("evaluation_stage_callback_failed", 0, 200)


def _stage_one_case(
    item: StageEvaluationCaseSelection,
    *,
    read_one_record: Callable[[str], object],
    deidentify: Callable[[str, object], object],
    scan_residuals: Callable[[object], object],
) -> EvaluationCaseV1 | None:
    with read_one_record(item.record_id) as raw:
        text = getattr(raw, "text")
        context = getattr(raw, "context")
        if not isinstance(text, str):
            raise ValueError
        with deidentify(text, context) as deidentified:
            findings = scan_residuals(deidentified)
            if not isinstance(findings, tuple):
                raise ValueError
            if findings:
                return None
            return item.build_case(deidentified.text)


def execute_stage_evaluation_command(
    arguments: argparse.Namespace,
    *,
    source_factory: Callable[..., object],
    key_loader: Callable[[], bytearray],
    stage_writer: Callable[[Path, tuple[object, ...], bytearray], None],
    path_validator: Callable[[Path], Path],
    current_time: Callable[[], datetime],
    epoch_clock: Callable[[], int],
    project_root: Path,
) -> StageEvaluationResult:
    selected = load_stage_evaluation_manifest(
        Path(arguments.selection_manifest), now=current_time()
    )
    target = path_validator(Path(arguments.staging_dataset))
    key: bytearray | None = None
    try:
        key = key_loader()
        if type(key) is not bytearray or len(key) != 32:
            raise PrivateEvaluationError("evaluation_key_unavailable")
        return _stage_from_source(
            arguments, selected, target, key, source_factory=source_factory,
            stage_writer=stage_writer, current_time=current_time,
            epoch_clock=epoch_clock, project_root=project_root,
        )
    finally:
        _wipe_secret(key)


def _stage_from_source(
    arguments: argparse.Namespace,
    selected: StageEvaluationSelection,
    target: Path,
    key: bytearray,
    *,
    source_factory: Callable[..., object],
    stage_writer: Callable[[Path, tuple[object, ...], bytearray], None],
    current_time: Callable[[], datetime],
    epoch_clock: Callable[[], int],
    project_root: Path,
) -> StageEvaluationResult:
    try:
        with source_factory(
            Path(arguments.vault), authorization_id=arguments.authorization_id,
            account=arguments.account, expected_vault_id=selected.vault_id,
            expected_scope=selected.scope_fingerprint,
            window_start=selected.window_start, window_end=selected.window_end,
            project_root=project_root, clock=epoch_clock,
        ) as source:
            def read(record_id: str) -> object:
                selected.require_current(current_time())
                return source.read_one_record(record_id)

            def write(cases: tuple[object, ...]) -> None:
                selected.require_current(current_time())
                stage_writer(target, cases, key)

            return stage_evaluation(
                selected, read_one_record=read,
                deidentify=deidentify_private_text, scan_residuals=scan_residuals,
                write_encrypted_stage=write,
            )
    except Exception:
        return StageEvaluationResult("evaluation_stage_callback_failed", 0, 200)


def load_stage_evaluation_key(
    *,
    getpass_fn: Callable[[str], str] = getpass.getpass,
) -> bytearray:
    encoded = ""
    try:
        encoded = getpass_fn(
            "Private evaluation staging key (base64, hidden): "
        )
        decoded = base64.b64decode(encoded.encode("ascii"), validate=True)
        if len(decoded) != 32:
            raise ValueError
        return bytearray(decoded)
    except (UnicodeError, ValueError, binascii.Error):
        raise PrivateEvaluationError("evaluation_key_unavailable") from None
    finally:
        encoded = ""


def _wipe_secret(value: bytearray | None) -> None:
    if value is not None:
        for index in range(len(value)):
            value[index] = 0
