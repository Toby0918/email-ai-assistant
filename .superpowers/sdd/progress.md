# Option C Multimodal Development Progress

Updated: 2026-07-17
State: TASK 9 SEMANTIC ACCURACY REPAIR IN PROGRESS - LIVE SMOKES DO NOT CLOSE SEMANTIC GATES

## Resume location

- Repository: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant`
- Isolated worktree: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.worktrees\multimodal-plan-c`
- Branch: `codex/multimodal-plan-c`
- Base commit: `9bf17e3 fix: close mailbox rollout release gates`
- Integration target after completed verification: local `master`, then push `master` only.

## User-owned state to preserve

- Root checkout is on `master`.
- Root checkout contains an unrelated user modification in `docs/operations/deployment_notes.md`.
- Do not overwrite, reset, checkout, stash, or otherwise modify that root-checkout file.
- The isolated worktree was clean before this task started.

## Approved scope

The user approved option C:

- OpenAI `gpt-5.6-sol` as the main single-call multimodal provider.
- Current visible email text/thread plus selected business inline images and supported visible attachments.
- Signature portraits, logos, icons, tracking pixels, hidden/external/ambiguous images excluded locally.
- DeepSeek retained as an explicitly enabled text-only fallback.
- Deterministic rules remain the final fallback.
- Exact order IDs, dates, amounts, quantities, and tracking values remain locally authoritative.
- The operator separately authorized the Task 9 synthetic API smoke and one
  current-clicked-email read-only check. Navigation, mailbox scanning, and
  sending remain prohibited.
- No mailbox traversal, scanning, navigation, automatic action, or access to any message other than the one the user clicks.
- Cost is not a constraint, but credentials and real content must never be printed, logged, committed, or exposed to Codex output.

## Completed in this session

