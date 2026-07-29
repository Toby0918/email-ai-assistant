"""Closed deterministic non-secret managed Config contract."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .canonical import canonical_json, fail

_ERROR = "managed_config_invalid"
_DOMAIN = re.compile(
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z]{2,63}",
    re.ASCII,
)
_INPUT_KEYS = (
    "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
    "EMAIL_AGENT_LOG_LEVEL",
)
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")


@dataclass(frozen=True, slots=True, init=False, repr=False)
class ManagedConfigV1:
    internal_email_domains: tuple[str, ...] = field(repr=False)
    log_level: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ManagedConfigV1 requires from_mapping()")

    @classmethod
    def from_mapping(cls, value: object) -> ManagedConfigV1:
        if (
            type(value) is not dict
            or set(value) != set(_INPUT_KEYS)
            or any(type(key) is not str for key in value)
        ):
            fail(_ERROR)
        domains = value["EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS"]
        log_level = value["EMAIL_AGENT_LOG_LEVEL"]
        if (
            type(domains) is not list
            or not 1 <= len(domains) <= 32
            or any(
                type(domain) is not str
                or _DOMAIN.fullmatch(domain) is None
                for domain in domains
            )
            or domains != sorted(set(domains))
            or type(log_level) is not str
            or log_level not in _LOG_LEVELS
        ):
            fail(_ERROR)
        config = object.__new__(cls)
        object.__setattr__(config, "internal_email_domains", tuple(domains))
        object.__setattr__(config, "log_level", log_level)
        return config

    def to_canonical_bytes(self) -> bytes:
        return canonical_json(
            {
                "config_type": "managed-non-secret-config/v1",
                "EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE": "conservative",
                "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": list(
                    self.internal_email_domains
                ),
                "EMAIL_AGENT_LLM_PROVIDER": "disabled",
                "EMAIL_AGENT_LOG_LEVEL": self.log_level,
                "EMAIL_AGENT_TEXT_FALLBACK_PROVIDER": "disabled",
            },
            code=_ERROR,
        )
