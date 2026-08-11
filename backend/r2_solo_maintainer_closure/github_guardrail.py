"""Fixed authenticated read-only GitHub guardrail observation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
import subprocess
import threading
from typing import Callable

from ._canonical import canonical_json, strict_object
from .contracts import ClosureErrorCode, SoloMaintainerClosureError
from .hosted_evidence import (
    GitHubGuardrailSnapshotV1,
    normalize_ruleset_configuration,
    ruleset_configuration_v1,
)
_GH_EXECUTABLE = r"C:\Program Files\GitHub CLI\gh.exe"
_HOST = "github.com"
_LOGIN = "Toby0918"
_REPOSITORY = "Toby0918/email-ai-assistant"
_LISTING_PATH = (
    f"/repos/{_REPOSITORY}/rulesets?ref=refs/heads/master"
    "&includes_parents=false&per_page=100"
)
_CLASSIC_PATH = f"/repos/{_REPOSITORY}/branches/master/protection"
_CLASSIC_MISSING_STDERR = b"gh: Branch not protected (HTTP 404)\n"
_AUTH_COMMAND = (
    _GH_EXECUTABLE, "auth", "status", "--active", "--hostname", _HOST,
    "--json", "hosts",
)
_API_PREFIX = (
    _GH_EXECUTABLE, "api", "--hostname", _HOST, "--method", "GET",
    "--include", "--header", "Accept:application/vnd.github+json",
)
_SAFE_ENVIRONMENT_KEYS = (
    "APPDATA", "COMSPEC", "HOMEDRIVE", "HOMEPATH", "LOCALAPPDATA", "PATHEXT",
    "PROGRAMDATA", "SYSTEMDRIVE", "SYSTEMROOT", "TEMP", "TMP", "USERPROFILE", "WINDIR",
)
_MAX_OUTPUT = 1024 * 1024
_TIMEOUT_SECONDS = 15
_MISSING = object()
_Runner = Callable[
    [tuple[str, ...], dict[str, str]],
    subprocess.CompletedProcess[bytes],
]

@dataclass(frozen=True, slots=True, repr=False)
class _GuardrailObservation:
    listing: object
    detail: object
    classic_branch_protection_present: object

@dataclass(frozen=True, slots=True, repr=False)
class _AuthIdentity:
    host: str
    login: str
    token_source: str
    git_protocol: str

class _GhGuardrailReadAdapter:
    """Use only the fixed GitHub CLI/keyring identity and fixed GET requests."""

    __slots__ = ("_runner",)

    def __init__(self, runner: _Runner | None = None) -> None:
        self._runner = _run_process if runner is None else runner

    def read(self) -> _GuardrailObservation:
        before = self._auth_identity()
        listing = self._api_json(_LISTING_PATH)
        ruleset_id = _ruleset_id(listing)
        detail = self._api_json(f"/repos/{_REPOSITORY}/rulesets/{ruleset_id}")
        classic = self._api_json(_CLASSIC_PATH, allow_classic_missing=True)
        after = self._auth_identity()
        if before != after:
            _reject()
        return _GuardrailObservation(listing, detail, classic is not _MISSING)

    def _auth_identity(self) -> _AuthIdentity:
        result = self._execute(_AUTH_COMMAND)
        if result.returncode != 0 or result.stderr:
            _reject()
        value = _decode_json(result.stdout)
        hosts = value.get("hosts") if type(value) is dict else None
        entries = hosts.get(_HOST) if type(hosts) is dict else None
        entry = entries[0] if type(entries) is list and len(entries) == 1 else None
        if (type(entry) is not dict or entry.get("state") != "success"
                or entry.get("active") is not True or entry.get("host") != _HOST
                or entry.get("login") != _LOGIN or entry.get("tokenSource") != "keyring"
                or entry.get("gitProtocol") != "https"):
            _reject()
        return _AuthIdentity(_HOST, _LOGIN, "keyring", "https")

    def _api_json(self, path: str, *, allow_classic_missing: bool = False) -> object:
        detail_prefix = f"/repos/{_REPOSITORY}/rulesets/"
        detail_id = path[len(detail_prefix):] if type(path) is str and path.startswith(detail_prefix) else ""
        approved = (path in (_LISTING_PATH, _CLASSIC_PATH)
                    or (detail_id.isascii() and detail_id.isdigit()
                        and not detail_id.startswith("0")))
        if (not approved
                or allow_classic_missing is not (path == _CLASSIC_PATH)):
            _reject()
        result = self._execute((*_API_PREFIX, path))
        status, body = _split_api_response(result.stdout)
        if (allow_classic_missing and status == 404 and result.returncode == 1
                and result.stderr == _CLASSIC_MISSING_STDERR):
            return _MISSING
        if status != 200 or result.returncode != 0 or result.stderr:
            _reject()
        return _decode_json(body)

    def _execute(self, arguments: tuple[str, ...]) -> subprocess.CompletedProcess[bytes]:
        try:
            result = self._runner(arguments, _child_environment())
        except Exception:
            _reject()
        if (type(result) is not subprocess.CompletedProcess
                or type(result.returncode) is not int
                or type(result.stdout) is not bytes or type(result.stderr) is not bytes
                or not result.stdout or len(result.stdout) > _MAX_OUTPUT
                or len(result.stderr) > _MAX_OUTPUT):
            _reject()
        return result

def collect_verified_guardrail(reader: object = None) -> GitHubGuardrailSnapshotV1:
    """Return the unchanged canonical snapshot or one fixed guardrail failure."""
    try:
        adapter = _GhGuardrailReadAdapter() if reader is None else reader
        observation = adapter.read()
        if (type(observation) is not _GuardrailObservation
                or observation.classic_branch_protection_present is not False):
            _reject()
        ruleset_id = _ruleset_id(observation.listing)
        configuration = _normalize_guardrail_detail(observation.detail)
        if configuration != ruleset_configuration_v1():
            _reject()
        return GitHubGuardrailSnapshotV1.create(
            ruleset_id=ruleset_id,
            ruleset_configuration=configuration,
        )
    except SoloMaintainerClosureError:
        raise SoloMaintainerClosureError(
            ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED
        ) from None
    except Exception:
        raise SoloMaintainerClosureError(
            ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED
        ) from None

def _ruleset_id(listing: object) -> int:
    item = listing[0] if type(listing) is list and len(listing) == 1 else None
    ruleset_id = item.get("id") if type(item) is dict else None
    if (type(ruleset_id) is not int or ruleset_id < 1
            or item.get("target") != "branch" or item.get("enforcement") != "active"
            or item.get("name") != "master-solo-maintainer-closure-v1"):
        _reject()
    return ruleset_id

def _normalize_guardrail_detail(detail: object) -> dict[str, object]:
    projected = normalize_ruleset_configuration(detail)
    rules = projected.get("rules")
    if (type(projected.get("bypass_actors")) is not list
            or projected["bypass_actors"] != [] or type(rules) is not list):
        _reject()
    pull_indices = tuple(
        index for index, rule in enumerate(rules)
        if type(rule) is dict and rule.get("type") == "pull_request"
    )
    if len(pull_indices) != 1:
        _reject()
    parameters = rules[pull_indices[0]].get("parameters")
    if (type(parameters) is not dict
            or ("required_reviewers" in parameters
                and (type(parameters["required_reviewers"]) is not list
                     or parameters["required_reviewers"] != []))):
        _reject()
    configuration = strict_object(canonical_json(projected))
    configuration["rules"][pull_indices[0]]["parameters"].pop("required_reviewers", None)
    return configuration

def _child_environment() -> dict[str, str]:
    environment = {}
    for name in _SAFE_ENVIRONMENT_KEYS:
        value = os.environ.get(name)
        if type(value) is str and value:
            environment[name] = value
    environment.update({
        "GH_PROMPT_DISABLED": "1", "GH_NO_UPDATE_NOTIFIER": "1",
        "GH_NO_EXTENSION_UPDATE_NOTIFIER": "1", "GH_TELEMETRY": "0",
        "DO_NOT_TRACK": "1", "NO_COLOR": "1", "LC_ALL": "C", "LANG": "C",
    })
    return environment

def _run_process(
    arguments: tuple[str, ...], environment: dict[str, str],
) -> subprocess.CompletedProcess[bytes]:
    process = None
    streams = ()
    threads = ()
    output: list[object] = [None, None]
    try:
        process = subprocess.Popen(
            arguments, env=environment, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
        )
        if process.stdout is None or process.stderr is None:
            _reject()
        streams = (process.stdout, process.stderr)
        threads = tuple(
            threading.Thread(
                target=_read_stream, args=(stream, process, output, index), daemon=True,
            )
            for index, stream in enumerate(streams)
        )
        for thread in threads:
            thread.start()
        try:
            return_code = process.wait(timeout=_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
            _reject()
        for thread in threads:
            thread.join(timeout=1)
        if (any(thread.is_alive() for thread in threads)
                or any(type(value) is not bytes or len(value) > _MAX_OUTPUT
                       for value in output)):
            _reject()
        return subprocess.CompletedProcess(arguments, return_code, output[0], output[1])
    except Exception:
        _reject()
    finally:
        if process is not None:
            if process.poll() is None:
                try:
                    process.kill()
                    process.wait(timeout=1)
                except Exception:
                    pass
            for thread in threads:
                thread.join(timeout=1)
            for stream in streams:
                stream.close()

def _read_stream(stream: object, process: subprocess.Popen[bytes],
                 output: list[object], index: int) -> None:
    try:
        payload = stream.read(_MAX_OUTPUT + 1)
    except Exception:
        payload = None
    output[index] = payload
    if type(payload) is not bytes or len(payload) > _MAX_OUTPUT:
        try:
            process.kill()
        except Exception:
            pass

def _split_api_response(payload: bytes) -> tuple[int, bytes]:
    separator = b"\r\n\r\n" if b"\r\n\r\n" in payload else b"\n\n"
    parts = payload.split(separator, 1)
    if len(parts) != 2:
        _reject()
    try:
        first_line = parts[0].replace(b"\r\n", b"\n").split(b"\n", 1)[0].decode("ascii")
    except UnicodeError:
        _reject()
    match = re.fullmatch(r"HTTP/(?:1\.[01]|2(?:\.0)?) ([0-9]{3})(?: [\x20-\x7e]*)?", first_line)
    if match is None:
        _reject()
    return int(match.group(1)), parts[1]

def _decode_json(payload: bytes) -> object:
    def pairs_hook(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result = {}
        for key, value in pairs:
            if type(key) is not str or key in result:
                _reject()
            result[key] = value
        return result

    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs_hook,
            parse_constant=lambda _value: _reject(),
        )
    except SoloMaintainerClosureError:
        raise
    except Exception:
        _reject()

def _reject() -> None:
    raise SoloMaintainerClosureError(ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED)
