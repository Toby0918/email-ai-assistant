---
last_update: 2026-08-07
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Final R2 Operator Runbook

Generated from the latent R2 command catalog and state machine; do not hand edit command semantics.

- Catalog fingerprint: `2ebcacc7c57df0341b11f7675666e4bc23b70df05885fcce9777f5edb45ed5a4`
- State-machine fingerprint: `ebddb1a10d88d9378bae5bcfb0e985b36b660cd5786d6b4ef68765080f44a9f1`
- Package-semantics fingerprint: `f90ea90b55f160bfa5dd396e5a0ebe5dc2989be50d08c2da837961f35fd435d2`
- Decision-registry fingerprint: `4ac5feffbdd30d088dd5f7b3629060cfe050a36b657392292e8c3da655afa383`
- R1-blocker-resolution fingerprint: `1193dbdb051b849c6e4e3f5c52d72ef30ff89c2393fcc307947c10759303f439`
- Issue #110 production result: `DORMANT_NO_ISSUE39_APPROVAL` before argv, TTY, confirmation, Adapter, journal, callback, or host access.
- Assurance model: `SOLE_MAINTAINER_SELF_REVIEW`; Issue #39 authority count: `0`.

## Latent command catalog

| # | Surface | Verb | Command | Effect | Non-authorizing catalog acknowledgement | Max operations |
| ---: | --- | --- | --- | --- | --- | ---: |
| 1 | `preflight` | `current-topology` | `current_topology_preflight` | `read_only` | `ACKNOWLEDGE_R2_PREFLIGHT` | 1 |
| 2 | `preflight` | `host-baseline` | `host_baseline` | `read_only` | `ACKNOWLEDGE_R2_PREFLIGHT` | 1 |
| 3 | `preflight` | `evidence-review` | `evidence_review` | `read_only` | `ACKNOWLEDGE_R2_PREFLIGHT` | 1 |
| 4 | `preflight` | `evidence-verification` | `evidence_verification` | `read_only` | `ACKNOWLEDGE_R2_PREFLIGHT` | 1 |
| 5 | `preflight` | `final-audit-readiness` | `final_audit_readiness` | `read_only` | `ACKNOWLEDGE_R2_PREFLIGHT` | 1 |
| 6 | `preflight` | `recovery-inspection` | `recovery_inspection` | `read_only` | `ACKNOWLEDGE_R2_PREFLIGHT` | 1 |
| 7 | `evidence` | `publish` | `evidence_publication` | `publication` | `ACKNOWLEDGE_R2_EVIDENCE_PUBLICATION` | 1 |
| 8 | `transaction` | `execute` | `execute` | `forward` | `ACKNOWLEDGE_R2_TRANSACTION_ACTION` | 1 |
| 9 | `transaction` | `resume` | `resume` | `resume` | `ACKNOWLEDGE_R2_TRANSACTION_ACTION` | 1 |
| 10 | `transaction` | `rollback` | `rollback` | `rollback` | `ACKNOWLEDGE_R2_TRANSACTION_ACTION` | 1 |

## Latent post-approval state machine

| Phase | Allowed commands | Next phases | Required evidence |
| --- | --- | --- | --- |
| `preflight` | `current-topology`, `host-baseline`, `evidence-review`, `evidence-verification`, `final-audit-readiness`, `recovery-inspection` | `evidence_publication` | `issue39_approval`, `fresh_execution_confirmation`, `exact_preflight_receipts` |
| `evidence_publication` | `publish` | `forward` | `fresh_execution_confirmation`, `reviewed_evidence_genesis` |
| `forward` | `execute` | `forward`, `forward_recovery`, `retention_reconciliation` | `fresh_execution_confirmation`, `unified_journal_commit` |
| `forward_recovery` | `recovery-inspection`, `resume`, `rollback` | `forward`, `rollback` | `tri_state_inspection`, `fresh_execution_confirmation` |
| `rollback` | `rollback` | `rollback`, `rollback_recovery`, `retention_reconciliation` | `fresh_execution_confirmation`, `lifo_reverse_commit` |
| `rollback_recovery` | `recovery-inspection`, `rollback` | `rollback`, `retention_reconciliation` | `tri_state_inspection`, `fresh_execution_confirmation` |
| `retention_reconciliation` | none | `issue38_final_review` | `object_level_retention_proof`, `zero_deletion_capability` |
| `issue38_final_review` | none | terminal | `fresh_issue38_review`, `no_issue39_authority` |

