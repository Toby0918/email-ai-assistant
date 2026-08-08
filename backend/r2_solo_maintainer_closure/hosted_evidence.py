"""Strict public GitHub provenance and branch-guardrail evidence values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ._canonical import (
    CanonicalValue, allocate_value, canonical_json, fingerprint,
    is_fingerprint, is_git_oid, strict_object,
)
from .contracts import ClosureErrorCode, SoloMaintainerClosureError


REPOSITORY = "Toby0918/email-ai-assistant"
FIXED_CHECKS = (
    ("quality-gates", ".github/workflows/agent_guardrails.yml"),
    ("portable-provenance", ".github/workflows/r2_provenance.yml"),
    ("windows-native-provenance", ".github/workflows/r2_provenance.yml"),
    ("windows-independent-provenance", ".github/workflows/r2_provenance.yml"),
    ("provenance-reconciliation", ".github/workflows/r2_provenance.yml"),
)
HOSTED_STEP_KEYS = (
    "quality-gates:Run architecture guardrails",
    "quality-gates:Run static linter guardrails",
    "quality-gates:Run mechanical rule guardrails",
    "quality-gates:Run full test suite",
    "quality-gates:Run maintenance scan",
    "portable-provenance:Verify portable Git-object provenance",
    "windows-native-provenance:Verify Windows native Git-object provenance",
    "windows-independent-provenance:Verify independent Windows process provenance",
    "provenance-reconciliation:Reconcile exact same-package receipts",
)
_RECORD_BODY = (
    "record_type", "repository", "workflow_path", "workflow_blob_oid",
    "workflow_run_id", "workflow_run_number", "workflow_run_attempt",
    "job_name", "job_id", "check_run_id", "head_branch", "head_sha",
    "event", "status", "conclusion", "check_app_id", "check_app_slug",
    "started_at_utc", "completed_at_utc", "hosted_evidence_human_approval_count",
)
class HostedCheckEvidenceV1(CanonicalValue):
    @classmethod
    def create(cls, **values: object):
        body = {"record_type": "HostedCheckEvidenceV1", "repository": REPOSITORY,
                "head_branch": "master", "event": "push", "status": "completed",
                "conclusion": "success", "check_app_id": 15368,
                "check_app_slug": "github-actions",
                "hosted_evidence_human_approval_count": 0, **values}
        _validate_record_body(body)
        return allocate_value(cls, {**body, "record_fingerprint": fingerprint(
            "r2-hosted-check-evidence-v1", body)})

    @classmethod
    def from_json(cls, payload: object):
        try:
            source = strict_object(payload)
            if set(source) != {*_RECORD_BODY, "record_fingerprint"}:
                raise SoloMaintainerClosureError()
            body = {name: source[name] for name in _RECORD_BODY}
            _validate_record_body(body)
            if source["record_fingerprint"] != fingerprint(
                    "r2-hosted-check-evidence-v1", body):
                raise SoloMaintainerClosureError()
            return allocate_value(cls, source)
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError() from None

    @classmethod
    def from_mapping(cls, source: object):
        return cls.from_json(canonical_json(source))
def hosted_evidence_set_fingerprint(records: tuple[HostedCheckEvidenceV1, ...]) -> str:
    _validate_records(records)
    return fingerprint("r2-hosted-check-evidence-set-v1", {
        "set_type": "HostedCheckEvidenceSetV1",
        "record_fingerprints": [item.record_fingerprint for item in records],
    })


_SNAPSHOT_BODY = (
    "snapshot_type", "repository", "ruleset_id", "ruleset_name", "ruleset_target",
    "ruleset_enforcement", "ruleset_configuration", "ruleset_configuration_fingerprint",
    "ruleset_count_for_master", "classic_branch_protection_present", "bypass_actor_count",
    "required_status_check_count", "required_status_check_app_id",
)
class GitHubGuardrailSnapshotV1(CanonicalValue):
    @classmethod
    def create(cls, *, ruleset_id: object, ruleset_configuration: object):
        configuration = _require_configuration(ruleset_configuration)
        body = {
            "snapshot_type": "GitHubGuardrailSnapshotV1", "repository": REPOSITORY,
            "ruleset_id": ruleset_id, "ruleset_name": "master-solo-maintainer-closure-v1",
            "ruleset_target": "branch", "ruleset_enforcement": "active",
            "ruleset_configuration": configuration,
            "ruleset_configuration_fingerprint": fingerprint(
                "r2-github-ruleset-configuration-v1", configuration),
            "ruleset_count_for_master": 1, "classic_branch_protection_present": 0,
            "bypass_actor_count": 0, "required_status_check_count": 5,
            "required_status_check_app_id": 15368,
        }
        _validate_snapshot_body(body)
        return allocate_value(cls, {**body, "snapshot_fingerprint": fingerprint(
            "r2-github-guardrail-snapshot-v1", body)})

    @classmethod
    def from_json(cls, payload: object):
        try:
            source = strict_object(payload)
            if set(source) != {*_SNAPSHOT_BODY, "snapshot_fingerprint"}:
                raise SoloMaintainerClosureError()
            body = {name: source[name] for name in _SNAPSHOT_BODY}
            _validate_snapshot_body(body)
            if source["snapshot_fingerprint"] != fingerprint(
                    "r2-github-guardrail-snapshot-v1", body):
                raise SoloMaintainerClosureError()
            return allocate_value(cls, source)
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError() from None

    @classmethod
    def from_mapping(cls, source: object):
        return cls.from_json(canonical_json(source))
@dataclass(frozen=True, slots=True, repr=False)
class GitHubEvidenceSnapshotV1:
    remote_commit_oid: str
    hosted_evidence: tuple[HostedCheckEvidenceV1, ...]
    github_guardrail_snapshot: GitHubGuardrailSnapshotV1
    hosted_step_fingerprints: tuple[tuple[str, str], ...]
    hosted_evidence_set_fingerprint: str

    @classmethod
    def create(cls, *, remote_commit_oid: object, hosted_evidence: object,
               github_guardrail_snapshot: object, hosted_step_fingerprints: object):
        if (not is_git_oid(remote_commit_oid) or type(hosted_evidence) is not tuple
                or type(github_guardrail_snapshot) is not GitHubGuardrailSnapshotV1
                or type(hosted_step_fingerprints) is not dict
                or set(hosted_step_fingerprints) != set(HOSTED_STEP_KEYS)
                or any(not is_fingerprint(value)
                       for value in hosted_step_fingerprints.values())):
            raise SoloMaintainerClosureError()
        _validate_records(hosted_evidence)
        if any(item.head_sha != remote_commit_oid for item in hosted_evidence):
            raise SoloMaintainerClosureError()
        steps = tuple((name, hosted_step_fingerprints[name]) for name in HOSTED_STEP_KEYS)
        return cls(remote_commit_oid, hosted_evidence, github_guardrail_snapshot, steps,
                   hosted_evidence_set_fingerprint(hosted_evidence))

    def step_fingerprint(self, key: str) -> str:
        try:
            return dict(self.hosted_step_fingerprints)[key]
        except KeyError:
            raise SoloMaintainerClosureError() from None
def ruleset_configuration_v1() -> dict[str, object]:
    return strict_object(canonical_json({
        "name": "master-solo-maintainer-closure-v1", "target": "branch",
        "enforcement": "active", "bypass_actors": [],
        "conditions": {"ref_name": {"include": ["refs/heads/master"], "exclude": []}},
        "rules": [
            {"type": "deletion"}, {"type": "non_fast_forward"},
            {"type": "pull_request", "parameters": {
                "allowed_merge_methods": ["merge", "squash", "rebase"],
                "dismiss_stale_reviews_on_push": False, "require_code_owner_review": False,
                "require_last_push_approval": False, "required_approving_review_count": 0,
                "required_review_thread_resolution": True}},
            {"type": "required_status_checks", "parameters": {
                "do_not_enforce_on_create": False,
                "strict_required_status_checks_policy": True,
                "required_status_checks": [
                    {"context": name, "integration_id": 15368}
                    for name, _path in FIXED_CHECKS]}},
        ],
    }))
def normalize_ruleset_configuration(detail: object) -> dict[str, object]:
    fields = ("name", "target", "enforcement", "bypass_actors", "conditions", "rules")
    if type(detail) is not dict or any(name not in detail for name in fields):
        raise SoloMaintainerClosureError()
    return {name: detail[name] for name in fields}


def require_reconciliation_graph(payload: bytes) -> None:
    expected = (b"\n  provenance-reconciliation:\n    needs:\n"
                b"      - portable-provenance\n      - windows-native-provenance\n"
                b"      - windows-independent-provenance\n    runs-on:")
    if type(payload) is not bytes or payload.count(expected) != 1:
        raise SoloMaintainerClosureError()


def latest_successful_run(runs: list[object], path: str, commit: str) -> dict[str, object]:
    matches = [item for item in runs if type(item) is dict and item.get("path") == path
               and item.get("head_sha") == commit and item.get("head_branch") == "master"
               and item.get("event") == "push"]
    if not matches:
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    selected = max(matches, key=lambda item: (
        item.get("run_number", -1), item.get("run_attempt", -1), item.get("id", -1)))
    if selected.get("status") != "completed" or selected.get("conclusion") != "success":
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    return selected


def validate_hosted_manifest_parts(body: dict[str, object]) -> None:
    raw_records, raw_snapshot = body.get("hosted_evidence"), body.get("github_guardrail_snapshot")
    if type(raw_records) is not list or len(raw_records) != 5:
        raise SoloMaintainerClosureError()
    records = tuple(HostedCheckEvidenceV1.from_mapping(item) for item in raw_records)
    snapshot = GitHubGuardrailSnapshotV1.from_mapping(raw_snapshot)
    if (body.get("hosted_evidence_count") != 5
            or body.get("hosted_evidence_set_fingerprint") != hosted_evidence_set_fingerprint(records)
            or body.get("github_guardrail_snapshot_fingerprint") != snapshot.snapshot_fingerprint):
        raise SoloMaintainerClosureError()


def _validate_record_body(body: dict[str, object]) -> None:
    expected = {"record_type": "HostedCheckEvidenceV1", "repository": REPOSITORY,
                "head_branch": "master", "event": "push", "status": "completed",
                "conclusion": "success", "check_app_id": 15368,
                "check_app_slug": "github-actions", "hosted_evidence_human_approval_count": 0}
    integers = ("workflow_run_id", "workflow_run_number", "workflow_run_attempt",
                "job_id", "check_run_id")
    path_by_name = dict(FIXED_CHECKS)
    if (set(body) != set(_RECORD_BODY) or any(body.get(name) != value for name, value in expected.items())
            or body.get("job_name") not in path_by_name
            or body.get("workflow_path") != path_by_name.get(body.get("job_name"))
            or not is_git_oid(body.get("workflow_blob_oid")) or not is_git_oid(body.get("head_sha"))
            or any(type(body.get(name)) is not int or body[name] < 1 for name in integers)
            or any(not _valid_timestamp(body.get(name))
                   for name in ("started_at_utc", "completed_at_utc"))
            or body.get("started_at_utc") > body.get("completed_at_utc")):
        raise SoloMaintainerClosureError()


def _valid_timestamp(value: object) -> bool:
    try:
        return type(value) is str and datetime.strptime(
            value, "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%dT%H:%M:%SZ") == value
    except (TypeError, ValueError):
        return False


def _validate_records(records: tuple[HostedCheckEvidenceV1, ...]) -> None:
    if (type(records) is not tuple or len(records) != 5
            or any(type(item) is not HostedCheckEvidenceV1 for item in records)
            or tuple((item.job_name, item.workflow_path) for item in records) != FIXED_CHECKS
            or len({item.record_fingerprint for item in records}) != 5):
        raise SoloMaintainerClosureError()
    provenance = records[1:]
    if len({(item.workflow_run_id, item.workflow_run_attempt) for item in provenance}) != 1:
        raise SoloMaintainerClosureError()


def hosted_step_fingerprints(records: tuple[object, ...], *job_sets: list[object]):
    by_record = {item.job_name: item for item in records}
    jobs = tuple(job for values in job_sets for job in values if type(job) is dict)
    result = {}
    for key in HOSTED_STEP_KEYS:
        job_name, step_name = key.split(":", 1)
        matches = tuple(job for job in jobs if job.get("name") == job_name)
        job = matches[0] if len(matches) == 1 else None
        record = by_record.get(job_name)
        steps = job.get("steps") if type(job) is dict else None
        matches = [item for item in steps or () if type(item) is dict
                   and item.get("name") == step_name]
        step = matches[0] if len(matches) == 1 else {}
        if (record is None or type(job) is not dict or job.get("id") != record.job_id
                or step.get("status") != "completed"
                or step.get("conclusion") != "success"
                or type(step.get("number")) is not int or step["number"] < 1):
            raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
        result[key] = fingerprint("r2-local-source-proof-v1", {
            "subject_type": "HOSTED_JOB_STEP", "source": job_name,
            "hosted_record_fingerprint": record.record_fingerprint,
            "step_name": step_name, "step_number": step["number"],
            "status": "completed", "conclusion": "success"})
    return result


def _require_configuration(value: object) -> dict[str, object]:
    if type(value) is not dict or canonical_json(value) != canonical_json(ruleset_configuration_v1()):
        raise SoloMaintainerClosureError()
    return strict_object(canonical_json(value))


def _validate_snapshot_body(body: dict[str, object]) -> None:
    configuration = _require_configuration(body.get("ruleset_configuration"))
    expected = {"snapshot_type": "GitHubGuardrailSnapshotV1", "repository": REPOSITORY,
                "ruleset_name": "master-solo-maintainer-closure-v1", "ruleset_target": "branch",
                "ruleset_enforcement": "active", "ruleset_count_for_master": 1,
                "classic_branch_protection_present": 0, "bypass_actor_count": 0,
                "required_status_check_count": 5, "required_status_check_app_id": 15368,
                "ruleset_configuration_fingerprint": fingerprint(
                    "r2-github-ruleset-configuration-v1", configuration)}
    if (set(body) != set(_SNAPSHOT_BODY) or type(body.get("ruleset_id")) is not int
            or body["ruleset_id"] < 1 or any(body.get(name) != value for name, value in expected.items())):
        raise SoloMaintainerClosureError()
