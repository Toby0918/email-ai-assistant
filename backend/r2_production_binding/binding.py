"""Immutable sole-maintainer production binding for one frozen master."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._binding_body import build_binding_body
from ._canonical import (
    canonical_json,
    fingerprint,
    fingerprint_entries,
    is_fingerprint,
    parse_fingerprint_entries,
    strict_json_object,
)
from .errors import ProductionBindingError
from .vocabulary import (
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
)


_SCALAR_FIELDS = (
    "binding_type", "final_master_binding_fingerprint", "final_commit_oid",
    "final_tree_oid", "closure_map_fingerprint", "source_package_fingerprint",
    "runbook_fingerprint", "workflow_fingerprint", "operation_fingerprint",
    "operator_role_registry_fingerprint", "command_domain_registry_fingerprint",
    "production_role_registry_fingerprint", "execution_confirmation_policy",
    "execution_confirmation_policy_fingerprint", "operator_role_count",
    "command_count", "command_domain_count", "production_role_count",
    "max_execution_confirmation_validity_seconds", "assurance_model",
    "operator_count", "independent_reviewer_count", "external_signer_count",
    "issue39_authority_count",
)
_BODY_FIELDS = (
    *_SCALAR_FIELDS,
    "operator_role_fingerprints",
    "command_domains",
    "production_role_fingerprints",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ApprovedCutoverBindingV3:
    binding_type: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    closure_map_fingerprint: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    operator_role_registry_fingerprint: str = field(repr=False)
    command_domain_registry_fingerprint: str = field(repr=False)
    production_role_registry_fingerprint: str = field(repr=False)
    execution_confirmation_policy: str
    execution_confirmation_policy_fingerprint: str = field(repr=False)
    operator_role_count: int
    command_count: int
    command_domain_count: int
    production_role_count: int
    max_execution_confirmation_validity_seconds: int
    operator_role_fingerprints: tuple = field(repr=False)
    command_domains: tuple = field(repr=False)
    production_role_fingerprints: tuple = field(repr=False)
    assurance_model: str
    operator_count: int
    independent_reviewer_count: int
    external_signer_count: int
    issue39_authority_count: int
    binding_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ApprovedCutoverBindingV3 requires create()")

    @classmethod
    def create(
        cls,
        *,
        final_master_binding: object,
        operation_fingerprint: object,
        operator_role_fingerprints: object,
        production_role_fingerprints: object,
    ) -> ApprovedCutoverBindingV3:
        body = build_binding_body(
            final_master_binding,
            operation_fingerprint,
            operator_role_fingerprints,
            production_role_fingerprints,
        )
        return _construct(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        final_master_binding: object,
    ) -> ApprovedCutoverBindingV3:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise ProductionBindingError()
            if set(source) != {*_BODY_FIELDS, "binding_fingerprint"}:
                raise ProductionBindingError()
            body = _rebuild_body(source, final_master_binding)
            if any(source[name] != body[name] for name in _BODY_FIELDS):
                raise ProductionBindingError()
            if source["binding_fingerprint"] != _binding_fingerprint(body):
                raise ProductionBindingError()
            return _construct(body)
        except ProductionBindingError:
            raise
        except Exception:
            raise ProductionBindingError() from None

    def to_mapping(self) -> dict[str, object]:
        body = {name: getattr(self, name) for name in _SCALAR_FIELDS}
        body["operator_role_fingerprints"] = fingerprint_entries(
            self.operator_role_fingerprints
        )
        body["command_domains"] = [
            {"command": command.value, "domain": domain.value}
            for command, domain in self.command_domains
        ]
        body["production_role_fingerprints"] = fingerprint_entries(
            self.production_role_fingerprints
        )
        return {**body, "binding_fingerprint": self.binding_fingerprint}

    def to_canonical_json(self) -> bytes:
        return canonical_json(self.to_mapping())


def production_action_fingerprint_v2(
    binding: object,
    command: object,
    *,
    subject_fingerprint: object = None,
) -> str:
    if (
        type(binding) is not ApprovedCutoverBindingV3
        or type(command) is not ProductionCommandV2
        or not (subject_fingerprint is None or is_fingerprint(subject_fingerprint))
    ):
        raise ProductionBindingError()
    body = {
        "binding_fingerprint": binding.binding_fingerprint,
        "command": command.value,
        "domain": dict(binding.command_domains)[command].value,
        "operation_fingerprint": binding.operation_fingerprint,
    }
    if subject_fingerprint is not None:
        body["subject_fingerprint"] = subject_fingerprint
    return fingerprint("r2-production-action-v3", body)


def _rebuild_body(source, final_master):
    return build_binding_body(
        final_master,
        source["operation_fingerprint"],
        parse_fingerprint_entries(
            source["operator_role_fingerprints"], OperatorRoleV2
        ),
        parse_fingerprint_entries(
            source["production_role_fingerprints"], ProductionRoleV2
        ),
    )


def _construct(body):
    value = object.__new__(ApprovedCutoverBindingV3)
    for name in _SCALAR_FIELDS:
        object.__setattr__(value, name, body[name])
    object.__setattr__(value, "operator_role_fingerprints", _operator_pairs(body))
    object.__setattr__(value, "command_domains", _command_pairs(body))
    object.__setattr__(value, "production_role_fingerprints", _role_pairs(body))
    object.__setattr__(value, "binding_fingerprint", _binding_fingerprint(body))
    return value


def _operator_pairs(body):
    return tuple(
        (OperatorRoleV2(item["role"]), item["fingerprint"])
        for item in body["operator_role_fingerprints"]
    )


def _command_pairs(body):
    return tuple(
        (ProductionCommandV2(item["command"]), AuthorityDomainV2(item["domain"]))
        for item in body["command_domains"]
    )


def _role_pairs(body):
    return tuple(
        (ProductionRoleV2(item["role"]), item["fingerprint"])
        for item in body["production_role_fingerprints"]
    )


def _binding_fingerprint(body):
    return fingerprint("r2-approved-cutover-binding-v3", body)
