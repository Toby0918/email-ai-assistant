"""Administrator-only offline verification and private DeepSeek evaluation CLI."""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import json
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from backend.private_evaluation.dataset_builder import build_evaluation_dataset
from backend.private_evaluation.errors import PrivateEvaluationError
from backend.private_evaluation.reporting import (
    FLASH_MODEL,
    PRO_MODEL,
    AggregateReport,
    write_aggregate_report,
)
from backend.private_evaluation.repository import (
    read_encrypted_dataset,
    write_new_encrypted_dataset,
)
from backend.private_evaluation.runner import run_private_evaluation
from backend.private_evaluation.runner_values import UsefulnessJudgeView
from backend.private_evaluation.schema import EvaluationDatasetV1
from backend.private_evaluation.selection import (
    EvaluationSelection,
    derive_selection_key,
    select_private_cases,
)
from backend.private_evaluation.staging_repository import (
    read_encrypted_stage,
)
from backend.private_evaluation.staging_values import EvaluationStageV1
from backend.private_evaluation.terminal_judge import (
    make_interactive_judge,
    require_terminal_readiness,
    terminal_streams_available,
)


CONFIRMATION = "I_CONFIRM_200_FLASH_40_PRO"
_HELP_FLAGS = frozenset({"-h", "--help"})
_PURE_HELP_FORMS = frozenset(
    {(flag,) for flag in _HELP_FLAGS}
    | {(command, flag) for command in ("build", "verify", "run") for flag in _HELP_FLAGS}
)


class _SafeParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise PrivateEvaluationError("argument_invalid")


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationCliDependencies:
    key_loader: Callable[[], bytearray]
    read_stage: Callable[[Path, bytearray], EvaluationStageV1]
    build_dataset: Callable[[EvaluationStageV1], EvaluationDatasetV1]
    write_dataset: Callable[[Path, EvaluationDatasetV1, bytearray], None]
    read_dataset: Callable[[Path, bytearray], EvaluationDatasetV1]
    derive_selection_key: Callable[[bytearray, str], bytes]
    select_cases: Callable[[EvaluationDatasetV1, bytes | bytearray], EvaluationSelection]
    terminal_available: Callable[[], bool]
    readiness_check: Callable[[], None]
    judge_factory: Callable[[], Callable[[UsefulnessJudgeView], bool] | None]
    provider_configured: Callable[[], bool]
    client_factory: Callable[[str], Callable[..., str]]
    report_writer: Callable[[AggregateReport, Path], None]
    emit: Callable[[dict[str, object]], None]


def run_cli(
    argv: list[str] | None = None,
    *,
    dependencies: EvaluationCliDependencies | None = None,
) -> int:
    deps = dependencies or _default_dependencies()
    try:
        raw_arguments = list(sys.argv[1:] if argv is None else argv)
        if any(value in _HELP_FLAGS for value in raw_arguments) and tuple(
            raw_arguments
        ) not in _PURE_HELP_FORMS:
            raise PrivateEvaluationError("argument_invalid")
        arguments = _parser().parse_args(raw_arguments)
        if arguments.command == "build":
            dataset = _build_dataset_command(arguments, deps)
            deps.emit({"ok": True, "code": "dataset_built", "case_count": len(dataset.cases)})
            return 0
        if arguments.command == "run":
            _authorize_interactive_run(arguments, deps)
        dataset, selection = _local_preflight(Path(arguments.dataset), deps)
        if arguments.command == "verify":
            deps.emit({"ok": True, "code": "dataset_verified", "case_count": len(dataset.cases)})
            return 0
        judge = _load_judge(deps)
        _require_provider(deps)
        report = _evaluate(selection, judge, deps)
        deps.report_writer(report, Path(arguments.report))
        deps.emit({
            "ok": True, "status_code": report.status_code,
            "decision_code": report.decision_code,
        })
        return 0
    except PrivateEvaluationError as exc:
        deps.emit({"ok": False, "code": _public_error_code(exc.code)})
        return 2
    except Exception:
        deps.emit({"ok": False, "code": "dataset_unavailable"})
        return 2


