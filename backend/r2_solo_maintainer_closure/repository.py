"""Fixed read-only Git object and public GitHub evidence ports."""
from __future__ import annotations
from dataclasses import dataclass
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import urllib.error
import urllib.request
from ._canonical import canonical_json, fingerprint, is_fingerprint, is_git_oid
from .contracts import ClosureErrorCode, FinalMasterBindingV1, SoloMaintainerClosureError
from .github_guardrail import collect_verified_guardrail
from .local_evidence import collect_repository_subjects, repository_subject_names
from .hosted_evidence import (
    FIXED_CHECKS, GitHubEvidenceSnapshotV1,
    HostedCheckEvidenceV1, latest_successful_run as _latest_run,
    require_reconciliation_graph as _require_reconciliation_graph,
    hosted_step_fingerprints,
)
ROOT = Path(__file__).resolve().parents[2]
_API = "https://api.github.com"
_REPOSITORY = "Toby0918/email-ai-assistant"
_REMOTE_REF = "refs/remotes/origin/master"
_MAX_OUTPUT = 8 * 1024 * 1024
_WORKFLOWS = tuple(path for _name, path in FIXED_CHECKS)
@dataclass(frozen=True, slots=True, repr=False)
class RepositorySnapshotV1:
    final_master_binding: FinalMasterBindingV1
    production_binding: object
    source_fingerprints: tuple[tuple[str, str], ...]
    workflow_blobs: tuple[tuple[str, str], ...]
    snapshot_fingerprint: str
    root: Path; tracked_paths: tuple[str, ...]
    @classmethod
    def create(cls, *, final_master_binding: object, production_binding: object,
               source_fingerprints: object, workflow_blob_oids: object, root: object = ROOT,
               tracked_paths: object):
        if (type(final_master_binding) is not FinalMasterBindingV1 or not isinstance(root, Path)
                or type(tracked_paths) is not tuple or not tracked_paths
                or tuple(sorted(set(tracked_paths))) != tracked_paths
                or any(not _safe_git_path(path) for path in tracked_paths)):
            raise SoloMaintainerClosureError()
        production = _production_mapping(production_binding, final_master_binding)
        sources = _ordered_pairs(source_fingerprints, repository_subject_names())
        workflows = _ordered_pairs(workflow_blob_oids, tuple(dict.fromkeys(_WORKFLOWS)), git=True)
        body = {"final_master_binding_fingerprint": final_master_binding.binding_fingerprint,
                "production_binding_fingerprint": production["binding_fingerprint"],
                "source_fingerprints": [{"source": name, "fingerprint": value}
                                        for name, value in sources],
                "workflow_blobs": [{"path": name, "blob_oid": value}
                                   for name, value in workflows], "tracked_paths": list(tracked_paths)}
        return cls(final_master_binding, production_binding, sources, workflows,
                   fingerprint("r2-solo-maintainer-closure-evidence-set-v1", body), root, tracked_paths)
    def workflow_blob_oid(self, path: str) -> str:
        try:
            return dict(self.workflow_blobs)[path]
        except KeyError:
            raise SoloMaintainerClosureError() from None
    def source_mapping(self) -> dict[str, str]:
        return dict(self.source_fingerprints)