1. Read project instructions, project status, tooling, architecture, linter, task-brief, documentation, security, prompt, schema, API, and prior provider decision material.
2. Read and activated the Superpowers planning, worktree, TDD, subagent-driven, and verification workflows.
3. Created the isolated worktree and branch listed above.
4. Verified the correct locked runtime:

   - Python: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`
   - Required `PYTHONPATH`: project root `.venv\Lib\site-packages` plus `C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages`
   - Python 3.12.13
   - openai 2.45.0
   - beautifulsoup4 4.15.0

5. Baseline full suite passed before changes:

   ```text
   Ran 1175 tests in 95.559s
   OK (skipped=1)
   ```

6. Completed read-only subagent investigations:

   - Tencent root cause: real message is in a visible same-origin `mainFrame`; resource collection currently rejects `extraction.document !== document`, and unknown body selectors cause empty automatic extraction while manual selection bypasses that check.
   - Provider contract: pinned OpenAI SDK supports Responses API, image/file input, `store=false`, timeout, and JSON-object/structured output. Existing private envelope and safety merge can be reused. Dynamic evidence-map compatibility means first release should keep JSON-object output plus strict local validation rather than claiming unverified strict JSON Schema support.
   - Existing DeepSeek remains text-only.

7. Added planning/governance documents only:

   - `docs/operations/multimodal_current_email_analysis_task_brief.md`
   - `docs/decisions/0007-multimodal-current-email-analysis.md`
   - `docs/superpowers/plans/2026-07-16-multimodal-current-email-analysis.md`

8. Completed Task 1 with strict TDD:

   - Focused RED: 96 tests, 19 expected failures for missing config fields,
     stale budgets/timeouts, and missing governance canaries.
   - Focused GREEN: 96 tests passed.
   - Downstream stale-contract regression: 89 tests passed after aligning fake
     clocks and legacy documentation assertions with the approved contract.
   - Final full suite: 1,181 tests passed with one expected skip.

9. Locked the Task 1 boundaries:

   - providers and text fallback remain disabled by default;
   - OpenAI model allowlist is exactly `gpt-5.6-sol` with a 35-second cap and no
     configurable endpoint;
   - normal runtime budgets are frontend/backend/OpenAI/DeepSeek/fallback/reserve
     = 60/55/35/10/12/5 seconds;
   - the separate private-evaluation runner remains 13 seconds;
   - the approved persistent disclosure is recorded in governance docs while
     frontend markup remains deferred to Task 7.

10. Committed the Task 1 implementation as
    `79da065b2efda46f5490babe36966f2aa9560082` (`feat: define multimodal
    provider boundaries`). Its fresh task review approved both specification
    compliance and code quality. The sole Minor finding was this progress
    record's stale pre-review/uncommitted wording; documentation correction
    `4250203f74016f342d77ab7d0ba017ba2456c6fa` passed clean re-review.

11. Completed Task 2 with strict TDD and fresh review:

    - Initial focused RED: 96 tests, 10 expected failures for the missing
      resolver/manifest entry, legacy automatic body/thread extraction,
      header/body ambiguity, and stale-context discard.
    - Review-derived RED cases covered message-authored subject/header/body and
      history lookalikes, verified metadata ownership, structured sibling
      history, document-level background history, and pure aggregate proof.
    - Final extension focus after review hardening: 120 tests passed.
    - Final full suite: 1,209 tests passed with one expected skip.
    - All three changed JavaScript files passed `node --check`; manifest JSON
      parsing and `git diff --check` passed.

12. Locked the Task 2 boundaries:

    - only the verified top document or exactly one unique visible, accessible,
      same-origin Tencent `mainFrame` can be selected;
    - verified header metadata remains authoritative, unowned or ambiguous
      history falls back to the verified current body, and pure thread-only
      aggregate roots require complete ownership proof;
    - document/frame/subject/header/current-body identity and text are
      revalidated after collection, and stale results return no payload;
    - no recursive frame traversal, `all_frames`, host-permission expansion,
      mailbox traversal, Task 3 resource classification, provider call, or live
      mailbox access was introduced.

13. Fresh Task 2 review required two fix waves. Commit
    `32904cc3729890271f1db84182e93b75b204dffa` closed body-ownership,
    rendered-visibility, and genuine-read-evidence findings. Commit
    `fa31c6f3117e8154b8b98b04ff5f5450cc9e6f63` preserved visible zero-width
    `<br>` line breaks without weakening frame/body geometry gates. Final
    re-review verdict: `CLEAN`, with no Critical, Important, or Minor findings.

14. Completed Task 3 with strict TDD:

    - Pure-classifier RED: all 16 new cases failed because the classifier did
      not exist; the same 16 cases passed after the local deterministic
      classifier was added.
    - Integration RED covered the missing business-photo payload, stale
      context discard, changed resource identity, verified `mainFrame`
      collection, and manifest load order. The combined focused surface then
      passed 97 tests.
    - A strict repeated-CID regression first reproduced two differently signed
      URLs for the same repeated image, then passed after identity matching
      included the opaque content ID.
    - Independent review reproduced four Important gaps. The exact four-case
      set failed before production fixes and passed afterward. The final
      browser-extension surface passed 158 tests.

15. Locked the Task 3 resource boundary:

    - only approved visible attachment links and large current-body business
      images from the verified Task 2 document context may become candidates;
    - known thread/history media, sibling avatars, signatures, repeated images,
      hidden, zero-layout, offscreen, external, and ambiguous media are rejected
      before fetch;
    - accepted inline images use only opaque `inline-image-N.ext` names and the
      existing four-field `attachment_files` shape;
    - candidate discovery is iterative and bounded by 20 candidates, 200
      visited nodes, depth 20, and the shared 20-second resource-phase deadline;
    - fetch remains capped at 5 resources, 10 MiB each, and 25 MiB total, with
      redirect, context, and resource-identity revalidation.

16. Fresh Task 3 re-review verdict: `CLEAN`. All four earlier Important
    findings are closed; no Critical or Important finding remains. All three
    changed JavaScript files passed `node --check`, manifest parsing passed,
    and the correct-environment full suite passed 1,235 tests with one expected
    skip.

17. Root fresh review of commit `187235c33c1e583e0985531fefc860c88f41b7d4`
    found two additional Important boundaries: an unbounded recursive resource
    pre-scan and approved profile links treated as attachments. Their exact
    tests each failed before production changes. The fix reuses the already
    revalidated Task 2 context, removes recursive resource discovery, shares
    the deadline/200-node state from the first candidate node, and requires
    positive attachment-control evidence. Re-review caught and closed one
    visited-set regression for fallback current-body images. The five-case
    closure set passed, the extension surface passed 161 tests, and final fresh
    re-review reported `CLEAN` with no remaining Critical or Important finding.
    The post-review correct-environment full suite passed 1,238 tests with one
    expected skip.

18. Completed Task 5 with strict TDD:

    - added the provider-neutral `ModelAnalysisRequest` and an isolated OpenAI
      Responses multimodal client using the fixed official endpoint;
    - preserved the DeepSeek Chat Completions payload and text-only behavior;
    - kept deidentified text as the privacy-gate prerequisite and routed model
      output through the existing private-output gate;
    - used one offline fake client with a forbidden Files API and no network,
      provider credential, mailbox, real email, or real attachment access;
    - focused client/prompt/privacy verification passed 74 tests;
    - the correct-environment full suite passed 1,303 tests with one expected
      skip before the final records-only update.

19. Closed the Task 5 fresh-review findings with strict RED-to-GREEN evidence:

    - fixed the model-text contract at a nonblank 512 KiB maximum, above the
      bounded legitimate prompt worst case, and revalidated placeholder and
      residual privacy safety immediately before dispatch;
    - revalidated exact media type, count, per-asset and aggregate bytes,
      duplicate object identity, and duplicate provider filename immediately
      before serialization while preserving repeated source IDs;
    - built Base64 content from temporary mutable snapshots before client
      construction and wiped the raw snapshots in `finally` on success and
      fixed failure paths;
    - failed closed on all four unsupported ambient SDK variables and required
      an exact nonblank string API key;
    - final focused verification passed 85 tests, static/architecture/mechanical
      verification passed 56 tests, and the correct-environment full suite
      passed 1,315 tests with one expected skip.

20. Closed the final Task 5 metadata-subclass re-review finding:

    - one RED test produced 15 expected failures across five media metadata
      fields and custom `str` subclass formatting, conversion, and equality;
    - dispatch now requires exact `str` values for `source_id`,
      `provider_filename`, `mime_type`, `kind`, and `detail` immediately before
      post-init revalidation and snapshot creation;
    - the plain repeated-source-ID case remains accepted;
    - final focused verification passed 86 tests, static/architecture/mechanical
      verification passed 56 tests, and the correct-environment full suite
      passed 1,316 tests with one expected skip.

21. Closed the targeted Task 5 deleted-slot fixed-error seam:

    - one six-slot RED produced five raw `AttributeError` errors for deleted
      metadata slots while the deleted-buffer control already failed closed;
    - metadata reads and exact-string validation now occur inside the existing
      fixed-error `try` after temporary wipe-buffer initialization;
    - all six deleted-slot cases map to content-free `invalid_request`, the 15
      subclass probes remain rejected, and plain repeated source IDs remain
      accepted;
    - final focused verification passed 87 tests, static/architecture/mechanical
      verification passed 56 tests, and the correct-environment full suite
      passed 1,317 tests with one expected skip.

22. Final targeted Task 5 re-review verdict: `CLEAN`.

    - All six deleted-slot cases now map to content-free `invalid_request`
      before client construction.
    - Exact plain-string metadata enforcement remains closed against custom
      `__format__`, `__str__`, and `__eq__` subclasses.
    - Legitimate repeated plain `source_id` values remain supported for
      multiple Office embedded images.
    - The final focused matrix passed 87 tests; Task 6 was not started during
      review closure.

23. Completed the Task 6 implementation through strict offline TDD:

    - OpenAI now uses the provider-neutral multimodal private request and the
      existing envelope, evidence, merge, exact-fact, timeline, language,
      schema, attachment-membership, and human-review gates;
    - one explicitly enabled DeepSeek text fallback is eligible only after an
      OpenAI failure with at least 12 seconds remaining, receives only its own
      text-only source view, and reports the actual terminal provider/model;
    - visual grounding is restricted to source-bound qualitative business
      observations and rejects identity, traits, exact facts, URLs,
      hidden/tool instructions, commitments, and outcomes;
    - final focused verification passed 148 tests, static/architecture/
      mechanical verification passed 56 tests, and the correct-environment
      full suite passed 1,328 tests with one expected skip;
    - no network, provider, browser, mailbox, real content, key, `.env`, public
      schema, SQLite schema, root checkout, merge, or push was touched.

24. Closed the independent Task 6 review findings through a second strict TDD
    cycle:

    - visual authority is now limited to the matching attachment augmentation,
      every visual text leaf requires matching owner/source evidence, and a
      finite full-leaf contract rejects names, protected traits, commands,
      URLs, numbers, identifiers, quantities, commitments, and outcomes;
    - mixed PDF/Office sources retain text grounding plus a separate visual
      capability without changing the independently rebuilt DeepSeek text-only
      source registry;
    - mapped OpenAI private-artifact output blocks DeepSeek with content-free
      diagnostics, while ordinary invalid provider/schema output still permits
      the explicitly configured single text fallback;
    - the final DeepSeek eligibility and timeout use one clock sample; 11.9 and
      11.999 seconds make zero calls, while exactly 12 seconds yields a bounded
      seven-second timeout with the response margin intact;
    - the review-fix focused matrix passed 223 tests, the architecture/static/
      mechanical/browser-static matrix passed 88 tests, and the full suite
      passed 1,338 tests with one expected skip.

25. Closed the second fresh Task 6 review findings through another bounded TDD
    cycle:

    - the OpenAI prompt and visual validator now render and enforce one finite
      canonical sentence contract for attachment summary/key-fact leaves;
      noncanonical variants, appended semantics, digits, and smuggling fail
      closed while the prompt retains 290 characters of headroom;
    - in any multimodal run, every cited text or hybrid source must directly
      contain the complete normalized global claim, and visual sources never
      ground global fields; pure-text compatibility remains unchanged;
    - fake thread evidence and unsupported identity/protected-trait/damage
      claims are rejected end to end, while unsupported reply/action fields
      fall back independently without discarding supported fields;
    - the second-fix focused matrix passed 101 tests, the expanded Task 6/
      provider/privacy matrix passed 264 tests, the architecture/static/
      mechanical/browser-static matrix passed 88 tests, and the fresh full
      suite passed 1,343 tests with one expected skip.

26. Closed the cross-language multimodal grounding gap through a third bounded
    Task 6 TDD cycle:

    - only `summary` and `priority_reason` may use one of nine fixed Chinese
      public templates when English or Chinese text supplies the evidence;
    - each cited text or hybrid source must independently contain one bounded,
      same-clause combination for the same local claim code; negated, distant,
      cross-clause, unrelated, mixed, paraphrased, and pure-visual evidence
      continues to fail closed;
    - no provider envelope, public HTTP, SQLite, or persistence schema changed,
      and only boolean local matching results leave the private bridge;
    - the OpenAI prompt and validator share the exact template list while the
      prompt remains 7,743 of 8,000 characters, retaining 257 characters;
    - prompt/grounding/result-safety verification passed 109 tests, the
      expanded Task 6/provider/privacy matrix passed 295 tests, the
      architecture/static/mechanical/browser-static/documentation matrix
      passed 105 tests, and the full suite passed 1,351 tests with one expected
      skip.

27. Closed the fourth fresh Task 6 adversarial findings through a bounded TDD
    cycle:

    - all nine cross-language templates now use independent directional phrase
      contracts with bounded gaps rather than unordered same-clause keywords;
    - cancellation, refusal, inability, negation, withdrawal, completed
      outcomes, comma/colon boundaries, NEL, Unicode line/paragraph separators,
      default-ignorable marks, and mixed-script obfuscation fail closed;
    - multimodal global literal claims now pass a local finite safety gate
      before substring acceptance, rejecting explicit identity/protected-trait,
      tool/shell, digit/exact-fact, completed-outcome, commitment, URL, and
      unsafe-operation text while preserving pure-text compatibility;
    - focused verification passed 113 tests, the expanded Task 6/provider/
      privacy matrix passed 287 tests, the architecture/static/mechanical/
      browser/documentation matrix passed 228 tests, and the full suite passed
      1,355 tests with one expected skip;
    - the unchanged OpenAI multimodal prompt remains 7,743 of 8,000 characters,
      retaining 257 characters of headroom.

28. Closed the fifth fresh Task 6 adversarial findings through a bounded TDD
    cycle:

    - cross-language request authority now requires either a sentence-start
      direct imperative or a sentence-start finite active role immediately
      followed by active `requests`/`asks` wording and a bounded directional
      target; arbitrary-position request/ask matching was removed;
    - contracted and auxiliary request negation, cancellation, conditional and
      reference/history/example prefixes, and punctuation-separated target
      smuggling fail closed across all nine templates; safe anchored quality
      statements remain available without reopening request matching;
    - multimodal global literal claims now reject finite identity/name-role
      assertions, the complete protected-trait vocabulary, and any independent
      shell/command/script/tool mention while ordinary supported Chinese prose,
      pure-text behavior, canonical visual leaves, and hybrid text grounding
      remain unchanged;
    - fixed RED verification produced 40 expected failures, followed by an
      11-failure identity/quality expansion; both fixed targets passed after the
      bounded implementation;
    - a final one-failure RED kept non-assertive `contact` use available in an
      English external draft while the finite identity assertions stay closed;
    - focused grounding/result-safety/prompt verification passed 118 tests,
      the expanded Task 6/provider/privacy matrix passed 344 tests, the static/
      architecture/mechanical/browser/documentation matrix passed 251 tests,
      API/schema/database verification passed 67 tests, and the full suite
      passed 1,360 tests with one expected skip;
    - the unchanged OpenAI multimodal prompt remains 7,743 of 8,000 characters,
      retaining 257 characters of headroom.

29. Closed the production-registry integration gap through a sixth bounded
    Task 6 TDD cycle:

    - the exact request-local registry serializes the first body line as
      `body = <text>`; all nine cross-language templates were therefore
      unreachable through the production path even though raw fixtures passed;
    - a fixed production-registry RED used real `ThreadSource`,
      `TimelineBuild`, and `build_deepseek_untrusted_context` construction and
      produced nine expected template failures plus one end-to-end merge
      failure;
    - only a caller holding explicit thread-source provenance may remove one
      exact normalized `body = ` prefix from a clause; attachment sources,
      ordinary untrusted text, metadata fields, and a second user-supplied
      prefix remain ineligible;
    - provider-visible grounding text, prompts, private/public envelopes, HTTP,
      SQLite, and persistence schemas are unchanged;
    - focused verification passed 121 tests, the expanded Task 6/provider/
      privacy matrix passed 356 tests, the static/architecture/mechanical/
      browser/documentation matrix passed 228 tests, API/schema/database passed
      67 tests, and the full suite passed 1,363 tests with one expected skip.

30. Completed Task 7 and its final adversarial review gate:

    - commit `cb85dc2` added the exact persistent multimodal disclosure to both
      frontend surfaces, the 60-second selected-media loading state, the
      task-first 320-pixel layout contract, and fixed content-free engine and
      fallback presentation;
    - commit `ca8a722` closed the two Important review findings by requiring
      own non-accessor error-code properties, own allowlist keys, and one
      frozen own-data engine snapshot reused across the banner, engine field,
      and technical details;
    - inherited properties, `toString`, `constructor`, `__proto__`, mutable
      getters, raw provider labels, private diagnostics, and raw backend error
      messages all fail closed without being rendered;
    - final verification passed 72 focused frontend tests, 66 architecture/
      mechanical/static/leakage tests, and 1,377 full-suite tests with one
      expected skip; all changed JavaScript passed `node --check` and
      `git diff --check` passed;
    - final independent adversarial re-review verdict: `CLEAN`.

31. Completed Task 8 documentation synchronization and offline release gates:

    - documentation commits `d915894`, `5ac408f`, and `99e9ed4` align the
      active Option C contracts, clarify backend-compatible engine labels
      versus the strict Task 7 UI allowlist, record the fixed OpenAI payload,
      and preserve OpenAI-to-eligible-DeepSeek-to-rules ordering;
    - fresh review of those documentation commits and the final independent
      release review are clean, with no Critical or Important findings;
    - all eight changed JavaScript files passed `node --check`; the
      documentation/architecture/static/mechanical/leakage/maintenance matrix
      passed 119 tests; the multimodal focused matrix passed 564 tests;
    - the full suite before project-status generation passed 1,390 tests in
      137.275 seconds with one expected skip;
    - project status was generated with stage
      `multimodal_current_email_offline_ready_live_pending`; the 119-test gate
      matrix passed again afterward, and the post-generation full suite passed
      1,390 tests in 136.257 seconds with one expected skip;
    - the repository leakage scan exited 0, maintenance scan with
      `--fail-on-high` exited 0 with no findings, and `git diff --check` was
      clean;
    - the first focused command incorrectly referenced a nonexistent worktree
      `.venv` and produced five `openai`/`bs4` import errors. Correcting
      `PYTHONPATH` to the existing root `.venv` required no installation and
      the unchanged 564-test matrix passed;
    - no provider, browser, mailbox, real content, key, `.env`, network, or
      local service was accessed. The user-owned deployment-notes BOM
      difference was not touched, and review-package files remain unstaged.

## SDD ledger

Task 1: complete (commits 9bf17e3..4250203, review clean)
Task 2: complete (commits e45aa2f..fa31c6f, review clean)
Task 3: complete (commits 9e881d4..6cb7617, review clean)
Task 4: complete (commits 66454d9..8cb9810, review clean)
Task 5: complete (commits b2dbbec..559b595, review clean)
Task 6: complete through 2a114ce (review clean)
Task 7: complete (commits cb85dc2 + ca8a722, review clean)
Task 8: complete (commits d915894 + 5ac408f + 99e9ed4, offline gates passed; review clean)
Task 9: in progress (synthetic OpenAI visual gate passed; current-clicked Tencent smoke pending)

## Historical Task 1 boundary

- Task 2 was not started.
- No API call was made.
- No browser, mailbox, email, image, attachment, key, or `.env` was accessed.
- No merge or push was performed.
- No project-status generator or maintenance scan was run after the planning-doc additions.

## Task 1 commit and review state

Task 1 implementation, tests, governance updates, and planning records are
committed at `79da065b2efda46f5490babe36966f2aa9560082`. The fresh review approved
specification compliance and code quality. Progress correction
`4250203f74016f342d77ab7d0ba017ba2456c6fa` addresses its sole Minor finding
and passed clean re-review.

## Task 2 boundary

- Task 2 implementation, tests, and progress records are complete; final fresh
  re-review is clean through `fa31c6f3117e8154b8b98b04ff5f5450cc9e6f63`.
- Task 3 was not started.
- No browser, mailbox, real email, image, attachment, provider, key, `.env`, or
  live API was accessed.
- No root-checkout file, merge target, remote branch, or user-owned dirty file
  was modified.
- Project-status generation and maintenance/release scans remain deferred to
  the plan's later integration/release-gate task.

## Task 3 boundary

- Task 3 implementation, tests, records, and fresh re-review are complete.
- Task 4 was not started. No backend, provider, prompt, API, SQLite, attachment
  sanitation, or office-media code was changed.
- No browser, mailbox, real email, image, attachment, provider, key, `.env`, or
  live API was accessed.
- No root-checkout file, merge target, remote branch, or user-owned dirty file
  was modified.
- Project-status generation and maintenance/release scans remain deferred to
  the plan's later integration/release-gate task.

## Task 4 boundary

- Task 4 request-local media sanitation, evidence binding, analyzer carrier,
  explicit buffer wiping, and API temporary-file cleanup are implemented.
- The root-review-expanded media/storage/parser/analyzer/API matrix passed 192
  tests. The correct-environment full suite passed 1,291 tests with one expected skip;
  the seven mechanical-rule tests and `git diff --check` also passed.
- Root fresh review of `34a82702d8eddf001190dfd5b71ac01812d139ae`
  identified four Important gaps. Exact RED coverage reproduced detached PDF
  active objects, partial Office-buffer retention on an unexpected exception,
  inconsistent Office raw caps, and local/central ZIP flag mismatch. All four
  are closed by bounded pre-clone/full-object PDF sanitation, shared raw-size
  policy, full local-header flag validation, and wipe-before-reraise handling.
- Follow-up commit `8cb98106deaa3b64d617cd0ca6b6ed3d4f37d6a4`
  passed clean re-review with no Critical, Important, or Minor findings.
- Task 5 was not started. No request builder, provider payload, prompt change,
  provider call, live browser, mailbox, real email, attachment, API key, or
  `.env` was accessed.
- No API response or SQLite schema changed, and no prepared binary or Base64
  enters repr, exceptions, response, persistence, or logs.
- No root-checkout file, merge target, remote branch, or user-owned dirty file
  was modified. Pre-existing untracked review packages remain unstaged.
- Project-status generation and maintenance/release scans remain deferred to
  the plan's later integration/release-gate task.

## Task 6 boundary

- Task 6 implementation, seven review fixes, tests, records, and the final
  independent provenance re-review are complete and clean. Task 7 has not
  started.
- No public HTTP or SQLite schema changed. No provider, browser, mailbox, real
  content, key, `.env`, live smoke, merge, push, or root-checkout file was
  touched.
- Pre-existing untracked review packages remain unstaged. Project-status
  generation and maintenance/release scans remain deferred to Task 8.

## Task 7 boundary

- Task 7 disclosure, status, task-card ordering, fixed engine presentation,
  raw-error suppression, adversarial hardening, tests, and final review are
  complete and clean through `ca8a722`.
- Public analysis fields, HTTP, SQLite, provider routing, prompt behavior,
  mailbox collection, attachment collection, and timeout contracts were not
  changed.
- No provider, browser, mailbox, real content, key, `.env`, live smoke, merge,
  push, project-status generation, or maintenance/release scan was performed.
- Pre-existing untracked review packages remain unstaged. Task 8 is the next
  approved offline documentation and release-gate boundary.

## Task 8 boundary

- Task 8 documentation synchronization, clean documentation review, generated
  project status, and all offline release gates are complete.
- The final independent release review is clean with no Critical or Important
  findings.
- No provider API, browser, mailbox, real email, real media, key, credential,
  `.env`, network, or local service was accessed.
- The root checkout's user-owned `docs/operations/deployment_notes.md` BOM
  difference remains untouched. Pre-existing review-package files remain
  unstaged.
- Task 9 live provider/browser/mailbox smoke is prohibited until separate,
  explicit operator authorization. Offline gate completion is not live-access
  authorization.

## Next action on resume

1. Preserve the root-checkout deployment-notes modification and keep all
   review-package files unstaged.
2. Ask the operator to open one representative message before resuming the
   current-clicked Tencent smoke. Do not navigate, enumerate, scan, or send.
3. Keep providers disabled outside the bounded Task 9 test process.

## Stop condition

The synthetic OpenAI visual gate is complete. Stop the current-clicked Tencent
smoke whenever no single message is already open; never navigate from an inbox
list to select one. Task 9 remains incomplete until that read-only path and the
remaining release gates are completed.

## Task 9 live-smoke diagnostic boundary

- The operator separately authorized one synthetic API smoke and a current-clicked
  message read-only test, with navigation, mailbox scanning, and sending prohibited.
- Backend-only presence checks confirmed both OpenAI and DeepSeek keys are available
  from the ignored root `.env`; no key value entered tool output, logs, or Git.
- The first inline harness stopped before a provider call because the fixed Python
  runtime needed the project and global dependency paths, and Windows spawn cannot
  reload a `<stdin>` main module. A file-backed, synthetic-only ignored runner then
  passed the attachment-worker and temporary-cleanup offline preflight and received
  a clean independent safety review.
- The separately authorized single OpenAI diagnostic retry returned the validated
  rule fallback with fixed diagnostic `provider_http_error` at stage `provider` for
  `gpt-5.6-sol`. Attachment handling completed, schema validation passed, and the
  request-local temporary directory was empty afterward. No raw provider output,
  prompt, media, key, exception detail, or synthetic analysis text was printed.
- Current official OpenAI documentation confirms that `gpt-5.6-sol` supports image
  input, Responses, structured output, low reasoning effort, and the request fields
  used by the client. After the operator confirmed project billing and separately
  authorized one status-only diagnostic probe, `GET /v1/models/gpt-5.6-sol`
  returned HTTP 200. The probe did not read the response body, did not retry or
  follow redirects, and emitted only the status and fixed `model_accessible`
  classification. This rules out missing model visibility for the configured key;
  the failed `POST /responses` smoke remains a request-level rejection to diagnose.
- The operator then authorized continued content-free diagnosis. A synthetic minimal
  `POST /v1/responses` returned HTTP 200, and the complete production instructions
  plus structured text message also returned HTTP 200. Adding only
  `text.format.type=json_object` changed the same request to HTTP 400. The complete
  production parameter set without that legacy format returned HTTP 200 for both
  text-only and one locally generated no-text PNG input. No response body, prompt,
  model output, key, media bytes, or provider exception text was printed or retained.
  This isolated the first live-gate failure to the legacy JSON-object response
  format. After explicit approval, the client omitted `text.format` while
  retaining the JSON-only prompt and all strict local validators.
- The next synthetic run reached a valid provider envelope but omitted visual
  attachment augmentation. Root-cause tracing showed that the internal
  `UNTRUSTED_MEDIA` marker was either absent from the provider prompt or, when
  included directly, correctly rejected by the residual privacy scan.
- The final fix projects that exact internal marker to one fixed, deidentified
  natural-language source description only for OpenAI. DeepSeek still excludes
  visual-only sources, and internal grounding mode is derived from provenance,
  not from matching untrusted text. The OpenAI-only prompt now requires one
  source-bound attachment augmentation with evidence for every leaf when a
  listed observation is visible.
- The final recreated no-text business-photo smoke passed: OpenAI was the
  accepted engine, the public schema was valid, no fallback event occurred,
  one attachment augmentation contained four canonical visual observations
  with four evidence pointers, source binding was valid, and the request-local
  temporary directory was empty afterward.
- One authorized Chrome read-only check found the browser at the inbox list
  with no message open. No email was selected, opened, read, or analyzed; no
  navigation, mailbox scan, or send action occurred. The current-clicked
  Tencent smoke therefore remains pending rather than failed.
- The temporary test service was stopped and its project-external Task 9 data
  directory was removed. DeepSeek live fallback, merge, and push were not
  performed. Task 9 remains incomplete.

## Task 9 current-message extraction repair

- The operator opened one representative Tencent message and clicked Analyze.
  The injected extension returned an empty body, so the backend rejected the
  request before any provider call.
- A content-free structural probe identified the supported host shape as one
  visible `.readmailinfo` header next to `#mailContentContainer.qmbox`, with the
  current body followed by nested complete-header `BLOCKQUOTE` history. No
  message text, identity, attachment name, or provider output was printed or
  retained.
