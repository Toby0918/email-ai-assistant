---
last_update: 2026-08-02
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Final R2 Operator Runbook

Generated from the executable R2 command catalog and state machine; do not hand edit command semantics.

- Catalog fingerprint: `2ebcacc7c57df0341b11f7675666e4bc23b70df05885fcce9777f5edb45ed5a4`
- State-machine fingerprint: `fd2a17d09970202682edaa7ee6bf946db8545e459ffe3304446f2e9acdb503b0`
- Package-semantics fingerprint: `f2c0c35c94206f99eda0b86d76bf508b340df13ff3f21d558e1f922755b816ac`
- Default production result: `DORMANT_NO_EXTERNAL_ISSUER` until separately supplied valid authority.

## Executable command catalog

| # | Surface | Verb | Command | Effect | Acknowledgement | Max operations |
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

## State machine

| Phase | Allowed commands | Next phases | Required evidence |
| --- | --- | --- | --- |
| `preflight` | `current-topology`, `host-baseline`, `evidence-review`, `evidence-verification`, `final-audit-readiness`, `recovery-inspection` | `evidence_publication` | `exact_preflight_receipts` |
| `evidence_publication` | `publish` | `forward` | `reviewed_evidence_genesis` |
| `forward` | `execute` | `forward`, `forward_recovery`, `retention_reconciliation` | `unified_journal_commit` |
| `forward_recovery` | `recovery-inspection`, `resume`, `rollback` | `forward`, `rollback` | `tri_state_inspection`, `fresh_authority` |
| `rollback` | `rollback` | `rollback`, `rollback_recovery`, `retention_reconciliation` | `lifo_reverse_commit` |
| `rollback_recovery` | `recovery-inspection`, `rollback` | `rollback`, `retention_reconciliation` | `tri_state_inspection`, `fresh_recovery_authority` |
| `retention_reconciliation` | none | `human_final_review` | `object_level_retention_proof`, `zero_deletion_capability` |
| `human_final_review` | none | terminal | `human_review_only`, `no_execution_authority` |

## Forward and recovery rules

Each invocation accepts exactly one catalog verb and at most one operation. `execute`, `resume`, and `rollback` require fresh single-use authority bound to the current unified-journal head and exact remaining plan.

A crash requires two-read `recovery-inspection`. Exact PRE requires fresh authority; exact POST commits without replay; ambiguity incident-stops. Rollback is journal-derived LIFO, preserves the failed Container first, and ends only at `LEGACY_FLAT_LAYOUT_RESTORED`.

## Retention and no-deletion rule

After forward, resume, rollback, or recovery, reconcile the deterministic object-level retention ledger. Original, new, partial, failed, evidence, and journal artifacts remain tracked with zero deletion capability, zero overwrite/prune/automatic-expiry capability, and zero private payload fields.

## Drift and authority boundary

Reject a stale final master, stale source-package hash, mixed binding, changed catalog/state-machine fingerprint, unknown verb, or historical R1 package semantics. This document, CI, synthetic evidence, and closure receipts are never execution authority.

Human final review and Issue #38 approval remain separate manual decisions. Issue #39 remains blocked until that approval.