## Issue #38 decision registry

Every row is re-reviewed exactly once against the frozen final master; historical R1 values are not current authority.

| # | Decision ID | Decision | R2 completion proof |
| ---: | --- | --- | --- |
| 1 | `R2-D38-01` | Maintenance window | final-master binding and human review |
| 2 | `R2-D38-02` | Start stop and abort gates | unified journal and incident-stop proof |
| 3 | `R2-D38-03` | Legacy source | Git-byte and exact-identity proof |
| 4 | `R2-D38-04` | Container ACL | Windows-native ACL and parent-scope proof |
| 5 | `R2-D38-05` | Evidence | reviewed create-only package and retention proof |
| 6 | `R2-D38-06` | Worktrees | fourteen-ref eleven-worktree Git-byte proof |
| 7 | `R2-D38-07` | Runtime | hash-locked dependency and Runtime publication proof |
| 8 | `R2-D38-08` | LocalData | stopped create-only SQLite publication proof |
| 9 | `R2-D38-09` | Browser extension | create-only CRX publication proof |
| 10 | `R2-D38-10` | Config and providers | create-only Config and provider-disabled proof |
| 11 | `R2-D38-11` | Preflight | six-verb production composition proof |
| 12 | `R2-D38-12` | Post-cutover verification | two-start lifecycle and independent-audit proof |
| 13 | `R2-D38-13` | Rollback | journal-derived LIFO legacy restoration proof |
| 14 | `R2-D38-14` | Retention and no deletion | object ledger and zero-delete capability proof |

## R1 blocker completion map

| Historical blocker | Blocker class | R2 completion proof |
| --- | --- | --- |
| Issue #34 | real host audit composition | preflight production root and final-audit receipt |
| Issue #35 | host baseline and evidence composition | evidence production root and verified package receipt |
| Issue #36 | mixed worktree transaction and recovery | Git-byte receipt unified journal and rollback seal |
| Issue #37 | managed unit publication and lifecycle | Runtime SQLite CRX Config and two-start receipts |

## Issue #110 reachability boundary

All ten catalog commands are latent. Every fixed production verb returns `DORMANT_NO_ISSUE39_APPROVAL` before reading argv, TTY, clock, acknowledgement, confirmation, bootstrap, Adapter, journal, callback, environment, file, or artifact state.

No Solo Maintainer closure manifest, attestation receipt, hosted check, CI result, runbook, bootstrap object, environment value, file, argument, acknowledgement, or synthetic marker can unlock a production root. Issue #38 approval and a separate Issue #39 code allowlist are required before any future wiring.

## Execution Confirmation boundary

A future action uses exactly one fresh, single-use `ExecutionConfirmationClaimV1` bound to the V3 production binding, closure manifest and attestation, exact command/action, current journal head, next sequence, transition, and remaining reverse plan.

The future exact acknowledgement is `CONFIRM_R2_ISSUE39_EXECUTION_V1_NOT_CLOSURE_ATTESTATION`. A claim must be durably appended before one Adapter attempt and becomes consumed by that attempt even on failure. The Issue #110 executable graph cannot reach preparation, confirmation, append, Adapter acquisition, or invocation.

## Forward and recovery rules

After a future separate enablement, each invocation accepts exactly one catalog verb and at most one operation. A crash requires two-read `recovery-inspection`; exact PRE requires a new Execution Confirmation, exact POST commits without replay, and ambiguity incident-stops. Rollback is journal-derived LIFO, preserves the failed Container first, and ends only at `LEGACY_FLAT_LAYOUT_RESTORED`.

## Retention and no-deletion rule

After forward, resume, rollback, or recovery, reconcile the deterministic object-level retention ledger. Original, new, partial, failed, evidence, and journal artifacts remain tracked with zero deletion capability, zero overwrite/prune/automatic-expiry capability, and zero private payload fields.

## Drift and decision boundary

Reject a stale final master, stale source-package hash, mixed V3 binding, changed catalog/state-machine fingerprint, unknown verb, or historical R1 package semantics. This document, Hosted Evidence, CI, synthetic evidence, Solo Maintainer Attestation, and closure receipts are never Issue #38 approval or Issue #39 execution authority.

The verifier can establish only `ELIGIBLE_FOR_ISSUE38_FINAL_REVIEW`. Issue #38 remains a separate fresh decision and Issue #39 remains blocked.
