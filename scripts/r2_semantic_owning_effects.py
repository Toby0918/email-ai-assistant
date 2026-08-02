"""Owning selectors and fault seams for the Issue #83 semantic matrix."""

from __future__ import annotations

import json
import os

from backend.cutover_composition_contracts.canonical import fingerprint
from backend.r2_config_publication import ConfigCrashGap, ConfigFaultSelectorV1
from backend.r2_cross_stage_recovery import (
    CrossStageAdaptersV1,
    CrossStageRecoveryMachine,
    CutoverSuccessAppendV1,
    EffectObservation,
    FinalFreshnessObservationV1,
    FinalSealRequestV1,
    PendingIntentV1,
    RecoveryBoundary,
    RecoveryCrashGap,
    RecoveryFaultSelectorV1,
)
from backend.r2_crx_publication import CrxCrashGap, CrxFaultSelectorV1
from backend.r2_independent_audits import AuditKind, IndependentAuditObservationV1
from backend.r2_independent_audits.testing import SyntheticIndependentAudit
from backend.r2_main_publication import (
    MainPublicationBoundary,
    MainPublicationCrashGap,
    MainPublicationSelectorV1,
)
from backend.r2_main_publication.testing import bind_test_main_publication
from backend.r2_validation_lifecycle import (
    ValidationBoundary,
    ValidationFaultSelectorV1,
    ValidationLifecycle,
)
from tests.r2_cross_stage_recovery_fixture import (
    HEAD,
    IDENTITIES,
    NONCE_B,
    NOW,
    RecoveryAdapters,
    snapshot,
)
from tests.r2_main_publication_fixture import build_main_publication_scenario
from tests.r2_validation_lifecycle_fixture import (
    SyntheticValidationAdapters,
    approved_slice,
)
from tests.test_r2_config_publication_windows import _World as _ConfigWorld
from tests.test_r2_crx_publication_windows import _World as _CrxWorld


def execute_owning_effect(semantic, root, direction, gap):
    functions = {
        "acl_scan": _acl,
        "staging": _staging,
        "publication": _publication,
        "service": _service,
        "audit_append": _audit,
        "recovery": _recovery,
        "final_seal": _final_seal,
    }
    return functions[semantic](root, direction, gap)


def _acl(root, direction, gap):
    scenario = build_main_publication_scenario(root)
    trace = None
    try:
        clock = (lambda: 120) if gap == "before_intent" else (lambda: 100)
        trace = bind_test_main_publication(
            scenario, observed_at_epoch=100, _clock=clock
        )
        if gap == "before_intent":
            try:
                trace.execute(MainPublicationSelectorV1.none())
            except ValueError:
                classification = trace.classify_restart()
            else:
                raise RuntimeError("R2_ACL_BEFORE_INTENT_NOT_BLOCKED")
        else:
            selector = MainPublicationSelectorV1.create(
                boundary=MainPublicationBoundary.DIRECTORY_RELOCATION,
                gap=_main_gap(gap),
            )
            try:
                trace.execute(selector)
            except RuntimeError:
                classification = trace.classify_restart()
            else:
                raise RuntimeError("R2_ACL_GAP_NOT_INTERRUPTED")
        rolled_back = False
        if direction == "reverse" and classification.value != "INCIDENT_STOP":
            trace.rollback()
            rolled_back = True
        return {
            "selector": gap,
            "classification": classification.value,
            "rolled_back": rolled_back,
        }
    finally:
        if trace is not None:
            trace.close()
        scenario.close()


def _main_gap(gap):
    values = {
        "after_intent": MainPublicationCrashGap.AFTER_INTENT,
        "after_effect": MainPublicationCrashGap.AFTER_EFFECT,
        "after_stable_observation": MainPublicationCrashGap.AFTER_OBSERVATION,
        "after_commit": MainPublicationCrashGap.AFTER_COMMIT,
    }
    return values[gap]


