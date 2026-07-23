"""Manage the local first-version assistant debug service."""

from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.email_agent import attachment_storage
from backend.email_agent import config as backend_config
from backend.email_agent.managed_runtime import (
    managed_failure_code,
    prepare_managed_runtime,
)
from backend.email_agent.server import validate_local_server_host
from backend.email_agent.standalone_verification import (
    prepare_standalone_runtime,
)


DEFAULT_PID_FILE = ROOT / "outputs" / "local_debug_service.pid"
DEFAULT_LOG_FILE = ROOT / "outputs" / "local_debug_service.log"
COMMANDS = ("start", "stop", "restart", "status", "health", "analysis")
CLEANUP_FAILURE_MESSAGE = (
    "Attachment cleanup failed. Check the configured temporary directory and permissions, then retry."
)
MANAGED_FAILURE_EXIT_CODE = 8


@dataclass(frozen=True)
class ServiceConfig:
    host: str
    port: int
    database: str | None
    pid_file: Path
    root: Path
    python_executable: str
    startup_timeout: float
    poll_interval: float
    log_file: Path = DEFAULT_LOG_FILE
    attachment_temp_dir: Path = ROOT / "outputs" / "attachment_temp"
    standalone_state_root: Path | None = None
    operational_config: backend_config.AppConfig | None = None
    managed_container: bool = False


@dataclass(frozen=True)
class CommandResult:
    exit_code: int
    message: str
    status: str | None = None


@dataclass(frozen=True)
class CleanupResult:
    removed_count: int


class LifecycleCleanupError(RuntimeError):
    """Raised when lifecycle cleanup cannot complete safely."""


HealthChecker = Callable[[str, int, float], bool]
Sleeper = Callable[[float], None]


def run_cleanup_before_service_start(
    config: backend_config.AppConfig | None = None,
) -> CleanupResult:
    """Run bounded attachment expiry cleanup without exposing source details."""
    try:
        storage_config = config or backend_config.load_config()
        removed_count = attachment_storage.cleanup_expired_attachments(storage_config)
    except Exception:
        raise LifecycleCleanupError(CLEANUP_FAILURE_MESSAGE) from None
    return CleanupResult(removed_count=removed_count)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the local email AI assistant service.")
    parser.add_argument("command", choices=COMMANDS)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--database", default=None)
    parser.add_argument("--pid-file", default=str(DEFAULT_PID_FILE))
    parser.add_argument("--startup-timeout", type=float, default=10.0)
    parser.add_argument("--poll-interval", type=float, default=0.25)
    parser.add_argument("--standalone-state-root", default=None)
    parser.add_argument("--managed-container", action="store_true")
    return parser


def config_from_args(args: argparse.Namespace) -> ServiceConfig:
    standalone_state_root = getattr(args, "standalone_state_root", None)
    managed_container = bool(getattr(args, "managed_container", False))
    if managed_container:
        if (
            standalone_state_root is not None
            or args.database is not None
            or Path(args.pid_file) != DEFAULT_PID_FILE
        ):
            raise ValueError(
                "operational paths are derived from managed placement"
            )
        runtime = prepare_managed_runtime(
            repository_root=ROOT,
            project_container=ROOT.parent,
        )
        return ServiceConfig(
            host=validate_local_server_host(args.host),
            port=args.port,
            database=str(runtime.database_path),
            pid_file=runtime.pid_file,
            root=runtime.placement.repository_root,
            python_executable=str(runtime.python_executable),
            startup_timeout=args.startup_timeout,
            poll_interval=args.poll_interval,
            log_file=runtime.log_file,
            attachment_temp_dir=runtime.attachment_temp_dir,
            operational_config=runtime.config,
            managed_container=True,
        )
    if standalone_state_root is not None:
        if args.database is not None or Path(args.pid_file) != DEFAULT_PID_FILE:
            raise ValueError(
                "operational paths are derived from standalone state root"
            )
        runtime = prepare_standalone_runtime(
            repository_root=ROOT,
            state_root=Path(standalone_state_root),
        )
        return ServiceConfig(
            host=validate_local_server_host(args.host),
            port=args.port,
            database=str(runtime.database_path),
            pid_file=runtime.pid_file,
            root=ROOT,
            python_executable=sys.executable,
            startup_timeout=args.startup_timeout,
            poll_interval=args.poll_interval,
            log_file=runtime.log_file,
            attachment_temp_dir=runtime.attachment_temp_dir,
            standalone_state_root=runtime.state_root,
            operational_config=runtime.config,
        )
    return ServiceConfig(
        host=validate_local_server_host(args.host),
        port=args.port,
        database=args.database,
        pid_file=Path(args.pid_file),
        root=ROOT,
        python_executable=sys.executable,
        startup_timeout=args.startup_timeout,
        poll_interval=args.poll_interval,
    )


