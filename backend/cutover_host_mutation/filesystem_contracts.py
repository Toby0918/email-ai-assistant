"""Portable no-clobber filesystem mutation observations."""

from __future__ import annotations

from dataclasses import dataclass, field

from .canonical import fingerprint, is_fingerprint
from .errors import CutoverHostMutationError
from .roles import FilesystemMutationKind


@dataclass(frozen=True, slots=True, init=False, repr=False)
class FilesystemMutationExpectationV1:
    schema_version: int
    kind: FilesystemMutationKind
    binding_fingerprint: str = field(repr=False)
    before_fingerprint: str = field(repr=False)
    expected_after_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated filesystem mutation expectation required")

    @classmethod
    def create(
        cls,
        *,
        kind: FilesystemMutationKind,
        binding_fingerprint: str,
        before_fingerprint: str,
        expected_after_fingerprint: str,
    ) -> FilesystemMutationExpectationV1:
        values = (
            binding_fingerprint,
            before_fingerprint,
            expected_after_fingerprint,
        )
        if (
            type(kind) is not FilesystemMutationKind
            or any(not is_fingerprint(item) for item in values)
            or len(set(values)) != len(values)
        ):
            raise CutoverHostMutationError("filesystem_contract_invalid")
        value = object.__new__(cls)
        object.__setattr__(value, "schema_version", 1)
        object.__setattr__(value, "kind", kind)
        object.__setattr__(value, "binding_fingerprint", binding_fingerprint)
        object.__setattr__(value, "before_fingerprint", before_fingerprint)
        object.__setattr__(
            value,
            "expected_after_fingerprint",
            expected_after_fingerprint,
        )
        return value


@dataclass(
    frozen=True,
    slots=True,
    init=False,
    repr=False,
    weakref_slot=True,
)
class FilesystemMutationObservationV1:
    schema_version: int
    kind: FilesystemMutationKind
    journal_intent_fingerprint: str = field(repr=False)
    journal_effect_fingerprint: str = field(repr=False)
    source_identity_fingerprint: str = field(repr=False)
    target_identity_fingerprint: str = field(repr=False)
    parent_identity_fingerprint: str = field(repr=False)
    volume_fingerprint: str = field(repr=False)
    same_identity: bool
    no_replace: bool
    reparse_free: bool
    observation_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("validated filesystem mutation observation required")

    @classmethod
    def create(
        cls,
        *,
        kind: FilesystemMutationKind,
        journal_intent_fingerprint: str,
        journal_effect_fingerprint: str,
        source_identity_fingerprint: str,
        target_identity_fingerprint: str,
        parent_identity_fingerprint: str,
        volume_fingerprint: str,
        same_identity: bool,
        no_replace: bool,
        reparse_free: bool,
    ) -> FilesystemMutationObservationV1:
        body = _observation_body(
            kind=kind,
            journal_intent_fingerprint=journal_intent_fingerprint,
            journal_effect_fingerprint=journal_effect_fingerprint,
            source_identity_fingerprint=source_identity_fingerprint,
            target_identity_fingerprint=target_identity_fingerprint,
            parent_identity_fingerprint=parent_identity_fingerprint,
            volume_fingerprint=volume_fingerprint,
            same_identity=same_identity,
            no_replace=no_replace,
            reparse_free=reparse_free,
        )
        if not _valid_observation(kind, body):
            raise CutoverHostMutationError("filesystem_contract_invalid")
        return _new_observation(cls, kind, body)


def _valid_observation(kind, body: dict[str, object]) -> bool:
    fingerprints = tuple(
        body[key]
        for key in (
            "journal_intent_fingerprint",
            "journal_effect_fingerprint",
            "source_identity_fingerprint",
            "target_identity_fingerprint",
            "parent_identity_fingerprint",
            "volume_fingerprint",
        )
    )
    return (
        type(kind) is FilesystemMutationKind
        and all(is_fingerprint(item) for item in fingerprints)
        and body["no_replace"] is True
        and body["reparse_free"] is True
        and _identity_rule(kind, body)
    )


def _identity_rule(kind, body: dict[str, object]) -> bool:
    if kind is FilesystemMutationKind.CREATE_DIRECTORY:
        return body["same_identity"] is False
    return (
        body["same_identity"] is True
        and body["source_identity_fingerprint"]
        == body["target_identity_fingerprint"]
    )


def _observation_body(**values: object) -> dict[str, object]:
    kind = values.pop("kind")
    return {
        "journal_effect_fingerprint": values["journal_effect_fingerprint"],
        "journal_intent_fingerprint": values["journal_intent_fingerprint"],
        "kind": kind.value if type(kind) is FilesystemMutationKind else kind,
        "no_replace": values["no_replace"],
        "parent_identity_fingerprint": values["parent_identity_fingerprint"],
        "reparse_free": values["reparse_free"],
        "same_identity": values["same_identity"],
        "schema_version": 1,
        "source_identity_fingerprint": values["source_identity_fingerprint"],
        "target_identity_fingerprint": values["target_identity_fingerprint"],
        "volume_fingerprint": values["volume_fingerprint"],
    }


def _new_observation(cls, kind, body):
    value = object.__new__(cls)
    object.__setattr__(value, "schema_version", 1)
    object.__setattr__(value, "kind", kind)
    for key, item in body.items():
        if key not in {"schema_version", "kind"}:
            object.__setattr__(value, key, item)
    object.__setattr__(
        value,
        "observation_fingerprint",
        fingerprint(
            "filesystem-mutation-observation-v1",
            body,
            code="filesystem_contract_invalid",
        ),
    )
    return value