- Test-first fixtures now cover that host shape, oldest-to-newest nested history,
  current-body line preservation, current business-image collection, and
  complete-header historical-image exclusion.
- The adapter, popup, and API client now independently reject an empty current
  body. Empty extraction cannot return `ok:true`, call the backend, or execute
  `fetch`; no whole-page fallback was added.
- The browser-extension discovery suite passes 172 tests; the complete suite
  passes 1,399 tests with one environment skip. JavaScript syntax checks,
  `git diff --check`, and the maintenance/leakage scan pass, and the independent
  vertical review is GO with no Critical or Important findings.
- The live smoke remains incomplete until the operator reloads the unpacked
  extension from this worktree, refreshes the already-open message so the new
  content scripts are injected, and clicks Analyze again. Navigation, mailbox
  scanning, and sending remain prohibited.

## Task 9 current-click live-smoke completion

- The operator reloaded the unpacked extension, refreshed the already-open
  Tencent message, and clicked Analyze. No navigation, mailbox scan, send,
  delete, move, or archive action was performed.
- The newest project-external SQLite projection records `ai_model` with label
  `OpenAI GPT-5.6 Sol`, rather than `rule_fallback`. The same public projection
  contains one attachment insight, a reply draft, and the mandatory human-review
  flag. Optional context metadata is intentionally absent from the public SQLite
  projection and was not treated as a failure.