def check_health(host: str, port: int, timeout: float = 1.0) -> bool:
    safe_host = validate_local_server_host(host)
    url = f"http://{safe_host}:{port}/api/health"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def status_service(
    config: ServiceConfig,
    health_checker: HealthChecker = check_health,
) -> CommandResult:
    validate_local_server_host(config.host)
    pid = _read_pid(config.pid_file)
    healthy = health_checker(config.host, config.port, 1.0)
    if healthy and pid is not None:
        return CommandResult(0, f"running pid={pid} url={_service_url(config)}", "running")
    if healthy:
        return CommandResult(4, f"unknown running service at {_service_url(config)}", "unknown")
    if pid is not None:
        return CommandResult(3, f"stopped with stale pid={pid}", "stopped")
    return CommandResult(3, "stopped", "stopped")


def health_service(
    config: ServiceConfig,
    health_checker: HealthChecker = check_health,
) -> CommandResult:
    validate_local_server_host(config.host)
    if health_checker(config.host, config.port, 1.0):
        return CommandResult(
            0,
            f"healthy url={_service_url(config)}",
            "healthy",
        )
    return CommandResult(3, "unhealthy", "unhealthy")


AnalysisRequester = Callable[
    [str, int, dict[str, object], float],
    dict[str, object],
]


def analyze_synthetic_email(
    config: ServiceConfig,
    requester: AnalysisRequester | None = None,
) -> CommandResult:
    validate_local_server_host(config.host)
    if (
        config.operational_config is None
    ):
        return CommandResult(7, "standalone state required", "error")
    request_analysis = requester or _request_synthetic_analysis
    response = request_analysis(
        config.host,
        config.port,
        _synthetic_analysis_payload(),
        10.0,
    )
    analysis = response.get("analysis")
    engine = analysis.get("analysis_engine") if isinstance(analysis, dict) else None
    source = engine.get("source") if isinstance(engine, dict) else None
    saved_id = response.get("saved_id")
    if (
        response.get("ok") is True
        and source == "rule_fallback"
        and type(saved_id) is int
        and saved_id > 0
    ):
        return CommandResult(0, "synthetic analysis ok", "ok")
    return CommandResult(6, "synthetic analysis failed", "error")


def start_service(
    config: ServiceConfig,
    popen: Callable[..., Any] | None = None,
    health_checker: HealthChecker = check_health,
    sleeper: Sleeper = time.sleep,
) -> CommandResult:
    validate_local_server_host(config.host)
    if health_checker(config.host, config.port, 1.0):
        return CommandResult(0, f"already running at {_service_url(config)}", "running")

    cleanup_result, cleanup_error = _attempt_lifecycle_cleanup(config)
    if cleanup_error is not None:
        return cleanup_error
    result = _start_after_cleanup(config, popen, health_checker, sleeper)
    return _with_cleanup_result(result, cleanup_result)


