---
last_update: 2026-07-29
status: active
owner: "@tobyWang"
review_cycle: as_needed
source_type: operation_guide
---

# Issue 57 managed activation publication task brief

## 1. Task name

```text
Issue #57 publish managed Runtime, LocalData, CRX, and Config in a sandbox
```

## 2. Task type

```text
security
```

## 3. Current status

```text
complete
```

## 4. Goal

Implement the bounded Issue #57 managed-publication phase from exact remote
`master@7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd`. The executable proof
must run only in a caller-owned synthetic Windows sandbox and must publish a
fresh offline Runtime, one stopped-source SQLite copy, one reviewed CRX, and
one deterministic non-secret Config without clobbering an existing target.

## 5. Non-goals

- Do not read, modify, copy, stop, start, repair, clean, or inspect any real
  Runtime, database, CRX, Config, service, browser profile, repository,
  worktree, ACL, mailbox, provider, credential, vault, private store, or
  private data.
- Do not add service activation, repository/worktree mutation, ACL mutation,
  rollback, failed-Container classification, browser installation, CRX
  building/signing/loading, provider calls, or private-row inspection.
- Do not add a real cutover command, CLI, HTTP route, scheduler, workflow,
  arbitrary source/target/config surface, authorization issuer, cleanup, or
  partial-publication repair.
- Do not implement Issues #58/#59, modify Issues #38/#39, close parent Spec
  #50, or merge the resulting pull request.

## 6. Background and references

- GitHub Issue #57, parent Spec #50, and closed dependencies #55/#56.
- `AGENTS.md`, `CONTEXT.md`, and the current project status log.
- `docs/decisions/0009-project-container-and-repository-boundaries.md`.
- `docs/security/project_container_cutover_contracts.md`.
- `docs/operations/project_container_migration_task_brief.md`.
- Issue #37 rehearsal and Issue #51 through #56 contract, journal, preflight,
  evidence, filesystem, and repository-transaction seams.
- Tooling, architecture, linter, mechanical, CI, documentation, testing,
  leakage, and maintenance constraints.

The root workspace contains user-owned dirty state and many existing
worktrees. This task uses only the clean sibling worktree
`D:\Projects\email_ai_assistant_issue_57_managed_activation` on
`codex/issue-57-managed-activation`.

## 7. Scope

Expected additions:

- `backend/cutover_managed_activation/` for closed policy values,
  content-free receipts, narrow adapters, Windows-sandbox publication,
  deterministic Config generation, receipt chaining, and the locked real
  constructor.
- Focused `tests/test_cutover_managed_activation_*.py` modules and synthetic
  Windows fixtures.
- This task brief.

Expected synchronized changes:

- Exact Issue #57 architecture, tooling, static, mechanical, CI, security,
  decision, project-structure, status, testing, and leakage contracts.
- The project-status generator and generated status log.

No frontend, provider, mailbox, vault, private-knowledge, private-evaluation,
normal-runtime analysis, service, repository/worktree, ACL, dependency, or
cleanup code is in scope.

## 8. Technical approach

### 8.1 TDD public seams

Tests observe only these Issue-approved seams:

1. `ManagedActivationPhase`, accepting one exact bundle of narrow Runtime,
   database, artifact, and Config adapters;
2. `LockedRuntimeBuilder`, which binds one approved Python 3.12.13 source,
   one hash-locked offline wheelhouse, one exact dependency lock, and one
   absent Runtime target;
3. Runtime self-verification through the newly published Runtime executable;
4. `StoppedDatabaseCopier`, requiring one exact stopped-service receipt and
   a held write-blocking source handle for the complete operation;
5. `ArtifactPublisher`, accepting only one profile-bound reviewed CRX;
6. `ConfigPublisher`, accepting only the closed non-secret schema and
   producing canonical bytes;
7. `ManagedRuntimeReceiptV1`, `StoppedDatabaseCopyReceiptV1`,
   `CrxPublicationReceiptV1`, `ConfigPublicationReceiptV1`, and their exact
   same-operation/profile/master chain;
8. the default-locked real managed-publication constructor.

Each vertical slice is one public failing test, minimal implementation, and
focused GREEN. Windows filesystem/process behavior is exercised only after a
private test-sandbox binder proves the caller-owned root, marker, profile,
authorization, fixed roles, target absence, and reparse-free scope.

### 8.2 ManagedActivationPhase capability boundary

