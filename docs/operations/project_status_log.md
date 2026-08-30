---
last_update: 2026-08-29
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Project Status Log

> Agent-readable project progress snapshot. This is not a normal development log.
> Agent should read `AGENTS.md` and this file before starting non-trivial work.

## Snapshot

| Field | Value |
|---|---|
| Generated on | 2026-08-29 |
| Current stage | multimodal_current_email_offline_ready_live_pending |
| Git branch | codex/closure-evidence-rollover |
| Git HEAD reference | Run `git rev-parse --short HEAD` in this workspace |
| Working tree status | Run `git status --short --ignored` in this workspace |

## Project Summary

本项目是企业邮箱中的 AI 辅助窗口。正常产品只做“用户点击按钮后分析当前打开邮件”，不做全邮箱扫描、不自动发送邮件、不删除邮件或归档邮件。

Separately authorized exception: the `administrator-only CLI remains default-off` and may import one authorized account within a rolling 24-month window only after explicit inventory fingerprint confirmation. The browser extension and normal runtime remain click-only and cannot scan a mailbox. The exception has no schedule, browser hook, normal-backend route, or automatic model call.

Issue #11 governed sales-corpus bootstrap is offline implemented. `scan` requires a separately stored strict private sales policy, binds only keyed metadata to a fresh corpus index, deduplicates cross-folder messages and attachment blobs, and exposes only fixed aggregate counts. Only an exact external-customer request to a strictly later allowlisted reply becomes a governed pair; unpaired records are rejected before downstream staging or reviewed attachment acquisition. No live mailbox, provider, or real private vault was used for this implementation.

ADR 0008 ratifies a future manual incremental-sync boundary and a contract-only, write-only deidentified current-click evidence seam. Issue #10 adds no sync command or evidence inbox; those implementations remain in future issues #17 and #18. Normal runtime receives no mailbox, historical-store, authority-store, reader, search, path, key, repository, polling, or hot-reload capability.

The private-knowledge snapshot is verified and read-only; an invalid or missing private-knowledge snapshot returns generic rule fallback. Tasks 1-7 of the multimodal current-email route are offline implemented and review-clean. The route is one OpenAI multimodal primary call, at most one eligible DeepSeek text-only fallback, and deterministic rules last; all providers remain disabled by default. Its budget tuple is `60/55/35/10/12/8/5` seconds: 60-second POST wait, 55-second backend target, 35-second OpenAI cap, 10-second DeepSeek cap, 12-second fallback minimum, 8-second parser cap, and 5-second reserve. Browser media discovery remains a separate 20-second resource collection phase. Private evaluation is blocked by `human_judge_unavailable` by default and does not switch production models.

Current-message attachment acquisition recognizes only a verified legacy current-message control after Analyze and keeps automatic bytes in browser memory. The manual picker selection is inert until Analyze. Both paths share 5 files, 10 MiB per file, and 25 MiB total, add no download/storage/filesystem permission, and expose no local path. Backend request-local files are removed from request `finally`; the 24-hour mtime cleanup is crash recovery only, not normal retention or a scheduled job. Only `attachment_insights[].status=parsed` proves content parsing.

Prior Task 9 synthetic and current-clicked smokes remain valid acquisition, routing, status, and cleanup evidence only. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. Current/history evidence alignment, provider-visible attachment coverage, deterministic reconciliation safeguards, and the documented private human gold-standard method now pass the offline gate; the reviewed repair is integrated into the current release line. Any new live operation still requires fresh explicit authorization. All providers remain disabled by default.

Issue #32 Managed launcher is implemented for the exact `email_ai_assistant\main` placement. It routes provider-disabled SQLite, attachment temp, logs, PID, runtime, artifact, worktree, and bounded non-secret Config paths to their approved zones while source and repository tooling remain at `main`. Synthetic loopback lifecycle verification passes, but no real Project Container migration or operational cutover has occurred.

Issue #34 manual content-free Container Audit is offline implemented behind seven injected read-only metadata adapters. Its exact nine-entry, ACL, volume, Git/worktree, runtime, SQLite, Config, Logs/Artifacts, and disabled-private-state contract fails closed and exposes only fixed status/counts. No real Container audit or host-security probe was run.

Issue #35 no-clobber migration evidence package is offline implemented as a manual internal Python contract. It binds exact reviewed local refs, branch-attached worktree identities, an allowlisted two-layer dirty-source snapshot, content-free Git/ACL/volume baselines, and every payload file with canonical SHA-256 evidence. Publication is external-target, create-only and fail-closed; verification restores Git objects, refs, dirty state and worktree identity in synthetic repositories. No real evidence package was created.

Issue #36 repository/worktree reparenting rehearsal is offline implemented as one pathless synthetic-only Python seam. It builds a temporary repository with a bound marker filesystem identity and a non-trivial Git baseline, creates and verifies one synthetic Issue #35 package, no-clobber moves the existing Git common directory and reviewed source into a synthetic `main`, applies injected repair/recreate worktree choices, verifies exact post-state and passes a synthetic ContainerAudit. All six publication-boundary failures verify rollback preservation; post-main failures preserve the complete Container at the single sibling rollback path. The public operation leaves the synthetic topology intact for independent caller observation. No real workspace, worktree, branch, directory, ACL, runtime, database or private data was touched; Issues #38 through #40 remain separate.

Issue #37 managed runtime and LocalData activation rehearsal is offline implemented behind exact five injected adapters and one pathless synthetic-only seam. Temporary synthetic sources prove a create-only pinned runtime, a Windows venv rebuilt from the exact dependency lock, `pre_publication` stopped-service create-only SQLite publication with identity/SHA-256/integrity/sidecar/count checks, reviewed-hash browser-extension publication, exact Managed writable roles, and one strict activation token across provider-disabled start, literal-loopback health, one persisted rule-fallback analysis and the same-service `post_activation` fresh-stop proof. Stale evidence and equality spoofing fail closed. The source database remains unchanged after success and every simulated race, reparse, existing-target, dependency, integrity or health failure. No real runtime, SQLite database, browser-extension artifact or migration evidence package was activated; Issues #38 through #40 remain separate.

Issue #51 locked Cutover Profile, authorization, and receipt contracts are offline implemented as a pure content-free Python contract layer. Immutable `CutoverProfileV1` values bind the reviewed cutover inputs without paths or host readers. The four distinct real-host authorization value types validate externally supplied canonical values and cannot create, issue, or mint authority. The strict canonical `ReceiptEnvelopeV1` values are duplicate/unknown rejecting, fingerprint-bound, and never accepted as authorization. `default_operator_entry()` remains fixed at `BLOCKED_NO_APPROVED_COMMAND`. Its approved consumers are the exact Issue #52 journal bridge, exact Issue #53 preflight contract bridge, exact Issue #54 evidence-publication contract bridge, exact Issue #55 mutation contract consumers, exact Issue #56 synthetic transaction scope consumers, exact Issue #57 synthetic managed-publication contract consumers, and exact Issue #58 synthetic lifecycle/real-lock consumers.

Issue #52 crash-safe journal and recovery classification are offline implemented in the pathless synthetic-only `backend.cutover_journal` package. Strict canonical create-only records bind sequence, previous/record hashes, fixed synthetic step/event/direction, operation/profile/authorization/owner fingerprints, and opaque observations. Every forward and reverse action uses durable `INTENT`, exact observed effect, and `COMMITTED`; each owner claim gets a distinct lease and each effect consumes a non-copyable, non-serializable single-use store permit bound to the exact active durable intent and durable journal head. The shared store-private issuance is atomically claimed; one synthetic medium operation gate serializes append, restart, permit mint/claim, and effect mutation; every namespace-published current head completes stable reread and full snapshot reverification before a successor append or permit. Stable-reread evidence is hash-bound, and head advance, pending state, or an observed fact invalidates stale permits. Pending or unbarriered records never authorize an effect; verified pending direction/event/outcome controls event-aware exact pending publication without effect replay or an extra action; durable observed facts are authoritative across fresh `RESUME_BOUND` renewal. Reverse steps are derived LIFO only from verified `COMMITTED/APPLIED` history. Exact Profile/master/operator, identity mapping, synthetic transition mapping, and post-effect observation all fail closed. Exact in-memory Windows/Linux traces prove file/namespace/stable-reread ordering without claiming real filesystem durability. Restart inspection is read-only, exact expected-post is never blindly repeated, and explicit resume/rollback fresh-validate phase-specific authorization including the pre-bound recovery fingerprint. Public results expose only fixed status, phase, receipt fingerprint, and allowlisted counts distinguishing `SAFE_ABORT`, `ROLLBACK_REQUIRED`, `INCIDENT_STOP`, and `CUTOVER_SUCCEEDED`. No real filesystem target, service, ACL, Git repository/worktree, Runtime, SQLite, provider, mailbox, vault, private data, preflight, migration, cutover, resume, or rollback was accessed or run; Issues #57 through #59 remain separate.

Issue #53 content-free Windows real-host preflight composition is offline implemented in `backend.real_host_preflight`. The package-private Windows observer opens every controlled path component without following reparse points and binds fixed-volume identity, 128-bit file identity, object type, parent identity, normalized-name fingerprint, attributes, reparse metadata, and exactly-one-link file alias evidence. Only exact, unexpired `TestSandboxAuthorizationV1` values plus a root/marker identity-bound atomically single-use permit can create test-owned temporary scopes; every observer operation reopens and validates the exact root and marker and holds both handle chains through the target observation, and no real project path was observed. `CurrentTopologyPreflight` captures an independent canonical Profile snapshot before any host callback, factory-reconstructs every callback value, binds source/parent/finance/target names to exact snapshot role selections, and requires two complete identical seven-reader observations. `PreMutationGate` is short-lived, UUIDv4 nonce-bound, single-operation and single-use; each topology receipt can be atomically claimed by at most one gate, and trusted receipt/gate state is module-owned with an exact nominal-class-to-observation-kind binding. `RealHostBaselineCollector` keeps source, parent, finance, volume, operator-SID, and three ACL roles separate while projecting the existing canonical `HostBaseline`. The unchanged nine-zone `ContainerAudit` receives exactly seven revalidated callbacks through a narrow bridge; final-audit readiness validates the identical bound readers without running or claiming a final-layout audit, and each execution uses a detached canonical policy plus freshly rebuilt adapters so callback-time mutation cannot relax policy or retarget readers. The zero-argument operator entry remains fixed at `BLOCKED_NO_APPROVED_COMMAND` and cannot accept test authorization. Production code has no service-control, ACL-apply, rename, worktree mutation, Runtime build, database copy, artifact, Config, provider, mailbox, vault, private-data, or content-reading capability. Windows behavior was exercised only in test-owned temporary sandboxes, and portable tests make no NTFS or Windows ACL claim. Issues #56 through #59, Issues #38/#39, and parent Spec #50 remain separate and unchanged.

