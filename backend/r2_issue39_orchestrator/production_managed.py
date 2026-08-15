"""Strict retained-attempt publication for the four fixed managed units."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace

from backend.cutover_managed_activation.runtime_capture import (
    capture_lock,
    capture_locked_wheels,
    open_python_source,
)
from backend.cutover_managed_activation.runtime_execution import (
    install_locked_wheels,
    publish_lock,
)
from backend.cutover_managed_activation.runtime_tree import RuntimeTreeWindow
from backend.cutover_managed_activation.runtime_verification import (
    validate_runtime_evidence,
    verify_with_new_runtime,
)
from backend.cutover_managed_activation.windows_file_handles import WindowsReadHandleApi

from .durable_io import read_segment, write_segment
from .production_host_state import retained_path
from .production_path_checks import (
    plain_directory as _plain,
    regular_file as _regular,
)
from .production_runtime_review import (
    issue39_runtime_verification_review,
    review_fixed_runtime_inputs,
)


_RUNTIME_SOURCE = Path(
    r"D:\Projects\email_ai_assistant-runtime\python-3.12.13-sqlite-3.50.4\python.exe"
)
_WHEELHOUSE = Path(r"D:\Projects\email_ai_assistant-runtime\issue39-wheelhouse")
_CONFIG = (
    b"EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS=cndlf.com\n"
    b"EMAIL_AGENT_LOG_LEVEL=INFO\n"
)
_ISOLATED_PATH = b"managed-startup.zip\nLib\nLib\\site-packages\nDLLs\n"
_SCRIPTS_ISOLATED_PATH = (
    b"..\\managed-startup.zip\n..\\Lib\n..\\Lib\\site-packages\n..\\DLLs\n"
)
_SCRIPT_RUNTIME_FILES = (
    "python.exe", "python3.dll", "python312.dll",
    "vcruntime140.dll", "vcruntime140_1.dll",
)


def mutate_managed(host, action, direction, attempt_token):
    unit, phase = action.action_name.rsplit("_", 1)
    stage, target = _paths(host, unit)
    if direction == "rollback":
        source = target if phase == "publish" else stage
        destination = stage if phase == "publish" else retained_path(
            host, action, stage
        )
        return _move(source, destination)
    if phase == "publish":
        _move(stage, target)
        if not _exact(unit, target, host):
            raise ValueError("R2_ISSUE39_MANAGED_PUBLISH_INVALID")
        return
    attempt = _attempt(stage, unit, attempt_token)
    {
        "runtime": _prepare_runtime,
        "database": _database_preparer,
        "crx": _prepare_crx,
        "config": _prepare_config,
    }[unit](host, attempt)
    if not _exact(unit, attempt, host):
        raise ValueError("R2_ISSUE39_MANAGED_PREPARE_INVALID")
    _move(attempt, stage)


def managed_state(host, name, reverse=False):
    unit, phase = name.rsplit("_", 1)
    action = next(item for item in host._catalog.actions if item.action_name == name)
    stage, target = _paths(host, unit)
    if reverse:
        path = stage if phase == "publish" else retained_path(host, action, stage)
        absent = target if phase == "publish" else stage
        return _state_exact(unit, path, absent, host, action)
    if phase == "publish":
        if _state_exact(unit, target, stage, host, action):
            return True
        if _exact(unit, stage, host) and not os.path.lexists(target):
            return False
        raise ValueError("R2_ISSUE39_MANAGED_AMBIGUOUS")
    if _state_exact(unit, stage, target, host, action):
        return True
    if not os.path.lexists(stage) and not os.path.lexists(target):
        return False
    raise ValueError("R2_ISSUE39_MANAGED_AMBIGUOUS")


def _state_exact(unit, present, absent, host, action):
    if os.path.lexists(absent) or not os.path.lexists(present):
        return False
    if _exact(unit, present, host):
        return True
    if unit != "database":
        return False
    from .production_host_state import database_identity_bound

    return database_identity_bound(host, action)


def managed_partial(host, action, direction):
    if direction != "forward" or not action.action_name.endswith("_prepare"):
        return None
    unit = action.action_name.rsplit("_", 1)[0]
    stage, target = _paths(host, unit)
    if os.path.lexists(stage) or os.path.lexists(target):
        return None
    parent = stage.parent
    prefix = f".{stage.name}.{unit}-attempt-"
    attempts = tuple(sorted(
        item for item in parent.iterdir() if item.name.startswith(prefix)
    ))
    if not attempts:
        return None
    if len(attempts) > 32 or any(not _plain(item) for item in attempts):
        raise ValueError("R2_ISSUE39_MANAGED_PARTIAL_INVALID")
    return hashlib.sha256(
        b"r2-issue39-managed-partial-v1\0"
        + action.action_fingerprint.encode("ascii")
        + b"\0".join(item.name.encode("ascii") for item in attempts)
    ).hexdigest()


def _prepare_runtime(host, attempt):
    from .production_native import create_directory_no_replace

    create_directory_no_replace(attempt.parent, attempt)
    review = review_fixed_runtime_inputs(host)
    scenario = SimpleNamespace(
        wheelhouse=_WHEELHOUSE,
        dependency_lock=host._layout.main / "requirements-ci-windows.lock",
    )
    source = tree = None
    try:
        source = open_python_source(_RUNTIME_SOURCE, review)
        captured = capture_locked_wheels(scenario, review)
        lock = capture_lock(scenario, review)
        tree = RuntimeTreeWindow.open(attempt)
        source.require_stable()
        source.publish_into(tree)
        tree.ensure_directory(("Scripts",))
        for name in _SCRIPT_RUNTIME_FILES:
            tree.create_file(
                ("Scripts", name),
                _read_held_file(attempt / name, 8 * 1024 * 1024),
            )
        tree.create_file(("Scripts", "python._pth"), _SCRIPTS_ISOLATED_PATH)
        tree.create_file(("Scripts", "python312._pth"), _SCRIPTS_ISOLATED_PATH)
        startup = source.startup_archive()
        tree.create_file(("managed-startup.zip",), startup)
        tree.create_file(("python._pth",), _ISOLATED_PATH)
        tree.create_file(("python312._pth",), _ISOLATED_PATH)
        install_locked_wheels(captured, tree)
        publish_lock(lock, tree)
        tree.verify_exact()
        verification_review = issue39_runtime_verification_review(review)
        evidence = verify_with_new_runtime(attempt, verification_review)
        validate_runtime_evidence(
            evidence, verification_review, attempt, source.sqlite_binary_hashes(),
            hashlib.sha256(startup).hexdigest(),
        )
        source.require_stable()
    except Exception:
        _close(tree, source, active_error=True)
        raise
    _close(tree, source, active_error=False)


def _database_preparer(host, attempt):
    from .production_database import prepare_database

    prepare_database(host, attempt)


def _prepare_crx(host, attempt):
    source = host._layout.legacy / "frontend" / "browser_extension.crx"
    api = WindowsReadHandleApi()
    handle = None
    try:
        handle = api.open_existing(source, deny_write=True)
        observed = api.observe(handle)
        payload = api.read_bounded(handle, limit=1024 * 1024)
        if hashlib.sha256(payload).hexdigest() != host._prepared._inputs.crx_fingerprint:
            raise ValueError("R2_ISSUE39_CRX_SOURCE_DRIFT")
        api.require_stable(handle, observed, source)
        write_segment(attempt, payload)
        api.require_stable(handle, observed, source)
    finally:
        if handle is not None:
            api.close(handle)


def _prepare_config(_host, attempt):
    write_segment(attempt, _CONFIG)


def _exact(unit, path, host):
    if unit == "runtime":
        return _runtime_exact(host, path)
    if unit == "database":
        from .production_database import database_exact

        return database_exact(host, path)
    if unit == "crx":
        return (
            _regular(path)
            and hashlib.sha256(read_segment(path)).hexdigest()
            == host._prepared._inputs.crx_fingerprint
        )
    if unit == "config":
        return _regular(path) and read_segment(path) == _CONFIG
    raise ValueError("R2_ISSUE39_MANAGED_INVALID")


def _runtime_exact(host, path):
    if not _plain(path):
        return False
    review = review_fixed_runtime_inputs(host)
    source = tree = None
    try:
        source = open_python_source(_RUNTIME_SOURCE, review)
        tree = RuntimeTreeWindow.open(path)
        tree.verify_exact()
        startup = read_segment(path / "managed-startup.zip")
        verification_review = issue39_runtime_verification_review(review)
        evidence = verify_with_new_runtime(path, verification_review)
        validate_runtime_evidence(
            evidence, verification_review, path, source.sqlite_binary_hashes(),
            hashlib.sha256(startup).hexdigest(),
        )
        source.require_stable()
        _close(tree, source, active_error=False)
        return True
    except Exception:
        _close(tree, source, active_error=True)
        return False


def _paths(host, unit):
    return getattr(host._layout, unit + "_stage"), getattr(host._layout, unit + "_target")


def _attempt(stage, unit, token):
    if not _fingerprint(token):
        raise ValueError("R2_ISSUE39_MANAGED_ATTEMPT_INVALID")
    return stage.parent / f".{stage.name}.{unit}-attempt-{token[:24]}"


def _move(source, target):
    from .production_native import move_no_replace

    move_no_replace(source, target)


def _read_held_file(path, maximum):
    api = WindowsReadHandleApi()
    handle = api.open_existing(path, deny_write=True)
    try:
        observed = api.observe(handle)
        payload = api.read_bounded(handle, limit=maximum)
        api.require_stable(handle, observed, path)
        return payload
    finally:
        api.close(handle)


def _close(tree, source, *, active_error):
    if tree is not None:
        tree.close(active_error=active_error)
    if source is not None:
        source.close(active_error=active_error)


def _fingerprint(value):
    return type(value) is str and len(value) == 64 and all(
        item in "0123456789abcdef" for item in value
    )
