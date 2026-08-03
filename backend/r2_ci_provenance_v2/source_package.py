"""Frozen Git-object byte source package for final-master CI."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from ._canonical import canonical_json, fingerprint, is_fingerprint, is_oid, sha256
from .errors import R2CiProvenanceError


_MODES = {"100644", "100755", "120000"}


@dataclass(frozen=True, slots=True, repr=False)
class R2GitObjectEntryV2:
    path_fingerprint: str = field(repr=False)
    mode: str
    blob_oid: str = field(repr=False)
    byte_sha256: str = field(repr=False)
    byte_count: int

    @classmethod
    def create(cls, *, relative_path, mode, blob_oid, content_bytes):
        try:
            if not _safe_relative(relative_path) or mode not in _MODES:
                raise R2CiProvenanceError()
            if not is_oid(blob_oid) or type(content_bytes) is not bytes:
                raise R2CiProvenanceError()
            framed = b"blob " + str(len(content_bytes)).encode("ascii") + b"\0" + content_bytes
            if hashlib.sha1(framed).hexdigest() != blob_oid:
                raise R2CiProvenanceError()
            return cls(sha256(relative_path.encode("utf-8")), mode, blob_oid,
                       sha256(content_bytes), len(content_bytes))
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    def to_mapping(self):
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


@dataclass(frozen=True, slots=True, init=False, repr=False)
class R2GitObjectSourcePackageV2:
    package_type: str
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    selected_entry_count: int
    selected_byte_count: int
    workflow_lock_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    historical_package_count: int
    ignored_content_reads: int
    private_content_reads: int
    entries: tuple[R2GitObjectEntryV2, ...] = field(repr=False)
    source_package_fingerprint: str = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("R2GitObjectSourcePackageV2 requires create()")

    @classmethod
    def create(cls, **values):
        expected = {"final_commit_oid", "final_tree_oid", "observed_commit_oid",
                    "observed_tree_oid", "entries", "workflow_lock", "runbook_fingerprint"}
        try:
            if set(values) != expected:
                raise R2CiProvenanceError()
            _require_identity(values)
            entries = _normalize_entries(values["entries"])
            body = _package_body(values, entries)
            result = object.__new__(cls)
            for name, item in body.items():
                object.__setattr__(result, name, item)
            object.__setattr__(result, "entries", entries)
            object.__setattr__(result, "source_package_fingerprint",
                               fingerprint("r2-git-object-source-package-v2", _public_body(body, entries)))
            return result
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    def to_mapping(self):
        body = {name: getattr(self, name) for name in self.__dataclass_fields__
                if name not in {"entries", "source_package_fingerprint"}}
        return {**_public_body(body, self.entries),
                "source_package_fingerprint": self.source_package_fingerprint}

    def to_canonical_json(self):
        return canonical_json(self.to_mapping())


def _safe_relative(value):
    if type(value) is not str or not 1 <= len(value.encode("utf-8")) <= 4096:
        return False
    if value.startswith("/") or "\\" in value or any(ord(item) < 32 for item in value):
        return False
    parts = value.split("/")
    return all(part not in {"", ".", ".."} for part in parts)


def _require_identity(values):
    commit, tree = values["final_commit_oid"], values["final_tree_oid"]
    if not is_oid(commit) or not is_oid(tree):
        raise R2CiProvenanceError()
    if commit != values["observed_commit_oid"] or tree != values["observed_tree_oid"]:
        raise R2CiProvenanceError()
    if not is_fingerprint(values["runbook_fingerprint"]):
        raise R2CiProvenanceError()
    from .workflow_lock import R2WorkflowLockV2
    if type(values["workflow_lock"]) is not R2WorkflowLockV2:
        raise R2CiProvenanceError()


def _normalize_entries(values):
    if type(values) is not tuple or not 1 <= len(values) <= 20_000:
        raise R2CiProvenanceError()
    if any(type(item) is not R2GitObjectEntryV2 for item in values):
        raise R2CiProvenanceError()
    result = tuple(sorted(values, key=lambda item: item.path_fingerprint))
    if len({item.path_fingerprint for item in result}) != len(result):
        raise R2CiProvenanceError()
    return result


def _package_body(values, entries):
    return {
        "package_type": "R2GitObjectSourcePackageV2",
        "final_commit_oid": values["final_commit_oid"],
        "final_tree_oid": values["final_tree_oid"],
        "selected_entry_count": len(entries),
        "selected_byte_count": sum(item.byte_count for item in entries),
        "workflow_lock_fingerprint": values["workflow_lock"].lock_fingerprint,
        "runbook_fingerprint": values["runbook_fingerprint"],
        "historical_package_count": 0,
        "ignored_content_reads": 0,
        "private_content_reads": 0,
    }


def _public_body(body, entries):
    return {**body, "entries": [item.to_mapping() for item in entries]}
