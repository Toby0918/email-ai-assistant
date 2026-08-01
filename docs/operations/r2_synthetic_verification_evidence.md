---
last_update: 2026-08-01
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# R2 Synthetic Verification Evidence

## Scope

This is fresh synthetic evidence for Issues #70-#83 against governing baseline
`ce039b9188587bbb3f8c9950b228b79910dda429`. It authorizes no real command,
Issue #39, host cutover, provider, mailbox, vault, private-data access, merge,
or approval/closure of #38 or #50. The accepted prototype fingerprint is
non-authorizing feasibility prior art only.

## Windows result

The fixed no-argument verifier completed in one fresh physical NTFS sandbox
with terminal `CUTOVER_SUCCESS`. It observed 3 fixed process types, 4 distinct
authorization domains, 9 Project Container zones, 1 repository, 11 worktrees,
4 managed units, 2 independent audit processes, and all 70 semantic gap cases.
Provider attempts, public leakage findings, and real-host operations were all
zero.

## Fresh fingerprints

```text
criteria: 82f7520f14b7ca6b88f2f5759edbe5c4a78ae1c5f7b346182320b660ad679d34
matrix: 627fa92e43112543f6721da25bea4a509b795f7bd01ec662d6c415c7c5280544
script: 5c595e2413163ba2d502b177775a9bd88a60255f96a84d57803890b6cbb20a8f
bundle: 5c82158257a4791ee472464f309264c12930fe01d68f243cf41653e8495d9a38
surface: e6e911e6ead5b8cc4fffd84d22fe03961f64a3e50620050e7fa2066272b57063
package: 7ef79199a1ca915548f2cbdc056ecb182e16f86c459ee367b5661d337e49f3d2
```

The package fingerprint binds the fresh criteria, canonical matrix, fixed
verifier script, exact aggregate bundle, and complete R2 production/script
surface. Any covered-byte change requires a fresh run and a new evidence
record. Portable tests validate contracts only and make no NTFS, ACL, TTY,
process-isolation, or native-durability claim.
