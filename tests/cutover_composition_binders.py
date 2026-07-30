"""Test-only assembly for Issue #59 executable composition objects."""

from __future__ import annotations

import tempfile
import threading
from dataclasses import fields, replace
from pathlib import Path

from backend.cutover_composition_contracts import (
    AuthorizationSequenceV1,
    CompositionBindingV1,
    CompositionContractError,
    ProjectContainerReceiptChainV1,
)
from backend.cutover_transaction_composition import (
    CutoverTransactionComposition,
    CutoverTransactionRolesV1,
    JournalOwnerV1,
)
from backend.cutover_transaction_composition.roles import (
    has_exact_roles as has_exact_transaction_roles,
)
from backend.cutover_transaction_composition.state import SingleActionState
from backend.migration_evidence_publication_composition import (
    MigrationEvidencePublicationComposition,
    MigrationEvidencePublicationRolesV1,
)
from backend.real_host_preflight_composition import (
    RealHostPreflightComposition,
    RealHostPreflightRolesV1,
)
from backend.real_host_preflight_composition.roles import (
    has_exact_roles as has_exact_preflight_roles,
)


_MARKER = ".issue59-composition-test-sandbox"
_MARKER_BYTES = b"ISSUE59_COMPOSITION_TEST_SANDBOX_V1\n"
_ERROR = "TEST_COMPOSITION_SCOPE_INVALID"


class TestOwnedCompositionScopeV1:
    """One internally created temporary scope for test-only assembly."""

    __slots__ = (
        "_owner",
        "_root",
        "_owned_directories",
        "_lock",
        "_closed",
    )
    __test__ = False

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("test composition scope requires internal creation")

    @classmethod
    def create(cls) -> TestOwnedCompositionScopeV1:
        owner = tempfile.TemporaryDirectory(
            prefix="issue59-composition-scope-"
        )
        root = Path(owner.name).resolve()
        (root / _MARKER).write_bytes(_MARKER_BYTES)
        value = object.__new__(cls)
        value._owner = owner
        value._root = root
        value._owned_directories = []
        value._lock = threading.RLock()
        value._closed = False
        return value

    def require_active(self) -> None:
        with self._lock:
            self._require_active_locked()

    def _require_active_locked(self) -> None:
        try:
            marker = self._root / _MARKER
            if (
                self._closed
                or type(self._owner) is not tempfile.TemporaryDirectory
                or Path(self._owner.name).resolve() != self._root
                or not self._root.is_dir()
                or marker.read_bytes() != _MARKER_BYTES
            ):
                raise ValueError
        except Exception:
            raise CompositionContractError(_ERROR) from None

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            owned = tuple(reversed(self._owned_directories))
            self._owned_directories.clear()
        failed = False
        for owner in (*owned, self._owner):
            try:
                owner.cleanup()
            except Exception:
                failed = True
        if failed:
            raise CompositionContractError(_ERROR) from None

    def own_temporary_directory(self, owner: object) -> None:
        with self._lock:
            self._require_active_locked()
            if type(owner) is not tempfile.TemporaryDirectory:
                raise CompositionContractError(_ERROR)
            try:
                root = Path(owner.name).resolve(strict=True)
            except Exception:
                raise CompositionContractError(_ERROR) from None
            if (
                not root.is_dir()
                or root.is_symlink()
                or owner is self._owner
                or owner in self._owned_directories
            ):
                raise CompositionContractError(_ERROR)
            self._owned_directories.append(owner)

    def call_while_active(self, callback, *args, **kwargs):
        with self._lock:
            self._require_active_locked()
            return callback(*args, **kwargs)


def bind_test_preflight(
    *,
    scope: TestOwnedCompositionScopeV1,
    binding: CompositionBindingV1,
    authorization_sequence: AuthorizationSequenceV1,
    roles: RealHostPreflightRolesV1,
    observed_at_epoch: int,
) -> RealHostPreflightComposition:
    error = "REAL_HOST_PREFLIGHT_COMPOSITION_REJECTED"
    _require_common(
        scope, binding, authorization_sequence, observed_at_epoch, error
    )
    if (
        not has_exact_preflight_roles(roles)
        or roles.binding_fingerprint != binding.binding_fingerprint
    ):
        _fail(error)
    roles = _guard_roles(scope, roles)
    value = object.__new__(RealHostPreflightComposition)
    value._binding = binding
    value._roles = roles
    value._observed_at = observed_at_epoch
    value._receipts = ()
    value._recovery_inspected = False
    return value


