"""Only prepare/confirm orchestration for Solo Maintainer Closure."""

from __future__ import annotations

import ctypes
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import os
import sys
import time
import unicodedata

from ._canonical import canonical_json, is_fingerprint
from .contracts import (
    ASSURANCE_MODEL, CONFIRMATION_ACKNOWLEDGEMENT, CONFIRMATION_WINDOW_SECONDS,
    ClosureErrorCode, SoloMaintainerAttestationReceiptV1, SoloMaintainerClosureCandidateV1,
    SoloMaintainerClosureError, SoloMaintainerClosureManifestV1,
)
from .evidence import (
    build_evidence_records, build_gap_proofs, evidence_set_fingerprint,
    gap_proof_set_fingerprint,
)
from .hosted_evidence import GitHubEvidenceSnapshotV1
from .local_evidence import build_local_source_proofs
from .repository import FixedGitHubPort, FixedRepositoryPort, RepositorySnapshotV1
from .storage import CreateOnlyClosureStorage


@dataclass(frozen=True, slots=True)
class _Ports:
    repository: object
    github: object
    storage: object
    console: object
    clock: object


class _SystemClock:
    def wall_epoch(self) -> int:
        return int(time.time())

    def monotonic_ns(self) -> int:
        return time.monotonic_ns()


class _WindowsConsole:
    def snapshot(self) -> tuple[int, int, int]:
        if os.name != "nt":
            raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)
        handles = []
        try:
            import msvcrt
            for stream in (sys.stdin, sys.stdout, sys.stderr):
                if not stream.isatty() or type(stream.fileno()) is not int:
                    raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)
                handle = msvcrt.get_osfhandle(stream.fileno())
                mode = ctypes.c_uint32()
                if handle == -1 or ctypes.windll.kernel32.GetConsoleMode(
                        ctypes.c_void_p(handle), ctypes.byref(mode)) != 1:
                    raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)
                handles.append(handle)
        except SoloMaintainerClosureError:
            raise
        except Exception:
            raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED) from None
        return tuple(handles)

    def require_unchanged(self, snapshot: object) -> None:
        if self.snapshot() != snapshot:
            raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)


class _ConsoleCeremony:
    def __init__(self, console: object) -> None:
        self._console = console
        self._snapshot = console.snapshot()

    def require_current(self) -> None:
        self._console.require_unchanged(self._snapshot)

    @property
    def stdin_handle(self) -> int:
        return self._snapshot[0]


_ACTIVE_CONSOLE_CEREMONY: ContextVar[object | None] = ContextVar(
    "r2_solo_maintainer_console_ceremony", default=None
)


@contextmanager
def _console_ceremony(console: object | None = None):
    active = _ACTIVE_CONSOLE_CEREMONY.get()
    if active is not None:
        yield active
        return
    guard = _ConsoleCeremony(_WindowsConsole() if console is None else console)
    token = _ACTIVE_CONSOLE_CEREMONY.set(guard)
    try:
        yield guard
    finally:
        _ACTIVE_CONSOLE_CEREMONY.reset(token)


def _fixed_ports() -> _Ports:
    return _Ports(FixedRepositoryPort(), FixedGitHubPort(),
                  CreateOnlyClosureStorage(), _WindowsConsole(), _SystemClock())


