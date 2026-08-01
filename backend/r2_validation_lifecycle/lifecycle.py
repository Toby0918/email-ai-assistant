"""Single-use two-start provider-disabled validation composition."""

from __future__ import annotations

from backend.cutover_composition_contracts.canonical import fingerprint
from backend.cutover_service_lifecycle import ServiceHealthEvidenceV1, ServiceStartEvidenceV1, ServiceStopEvidenceV1
from backend.r2_independent_audits import AuditKind

from .adapters import ValidationAdaptersV1
from .contracts import ApprovedValidationSliceV1, FinalDatabaseProofV1, IndependentAuditCompletionV1, IndependentAuditRequestV1, OperatorPublicConfirmationV1, PersistedPublicRowEvidenceV1, PublicRuleFallbackResultV1, ValidationBoundary, ValidationFaultSelectorV1, ValidationLifecycleResultV1, ValidationStatus, start_request


class _Rejected(Exception):
    def __init__(self, status):
        self.status = status


class ValidationLifecycle:
    __slots__ = ("_approved", "_adapters", "_nonce", "_now", "_fault", "_state", "_completed", "_analysis_count", "_write_count", "_provider_attempts", "_start_a", "_start_b", "_health_a", "_health_b", "_analysis", "_row", "_stopped", "_audit_pids")

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("ValidationLifecycle requires create()")

    @classmethod
    def create(cls, *, approved, adapters, nonce_factory, now, fault):
        if type(approved) is not ApprovedValidationSliceV1 or type(adapters) is not ValidationAdaptersV1 or not adapters.exact() or not callable(nonce_factory) or not callable(now) or type(fault) is not ValidationFaultSelectorV1:
            raise ValueError("R2_VALIDATION_LIFECYCLE_BINDING_INVALID")
        value = object.__new__(cls)
        value._approved, value._adapters = approved, adapters
        value._nonce, value._now, value._fault = nonce_factory, now, fault
        value._state, value._completed = "ready", 0
        value._analysis_count = value._write_count = value._provider_attempts = 0
        value._start_a = value._start_b = value._health_a = value._health_b = None
        value._analysis = value._row = value._stopped = None
        value._audit_pids = []
        return value

    def run(self):
        if self._state != "ready":
            raise ValueError("R2_VALIDATION_LIFECYCLE_SINGLE_USE")
        self._state = "running"
        steps = ((ValidationBoundary.START_A, self._do_start_a), (ValidationBoundary.HEALTH_A, self._do_health_a), (ValidationBoundary.ANALYSIS_A, self._do_analysis), (ValidationBoundary.CONFIRM_A, self._do_confirm), (ValidationBoundary.ROW_A, self._do_row), (ValidationBoundary.STOP_A, self._do_stop), (ValidationBoundary.DATABASE_VERIFY, self._do_database), (ValidationBoundary.STOPPED_AUDIT, self._do_stopped_audit), (ValidationBoundary.START_B, self._do_start_b), (ValidationBoundary.HEALTH_B, self._do_health_b), (ValidationBoundary.FINAL_AUDIT, self._do_final_audit))
        for boundary, action in steps:
            stopped = self._step(boundary, action)
            if stopped is not None:
                self._state = "stopped"
                return stopped
        self._state = "complete"
        return self._result(ValidationStatus.VALIDATED)

    def _step(self, boundary, action):
        if self._fault.boundary is boundary:
            status = ValidationStatus.INCIDENT_STOP if self._fault.kind == "ambiguous_failure" else ValidationStatus.ROLLBACK_REQUIRED
            return self._result(status)
        try:
            action()
        except _Rejected as error:
            return self._result(error.status)
        except Exception:
            return self._result(ValidationStatus.INCIDENT_STOP)
        self._completed += 1
        return None

    def _do_start_a(self):
        request = start_request(self._approved, "start_a", self._nonce())
        self._start_a = self._adapters.start_provider_disabled(request)
        self._validate_start(request, self._start_a, None)

    def _do_health_a(self):
        self._health_a = self._adapters.read_health(self._start_a)
        self._validate_health(self._start_a, self._health_a)

    def _do_analysis(self):
        self._analysis = self._adapters.analyze_public_rule_fallback(self._request_a())
        if type(self._analysis) is not PublicRuleFallbackResultV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        self._provider_attempts = self._analysis.provider_attempts
        self._analysis_count = 1
        if self._analysis.request_fingerprint != self._request_a().request_fingerprint or self._analysis.analysis_engine_source != "rule_fallback" or self._analysis.provider_attempts != 0 or not self._analysis.safe:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)

    def _do_confirm(self):
        value = self._adapters.confirm_public_result(self._analysis)
        if type(value) is not OperatorPublicConfirmationV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        if not value.confirmed or value.result_fingerprint != self._analysis.result_fingerprint:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)

    def _do_row(self):
        self._row = self._adapters.observe_persisted_row(self._analysis, self._approved.database_role_fingerprint)
        if type(self._row) is not PersistedPublicRowEvidenceV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        self._write_count = self._row.write_count
        if self._row.result_fingerprint != self._analysis.result_fingerprint or self._row.database_role_fingerprint != self._approved.database_role_fingerprint or self._row.matching_rows != 1 or self._row.write_count != 1:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)

    def _do_stop(self):
        value = self._adapters.stop_exact(self._start_a)
        if type(value) is not ServiceStopEvidenceV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        if value != ServiceStopEvidenceV1.create_from_start(self._start_a):
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)
        self._stopped = value

    def _do_database(self):
        value = self._adapters.final_database_proof(self._approved.database_role_fingerprint, self._row)
        if type(value) is not FinalDatabaseProofV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        if value.database_role_fingerprint != self._approved.database_role_fingerprint or value.checkpoint != "FINAL_OR_RECOVERY_VERIFY" or value.matching_rows != 1 or value.sidecar_count != 0 or not value.source_unchanged:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)

    def _do_stopped_audit(self):
        self._validate_audit(self._adapters.run_independent_audit(self._audit_request(AuditKind.STOPPED_LAYOUT, self._start_a, self._stopped)), AuditKind.STOPPED_LAYOUT, self._start_a, self._stopped)

    def _do_start_b(self):
        request = start_request(self._approved, "start_b", self._nonce())
        self._start_b = self._adapters.start_provider_disabled(request)
        self._validate_start(request, self._start_b, self._start_a)

    def _do_health_b(self):
        self._health_b = self._adapters.read_health(self._start_b)
        self._validate_health(self._start_b, self._health_b)

    def _do_final_audit(self):
        self._validate_audit(self._adapters.run_independent_audit(self._audit_request(AuditKind.FINAL_RUNNING_HEALTH, self._start_b, self._health_b)), AuditKind.FINAL_RUNNING_HEALTH, self._start_b, self._health_b)

    def _validate_start(self, request, start, prior):
        if type(start) is not ServiceStartEvidenceV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        expected = (request.nonce, request.profile_fingerprint, request.runtime_fingerprint, request.config_fingerprint, request.database_role_fingerprint, request.port, "disabled", "disabled")
        observed = (start.nonce, start.profile_fingerprint, start.runtime_fingerprint, start.config_fingerprint, start.data_role_fingerprint, start.port, start.primary_provider, start.fallback_provider)
        if observed != expected or start.executable_fingerprint != request.runtime_fingerprint or start.port_owner_pid != start.pid:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)
        if prior is not None and (start.pid == prior.pid or start.start_time_ns == prior.start_time_ns or start.nonce == prior.nonce):
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)

    def _validate_health(self, start, health):
        if type(health) is not ServiceHealthEvidenceV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        if health.to_mapping() != {**start.to_mapping(), "healthy": True}:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)

    def _audit_request(self, kind, start, evidence):
        identities = fingerprint("r2-validation-audit-identities-v1", {"approved": self._approved.approved_identities_fingerprint, "start": start.to_mapping(), "evidence": evidence.to_mapping()})
        health = fingerprint("r2-validation-audit-health-v1", evidence.to_mapping())
        return IndependentAuditRequestV1(kind, start.nonce, start.pid, self._approved.journal_head_fingerprint, identities, health)

    def _validate_audit(self, value, kind, start, evidence):
        request = self._audit_request(kind, start, evidence)
        if type(value) is not IndependentAuditCompletionV1:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        exact = (value.audit_kind is kind and value.service_nonce == request.service_nonce and value.service_process_id == request.service_process_id and value.journal_head_fingerprint == request.journal_head_fingerprint and value.approved_identities_fingerprint == request.approved_identities_fingerprint and value.health_evidence_fingerprint == request.health_evidence_fingerprint and value.attested)
        now = self._now()
        if not exact:
            raise _Rejected(ValidationStatus.ROLLBACK_REQUIRED)
        if type(now) is not int or not value.observed_at_epoch <= now <= value.expires_at_epoch or value.expires_at_epoch - value.observed_at_epoch != 300 or value.audit_process_id in {start.pid, *self._audit_pids}:
            raise _Rejected(ValidationStatus.INCIDENT_STOP)
        self._audit_pids.append(value.audit_process_id)

    def _request_a(self):
        return start_request(self._approved, "start_a", self._start_a.nonce)

    def _result(self, status):
        body = {"status": status.value, "completed": self._completed, "analysis": self._analysis_count, "writes": self._write_count, "providers": self._provider_attempts, "slice": self._approved.slice_fingerprint}
        return ValidationLifecycleResultV1(status, self._completed, self._analysis_count, self._write_count, self._provider_attempts, fingerprint("r2-validation-lifecycle-result-v1", body))