The phase receives exactly four sealed adapters. The Runtime adapter exposes
only `publish_runtime`; the database adapter exposes only
`copy_stopped_database`; the artifact adapter exposes only `publish_crx`; and
the Config adapter exposes only `publish_config`. The phase rejects custom
containers, subclasses, additional fields, and mismatched receipt chains.

The phase owns no service, repository, worktree, Git, ACL, browser, mailbox,
provider, credential, vault, environment, registry, clipboard, hidden-input,
private-data, repair, overwrite, delete, or cleanup capability.

### 8.3 Locked Runtime publication and verification

The test harness first materializes one approved CPython distribution inside
the caller-owned sandbox. Its canonical manifest binds every directory/file,
exact entry count, total bytes, tree fingerprint, executable name/SHA-256,
Python `3.12.13`, and SQLite `3.50.4`. Before any source code executes, the
builder independently rebuilds that bounded manifest, rejects every reparse
point or alternate stream, holds every source entry against write/delete
sharing, and starts a recursive source-tree change guard that remains pending
through build and verification.
The builder never discovers a system interpreter through `PATH` or
`sys.executable`; source selection is explicit and profile-bound. A changed,
reparse-traversing, non-regular, wrong-version, or wrong-SQLite source is
rejected.
Scope review rejects any source executable outside the owned sandbox.
Source, wheel, and lock capture checks held-handle size and the remaining
aggregate budget before a bounded read; wheelhouse enumeration stops at the
expected-count ceiling before collecting entries. It never rereads the test
runner's external Runtime path.

The dependency lock is canonical, pins the complete reviewed installed set,
and binds every wheel filename, normalized package/version, SHA-256, and
import fingerprint. The wheelhouse must contain exactly those regular,
non-reparse wheel files and no extra wheel. Publication creates a brand-new
isolated Runtime directory once from the reviewed source and installs only
hash-approved bytes captured while each reviewed wheel handle denies writes
and replacement. `.pth`, `sitecustomize.py`, and `usercustomize.py` members
are rejected before target creation. No pip, index access, network, cache,
user-site, system-Python lookup, or dependency resolution exists. The nine
direct pinned dependencies remain mandatory; the complete lock may additionally
contain bounded reviewed transitive/platform wheels, and the installed set must
equal that full lock.

Wheel payload, aggregate capture, member count, per-member expanded bytes,
per-wheel expanded bytes, compression ratio, and supported compression are
fixed before extraction. Runtime entry count, per-file bytes, total bytes,
path bytes, and path depth are also fixed. Wheel extraction and Runtime hashing
are bounded and streaming; resource overflow fails before unsafe allocation or
disk growth. EOCD/central-directory bounds run before `ZipFile`, and directory
entry counts are bounded before sorting.

After an empty create-only Runtime root is opened, the private Runtime-tree
window streams only the already reviewed CPython files from their held source
handles into create-only target files, immediately downgrades each completed
file to a read-only write/delete-blocking handle, and never executes the
mutable source namespace. The same window rejects reparse/junction entries and
alternate data streams. Every wheel member and the dependency lock are created
relative to held child-parent handles, added to the expected manifest, and
held against replacement or writes. Exact scans reject every extra, missing,
or changed file or directory. Before target execution, the builder streams the
complete approved `Lib/encodings` package from held source handles into one
bounded deterministic ZIP_STORED `managed-startup.zip`. The archive is
create-only, held, exact-tree bound, and self-hashed by the new Runtime.
Code-fixed `python312._pth` and `python._pth` sentinels are then published
create-only with ordered `managed-startup.zip`, `Lib`, and `DLLs`, no
`import site`, and reopened read-only against write/delete sharing. CPython
therefore resolves its pre-script `encodings` package from an immutable archive
whose namespace cannot gain transient children. Source copies containing
startup hooks are rejected; archive or sentinel collision fails before
execution, and later replacement is blocked.
A recursive Windows directory-change
guard watches the Runtime parent before the complete installed tree is sealed,
remains pending through self-verification and receipt construction, covers
child and NTFS stream changes, and linearizes success only when cancellation
wins. Exact scans also require only the default Runtime-root stream. Even a
transient add/verify/remove or root-ADS change therefore returns no receipt.

