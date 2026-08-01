"""Closed content-free manifest and topology receipt contracts."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import fingerprint, is_fingerprint


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RepositoryContentManifestV1:
    schema_version: int
    git_count: int
    tracked_count: int
    approved_untracked_count: int
    selected_unit_count: int
    skeleton_count: int
    retained_residue_count: int
    complete: bool
    content_observed: bool
    manifest_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated repository manifest required")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class RepositoryTopologyReceiptV1:
    schema_version: int
    status: str
    manifest_fingerprint: str = field(repr=False)
    journal_head_fingerprint: str = field(repr=False)
    repository_count: int
    worktree_count: int
    embedded_count: int
    external_count: int
    retained_residue_count: int
    original_physical_identities_retained: bool
    original_admin_identities_retained: bool
    content_observed: bool
    receipt_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated repository topology receipt required")


def build_manifest(*, items, skeleton_count: int, residue_count: int):
    categories = tuple(item.category for item in items)
    body = {
        "schema_version": 1,
        "git_count": categories.count("git"),
        "tracked_count": categories.count("tracked"),
        "approved_untracked_count": categories.count("approved_untracked"),
        "selected_unit_count": len(items),
        "skeleton_count": skeleton_count,
        "retained_residue_count": residue_count,
        "complete": True,
        "content_observed": False,
        "items": [item.contract_mapping() for item in items],
    }
    if not _valid_manifest_body(body):
        raise ValueError("repository_manifest_invalid")
    public = {key: value for key, value in body.items() if key != "items"}
    result = object.__new__(RepositoryContentManifestV1)
    _set(result, public)
    object.__setattr__(
        result,
        "manifest_fingerprint",
        fingerprint("repository-content-manifest-v1", body),
    )
    return result


def build_receipt(
    *,
    status: str,
    manifest_fingerprint: str,
    journal_head_fingerprint: str,
    retained_residue_count: int,
) -> RepositoryTopologyReceiptV1:
    body = {
        "schema_version": 1,
        "status": status,
        "manifest_fingerprint": manifest_fingerprint,
        "journal_head_fingerprint": journal_head_fingerprint,
        "repository_count": 1,
        "worktree_count": 11,
        "embedded_count": 8,
        "external_count": 3,
        "retained_residue_count": retained_residue_count,
        "original_physical_identities_retained": True,
        "original_admin_identities_retained": True,
        "content_observed": False,
    }
    if (
        status not in {
            "REPOSITORY_TOPOLOGY_PUBLISHED",
            "LEGACY_FLAT_LAYOUT_RESTORED",
        }
        or not is_fingerprint(manifest_fingerprint)
        or not is_fingerprint(journal_head_fingerprint)
        or type(retained_residue_count) is not int
        or retained_residue_count < 1
    ):
        raise ValueError("repository_topology_receipt_invalid")
    result = object.__new__(RepositoryTopologyReceiptV1)
    _set(result, body)
    object.__setattr__(
        result,
        "receipt_fingerprint",
        fingerprint("repository-topology-receipt-v1", body),
    )
    return result


def _valid_manifest_body(body: dict[str, object]) -> bool:
    return (
        body["git_count"] == 1
        and body["tracked_count"] >= 1
        and body["approved_untracked_count"] >= 0
        and body["selected_unit_count"] == len(body["items"])
        and body["selected_unit_count"] >= 2
        and type(body["skeleton_count"]) is int
        and body["skeleton_count"] >= 0
        and type(body["retained_residue_count"]) is int
        and body["retained_residue_count"] >= 1
    )


def _set(target: object, values: dict[str, object]) -> None:
    for name, value in values.items():
        object.__setattr__(target, name, value)
