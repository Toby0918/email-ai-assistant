---
last_update: 2026-08-01
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Synthetic Verification Criteria

## Authority boundary

This document defines only fresh synthetic verification for Issues #70-#83.
It does not authorize Issue #39, any real command, a real host cutover, provider
access, mailbox access, vault access, private-data access, merge, or approval of
Issue #38, #50, or #39.

The accepted prototype fingerprint
`2923d0940a609b8bb2f9112ba1c1708511de44bd8ecf8611b45603fcbbe49af1`
is non-authorizing feasibility prior art only. It is not an input authority,
receipt predecessor, current-master fingerprint, or substitute for fresh R2
evidence.

## Required Windows evidence

One verifier-owned fresh physical NTFS sandbox must prove:

1. Three distinct fixed process types: preflight, evidence, and transaction.
2. Four distinct authorization domains: preflight, evidence, execution, and
   recovery.
3. Real local `stdin`, `stdout`, and `stderr` TTY ingress at the process seam.
4. Nine exact Project Container zones, one Repository Root, and eleven reviewed
   worktrees.
5. Independent Runtime, database, reviewed CRX, and loader-compatible Config
   units.
6. Start A health, exactly one safe public `rule_fallback` result, exactly one
   matching synthetic row, exact stop, and final database/sidecar proof.
7. Independent stopped-layout and final-running audit processes, Start B health
   without analysis/write, and one final `CUTOVER_SUCCESS` append.
8. Fixed aggregate output, zero public leakage, zero real-host operation, and
   provider attempts equal to zero.

Windows-specific claims are valid only for the Windows-only verifier test.
Portable contract tests validate vocabulary and hashing only and make no
filesystem, ACL, TTY, or process-separation claim.

## Semantic gap evidence

The fixed matrix is the Cartesian product of seven semantics (`acl_scan`,
`staging`, `publication`, `service`, `audit_append`, `recovery`, `final_seal`),
two directions (`forward`, `reverse`), and five gaps (`before_intent`,
`after_intent`, `after_effect`, `after_stable_observation`, `after_commit`).
All 70 cases must execute in distinct fresh test-owned sandboxes.

## Fingerprint package

Fresh evidence must report distinct deterministic SHA-256 fingerprints for the
criteria bytes, canonical 70-case matrix, fixed verifier script bytes, exact
aggregate bundle, complete R2 surface, and the package binding all five inputs
plus the surface. No path, secret, raw terminal transcript, message, customer,
provider payload, or private value may enter public output.