def _start_after_cleanup(
    config: ServiceConfig,
    popen: Callable[..., Any] | None = None,
    health_checker: HealthChecker = check_health,
    sleeper: Sleeper = time.sleep,
) -> CommandResult:
    validate_local_server_host(config.host)
    command = _build_start_command(config)
    config.pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid = _launch_background(command, config, popen)
    _write_pid(config.pid_file, pid)

    if _wait_until_healthy(config, health_checker, sleeper):
        return CommandResult(0, f"started pid={pid} url={_service_url(config)}", "running")
    return CommandResult(2, f"started pid={pid} but health check failed", "unknown")


def stop_service(
    config: ServiceConfig,
    health_checker: HealthChecker = check_health,
    killer: Callable[[int], None] | None = None,
    sleeper: Sleeper = time.sleep,
) -> CommandResult:
    validate_local_server_host(config.host)
    pid = _read_pid(config.pid_file)
    if pid is None:
        return _stop_without_pid(config, health_checker)
    if not health_checker(config.host, config.port, 1.0):
        _remove_pid(config.pid_file)
        return CommandResult(0, f"removed stale pid={pid}", "stopped")

    process_killer = killer or _kill_process
    process_killer(pid)
    _wait_until_stopped(config, health_checker, sleeper)
    _remove_pid(config.pid_file)
    return CommandResult(0, f"stopped pid={pid}", "stopped")


def restart_service(
    config: ServiceConfig,
    stopper: Callable[[ServiceConfig], CommandResult] = stop_service,
    popen: Callable[..., Any] | None = None,
    health_checker: HealthChecker = check_health,
    sleeper: Sleeper = time.sleep,
) -> CommandResult:
    validate_local_server_host(config.host)
    cleanup_result, cleanup_error = _attempt_lifecycle_cleanup(config)
    if cleanup_error is not None:
        return cleanup_error
    stop_result = stopper(config)
    if stop_result.exit_code not in {0, 3}:
        return _with_cleanup_result(stop_result, cleanup_result)
    start_result = _start_after_cleanup(config, popen, health_checker, sleeper)
    return _with_cleanup_result(start_result, cleanup_result)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.managed_container:
        return _run_managed_entry(args)
    config = config_from_args(args)
    result = _dispatch(args.command, config)
    print(result.message)
    return result.exit_code


def _run_managed_entry(args: argparse.Namespace) -> int:
    try:
        config = config_from_args(args)
        result = _dispatch(args.command, config)
    except Exception as error:
        print(managed_failure_code(error), file=sys.stderr)
        return MANAGED_FAILURE_EXIT_CODE
    print(result.message)
    return result.exit_code


def _dispatch(command: str, config: ServiceConfig) -> CommandResult:
    if command == "start":
        return start_service(config)
    if command == "stop":
        return stop_service(config)
    if command == "restart":
        return restart_service(config)
    if command == "health":
        return health_service(config)
    if command == "analysis":
        return analyze_synthetic_email(config)
    return status_service(config)


def _attempt_lifecycle_cleanup(
    service_config: ServiceConfig,
) -> tuple[CleanupResult, None] | tuple[None, CommandResult]:
    try:
        cleanup_config = service_config.operational_config
        return run_cleanup_before_service_start(cleanup_config), None
    except LifecycleCleanupError:
        return None, CommandResult(5, CLEANUP_FAILURE_MESSAGE, "error")


def _with_cleanup_result(result: CommandResult, cleanup_result: CleanupResult | None) -> CommandResult:
    if cleanup_result is None:
        return result
    message = f"attachment cleanup removed={cleanup_result.removed_count}; {result.message}"
    return CommandResult(result.exit_code, message, result.status)


def _build_start_command(config: ServiceConfig) -> list[str]:
    command = [
        config.python_executable,
        "-B",
        str(config.root / "scripts" / "run_local_debug.py"),
        "--host",
        config.host,
        "--port",
        str(config.port),
    ]
    if config.managed_container:
        command.append("--managed-container")
    elif config.standalone_state_root is not None:
        command.extend([
            "--standalone-state-root",
            str(config.standalone_state_root),
        ])
    elif config.database:
        command.extend(["--database", config.database])
    return command


