"""Closed Issue #38 decision and R1-blocker completion-proof registries."""

from dataclasses import dataclass

from backend.r2_transaction_journal_v2._canonical import fingerprint


@dataclass(frozen=True, slots=True)
class R2RunbookDecisionV2:
    ordinal: int
    decision_id: str
    title: str
    completion_proof: str

    def to_mapping(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True)
class R2R1BlockerResolutionV2:
    issue: int
    blocker_class: str
    completion_proof: str

    def to_mapping(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


_DECISIONS = tuple(
    R2RunbookDecisionV2(index, *values)
    for index, values in enumerate((
        ("R2-D38-01", "Maintenance window", "final-master binding and human review"),
        ("R2-D38-02", "Start stop and abort gates", "unified journal and incident-stop proof"),
        ("R2-D38-03", "Legacy source", "Git-byte and exact-identity proof"),
        ("R2-D38-04", "Container ACL", "Windows-native ACL and parent-scope proof"),
        ("R2-D38-05", "Evidence", "reviewed create-only package and retention proof"),
        ("R2-D38-06", "Worktrees", "fourteen-ref eleven-worktree Git-byte proof"),
        ("R2-D38-07", "Runtime", "hash-locked dependency and Runtime publication proof"),
        ("R2-D38-08", "LocalData", "stopped create-only SQLite publication proof"),
        ("R2-D38-09", "Browser extension", "create-only CRX publication proof"),
        ("R2-D38-10", "Config and providers", "create-only Config and provider-disabled proof"),
        ("R2-D38-11", "Preflight", "six-verb production composition proof"),
        ("R2-D38-12", "Post-cutover verification", "two-start lifecycle and independent-audit proof"),
        ("R2-D38-13", "Rollback", "journal-derived LIFO legacy restoration proof"),
        ("R2-D38-14", "Retention and no deletion", "object ledger and zero-delete capability proof"),
    ))
)

_BLOCKERS = (
    R2R1BlockerResolutionV2(34, "real host audit composition", "preflight production root and final-audit receipt"),
    R2R1BlockerResolutionV2(35, "host baseline and evidence composition", "evidence production root and verified package receipt"),
    R2R1BlockerResolutionV2(36, "mixed worktree transaction and recovery", "Git-byte receipt unified journal and rollback seal"),
    R2R1BlockerResolutionV2(37, "managed unit publication and lifecycle", "Runtime SQLite CRX Config and two-start receipts"),
)


def issue38_decision_registry_v2():
    return _DECISIONS


def r1_blocker_resolution_registry_v2():
    return _BLOCKERS


def decision_registry_fingerprint_v2():
    return fingerprint("r2-issue38-decision-registry-v2", [item.to_mapping() for item in _DECISIONS])


def blocker_resolution_fingerprint_v2():
    return fingerprint("r2-r1-blocker-resolution-registry-v2", [item.to_mapping() for item in _BLOCKERS])