class SoloMaintainerClosure:
    """Derive one review candidate and record one fresh local attestation."""

    def __init__(self) -> None:
        self._ports = _fixed_ports()
        self._candidate = None
        self._repository = None
        self._github = None
        self._prepared_monotonic_ns = None
        self._prepare_called = False
        self._confirm_called = False

    def prepare(self) -> SoloMaintainerClosureCandidateV1:
        if self._prepare_called:
            raise SoloMaintainerClosureError()
        self._prepare_called = True
        repository, github = self._collect()
        prepared_at = self._ports.clock.wall_epoch()
        monotonic = self._ports.clock.monotonic_ns()
        if type(prepared_at) is not int or prepared_at < 0 or type(monotonic) is not int:
            raise SoloMaintainerClosureError()
        manifest = _manifest(repository, github)
        candidate = SoloMaintainerClosureCandidateV1.create(manifest, prepared_at)
        self._candidate, self._repository, self._github = candidate, repository, github
        self._prepared_monotonic_ns = monotonic
        return candidate

    def confirm(self, exact_manifest_fingerprint: str,
                exact_acknowledgement: str) -> SoloMaintainerAttestationReceiptV1:
        with _console_ceremony(self._ports.console) as console:
            return self._confirm_guarded(
                exact_manifest_fingerprint, exact_acknowledgement, console
            )

    def _confirm_guarded(self, exact_manifest_fingerprint, exact_acknowledgement,
                         console) -> SoloMaintainerAttestationReceiptV1:
        if self._confirm_called:
            raise SoloMaintainerClosureError()
        self._confirm_called = True
        candidate = self._candidate if self._candidate is not None else self.prepare()
        _require_confirmation_values(candidate, exact_manifest_fingerprint,
                                     exact_acknowledgement)
        confirmed_at = self._ports.clock.wall_epoch()
        confirmed_monotonic = self._ports.clock.monotonic_ns()
        _require_fresh(candidate, self._prepared_monotonic_ns,
                       confirmed_at, confirmed_monotonic)
        repository, github = self._collect()
        _require_same_evidence(self._repository, self._github, repository, github)
        fresh_manifest = _manifest(repository, github)
        if fresh_manifest.to_canonical_json() != candidate.manifest_value.to_canonical_json():
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        _require_fresh(candidate, self._prepared_monotonic_ns,
                       self._ports.clock.wall_epoch(),
                       self._ports.clock.monotonic_ns())
        console.require_current()
        receipt = SoloMaintainerAttestationReceiptV1.create(candidate, confirmed_at)
        manifest_payload = fresh_manifest.to_canonical_json()
        receipt_payload = receipt.to_canonical_json()

        def before_commit(staged_manifest: bytes, staged_receipt: bytes) -> None:
            self._require_commit_state(candidate, console, manifest_payload,
                                       receipt_payload, staged_manifest, staged_receipt)

        self._ports.storage.publish(manifest_payload, receipt_payload,
                                    candidate.manifest_fingerprint, before_commit)
        return receipt

    def _require_commit_state(self, candidate, console, manifest_payload,
                              receipt_payload, staged_manifest, staged_receipt) -> None:
        repository, github = self._collect()
        _require_same_evidence(self._repository, self._github, repository, github)
        fresh = _manifest(repository, github).to_canonical_json()
        if (fresh != candidate.manifest_value.to_canonical_json()
                or fresh != manifest_payload or staged_manifest != manifest_payload
                or staged_receipt != receipt_payload):
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        _require_fresh(candidate, self._prepared_monotonic_ns,
                       self._ports.clock.wall_epoch(),
                       self._ports.clock.monotonic_ns())
        console.require_current()

    def _collect(self) -> tuple[RepositorySnapshotV1, GitHubEvidenceSnapshotV1]:
        repository = self._ports.repository.collect()
        if type(repository) is not RepositorySnapshotV1:
            raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
        github = self._ports.github.collect(repository)
        if type(github) is not GitHubEvidenceSnapshotV1:
            raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
        return repository, github


def _manifest(repository: RepositorySnapshotV1,
              github: GitHubEvidenceSnapshotV1) -> SoloMaintainerClosureManifestV1:
    binding = repository.final_master_binding
    guardrail = github.github_guardrail_snapshot
    local_proofs = build_local_source_proofs(repository, github, repository.root)
    records = build_evidence_records(
        binding, local_proofs, github.hosted_evidence, guardrail)
    gaps = build_gap_proofs(binding, records)
    body = {
        "manifest_type": "SoloMaintainerClosureManifestV1",
        "final_master_binding": binding.to_mapping(),
        "final_master_binding_fingerprint": binding.binding_fingerprint,
        "final_commit_oid": binding.final_commit_oid, "final_tree_oid": binding.final_tree_oid,
        "closure_map_fingerprint": binding.closure_map_fingerprint,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "workflow_fingerprint": binding.workflow_fingerprint,
        "production_binding": repository.production_binding.to_mapping(),
        "production_binding_fingerprint": repository.production_binding.binding_fingerprint,
        "github_guardrail_snapshot": guardrail.to_mapping(),
        "github_guardrail_snapshot_fingerprint": guardrail.snapshot_fingerprint,
        "hosted_evidence": [item.to_mapping() for item in github.hosted_evidence],
        "hosted_evidence_count": 5,
        "hosted_evidence_set_fingerprint": github.hosted_evidence_set_fingerprint,
        "evidence_records": [item.to_mapping() for item in records],
        "evidence_record_count": 14, "evidence_set_fingerprint": evidence_set_fingerprint(records),
        "gap_proofs": list(gaps), "gap_proof_count": 8,
        "gap_proof_set_fingerprint": gap_proof_set_fingerprint(gaps),
        "assurance_model": ASSURANCE_MODEL, "operator_count": 1,
        **_manifest_zero_counts(),
    }
    return SoloMaintainerClosureManifestV1.create(body)


