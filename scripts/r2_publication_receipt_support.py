"""Canonical durable receipt mappings for the complete R2 verifier."""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum

from backend.cutover_composition_contracts.canonical import fingerprint, is_fingerprint
from backend.r2_config_publication import ConfigPublicationReceiptV1
from backend.r2_crx_publication import CrxPublicationReceiptV1
from backend.r2_database_publication import DatabaseTransactionResultV1
from backend.r2_evidence_process import EvidenceProcessResult
from backend.r2_main_publication import PostMoveMainAclConformanceReceiptV1
from backend.r2_repository_manifest import RepositoryTopologyReceiptV1
from backend.r2_runtime_publication import RuntimePublicationReceiptV1
from backend.r2_cross_stage_recovery.receipt_links import (
    INITIAL_JOURNAL_HEAD_FINGERPRINT,
    INITIAL_RECEIPT_FINGERPRINT,
    ReceiptPredecessorLinkV1,
)


_PUBLICATION_TYPES = (
    EvidenceProcessResult,
    PostMoveMainAclConformanceReceiptV1,
    RepositoryTopologyReceiptV1,
    RuntimePublicationReceiptV1,
    DatabaseTransactionResultV1,
    CrxPublicationReceiptV1,
    ConfigPublicationReceiptV1,
)

_FIELD_SCHEMAS = {
    "EvidenceProcessResult": ("status", "accepted", "rejected", "published"),
    "PostMoveMainAclConformanceReceiptV1": (
        "schema_version", "status", "projection_fingerprint",
        "main_identity_fingerprint", "inventory_fingerprint",
        "journal_head_fingerprint", "object_count", "owner_group_exact",
        "dacl_whole_tree_exact", "content_observed", "receipt_fingerprint",
    ),
    "RepositoryTopologyReceiptV1": (
        "schema_version", "status", "manifest_fingerprint",
        "journal_head_fingerprint", "repository_count", "worktree_count",
        "embedded_count", "external_count", "retained_residue_count",
        "original_physical_identities_retained",
        "original_admin_identities_retained", "content_observed",
        "receipt_fingerprint",
    ),
    "RuntimePublicationReceiptV1": (
        "status", "python_version", "sqlite_version", "dependency_count",
        "verification_authority", "same_volume", "complete",
        "pending_classification", "retained_artifact_count",
        "tree_fingerprint", "verification_fingerprint", "receipt_fingerprint",
    ),
    "DatabaseTransactionResultV1": (
        "status", "receipt_fingerprint", "journal_head_fingerprint",
        "lease_read_passes", "retained_artifact_count", "source_mutations",
    ),
    "CrxPublicationReceiptV1": (
        "status", "pending_state", "format_version", "size_bytes",
        "source_held_through_final_verify", "target_held_through_final_verify",
        "retained_artifact_count", "source_identity_fingerprint",
        "artifact_hash", "target_identity_fingerprint", "receipt_fingerprint",
    ),
    "ConfigPublicationReceiptV1": (
        "status", "pending_state", "setting_count", "provider_disabled",
        "loader_verified", "retained_artifact_count", "selection_fingerprint",
        "document_fingerprint", "target_identity_fingerprint",
        "receipt_fingerprint",
    ),
}

_SUCCESS_STATUSES = (
    "EVIDENCE_PUBLISHED",
    "MAIN_PUBLISHED",
    "REPOSITORY_TOPOLOGY_PUBLISHED",
    "RUNTIME_PUBLISHED",
    "DATABASE_PUBLISHED",
    "CRX_PUBLISHED",
    "CONFIG_PUBLISHED",
)

_RECEIPT_DOMAINS = {
    "PostMoveMainAclConformanceReceiptV1": "post-move-main-acl-conformance-v1",
    "RepositoryTopologyReceiptV1": "repository-topology-receipt-v1",
    "RuntimePublicationReceiptV1": "runtime-publication-receipt-v1",
    "CrxPublicationReceiptV1": "crx-publication-receipt-v1",
    "ConfigPublicationReceiptV1": "config-publication-receipt-v1",
}


@dataclass(frozen=True, slots=True)
class VerifiedPublicationReceiptV1:
    index: int
    publication_type: str
    receipt_fields: tuple[tuple[str, object], ...]
    material_fingerprint: str

    def mapping(self) -> dict[str, object]:
        return dict(self.receipt_fields)


@dataclass(frozen=True, slots=True)
class VerifiedPublicationChainV1:
    receipts: tuple[VerifiedPublicationReceiptV1, ...]
    terminal_head_fingerprint: str


def canonical_publication_receipt(value, index):
    if type(index) is not int or not 0 <= index < len(_PUBLICATION_TYPES):
        raise ValueError("R2_PUBLICATION_RECEIPT_INDEX_INVALID")
    expected_type = _PUBLICATION_TYPES[index]
    if type(value) is not expected_type:
        raise ValueError("R2_PUBLICATION_RECEIPT_TYPE_INVALID")
    names = tuple(item.name for item in fields(value))
    type_name = expected_type.__name__
    if names != _FIELD_SCHEMAS[type_name]:
        raise ValueError("R2_PUBLICATION_RECEIPT_SCHEMA_INVALID")
    mapping = {name: _primitive(getattr(value, name)) for name in names}
    return _verified(index, type_name, mapping)