Issue #54 reviewed Migration Evidence publication and verification is present for synthetic-only use in `backend.migration_evidence_publication` and `backend.migration_evidence_verifier`. Profile-bound review keeps the complete `MigrationEvidenceReview` in memory and exposes only `MigrationEvidenceReviewReceiptV1`; its test-only target-parent marker hard-link anchor rejects same-path replacement even when POSIX recycles directory identity. Create requires the exact `EvidencePublicationAuthorizationV1` and confirmed review fingerprint, then performs complete rediscovery and fresh HostBaseline collection before the existing create-only no-clobber commit; creator-owned source-snapshot, package, manifest, and published-identity bindings reject post-review or post-commit replacement. The creator cannot call the independent verifier. Verification runs in a separate read-only process, reads the package once through a bounded descriptor, verifies those exact bytes through the independent payload verifier, requires an identical target reread, and independently recomputes package/manifest hashes and counts without publication or mutation capability. `MigrationEvidenceReviewReceiptV1`, `MigrationEvidenceCreatedReceiptV1`, and `MigrationEvidenceVerifiedReceiptV1` must agree exactly before `MigrationEvidenceReceiptSetV1` can exist; receipts and the Set remain content-free evidence rather than authority. All real entries remain locked before Issue #39 and reject missing, wrong-phase, and test authorization. No real evidence package was created, and no host preflight, service, repository/worktree move, ACL, Runtime, database, provider, mailbox, vault, private-store, or private-data operation was run. The package is evidence, not a backup, Runtime artifact, private-data container, or migration authorization. Focused, affected, constraint, full-suite, maintenance, Standards, and Spec verification passed locally. Ready-for-review PR #63 already exists; the Linux inode-reuse repair still requires explicit allowlist stage, commit, and push before remote CI reruns, and merge remains unauthorized.

Issue #55 fixed-role Windows ACL and no-clobber filesystem primitives are offline implemented in `backend.cutover_host_mutation`. The public surface contains only closed portable ACL/filesystem observations and four content-free receipt types. The internal `WindowsAclAdapter` performs complete read-only source compatibility without reparse traversal, exact parent/finance capture-and-compare, and exact inheritance verification across eight fixed direct zones. The newly created empty Container is published by parent-handle-relative `NtCreateFile` with `FILE_CREATE` and a protected operator-only construction DACL that grants no child-creation right; root, marker, parent, and target handles remain held until the journaled final DACL linearization point. The final DACL grants inheritable Full Control only to the current token SID, SYSTEM, and built-in Administrators; owner/group are compared unchanged and the exact `SetSecurityInfo` call omits all owner/group/SACL flags and pointers. Create-only directory, file publication, and same-identity move effects require a durable Issue #52 INTENT, bind opened scope/source/parent handles, fixed NTFS volume, 128-bit file ID, parent identity and reparse-free state, set no-replace, and prove identical target identity. Native tests ran only in caller-owned temporary NTFS sandboxes; portable Linux tests claim no Windows ACL or NTFS behavior. The real constructor rejects test authorization and remains locked at `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. No real ACL, repository/worktree, service, Runtime, SQLite, provider, mailbox, vault, private store, or private data was accessed or changed. Issues #56 through #59, Issues #38/#39, and parent Spec #50 remain separate.

Issue #56 reversible mixed-topology repository/worktree transaction is offline implemented in `backend.cutover_repository_transaction`. A caller-owned temporary Windows sandbox binds the original Repository Root plus exactly eight embedded and three external clean reviewed worktrees, their refs/commits/common-directory identity, opened Git executable identity/version/content, physical identities, and opaque administrative entries. The fixed scope-bound Git runner denies executable write/delete sharing, revalidates executable content/identity in the same handle window before and after every allowlisted process, rejects unsafe local config at scope bind/rebind and unexpected administrative namespaces, suppresses repository hooks, bounds process-tree lifetime and output, and exposes no arbitrary command seam. Forward durably journals INTENT before each #55 no-replace or fixed Git effect, preserves every original physical/admin object before counterpart creation, relocates the original Repository Root identity to `main`, publishes the exact non-main zones create-only, recreates all eleven reviewed counterparts, and records the actual #55 object identity or Git observation in OBSERVED. COMMITTED requires an independent exact reread: filesystem targets are held against write/delete sharing, administrative values also bind opaque content, and Git values repeat relationship/ref/commit/clean-state verification. The journaled Container-create identity is the unchanged ContainerAudit trusted policy selection and must equal the freshly observed Container object; the three external worktrees remain under separate exact Git verification, and final Git verification rejects non-intentional local-ref or remote-configuration drift. Reverse accepts every complete forward boundary and safely classified forward crash gap; exact before-effect state appends `ABORTED/NOT_APPLIED`, exact after-effect state appends only missing facts without replay, and any published new state is retained before the original Repository Root, all eleven original administrative identities, and all eleven original physical identities are restored. Crash-gap classification remains exact `SAFE_ABORT`, `SAFE_COMMIT_FACTS`, or `INCIDENT_STOP`. An explicitly repeated reverse call derives the exact committed-stage plan, classifies and reconciles each safe reverse INTENT/effect/OBSERVED/COMMITTED crash gap, validates complete journal-bound failed evidence before any resumed mutation, validates the exact checkpoint, and continues only the remaining fixed mutations; the failed Container must retain the journaled Container identity. Ambiguity remains `INCIDENT_STOP`, and there is no background or implicit resume. Collision, after-INTENT target race, OBSERVED-to-COMMITTED drift, reparse, volume/scope, ref, remote, dirty, executable content/identity, physical, same-name admin reuse, unsafe Git config/hook, observation, zone-inventory, administrative-namespace, and topology drift fail closed. Journal, receipts, repr, stdout, and stderr are content-free. The real constructor remains `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. No real repository/worktree, service, ACL, Runtime, SQLite, provider, mailbox, vault, private store, or private data was accessed or changed. Issues #57 through #59, Issues #38/#39, and parent Spec #50 remain separate.

Issue #57 managed Runtime, LocalData, CRX, and Config publication is offline implemented in `backend.cutover_managed_activation`. `ManagedActivationPhase` composes exactly four narrow adapters, validates each receipt before the next callback, and returns one fingerprinted set that independently rebuilds all four complete typed receipt mappings and their common operation/Profile/master/authorization chain. Immutable scope snapshots bind every target name and hold root, marker, and target-parent handles; target creation is parent-handle-relative `NtCreateFile(FILE_CREATE)`, unsafe Windows components including ADS and superscript reserved-device syntax are rejected, and held file targets deny concurrent writers through final verification. The test harness materializes the approved Python distribution inside each caller-owned sandbox, and external source paths fail. A canonical manifest binds the complete CPython source tree, entry count, total bytes, executable hash, and tree fingerprint. Before target execution, every source entry is resource/reparse/ADS checked, held against write/delete sharing, and recursively monitored through verification. The approved distribution is streamed from held handles into an empty create-only Runtime root, so post-authorization additions to the mutable source namespace, including `_pth` startup paths, are never executed. The complete approved `Lib/encodings` package is streamed from held source handles into bounded deterministic ZIP_STORED `managed-startup.zip`; code-fixed create-only `python312._pth` and `python._pth` sentinels put that immutable archive before `Lib`/`DLLs`, omit `import site`, and remain held before target execution, preventing both pre-script encoding-package injection and later startup hooks. `LockedRuntimeBuilder` creates a fresh Runtime from that exact approved Python 3.12.13 source, a canonical lock enumerating the complete installed closure, and captured bytes from a hash-locked offline wheelhouse. It copies no prior venv, rejects `.pth`/`sitecustomize.py`/`usercustomize.py`, and has no PATH lookup, pip/index/network access, user-site, user cache, or live dependency resolution. Held-handle and remaining-aggregate gates precede source/wheel/lock allocation. Fixed wheel/archive/Runtime resource ceilings, pre-`ZipFile` central-directory bounds, expected-count wheelhouse and pre-sort tree enumeration bounds, and bounded streaming extraction, hashing, and subprocess stdout prevent unbounded allocation, buffering, or disk growth; stdout overflow terminates the child. A held exact Runtime tree binds the streamed CPython baseline plus every child-handle-relative wheel/lock addition and rejects junction/reparse, ADS, extra, missing, or changed entries. A recursive directory-change guard on the Runtime parent spans sealing, self-verification, and receipt construction; transient child or Runtime-root stream mutation yields no receipt. Under fixed `-X frozen_modules=on -I -B -S`, the new Runtime verifier imports only built-in `sys`, `nt`, `_sha2`, and `_imp`, proves `_imp.is_frozen("codecs")`, and rejects every later import; transient `Lib/codecs/__init__.py` cannot execute before the hook. It proves Python, SQLite, startup-ZIP, dependency-lock, exact installed-set, and import fingerprints from exact target bytes and bounded metadata; SQLite binary hashes are compared with the held approved source entries, so transient target packages cannot execute. `StoppedDatabaseCopier` requires an exact stopped-service receipt, holds a write-blocking source handle through copy and verification, rejects any WAL, SHM, or rollback journal before copy and again after final target verification, uses read-only/query-only integrity verification without application-row inspection, durably flushes a create-only destination, and requires an unchanged source identity and stable hash. The artifact publisher holds the source and target through receipt construction and a final exact reread, copies only one profile-bound reviewed CRX after exact format/size/hash validation, and cannot build, sign, install, load, or inspect a browser profile. The Config publisher emits deterministic non-secret Config canonical bytes from a closed allowlisted schema without environment, registry, credential-store, clipboard, hidden-input, mailbox, vault, or provider readers. Every collision, drift, or failure fails closed, and any partial or failed publication remains in place. Receipts, stdout, stderr, and errors are content-free. Each real constructor rejects missing or test authorization and remains `BLOCKED_NO_APPROVED_COMMAND` even after exact `CutoverExecutionAuthorizationV1` validation before Issue #39. No real Runtime, SQLite, CRX, Config, service, browser, repository/worktree, ACL, provider, mailbox, credential, vault, private store, or private data was accessed or changed. Issues #58/#59, Issues #38/#39, and parent Spec #50 remain separate.

