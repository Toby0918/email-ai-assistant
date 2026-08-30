"""Fixed read-only Git observation for closure evidence rollover."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import subprocess

from backend.r2_solo_maintainer_closure._canonical import is_fingerprint, is_git_oid
from backend.r2_solo_maintainer_closure.contracts import SoloMaintainerClosureCandidateV1
from backend.r2_solo_maintainer_closure.repository import ROOT

from .contracts import ClosureEvidenceRolloverError, RolloverErrorCode


_REMOTE_REF = "refs/remotes/origin/master"
_MAX_OUTPUT = 1024 * 1024


@dataclass(frozen=True, slots=True, repr=False)
class RolloverRepositorySnapshotV1:
    current_commit_oid: str
    current_tree_oid: str
    historical_commit_oid: str
    historical_tree_oid: str

    @classmethod
    def create(
        cls,
        *,
        current_commit_oid: object,
        current_tree_oid: object,
        historical_commit_oid: object,
        historical_tree_oid: object,
    ):
        values = (
            current_commit_oid, current_tree_oid, historical_commit_oid,
            historical_tree_oid,
        )
        if (
            not all(is_git_oid(value) for value in values)
            or current_commit_oid == historical_commit_oid
        ):
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
        return cls(*values)


class FixedRolloverRepository:
    """Require one clean exact-master checkout and one strict historical ancestor."""

    def collect(
        self, old_commit_oid: str, old_tree_oid: str
    ) -> RolloverRepositorySnapshotV1:
        try:
            if not is_git_oid(old_commit_oid) or not is_git_oid(old_tree_oid):
                raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
            current = _git("rev-parse", "HEAD^{commit}").decode("ascii").strip()
            remote = _git("rev-parse", _REMOTE_REF + "^{commit}").decode("ascii").strip()
            tree = _git("rev-parse", "HEAD^{tree}").decode("ascii").strip()
            observed_old = _git("rev-parse", old_commit_oid + "^{commit}").decode(
                "ascii"
            ).strip()
            observed_old_tree = _git("rev-parse", old_commit_oid + "^{tree}").decode(
                "ascii"
            ).strip()
            status = _git(
                "-c", "status.showUntrackedFiles=all", "status", "--porcelain=v1", "-z",
                "--untracked-files=all",
            )
            if (
                current != remote
                or current == old_commit_oid
                or observed_old != old_commit_oid
                or observed_old_tree != old_tree_oid
                or status
                or not _is_ancestor(old_commit_oid, current)
            ):
                raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
            return RolloverRepositorySnapshotV1.create(
                current_commit_oid=current,
                current_tree_oid=tree,
                historical_commit_oid=observed_old,
                historical_tree_oid=observed_old_tree,
            )
        except ClosureEvidenceRolloverError:
            raise
        except Exception:
            raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED) from None


def _git(*arguments: str) -> bytes:
    environment = {
        "PATH": os.pathsep.join(os.get_exec_path()),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "LANG": "C",
    }
    completed = subprocess.run(
        ("git", "--no-replace-objects", "-c", "core.fsmonitor=false", *arguments),
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        check=False,
    )
    if completed.returncode or completed.stderr or len(completed.stdout) > _MAX_OUTPUT:
        raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
    return completed.stdout


def _is_ancestor(old_commit: str, current_commit: str) -> bool:
    environment = {
        "PATH": os.pathsep.join(os.get_exec_path()),
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_OPTIONAL_LOCKS": "0",
        "LC_ALL": "C",
        "LANG": "C",
    }
    completed = subprocess.run(
        (
            "git", "--no-replace-objects", "-c", "core.fsmonitor=false",
            "merge-base", "--is-ancestor", old_commit, current_commit,
        ),
        cwd=ROOT,
        env=environment,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        timeout=30,
        check=False,
    )
    return completed.returncode == 0 and not completed.stdout and not completed.stderr


@dataclass(frozen=True, slots=True, repr=False)
class ClosureEvidenceObservationV1:
    manifest: bytes
    receipt: bytes
    historical_commit_oid: str
    historical_tree_oid: str
    manifest_fingerprint: str
    receipt_fingerprint: str
    evidence_identity_fingerprint: str
    parent_identity_fingerprint: str
    parent_dacl_sha256: str
    historical_target_name: str
    source: Path | None

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256(self.manifest).hexdigest()

    @property
    def receipt_sha256(self) -> str:
        return hashlib.sha256(self.receipt).hexdigest()


def create_evidence_observation(**values) -> ClosureEvidenceObservationV1:
    commit, manifest = values.get("historical_commit_oid"), values.get(
        "manifest_fingerprint"
    )
    if (
        type(values.get("manifest")) is not bytes or not values["manifest"]
        or type(values.get("receipt")) is not bytes or not values["receipt"]
        or not is_git_oid(commit)
        or not is_git_oid(values.get("historical_tree_oid"))
        or not all(is_fingerprint(values.get(name)) for name in (
            "manifest_fingerprint", "receipt_fingerprint",
            "evidence_identity_fingerprint", "parent_identity_fingerprint",
            "parent_dacl_sha256",
        ))
        or values.get("historical_target_name") != historical_target_name(commit, manifest)
        or values.get("source") is not None
        and not isinstance(values.get("source"), Path)
    ):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)
    return ClosureEvidenceObservationV1(**values)


def require_closure_cross_binding(manifest, receipt) -> None:
    copied = (
        "manifest_fingerprint", "final_commit_oid", "final_tree_oid",
        "final_master_binding_fingerprint", "source_package_fingerprint",
        "production_binding_fingerprint", "github_guardrail_snapshot_fingerprint",
        "hosted_evidence_set_fingerprint", "evidence_set_fingerprint",
        "gap_proof_set_fingerprint",
    )
    candidate = SoloMaintainerClosureCandidateV1.create(manifest, receipt.prepared_at_epoch)
    if (any(getattr(manifest, name) != getattr(receipt, name) for name in copied)
            or candidate.candidate_fingerprint != receipt.candidate_fingerprint):
        raise ClosureEvidenceRolloverError(RolloverErrorCode.STATE_REJECTED)


def historical_target_name(commit: str, manifest: str) -> str:
    return f"r2-solo-maintainer-closure-v1.historical-{commit[:16]}-{manifest[:16]}"
