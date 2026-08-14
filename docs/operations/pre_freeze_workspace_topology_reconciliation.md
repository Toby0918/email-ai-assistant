---
last_update: 2026-08-13
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Pre-freeze workspace topology reconciliation

## Result

This is a content-free, read-only inventory collected before freezing the next
Issue #38 master. It records directory names, Git/worktree metadata, status
counts, registry state, and recommended disposition classes. It does not read
legacy LocalData, private data, mailbox, provider, vault, credential, database,
or file payload content.

No directory, worktree, Git administrative entry, ref, artifact, stage, or
failure site was deleted, moved, renamed, overwritten, unregistered, pruned,
repaired, or cleaned during collection.

Governing hosted baseline:

- master: `160bd10ee18cf6692352bcd65a3ae04277e8b313`
- tree: `4a2d8a7ab6a733c3961d92a2b78bd35f86314fa8`
- active ruleset: `20601214`

## Disposition classes

| Class | Meaning |
|---|---|
| `PRESERVE_ROOT` | Existing Repository Root; only the separately authorized cutover transaction may reparent it. |
| `PRESERVE_PROJECT_CONTAINER` | Current project-container directory; this inventory does not authorize moving or changing it. |
| `PRESERVE_ACTIVE_DIRTY` | Active or dirty worktree; no move, removal, or pointer change before owner review. |
| `PRESERVE_CLOSURE_EVIDENCE` | Historical Issue #38 evidence worktree retained until a later closure disposition. |
| `PRESERVE_LOCKED` | Git reports the worktree locked; do not unlock or mutate it in this task. |
| `REVIEW_CONTAINER_WORKTREES` | Existing embedded `.worktrees` checkout; review for the future `Worktrees` zone. |
| `REVIEW_EXTERNAL_WORKTREE` | Clean registered external checkout; compare branch purpose and hosted relation before migrate/retire selection. |
| `PRESERVE_UNREGISTERED_GIT` | Git checkout/repository not registered in the current common-dir roster; retain for ownership and origin review. |
| `PRESERVE_ROLLBACK_RESOURCE` | Runtime or environment rollback resource; retain until post-migration verification and separate cleanup approval. |
| `PRESERVE_LEGACY_DATA_UNREAD` | Possible legacy data location; do not inspect or move without a separate data authorization. |
| `DISPOSE_SYNTHETIC_AFTER_PROOF` | Synthetic residue candidate; removal requires exact-target proof and separate approval. |
| `UNRESOLVED_PRESERVE` | Classification cannot be safely narrowed from content-free metadata alone. |
| `OUT_OF_SCOPE_PRESERVE` | Top-level directory outside this repository migration; its contents were not inspected and no disposition is proposed. |

## `D:\` top-level findings

