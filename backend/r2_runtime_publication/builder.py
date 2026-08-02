"""Offline construction and exact self-verification of one Runtime stage."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_managed_activation.runtime_capture import (
    capture_lock,
    capture_locked_wheels,
    open_python_source,
)
from backend.cutover_managed_activation.runtime_execution import (
    install_locked_wheels,
    publish_lock,
)
from backend.cutover_managed_activation.runtime_policy import (
    RuntimeInputReviewV1,
    review_runtime_inputs,
)
from backend.cutover_managed_activation.runtime_tree import RuntimeTreeWindow
from backend.cutover_managed_activation.runtime_verification import (
    validate_runtime_evidence,
    verify_with_new_runtime,
)

from .canonical import fingerprint

_ISOLATED_PATH = b"managed-startup.zip\nLib\nDLLs\n"


@dataclass(frozen=True, slots=True, repr=False)
class RuntimeInputPaths:
    python_source: Path
    source_manifest: Path
    wheelhouse: Path
    dependency_lock: Path


@dataclass(frozen=True, slots=True, repr=False)
class PreparedRuntime:
    review: RuntimeInputReviewV1
    tree_fingerprint: str
    verification_fingerprint: str
    staging_identity_fingerprint: str
    sqlite_hashes: tuple[tuple[str, str], ...]
    startup_hash: str


def review_inputs(paths: RuntimeInputPaths) -> RuntimeInputReviewV1:
    return review_runtime_inputs(
        source=paths.python_source,
        source_manifest=paths.source_manifest,
        wheelhouse=paths.wheelhouse,
        dependency_lock=paths.dependency_lock,
    )


def prepare_runtime(paths, staging, expected, fault) -> PreparedRuntime:
    os.mkdir(staging)
    if staging.stat().st_dev != staging.parent.stat().st_dev:
        raise ValueError("runtime_staging_volume_invalid")
    current = review_inputs(paths)
    if current != expected:
        raise ValueError("runtime_source_drift")
    source = tree = None
    try:
        source = open_python_source(paths.python_source, current)
        captured = capture_locked_wheels(paths, current)
        lock = capture_lock(paths, current)
        tree = RuntimeTreeWindow.open(staging)
        startup_hash = _populate(source, captured, lock, tree)
        _inject_reparse(staging, fault)
        tree_fingerprint = tree.verify_exact()
        evidence = verify_with_new_runtime(staging, current)
        if fault.kind == "verification_failure":
            evidence = {**evidence, "python_version": "0.0.0"}
        sqlite_hashes = source.sqlite_binary_hashes()
        validate_runtime_evidence(
            evidence,
            current,
            staging,
            sqlite_hashes,
            startup_hash,
        )
        _inject_input_drift(paths, current, fault)
        source.require_stable()
        if review_inputs(paths) != current:
            raise ValueError("runtime_source_drift")
        final_tree = tree.verify_exact()
        if final_tree != tree_fingerprint:
            raise ValueError("runtime_verification_drift")
        prepared = _prepared(
            staging,
            current,
            final_tree,
            evidence,
            sqlite_hashes,
            startup_hash,
        )
    except Exception:
        _close(tree, source, active_error=True)
        raise
    _close(tree, source, active_error=False)
    return prepared


def verify_published(target: Path, prepared: PreparedRuntime) -> None:
    tree = RuntimeTreeWindow.open(target)
    try:
        observed = tree.verify_exact()
        evidence = verify_with_new_runtime(target, prepared.review)
        validate_runtime_evidence(
            evidence,
            prepared.review,
            target,
            prepared.sqlite_hashes,
            prepared.startup_hash,
        )
        if (
            observed != prepared.tree_fingerprint
            or fingerprint("runtime-self-verification-v1", evidence)
            != prepared.verification_fingerprint
        ):
            raise ValueError("runtime_publish_verification_failed")
    except Exception:
        tree.close(active_error=True)
        raise
    tree.close(active_error=False)


def observe_tree(path: Path) -> str | None:
    if not path.is_dir() or path.is_symlink():
        return None
    tree = None
    try:
        tree = RuntimeTreeWindow.open(path)
        return tree.verify_exact()
    except Exception:
        return None
    finally:
        if tree is not None:
            tree.close(active_error=True)


def _populate(source, captured, lock, tree) -> str:
    source.require_stable()
    source.publish_into(tree)
    startup = source.startup_archive()
    tree.create_file(("managed-startup.zip",), startup)
    tree.create_file(("python._pth",), _ISOLATED_PATH)
    tree.create_file(("python312._pth",), _ISOLATED_PATH)
    install_locked_wheels(captured, tree)
    publish_lock(lock, tree)
    return hashlib.sha256(startup).hexdigest()


def _prepared(staging, review, tree, evidence, sqlite_hashes, startup):
    stat = staging.stat()
    identity = fingerprint(
        "runtime-staging-identity-v1",
        [stat.st_dev, stat.st_ino, tree],
    )
    return PreparedRuntime(
        review=review,
        tree_fingerprint=tree,
        verification_fingerprint=fingerprint(
            "runtime-self-verification-v1", evidence
        ),
        staging_identity_fingerprint=identity,
        sqlite_hashes=sqlite_hashes,
        startup_hash=startup,
    )


def _inject_input_drift(paths, review, fault) -> None:
    if fault.kind == "source_drift":
        wheel = paths.wheelhouse / review.wheels[0].wheel
        with wheel.open("ab") as handle:
            handle.write(b"drift")
            handle.flush()
            os.fsync(handle.fileno())
    elif fault.kind == "dependency_drift":
        with paths.dependency_lock.open("ab") as handle:
            handle.write(b" ")
            handle.flush()
            os.fsync(handle.fileno())


def _inject_reparse(staging: Path, fault) -> None:
    if fault.kind != "reparse":
        return
    try:
        os.symlink(
            staging.parent,
            staging / "injected-reparse",
            target_is_directory=True,
        )
    except OSError:
        raise ValueError("runtime_reparse_fault_injected") from None


def _close(tree, source, *, active_error: bool) -> None:
    if tree is not None:
        tree.close(active_error=active_error)
    if source is not None:
        source.close(active_error=active_error)