class FixedRepositoryPort:
    """Derive one clean exact-master snapshot from fixed local Git objects."""
    def collect(self) -> RepositorySnapshotV1:
        try:
            head = _git("rev-parse", "HEAD^{commit}").decode("ascii").strip()
            remote = _git("rev-parse", _REMOTE_REF + "^{commit}").decode("ascii").strip()
            if (head != remote or not is_git_oid(head) or _git(
                    "-c", "status.showUntrackedFiles=all", "status", "--porcelain=v1", "-z",
                    "--untracked-files=all")
                    or _git("fsck", "--strict", "--no-dangling", "--no-reflogs", head)):
                raise SoloMaintainerClosureError(ClosureErrorCode.MASTER_DRIFT)
            tree = _git("rev-parse", "HEAD^{tree}").decode("ascii").strip()
            descriptors = _tree_descriptors(tree)
            _require_index_and_checkout(descriptors)
            package, raw = _source_package(head, tree, descriptors)
            binding = FinalMasterBindingV1.create(
                final_commit_oid=head, final_tree_oid=tree,
                source_package_fingerprint=package.source_package_fingerprint,
                runbook_fingerprint=package.runbook_fingerprint,
                workflow_fingerprint=package.workflow_lock_fingerprint)
            from backend.r2_production_composition import build_production_binding_candidate_v1
            production = build_production_binding_candidate_v1(final_master_binding=binding)
            sources = _local_sources(binding, production, descriptors)
            workflows = {path: _blob_oid(descriptors, path) for path in set(_WORKFLOWS)}
            _require_reconciliation_graph(raw[".github/workflows/r2_provenance.yml"])
            return RepositorySnapshotV1.create(final_master_binding=binding, production_binding=production,
                source_fingerprints=sources, workflow_blob_oids=workflows,
                tracked_paths=tuple(path for path, _mode, _oid, _content in descriptors))
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED) from None
class FixedGitHubPort:
    """Collect exact public provenance and authenticated guardrail metadata."""
    def collect(self, repository: RepositorySnapshotV1) -> GitHubEvidenceSnapshotV1:
        try:
            if type(repository) is not RepositorySnapshotV1:
                raise SoloMaintainerClosureError()
            commit = _remote_commit()
            if commit != repository.final_master_binding.final_commit_oid:
                raise SoloMaintainerClosureError(ClosureErrorCode.MASTER_DRIFT)
            guardrail = collect_verified_guardrail()
            records, steps = _hosted_records(repository, commit)
            return GitHubEvidenceSnapshotV1.create(
                remote_commit_oid=commit, hosted_evidence=records,
                github_guardrail_snapshot=guardrail,
                hosted_step_fingerprints=steps)
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError(
                ClosureErrorCode.HOSTED_EVIDENCE_REJECTED) from None
def _production_mapping(value: object, binding: FinalMasterBindingV1) -> dict[str, object]:
    try:
        mapping = value.to_mapping()
    except Exception:
        raise SoloMaintainerClosureError() from None
    if (type(mapping) is not dict or mapping.get("binding_type") != "ApprovedCutoverBindingV3"
            or mapping.get("final_master_binding_fingerprint") != binding.binding_fingerprint
            or not is_fingerprint(mapping.get("binding_fingerprint"))):
        raise SoloMaintainerClosureError()
    return mapping
def _ordered_pairs(value: object, names: tuple[str, ...], git: bool = False):
    if type(value) is not dict or set(value) != set(names):
        raise SoloMaintainerClosureError()
    result = tuple((name, value[name]) for name in names)
    validator = is_git_oid if git else is_fingerprint
    if any(not validator(item) for _name, item in result):
        raise SoloMaintainerClosureError()
    return result