- The sanitized diagnostics contain no new fallback event for this request.
  Verification inspected only fixed engine/status fields and structural counts;
  no real subject, address, body, attachment name, model output, key, or other
  identifiable email content was printed or copied into the repository.
- The authorized synthetic provider smoke and the authorized current-clicked
  Tencent smoke are now complete. Providers remain disabled outside the bounded
  test service, and the browser extension remains click-only for the currently
  visible message.
- Post-smoke release verification used the pinned Python 3.12.13 runtime and
  passed all 1,404 tests with one environment skip. JavaScript syntax checks and
  `git diff --check` passed, and the fail-on-high maintenance scan reported no
  cleanup findings. The bounded local service health endpoint remained healthy.

## Current-email grounding and attachment repair execution

- Approved plans committed at `470f329` after a clean 1,404-test baseline.
- MOQ Task 1 is in progress under Subagent-Driven Development.
- Per-task base for MOQ Task 1: `470f329c7ef0f058a6052205598f5bf6609b5c0d`.
- Live attachment smoke remains outside the offline execution boundary and
  requires a fresh, explicit operator authorization after Tasks 1-4 are clean.

### MOQ repair task ledger

- Task 1 complete and review-clean through `2cb1652`; controller verification:
  6 focused tests passed and task files are clean.
