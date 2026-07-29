"""Create-only offline Runtime build orchestration."""

from __future__ import annotations

import hashlib

from .canonical import fail
from .errors import ManagedActivationError
from .publication_scope import PublicationScopeWindow
from .receipts import ManagedRuntimeReceiptV1
from .runtime_capture import (
    capture_lock,
    capture_locked_wheels,
    open_python_source,
)
from .runtime_execution import (
    install_locked_wheels as _install_locked_wheels,
    publish_lock as _publish_lock,
)
from .runtime_policy import review_runtime_inputs
from .runtime_tree import RuntimeTreeWindow
from .runtime_verification import (
    validate_runtime_evidence,
    verify_with_new_runtime,
)
from .windows_directory_monitor import WindowsDirectoryChangeGuard
from .scope_models import _SyntheticActivationScope

_ERROR = "runtime_publication_failed"
_STARTUP_ARCHIVE = "managed-startup.zip"
_ISOLATED_PATH_BYTES = b"managed-startup.zip\nLib\nDLLs\n"


class LockedRuntimeBuilder:
    """Build one reviewed Runtime without live dependency resolution."""

    def __new__(cls, *args: object, **kwargs: object):
        raise TypeError("LockedRuntimeBuilder exposes publish() only")

    @classmethod
    def publish(cls, *, scope: object) -> ManagedRuntimeReceiptV1:
        if type(scope) is not _SyntheticActivationScope:
            fail("runtime_scope_invalid")
        source = None
        window = None
        tree = None
        try:
            current = _review_inputs(scope)
            source = open_python_source(
                scope.review.scenario.python_source, current
            )
            captured = capture_locked_wheels(scope.review.scenario, current)
            lock_payload = capture_lock(scope.review.scenario, current)
            window = PublicationScopeWindow.open(scope=scope, role="runtime")
            target = _create_runtime_target(scope, window)
            tree = RuntimeTreeWindow.open(target)
            receipt = _publish_reviewed_runtime(
                scope, current, source, captured, lock_payload, window, tree
            )
        except ManagedActivationError:
            _close_failure(tree, source, window)
            raise
        except Exception:
            _close_failure(tree, source, window)
            fail(_ERROR)
        _close_success(tree, source, window)
        return receipt


def _publish_reviewed_runtime(
    scope, current, source, captured, lock_payload, window, tree
):
    scenario = scope.review.scenario
    target = scenario.runtime_target
    source.require_stable()
    _publish_source_runtime(source, tree)
    startup_hash = _publish_startup_archive(source, tree)
    _publish_isolation_files(tree)
    _install_locked_wheels(captured, tree)
    _publish_lock(lock_payload, tree)
    guard = WindowsDirectoryChangeGuard.open(target.parent)
    try:
        receipt = _verify_and_receipt(
            scope, current, source, window, tree, target, startup_hash
        )
        guard.seal_unchanged()
    except Exception:
        guard.close(active_error=True)
        raise
    guard.close(active_error=False)
    return receipt


def _verify_and_receipt(
    scope, current, source, window, tree, target, startup_hash
):
    tree.verify_exact()
    evidence = verify_with_new_runtime(target, current)
    validate_runtime_evidence(
        evidence,
        current,
        target,
        source.sqlite_binary_hashes(),
        startup_hash,
    )
    source.require_stable()
    if _review_inputs(scope) != current:
        fail("runtime_source_changed")
    observation = tree.verify_exact()
    window.verify_target()
    tree.verify_exact()
    return _runtime_receipt(scope, current, observation)


def _create_runtime_target(scope, window):
    scenario = scope.review.scenario
    window.create_target()
    return scenario.runtime_target


def _publish_source_runtime(source, tree) -> None:
    source.publish_into(tree)


def _publish_startup_archive(source, tree) -> str:
    payload = source.startup_archive()
    tree.create_file((_STARTUP_ARCHIVE,), payload)
    return hashlib.sha256(payload).hexdigest()


def _publish_isolation_files(tree) -> None:
    tree.create_file(("python._pth",), _ISOLATED_PATH_BYTES)
    tree.create_file(("python312._pth",), _ISOLATED_PATH_BYTES)


def _close_failure(*resources) -> None:
    for resource in resources:
        if resource is not None:
            resource.close(active_error=True)


def _close_success(*resources) -> None:
    failed = False
    for resource in resources:
        try:
            resource.close(active_error=False)
        except ManagedActivationError:
            failed = True
    if failed:
        fail(_ERROR)


def _runtime_receipt(scope, current, observation):
    return ManagedRuntimeReceiptV1.create(
        operation_fingerprint=scope.review.operation_fingerprint,
        profile_fingerprint=scope.profile.profile_fingerprint,
        governing_master_commit=scope.profile.governing_master_commit,
        authorization_fingerprint=scope.authorization_fingerprint,
        input_fingerprints=(
            current.python_runtime_fingerprint,
            current.wheelhouse_fingerprint,
            current.dependency_lock_fingerprint,
        ),
        observation_fingerprint=observation,
        counts={"published": 1, "rejected": 0},
    )


def _review_inputs(scope: _SyntheticActivationScope):
    scenario = scope.review.scenario
    current = review_runtime_inputs(
        source=scenario.python_source,
        source_manifest=scenario.python_source_manifest,
        wheelhouse=scenario.wheelhouse,
        dependency_lock=scenario.dependency_lock,
    )
    if current != scope.review.runtime_inputs:
        fail("runtime_source_changed")
    return current
