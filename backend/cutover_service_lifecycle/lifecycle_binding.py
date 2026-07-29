"""Closed construction validation for the Issue #58 lifecycle."""

from __future__ import annotations

from backend.cutover_managed_activation import ManagedActivationReceiptSetV1

from .canonical import is_fingerprint
from .controller import ProviderDisabledServiceController
from .rollback_adapters import has_exact_rollback_adapter
from .rollback_contracts import CommittedRollbackPlanV1


EXPECTED_FIELDS = {
    "operation_fingerprint",
    "profile_fingerprint",
    "governing_master_commit",
    "publication_authorization_fingerprint",
    "journal_head_fingerprint",
    "publications",
    "controller",
    "rollback_adapter",
    "rollback_plan",
}


def valid_lifecycle_bindings(values: dict[str, object]) -> bool:
    try:
        return _valid_rebuilt_bindings(values)
    except Exception:
        return False


def _valid_rebuilt_bindings(values: dict[str, object]) -> bool:
    if not _valid_types(values):
        return False
    publications = values["publications"]
    controller = values["controller"]
    rebuilt_publications = ManagedActivationReceiptSetV1.from_mapping(
        publications.to_mapping()
    )
    rebuilt_plan = _rebuilt_plan(values["rollback_plan"])
    return (
        rebuilt_publications == publications
        and rebuilt_plan == values["rollback_plan"]
        and publications.profile_fingerprint
        == values["profile_fingerprint"]
        and publications.operation_fingerprint
        == values["operation_fingerprint"]
        and publications.governing_master_commit
        == values["governing_master_commit"]
        and publications.authorization_fingerprint
        == values["publication_authorization_fingerprint"]
        and controller.matches_binding(
            operation_fingerprint=values["operation_fingerprint"],
            profile_fingerprint=values["profile_fingerprint"],
            governing_master_commit=values["governing_master_commit"],
            publication_authorization_fingerprint=values[
                "publication_authorization_fingerprint"
            ],
        )
    )


def _rebuilt_plan(plan: CommittedRollbackPlanV1):
    names = (
        "journal_head_fingerprint",
        "committed_records_fingerprint",
        "original_topology_fingerprint",
        "parent_descriptor_fingerprint",
        "finance_descriptor_fingerprint",
        "original_database_fingerprint",
        "sidecar_state_fingerprint",
        "legacy_runtime_fingerprint",
        "repository_identity_fingerprint",
    )
    return CommittedRollbackPlanV1.create(
        **{name: getattr(plan, name) for name in names}
    )


def _valid_types(values: dict[str, object]) -> bool:
    return (
        set(values) == EXPECTED_FIELDS
        and is_fingerprint(values["operation_fingerprint"])
        and is_fingerprint(values["profile_fingerprint"])
        and type(values["governing_master_commit"]) is str
        and len(values["governing_master_commit"]) == 40
        and is_fingerprint(values["publication_authorization_fingerprint"])
        and is_fingerprint(values["journal_head_fingerprint"])
        and type(values["publications"]) is ManagedActivationReceiptSetV1
        and type(values["controller"])
        is ProviderDisabledServiceController
        and has_exact_rollback_adapter(values["rollback_adapter"])
        and type(values["rollback_plan"]) is CommittedRollbackPlanV1
        and values["rollback_plan"].journal_head_fingerprint
        == values["journal_head_fingerprint"]
    )