- Task 2 in progress; per-task base is `2cb1652`.

- Task 2 complete and review-clean through `6c78104`; controller verification:
  166 combined focused and regression tests passed.
- Task 3 in progress; per-task base is `6c78104`.

- Task 3 complete and review-clean through `6bac7c8`; controller verification:
  187 Task 3 tests passed, mechanical limit restored to 299 lines, and the
  full repository suite later passed 1,426 tests with one environment skip.
- Prior verified Plan C working changes were isolated in checkpoint `3d41525`
  after full tests, all extension JavaScript checks, leakage scan, maintenance
  scan, and `git diff --check` passed.
- MOQ Task 4 in progress; per-task base is `3d41525`.

- MOQ Task 4 complete and review-clean through `42f103c`; its latest full gate
  passed 1,427 tests with one environment skip plus maintenance, leakage, and
  diff checks.
- The labeled-MOQ plan is complete.
- Attachment Task 1 in progress; per-task base is `42f103c`.

- Attachment Task 1 complete and review-clean through `0c3a54f`; controller
  verification passed 92 focused tests, both changed JavaScript syntax checks,
  and `git diff --check`. The final frozen gate reported no Critical or
  Important findings.
- Attachment Task 2 in progress; per-task base is `0c3a54f`.

- Attachment Task 2 complete and review-clean through `e0c41b6`; controller
  verification passed 190 browser-extension tests, 49 architecture/static
  tests, both JavaScript syntax checks, and `git diff --check`. The bounded
  re-review reported no Critical, Important, or Minor findings.