| Path | Observation | Class |
|---|---|---|
| `D:\$RECYCLE.BIN` | System directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\aDrive` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\BaiduNetdisk` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\BaiduNetdiskDownload` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\bililive` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Config.Msi` | System directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\DRIVE DOWNLOAD` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\e38v` | Registered detached worktree at `9f736f2e4e367c6e9f4c90e9073a8d37fc572240`; six status entries. | `PRESERVE_ACTIVE_DIRTY` |
| `D:\FFOutput` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Gihosoft` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\IQIYI Video` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\issue57-approved-python-source-8cspm3bc` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\issue57-approved-python-source-9m7zbbek` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\issue57-approved-python-source-aa5azj9x` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\issue57-approved-python-source-mjfbfdww` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\issue57-approved-python-source-ptmzs8ju` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\issue57-approved-python-source-trrlgldc` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\issue57-approved-python-source-xx0m0e2j` | Unregistered Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\Macrowing` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\NetEase` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\obs-studio` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Overwolf` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Projects` | Current project-container directory; its top-level children are reconciled separately below. | `PRESERVE_PROJECT_CONTAINER` |
| `D:\Rocq-Platform~9.0~2025.08` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\System Volume Information` | System directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\taobao` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Tencent` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Thunder Network` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\WeSing` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\WeSingCache` | Unrelated top-level directory; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |

Drive-root pass condition after separately authorized disposition:
`issue57-approved-python-source-*` count equals zero and no replacement appears
during the fixed focused/full test commands.

## Registered worktree roster

Git reported 33 registered worktrees. `status` is the count from
`git status --short`; it does not expose changed path names. `relation` is the
GitHub compare relationship from hosted master to the recorded HEAD; `404`
means that exact object was not available through the hosted compare API.

| # | Path | HEAD | Branch | Status | Lock | Relation | Class |
|---:|---|---|---|---:|---|---|---|
| 1 | `D:/Projects/email_ai_assistant` | `f0717816` | `master` | 0 | no | diverged | `PRESERVE_ROOT` |
| 2 | `C:/Users/33506/.codex/worktrees/55fd/email_ai_assistant` | `f0717816` | `codex/issue-38-live-confirm` | 10 | no | diverged | `PRESERVE_ACTIVE_DIRTY` |
| 3 | `D:/e38v` | `9f736f2e` | detached | 6 | no | behind | `PRESERVE_ACTIVE_DIRTY` |
| 4 | `D:/Projects/email_ai_assistant/.worktrees/current-email-ui-preview` | `3e02b3dd` | `prototype/current-email-ui-preview` | 0 | no | 404 | `REVIEW_CONTAINER_WORKTREES` |
| 5 | `D:/Projects/email_ai_assistant/.worktrees/issue-23-action-console-shell` | `0c142c1c` | `agent/issue-23-action-console-shell` | 0 | no | 404 | `REVIEW_CONTAINER_WORKTREES` |
| 6 | `D:/Projects/email_ai_assistant/.worktrees/issue-23-master-integration` | `772a34de` | `codex/issue-23-master-integration` | 0 | no | behind | `REVIEW_CONTAINER_WORKTREES` |
| 7 | `D:/Projects/email_ai_assistant/.worktrees/issue-30-repository-placement` | `c241cb82` | `codex/issue-30-repository-placement` | 0 | no | diverged | `REVIEW_CONTAINER_WORKTREES` |
| 8 | `D:/Projects/email_ai_assistant/.worktrees/issue-31-standalone-verification` | `906e23c8` | `codex/issue-31-standalone-verification` | 0 | no | diverged | `REVIEW_CONTAINER_WORKTREES` |
| 9 | `D:/Projects/email_ai_assistant/.worktrees/issue-33-protected-private-stores` | `1d2af2ee` | `codex/issue-33-protected-private-stores` | 0 | no | diverged | `REVIEW_CONTAINER_WORKTREES` |
| 10 | `D:/Projects/email_ai_assistant/.worktrees/issue-34-container-audit` | `3110ba03` | `codex/issue-34-container-audit` | 0 | no | diverged | `REVIEW_CONTAINER_WORKTREES` |
| 11 | `D:/Projects/email_ai_assistant/.worktrees/issue-35-migration-evidence-package` | `85f179f5` | `codex/issue-35-migration-evidence-package` | 0 | no | diverged | `REVIEW_CONTAINER_WORKTREES` |
| 12 | `D:/Projects/email_ai_assistant/.worktrees/issue-54-migration-evidence-publication` | `8ab7ff9b` | `codex/issue-54-migration-evidence-publication` | 0 | no | diverged | `REVIEW_CONTAINER_WORKTREES` |
| 13 | `D:/Projects/email_ai_assistant_issue38_maintenance_evidence_fix_9f736f2e` | `5c1f77c6` | `codex/pre-freeze-topology-reconciliation` | 5 | no | behind | `PRESERVE_ACTIVE_DIRTY` |
| 14 | `D:/Projects/email_ai_assistant_issue38_r2_final_master_review_7a97afb5` | `7a97afb5` | detached | 0 | no | behind | `PRESERVE_CLOSURE_EVIDENCE` |
| 15 | `D:/Projects/email_ai_assistant_issue38_r2_solo_prepare_9f736f2e` | `9f736f2e` | detached | 0 | no | behind | `PRESERVE_CLOSURE_EVIDENCE` |
| 16 | `D:/Projects/email_ai_assistant_issue38_r2_solo_prepare_lf_9f736f2e` | `9f736f2e` | detached | 0 | no | behind | `PRESERVE_CLOSURE_EVIDENCE` |
| 17 | `D:/Projects/email_ai_assistant_issue_104_r2_adapter_binding` | `f2c79da4` | `codex/issue-104-r2-adapter-binding` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 18 | `D:/Projects/email_ai_assistant_issue_105_r2_external_artifacts` | `d6b1d44f` | `codex/issue-105-r2-external-artifacts` | 0 | no | behind | `REVIEW_EXTERNAL_WORKTREE` |
| 19 | `D:/Projects/email_ai_assistant_issue_110_solo_maintainer_closure` | `de95199b` | `codex/issue-110-solo-maintainer-closure` | 0 | no | behind | `REVIEW_EXTERNAL_WORKTREE` |
| 20 | `D:/Projects/email_ai_assistant_issue_32_managed_container_mode` | `219d2065` | `codex/issue-32-managed-container-mode` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 21 | `D:/Projects/email_ai_assistant_issue_33_guardrail_compatibility` | `b405d5a8` | `codex/r2-guardrail-reader-compatibility` | 1 | no | behind | `PRESERVE_ACTIVE_DIRTY` |
| 22 | `D:/Projects/email_ai_assistant_issue_36_reparenting_rehearsal` | `088f1208` | `codex/issue-36-reparenting-rehearsal` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 23 | `D:/Projects/email_ai_assistant_issue_37_runtime_localdata_rehearsal` | `fc9ddeab` | `codex/issue-37-runtime-localdata-rehearsal` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 24 | `D:/Projects/email_ai_assistant_issue_51_cutover_contracts` | `1f30ad24` | `codex/issue-51-cutover-contracts` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 25 | `D:/Projects/email_ai_assistant_issue_52_crash_safe_journal` | `388a9f13` | `codex/issue-52-crash-safe-journal` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 26 | `D:/Projects/email_ai_assistant_issue_53_real_host_preflight` | `0d98c090` | `codex/issue-53-real-host-preflight` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 27 | `D:/Projects/email_ai_assistant_issue_55_acl_filesystem` | `c43e320b` | `codex/issue-55-acl-filesystem` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 28 | `D:/Projects/email_ai_assistant_issue_56_repository_transaction` | `61910d0d` | `codex/issue-56-repository-transaction` | 0 | yes | diverged | `PRESERVE_LOCKED` |
| 29 | `D:/Projects/email_ai_assistant_issue_57_managed_activation` | `7b17e2f9` | `codex/issue-57-managed-activation` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 30 | `D:/Projects/email_ai_assistant_issue_58_activation_recovery` | `21519425` | `codex/issue-58-provider-disabled-recovery` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 31 | `D:/Projects/email_ai_assistant_issue_59_final_composition` | `39b7026a` | `codex/issue-59-final-composition` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 32 | `D:/Projects/email_ai_assistant_issues_70_83_r2_remediation` | `c94e3e21` | `codex/issues-70-83-r2-remediation` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |
| 33 | `D:/Projects/email_ai_assistant_issues_86_102_r2_closure` | `d5754d04` | `codex/issues-86-102-r2-closure` | 0 | no | diverged | `REVIEW_EXTERNAL_WORKTREE` |

The observed root status count is zero, although a prior protected baseline had
13 entries. This report records the drift without attributing, repairing, or
reconstructing it.

## `D:\Projects` top-level directories

There are 38 top-level directories, including the current Repository Root.
Twenty-one are registered external worktrees already listed in roster rows 13
through 33. The remaining seventeen are reconciled here. This union is the
complete top-level directory set; no name-based relevance filter was applied.

| Path | Observation | Class |
|---|---|---|
| `D:\Projects\email_ai_assistant` | Current registered Repository Root. | `PRESERVE_ROOT` |
| `D:\Projects\email_ai_assistant_issue_104_live_adapter_surface_fix_7615be47` | Clean linked-Git checkout not present in the current worktree registry. | `PRESERVE_UNREGISTERED_GIT` |
| `D:\Projects\email_ai_assistant_issue_104_post_merge_audit_7615be47` | Clean standalone Git repository at `7615be47`. | `PRESERVE_UNREGISTERED_GIT` |
| `D:\Projects\email_ai_assistant_r2_final_8f12b21a` | Clean standalone Git repository at `8f12b21a`. | `PRESERVE_UNREGISTERED_GIT` |
| `D:\Projects\email_ai_assistant_r2_provenance_yaml_fix` | Clean standalone Git repository at `7850713f`. | `PRESERVE_UNREGISTERED_GIT` |
| `D:\Projects\email_ai_assistant-runtime` | Pinned runtime resource. | `PRESERVE_ROLLBACK_RESOURCE` |
| `D:\Projects\email_ai_assistant-venv-py3126-backup-20260722` | Legacy venv backup. | `PRESERVE_ROLLBACK_RESOURCE` |
| `D:\Projects\email-ai-assistant` | Contains a possible legacy local-data location; content not inspected. | `PRESERVE_LEGACY_DATA_UNREAD` |
| `D:\Projects\financial_statement_analysis` | Separate project outside this migration; contents not inspected. | `OUT_OF_SCOPE_PRESERVE` |
| `D:\Projects\email_ai_assistant_r2_provenance_5eb3b452_testtmp` | Unregistered provenance verification residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\Projects\issue57-approved-python-source-ww11p5ww` | Issue #57 approved-source fixture residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\Projects\issue57-synthetic-pce62k38` | Issue #57 synthetic scenario residue. | `DISPOSE_SYNTHETIC_AFTER_PROOF` |
| `D:\Projects\issue105-dir-op-j8mjsuf7` | Issue #105 failure-site residue; exact provenance not yet bound. | `UNRESOLVED_PRESERVE` |
| `D:\Projects\issue105-fullguard2-i4xc43s8` | Issue #105 failure-site residue; exact provenance not yet bound. | `UNRESOLVED_PRESERVE` |
| `D:\Projects\issue105-postqueue-883xheee` | Issue #105 failure-site residue; exact provenance not yet bound. | `UNRESOLVED_PRESERVE` |
| `D:\Projects\issue105-selfacl-68edwlcu` | Issue #105 failure-site residue; exact provenance not yet bound. | `UNRESOLVED_PRESERVE` |
| `D:\Projects\tmpi5eb50sg` | Unregistered unknown temporary-looking directory; content not inspected. | `UNRESOLVED_PRESERVE` |

