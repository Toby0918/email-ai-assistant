"""One-observation process surface that receives one exact audit sink."""

from __future__ import annotations

from .contracts import IndependentAuditObservationV1, IndependentAuditResult
from .sink import IndependentAuditAttestationSinkV1


class IndependentAuditProcess:
    __slots__ = ("_sink",)

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("IndependentAuditProcess requires create()")

    @classmethod
    def create(cls, sink: IndependentAuditAttestationSinkV1):
        if type(sink) is not IndependentAuditAttestationSinkV1:
            raise TypeError("INDEPENDENT_AUDIT_EXACT_SINK_REQUIRED")
        process = cls.__new__(cls)
        process._sink = sink
        return process

    def run(
        self, observation: IndependentAuditObservationV1
    ) -> IndependentAuditResult:
        return self._sink.attest(observation)