def _parser() -> _SafeParser:
    parser = _SafeParser(
        prog="evaluate_private_deepseek.py", allow_abbrev=False
    )
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", allow_abbrev=False)
    build.add_argument("--staging", required=True)
    build.add_argument("--dataset", required=True)
    verify = commands.add_parser("verify", allow_abbrev=False)
    verify.add_argument("--dataset", required=True)
    run = commands.add_parser("run", allow_abbrev=False)
    run.add_argument("--dataset", required=True)
    run.add_argument("--report", required=True)
    run.add_argument("--confirm-private-evaluation")
    run.add_argument("--interactive-judge", action="store_true")
    return parser


def _build_dataset_command(
    arguments: argparse.Namespace,
    deps: EvaluationCliDependencies,
) -> EvaluationDatasetV1:
    master: bytearray | None = None
    selection_key: bytearray | None = None
    try:
        master = _load_key(deps)
        stage = deps.read_stage(Path(arguments.staging), master)
        dataset = deps.build_dataset(stage)
        selection_key = bytearray(
            deps.derive_selection_key(master, dataset.dataset_namespace)
        )
        deps.select_cases(dataset, selection_key)
        deps.write_dataset(Path(arguments.dataset), dataset, master)
        return dataset
    finally:
        _wipe(selection_key)
        _wipe(master)


def _local_preflight(
    path: Path, deps: EvaluationCliDependencies
) -> tuple[EvaluationDatasetV1, EvaluationSelection]:
    master: bytearray | None = None
    selection_key: bytearray | None = None
    try:
        master = _load_key(deps)
        dataset = deps.read_dataset(path, master)
        selection_key = bytearray(
            deps.derive_selection_key(master, dataset.dataset_namespace)
        )
        selection = deps.select_cases(dataset, selection_key)
        return dataset, selection
    finally:
        _wipe(selection_key)
        _wipe(master)


def _load_key(deps: EvaluationCliDependencies) -> bytearray:
    try:
        key = deps.key_loader()
    except PrivateEvaluationError:
        raise
    except (Exception, KeyboardInterrupt):
        raise PrivateEvaluationError("evaluation_key_unavailable") from None
    if type(key) is not bytearray or len(key) != 32:
        _wipe(key if type(key) is bytearray else None)
        raise PrivateEvaluationError("evaluation_key_unavailable")
    return key


def _authorize_interactive_run(
    arguments: argparse.Namespace,
    deps: EvaluationCliDependencies,
) -> None:
    if arguments.interactive_judge is not True:
        raise PrivateEvaluationError("human_judge_unavailable")
    if arguments.confirm_private_evaluation != CONFIRMATION:
        raise PrivateEvaluationError("operator_confirmation_required")
    try:
        available = deps.terminal_available()
    except Exception:
        available = False
    if available is not True:
        raise PrivateEvaluationError("human_judge_unavailable")
    try:
        deps.readiness_check()
    except PrivateEvaluationError:
        raise
    except (Exception, KeyboardInterrupt):
        raise PrivateEvaluationError("human_judge_failed") from None


def _load_judge(
    deps: EvaluationCliDependencies,
) -> Callable[[UsefulnessJudgeView], bool]:
    try:
        judge = deps.judge_factory()
    except Exception:
        judge = None
    if not callable(judge):
        raise PrivateEvaluationError("human_judge_unavailable")
    return judge


def _require_provider(deps: EvaluationCliDependencies) -> None:
    try:
        configured = deps.provider_configured()
    except Exception:
        configured = False
    if configured is not True:
        raise PrivateEvaluationError("provider_configuration_unavailable")


def _evaluate(
    selection: EvaluationSelection,
    judge: Callable[[UsefulnessJudgeView], bool],
    deps: EvaluationCliDependencies,
) -> AggregateReport:
    try:
        flash = deps.client_factory(FLASH_MODEL)
        pro = deps.client_factory(PRO_MODEL)
    except Exception:
        raise PrivateEvaluationError("provider_configuration_unavailable") from None
    report = run_private_evaluation(
        selection, flash_client=flash, pro_client=pro,
        usefulness_judge=judge,
    )
    return AggregateReport.from_mapping(report.to_mapping())