Issue #58 provider-disabled activation and legacy recovery is offline implemented in `backend.cutover_service_lifecycle`. `ProviderDisabledServiceController` accepts only exact injected new-service and legacy-service role adapters. New activation validates the complete Issue #57 operation/Profile/master/authorization receipt chain, uses the reviewed managed Runtime and deterministic Config, forbids legacy-environment inheritance, keeps both providers disabled, and binds every start to a fresh UUIDv4 nonce. Health must match PID, start time, executable, port ownership, Profile, `LocalData` role, nonce, and provider-disabled state. The only activation input is one code-fixed synthetic request; acceptance requires a deterministic-rules result, exactly zero provider attempts, and exactly one matching synthetic row in the new `LocalData`. Known pre-mutation start rejection becomes `SAFE_ABORT` without containment or rollback. Known post-mutation validation failures become `ROLLBACK_REQUIRED`, while identity, journal, reparse, provider-boundary, safety, or unexpected post-start ambiguity becomes `INCIDENT_STOP` after exact containment. Rollback requires explicit synthetic authorization and an immutable plan binding the complete committed journal entries, original topology, ACL descriptors, database/sidecar state, legacy Runtime, and repository identity. Every fixed reverse stage chains the previous observation or receipt, restoration binds the actual #56 reverse receipt, and the transaction retains the failed Container, new external worktrees, and Git administrative evidence while proving restoration of the original main plus all eleven worktrees. Windows synthetic proof resumes every committed reverse boundary and rejects a pre-existing failed-Container collision. Legacy recovery uses a dedicated injected provider-disabled Config, a distinct fresh recovery nonce, no environment reader, and no synthetic analysis; failure is fixed as `INCIDENT_STOP_LEGACY_SERVICE_RECOVERY_FAILED` with no retry, alternate launcher, or Config. Public receipts, journal bindings, stdout, stderr, and errors remain content-free. Real construction requires exact external cutover and recovery authorizations and still returns `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. No real service, repository/worktree, ACL, Runtime, SQLite, browser, mailbox, provider, credential, vault, private data, or host state was accessed or changed. Issue #59, Issues #38/#39, merge, and parent Spec #50 remain separate.

Issue #59 final Project Container composition is offline implemented across `backend.real_host_preflight_composition`, `backend.migration_evidence_publication_composition`, `backend.cutover_transaction_composition`, and the pure `backend.cutover_composition_contracts`. The three operator roots are physically separate, mutually non-importing, and accept only exact binding-bound nominal role bundles. Mechanical guards keep them out of normal runtime, browser, scripts, cleanup, scheduler, and workflows and reject arbitrary source, target, worktree, Runtime, database, artifact, Config, ACL, rollback, shell, PowerShell, or Git command inputs. Backend packages expose no executable test binder; test-only assembly requires an internally created temporary scope with no root-selection input, owns every component `TemporaryDirectory`, and rechecks it before every role or journal callback. Every real constructor and entry validates its exact phase authorization, rejects synthetic/test authorization, and still returns `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. `ProjectContainerReceiptChainV1` binds one operation, Profile, governing master, operator, authorization sequence, review, package verification, ACL baseline, fresh pre-mutation gate, one journal owner, linked prior/current journal heads, terminal receipt, activation, final audit, failed-Container preservation, rollback restoration, legacy health, and terminal recovery state. Every partial chain is an approved prefix, and its fingerprint commits its ordered recursively linked terminal receipt. Execute, resume, and rollback are single-action; the owner atomically claims the gate across composition objects, supplies the per-boundary authorization clock, and fail-closes receipt, predecessor, binding, freshness, journal, or state drift. Windows end-to-end proof composes the existing #53-#58 seams only in caller-owned temporary sandboxes, routes the forward ACL-through-activation path through transaction `execute()`, binds the #55 ACL policy receipt into the #56 Profile, uses the actual #56 journal, passes the exact #57 receipt set into #58, and reaches exact legacy recovery after failed activation with zero provider attempts; no substitute publication receipts are created. Portable/Linux tests make no NTFS or Windows ACL claim. No real preflight, evidence package, ACL, repository/worktree, Runtime, SQLite, CRX/Config, service, activation, rollback, provider, mailbox, vault, private store, or private-data operation occurred. Issue #38 remains open/ready-for-human, R1 remains `NOT EXECUTABLE`, and Issue #39 remains unstarted. Merging #59 changes the governing master, invalidates old R1, and requires all fourteen #38 approval items plus a new R2 against the exact final master before #39 can be considered.

Issues #70-#83 dormant R2 cutover remediation are offline implemented across the additive R2 contract, fixed preflight/evidence/transaction process, main/manifest/database/Runtime/CRX/Config publication, independent-audit, validation-lifecycle, cross-stage recovery, and verification-evidence packages. The fixed no-argument `scripts/verify_r2_synthetic_topology.py` owns one fresh physical NTFS sandbox and composes preflight, evidence, quiescence, legacy anchor, nine-zone Container/main/whole-tree ACL, one repository, all eleven reviewed worktrees, four managed units, Start A with one `rule_fallback` result and one row, stop, independent stopped audit, Start B without analysis/write, independent final-running audit, and one terminal `CUTOVER_SUCCESS`. Preflight, evidence, and transaction use distinct real local TTY processes; execution and recovery remain distinct fixed verbs and all four authorization domains are nominally separate. The exact seven-semantics, two-directions, five-gaps matrix covers 70 fresh scopes. Obsolete batched managed publication, stale R1 verification, in-process operator substitution, self-certified audit, and legacy R2 success are mechanically unreachable. Fresh criteria, matrix, script, bundle, complete R2 surface, and package fingerprints are recorded as six deterministic evidence fingerprints; the accepted prototype fingerprint remains non-authorizing prior art. Portable tests make no NTFS, ACL, TTY, process-isolation, or native-durability claim. Every real entry remains `BLOCKED_NO_APPROVED_COMMAND`; no real host, provider, mailbox, vault, private data, or Issue #39 operation was accessed or run, and #38/#50/#39 remain unchanged.

Issue #104 three-stateful-Adapter seam remains implemented offline in `backend.r2_production_composition`. The catalog retains three exact stateful Adapter slots covering six preflight commands, one evidence command, and three transaction commands. Binding captures and immediately reverifies command/domain, nominal type, complete owning-module source, class surface, registry and target identity; mutable instance state remains excluded. Underlying receipt/outcome validation still precedes completion. Issue #110 replaces candidate key/signature/envelope inputs with the exact Solo Maintainer final-master binding and closed `ApprovedCutoverBindingV3` structural facts. Synthetic Adapters remain testing-only, while every production root stops at `DORMANT_NO_ISSUE39_APPROVAL` before Adapter lookup. No real Adapter or host operation is created, and #38/#39 remain unchanged.

Issue #110 Solo Maintainer Closure is implemented in `backend.r2_solo_maintainer_closure`, `backend.r2_production_binding`, and `scripts/close_r2_final_master.py`. The strict two-file trust model binds one frozen clean master, the five exact GitHub Actions hosted checks, fourteen evidence records, eight ordered gap proofs, one exact active master-ruleset snapshot, one canonical manifest, and one Solo Maintainer Attestation with assurance counts one operator and zero independent/external/hosted-human reviewers. Private typed local proofs bind canonical values, relevant frozen blobs, same-SHA hosted records/job steps, and fresh status/maintenance/leakage observations without claiming durable runtime receipt instances. `ApprovedCutoverBindingV3` removes V2 public keys, signatures, envelopes, and issuers; execution confirmation binds closure, attestation, exact action/journal/plan/TTY/time facts and a create-only durable claim, but remains unreachable from production. The legacy final-master/global-gate/external-artifact/signature paths are removed rather than retained as aliases. GitHub ruleset `20601214` exists for `master`, and the private guardrail reader observes it through authenticated fixed GET-only GitHub CLI calls backed by the active keyring login; Python neither reads nor prints the token. The compatibility layer accepts the additive beta `required_reviewers=[]` response shape and the absent-or-exact-true `require_extra_approval_for_unattributed_changes` default only at exact integer zero approving reviews. It removes only those approved wire values before canonical comparison; missing or non-empty bypass actors, false or wrongly typed defaults, Boolean or nonzero approval counts, and every other drift fail closed. No live `prepare`, `confirm`, or protected verifier was run or authorized by this local compatibility work, and #38/#39 remain unchanged. Closure and CI evidence do not approve Issue #38, create or approve a ruleset, authorize or execute Issue #39, mutate a real host, access provider/mailbox/vault/private data, clean retained stages, push, or merge.

