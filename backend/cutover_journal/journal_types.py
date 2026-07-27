"""Closed step and state values for Issue #52."""

from enum import Enum


class JournalDirection(str, Enum):
    FORWARD = "FORWARD"
    REVERSE = "REVERSE"


class JournalEventCode(str, Enum):
    INTENT = "INTENT"
    RESUME_BOUND = "RESUME_BOUND"
    EFFECT_OBSERVED = "EFFECT_OBSERVED"
    COMMITTED = "COMMITTED"


class JournalEffectOutcome(str, Enum):
    PENDING = "PENDING"
    APPLIED = "APPLIED"
    NOT_APPLIED = "NOT_APPLIED"


class JournalStepCode(str, Enum):
    SYNTHETIC_PREPARE = "SYNTHETIC_PREPARE"
    SYNTHETIC_PUBLISH = "SYNTHETIC_PUBLISH"


FORWARD_STEP_ORDER = tuple(step.value for step in JournalStepCode)
