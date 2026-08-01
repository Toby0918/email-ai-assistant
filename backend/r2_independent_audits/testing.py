"""Synthetic-only binding for an independent audit invocation."""

from __future__ import annotations

import os

from .process import IndependentAuditProcess
from .sink import IndependentAuditAttestationSinkV1


class SyntheticIndependentAudit:
    __slots__ = ("_process",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("SyntheticIndependentAudit requires create()")

    @classmethod
    def create(cls, **values):
        sink = IndependentAuditAttestationSinkV1.bind(
            **values,
            process_id=os.getpid(),
        )
        audit = object.__new__(cls)
        audit._process = IndependentAuditProcess.create(sink)
        return audit

    def run(self, observation):
        return self._process.run(observation)