Historical closure evidence rollover is implemented in the independent five-file `backend.r2_closure_evidence_rollover` package and fixed `scripts/rollover_r2_solo_maintainer_closure.py run` entry. Its parameterless coordinator creates one canonical 300-second single-use candidate bound to a clean exact current master, a strict historical-ancestor closure, exact manifest/receipt bytes and candidate linkage, Windows file/stream/DACL identities, separately bound Git-common parent identity/DACL, and one deterministic absent historical target. Wall and private monotonic clocks enforce the half-open window at entry and commit. Execution rederives the complete state before the native commit boundary, reads bytes through writer-excluding handles, retains a pending source-directory oplock across the child-handle release required by Windows, verifies the candidate-bound parent handle, and performs only a same-parent, same-volume, no-replace directory rename while preserving bytes, identities, and DACL. It has no caller path/ref/repository/command, copy, delete, overwrite, repair, cleanup, pathname rollback, Issue #38 approval, execution authority, or Issue #39 authority. Automated verification uses only test-owned temporary evidence and never reads or moves the real Git-common closure. No live rollover was run by this implementation work.

Issue #39 one-command Project Container orchestration is implemented in `backend.r2_issue39_orchestrator` and `scripts/execute_project_container_cutover.py`. Its governed code allowlist permits only that fixed composition root, the fixed script, and the package-owned retained restart runner; the three historical standalone preflight/evidence/transaction roots remain `DORMANT_NO_ISSUE39_APPROVAL`. The initial wrapper now accepts only the code-fixed registered `issue39-governed-enablement` launcher worktree and rejects the legacy root, alternate/copy/reparse launchers before importing the orchestrator. Its production order is zero-mutation closure/Issue #38/input/complete dynamic-roster readiness, fixed real-console confirmation, exact incident disposition, fresh complete prepare, create-only evidence plus retained-anchor transfer, and a dynamic closed catalog. The portable six-worktree synthetic baseline remains 27 actions/24 host effects; a 2026-08-29 read-only live observation found 14 linked worktrees, which would derive 35/32 if unchanged, but fresh prepare is authoritative. Every preflight, evidence/bootstrap, catalog, recovery and terminal V3 confirmation first displays one strict content-free bound action-context line, followed by the existing fresh candidate and fixed acknowledgement. Every host effect uses a fresh action-bound durable claim and journaled intent; restart classifies two stable observations without replaying an already-present effect, while rollback retains failed state. Terminal success requires a journal-reconstructed ordered validation receipt and two fresh full audits of layout, roster, Git, ACL, managed units, provider-disabled service identity, and the single deterministic rule-fallback row. Code enablement, tests, CI, and merge are implementation evidence only. This repair has not executed real incident disposition, evidence publication, cutover, resume or rollback; real execution still requires a separate final authorization.

The selected daily frontend remains the Tencent Exmail Chrome / Edge 浏览器扩展, with current-message collection only after an explicit user click.

## Guardrails Established

| File | Exists |
|---|---|
| `Project entry rules: AGENTS.md` | yes |
| `Tooling constraints: docs/constraints/tooling_constraints.md` | yes |
| `Architecture constraints: docs/constraints/architecture_constraints.md` | yes |
| `Static linter constraints: docs/constraints/linter_constraints.md` | yes |
| `Mechanical rule translation: docs/constraints/mechanical_rule_translation.md` | yes |
| `CI guardrails: .github/workflows/agent_guardrails.yml` | yes |
| `Cleanup automation: docs/operations/cleanup_agent_codex.md` | yes |
| `Maintenance scan: scripts/maintenance_scan.py` | yes |
| `Repository leakage scan: scripts/repository_leakage_scan.py` | yes |
| `Agent task brief: docs/templates/agent_task_brief_template.md` | yes |
| `Authorized mailbox ingest boundary: docs/operations/authorized_mailbox_ingest_task_brief.md` | yes |
| `Bounded corpus-to-runtime handoffs: docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md` | yes |
| `Governed sales corpus bootstrap: docs/operations/issue11_governed_sales_corpus_task_brief.md` | yes |
| `No-clobber migration evidence package: docs/operations/issue35_migration_evidence_package_task_brief.md` | yes |
| `Synthetic repository reparenting rehearsal: docs/operations/issue36_reparenting_rehearsal_task_brief.md` | yes |
| `Synthetic Managed runtime activation rehearsal: docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md` | yes |
| `Locked cutover contracts: docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md` | yes |
| `Synthetic crash-safe journal and recovery classification: docs/operations/issue52_crash_safe_journal_recovery_task_brief.md` | yes |
| `Content-free Windows real-host preflight composition: docs/operations/issue53_windows_real_host_preflight_task_brief.md` | yes |
| `Reviewed Migration Evidence publication and verification: docs/operations/issue54_migration_evidence_publication_task_brief.md` | yes |
| `Fixed-role Windows ACL and no-clobber primitives: docs/operations/issue55_windows_acl_filesystem_primitives_task_brief.md` | yes |
| `Reversible mixed-topology repository transaction: docs/operations/issue56_repository_worktree_transaction_task_brief.md` | yes |
| `Create-only managed activation publication: docs/operations/issue57_managed_activation_publication_task_brief.md` | yes |
| `Provider-disabled activation and legacy recovery transaction: docs/operations/issue58_provider_disabled_activation_recovery_task_brief.md` | yes |
| `Project Container cutover contract security boundary: docs/security/project_container_cutover_contracts.md` | yes |
| `R2 production Adapter binding remediation: docs/operations/r2_production_adapter_binding_remediation_task_brief.md` | yes |
| `R2 Solo Maintainer Closure boundary: docs/operations/r2_solo_maintainer_closure_task_brief.md` | yes |
| `R2 Solo Maintainer Closure operator sequence: docs/operations/r2_solo_maintainer_closure_runbook.md` | yes |
| `R2 historical closure evidence rollover boundary: docs/operations/r2_closure_evidence_rollover_task_brief.md` | yes |
| `R2 GitHub unattributed-approval compatibility: docs/operations/r2_github_guardrail_unattributed_approval_compatibility_task_brief.md` | yes |
| `Solo Maintainer Closure and execution-confirmation decision: docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md` | yes |

## Key File Status