The target Runtime executable performs verification under fixed
`-X frozen_modules=on -I -B -S`. It
reports only
canonical content-free evidence for exact Python, SQLite, dependency-lock,
installed-set, and import fingerprints. Before the script takes control, the
fixed `-X` mode guarantees `codecs` resolves through CPython's FrozenImporter;
the new Runtime explicitly proves `_imp.is_frozen("codecs")`. Its verifier
imports only the CPython built-ins `sys`, `nt`, `_sha2`, and `_imp`; an audit
hook rejects every later import,
so a transient Python package below an allowed target directory is never
executed. A transient `Lib/codecs/__init__.py` therefore also cannot execute.
The executable hashes itself, the exact `_sqlite3.pyd` and
`sqlite3.dll` target binaries, `managed-startup.zip`, the dependency lock, and
exact installed import leaves. The builder compares the SQLite binary hashes to the approved,
write/delete-blocked source-tree entries and parses only bounded expected
`METADATA` leaves while independently rejecting extra distribution metadata.
Installed package code is never imported or executed. The builder rejects any evidence not
produced by the exact newly published executable and independently rereads
the target tree. Target collisions and all partial builds are retained.
Runtime stdout is read incrementally into a fixed-cap buffer. Overflow or
timeout terminates the child and returns only the fixed content-free failure
code; process output is never first accumulated without a bound.

### 8.4 Stopped SQLite publication

`StoppedDatabaseCopier` accepts only a strict content-free stopped-service
receipt bound to the same operation, Profile, master, service role, database
source identity, and authorization. Before any destination create, it opens
the source with Windows sharing that permits reads but denies write/delete
sharing. That handle remains held while sidecars are checked, the complete
source is copied, the destination is flushed, hashes are compared, and the
source handle identity and hash are rechecked. After target verification and
target-handle close, one final sidecar/hash/identity gate runs before the
source handle is released and success can return.

The exact `-wal`, `-shm`, and `-journal` sibling roles are checked only for
presence. Any present or unreadable sidecar fails. Integrity uses SQLite
read-only/query-only verification without reading application rows. No
checkpoint, sidecar deletion, source mutation, schema/content export, repair,
or retry exists. The destination is create-only; copy or verification failure
retains any partial target.

### 8.5 Reviewed CRX publication

The CRX review binds source identity, profile role, CRX format version,
expected size, and SHA-256. The publisher holds and rereads the source,
validates the CRX header, creates the target once, copies bytes, flushes the
destination, and verifies exact size/hash plus unchanged source identity. Both
source and target handles remain held through receipt construction, a final
target reread, and final identity verification.

No build, signing, install, load, unpack, browser-profile access, mailbox-page
access, alternate target, overwrite, repair, or cleanup capability exists.

### 8.6 Deterministic Config publication

Config input is a closed mapping whose only variable keys are
`EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS` and `EMAIL_AGENT_LOG_LEVEL`. The
publisher adds code-fixed provider-disabled values, validates the allowlisted
types and domains, sorts and canonicalizes the complete mapping, and requires
the exact profile-bound expected size and SHA-256 before create-only
publication and durable reread.

Unknown, secret, provider-enable, mailbox, vault, private, credential, path,
token, key, or dynamic fields fail. The module has no environment-file,
process-environment, registry, credential-store, clipboard, hidden-input,
mailbox, vault, private-knowledge, provider, or arbitrary reader import.

### 8.7 Receipts, failures, and real lock

All four receipts are strict immutable values containing only schema/type,
fixed status, operation/profile/master/authorization fingerprints, fixed
role, input/observation fingerprints, allowlisted counts, and their receipt
fingerprint. They contain no paths, commands, exception text, source bytes,
database rows, filenames, domains, Config values, package names, credentials,
or private content.

The phase returns a fingerprinted receipt set only when the four complete
typed receipt mappings bind the same operation, Profile, master, and
authorization in fixed order. Parsing independently rebuilds all receipts,
checks the top-level chain, and recomputes the set fingerprint. Receipts are
journal-compatible evidence only and never authorize effects. Failures expose
only fixed codes and leave every partial publication in place for later
failed-Container handling.

The real constructor accepts only an exact
`CutoverExecutionAuthorizationV1`, validates the fixed `execute` context, and
still returns `BLOCKED_NO_APPROVED_COMMAND` before Issue #39. Missing, test,
wrong-type, wrong-phase, expired, malformed, or mismatched authorization is
blocked.

### 8.8 Immutable scope and handle-relative target creation