def _git(*arguments: str) -> bytes:
    environment = {"PATH": os.pathsep.join(os.get_exec_path()), "GIT_TERMINAL_PROMPT": "0",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                   "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C", "LANG": "C"}
    completed = subprocess.run(
        ("git", "--no-replace-objects", "-c", "core.fsmonitor=false", *arguments),
        cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, capture_output=True,
        timeout=30, check=False)
    if completed.returncode or len(completed.stdout) > _MAX_OUTPUT or completed.stderr:
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    return completed.stdout
def _tree_descriptors(tree: str) -> tuple[tuple[str, str, str, bytes], ...]:
    records = _git("ls-tree", "-r", "-z", "--full-tree", tree).split(b"\0")
    result = []
    for record in records[:-1]:
        header, path_bytes = record.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ")
        path = path_bytes.decode("utf-8")
        if kind != "blob" or mode not in {"100644", "100755"} or not _safe_git_path(path):
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        content = _git("cat-file", "blob", oid)
        result.append((path, mode, oid, content))
    if records[-1] or not result:
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    return tuple(result)
def _require_index_and_checkout(descriptors) -> None:
    expected = {path: (mode, oid, content) for path, mode, oid, content in descriptors}
    staged = {}
    records = _git("ls-files", "--stage", "-z").split(b"\0")
    for record in records[:-1]:
        header, raw_path = record.split(b"\t", 1)
        mode, oid, stage = header.decode("ascii").split(" ")
        staged[raw_path.decode("utf-8")] = mode, oid, stage
    flags = _git("ls-files", "-v", "-z").split(b"\0")
    expected_stage = {path: (mode, oid, "0") for path, (mode, oid, _data) in expected.items()}
    visible = {item[2:].decode("utf-8") for item in flags[:-1] if item.startswith(b"H ")}
    if records[-1] or flags[-1] or staged != expected_stage or visible != set(expected):
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    for path, (_mode, _oid, content) in expected.items():
        target = ROOT.joinpath(*PurePosixPath(path).parts); before = os.lstat(target)
        observed = target.read_bytes(); after = os.lstat(target)
        reparse = getattr(before, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if (not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or reparse
                or target.is_symlink() or observed != content
                or (after.st_dev, after.st_ino, after.st_mode, after.st_size)
                != (before.st_dev, before.st_ino, before.st_mode, before.st_size)):
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
def _source_package(head: str, tree: str, descriptors: tuple[tuple[str, str, str, bytes], ...]):
    from backend.r2_ci_provenance_v2 import R2GitObjectEntryV2, R2GitObjectSourcePackageV2
    from backend.r2_ci_provenance_v2._canonical import sha256
    from scripts.r2_ci_provenance_support import _workflow_lock
    raw = {path: content for path, _mode, _oid, content in descriptors}
    runbook = "docs/operations/r2_final_operator_runbook.md"
    entries = tuple(R2GitObjectEntryV2.create(
        relative_path=path, mode=mode, blob_oid=oid, content_bytes=content)
        for path, mode, oid, content in descriptors)
    package = R2GitObjectSourcePackageV2.create(
        final_commit_oid=head, final_tree_oid=tree, observed_commit_oid=head,
        observed_tree_oid=tree, entries=entries, workflow_lock=_workflow_lock(raw),
        runbook_fingerprint=sha256(b"r2-operator-runbook-document-v2\0" + raw[runbook]))
    return package, raw
def _local_sources(binding: FinalMasterBindingV1, production: object, descriptors): return collect_repository_subjects(binding, production, descriptors)
def _blob_oid(descriptors: tuple[tuple[str, str, str, bytes], ...], path: str) -> str:
    matches = [oid for name, _mode, oid, _content in descriptors if name == path]
    if len(matches) != 1 or not is_git_oid(matches[0]):
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    return matches[0]
def _safe_git_path(value: str) -> bool:
    path = PurePosixPath(value)
    return (value == path.as_posix() and not path.is_absolute() and value not in {"", "."}
            and all(part not in {"", ".", ".."} for part in path.parts))
def _remote_commit() -> str:
    value = _get_json(f"/repos/{_REPOSITORY}/git/ref/heads/master")
    commit = value.get("object", {}).get("sha") if type(value) is dict else None
    if not is_git_oid(commit):
        raise SoloMaintainerClosureError(ClosureErrorCode.MASTER_DRIFT)
    return commit
def _hosted_records(repository: RepositorySnapshotV1, commit: str):
    runs = _get_json(f"/repos/{_REPOSITORY}/actions/runs?branch=master&event=push&per_page=100")
    values = runs.get("workflow_runs") if type(runs) is dict else None
    if type(values) is not list:
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    quality = _latest_run(values, FIXED_CHECKS[0][1], commit)
    provenance = _latest_run(values, FIXED_CHECKS[1][1], commit)
    checks = _check_runs(commit)
    quality_jobs, provenance_jobs = _jobs_for_run(quality), _jobs_for_run(provenance)
    records = [_record_from_run(quality, FIXED_CHECKS[0], repository, quality_jobs, checks)]
    records.extend(_record_from_run(provenance, item, repository, provenance_jobs, checks)
                   for item in FIXED_CHECKS[1:])
    values = tuple(records)
    return values, hosted_step_fingerprints(values, quality_jobs, provenance_jobs)
def _jobs_for_run(run: dict[str, object]) -> list[object]:
    path = (f"/repos/{_REPOSITORY}/actions/runs/{run.get('id')}/attempts/"
            f"{run.get('run_attempt')}/jobs?per_page=100")
    value = _get_json(path); jobs = value.get("jobs") if type(value) is dict else None
    if type(jobs) is not list or value.get("total_count") != len(jobs):
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    return jobs
def _record_from_run(run: dict[str, object], spec: tuple[str, str],
                     repository: RepositorySnapshotV1, jobs: list[object], checks: dict):
    matches = [job for job in jobs if type(job) is dict and job.get("name") == spec[0]]
    job = matches[0] if len(matches) == 1 else {}; check_id = _check_id(job.get("check_run_url"))
    check = checks.get(check_id)
    if len(matches) != 1 or check is None:
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    if (job.get("status") != "completed" or job.get("conclusion") != "success"
            or check.get("name") != spec[0] or check.get("head_sha") != run.get("head_sha")):
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    return HostedCheckEvidenceV1.create(
        workflow_path=spec[1], workflow_blob_oid=repository.workflow_blob_oid(spec[1]),
        workflow_run_id=run["id"], workflow_run_number=run["run_number"],
        workflow_run_attempt=run["run_attempt"], job_name=spec[0], job_id=job["id"],
        check_run_id=check["id"], head_sha=run["head_sha"],
        started_at_utc=job["started_at"], completed_at_utc=job["completed_at"])
def _check_runs(commit: str) -> dict[str, dict[str, object]]:
    value = _get_json(f"/repos/{_REPOSITORY}/commits/{commit}/check-runs?per_page=100")
    runs = value.get("check_runs") if type(value) is dict else None
    result = {}
    for item in runs or []:
        app = item.get("app") if type(item) is dict else None
        if (item.get("name") in dict(FIXED_CHECKS) and item.get("status") == "completed"
                and item.get("conclusion") == "success" and type(app) is dict
                and app.get("id") == 15368 and app.get("slug") == "github-actions"):
            if type(item.get("id")) is not int or item["id"] in result:
                raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
            result[item["id"]] = item
    return result
def _check_id(value: object):
    prefix = f"{_API}/repos/{_REPOSITORY}/check-runs/"
    suffix = value[len(prefix):] if type(value) is str and value.startswith(prefix) else ""
    return int(suffix) if suffix.isascii() and suffix.isdigit() and not suffix.startswith("0") else None
def _get_json(path: str):
    if type(path) is not str or not path.startswith(f"/repos/{_REPOSITORY}/"):
        raise SoloMaintainerClosureError()
    request = urllib.request.Request(
        _API + path, headers={"Accept": "application/vnd.github+json",
                              "User-Agent": "email-ai-assistant-r2-closure"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read(_MAX_OUTPUT + 1)
    except urllib.error.HTTPError:
        raise SoloMaintainerClosureError() from None
    if len(payload) > _MAX_OUTPUT:
        raise SoloMaintainerClosureError()
    try:
        return json.loads(payload.decode("utf-8"), parse_constant=lambda _item: _invalid_json())
    except Exception:
        raise SoloMaintainerClosureError() from None
def _invalid_json() -> None:
    raise SoloMaintainerClosureError()