| File | Exists |
|---|---|
| `AGENTS.md` | yes |
| `README.md` | yes |
| `.env.example` | yes |
| `requirements.txt` | yes |
| `.gitignore` | yes |
| `.github/workflows/agent_guardrails.yml` | yes |
| `.github/workflows/cleanup_agent.yml` | yes |
| `backend/current_evidence/__init__.py` | yes |
| `backend/current_evidence/artifact_policy.py` | yes |
| `backend/current_evidence/contract.py` | yes |
| `backend/current_evidence/handoff.py` | yes |
| `backend/r2_production_binding/_adapter_identity.py` | yes |
| `backend/r2_production_binding/__init__.py` | yes |
| `backend/r2_production_composition/__init__.py` | yes |
| `backend/r2_production_composition/adapter_binding.py` | yes |
| `backend/r2_production_composition/catalog.py` | yes |
| `backend/r2_production_composition/preflight.py` | yes |
| `backend/r2_production_composition/evidence.py` | yes |
| `backend/r2_production_composition/transaction.py` | yes |
| `backend/r2_production_composition/binding_candidate.py` | yes |
| `docs/operations/r2_production_adapter_binding_remediation_task_brief.md` | yes |
| `backend/r2_solo_maintainer_closure/__init__.py` | yes |
| `backend/r2_solo_maintainer_closure/_canonical.py` | yes |
| `backend/r2_solo_maintainer_closure/contracts.py` | yes |
| `backend/r2_solo_maintainer_closure/evidence.py` | yes |
| `backend/r2_solo_maintainer_closure/hosted_evidence.py` | yes |
| `backend/r2_solo_maintainer_closure/local_evidence.py` | yes |
| `backend/r2_solo_maintainer_closure/repository.py` | yes |
| `backend/r2_solo_maintainer_closure/github_guardrail.py` | yes |
| `backend/r2_solo_maintainer_closure/storage.py` | yes |
| `backend/r2_solo_maintainer_closure/closure.py` | yes |
| `backend/r2_production_binding/execution_confirmation.py` | yes |
| `scripts/close_r2_final_master.py` | yes |
| `scripts/verify_r2_final_master_closure.py` | yes |
| `tests/test_r2_solo_maintainer_closure.py` | yes |
| `tests/test_r2_solo_maintainer_github_guardrail.py` | yes |
| `tests/test_r2_solo_maintainer_closure_architecture.py` | yes |
| `tests/test_close_r2_final_master.py` | yes |
| `tests/test_r2_execution_confirmation.py` | yes |
| `tests/test_r2_execution_confirmation_architecture.py` | yes |
| `docs/operations/r2_solo_maintainer_closure_task_brief.md` | yes |
| `docs/operations/r2_github_guardrail_response_compatibility_task_brief.md` | yes |
| `docs/operations/r2_github_guardrail_unattributed_approval_compatibility_task_brief.md` | yes |
| `docs/operations/r2_solo_maintainer_closure_runbook.md` | yes |
| `docs/decisions/0010-solo-maintainer-closure-and-execution-confirmation.md` | yes |
| `docs/decisions/0011-authenticated-github-guardrail-observation.md` | yes |
| `backend/r2_closure_evidence_rollover/__init__.py` | yes |
| `backend/r2_closure_evidence_rollover/contracts.py` | yes |
| `backend/r2_closure_evidence_rollover/repository.py` | yes |
| `backend/r2_closure_evidence_rollover/storage.py` | yes |
| `backend/r2_closure_evidence_rollover/rollover.py` | yes |
| `scripts/rollover_r2_solo_maintainer_closure.py` | yes |
| `tests/test_r2_closure_evidence_rollover.py` | yes |
| `tests/test_r2_closure_evidence_rollover_architecture.py` | yes |
| `docs/operations/r2_closure_evidence_rollover_task_brief.md` | yes |
| `backend/cutover_contracts/__init__.py` | yes |
| `backend/cutover_contracts/_canonical.py` | yes |
| `backend/cutover_contracts/authorization.py` | yes |
| `backend/cutover_contracts/authorization_schema.py` | yes |
| `backend/cutover_contracts/authorization_validation.py` | yes |
| `backend/cutover_contracts/errors.py` | yes |
| `backend/cutover_contracts/operator_entry.py` | yes |
| `backend/cutover_contracts/profile.py` | yes |
| `backend/cutover_contracts/profile_schema.py` | yes |
| `backend/cutover_contracts/receipt.py` | yes |
| `backend/cutover_contracts/receipt_matrix.py` | yes |
| `backend/cutover_contracts/receipt_schema.py` | yes |
| `backend/cutover_contracts/receipt_types.py` | yes |
| `backend/cutover_journal/__init__.py` | yes |
| `backend/cutover_journal/_canonical.py` | yes |
| `backend/cutover_journal/action_common.py` | yes |
| `backend/cutover_journal/chain_reducer.py` | yes |
| `backend/cutover_journal/closed_classifier.py` | yes |
| `backend/cutover_journal/contracts_bridge.py` | yes |
| `backend/cutover_journal/durability.py` | yes |
| `backend/cutover_journal/effect_permit.py` | yes |
| `backend/cutover_journal/effect_guard.py` | yes |
| `backend/cutover_journal/effect_state.py` | yes |
| `backend/cutover_journal/errors.py` | yes |
| `backend/cutover_journal/journal_chain.py` | yes |
| `backend/cutover_journal/journal_record.py` | yes |
| `backend/cutover_journal/journal_store.py` | yes |
| `backend/cutover_journal/journal_types.py` | yes |
| `backend/cutover_journal/operation_binding.py` | yes |
| `backend/cutover_journal/pending_classifier.py` | yes |
| `backend/cutover_journal/record_schema.py` | yes |
| `backend/cutover_journal/recovery.py` | yes |
| `backend/cutover_journal/recovery_classifier.py` | yes |
| `backend/cutover_journal/recovery_types.py` | yes |
| `backend/cutover_journal/resume_actions.py` | yes |
| `backend/cutover_journal/rollback_actions.py` | yes |
| `backend/cutover_journal/store_support.py` | yes |
| `backend/cutover_journal/transaction.py` | yes |
| `backend/real_host_preflight/__init__.py` | yes |
| `backend/real_host_preflight/audit_bridge.py` | yes |
| `backend/real_host_preflight/audit_types.py` | yes |
| `backend/real_host_preflight/authorization_gate.py` | yes |
| `backend/real_host_preflight/baseline.py` | yes |
| `backend/real_host_preflight/baseline_bridge.py` | yes |
| `backend/real_host_preflight/baseline_evidence.py` | yes |
| `backend/real_host_preflight/callbacks.py` | yes |
| `backend/real_host_preflight/canonical.py` | yes |
| `backend/real_host_preflight/collection.py` | yes |
| `backend/real_host_preflight/composition.py` | yes |
| `backend/real_host_preflight/contracts.py` | yes |
| `backend/real_host_preflight/contracts_bridge.py` | yes |
| `backend/real_host_preflight/errors.py` | yes |
| `backend/real_host_preflight/evidence.py` | yes |
| `backend/real_host_preflight/integrity.py` | yes |
| `backend/real_host_preflight/mutation_gate.py` | yes |
| `backend/real_host_preflight/operator_entry.py` | yes |
| `backend/real_host_preflight/profile_snapshot.py` | yes |
| `backend/real_host_preflight/receipts.py` | yes |
| `backend/real_host_preflight/sandbox_lease.py` | yes |
| `backend/real_host_preflight/sandbox_state.py` | yes |
| `backend/real_host_preflight/sandbox_validation.py` | yes |
| `backend/real_host_preflight/topology.py` | yes |
| `backend/real_host_preflight/topology_evidence.py` | yes |
| `backend/real_host_preflight/windows_api.py` | yes |
| `backend/real_host_preflight/windows_chain.py` | yes |
| `backend/real_host_preflight/windows_observation.py` | yes |
| `backend/real_host_preflight/windows_paths.py` | yes |
| `backend/real_host_preflight/windows_projection.py` | yes |
| `backend/migration_evidence/__init__.py` | yes |
| `backend/migration_evidence/archive_validation.py` | yes |
| `backend/migration_evidence/package.py` | yes |
| `backend/migration_evidence/results.py` | yes |
| `backend/migration_evidence/review.py` | yes |
| `backend/migration_evidence/verification.py` | yes |
| `backend/migration_evidence_publication/__init__.py` | yes |
| `backend/migration_evidence_publication/canonical.py` | yes |
| `backend/migration_evidence_publication/contracts_bridge.py` | yes |
| `backend/migration_evidence_publication/creator_bridge.py` | yes |
| `backend/migration_evidence_publication/errors.py` | yes |
| `backend/migration_evidence_publication/host_baseline_bridge.py` | yes |
| `backend/migration_evidence_publication/operator_entry.py` | yes |
| `backend/migration_evidence_publication/package_observation.py` | yes |
| `backend/migration_evidence_publication/profile_binding.py` | yes |
| `backend/migration_evidence_publication/profile_git_binding.py` | yes |
| `backend/migration_evidence_publication/publication.py` | yes |
| `backend/migration_evidence_publication/publication_receipts.py` | yes |
| `backend/migration_evidence_publication/published_scope.py` | yes |
| `backend/migration_evidence_publication/receipt_set.py` | yes |
| `backend/migration_evidence_publication/receipts.py` | yes |
| `backend/migration_evidence_publication/review.py` | yes |
| `backend/migration_evidence_publication/review_bridge.py` | yes |
| `backend/migration_evidence_publication/selection.py` | yes |
| `backend/migration_evidence_publication/selection_state.py` | yes |
| `backend/migration_evidence_publication/synthetic_scope.py` | yes |
| `backend/migration_evidence_publication/verification_composition.py` | yes |
| `backend/migration_evidence_verifier/__init__.py` | yes |
| `backend/migration_evidence_verifier/bridge.py` | yes |
| `backend/migration_evidence_verifier/canonical.py` | yes |
| `backend/migration_evidence_verifier/contracts.py` | yes |
| `backend/migration_evidence_verifier/package_read.py` | yes |
| `backend/migration_evidence_verifier/process.py` | yes |
| `backend/migration_evidence_verifier/process_tree.py` | yes |
| `backend/migration_evidence_verifier/worker.py` | yes |
| `backend/cutover_host_mutation/__init__.py` | yes |
| `backend/cutover_host_mutation/acl_contracts.py` | yes |
| `backend/cutover_host_mutation/acl_journal.py` | yes |
| `backend/cutover_host_mutation/acl_paths.py` | yes |
| `backend/cutover_host_mutation/acl_receipt_factory.py` | yes |
| `backend/cutover_host_mutation/acl_state.py` | yes |
| `backend/cutover_host_mutation/canonical.py` | yes |
| `backend/cutover_host_mutation/errors.py` | yes |
| `backend/cutover_host_mutation/filesystem_contracts.py` | yes |
| `backend/cutover_host_mutation/filesystem_state.py` | yes |
| `backend/cutover_host_mutation/journal_intent.py` | yes |
| `backend/cutover_host_mutation/operator_entry.py` | yes |
| `backend/cutover_host_mutation/receipts.py` | yes |
| `backend/cutover_host_mutation/roles.py` | yes |
| `backend/cutover_host_mutation/source_acl_compatibility.py` | yes |
| `backend/cutover_host_mutation/windows_acl.py` | yes |
| `backend/cutover_host_mutation/windows_acl_adapter.py` | yes |
| `backend/cutover_host_mutation/windows_acl_apply.py` | yes |
| `backend/cutover_host_mutation/windows_acl_apply_bindings.py` | yes |
| `backend/cutover_host_mutation/windows_acl_factory.py` | yes |
| `backend/cutover_host_mutation/windows_construction_acl.py` | yes |
| `backend/cutover_host_mutation/windows_directory.py` | yes |
| `backend/cutover_host_mutation/windows_directory_factory.py` | yes |
| `backend/cutover_host_mutation/windows_directory_native.py` | yes |
| `backend/cutover_host_mutation/windows_directory_resources.py` | yes |
| `backend/cutover_host_mutation/windows_filesystem.py` | yes |
| `backend/cutover_host_mutation/windows_filesystem_common.py` | yes |
| `backend/cutover_host_mutation/windows_handles.py` | yes |
| `backend/cutover_host_mutation/windows_native_bindings.py` | yes |
| `backend/cutover_host_mutation/windows_no_replace.py` | yes |
| `backend/cutover_host_mutation/windows_no_replace_factory.py` | yes |
| `backend/cutover_host_mutation/windows_security.py` | yes |
| `backend/cutover_host_mutation/windows_security_bindings.py` | yes |
| `backend/cutover_host_mutation/windows_security_projection.py` | yes |
| `backend/cutover_host_mutation/windows_sid.py` | yes |
| `backend/cutover_repository_transaction/__init__.py` | yes |
| `backend/cutover_repository_transaction/contracts.py` | yes |
| `backend/cutover_repository_transaction/container_audit_bridge.py` | yes |
| `backend/cutover_repository_transaction/durable_store.py` | yes |
| `backend/cutover_repository_transaction/errors.py` | yes |
| `backend/cutover_repository_transaction/failed_evidence.py` | yes |
| `backend/cutover_repository_transaction/forward.py` | yes |
| `backend/cutover_repository_transaction/forward_recovery.py` | yes |
| `backend/cutover_repository_transaction/git_inspection.py` | yes |
| `backend/cutover_repository_transaction/git_executable.py` | yes |
| `backend/cutover_repository_transaction/git_recreation.py` | yes |
| `backend/cutover_repository_transaction/git_runner.py` | yes |
| `backend/cutover_repository_transaction/issue52_bridge.py` | yes |
| `backend/cutover_repository_transaction/journal_record.py` | yes |
| `backend/cutover_repository_transaction/journal_chain.py` | yes |
| `backend/cutover_repository_transaction/journal_identity.py` | yes |
| `backend/cutover_repository_transaction/journal_types.py` | yes |
| `backend/cutover_repository_transaction/mutation_executor.py` | yes |
| `backend/cutover_repository_transaction/real_lock.py` | yes |
| `backend/cutover_repository_transaction/restart_classification.py` | yes |
| `backend/cutover_repository_transaction/reverse.py` | yes |
| `backend/cutover_repository_transaction/reverse_checkpoint.py` | yes |
| `backend/cutover_repository_transaction/reverse_plan.py` | yes |
| `backend/cutover_repository_transaction/reverse_resume.py` | yes |
| `backend/cutover_repository_transaction/scope_models.py` | yes |
| `backend/cutover_repository_transaction/scope_paths.py` | yes |
| `backend/cutover_repository_transaction/stable_observation.py` | yes |
| `backend/cutover_repository_transaction/synthetic_scope.py` | yes |
| `backend/cutover_repository_transaction/transaction.py` | yes |
| `backend/cutover_repository_transaction/transaction_types.py` | yes |
| `backend/cutover_repository_transaction/verification.py` | yes |
| `backend/cutover_repository_transaction/windows_identity.py` | yes |
| `backend/cutover_managed_activation/__init__.py` | yes |
| `backend/cutover_managed_activation/adapters.py` | yes |
| `backend/cutover_managed_activation/artifact_publisher.py` | yes |
| `backend/cutover_managed_activation/canonical.py` | yes |
| `backend/cutover_managed_activation/config_contract.py` | yes |
| `backend/cutover_managed_activation/config_publisher.py` | yes |
| `backend/cutover_managed_activation/database_copier.py` | yes |
| `backend/cutover_managed_activation/errors.py` | yes |
| `backend/cutover_managed_activation/phase.py` | yes |
| `backend/cutover_managed_activation/publication_scope.py` | yes |
| `backend/cutover_managed_activation/real_lock.py` | yes |
| `backend/cutover_managed_activation/receipts.py` | yes |
| `backend/cutover_managed_activation/runtime_archive.py` | yes |
| `backend/cutover_managed_activation/runtime_builder.py` | yes |
| `backend/cutover_managed_activation/runtime_capture.py` | yes |
| `backend/cutover_managed_activation/runtime_execution.py` | yes |
| `backend/cutover_managed_activation/runtime_limits.py` | yes |
| `backend/cutover_managed_activation/runtime_policy.py` | yes |
| `backend/cutover_managed_activation/runtime_source_tree.py` | yes |
| `backend/cutover_managed_activation/runtime_tree.py` | yes |
| `backend/cutover_managed_activation/runtime_verification.py` | yes |
| `backend/cutover_managed_activation/scope_models.py` | yes |
| `backend/cutover_managed_activation/scope_paths.py` | yes |
| `backend/cutover_managed_activation/scope_profile.py` | yes |
| `backend/cutover_managed_activation/stopped_service.py` | yes |
| `backend/cutover_managed_activation/synthetic_scope.py` | yes |
| `backend/cutover_managed_activation/windows_file_handles.py` | yes |
| `backend/cutover_managed_activation/windows_directory_monitor.py` | yes |
| `backend/cutover_managed_activation/windows_publication_io.py` | yes |
| `backend/cutover_managed_activation/windows_streams.py` | yes |
| `backend/cutover_service_lifecycle/__init__.py` | yes |
| `backend/cutover_service_lifecycle/activation_contracts.py` | yes |
| `backend/cutover_service_lifecycle/activation_validation.py` | yes |
| `backend/cutover_service_lifecycle/adapters.py` | yes |
| `backend/cutover_service_lifecycle/canonical.py` | yes |
| `backend/cutover_service_lifecycle/contracts.py` | yes |
| `backend/cutover_service_lifecycle/controller.py` | yes |
| `backend/cutover_service_lifecycle/errors.py` | yes |
| `backend/cutover_service_lifecycle/failures.py` | yes |
| `backend/cutover_service_lifecycle/legacy_contracts.py` | yes |
| `backend/cutover_service_lifecycle/legacy_recovery.py` | yes |
| `backend/cutover_service_lifecycle/lifecycle.py` | yes |
| `backend/cutover_service_lifecycle/lifecycle_binding.py` | yes |
| `backend/cutover_service_lifecycle/real_lock.py` | yes |
| `backend/cutover_service_lifecycle/rollback_adapters.py` | yes |
| `backend/cutover_service_lifecycle/rollback_contracts.py` | yes |
| `backend/cutover_service_lifecycle/rollback_validation.py` | yes |
| `backend/cutover_composition_contracts/__init__.py` | yes |
| `backend/cutover_composition_contracts/authorization_sequence.py` | yes |
| `backend/cutover_composition_contracts/binding.py` | yes |
| `backend/cutover_composition_contracts/canonical.py` | yes |
| `backend/cutover_composition_contracts/chain.py` | yes |
| `backend/cutover_composition_contracts/errors.py` | yes |
| `backend/cutover_composition_contracts/receipts.py` | yes |
| `backend/real_host_preflight_composition/__init__.py` | yes |
| `backend/real_host_preflight_composition/composition.py` | yes |
| `backend/real_host_preflight_composition/contracts_bridge.py` | yes |
| `backend/real_host_preflight_composition/operator_entry.py` | yes |
| `backend/real_host_preflight_composition/roles.py` | yes |
| `backend/migration_evidence_publication_composition/__init__.py` | yes |
| `backend/migration_evidence_publication_composition/composition.py` | yes |
| `backend/migration_evidence_publication_composition/contracts_bridge.py` | yes |
| `backend/migration_evidence_publication_composition/operator_entry.py` | yes |
| `backend/migration_evidence_publication_composition/roles.py` | yes |
| `backend/cutover_transaction_composition/__init__.py` | yes |
| `backend/cutover_transaction_composition/composition.py` | yes |
| `backend/cutover_transaction_composition/contracts_bridge.py` | yes |
| `backend/cutover_transaction_composition/operator_entry.py` | yes |
| `backend/cutover_transaction_composition/roles.py` | yes |
| `backend/cutover_transaction_composition/state.py` | yes |
| `backend/reparenting_rehearsal/__init__.py` | yes |
| `backend/reparenting_rehearsal/rehearsal.py` | yes |
| `backend/runtime_activation_rehearsal/__init__.py` | yes |
| `backend/runtime_activation_rehearsal/rehearsal.py` | yes |
| `backend/runtime_activation_rehearsal/service_checks.py` | yes |
| `backend/mailbox_ingest/governed_scan.py` | yes |
| `backend/mailbox_ingest/sales_corpus_index.py` | yes |
| `backend/mailbox_ingest/sales_message_policy.py` | yes |
| `backend/mailbox_ingest/sales_policy_file.py` | yes |
| `backend/email_agent/__init__.py` | yes |
| `backend/email_agent/analysis_schema.py` | yes |
| `backend/email_agent/analysis_budget.py` | yes |
| `backend/email_agent/analysis_diagnostics.py` | yes |
| `backend/email_agent/analysis_model_routes.py` | yes |
| `backend/email_agent/analysis_provider_policy.py` | yes |
| `backend/email_agent/analysis_route_support.py` | yes |
| `backend/email_agent/attachment_media_context.py` | yes |
| `backend/email_agent/attachment_parser.py` | yes |
| `backend/email_agent/attachment_safety.py` | yes |
| `backend/email_agent/attachment_storage.py` | yes |
| `backend/email_agent/config.py` | yes |
| `backend/email_agent/managed_runtime.py` | yes |
| `backend/email_agent/managed_runtime_errors.py` | yes |
| `backend/email_agent/managed_runtime_validation.py` | yes |
| `backend/email_agent/logging_config.py` | yes |
| `backend/email_agent/email_cleaner.py` | yes |
| `backend/email_agent/analyzer.py` | yes |
| `backend/email_agent/rule_analyzer.py` | yes |
| `backend/email_agent/llm_client.py` | yes |
| `backend/email_agent/database.py` | yes |
| `backend/email_agent/exporter.py` | yes |
| `backend/email_agent/api.py` | yes |
| `backend/email_agent/server.py` | yes |
| `backend/email_agent/frontend_assets.py` | yes |
| `backend/email_agent/image_media_safety.py` | yes |
| `backend/email_agent/llm_errors.py` | yes |
| `backend/email_agent/model_context_selection.py` | yes |
| `backend/email_agent/model_cross_language_grounding.py` | yes |
| `backend/email_agent/model_grounding.py` | yes |
| `backend/email_agent/model_multimodal_claim_safety.py` | yes |
| `backend/email_agent/model_request.py` | yes |
| `backend/email_agent/model_result_safety.py` | yes |
| `backend/email_agent/model_source_grounding.py` | yes |
| `backend/email_agent/model_visual_grounding.py` | yes |
| `backend/email_agent/multimodal_media.py` | yes |
| `backend/email_agent/office_embedded_media.py` | yes |
| `backend/email_agent/openai_multimodal_client.py` | yes |
| `backend/email_agent/participant_identity_aliases.py` | yes |
| `backend/email_agent/pdf_media_safety.py` | yes |
| `backend/email_agent/private_context_gate.py` | yes |
| `backend/email_agent/private_provider_output_gate.py` | yes |
| `backend/email_agent/prompt_context.py` | yes |
| `backend/email_agent/thread_prompt_projection.py` | yes |
| `frontend/local_debug_page/index.html` | yes |
| `frontend/local_debug_page/app.js` | yes |
| `frontend/local_debug_page/styles.css` | yes |
| `frontend/browser_extension/manifest.json` | yes |
| `frontend/browser_extension/popup.html` | yes |
| `frontend/browser_extension/popup.css` | yes |
| `frontend/browser_extension/popup.js` | yes |
| `frontend/browser_extension/content/current_message_collector.js` | yes |
| `frontend/browser_extension/content/exmail_adapter.js` | yes |
| `frontend/browser_extension/content/exmail_visible_context.js` | yes |
| `frontend/browser_extension/content/exmail_visible_resource_classifier.js` | yes |
| `frontend/browser_extension/shared/api_client.js` | yes |
| `frontend/browser_extension/shared/manual_attachment_files.js` | yes |
| `frontend/browser_extension/shared/render_analysis.js` | yes |
| `frontend/browser_extension/shared/analysis_components.css` | yes |
| `docs/constraints/tooling_constraints.md` | yes |
| `docs/constraints/architecture_constraints.md` | yes |
| `docs/constraints/linter_constraints.md` | yes |
| `docs/constraints/mechanical_rule_translation.md` | yes |
| `docs/security/project_container_cutover_contracts.md` | yes |
| `docs/decisions/0006-authorized-mailbox-ingest-and-private-knowledge.md` | yes |
| `docs/decisions/0007-multimodal-current-email-analysis.md` | yes |
| `docs/decisions/0008-bounded-corpus-to-runtime-handoffs.md` | yes |
| `docs/decisions/0009-project-container-and-repository-boundaries.md` | yes |
| `docs/operations/authorized_mailbox_ingest_task_brief.md` | yes |
| `docs/operations/bounded_corpus_runtime_handoffs_task_brief.md` | yes |
| `docs/operations/issue11_governed_sales_corpus_task_brief.md` | yes |
| `docs/operations/deepseek_analysis_contract_alignment_task_brief.md` | yes |
| `docs/operations/private_deepseek_evaluation_task_brief.md` | yes |
| `docs/operations/private_mailbox_rollout_closeout_task_brief.md` | yes |
| `docs/operations/multimodal_current_email_analysis_task_brief.md` | yes |
| `docs/operations/current_email_grounding_and_attachment_repair_task_brief.md` | yes |
| `docs/operations/issue32_managed_container_mode_task_brief.md` | yes |
| `docs/operations/issue35_migration_evidence_package_task_brief.md` | yes |
| `docs/operations/issue36_reparenting_rehearsal_task_brief.md` | yes |
| `docs/operations/issue37_managed_runtime_localdata_rehearsal_task_brief.md` | yes |
| `docs/operations/issue51_cutover_profile_authorization_receipt_task_brief.md` | yes |
| `docs/operations/issue52_crash_safe_journal_recovery_task_brief.md` | yes |
| `docs/operations/issue53_windows_real_host_preflight_task_brief.md` | yes |
| `docs/operations/issue54_migration_evidence_publication_task_brief.md` | yes |
| `docs/operations/issue55_windows_acl_filesystem_primitives_task_brief.md` | yes |
| `docs/operations/issue56_repository_worktree_transaction_task_brief.md` | yes |
| `docs/operations/issue57_managed_activation_publication_task_brief.md` | yes |
| `docs/operations/issue58_provider_disabled_activation_recovery_task_brief.md` | yes |
| `docs/operations/issue59_project_container_composition_task_brief.md` | yes |
| `docs/operations/issues70_83_r2_cutover_remediation_task_brief.md` | yes |
| `docs/operations/r2_synthetic_verification_criteria.md` | yes |
| `docs/operations/r2_synthetic_verification_evidence.md` | yes |
| `docs/operations/project_status_log.md` | yes |
| `docs/operations/project_status_log_guide.md` | yes |
| `docs/operations/agents_project_status_snippet.md` | yes |
| `docs/operations/cleanup_agent.md` | yes |
| `docs/operations/cleanup_agent_codex.md` | yes |
| `docs/operations/codex_cleanup_task.md` | yes |
| `docs/operations/documentation_rules.md` | yes |
| `docs/operations/first_version_task_brief.md` | yes |
| `docs/operations/tencent_exmail_browser_extension_task_brief.md` | yes |
| `docs/templates/agent_task_brief_template.md` | yes |
| `docs/templates/cleanup_task_template.md` | yes |
| `scripts/repo_utils.py` | yes |
| `scripts/maintenance_scan.py` | yes |
| `scripts/repository_leakage_scan.py` | yes |
| `scripts/generate_project_status.py` | yes |
| `scripts/verify_r2_synthetic_topology.py` | yes |
| `scripts/run_local_debug.py` | yes |
| `scripts/manage_local_service.py` | yes |
| `scripts/manage_mailbox_vault.py` | yes |
| `scripts/manage_private_knowledge.py` | yes |
| `scripts/evaluate_private_deepseek.py` | yes |
| `start_local_service.cmd` | yes |
| `stop_local_service.cmd` | yes |
| `restart_local_service.cmd` | yes |
| `status_local_service.cmd` | yes |
| `tests/fixtures/sample_emails.json` | yes |
| `tests/test_analysis_schema.py` | yes |
| `tests/test_analysis_model_routes.py` | yes |
| `tests/test_golden_email_analysis.py` | yes |
| `tests/test_rule_analyzer.py` | yes |
| `tests/test_database.py` | yes |
| `tests/test_server.py` | yes |
| `tests/test_frontend_local_debug.py` | yes |
| `tests/test_repo_utils.py` | yes |
| `tests/test_config.py` | yes |
| `tests/test_run_local_debug.py` | yes |
| `tests/test_manage_local_service.py` | yes |
| `tests/test_managed_container_mode.py` | yes |
| `tests/test_migration_evidence_no_clobber.py` | yes |
| `tests/migration_evidence_publication_fixtures.py` | yes |
| `tests/test_migration_evidence_publication_architecture.py` | yes |
| `tests/test_migration_evidence_publication_commit_binding.py` | yes |
| `tests/test_migration_evidence_publication_create_verify.py` | yes |
| `tests/test_migration_evidence_publication_operator.py` | yes |
| `tests/test_migration_evidence_publication_package_observation.py` | yes |
| `tests/test_migration_evidence_publication_receipts.py` | yes |
| `tests/test_migration_evidence_publication_review.py` | yes |
| `tests/cutover_host_mutation_fixtures.py` | yes |
| `tests/test_cutover_host_mutation_architecture.py` | yes |
| `tests/test_cutover_host_mutation_contracts.py` | yes |
| `tests/test_cutover_host_mutation_operator.py` | yes |
| `tests/test_cutover_host_mutation_portable.py` | yes |
| `tests/test_cutover_host_mutation_windows_acl.py` | yes |
| `tests/test_cutover_host_mutation_windows_filesystem.py` | yes |
| `tests/cutover_repository_transaction_fixtures.py` | yes |
| `tests/test_cutover_repository_transaction_architecture.py` | yes |
| `tests/test_cutover_repository_transaction_contracts.py` | yes |
| `tests/test_cutover_repository_transaction_crash_gaps.py` | yes |
| `tests/test_cutover_repository_transaction_durable_store.py` | yes |
| `tests/test_cutover_repository_transaction_fail_closed.py` | yes |
| `tests/test_cutover_repository_transaction_journal.py` | yes |
| `tests/test_cutover_repository_transaction_real_lock.py` | yes |
| `tests/test_cutover_repository_transaction_windows_round_trip.py` | yes |
| `tests/test_cutover_repository_transaction_windows_boundary_reverse.py` | yes |
| `tests/test_cutover_repository_transaction_windows_scope.py` | yes |
| `tests/cutover_managed_activation_fixtures.py` | yes |
| `tests/test_cutover_managed_activation_architecture.py` | yes |
| `tests/test_cutover_managed_activation_contracts.py` | yes |
| `tests/test_cutover_managed_activation_fail_closed.py` | yes |
| `tests/test_cutover_managed_activation_real_lock.py` | yes |
| `tests/test_cutover_managed_activation_windows_edges.py` | yes |
| `tests/test_cutover_service_lifecycle_activation.py` | yes |
| `tests/test_cutover_service_lifecycle_architecture.py` | yes |
| `tests/test_cutover_service_lifecycle_contracts.py` | yes |
| `tests/test_cutover_service_lifecycle_leakage.py` | yes |
| `tests/test_cutover_service_lifecycle_real_lock.py` | yes |
| `tests/test_cutover_service_lifecycle_rollback.py` | yes |
| `tests/test_cutover_service_lifecycle_windows_sandbox.py` | yes |
| `tests/cutover_composition_fixtures.py` | yes |
| `tests/cutover_composition_binders.py` | yes |
| `tests/project_container_composition_windows_fixtures.py` | yes |
| `tests/test_cutover_composition_architecture.py` | yes |
| `tests/test_cutover_composition_operator_lock.py` | yes |
| `tests/test_cutover_composition_receipt_chain.py` | yes |
| `tests/test_cutover_composition_coverage_contract.py` | yes |
| `tests/test_cutover_composition_leakage.py` | yes |
| `tests/test_real_host_preflight_composition_root.py` | yes |
| `tests/test_migration_evidence_publication_composition_root.py` | yes |
| `tests/test_cutover_transaction_composition_root.py` | yes |
| `tests/test_project_container_composition_windows_end_to_end.py` | yes |
| `tests/windows_reparse_fixtures.py` | yes |
| `tests/test_migration_evidence_restore.py` | yes |
| `tests/test_migration_evidence_verification.py` | yes |
| `tests/test_migration_evidence_verifier_architecture.py` | yes |
| `tests/test_migration_evidence_verifier_process.py` | yes |
| `tests/test_reparenting_rehearsal_rollback.py` | yes |
| `tests/test_reparenting_rehearsal_safety.py` | yes |
| `tests/test_reparenting_rehearsal_success.py` | yes |
| `tests/test_runtime_activation_rehearsal_architecture.py` | yes |
| `tests/test_runtime_activation_rehearsal_integration.py` | yes |
| `tests/test_runtime_activation_rehearsal_service.py` | yes |
| `tests/cutover_contract_fixtures.py` | yes |
| `tests/test_cutover_authorization_contract.py` | yes |
| `tests/test_cutover_contract_architecture.py` | yes |
| `tests/test_cutover_profile_contract.py` | yes |
| `tests/test_cutover_receipt_contract.py` | yes |
| `tests/cutover_journal_fixtures.py` | yes |
| `tests/test_cutover_journal_architecture.py` | yes |
| `tests/test_cutover_journal_chain.py` | yes |
| `tests/test_cutover_journal_crash_matrix.py` | yes |
| `tests/test_cutover_journal_durability.py` | yes |
| `tests/test_cutover_journal_record_contract.py` | yes |
| `tests/test_cutover_journal_recovery.py` | yes |
| `tests/real_host_preflight_fixtures.py` | yes |
| `tests/test_real_host_preflight_architecture.py` | yes |
| `tests/test_real_host_preflight_baseline.py` | yes |
| `tests/test_real_host_preflight_composition.py` | yes |
| `tests/test_real_host_preflight_gate.py` | yes |
| `tests/test_real_host_preflight_leakage.py` | yes |
| `tests/test_real_host_preflight_portable.py` | yes |
| `tests/test_real_host_preflight_topology.py` | yes |
| `tests/test_real_host_preflight_windows.py` | yes |
| `tests/test_real_host_preflight_windows_composition.py` | yes |
| `tests/support.py` | yes |
| `tests/test_architecture_constraints.py` | yes |
| `tests/test_current_evidence_handoff.py` | yes |
| `tests/test_static_linter_constraints.py` | yes |
| `tests/test_mechanical_rule_constraints.py` | yes |
| `tests/test_mailbox_transport_constraints.py` | yes |
| `tests/test_mailbox_governed_scan.py` | yes |
| `tests/test_mailbox_sales_corpus_index.py` | yes |
| `tests/test_maintenance_scan.py` | yes |
| `tests/test_generate_project_status.py` | yes |
| `tests/test_repository_leakage_scan.py` | yes |
| `tests/test_rollout_closeout_contracts.py` | yes |
| `tests/test_r2_full_topology_windows.py` | yes |
| `tests/test_r2_semantic_gap_matrix.py` | yes |
| `tests/test_r2_verification_architecture.py` | yes |
| `tests/test_r2_verification_evidence_contracts.py` | yes |
| `tests/test_r2_production_adapter_binding_v1.py` | yes |
| `tests/test_r2_production_composition_v1.py` | yes |
| `tests/test_r2_production_composition_v1_architecture.py` | yes |
| `tests/test_r2_production_binding_candidate_v1.py` | yes |
| `tests/test_email_cleaner.py` | yes |
| `tests/test_analyzer.py` | yes |
| `tests/test_api.py` | yes |
| `tests/test_browser_extension_manifest.py` | yes |
| `tests/test_browser_extension_static.py` | yes |
| `tests/test_browser_extension_behavior.py` | yes |
| `tests/test_browser_extension_renderer_behavior.py` | yes |
| `tests/test_browser_extension_manual_attachment_files.py` | yes |
| `tests/test_browser_extension_task_focused_ui.py` | yes |
| `tests/test_browser_extension_visible_resource_classifier.py` | yes |
| `tests/test_model_grounding.py` | yes |
| `tests/test_model_result_safety.py` | yes |
| `tests/test_multimodal_documentation_contracts.py` | yes |
| `tests/test_multimodal_media.py` | yes |
| `tests/test_office_embedded_media.py` | yes |
| `tests/test_openai_multimodal_client.py` | yes |

