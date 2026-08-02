"""Fixed adapter from a repository HEAD to content-free Issue #100 receipts."""

from __future__ import annotations

import io
import os
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
import platform
import subprocess
import sys
import unittest

from backend.r2_ci_provenance_v2 import (
    CiProvenanceKindV2,
    R2CiProvenanceError,
    R2CiProvenanceReceiptV2,
    R2GitObjectEntryV2,
    R2GitObjectSourcePackageV2,
    R2WorkflowLockV2,
    fixed_suite_fingerprint_v2,
    fixed_suite_v2,
)
from backend.r2_ci_provenance_v2._canonical import fingerprint, sha256
from scripts.repository_leakage_scan import scan_repository


_RUNBOOK = "docs/operations/r2_final_operator_runbook.md"


def read_git_object_source_package_v2(root: Path):
    root = root.resolve(strict=True)
    commit = _git(root, "rev-parse", "HEAD^{commit}").decode("ascii").strip()
    tree = _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    records = _tree_records(_git(root, "ls-tree", "-rz", "--full-tree", "HEAD"))
    entries, raw = [], {}
    for mode, oid, relative in records:
        content = _git(root, "cat-file", "blob", oid)
        entries.append(R2GitObjectEntryV2.create(
            relative_path=relative, mode=mode, blob_oid=oid, content_bytes=content
        ))
        raw[relative] = content
    lock = _workflow_lock(raw)
    if _RUNBOOK not in raw:
        raise R2CiProvenanceError()
    observed_commit = _git(root, "rev-parse", "HEAD^{commit}").decode("ascii").strip()
    observed_tree = _git(root, "rev-parse", "HEAD^{tree}").decode("ascii").strip()
    package = R2GitObjectSourcePackageV2.create(
        final_commit_oid=commit,
        final_tree_oid=tree,
        observed_commit_oid=observed_commit,
        observed_tree_oid=observed_tree,
        entries=tuple(entries),
        workflow_lock=lock,
        runbook_fingerprint=sha256(raw[_RUNBOOK]),
    )
    return package, lock


def verify_ci_environment_v2(kind: CiProvenanceKindV2):
    if type(kind) is not CiProvenanceKindV2:
        raise R2CiProvenanceError()
    if kind is CiProvenanceKindV2.PORTABLE and not sys.platform.startswith("linux"):
        raise R2CiProvenanceError()
    if kind is not CiProvenanceKindV2.PORTABLE and sys.platform != "win32":
        raise R2CiProvenanceError()
    fields = (
        kind.value,
        platform.system(),
        platform.machine(),
        os.environ.get("RUNNER_OS", ""),
        os.environ.get("RUNNER_ARCH", ""),
        os.environ.get("ImageOS", ""),
        os.environ.get("GITHUB_JOB", ""),
        os.environ.get("RUNNER_NAME", ""),
        os.environ.get("GITHUB_RUN_ID", ""),
        os.environ.get("GITHUB_RUN_ATTEMPT", ""),
    )
    if any(not item for item in fields[3:]):
        raise R2CiProvenanceError()
    return fingerprint("r2-ci-runner-v2", list(fields))


def execute_fixed_suite_v2(kind: CiProvenanceKindV2, root: Path):
    previous = Path.cwd()
    stream = io.StringIO()
    try:
        os.chdir(root)
        suite = unittest.defaultTestLoader.loadTestsFromNames(fixed_suite_v2(kind))
        with redirect_stdout(stream), redirect_stderr(stream):
            result = unittest.TextTestRunner(stream=stream, verbosity=0).run(suite)
    finally:
        os.chdir(previous)
    if not result.wasSuccessful() or result.testsRun < 1 or len(result.skipped) != 0:
        raise R2CiProvenanceError()
    return result.testsRun


def create_ci_receipt_v2(root: Path, kind: CiProvenanceKindV2):
    runner = verify_ci_environment_v2(kind)
    package, lock = read_git_object_source_package_v2(root)
    execute_fixed_suite_v2(kind, root)
    if scan_repository(root):
        raise R2CiProvenanceError()
    return R2CiProvenanceReceiptV2.create(
        source_package=package,
        workflow_lock=lock,
        provenance_kind=kind,
        runner_fingerprint=runner,
        suite_fingerprint=fixed_suite_fingerprint_v2(kind),
        required_skip_count=0,
        platform_divergence_count=0,
        leakage_finding_count=0,
        failure_count=0,
    )


def _git(root: Path, *arguments: str):
    try:
        result = subprocess.run(
            ("git", *arguments), cwd=root, check=True, capture_output=True,
            timeout=30,
        )
    except Exception:
        raise R2CiProvenanceError() from None
    if result.stderr:
        raise R2CiProvenanceError()
    return result.stdout


def _tree_records(payload):
    records = []
    try:
        for record in payload.split(b"\0"):
            if not record:
                continue
            metadata, path = record.split(b"\t", 1)
            mode, kind, oid = metadata.decode("ascii").split(" ")
            if kind != "blob":
                raise R2CiProvenanceError()
            records.append((mode, oid, path.decode("utf-8")))
    except R2CiProvenanceError:
        raise
    except Exception:
        raise R2CiProvenanceError() from None
    if not records:
        raise R2CiProvenanceError()
    return tuple(records)


def _workflow_lock(raw):
    workflows = tuple(
        (path, content) for path, content in raw.items()
        if path.startswith(".github/workflows/")
        and (path.endswith(".yml") or path.endswith(".yaml"))
    )
    return R2WorkflowLockV2.create(workflows=workflows)
