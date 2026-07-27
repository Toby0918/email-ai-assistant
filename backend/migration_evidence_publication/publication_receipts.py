"""Closed content-free create and verify receipts for Issue #54."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from weakref import WeakKeyDictionary

from .canonical import canonical_json, fingerprint


_RECEIPT_ERROR = "MIGRATION_EVIDENCE_PUBLICATION_RECEIPT_INVALID"


@dataclass(frozen=True, slots=True)
class MigrationEvidencePackageCountsV1:
    files: int
    refs: int
    worktrees: int


@dataclass(frozen=True, slots=True, repr=False)
class _PublicationBinding:
    receipt_type: str
    status: str
    receipt_fingerprint: str
    prior_receipt_fingerprint: str
    operation_fingerprint: str
    profile_fingerprint: str
    master_fingerprint: str
    review_fingerprint: str
    selection_fingerprint: str
    git_fingerprint: str
    host_fingerprint: str
    review_counts_fingerprint: str
    package_sha256: str
    manifest_sha256: str
    package_identity_fingerprint: str
    package_counts_fingerprint: str
    package_counts: MigrationEvidencePackageCountsV1
    authorization_fingerprint: str
    process_fingerprint: str | None


_RECEIPT_STATES: WeakKeyDictionary[object, _PublicationBinding] = (
    WeakKeyDictionary()
)
_RECEIPT_STATES_LOCK = Lock()


class _ClosedPublicationReceipt:
    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated publication receipt construction required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError(_RECEIPT_ERROR)

    def __delattr__(self, _name: str) -> None:
        raise ValueError(_RECEIPT_ERROR)

    def __copy__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __deepcopy__(self, _memo: object) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __reduce__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError(_RECEIPT_ERROR)

    def __getstate__(self) -> object:
        raise ValueError(_RECEIPT_ERROR)

    @property
    def receipt_fingerprint(self) -> str:
        return _publication_binding(self).receipt_fingerprint

    @property
    def review_fingerprint(self) -> str:
        return _publication_binding(self).review_fingerprint

    @property
    def review_counts_fingerprint(self) -> str:
        return _publication_binding(self).review_counts_fingerprint

    @property
    def package_sha256(self) -> str:
        return _publication_binding(self).package_sha256

    @property
    def manifest_sha256(self) -> str:
        return _publication_binding(self).manifest_sha256

    @property
    def package_identity_fingerprint(self) -> str:
        return _publication_binding(
            self
        ).package_identity_fingerprint

    @property
    def package_counts_fingerprint(self) -> str:
        return _publication_binding(self).package_counts_fingerprint

    @property
    def package_counts(self) -> MigrationEvidencePackageCountsV1:
        return _publication_binding(self).package_counts

    def to_mapping(self) -> dict[str, object]:
        return _mapping(_publication_binding(self))

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


class MigrationEvidenceCreatedReceiptV1(_ClosedPublicationReceipt):
    """Opaque receipt for one create-only publication."""

    __slots__ = ()


class MigrationEvidenceVerifiedReceiptV1(_ClosedPublicationReceipt):
    """Opaque receipt for one separate-process verification."""

    __slots__ = ()


def _mint_created_receipt(
    *,
    common: dict[str, str],
    review_receipt_fingerprint: str,
    package_counts: MigrationEvidencePackageCountsV1,
    authorization_fingerprint: str,
) -> MigrationEvidenceCreatedReceiptV1:
    return _mint_receipt(
        receipt_class=MigrationEvidenceCreatedReceiptV1,
        receipt_type="MigrationEvidenceCreatedReceiptV1",
        status="MIGRATION_EVIDENCE_CREATED",
        common=common,
        prior_receipt_fingerprint=review_receipt_fingerprint,
        package_counts=package_counts,
        authorization_fingerprint=authorization_fingerprint,
        process_fingerprint=None,
    )


def _mint_verified_receipt(
    *,
    created: _PublicationBinding,
    authorization_fingerprint: str,
    process_fingerprint: str,
) -> MigrationEvidenceVerifiedReceiptV1:
    common = _common_mapping(created)
    return _mint_receipt(
        receipt_class=MigrationEvidenceVerifiedReceiptV1,
        receipt_type="MigrationEvidenceVerifiedReceiptV1",
        status="MIGRATION_EVIDENCE_VERIFIED",
        common=common,
        prior_receipt_fingerprint=created.receipt_fingerprint,
        package_counts=created.package_counts,
        authorization_fingerprint=authorization_fingerprint,
        process_fingerprint=process_fingerprint,
    )


def _mint_receipt(
    *,
    receipt_class: type[_ClosedPublicationReceipt],
    receipt_type: str,
    status: str,
    common: dict[str, str],
    prior_receipt_fingerprint: str,
    package_counts: MigrationEvidencePackageCountsV1,
    authorization_fingerprint: str,
    process_fingerprint: str | None,
) -> _ClosedPublicationReceipt:
    provisional = _build_binding(
        receipt_type=receipt_type,
        status=status,
        receipt_fingerprint="",
        prior_receipt_fingerprint=prior_receipt_fingerprint,
        common=common,
        package_counts=package_counts,
        authorization_fingerprint=authorization_fingerprint,
        process_fingerprint=process_fingerprint,
    )
    receipt_fingerprint = fingerprint(
        "migration-evidence-publication-receipt-v1",
        _mapping(provisional, include_receipt=False),
    )
    state = _build_binding(
        receipt_type=receipt_type,
        status=status,
        receipt_fingerprint=receipt_fingerprint,
        prior_receipt_fingerprint=prior_receipt_fingerprint,
        common=common,
        package_counts=package_counts,
        authorization_fingerprint=authorization_fingerprint,
        process_fingerprint=process_fingerprint,
    )
    receipt = object.__new__(receipt_class)
    with _RECEIPT_STATES_LOCK:
        _RECEIPT_STATES[receipt] = state
    return receipt


def _build_binding(
    *,
    receipt_type: str,
    status: str,
    receipt_fingerprint: str,
    prior_receipt_fingerprint: str,
    common: dict[str, str],
    package_counts: MigrationEvidencePackageCountsV1,
    authorization_fingerprint: str,
    process_fingerprint: str | None,
) -> _PublicationBinding:
    return _PublicationBinding(
        receipt_type=receipt_type,
        status=status,
        receipt_fingerprint=receipt_fingerprint,
        prior_receipt_fingerprint=prior_receipt_fingerprint,
        package_counts=package_counts,
        authorization_fingerprint=authorization_fingerprint,
        process_fingerprint=process_fingerprint,
        **common,
    )


def _publication_binding(receipt: object) -> _PublicationBinding:
    if type(receipt) not in (
        MigrationEvidenceCreatedReceiptV1,
        MigrationEvidenceVerifiedReceiptV1,
    ):
        raise ValueError(_RECEIPT_ERROR)
    with _RECEIPT_STATES_LOCK:
        state = _RECEIPT_STATES.get(receipt)
    if state is None:
        raise ValueError(_RECEIPT_ERROR)
    return state


def _common_mapping(state: _PublicationBinding) -> dict[str, str]:
    names = (
        "operation_fingerprint",
        "profile_fingerprint",
        "master_fingerprint",
        "review_fingerprint",
        "selection_fingerprint",
        "git_fingerprint",
        "host_fingerprint",
        "review_counts_fingerprint",
        "package_sha256",
        "manifest_sha256",
        "package_identity_fingerprint",
        "package_counts_fingerprint",
    )
    return {name: getattr(state, name) for name in names}


def _mapping(
    state: _PublicationBinding,
    *,
    include_receipt: bool = True,
) -> dict[str, object]:
    value: dict[str, object] = {
        "receipt_type": state.receipt_type,
        "status": state.status,
        "prior_receipt_fingerprint": state.prior_receipt_fingerprint,
        **_common_mapping(state),
        "package_counts": {
            "files": state.package_counts.files,
            "refs": state.package_counts.refs,
            "worktrees": state.package_counts.worktrees,
        },
        "authorization_fingerprint": state.authorization_fingerprint,
    }
    if state.process_fingerprint is not None:
        value["process_fingerprint"] = state.process_fingerprint
    if include_receipt:
        value["receipt_fingerprint"] = state.receipt_fingerprint
    return value