## docs Directory Status

| File | Exists |
|---|---|
| `docs/product` | yes |
| `docs/knowledge_base` | yes |
| `docs/prompts` | yes |
| `docs/data` | yes |
| `docs/api` | yes |
| `docs/security` | yes |
| `docs/constraints` | yes |
| `docs/conventions` | yes |
| `docs/decisions` | yes |
| `docs/operations` | yes |
| `docs/templates` | yes |

## docs Metadata Summary

| Status | Count |
|---|---:|
| active | 130 |
| draft | 24 |
| deprecated | 5 |
| missing_front_matter | 0 |

## Recommended Next Steps

1. Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_TEXT_FALLBACK_PROVIDER=disabled` outside a separately authorized, bounded live test process; all providers remain disabled by default, and offline completion does not authorize live operation.
2. Task 9 synthetic provider and current-clicked Tencent smokes are complete. Task 9 forced OpenAI-to-DeepSeek synthetic fallback is complete: one OpenAI attempt was intercepted before network access, exactly one DeepSeek text-only request was made, DeepSeek SDK retries were zero, and no SQLite write occurred. The root `.env` was unchanged.
3. Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness. The evidence-reconciliation and private human gold-standard gates pass offline and the reviewed repair is integrated into the current release line.
4. Any new live operation still requires fresh explicit authorization.
5. Keep the administrator-only mailbox CLI and click-only current-message runtime as separate authorization surfaces.
6. Run the content-free repository leakage scan and complete final verification before release; preserve unrelated working-copy changes and keep any remote push separate.

## Do Not Touch Boundaries

- 浏览器扩展和正常运行时不接入真实邮箱账号；唯一例外是管理员手动运行的单账户只读导入 CLI。
- 浏览器扩展和正常运行时不读取真实邮箱数据；管理员 CLI 只处理授权范围并先确认 inventory fingerprint。
- 不自动发送邮件。
- 不自动删除邮件。
- 不自动归档邮件。
- 浏览器扩展和正常运行时不自动扫描所有邮件；管理员 CLI 没有 schedule、后台轮询或自动模型推理。
- 不把 OpenAI API key 放入前端。
- 不新增依赖，除非先更新约束文档并获得确认。
- 不放宽任何测试、linter 或架构约束。
- 真实 migration evidence package 必须先展示 exact target、content-free inclusion/exclusion manifest、reviewed local refs 和 worktree selection，并在单独确认前停止。
- Issue #36 只证明 temporary synthetic rehearsal；不得把它当作真实 migration、audit、worktree repair 或 cutover 授权。
- Issue #37 只证明 injected-adapter temporary synthetic activation rehearsal；不得把它当作真实 runtime、SQLite、artifact activation 或 cutover 授权。
- Issue #51 只建立 pure content-free contracts；四种 real-host authorization 只能验证外部 canonical values，不能 create、issue 或 mint，且默认 operator entry 保持 BLOCKED。
- Issue #52 只建立 pathless synthetic journal/recovery proof；pending/unbarriered record 不授权 effect，每次 owner claim 与 durable-intent permit 都是 exact synthetic capability，observed/pending/profile/identity/mapping fail closed，restart inspection 只读，且不得触碰真实 host 或 private capability。
- Issue #53 只建立 test-sandbox-owned Windows read-only observation 与窄 callback composition；真实 operator entry 继续 BLOCKED，不得把 receipt、test authorization 或 readiness 当作 mutation/cutover authority。
- Issue #54 只建立 profile-bound synthetic review、separately authorized create-only publication 与 separate read-only verifier；真实 entries 在 Issue #39 前继续 BLOCKED，receipts/Set 只是 content-free evidence，package 不是 backup、Runtime artifact、private-data container 或 migration authorization。
- Issue #55 只建立 test-owned NTFS sandbox 内的 fixed-role ACL 与 handle-relative no-clobber primitives；每个 effect 必须先消费 durable INTENT，真实 constructor 在 Issue #39 前继续 BLOCKED，不得把 test authorization、receipt 或 observation 当作 real-host authority。
- Issue #56 只证明 caller-owned synthetic Windows sandbox 内 exact 8 embedded + 3 external mixed-topology forward/reverse transaction；不得把 journal、receipt、crash classification 或测试结果当作真实 repository/worktree cutover、Issues #57-#59、#38/#39、merge 或父 Spec closure 授权。
- Issue #57 only proves create-only managed Runtime, LocalData, CRX, and Config publication inside caller-owned synthetic Windows sandboxes; receipts and tests do not authorize real activation, Issues #58/#59, Issues #38/#39, merge, or parent Spec closure.
- Issue #58 only proves provider-disabled activation, committed-journal-driven rollback, and dedicated legacy recovery inside caller-owned synthetic sandboxes; receipts and tests do not authorize a real service probe or operation, Issue #59, Issues #38/#39, merge, or parent Spec closure.
- Issue #59 only assembles three default-locked operator roots and a content-free receipt chain. Backend packages expose no executable test binder; test-only assembly owns every component TemporaryDirectory through one internal scope and rechecks it before every role or journal callback. Windows execution remains confined to caller-owned test sandboxes; no real command or authorization exists before #39. After merge, the final master invalidates R1 and requires all fourteen #38 approval items plus a new R2 before #39.
- Issues #70-#83 only implement dormant R2 contracts and fresh synthetic Windows proof. The fixed verifier owns its NTFS sandbox and emits aggregate fingerprints/counts; it does not authorize Issue #39, a real command, any host operation, merge, or approval/closure of #38 or #50. The accepted prototype fingerprint remains non-authorizing prior art.
- Issue #104 retains three exact stateful Adapter slots and owning-module source identity, but Issue #110 keeps every production Adapter path dormant before lookup. Neither issue authorizes a host operation, production artifact, Issue #38 approval, Issue #39, or closure.
- Issue #110 replaces the legacy V1 external-signature path with two strict Solo Maintainer Closure files and a dormant V3 execution-confirmation seam. Ruleset 20601214 exists for master; compatibility work is limited to authenticated fixed GET-only keyring observation, Python never reads the token, and normalization accepts only exact empty required_reviewers plus absent or exact-true unattributed-approval at exact integer zero approvals. No live prepare, confirm, or protected verifier was run or authorized; #38/#39 remain unchanged, and no closure evidence authorizes host/provider/mailbox/vault/private-data access, cleanup, push, or merge.

## Notes for Agent

- 先读 `AGENTS.md`，再读本文件。
- 涉及工具、架构、linter、机械规则、安全边界时，继续读 `docs/constraints/`。
- 涉及任务执行前规划时，填写 `docs/templates/agent_task_brief_template.md`。
- 不要把项目进度流水账写入 `AGENTS.md`。