def read_verified_publications(records):
    return read_verified_publication_chain(records).receipts


def read_verified_publication_chain(records):
    if type(records) is not tuple or len(records) != len(_PUBLICATION_TYPES):
        raise RuntimeError("R2_DURABLE_PUBLICATION_COUNT_INVALID")
    verified = []
    predecessor = INITIAL_RECEIPT_FINGERPRINT
    prior_head = INITIAL_JOURNAL_HEAD_FINGERPRINT
    expected_record_fields = {
        "record_type", "receipt", "predecessor", "prior_head", "head",
        "material", "publication_type", "publication_schema_version",
        "receipt_fields",
    }
    for index, record in enumerate(records):
        if type(record) is not dict or set(record) != expected_record_fields:
            raise RuntimeError("R2_DURABLE_PUBLICATION_RECORD_INVALID")
        if record["record_type"] != "PUBLICATION_RECEIPT":
            raise RuntimeError("R2_DURABLE_PUBLICATION_RECORD_INVALID")
        if record["publication_schema_version"] != 1:
            raise RuntimeError("R2_DURABLE_PUBLICATION_SCHEMA_INVALID")
        view = _verified(index, record["publication_type"], record["receipt_fields"])
        if record["material"] != view.material_fingerprint:
            raise RuntimeError("R2_DURABLE_PUBLICATION_MATERIAL_INVALID")
        link = ReceiptPredecessorLinkV1.create(
            record_type="PUBLICATION_RECEIPT",
            material_fingerprint=view.material_fingerprint,
            predecessor_fingerprint=predecessor,
            prior_head_fingerprint=prior_head,
        )
        if (
            record["receipt"], record["predecessor"],
            record["prior_head"], record["head"],
        ) != (
            link.receipt_fingerprint, link.predecessor_fingerprint,
            link.prior_head_fingerprint, link.journal_head_fingerprint,
        ):
            raise RuntimeError("R2_DURABLE_PUBLICATION_LINK_INVALID")
        verified.append(view)
        predecessor = link.receipt_fingerprint
        prior_head = link.journal_head_fingerprint
    return VerifiedPublicationChainV1(tuple(verified), prior_head)


def _verified(index, type_name, mapping):
    if (
        type(type_name) is not str
        or type(mapping) is not dict
        or type_name != _PUBLICATION_TYPES[index].__name__
        or set(mapping) != set(_FIELD_SCHEMAS[type_name])
    ):
        raise RuntimeError("R2_DURABLE_PUBLICATION_SCHEMA_INVALID")
    ordered = {name: mapping[name] for name in _FIELD_SCHEMAS[type_name]}
    _validate_values(index, type_name, ordered)
    material = fingerprint(
        "r2-executed-publication-output-v2", [index, type_name, ordered]
    )
    return VerifiedPublicationReceiptV1(
        index=index,
        publication_type=type_name,
        receipt_fields=tuple(ordered.items()),
        material_fingerprint=material,
    )


def _validate_values(index, type_name, mapping):
    if any(type(value) not in {str, int, bool} for value in mapping.values()):
        raise RuntimeError("R2_DURABLE_PUBLICATION_VALUE_INVALID")
    if mapping["status"] != _SUCCESS_STATUSES[index]:
        raise RuntimeError("R2_DURABLE_PUBLICATION_STATUS_INVALID")
    for name, value in mapping.items():
        if name.endswith("_fingerprint") and not is_fingerprint(value):
            raise RuntimeError("R2_DURABLE_PUBLICATION_FINGERPRINT_INVALID")
    if "schema_version" in mapping and mapping["schema_version"] != 1:
        raise RuntimeError("R2_DURABLE_PUBLICATION_SCHEMA_INVALID")
    _validate_receipt_fingerprint(type_name, mapping)


def _validate_receipt_fingerprint(type_name, mapping):
    if type_name == "EvidenceProcessResult":
        if (mapping["accepted"], mapping["rejected"], mapping["published"]) != (1, 0, 1):
            raise RuntimeError("R2_DURABLE_PUBLICATION_EVIDENCE_INVALID")
        return
    body = dict(mapping)
    observed = body.pop("receipt_fingerprint")
    if type_name == "DatabaseTransactionResultV1":
        expected = fingerprint(
            "database-transaction-result-v1",
            [
                body["status"], body["journal_head_fingerprint"],
                body["lease_read_passes"], body["retained_artifact_count"],
            ],
        )
    else:
        expected = fingerprint(_RECEIPT_DOMAINS[type_name], body)
    if observed != expected:
        raise RuntimeError("R2_DURABLE_PUBLICATION_RECEIPT_INVALID")


def _primitive(value):
    if isinstance(value, Enum):
        return value.value
    if type(value) in {str, int, bool}:
        return value
    raise ValueError("R2_PUBLICATION_RECEIPT_VALUE_INVALID")