- Attachment Task 3 in progress; per-task base is `e0c41b6`.

- Attachment Task 3 complete and review-clean through `5adabf9`; controller
  verification passed the 38-test task matrix, 49 architecture/static tests,
  renderer JavaScript syntax, and `git diff --check`. Independent review
  approved the no-download-to-parsed vertical path and isolated success/failure
  request-temp cleanup proof with no findings.
- Attachment Task 4 in progress; per-task base is `5adabf9`.

- Attachment Task 4 complete and frozen through `3fab43c`; final controller
  verification passed 56 documentation/static/status tests and the 195-test
  Task 4 matrix. The frozen gate found no Critical or Important issues. The
  latest full suite passed 1,452 tests with one environment skip; all extension
  JavaScript syntax checks, leakage scan, maintenance `--fail-on-high`, and
  `git diff --check` passed.
- Offline attachment Tasks 1-4 are complete. Task 5 remains not live-tested and
  requires fresh explicit authorization; no live operation was performed.
- Broad branch review found one documentation-only Important: two historical
  surfaces still described the already-completed bounded Task 9 current-click
  smoke as pending. Strict TDD corrected those surfaces in `440eac9`; the
  bounded re-review approved the fix with no Critical or Important findings.
  Remaining Task 9 gates stay unchecked, while the new Attachment Task 5 remains
  pending, not live-tested, and gated by fresh explicit authorization.
