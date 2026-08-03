"""Same-package CI provenance receipts and reconciliation bundle."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ._canonical import canonical_json, fingerprint, is_fingerprint, strict_object
from .errors import R2CiProvenanceError
from .source_package import R2GitObjectSourcePackageV2
from .suites import CiProvenanceKindV2, fixed_suite_fingerprint_v2
from .workflow_lock import R2WorkflowLockV2


class CiProvenanceStatusV2(str, Enum):
    CI_PROVENANCE_VERIFIED = "CI_PROVENANCE_VERIFIED"
    CI_PROVENANCE_RECONCILED = "CI_PROVENANCE_RECONCILED"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2CiProvenanceReceiptV2:
    receipt_type: str
    status: CiProvenanceStatusV2
    provenance_kind: CiProvenanceKindV2
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    selected_entry_count: int
    selected_byte_count: int
    workflow_lock_fingerprint: str = field(repr=False)
    dependency_lock_fingerprint: str = field(repr=False)
    platform_lock_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    suite_fingerprint: str = field(repr=False)
    runner_fingerprint: str = field(repr=False)
    installed_dependency_fingerprint: str = field(repr=False)
    hash_locked_dependency_count: int
    wheel_hash_count: int
    portable_full_suite: int
    historical_package_count: int
    required_skip_count: int
    platform_divergence_count: int
    leakage_finding_count: int
    failure_count: int
    private_content_reads: int
    worktree_content_reads: int
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2CiProvenanceReceiptV2 requires create()")

    @classmethod
    def create(cls, **values):
        try:
            _require_receipt_inputs(values)
            package, kind = values["source_package"], values["provenance_kind"]
            body = _receipt_body(package, kind, values)
            return _allocate(cls, body, "receipt_fingerprint",
                             fingerprint("r2-ci-provenance-receipt-v2", body))
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    @classmethod
    def from_json(cls, payload, *, source_package, workflow_lock):
        try:
            source = strict_object(payload)
            result = cls.create(
                source_package=source_package,
                workflow_lock=workflow_lock,
                provenance_kind=CiProvenanceKindV2(source["provenance_kind"]),
                runner_fingerprint=source["runner_fingerprint"],
                installed_dependency_fingerprint=source["installed_dependency_fingerprint"],
                suite_fingerprint=source["suite_fingerprint"],
                required_skip_count=source["required_skip_count"],
                platform_divergence_count=source["platform_divergence_count"],
                leakage_finding_count=source["leakage_finding_count"],
                failure_count=source["failure_count"],
            )
            if payload != canonical_json(source) or source != result.to_mapping():
                raise R2CiProvenanceError()
            return result
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    def to_mapping(self):
        return _mapping(self)

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2CiProvenanceBundleV2:
    bundle_type: str
    status: CiProvenanceStatusV2
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    workflow_lock_fingerprint: str = field(repr=False)
    dependency_lock_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    provenance_receipt_count: int
    historical_package_count: int
    required_skip_count: int
    platform_divergence_count: int
    leakage_finding_count: int
    failure_count: int
    runner_fingerprint_count: int
    hash_locked_dependency_count: int
    wheel_hash_count: int
    portable_full_suite_receipt_count: int
    receipt_set_fingerprint: str = field(repr=False)
    bundle_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2CiProvenanceBundleV2 requires create()")

    @classmethod
    def create(cls, *, source_package, workflow_lock, receipts):
        try:
            ordered = _require_bundle_inputs(source_package, workflow_lock, receipts)
            body = _bundle_body(source_package, workflow_lock, ordered)
            return _allocate(cls, body, "bundle_fingerprint",
                             fingerprint("r2-ci-provenance-bundle-v2", body))
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    @classmethod
    def from_json(cls, payload, *, source_package, workflow_lock, receipts):
        try:
            source = strict_object(payload)
            result = cls.create(source_package=source_package,
                                workflow_lock=workflow_lock, receipts=receipts)
            if payload != canonical_json(source) or source != result.to_mapping():
                raise R2CiProvenanceError()
            return result
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    def to_mapping(self):
        return _mapping(self)

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _require_receipt_inputs(values):
    expected = {"source_package", "workflow_lock", "provenance_kind",
                "runner_fingerprint", "installed_dependency_fingerprint",
                "suite_fingerprint", "required_skip_count",
                "platform_divergence_count", "leakage_finding_count", "failure_count"}
    if set(values) != expected:
        raise R2CiProvenanceError()
    package, lock, kind = (values["source_package"], values["workflow_lock"],
                           values["provenance_kind"])
    if type(package) is not R2GitObjectSourcePackageV2 or type(lock) is not R2WorkflowLockV2:
        raise R2CiProvenanceError()
    if type(kind) is not CiProvenanceKindV2 or package.workflow_lock_fingerprint != lock.lock_fingerprint:
        raise R2CiProvenanceError()
    if not is_fingerprint(values["runner_fingerprint"]) or not is_fingerprint(
        values["installed_dependency_fingerprint"]
    ):
        raise R2CiProvenanceError()
    if values["suite_fingerprint"] != fixed_suite_fingerprint_v2(kind):
        raise R2CiProvenanceError()
    if any(type(values[name]) is not int or values[name] != 0 for name in
           ("required_skip_count", "platform_divergence_count",
            "leakage_finding_count", "failure_count")):
        raise R2CiProvenanceError()


def _receipt_body(package, kind, values):
    lock = values["workflow_lock"]
    platform = "linux" if kind is CiProvenanceKindV2.PORTABLE else "windows"
    return {
        "receipt_type": "R2CiProvenanceReceiptV2",
        "status": CiProvenanceStatusV2.CI_PROVENANCE_VERIFIED.value,
        "provenance_kind": kind.value,
        "final_commit_oid": package.final_commit_oid,
        "final_tree_oid": package.final_tree_oid,
        "source_package_fingerprint": package.source_package_fingerprint,
        "selected_entry_count": package.selected_entry_count,
        "selected_byte_count": package.selected_byte_count,
        "workflow_lock_fingerprint": package.workflow_lock_fingerprint,
        "dependency_lock_fingerprint": lock.dependency_lock_fingerprint,
        "platform_lock_fingerprint": lock.dependency_lock.platform_fingerprint(platform),
        "runbook_fingerprint": package.runbook_fingerprint,
        "suite_fingerprint": values["suite_fingerprint"],
        "runner_fingerprint": values["runner_fingerprint"],
        "installed_dependency_fingerprint": values["installed_dependency_fingerprint"],
        "hash_locked_dependency_count": lock.dependency_lock.dependency_count,
        "wheel_hash_count": lock.dependency_lock.wheel_hash_count // 2,
        "portable_full_suite": int(kind is CiProvenanceKindV2.PORTABLE),
        "historical_package_count": 0,
        "required_skip_count": 0,
        "platform_divergence_count": 0,
        "leakage_finding_count": 0,
        "failure_count": 0,
        "private_content_reads": 0,
        "worktree_content_reads": 0,
    }


def _require_bundle_inputs(package, lock, receipts):
    if type(package) is not R2GitObjectSourcePackageV2 or type(lock) is not R2WorkflowLockV2:
        raise R2CiProvenanceError()
    if type(receipts) is not tuple or len(receipts) != len(CiProvenanceKindV2):
        raise R2CiProvenanceError()
    if any(type(item) is not R2CiProvenanceReceiptV2 for item in receipts):
        raise R2CiProvenanceError()
    ordered = tuple(sorted(receipts, key=lambda item: item.provenance_kind.value))
    if tuple(sorted(item.provenance_kind.value for item in ordered)) != tuple(
            sorted(item.value for item in CiProvenanceKindV2)):
        raise R2CiProvenanceError()
    if len({item.runner_fingerprint for item in ordered}) != len(ordered):
        raise R2CiProvenanceError()
    expected = (package.final_commit_oid, package.final_tree_oid,
                package.source_package_fingerprint, lock.lock_fingerprint,
                lock.dependency_lock_fingerprint, package.runbook_fingerprint)
    if any(_receipt_binding(item) != expected for item in ordered):
        raise R2CiProvenanceError()
    return ordered


def _receipt_binding(item):
    return (item.final_commit_oid, item.final_tree_oid, item.source_package_fingerprint,
            item.workflow_lock_fingerprint, item.dependency_lock_fingerprint,
            item.runbook_fingerprint)


def _bundle_body(package, lock, receipts):
    return {
        "bundle_type": "R2CiProvenanceBundleV2",
        "status": CiProvenanceStatusV2.CI_PROVENANCE_RECONCILED.value,
        "final_commit_oid": package.final_commit_oid,
        "final_tree_oid": package.final_tree_oid,
        "source_package_fingerprint": package.source_package_fingerprint,
        "workflow_lock_fingerprint": lock.lock_fingerprint,
        "dependency_lock_fingerprint": lock.dependency_lock_fingerprint,
        "runbook_fingerprint": package.runbook_fingerprint,
        "provenance_receipt_count": 3,
        "historical_package_count": 0,
        "required_skip_count": 0,
        "platform_divergence_count": 0,
        "leakage_finding_count": 0,
        "failure_count": 0,
        "runner_fingerprint_count": 3,
        "hash_locked_dependency_count": lock.dependency_lock.dependency_count,
        "wheel_hash_count": lock.dependency_lock.wheel_hash_count,
        "portable_full_suite_receipt_count": 1,
        "receipt_set_fingerprint": fingerprint("r2-ci-provenance-receipt-set-v2",
                                               [item.receipt_fingerprint for item in receipts]),
    }


def _mapping(value):
    result = {}
    for name in value.__dataclass_fields__:
        item = getattr(value, name)
        result[name] = item.value if isinstance(item, Enum) else item
    return result


def _allocate(kind, body, fingerprint_name, fingerprint_value):
    result = object.__new__(kind)
    for name, item in body.items():
        enum = CiProvenanceStatusV2 if name == "status" else (
            CiProvenanceKindV2 if name == "provenance_kind" else None)
        object.__setattr__(result, name, enum(item) if enum else item)
    object.__setattr__(result, fingerprint_name, fingerprint_value)
    return result
