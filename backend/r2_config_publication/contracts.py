"""Closed non-secret Config selection, fault, and receipt contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .canonical import fingerprint, is_fingerprint

_KEYS = (
    "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
    "EMAIL_AGENT_LOG_LEVEL",
)
_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_DOMAIN = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}",
    re.ASCII,
)


class ConfigCrashGap(str, Enum):
    AFTER_INTENT = "after_intent"
    AFTER_EFFECT = "after_effect"
    AFTER_STABLE_VERIFY = "after_stable_verify"
    AFTER_COMMIT = "after_commit"


class ConfigPendingState(str, Enum):
    EFFECT_ABSENT_EXACT = "EFFECT_ABSENT_EXACT"
    EFFECT_PRESENT_EXACT = "EFFECT_PRESENT_EXACT"
    EFFECT_AMBIGUOUS = "EFFECT_AMBIGUOUS"


class ConfigPublicationStatus(str, Enum):
    PUBLISHED = "CONFIG_PUBLISHED"
    RECOVERED = "CONFIG_LOCAL_STATE_RECOVERED"
    INCIDENT_STOP = "INCIDENT_STOP"


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ManagedConfigSelectionV1:
    internal_email_domains: tuple[str, ...] = field(repr=False)
    log_level: str = field(repr=False)
    setting_count: int
    selection_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ManagedConfigSelectionV1 requires create()")

    @classmethod
    def create(cls, value: object):
        if type(value) is not dict or set(value) != set(_KEYS):
            raise ValueError("config_selection_invalid")
        domains = value[_KEYS[0]]
        level = value[_KEYS[1]]
        if (
            type(domains) is not list
            or not 1 <= len(domains) <= 32
            or any(
                type(domain) is not str
                or _DOMAIN.fullmatch(domain) is None
                for domain in domains
            )
            or domains != sorted(set(domains))
            or level not in _LEVELS
        ):
            raise ValueError("config_selection_invalid")
        result = object.__new__(cls)
        object.__setattr__(result, "internal_email_domains", tuple(domains))
        object.__setattr__(result, "log_level", level)
        object.__setattr__(result, "setting_count", 2)
        object.__setattr__(
            result,
            "selection_fingerprint",
            fingerprint("managed-config-selection-v1", value),
        )
        return result

    def dotenv_bytes(self) -> bytes:
        domains = ",".join(self.internal_email_domains)
        return (
            f"{_KEYS[0]}={domains}\n{_KEYS[1]}={self.log_level}\n"
        ).encode("utf-8")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ConfigPublicationPrerequisiteV1:
    quiescence_receipt_fingerprint: str = field(repr=False)
    contract_fingerprint: str = field(repr=False)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ConfigPublicationPrerequisiteV1 requires create()")

    @classmethod
    def create(cls, *, quiescence_receipt_fingerprint: object):
        if not is_fingerprint(quiescence_receipt_fingerprint):
            raise ValueError("config_prerequisite_invalid")
        result = object.__new__(cls)
        object.__setattr__(
            result,
            "quiescence_receipt_fingerprint",
            quiescence_receipt_fingerprint,
        )
        object.__setattr__(
            result,
            "contract_fingerprint",
            fingerprint(
                "config-publication-prerequisite-v1",
                quiescence_receipt_fingerprint,
            ),
        )
        return result


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ConfigFaultSelectorV1:
    kind: str
    boundary: str
    gap: ConfigCrashGap | None

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ConfigFaultSelectorV1 requires a fixed factory")

    @classmethod
    def none(cls):
        return _selector(cls, "none")

    @classmethod
    def crash(cls, boundary: str, gap: ConfigCrashGap):
        if (
            boundary not in {"config_prepare", "config_publish"}
            or type(gap) is not ConfigCrashGap
        ):
            raise ValueError("config_fault_selector_invalid")
        return _selector(cls, "crash", boundary=boundary, gap=gap)

    @classmethod
    def collision(cls):
        return _selector(cls, "collision")

    @classmethod
    def partial_staging(cls):
        return _selector(cls, "partial_staging")

    @classmethod
    def target_replacement(cls):
        return _selector(cls, "target_replacement")

    @classmethod
    def encoding_drift(cls):
        return _selector(cls, "encoding_drift")

    @classmethod
    def line_ending_drift(cls):
        return _selector(cls, "line_ending_drift")

    @classmethod
    def loader_mismatch(cls):
        return _selector(cls, "loader_mismatch")


@dataclass(frozen=True, slots=True, repr=False)
class ConfigPublicationReceiptV1:
    status: ConfigPublicationStatus
    pending_state: ConfigPendingState
    setting_count: int
    provider_disabled: bool
    loader_verified: bool
    retained_artifact_count: int
    selection_fingerprint: str = field(repr=False)
    document_fingerprint: str = field(repr=False)
    target_identity_fingerprint: str = field(repr=False)
    receipt_fingerprint: str = field(repr=False)


def build_receipt(*, status, state, selection, document, target, retained):
    published = status is ConfigPublicationStatus.PUBLISHED
    body = {
        "status": status.value,
        "pending_state": state.value,
        "setting_count": selection.setting_count,
        "provider_disabled": True,
        "loader_verified": published,
        "retained_artifact_count": retained,
        "selection_fingerprint": selection.selection_fingerprint,
        "document_fingerprint": document,
        "target_identity_fingerprint": target,
    }
    return ConfigPublicationReceiptV1(
        status,
        state,
        selection.setting_count,
        True,
        published,
        retained,
        selection.selection_fingerprint,
        document,
        target,
        fingerprint("config-publication-receipt-v1", body),
    )


def _selector(cls: type, kind: str, **values: object):
    result = object.__new__(cls)
    for name, value in {
        "kind": kind,
        "boundary": "",
        "gap": None,
        **values,
    }.items():
        object.__setattr__(result, name, value)
    return result