- Final controller verification at `440eac9` passed 1,453 tests with one
  environment skip, all nine browser-extension JavaScript syntax checks, the
  41-test leakage/closeout/maintenance/status matrix, deterministic project
  status generation, maintenance `--fail-on-high`, and `git diff --check`.
  Offline Tasks 1-4 and the final offline branch gate are complete. No browser,
  mailbox, provider, API, navigation, scan, send, or network operation occurred.

### Attachment Task 5 bounded real smoke

- The operator supplied fresh explicit authorization for one current-clicked
  attachment smoke with no navigation, mailbox scan, send action, or content
  output. The verified worktree service started with the existing provider-
  disabled default and a zero-file request-temp baseline.
- The automatic acquisition attempt produced one fixed `resource_unavailable`
  result: one attachment insight was `unavailable`, none were `parsed`, and the
  request-temp file count returned to zero.
- Following the approved Task 5 fallback, the operator selected a supported
  current-message local file through the explicit picker. The final result had
  two attachment insights: one `parsed` manual attachment and one remaining
  `unavailable` automatic candidate. The request-temp file count again returned
  to zero. No filename, subject, address, body, attachment text, summary, draft,
  credential, provider payload, or other identifiable content was inspected or
  recorded here.
- The bounded service was identity-checked by executable, command, and port
  ownership, then stopped. Manual picker acquisition, backend parsing, truthful
  `parsed` status, and request-finally cleanup are live-verified. Automatic
  Tencent control acquisition is not live-verified successful and requires a
  separately authorized content-free diagnostic/fix cycle if it is to be
  pursued further.

