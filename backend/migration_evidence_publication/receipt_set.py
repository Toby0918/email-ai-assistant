"""Exact review-created-verified receipt consistency set."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from weakref import WeakKeyDictionary

from .canonical import canonical_json, fingerprint
from .errors import MigrationEvidencePublicationError
from .publication_receipts import (
    MigrationEvidenceCreatedReceiptV1,
    MigrationEvidencePackageCountsV1,
    MigrationEvidenceVerifiedReceiptV1,
    _PublicationBinding,
    _publication_binding,
)
from .receipts import (
    MigrationEvidenceReviewReceiptV1,
    _ReviewReceiptBinding,
    _receipt_binding,
)


_ERROR = "MIGRATION_EVIDENCE_RECEIPT_CHAIN_REJECTED"


@dataclass(frozen=True, slots=True, repr=False)
class _ChainBinding:
    chain_fingerprint: str
    review_receipt_fingerprint: str
    created_receipt_fingerprint: str
    verified_receipt_fingerprint: str
    operation_fingerprint: str
    profile_fingerprint: str
    master_fingerprint: str
    review_fingerprint: str
    package_sha256: str
    manifest_sha256: str
    package_identity_fingerprint: str
    package_counts_fingerprint: str
    package_counts: MigrationEvidencePackageCountsV1


_CHAIN_STATES: WeakKeyDictionary[object, _ChainBinding] = (
    WeakKeyDictionary()
)
_CHAIN_STATES_LOCK = Lock()


class MigrationEvidenceReceiptSetV1:
    """Content-free proof that all three nominal receipts agree."""

    __slots__ = ("__weakref__",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated receipt chain construction required")

    def __setattr__(self, _name: str, _value: object) -> None:
        raise ValueError(_ERROR)

    def __delattr__(self, _name: str) -> None:
        raise ValueError(_ERROR)

    def __copy__(self) -> object:
        raise ValueError(_ERROR)

    def __deepcopy__(self, _memo: object) -> object:
        raise ValueError(_ERROR)

    def __reduce__(self) -> object:
        raise ValueError(_ERROR)

    def __reduce_ex__(self, _protocol: int) -> object:
        raise ValueError(_ERROR)

    def __getstate__(self) -> object:
        raise ValueError(_ERROR)

    @property
    def receipt_set_fingerprint(self) -> str:
        return _chain_binding(self).chain_fingerprint

    def to_mapping(self) -> dict[str, object]:
        return _chain_mapping(_chain_binding(self))

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def require_matching_migration_evidence_receipts(
    *,
    review_receipt: MigrationEvidenceReviewReceiptV1,
    created_receipt: MigrationEvidenceCreatedReceiptV1,
    verified_receipt: MigrationEvidenceVerifiedReceiptV1,
) -> MigrationEvidenceReceiptSetV1:
    """Mint a chain only when all opaque bindings match exactly."""

    try:
        review = _receipt_binding(review_receipt)
        created = _publication_binding(created_receipt)
        verified = _publication_binding(verified_receipt)
        _require_match(review, created, verified)
        return _mint_chain(review, created, verified)
    except Exception:
        raise MigrationEvidencePublicationError(_ERROR) from None


def _require_match(
    review: _ReviewReceiptBinding,
    created: _PublicationBinding,
    verified: _PublicationBinding,
) -> None:
    review_common = (
        review.operation_fingerprint,
        review.profile_fingerprint,
        review.master_fingerprint,
        review.review_fingerprint,
        review.selection_fingerprint,
        review.git_fingerprint,
        review.host_fingerprint,
        review.counts_fingerprint,
    )
    created_common = _review_common(created)
    verified_common = _review_common(verified)
    created_package = _package_common(created)
    verified_package = _package_common(verified)
    if (
        created.receipt_type != "MigrationEvidenceCreatedReceiptV1"
        or verified.receipt_type
        != "MigrationEvidenceVerifiedReceiptV1"
        or created.prior_receipt_fingerprint
        != review.receipt_fingerprint
        or verified.prior_receipt_fingerprint
        != created.receipt_fingerprint
        or review_common != created_common
        or created_common != verified_common
        or created_package != verified_package
        or created.package_counts != verified.package_counts
    ):
        raise ValueError(_ERROR)


def _review_common(state: _PublicationBinding) -> tuple[str, ...]:
    return (
        state.operation_fingerprint,
        state.profile_fingerprint,
        state.master_fingerprint,
        state.review_fingerprint,
        state.selection_fingerprint,
        state.git_fingerprint,
        state.host_fingerprint,
        state.review_counts_fingerprint,
    )


def _package_common(state: _PublicationBinding) -> tuple[str, ...]:
    return (
        state.package_sha256,
        state.manifest_sha256,
        state.package_identity_fingerprint,
        state.package_counts_fingerprint,
    )


def _mint_chain(
    review: _ReviewReceiptBinding,
    created: _PublicationBinding,
    verified: _PublicationBinding,
) -> MigrationEvidenceReceiptSetV1:
    state = _ChainBinding(
        chain_fingerprint="",
        review_receipt_fingerprint=review.receipt_fingerprint,
        created_receipt_fingerprint=created.receipt_fingerprint,
        verified_receipt_fingerprint=verified.receipt_fingerprint,
        operation_fingerprint=review.operation_fingerprint,
        profile_fingerprint=review.profile_fingerprint,
        master_fingerprint=review.master_fingerprint,
        review_fingerprint=review.review_fingerprint,
        package_sha256=created.package_sha256,
        manifest_sha256=created.manifest_sha256,
        package_identity_fingerprint=(
            created.package_identity_fingerprint
        ),
        package_counts_fingerprint=created.package_counts_fingerprint,
        package_counts=created.package_counts,
    )
    bound = _ChainBinding(
        **{
            **_chain_fields(state),
            "chain_fingerprint": fingerprint(
                "migration-evidence-receipt-chain-v1",
                _chain_mapping(state, include_chain=False),
            ),
        }
    )
    chain = object.__new__(MigrationEvidenceReceiptSetV1)
    with _CHAIN_STATES_LOCK:
        _CHAIN_STATES[chain] = bound
    return chain


def _chain_fields(state: _ChainBinding) -> dict[str, object]:
    return {
        name: getattr(state, name)
        for name in state.__dataclass_fields__
        if name != "chain_fingerprint"
    }


def _chain_binding(chain: object) -> _ChainBinding:
    if type(chain) is not MigrationEvidenceReceiptSetV1:
        raise ValueError(_ERROR)
    with _CHAIN_STATES_LOCK:
        state = _CHAIN_STATES.get(chain)
    if state is None:
        raise ValueError(_ERROR)
    return state


def _chain_mapping(
    state: _ChainBinding,
    *,
    include_chain: bool = True,
) -> dict[str, object]:
    value = {
        "receipt_type": "MigrationEvidenceReceiptSetV1",
        "status": "MIGRATION_EVIDENCE_RECEIPTS_MATCH",
        **{
            key: item
            for key, item in _chain_fields(state).items()
            if key != "package_counts"
        },
        "package_counts": {
            "files": state.package_counts.files,
            "refs": state.package_counts.refs,
            "worktrees": state.package_counts.worktrees,
        },
    }
    if include_chain:
        value["chain_fingerprint"] = state.chain_fingerprint
    return value
