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

from backend.private_evaluation.errors import PrivateEvaluationError
from backend.private_evaluation.reporting import (
    FLASH_MODEL,
    PRO_MODEL,
    AggregateReport,
    write_aggregate_report,
)
from backend.private_evaluation.repository import read_encrypted_dataset
from backend.private_evaluation.runner import run_private_evaluation
from backend.private_evaluation.schema import EvaluationDatasetV1
from backend.private_evaluation.selection import (
    EvaluationSelection,
    derive_selection_key,
    select_private_cases,
)


CONFIRMATION = "I_CONFIRM_200_FLASH_40_PRO"


class _SafeParser(argparse.ArgumentParser):
    def error(self, _message: str) -> None:
        raise PrivateEvaluationError("argument_invalid")


@dataclass(frozen=True, slots=True, repr=False)
class EvaluationCliDependencies:
    key_loader: Callable[[], bytearray]
    read_dataset: Callable[[Path, bytearray], EvaluationDatasetV1]
    derive_selection_key: Callable[[bytearray, str], bytes]
    select_cases: Callable[[EvaluationDatasetV1, bytes | bytearray], EvaluationSelection]
    provider_configured: Callable[[], bool]
    usefulness_judge: Callable[[object], bool] | None
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
        arguments = _parser().parse_args(argv)
        dataset, selection = _local_preflight(Path(arguments.dataset), deps)
        if arguments.command == "verify":
            deps.emit({"ok": True, "code": "dataset_verified", "case_count": len(dataset.cases)})
            return 0
        _authorize_run(arguments, deps)
        report = _evaluate(selection, deps)
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
    parser = _SafeParser(add_help=False, allow_abbrev=False)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", add_help=False, allow_abbrev=False)
    verify.add_argument("--dataset", required=True)
    run = commands.add_parser("run", add_help=False, allow_abbrev=False)
    run.add_argument("--dataset", required=True)
    run.add_argument("--report", required=True)
    run.add_argument("--confirm-private-evaluation", required=True)
    return parser


def _local_preflight(
    path: Path, deps: EvaluationCliDependencies
) -> tuple[EvaluationDatasetV1, EvaluationSelection]:
    master: bytearray | None = None
    selection_key: bytearray | None = None
    try:
        master = deps.key_loader()
        if type(master) is not bytearray or len(master) != 32:
            raise PrivateEvaluationError("evaluation_key_unavailable")
        dataset = deps.read_dataset(path, master)
        selection_key = bytearray(
            deps.derive_selection_key(master, dataset.dataset_namespace)
        )
        selection = deps.select_cases(dataset, selection_key)
        return dataset, selection
    finally:
        _wipe(selection_key)
        _wipe(master)


def _authorize_run(arguments: argparse.Namespace, deps: EvaluationCliDependencies) -> None:
    if arguments.confirm_private_evaluation != CONFIRMATION:
        raise PrivateEvaluationError("operator_confirmation_required")
    try:
        configured = deps.provider_configured()
    except Exception:
        configured = False
    if configured is not True:
        raise PrivateEvaluationError("provider_configuration_unavailable")
    if not callable(deps.usefulness_judge):
        raise PrivateEvaluationError("human_judge_unavailable")


def _evaluate(selection: EvaluationSelection, deps: EvaluationCliDependencies) -> AggregateReport:
    try:
        flash = deps.client_factory(FLASH_MODEL)
        pro = deps.client_factory(PRO_MODEL)
    except Exception:
        raise PrivateEvaluationError("provider_configuration_unavailable") from None
    report = run_private_evaluation(
        selection, flash_client=flash, pro_client=pro,
        usefulness_judge=deps.usefulness_judge,
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
    except (UnicodeError, ValueError, binascii.Error):
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
        key_loader=_load_live_key, read_dataset=read_encrypted_dataset,
        derive_selection_key=derive_selection_key, select_cases=select_private_cases,
        provider_configured=_provider_configured, usefulness_judge=None,
        client_factory=_live_client_factory, report_writer=write_aggregate_report,
        emit=_emit_json,
    )


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