### Attachment Task 6 bounded automatic-acquisition repair

- A content-free current-message diagnostic isolated three pre-fetch blockers:
  one exact Tencent legacy wrapper, a rendered attachment anchor below the
  viewport, and absent attachment type metadata. No message or attachment
  content was recorded.
- The operator approved only the bounded offline repair. Commits `6d39860` and
  `baf5d62` implement exact one-wrapper ownership, attachment-only off-viewport
  layout, and one-fetch response type validation with fail-closed metadata and
  Content-Disposition handling.
- Strict TDD recorded the expected RED failures. Controller verification passed
  177 focused tests, the implementation/fix full-suite evidence passed 1,459
  tests with one environment skip, and all changed JavaScript syntax and diff
  checks passed. Independent re-review reported no Critical, Important, or
  Minor findings.
- This task performed no real browser, mailbox, attachment, provider, API,
  navigation, scan, send, persistence, or network operation. Automatic Tencent
  attachment acquisition remains not live-verified successful and requires a
  fresh explicit authorization before any new current-message smoke.

### Attachment Task 5 automatic-acquisition retest

- The operator supplied fresh authorization and performed exactly one manual
  Analyze click on the already-open current message. No navigation, mailbox
  scan, send, delete, move, archive, or manual attachment picker occurred.
- The bounded worktree service ran with remote providers disabled. Exactly one
  new public analysis record was created; both automatic attachment insights
  reported `parsed`, with zero non-parsed insights.
- The request temporary directory returned to zero files and the bounded
  loopback service was stopped with zero remaining listeners. Only aggregate
  status and counts were inspected; no message or attachment content, names,
  summary, draft, identifiers, credentials, or provider payload were read or
  recorded here.

### Automatic attachment smoke closeout

- Closeout Task 1 is in progress under Subagent-Driven Development; per-task
  base is `481ea07`.
- The pre-task baseline passed 1,459 tests with one environment skip under
  Python 3.12.13 using the existing locked dependency locations. No dependency
  was installed or changed.

## Task 9 forced OpenAI-to-DeepSeek synthetic fallback smoke

- The operator authorized exactly one synthetic provider fallback operation.
  The fixed `example.test` request contained no attachments or media and did
  not use a browser, mailbox, server, or SQLite path.
- The bounded helper intercepted exactly one OpenAI attempt in process before
  any OpenAI network operation, then delegated exactly one text-only request to
  the production DeepSeek route. The DeepSeek SDK retry count was zero.
- The accepted terminal engine was `ai_model` with label
  `DeepSeek V4 Flash text fallback`; the public schema was valid and zero
  terminal rule-fallback diagnostics were emitted.
- Only fixed aggregate fields were inspected. No key, prompt, provider raw
  output, synthetic body, exception detail, or private content was printed or
  persisted. The root `.env` hash was unchanged and no automatic retry ran.
- The one-shot helper and its isolated regression test were removed after the
  authorized operation. Normal provider defaults remain disabled outside that
  bounded process.

## Task 9 semantic accuracy repair

- Task 9 semantic accuracy repair is offline complete. A parsed attachment status does not prove semantic correctness.
- The earlier bounded smokes proved acquisition, parsing status, provider routing,
  and temporary cleanup only. Operator review subsequently found that historical
  evidence was not consistently used and attachment interpretation was incorrect.
- The offline plan in
  `docs/superpowers/plans/2026-07-20-task9-semantic-accuracy-repair.md`: one
  current-plus-history evidence set, explicit source roles, complete model-visible
  attachment coverage, deterministic reconciliation safeguards, and a documented
  private human gold-standard method is implemented and independently review-clean.
- No new live browser, mailbox, provider, SQLite, attachment, or network operation
  is authorized by this repair record.
- TDD and independent reviews closed the thread completeness/order, Tencent DOM,
  attachment process transport/grounding, deterministic reconciliation, and private
  human-reference gates with no remaining Critical or Important findings.
- Final adversarial review also closed deterministic attachment-fact replacement,
  projection-created partial tails, abbreviation/initialism/decimal boundaries, and
  long CJK attachment truncation with and without early whitespace. The final
  independent verdict is READY with no Critical, Important, or Minor findings.
- The first controller full-suite pass completed 1,509 tests with one environment
  skip. Final status generation, leakage, maintenance, JavaScript, and diff gates are
  recorded by the Task 9 closeout verification rather than by any live operation.
