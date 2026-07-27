"""Synthetic-only fixtures for Issue #54 review composition tests."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    RealPreflightAuthorizationV1,
    TestSandboxAuthorizationV1,
)
from backend.migration_evidence import prepare_migration_evidence_review
from backend.real_host_preflight import (
    AclBaselineObservationV1,
    BaselineAclRole,
    OperatorSidObservationV1,
    RealHostBaselineCallbacks,
    RealHostBaselineCollector,
    VolumeObservationV1,
)
from backend.real_host_preflight.canonical import (
    role_selection_fingerprint,
)
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)
from tests.real_host_preflight_fixtures import (
    object_observation,
)


OBSERVED_AT = 1_800_000_100
OPERATION_FINGERPRINT = opaque_fingerprint(901)
GOVERNING_MASTER = "9f93e3bc01687ab3a263dd111183d2bfb4abead6"
MARKER_NAME = ".issue-54-migration-evidence-synthetic-sandbox"
MARKER_BYTES = b"MIGRATION_EVIDENCE_SYNTHETIC_SANDBOX_V1\n"


class PublicationReviewFixture:
    """One temporary repository with the exact eleven-worktree roster."""

    def __init__(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        (self.root / MARKER_NAME).write_bytes(MARKER_BYTES)
        self.repository = _create_repository(self.root)
        self.worktrees = _create_worktree_roster(
            self.root,
            self.repository,
        )
        self.refs = tuple(
            ["refs/heads/master"]
            + [f"refs/heads/worktree-{index:02d}" for index in range(2, 12)]
        )
        (self.repository / "backend" / "service.py").write_text(
            "VALUE = 'reviewed synthetic change'\n",
            encoding="utf-8",
        )
        (self.repository / "tests").mkdir()
        (self.repository / "tests" / "test_synthetic.py").write_text(
            "def test_synthetic():\n    assert True\n",
            encoding="utf-8",
        )
        self.approved_dirty_paths = (
            "backend/service.py",
            "tests/test_synthetic.py",
        )
        self.target = (
            self.root
            / "publication"
            / "reviewed.migration-evidence.zip"
        )
        self.target.parent.mkdir()
        self.host_state = _MutableHostState()
        self.collector = _baseline_collector(self.host_state)
        self.profile = self._build_profile()

    def close(self) -> None:
        self.temporary.cleanup()

    def drift_host_baseline(self) -> None:
        self.host_state.acl_seed = 602

    def reset_host_baseline(self) -> None:
        self.host_state.acl_seed = 502

    def profile_with_changed_binding(
        self,
        section: str,
        key: str | int,
    ) -> CutoverProfileV1:
        body = self.profile.to_mapping()
        body.pop("profile_fingerprint")
        if section == "worktree_roster":
            roster = body[section]
            assert type(roster) is list and type(key) is int
            roster[key]["selection_fingerprint"] = opaque_fingerprint(980)
        else:
            values = body[section]
            assert type(values) is dict and type(key) is str
            values[key] = opaque_fingerprint(980)
        return CutoverProfileV1.create(body)

    def bind_selection(
        self,
        profile: CutoverProfileV1 | None = None,
        *,
        authorization_phase: str = "evidence_review",
        baseline_phase: str = "host_baseline",
        baseline_collector: object | None = None,
    ) -> object:
        from backend.migration_evidence_publication.selection import (
            _bind_test_profile_bound_selection,
        )

        selected_profile = profile or self.profile
        return _bind_test_profile_bound_selection(
            temporary_directory=self.temporary,
            profile=selected_profile,
            authorization=_sandbox_authorization(
                selected_profile,
                phase=authorization_phase,
            ),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
            repository_root=self.repository,
            target=self.target,
            approved_dirty_paths=self.approved_dirty_paths,
            reviewed_refs=self.refs,
            approved_worktrees=self.worktrees,
            baseline_collector=(
                self.collector
                if baseline_collector is None
                else baseline_collector
            ),
            baseline_authorization=_sandbox_authorization(
                selected_profile,
                phase=baseline_phase,
            ),
        )

    def real_authorization(
        self,
        profile: CutoverProfileV1 | None = None,
        *,
        phase: str = "evidence_review",
    ) -> RealPreflightAuthorizationV1:
        selected_profile = profile or self.profile
        body = {
            "authorization_type": "RealPreflightAuthorizationV1",
            "operation": "real_preflight",
            "operation_fingerprint": OPERATION_FINGERPRINT,
            "profile_fingerprint": selected_profile.profile_fingerprint,
            "governing_master_commit": (
                selected_profile.governing_master_commit
            ),
            "operator_fingerprint": selected_profile.operator_fingerprint,
            "phase": phase,
            "issued_at_epoch": OBSERVED_AT - 20,
            "not_before_epoch": OBSERVED_AT - 10,
            "expires_at_epoch": OBSERVED_AT + 300,
        }
        return RealPreflightAuthorizationV1.from_mapping(
            {
                **body,
                "authorization_fingerprint": hashlib.sha256(
                    _canonical_json(body)
                ).hexdigest(),
            }
        )

    def _build_profile(self) -> CutoverProfileV1:
        components = _baseline_components()
        body = valid_profile_body()
        body["governing_master_commit"] = GOVERNING_MASTER
        role_names = {
            "repository_root": (
                "source_root",
                components["source"].normalized_name_fingerprint,
            ),
            "projects_parent": (
                "target_parent",
                components["parent"].normalized_name_fingerprint,
            ),
            "finance_project": (
                "finance_root",
                components["finance"].normalized_name_fingerprint,
            ),
        }
        for profile_role, (role, name) in role_names.items():
            body["role_selections"][profile_role] = (
                role_selection_fingerprint(role, name)
            )
        provisional = CutoverProfileV1.create(copy.deepcopy(body))
        baseline = self.collector.collect(
            profile=provisional,
            authorization=_sandbox_authorization(
                provisional,
                phase="host_baseline",
            ),
            operation_fingerprint=OPERATION_FINGERPRINT,
            observed_at_epoch=OBSERVED_AT,
        )
        review = prepare_migration_evidence_review(
            repository_root=self.repository,
            target=self.target,
            approved_dirty_paths=self.approved_dirty_paths,
            reviewed_refs=self.refs,
            approved_worktrees=self.worktrees,
            host_baseline=baseline,
        )
        from backend.migration_evidence_publication.profile_binding import (
            _profile_bindings_for_review,
        )

        bindings = _profile_bindings_for_review(review, self.worktrees)
        body["evidence_roles"] = bindings.evidence_roles
        body["reviewed_git_selections"] = (
            bindings.reviewed_git_selections
        )
        body["worktree_roster"] = list(bindings.worktree_roster)
        return CutoverProfileV1.create(body)


def _create_repository(root: Path) -> Path:
    repository = root / "review-root"
    repository.mkdir()
    _run_git(repository, "init", "--initial-branch=master")
    _run_git(repository, "config", "user.name", "Synthetic Reviewer")
    _run_git(
        repository,
        "config",
        "user.email",
        "reviewer@example.test",
    )
    (repository / "backend").mkdir()
    (repository / "backend" / "service.py").write_text(
        "VALUE = 'committed synthetic value'\n",
        encoding="utf-8",
    )
    _run_git(repository, "add", "backend/service.py")
    _run_git(repository, "commit", "-m", "synthetic baseline")
    return repository


def _create_worktree_roster(
    root: Path,
    repository: Path,
) -> tuple[Path, ...]:
    embedded = root / "embedded"
    external = root / "external"
    embedded.mkdir()
    external.mkdir()
    paths = [repository]
    for index in range(2, 12):
        branch = f"worktree-{index:02d}"
        parent = embedded if index <= 8 else external
        path = parent / branch
        _run_git(repository, "branch", branch, "master")
        _run_git(repository, "worktree", "add", str(path), branch)
        paths.append(path.resolve())
    return tuple(paths)


def _baseline_components() -> dict[str, object]:
    parent = object_observation(
        1,
        parent_identity_fingerprint=opaque_fingerprint(401),
    )
    source = object_observation(
        2,
        parent_identity_fingerprint=parent.object_identity_fingerprint,
    )
    finance = object_observation(
        3,
        parent_identity_fingerprint=parent.object_identity_fingerprint,
    )
    return {"parent": parent, "source": source, "finance": finance}


class _MutableHostState:
    def __init__(self) -> None:
        self.acl_seed = 502


def _baseline_collector(
    state: _MutableHostState,
) -> RealHostBaselineCollector:
    values = _baseline_components()
    parent = values["parent"]
    source = values["source"]
    finance = values["finance"]

    def acl(
        role: BaselineAclRole,
        observed: object,
        count: int,
        seed: int,
    ) -> AclBaselineObservationV1:
        return AclBaselineObservationV1.create(
            role=role,
            object_identity_fingerprint=(
                observed.object_identity_fingerprint
            ),
            descriptor_fingerprint=opaque_fingerprint(seed),
            entry_count=count,
            complete=True,
            content_observed=False,
        )

    callbacks = RealHostBaselineCallbacks(
        source_root=lambda: source,
        parent=lambda: parent,
        finance=lambda: finance,
        volume=lambda: VolumeObservationV1.create(
            volume_fingerprint=opaque_fingerprint(301),
            filesystem_name="NTFS",
            drive_type="fixed",
            complete=True,
        ),
        operator_sid=lambda: OperatorSidObservationV1.create(
            sid_fingerprint=opaque_fingerprint(501),
            complete=True,
            content_observed=False,
        ),
        source_acl=lambda: acl(
            BaselineAclRole.SOURCE_ROOT,
            source,
            2,
            state.acl_seed,
        ),
        parent_acl=lambda: acl(
            BaselineAclRole.PARENT,
            parent,
            3,
            503,
        ),
        finance_acl=lambda: acl(
            BaselineAclRole.FINANCE,
            finance,
            4,
            504,
        ),
    )
    return RealHostBaselineCollector(callbacks)


def _sandbox_authorization(
    profile: CutoverProfileV1,
    *,
    phase: str,
) -> TestSandboxAuthorizationV1:
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=OPERATION_FINGERPRINT,
        phase=phase,
        expires_at_epoch=OBSERVED_AT + 300,
    )


def _run_git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("ascii")