def _manifest_zero_counts() -> dict[str, int]:
    names = (
        "independent_reviewer_count", "external_signer_count",
        "hosted_evidence_human_approval_count", "solo_maintainer_attestation_count",
        "approval_count", "execution_authority_count", "issue39_authority_count",
        "historical_master_count", "open_finding_count", "contract_changing_finding_count",
        "decision_contradiction_finding_count", "security_incident_finding_count",
        "surface_omission_count", "evidence_defect_count", "required_skip_count",
        "unclassified_skip_count", "platform_divergence_count", "leakage_finding_count",
        "private_data_access_count", "real_host_operation_count", "provider_attempt_count",
        "cleanup_operation_count", "deletion_operation_count", "overwrite_operation_count",
        "failure_count",
    )
    return {name: 0 for name in names}


def _require_confirmation_values(candidate: SoloMaintainerClosureCandidateV1,
                                 supplied_fingerprint: object, supplied_ack: object) -> None:
    if (not _plain_visible(supplied_fingerprint)
            or not is_fingerprint(supplied_fingerprint)
            or supplied_fingerprint != candidate.manifest_fingerprint):
        raise SoloMaintainerClosureError(ClosureErrorCode.FINGERPRINT_REJECTED)
    if (not _plain_visible(supplied_ack)
            or supplied_ack != CONFIRMATION_ACKNOWLEDGEMENT):
        raise SoloMaintainerClosureError(ClosureErrorCode.ACKNOWLEDGEMENT_REJECTED)


def _plain_visible(value: object) -> bool:
    return (type(value) is str and value != "" and all(
        ord(character) >= 32 and not 127 <= ord(character) <= 159
        and unicodedata.category(character) != "Cf" for character in value))


def _require_fresh(candidate: SoloMaintainerClosureCandidateV1, prepared_monotonic: object,
                   confirmed_at: object, confirmed_monotonic: object) -> None:
    if (type(confirmed_at) is not int or type(confirmed_monotonic) is not int
            or type(prepared_monotonic) is not int
            or not candidate.prepared_at_epoch <= confirmed_at < candidate.expires_at_epoch
            or not 0 <= confirmed_monotonic - prepared_monotonic
            < CONFIRMATION_WINDOW_SECONDS * 1_000_000_000):
        raise SoloMaintainerClosureError(ClosureErrorCode.STALE)


def _require_same_evidence(old_repository: RepositorySnapshotV1,
                           old_github: GitHubEvidenceSnapshotV1,
                           repository: RepositorySnapshotV1,
                           github: GitHubEvidenceSnapshotV1) -> None:
    if (old_repository.final_master_binding.to_canonical_json()
            != repository.final_master_binding.to_canonical_json()
            or old_github.remote_commit_oid != github.remote_commit_oid):
        raise SoloMaintainerClosureError(ClosureErrorCode.MASTER_DRIFT)
    if old_repository.snapshot_fingerprint != repository.snapshot_fingerprint:
        raise SoloMaintainerClosureError(ClosureErrorCode.EVIDENCE_REJECTED)
    old_hosted = canonical_json([item.to_mapping() for item in old_github.hosted_evidence])
    new_hosted = canonical_json([item.to_mapping() for item in github.hosted_evidence])
    if old_hosted != new_hosted:
        raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)
    if (old_github.github_guardrail_snapshot.to_canonical_json()
            != github.github_guardrail_snapshot.to_canonical_json()):
        raise SoloMaintainerClosureError(ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED)