Review snapshots every path and Config value into an immutable private
scenario. Each publication reopens and holds the sandbox root, marker, and
exact target parent, then creates the absent target relative to that parent
handle with `NtCreateFile(FILE_CREATE)`. Target handles deny replacement;
created file handles also deny concurrent writers through final reread and
identity verification. The operation fingerprint binds every target name as an
opaque hash. Caller mutation, parent replacement, reparse drift, collision, or
native close failure collapses to a fixed content-free code.
Unsafe Windows single-component names, including alternate-stream syntax,
reserved devices (including `COM¹/²/³` and `LPT¹/²/³` aliases), controls,
separators, wildcards, and trailing dot/space, fail before native creation.

## 9. Data structure or interface changes

### Database changes

None.

### API changes

Internal synthetic-only Python contracts and a locked real constructor. No
HTTP, CLI, browser, service, or scheduled entry point.

### AI output JSON changes

None.

### Prompt changes

None.

## 10. Security and privacy checks

- [x] No real Runtime, SQLite, CRX, Config, service, browser, repository,
  worktree, ACL, provider, mailbox, credential, vault, private store, or
  private data is accessed by the publication phase.
- [x] Every executable publication and verification is confined to a
  caller-owned synthetic Windows sandbox.
- [x] Runtime input, wheels, dependency lock, CRX, SQLite, and Config are
  exact profile-bound selections.
- [x] Network, system Python, user-site, user cache, live resolution, legacy
  venv reuse, environment, registry, clipboard, hidden input, and private
  readers are unavailable.
- [x] No replace, repair, delete, checkpoint, cleanup, signing, install, load,
  alternate target, or partial-publication rollback capability is added.
- [x] Providers remain disabled and no mailbox or private-data capability is
  added.

## 11. Prompt injection protection

Not applicable to email or AI input. Manifests, wheel metadata, filenames,
CRX bytes, SQLite metadata, Config fields, process output, and observations
are untrusted. They are accepted only through closed schemas, fixed parsers,
exact allowlists, bounded canonical encodings, and opaque fingerprints; none
is interpreted as an arbitrary command or instruction.

## 12. Acceptance criteria

1. Every Issue #57 acceptance criterion is covered by a focused executable
   test or exact mechanical guard.
2. `ManagedActivationPhase` receives only the four narrow adapters and
   produces the exact same-operation/profile/master receipt chain.
3. Runtime publication uses only an approved, complete canonical-tree
   manifested Python 3.12.13 source distribution and exact
   complete dependency lock plus hash-locked offline wheelhouse, installs only
   captured reviewed bytes, creates the final target once, and proves
   Python/SQLite/lock/complete-installed/import evidence through the new
   Runtime.
4. Runtime network, system-Python, user-site/cache, startup hook, unreviewed
   wheel, live resolution, legacy venv, path-swap race, child junction/reparse,
   alternate data stream, extra/missing tree member, drift, collision, and
   partial-build cases fail closed without cleanup. Source-tree drift after
   authorization fails before code execution; wheelhouse/aggregate and
   subprocess-output exhaustion fail before unbounded collection or buffering.
5. Database publication requires exact stopped-service evidence and a held
   write-blocking source handle; sidecars, lock failure, integrity failure,
   source drift, collision, copy mismatch, post-target-verification sidecar,
   and flush failure fail closed.
6. CRX publication holds source and target through the final reread and is
   exact profile/identity/format/hash/size create-only copy; it cannot build,
   sign, install, load, or access browser/mailbox state.
7. Config bytes are deterministic, canonical, provider-disabled, non-secret,
   profile-bound, and independent of every legacy/dynamic secret source.
8. Every partial or failed publication is retained; no target is overwritten,
   deleted, repaired, or silently replaced.
9. Immutable scope snapshots, held target-parent handles, handle-relative
   `NtCreateFile(FILE_CREATE)`, and concurrent-writer denial prevent caller or
   parent retargeting during publication.
10. Receipts, results, repr, stdout, stderr, logs, and errors remain
   content-free.
11. The real constructor remains locked without exact execution
    authorization and before a later approved Issue #39 command.
12. Windows sandbox, Linux portable-contract, focused, affected, full,
    constraints, compile, frontend syntax, manifest, leakage, maintenance,
    diff, and dual-axis review gates pass.

## 13. Test plan

- TDD vertical slices: receipt contracts; exact adapter bundle; Runtime
  manifest/lock/wheel policy; Runtime create/self-verify; database stop/handle/
  sidecar/integrity/copy; CRX review/copy; Config schema/canonical publication;
  complete phase; partial retention; real lock; architecture/leakage.