def _launch_background(
    command: list[str],
    config: ServiceConfig,
    popen: Callable[..., Any] | None,
) -> int:
    if popen is not None:
        return _launch_with_popen(command, config, popen)
    if os.name == "nt":
        return _launch_with_powershell(command, config)
    return _launch_with_popen(command, config, subprocess.Popen)


def _launch_with_popen(
    command: list[str],
    config: ServiceConfig,
    popen: Callable[..., Any],
) -> int:
    with _log_handle(config.log_file) as log_handle:
        process = popen(
            command,
            cwd=str(config.root),
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            **_background_kwargs(),
        )
    return int(process.pid)


def _launch_with_powershell(command: list[str], config: ServiceConfig) -> int:
    config.log_file.parent.mkdir(parents=True, exist_ok=True)
    command_line = subprocess.list2cmdline(command)
    script = (
        "$ErrorActionPreference = 'Stop'; "
        "$startup = ([wmiclass]'Win32_ProcessStartup').CreateInstance(); "
        "$startup.ShowWindow = 0; "
        "$result = ([wmiclass]'Win32_Process').Create("
        f"{_ps_literal(command_line)}, {_ps_literal(str(config.root))}, $startup); "
        "if ($result.ReturnValue -ne 0) { "
        "throw \"Win32_Process.Create failed code $($result.ReturnValue)\" "
        "}; "
        "Write-Output $result.ProcessId"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
        cwd=str(config.root),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "PowerShell Start-Process failed.")
    return int(result.stdout.strip().splitlines()[-1])


def _wait_until_healthy(
    config: ServiceConfig,
    health_checker: HealthChecker,
    sleeper: Sleeper,
) -> bool:
    deadline = time.monotonic() + config.startup_timeout
    while time.monotonic() <= deadline:
        if health_checker(config.host, config.port, 1.0):
            return True
        sleeper(config.poll_interval)
    return False


def _wait_until_stopped(
    config: ServiceConfig,
    health_checker: HealthChecker,
    sleeper: Sleeper,
) -> None:
    deadline = time.monotonic() + config.startup_timeout
    while time.monotonic() <= deadline:
        if not health_checker(config.host, config.port, 1.0):
            return
        sleeper(config.poll_interval)


def _stop_without_pid(config: ServiceConfig, health_checker: HealthChecker) -> CommandResult:
    if health_checker(config.host, config.port, 1.0):
        return CommandResult(4, "service is running but has no managed pid file", "unknown")
    return CommandResult(3, "stopped", "stopped")


def _read_pid(pid_file: Path) -> int | None:
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except ValueError:
        return None
    return pid if pid > 0 else None


def _write_pid(pid_file: Path, pid: int) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(pid), encoding="utf-8")


def _remove_pid(pid_file: Path) -> None:
    try:
        pid_file.unlink()
    except FileNotFoundError:
        return


def _service_url(config: ServiceConfig) -> str:
    return f"http://{config.host}:{config.port}"


def _synthetic_analysis_payload() -> dict[str, object]:
    return {
        "user_confirmed": True,
        "subject": "Synthetic delivery question",
        "from": "buyer@example.test",
        "to": ["sales@example.test"],
        "body_text": "Can you confirm a synthetic delivery window?",
    }


def _request_synthetic_analysis(
    host: str,
    port: int,
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    request = urllib.request.Request(
        f"http://{host}:{port}/api/analyze-current-email",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except (
        json.JSONDecodeError,
        OSError,
        UnicodeDecodeError,
        urllib.error.URLError,
    ):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _log_handle(log_file: Path) -> Any:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    return log_file.open("ab")


def _background_kwargs() -> dict[str, Any]:
    if os.name == "nt":
        return {
            "creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
        }
    return {"start_new_session": True}


def _kill_process(pid: int) -> None:
    os.kill(pid, signal.SIGTERM)


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


if __name__ == "__main__":
    raise SystemExit(main())