def _staging(root, direction, gap):
    with _CrxWorld(root) as world:
        transaction = world.transaction()
        if gap == "before_intent":
            value = transaction.recover()
        else:
            selector = CrxFaultSelectorV1.crash(
                "crx_publish" if direction == "forward" else "crx_prepare",
                _crx_gap(gap),
            )
            try:
                transaction.execute(selector)
            except RuntimeError:
                value = transaction.recover()
            else:
                raise RuntimeError("R2_STAGING_GAP_NOT_INTERRUPTED")
        return {
            "selector": gap,
            "status": value.status.value,
            "pending": value.pending_state.value,
        }


def _crx_gap(gap):
    return {
        "after_intent": CrxCrashGap.AFTER_INTENT,
        "after_effect": CrxCrashGap.AFTER_EFFECT,
        "after_stable_observation": CrxCrashGap.AFTER_STABLE_VERIFY,
        "after_commit": CrxCrashGap.AFTER_COMMIT,
    }[gap]


def _publication(root, direction, gap):
    with _ConfigWorld(root) as world:
        transaction = world.transaction()
        if gap == "before_intent":
            value = transaction.recover()
        else:
            selector = ConfigFaultSelectorV1.crash(
                "config_publish" if direction == "forward" else "config_prepare",
                _config_gap(gap),
            )
            try:
                transaction.execute(selector)
            except RuntimeError:
                value = transaction.recover()
            else:
                raise RuntimeError("R2_PUBLICATION_GAP_NOT_INTERRUPTED")
        return {
            "selector": gap,
            "status": value.status.value,
            "pending": value.pending_state.value,
        }


def _config_gap(gap):
    return {
        "after_intent": ConfigCrashGap.AFTER_INTENT,
        "after_effect": ConfigCrashGap.AFTER_EFFECT,
        "after_stable_observation": ConfigCrashGap.AFTER_STABLE_VERIFY,
        "after_commit": ConfigCrashGap.AFTER_COMMIT,
    }[gap]


def _service(root, direction, gap):
    del root
    boundary = {
        "before_intent": ValidationBoundary.START_A,
        "after_intent": ValidationBoundary.HEALTH_A,
        "after_effect": ValidationBoundary.ANALYSIS_A,
        "after_stable_observation": ValidationBoundary.CONFIRM_A,
        "after_commit": ValidationBoundary.ROW_A,
    }[gap]
    fault = (
        ValidationFaultSelectorV1.crash(boundary)
        if direction == "forward"
        else ValidationFaultSelectorV1.deterministic_failure(boundary)
    )
    value = ValidationLifecycle.create(
        approved=approved_slice(),
        adapters=SyntheticValidationAdapters().bundle(),
        nonce_factory=_nonces(),
        now=lambda: NOW,
        fault=fault,
    ).run()
    return {
        "fault": fault.kind,
        "boundary": boundary.value,
        "status": value.status.value,
        "completed": value.completed_boundaries,
    }