def bind_test_publication(
    *,
    scope: TestOwnedCompositionScopeV1,
    binding: CompositionBindingV1,
    authorization_sequence: AuthorizationSequenceV1,
    roles: MigrationEvidencePublicationRolesV1,
    confirmed_review_fingerprint: str,
    observed_at_epoch: int,
) -> MigrationEvidencePublicationComposition:
    error = "MIGRATION_EVIDENCE_PUBLICATION_COMPOSITION_REJECTED"
    _require_common(
        scope, binding, authorization_sequence, observed_at_epoch, error
    )
    if (
        type(roles) is not MigrationEvidencePublicationRolesV1
        or roles.binding_fingerprint != binding.binding_fingerprint
        or not callable(roles.publish_confirmed_review)
        or not _is_fingerprint(confirmed_review_fingerprint)
    ):
        _fail(error)
    roles = _guard_roles(scope, roles)
    value = object.__new__(MigrationEvidencePublicationComposition)
    value._binding = binding
    value._roles = roles
    value._confirmed = confirmed_review_fingerprint
    value._published = False
    return value


def bind_test_transaction(
    *,
    scope: TestOwnedCompositionScopeV1,
    binding: CompositionBindingV1,
    authorization_sequence: AuthorizationSequenceV1,
    roles: CutoverTransactionRolesV1,
    journal_owner: JournalOwnerV1,
    initial_chain: ProjectContainerReceiptChainV1,
    observed_at_epoch: int,
) -> CutoverTransactionComposition:
    error = "CUTOVER_TRANSACTION_COMPOSITION_REJECTED"
    _require_common(
        scope, binding, authorization_sequence, observed_at_epoch, error
    )
    if (
        not has_exact_transaction_roles(roles)
        or roles.binding_fingerprint != binding.binding_fingerprint
        or type(journal_owner) is not JournalOwnerV1
        or not _is_fingerprint(journal_owner.owner_fingerprint)
        or not callable(journal_owner.verify_head)
        or not callable(journal_owner.claim_gate)
        or not callable(journal_owner.now_epoch)
        or type(initial_chain) is not ProjectContainerReceiptChainV1
        or _chain_binding(initial_chain) != _binding_tuple(binding)
    ):
        _fail(error)
    roles = _guard_roles(scope, roles)
    journal_owner = JournalOwnerV1(
        owner_fingerprint=journal_owner.owner_fingerprint,
        verify_head=_guard_callable(scope, journal_owner.verify_head),
        claim_gate=_guard_callable(scope, journal_owner.claim_gate),
        now_epoch=_guard_callable(scope, journal_owner.now_epoch),
    )
    value = object.__new__(CutoverTransactionComposition)
    value._binding = binding
    value._roles = roles
    value._journal_owner = journal_owner
    value._initial = initial_chain
    value._observed_at = observed_at_epoch
    value._state = SingleActionState()
    return value


def _require_common(scope, binding, sequence, observed, error) -> None:
    if type(scope) is not TestOwnedCompositionScopeV1:
        _fail(error)
    scope.require_active()
    if (
        type(binding) is not CompositionBindingV1
        or type(sequence) is not AuthorizationSequenceV1
        or sequence._sandbox_authorized is not True
        or binding.authorization_sequence_fingerprint
        != sequence.sequence_fingerprint
        or type(observed) is not int
        or not 0 <= observed < sequence.expires_at_epoch
    ):
        _fail(error)


def _guard_roles(scope, roles):
    guarded = {
        item.name: _guard_callable(scope, getattr(roles, item.name))
        for item in fields(roles)
        if item.name != "binding_fingerprint"
    }
    return replace(roles, **guarded)


def _guard_callable(scope, callback):
    def call(*args, **kwargs):
        return scope.call_while_active(callback, *args, **kwargs)

    return call


def _binding_tuple(binding):
    return (
        binding.operation_fingerprint,
        binding.profile_fingerprint,
        binding.governing_master_fingerprint,
        binding.operator_fingerprint,
        binding.authorization_sequence_fingerprint,
    )


def _chain_binding(chain):
    return (
        chain.operation_fingerprint,
        chain.profile_fingerprint,
        chain.governing_master_fingerprint,
        chain.operator_fingerprint,
        chain.authorization_sequence_fingerprint,
    )


def _is_fingerprint(value) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _fail(error: str = _ERROR) -> None:
    raise CompositionContractError(error)