The twenty-one registered external worktree directories omitted from this table
are roster rows 13 through 33. Together, those twenty-one rows plus the seventeen
rows above account for all 38 `D:\Projects` top-level directories.

## Reconciliation totals

| Scope | Observed | Reconciled |
|---|---:|---:|
| `D:\` top-level directories | 30 | 30 |
| Registered worktrees | 33 | 33 |
| `D:\Projects` top-level directories | 38 | 38 |
| Dirty registered worktrees | 4 | 4 |
| Locked registered worktrees | 1 | 1 |
| Issue #57 fixture/synthetic residues | 9 | 9 |

## Required next gates

1. Publish the Issue #57 fixture-parent repair only after focused/full tests and
   dual review pass.
2. Refresh this inventory after publication; new residue or status drift stops
   disposition.
3. Review each `PRESERVE_ACTIVE_DIRTY`, `PRESERVE_LOCKED`,
   `PRESERVE_UNREGISTERED_GIT`, and `UNRESOLVED_PRESERVE` entry individually.
4. Present an exact move/unregister/remove plan and obtain a separate approval.
5. Only after topology stabilization may a new LF exact closure worktree and
   fresh Solo Maintainer `prepare` be created.
6. Issue #38 confirmation, verifier, fourteen review decisions, final closure,
   Issue #39, and real migration remain separate gates.