def _audit(root, direction, gap):
    kind = (
        AuditKind.STOPPED_LAYOUT
        if direction == "forward"
        else AuditKind.FINAL_RUNNING_HEALTH
    )
    target = root / "attestation.json"
    values = _audit_values(kind, direction)

    def append(value):
        payload = json.dumps(value, sort_keys=True, separators=(",", ":"))
        with target.open("x", encoding="ascii", newline="\n") as stream:
            stream.write(payload + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    audit = SyntheticIndependentAudit.create(
        **values, now=lambda: NOW, append_attestation=append
    )
    observation = _audit_observation(values, gap)
    result = audit.run(observation)
    return {
        "gap": gap,
        "disposition": result.disposition.value,
        "durable": target.exists() and target.read_bytes().endswith(b"\n"),
    }


def _audit_values(kind, direction):
    return {
        "kind": kind,
        "operation_fingerprint": fingerprint("r2-gap-operation-v1", direction),
        "approved_binding_fingerprint": fingerprint("r2-gap-binding-v1", direction),
        "journal_head_fingerprint": HEAD,
        "approved_identities_fingerprint": IDENTITIES,
        "health_evidence_fingerprint": fingerprint("r2-gap-health-v1", direction),
        "observed_at_epoch": NOW,
    }


def _audit_observation(values, gap):
    operation = values["operation_fingerprint"]
    health = values["health_evidence_fingerprint"]
    unambiguous = True
    if gap == "before_intent":
        operation = fingerprint("r2-gap-before-intent-v1", operation)
    elif gap == "after_intent":
        operation = fingerprint("r2-gap-after-intent-v1", operation)
    elif gap == "after_effect":
        health = fingerprint("r2-gap-after-effect-v1", health)
    elif gap == "after_stable_observation":
        unambiguous = False
    return IndependentAuditObservationV1(
        audit_kind=values["kind"],
        operation_fingerprint=operation,
        approved_binding_fingerprint=values["approved_binding_fingerprint"],
        journal_head_fingerprint=values["journal_head_fingerprint"],
        approved_identities_fingerprint=values["approved_identities_fingerprint"],
        health_evidence_fingerprint=health,
        observed_at_epoch=NOW,
        unambiguous=unambiguous,
    )


def _recovery(root, direction, gap):
    del root
    adapters = RecoveryAdapters()
    boundary = RecoveryBoundary.PRESERVE_FAILED_CONTAINER
    intent_fingerprint = fingerprint(
        "r2-semantic-recovery-intent-v1", {"direction": direction, "gap": gap}
    )
    pending = (
        PendingIntentV1.create(
            direction=direction,
            boundary=boundary,
            intent_fingerprint=intent_fingerprint,
        ),
    )
    if direction == "reverse":
        adapters.observations[intent_fingerprint] = EffectObservation.ABSENT
    fault = RecoveryFaultSelectorV1.crash(boundary, RecoveryCrashGap(gap))
    machine = CrossStageRecoveryMachine.create(
        snapshot=snapshot(pending=pending, remaining=(boundary,)),
        adapters=adapters.bundle(),
        now=lambda: NOW,
        fault=fault,
    )
    value = machine.recover(adapters.authority)
    return {
        "gap": gap,
        "status": value.status.value,
        "mutations": value.host_mutations,
        "appends": value.journal_appends,
    }


def _final_seal(root, direction, gap):
    del root
    if direction == "reverse":
        return _recovery(None, direction, gap)
    validation = ValidationLifecycle.create(
        approved=approved_slice(),
        adapters=SyntheticValidationAdapters().bundle(),
        nonce_factory=_nonces(),
        now=lambda: NOW,
        fault=ValidationFaultSelectorV1.none(),
    ).run()
    machine = CrossStageRecoveryMachine.create(
        snapshot=snapshot(pending=(), remaining=()),
        adapters=_seal_adapters(),
        now=lambda: NOW,
        fault=RecoveryFaultSelectorV1.seal_crash(RecoveryCrashGap(gap)),
    )
    value = machine.seal(_seal_request(validation))
    return {"gap": gap, "status": value.status.value, "appends": value.journal_appends}


def _seal_request(validation):
    return FinalSealRequestV1.create(
        validation=validation,
        current_journal_head=HEAD,
        nonce_b=NONCE_B,
        approved_identities_fingerprint=IDENTITIES,
        stopped_identities_fingerprint=validation.stopped_audit.approved_identities_fingerprint,
        final_identities_fingerprint=validation.final_audit.approved_identities_fingerprint,
    )


def _seal_adapters():
    state = {"head": HEAD}

    def freshness():
        return FinalFreshnessObservationV1.create(
            journal_head_fingerprint=HEAD,
            nonce_b=NONCE_B,
            approved_identities_fingerprint=IDENTITIES,
            observed_at_epoch=NOW,
        )

    def append(record_type, prior, material):
        new_head = fingerprint("r2-gap-success-head-v1", material)
        state["head"] = new_head
        return CutoverSuccessAppendV1.create(
            record_type=record_type,
            prior_head_fingerprint=prior,
            journal_head_fingerprint=new_head,
            material_fingerprint=material,
        )

    return CrossStageAdaptersV1(
        observe_intent=lambda _value: None,
        current_journal_head=lambda: state["head"],
        reverse_boundary=lambda *_values: None,
        minimal_final_freshness=freshness,
        append_cutover_success=append,
    )


def _nonces():
    return iter(("11111111-1111-4111-8111-111111111111", NONCE_B)).__next__
