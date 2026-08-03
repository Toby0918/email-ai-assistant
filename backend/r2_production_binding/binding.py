"""Immutable reviewed production binding for one frozen final master."""

from __future__ import annotations

from dataclasses import dataclass, field

from ._canonical import (
    canonical_json,
    fingerprint,
    fingerprint_entries,
    is_fingerprint,
    parse_fingerprint_entries,
    parse_public_key_entries,
    strict_json_object,
)
from ._binding_body import build_binding_body
from .errors import ProductionBindingError
from .vocabulary import (
    AuthorityDomainV2,
    OperatorRoleV2,
    ProductionCommandV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
)


_SCALAR_FIELDS = (
    "binding_type",
    "final_master_binding_fingerprint",
    "final_commit_oid",
    "final_tree_oid",
    "closure_map_fingerprint",
    "source_package_fingerprint",
    "runbook_fingerprint",
    "workflow_fingerprint",
    "operation",
    "operation_fingerprint",
    "operator_role_registry_fingerprint",
    "command_domain_registry_fingerprint",
    "public_key_registry_fingerprint",
    "production_role_registry_fingerprint",
    "authority_domain_count",
    "preflight_verb_count",
    "process_root_count",
    "local_ref_count",
    "worktree_count",
    "managed_unit_count",
    "max_authority_validity_seconds",
)
_BODY_FIELDS = (
    *_SCALAR_FIELDS,
    "operator_role_fingerprints",
    "command_domains",
    "verification_public_keys",
    "production_role_fingerprints",
)


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ApprovedCutoverBindingV2:
    binding_type: str = field(repr=False)
    final_master_binding_fingerprint: str = field(repr=False)
    final_commit_oid: str = field(repr=False)
    final_tree_oid: str = field(repr=False)
    closure_map_fingerprint: str = field(repr=False)
    source_package_fingerprint: str = field(repr=False)
    runbook_fingerprint: str = field(repr=False)
    workflow_fingerprint: str = field(repr=False)
    operation: str = field(repr=False)
    operation_fingerprint: str = field(repr=False)
    operator_role_registry_fingerprint: str = field(repr=False)
    command_domain_registry_fingerprint: str = field(repr=False)
    public_key_registry_fingerprint: str = field(repr=False)
    production_role_registry_fingerprint: str = field(repr=False)
    authority_domain_count: int
    preflight_verb_count: int
    process_root_count: int
    local_ref_count: int
    worktree_count: int
    managed_unit_count: int
    max_authority_validity_seconds: int
    operator_role_fingerprints: tuple[tuple[OperatorRoleV2, str], ...] = field(repr=False)
    command_domains: tuple[tuple[ProductionCommandV2, AuthorityDomainV2], ...] = field(repr=False)
    verification_public_keys: tuple[tuple[PublicKeyRoleV2, bytes], ...] = field(repr=False)
    production_role_fingerprints: tuple[tuple[ProductionRoleV2, str], ...] = field(repr=False)
    binding_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ApprovedCutoverBindingV2 requires create()")

    @classmethod
    def create(
        cls,
        *,
        final_master_binding: object,
        operation_fingerprint: object,
        operator_role_fingerprints: object,
        verification_public_keys: object,
        production_role_fingerprints: object,
    ) -> ApprovedCutoverBindingV2:
        body = build_binding_body(
            final_master_binding,
            operation_fingerprint,
            operator_role_fingerprints,
            verification_public_keys,
            production_role_fingerprints,
        )
        return _construct(body)

    @classmethod
    def from_json(
        cls,
        payload: object,
        *,
        final_master_binding: object,
    ) -> ApprovedCutoverBindingV2:
        try:
            source = strict_json_object(payload)
            if canonical_json(source) != payload:
                raise ProductionBindingError()
            if set(source) != {*_BODY_FIELDS, "binding_fingerprint"}:
                raise ProductionBindingError()
            body = build_binding_body(
                final_master_binding,
                source["operation_fingerprint"],
                parse_fingerprint_entries(
                    source["operator_role_fingerprints"], OperatorRoleV2
                ),
                parse_public_key_entries(source["verification_public_keys"]),
                parse_fingerprint_entries(
                    source["production_role_fingerprints"], ProductionRoleV2
                ),
            )
            if any(source[name] != body[name] for name in _BODY_FIELDS):
                raise ProductionBindingError()
            expected = fingerprint("r2-approved-cutover-binding-v2", body)
            if source["binding_fingerprint"] != expected:
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
        body["verification_public_keys"] = [
            {"role": role.value, "public_key_hex": key.hex()}
            for role, key in self.verification_public_keys
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
        type(binding) is not ApprovedCutoverBindingV2
        or type(command) is not ProductionCommandV2
        or not (
            subject_fingerprint is None
            or is_fingerprint(subject_fingerprint)
        )
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
    return fingerprint(
        "r2-production-action-v2",
        body,
    )


def _construct(body: dict[str, object]) -> ApprovedCutoverBindingV2:
    value = object.__new__(ApprovedCutoverBindingV2)
    for name in _SCALAR_FIELDS:
        object.__setattr__(value, name, body[name])
    object.__setattr__(
        value,
        "operator_role_fingerprints",
        tuple(
            (OperatorRoleV2(entry["role"]), entry["fingerprint"])
            for entry in body["operator_role_fingerprints"]
        ),
    )
    object.__setattr__(
        value,
        "command_domains",
        tuple(
            (
                ProductionCommandV2(entry["command"]),
                AuthorityDomainV2(entry["domain"]),
            )
            for entry in body["command_domains"]
        ),
    )
    object.__setattr__(
        value,
        "verification_public_keys",
        tuple(
            (PublicKeyRoleV2(entry["role"]), bytes.fromhex(entry["public_key_hex"]))
            for entry in body["verification_public_keys"]
        ),
    )
    object.__setattr__(
        value,
        "production_role_fingerprints",
        tuple(
            (ProductionRoleV2(entry["role"]), entry["fingerprint"])
            for entry in body["production_role_fingerprints"]
        ),
    )
    object.__setattr__(
        value,
        "binding_fingerprint",
        fingerprint("r2-approved-cutover-binding-v2", body),
    )
    return value