def _load_live_key(*, getpass_fn: Callable[[str], str] = getpass.getpass) -> bytearray:
    encoded = ""
    try:
        encoded = getpass_fn("Private evaluation key (base64, hidden): ")
        decoded = base64.b64decode(encoded.encode("ascii"), validate=True)
        if len(decoded) != 32:
            raise ValueError
        return bytearray(decoded)
    except (
        UnicodeError, ValueError, binascii.Error, EOFError, OSError,
        KeyboardInterrupt,
    ):
        raise PrivateEvaluationError("evaluation_key_unavailable") from None
    finally:
        encoded = ""


def _provider_configured() -> bool:
    try:
        from backend.email_agent.config import load_config

        config = load_config()
        return config.llm_provider == "deepseek" and bool(config.deepseek_api_key)
    except Exception:
        return False


def _live_client_factory(model: str) -> Callable[..., str]:
    if model not in {FLASH_MODEL, PRO_MODEL}:
        raise PrivateEvaluationError("provider_configuration_unavailable")
    from backend.email_agent.config import load_config
    from backend.email_agent.llm_client import generate_analysis

    config = replace(load_config(), deepseek_model=model)
    if config.llm_provider != "deepseek" or not config.deepseek_api_key:
        raise PrivateEvaluationError("provider_configuration_unavailable")

    def client(prompt: str, **options: object) -> str:
        _validate_live_options(model, options)
        return generate_analysis(
            prompt, system_prompt=str(options["system_prompt"]),
            config=config, timeout_seconds=10.0,
        )

    return client


def _validate_live_options(model: str, options: dict[str, object]) -> None:
    expected = {
        "model": model, "response_format": "json_object", "temperature": 0,
        "stream": False, "max_tokens": 2400, "thinking": False,
        "max_retries": 0, "timeout_seconds": 10.0,
    }
    if set(options) != set(expected) | {"system_prompt"}:
        raise PrivateEvaluationError("provider_configuration_unavailable")
    if type(options["system_prompt"]) is not str:
        raise PrivateEvaluationError("provider_configuration_unavailable")
    for name, value in expected.items():
        if type(value) is not type(options[name]) or options[name] != value:
            raise PrivateEvaluationError("provider_configuration_unavailable")


def _default_dependencies() -> EvaluationCliDependencies:
    return EvaluationCliDependencies(
        key_loader=_load_live_key, read_stage=read_encrypted_stage,
        build_dataset=build_evaluation_dataset,
        write_dataset=write_new_encrypted_dataset,
        read_dataset=read_encrypted_dataset,
        derive_selection_key=derive_selection_key, select_cases=select_private_cases,
        terminal_available=_terminal_available, readiness_check=_readiness_check,
        judge_factory=_judge_factory,
        provider_configured=_provider_configured,
        client_factory=_live_client_factory, report_writer=write_aggregate_report,
        emit=_emit_json,
    )


def _terminal_available() -> bool:
    return terminal_streams_available(sys.stdin, sys.stdout)


def _readiness_check() -> None:
    require_terminal_readiness(sys.stdin, sys.stdout)


def _judge_factory() -> Callable[[UsefulnessJudgeView], bool]:
    return make_interactive_judge(sys.stdin, sys.stdout)


def _emit_json(value: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=True, sort_keys=True) + "\n")


def _public_error_code(code: object) -> str:
    allowed = {
        "argument_invalid", "operator_confirmation_required", "dataset_unavailable",
        "evaluation_key_unavailable", "dataset_decrypt_invalid",
        "dataset_schema_invalid", "dataset_case_count_invalid",
        "dataset_strata_incomplete", "pair_approval_insufficient",
        "provider_configuration_unavailable", "human_judge_unavailable",
        "human_judge_failed", "aggregate_serialization_violation",
        "evaluation_stage_unavailable", "evaluation_stage_decrypt_invalid",
        "evaluation_stage_schema_invalid",
    }
    return code if type(code) is str and code in allowed else "dataset_unavailable"


def _wipe(value: bytearray | None) -> None:
    if value is not None:
        for index in range(len(value)):
            value[index] = 0


def main() -> int:
    return run_cli()


if __name__ == "__main__":
    raise SystemExit(main())
