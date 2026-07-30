"""Caller-owned synthetic Windows Git topology for Issue #56 tests."""

from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _SyntheticWorktreePaths,
)
from tests.cutover_contract_fixtures import valid_profile_body

EXPECTED_MASTER = "96fceda6e85316dd6b17ef516adf96491d28cb6d"
OBSERVED_AT = 1_900_000_000


@dataclass(slots=True)
class SyntheticRepositoryScenario:
    owner: tempfile.TemporaryDirectory[str]
    root: Path
    marker: Path
    source: Path
    legacy: Path
    failed_container: Path
    journal_root: Path
    admin_preservation: Path
    worktree_preservation: Path
    rollback_root: Path
    external_target_parent: Path
    worktrees: tuple[_SyntheticWorktreePaths, ...]

    def close(self) -> None:
        self.owner.cleanup()


def build_synthetic_repository_scenario() -> SyntheticRepositoryScenario:
    owner = tempfile.TemporaryDirectory(prefix="issue56-synthetic-")
    root = Path(owner.name)
    marker = root / ".codex-cutover-mutation-test-sandbox"
    marker.write_bytes(b"issue56-synthetic-marker-v1")
    source = root / "repository"
    paths = _prepare_parents(root)
    _run_git(root, "init", "-b", "master", str(source))
    _run_git(source, "config", "user.name", "Synthetic Operator")
    _run_git(source, "config", "user.email", "synthetic@example.test")
    (source / "README.md").write_text("synthetic repository\n", "utf-8")
    _run_git(source, "add", "README.md")
    _run_git(source, "commit", "-m", "synthetic baseline")
    _exclude_embedded_worktrees(source)
    worktrees = _create_worktrees(root, source, paths)
    return SyntheticRepositoryScenario(
        owner=owner,
        root=root,
        marker=marker,
        source=source,
        legacy=root / "legacy-repository",
        failed_container=root / "failed-container",
        journal_root=paths["journal"],
        admin_preservation=paths["admin"],
        worktree_preservation=paths["physical"],
        rollback_root=paths["rollback"],
        external_target_parent=paths["external_target"],
        worktrees=worktrees,
    )


def profile_for_review(
    review,
    *,
    acl_policy_fingerprint: str | None = None,
) -> CutoverProfileV1:
    body = valid_profile_body()
    body["governing_master_commit"] = EXPECTED_MASTER
    if acl_policy_fingerprint is not None:
        body["acl_policy"]["policy_fingerprint"] = (
            acl_policy_fingerprint
        )
    body["role_selections"] = dict(review.role_selections)
    body["evidence_roles"] = dict(review.evidence_roles)
    body["reviewed_git_selections"] = dict(
        review.reviewed_git_selections
    )
    body["rollback_roles"] = dict(review.rollback_roles)
    body["worktree_roster"] = [
        {
            "role": worktree.role,
            "placement": worktree.placement.value,
            "selection_fingerprint": worktree.selection_fingerprint,
        }
        for worktree in review.roster.worktrees
    ]
    return CutoverProfileV1.create(body)


def authorization_for(profile, operation_fingerprint):
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=operation_fingerprint,
        phase="execute",
        expires_at_epoch=OBSERVED_AT + 600,
    )


def run_fixture_git(cwd: Path, *arguments: str) -> bytes:
    return _run_git(cwd, *arguments)


def _prepare_parents(root: Path) -> dict[str, Path]:
    values = {
        "admin": root / "preservation" / "admin",
        "physical": root / "preservation" / "physical",
        "rollback": root / "rollback-evidence",
        "external_original": root / "external-original",
        "external_target": root / "external-target",
        "journal": root / "journal",
        "finance": root / "finance-synthetic",
    }
    for path in values.values():
        path.mkdir(parents=True)
    return values


def _exclude_embedded_worktrees(source: Path) -> None:
    exclude = source / ".git" / "info" / "exclude"
    with exclude.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write("\n.synthetic-worktrees/\n")


def _create_worktrees(root, source, paths):
    worktrees: list[_SyntheticWorktreePaths] = []
    for index in range(1, 12):
        role = f"worktree_{index:02d}"
        original = _original_path(source, paths, index)
        original.parent.mkdir(parents=True, exist_ok=True)
        _run_git(source, "worktree", "add", "-b", role, str(original))
        target = _target_path(root, paths, index)
        preservation = paths["physical"] / role
        worktrees.append(
            _SyntheticWorktreePaths(
                role=role,
                placement="embedded" if index <= 8 else "external",
                original=original,
                target=target,
                preservation=preservation,
            )
        )
    return tuple(worktrees)


def _original_path(source, paths, index):
    if index <= 8:
        return source / ".synthetic-worktrees" / f"worktree-{index:02d}"
    return paths["external_original"] / f"worktree-{index:02d}"


def _target_path(root, paths, index):
    if index <= 8:
        return root / "repository" / "Worktrees" / f"worktree-{index:02d}"
    return paths["external_target"] / f"worktree-{index:02d}"


def _run_git(cwd: Path, *arguments: str) -> bytes:
    command = ["git", *arguments]
    completed = subprocess.run(
        command,
        cwd=cwd,
        env=_git_environment(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
        check=False,
        shell=False,
    )
    if completed.returncode != 0 or len(completed.stdout) > 1_000_000:
        raise RuntimeError("synthetic_git_fixture_failed")
    return completed.stdout


def _git_environment(cwd: Path) -> dict[str, str]:
    allowed = (
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "WINDIR",
        "TEMP",
        "TMP",
        "COMSPEC",
    )
    environment = {key: os.environ[key] for key in allowed if key in os.environ}
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_CEILING_DIRECTORIES": str(cwd.anchor),
        }
    )
    return environment