- Run the focused Issue #57 suite after every slice.
- Run affected Issue #37 and Issue #51 through #56 suites plus ContainerAudit,
  architecture, static, mechanical, status, documentation, transport,
  leakage, and maintenance tests.
- Run `python -B -m unittest discover -s tests`.
- Run `python -B -m compileall -q backend scripts tests`, every frontend
  JavaScript file through `node --check`, and parse the extension manifest.
- Regenerate the project status, rerun full tests and maintenance, then
  perform parallel Standards and Spec review from the exact fixed point.

## 14. Rollback plan

Before publication, remove or repair only Issue #57 allowlisted files in this
isolated worktree. Tests retain synthetic failed publications until
independent assertions and then dispose only the caller-owned sandbox parent.
No real host state exists to reverse. After publication, a normal Git revert
of the Issue #57 commit is sufficient.

## 15. Questions requiring human confirmation

None. Issue #57 and this request fix the synthetic seams and safety
boundaries. Any real command composition, authorization issuance, service
activation/recovery, Issue #58/#59 work, cleanup, or merge needs separate
approval.

## 16. Pre-execution checklist

- [x] Read `$implement`, `$tdd`, `$code-review`, and GitHub workflow rules.
- [x] Read `AGENTS.md`, `CONTEXT.md`, status, task-brief, tooling,
  architecture, linter, mechanical, CI, security, and decision rules.
- [x] Live-verified Issue #57, parent #50, closed #55/#56, and exact remote
  master.
- [x] Inventoried and preserved the dirty root and every existing worktree.
- [x] Created a clean sibling worktree and `codex/` branch from the exact SHA.
- [x] Fixed the TDD public seams and confirmed no real host/private capability
  is required.

## 17. Remote provider private-context checklist

Not applicable. Provider input, runtime knowledge, budgets, routes, and public
schemas are unchanged. All providers remain disabled.

## 18. Administrator stage-evaluation checklist

Not applicable. No private-evaluation staging surface is imported or invoked.

## 19. Final dataset build and interactive judge checklist

Not applicable. No dataset, provider judge, TTY workflow, or report is opened.

## 20. Bounded corpus-to-runtime handoff checklist

Not applicable. Mailbox synchronization and current-click evidence remain
unchanged.

## 21. Repository placement and operational layout checklist

- [x] No real Container, Runtime, database, CRX, Config, service, browser,
  Repository Root, worktree, ACL, or private zone is accessed or changed.
- [x] Exact sandbox authorization and opaque bindings prevent arbitrary path
  or target mutation.
- [x] Runtime, database, CRX, and Config publication are create-only and
  preserve all partial/failed targets.
- [x] No capability crosses into repository/worktree, service, ACL, mailbox,
  provider, vault, credential, private-data, or cleanup domains.
- [x] The real constructor remains blocked before later composition approval.
- [x] Issues #58/#59, #38/#39, and parent #50 remain unchanged.

## 22. Post-execution record

- Issue #57 implementation is complete in the isolated
  `codex/issue-57-managed-activation` worktree from exact governing master
  `7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd`.
- TDD evidence includes 73 final focused tests. The Windows sandbox regressions
  prove zero marker execution for transient `sitecustomize`, `hashlib`,
  pre-script `encodings.aliases`, and frozen-`codecs` package injection.
- The affected Issue #37 and #51-#56 group passed 354 tests. Final architecture,
  static, mechanical, transport, documentation, and status constraints passed
  143 tests.
- The final full suite passed 2,307 tests with 3 skips in 1,890.707 seconds.
  Compileall, frontend JavaScript syntax, extension manifest parsing,
  `git diff --check`, maintenance, and the tracked-plus-untracked repository
  leakage scan also passed; leakage count was zero.
- Final Standards and Spec reviews are clean with no P1, P2, or P3 findings
  after repairing target namespace, pre-script `encodings`, and frozen
  `codecs` startup boundaries.
- No real Runtime, SQLite, CRX, Config, service, browser, mailbox, provider,
  credential, vault, private data, repository/worktree, or ACL operation ran.
  Synthetic receipts and tests remain evidence only, not live authority.
- Remote baseline/Issue revalidation, explicit allowlist staging, commit, push,
  ready-for-review PR, and CI results are delivery gates and are reported in
  the PR and final handoff; merge and adjacent issues remain unauthorized.
