# Task 6 Implementation Report

Status: COMPLETE - FINAL INDEPENDENT REVIEW CLEAN
Date: 2026-07-16
Worktree: `C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.worktrees\multimodal-plan-c`
Branch: `codex/multimodal-plan-c`

## Outcome

Task 6 now routes explicitly enabled OpenAI analysis through the existing
model-led private envelope and safety pipeline, optionally makes one bounded
DeepSeek text-only fallback call after an eligible OpenAI failure, and returns
the deterministic rule result if no provider result is accepted.

- OpenAI receives the post-preflight `ModelAnalysisRequest`: locally
  deidentified text plus Task 4 sanitized media. The injected generator seam
  receives the same request type.
- DeepSeek fallback is available only for an OpenAI primary route with
  `text_fallback_provider=deepseek` and at least 12 seconds remaining
  immediately before its call. It receives only a separately prepared `str`
  view, excludes marker-only visual sources, is capped at 10 seconds, and is
  never retried.
- Accepted engine labels are carried by `ModelRun` and cannot be replaced by a
  caller-supplied label: `OpenAI GPT-5.6 Sol` or `DeepSeek V4 Flash/Pro text
  fallback`.
- Terminal diagnostics retain only allowlisted provider/model/reason metadata.
  A secondary DeepSeek failure reports DeepSeek rather than the earlier OpenAI
  attempt.
- Visual evidence uses an internal `grounding_mode`. It may ground only
  source-bound qualitative damage, label placement/presence, component
  presence, packing/layout, or visible-condition observations. Identity,
  protected traits, exact facts, URLs, hidden/tool instructions, commitments,
  and completed outcomes fail closed.
- A mixed Office source is visual-capable for OpenAI and text-only for the
  independent DeepSeek fallback view. Repeated visual source IDs remain safe.
- Sanitized visual sources may qualitatively augment their own
  `metadata_only` attachment while preserving that public status, limitations,
  exact membership, filename/index binding, and human-review safeguards.
- Public HTTP fields, SQLite columns, and the public analysis schema are
  unchanged.

## Files

Implementation:

- `backend/email_agent/analysis_budget.py`
- `backend/email_agent/analysis_route_support.py`
- `backend/email_agent/analysis_model_routes.py`
- `backend/email_agent/analysis_provider_policy.py`
- `backend/email_agent/analysis_diagnostics.py`
- `backend/email_agent/llm_errors.py`
- `backend/email_agent/prompt_context.py`
- `backend/email_agent/model_grounding.py`
- `backend/email_agent/model_source_grounding.py`
- `backend/email_agent/model_cross_language_grounding.py`
- `backend/email_agent/model_multimodal_claim_safety.py`
- `backend/email_agent/model_visual_grounding.py`
- `backend/email_agent/model_result_safety.py`
- `backend/email_agent/openai_multimodal_client.py`

Tests:

- `tests/test_analysis_budget.py`
- `tests/test_analysis_route_support.py`
- `tests/test_analysis_model_routes.py`
- `tests/test_model_grounding.py`
- `tests/test_model_result_safety.py`
- `tests/test_analyzer.py`
- `tests/test_prompt_context.py`

Records:

- `.superpowers/sdd/task-6-brief.md`
- `.superpowers/sdd/task-6-report.md`
- `.superpowers/sdd/progress.md`

The two small policy helpers keep every backend Python module at or below 300
lines and every function at or below 50 lines without broadening behavior.

## TDD evidence

All Python evidence used Python 3.12.13 from the pinned Codex runtime and the
approved project/Python 3.12 `PYTHONPATH`.

- Clean pre-change baseline: 1,317 tests passed with one expected skip.
- Initial fixed RED: 33 tests produced six failures and four errors for the
  missing `ModelRun` metadata, request-type routing, text fallback, visual
  grounding mode, and terminal diagnostics.
- First implementation run reduced the matrix to two failures. Systematic
  tracing showed the fixed Task 4 `UNTRUSTED_MEDIA` binary marker was correctly
  rejected by the text privacy genericizer. The fix kept the scanner closed,
  excluded that marker from text views, and reconstructed only the internal
  OpenAI visual registry from sanitized media. The fixed 33-test matrix then
  passed.
- A narrow label/hidden-instruction RED produced three expected failures in an
  80-test run. Accepted `ModelRun` labels now take precedence, and hidden/action
  language is rejected even when appended to an otherwise allowed damage
  observation. The same 80 tests passed after the fix.
- One exact visual-attachment RED proved a qualitative augmentation was being
  dropped solely because local OCR retained `metadata_only`. The minimum merge
  change accepts only a matching visual source and preserves the public status;
  the exact test then passed.

### Fresh-review remediation

The independent specification and adversarial reviews identified four related
fail-closed gaps. A fixed 88-test RED matrix reproduced twelve failures:

- five allowword-smuggling visual leaves accepted names/protected traits,
  PowerShell/upload instructions, an unlabeled identifier, boxes, and pounds;
- two visual sources could author a global summary with or without evidence;
- two hybrid-source cases could author global/person claims;
- one mixed Office source lost its text capability;
- one mapped OpenAI private-artifact output entered DeepSeek fallback; and
- one stale 12-second gate still called DeepSeek after the final budget had
  fallen to 11.9 seconds.

The fix now applies a complete finite visual-observation contract only to the
matching attachment augmentation. Visual evidence cannot authorize global
fields; every visual leaf requires matching owner/source evidence. Mixed
PDF/Office sources retain independent text and visual capabilities through an
internal `hybrid` mode, while DeepSeek receives a freshly built text-only
registry. OpenAI privacy-output refusals carry a content-free internal fallback
block; ordinary invalid provider output remains eligible for the configured
text fallback. The final DeepSeek timeout and 12-second eligibility are derived
from one authoritative clock read, preserving the five-second response margin.

A follow-up RED proved the first privacy fix was too broad: mapped ordinary
invalid JSON made zero DeepSeek calls. The selective fix blocks only placeholder
or private-artifact output and restored the expected one-call text fallback.

Final review-fix focused matrix:

```text
Ran 223 tests in 5.084s
OK
```

Final architecture/static/mechanical/browser-static matrix:

```text
Ran 88 tests in 3.474s
OK
```

Final post-review-fix pinned-runtime suite:

```text
Ran 1338 tests in 100.318s
OK (skipped=1)
```

`git diff --check` exited 0 with only the checkout's expected LF-to-CRLF
warnings. No network, browser, mailbox, provider, or live service was accessed.

Final focused matrix:

```text
Ran 148 tests in 4.171s
OK
```

Final architecture/static/mechanical matrix:

```text
Ran 56 tests in 3.431s
OK
```

Final full pinned-runtime suite:

```text
Ran 1328 tests in 90.882s
OK (skipped=1)
```

`git diff --check` exited 0 before records were staged; the checkout emitted
only its expected LF-to-CRLF conversion warnings.

The pre-review SHA-256 of the sorted 13-file implementation/test hash manifest
was:

```text
d43909ad0df961ca5ee8389af1c67790295f08e7d36c1a64fa3332a2c809ca9f
```

### Second fresh-review remediation

The second independent review found two contract-alignment gaps. The OpenAI
prompt described visual safety constraints without publishing the exact finite
sentences accepted by the validator, and a multimodal response could cite an
unrelated text or hybrid source for a global claim. A fixed 83-test RED run
reproduced eight failures plus one import error before production changes.

The prompt and validator now share one canonical visual-observation source.
Only the rendered complete sentences are accepted after case and whitespace
normalization, and attachment augmentation summaries and key facts must each
be one such complete sentence. Natural-language variants, appended semantics,
digits, identity, protected-trait, and instruction smuggling remain rejected.
The final OpenAI system prompt is 7,710 of the 8,000-character limit, retaining
a 290-character reserve.

Whenever a multimodal run contains any visual or hybrid source, every global
text leaf must be fully grounded by every cited text or hybrid source. A visual
source can never authorize a global leaf, unrelated or mixed evidence fails
closed, and pure-text runs preserve their prior compatibility behavior. The
end-to-end safety pipeline now rejects fake thread evidence and unsupported
identity, protected-trait, and damage claims while accepting directly supported
normalized text. Unsupported reply and action fields fall back individually
without discarding separately grounded fields.

Second-review verification:

```text
Focused prompt/grounding/safety matrix: 101 tests, OK
Expanded Task 6/provider/privacy matrix: 264 tests in 5.416s, OK
Architecture/static/mechanical/browser-static matrix: 88 tests in 3.533s, OK
Fresh full pinned-runtime suite: 1343 tests in 95.170s, OK (skipped=1)
```

The first full-suite attempt encountered one unrelated Windows loopback
`ConnectionAbortedError` in an existing server test. That exact test immediately
passed alone (one test in 0.524s), and the fresh full-suite rerun above passed.
No external network, provider, browser, mailbox, API, or real data was accessed.

### Third fresh-review remediation

The third independent review found that the strict multimodal global-claim
contract was impossible to satisfy for an English source: the provider had to
return Chinese public prose, while every cited text source had to contain that
same complete claim literally. The fixed five-target RED run produced twelve
expected assertion/subtest failures for the missing English-to-Chinese bridge,
end-to-end model contribution, and prompt contract.

The minimum repair keeps the private envelope and public/SQLite schemas
unchanged. A small local module maps nine exact Chinese templates to finite
claim codes. Only `/analysis/summary` and `/analysis/priority_reason` can use
the bridge, and every cited text or hybrid source must independently contain a
same-clause bounded combination for the same code. The matcher returns only a
boolean: it does not expose, persist, or log its internal match span or source
text. Negation, more than 96 characters between required terms, cross-clause
terms, unrelated or mixed evidence, arbitrary paraphrases, and pure-visual
evidence fail closed. Existing literal text grounding remains authoritative,
and pure-text compatibility is unchanged. A follow-up RED across all nine
templates caught and fixed an NFKC lookup mismatch for templates containing a
full-width comma.

The OpenAI prompt renders the exact same fixed templates used by the validator.
The shared prose was compacted without removing its untrusted-content,
source-binding, attachment parsing, mailbox-action, commitment, exact-fact,
human-review, identity, or protected-trait constraints. The final multimodal
prompt is 7,743 of the 8,000-character limit, leaving 257 characters.

Third-review-fix verification:

```text
Focused prompt/grounding/result-safety matrix: 109 tests in 0.792s, OK
Expanded Task 6/provider/privacy matrix: 295 tests in 5.247s, OK
Architecture/static/mechanical/browser-static/documentation matrix: 105 tests in 3.939s, OK
Fresh full pinned-runtime suite: 1351 tests in 94.898s, OK (skipped=1)
```

No external network, provider, browser, mailbox, API, live service, credential,
or real data was accessed.

### Fourth fresh-review remediation

The fourth independent adversarial review found two remaining multimodal
grounding gaps. The cross-language bridge combined unordered keywords within a
clause, so cancellation, completed outcomes, and unrelated nearby terms could
authorize one of the fixed Chinese templates. Separately, the literal
substring path accepted unsafe source-equals-claim global text whenever a
visual or hybrid source was present.

A fixed three-test RED run produced 21 expected subtest failures. The synthetic
matrix included all nine cross-language templates, cancellation, refusal,
inability and completed-outcome language, comma-separated unrelated terms,
Chinese cancellation and withdrawal, Greek and combining-mark `not`
obfuscation, U+0085/U+2028/U+2029 boundaries, explicit person identification,
protected traits, PowerShell/tool instructions, an unlabeled number, and a
completed order claim. URL and explicit commitment controls were retained as
passing regression cases.

The bridge now uses nine independent directional phrase contracts with bounded
gaps. Commas, colons, Unicode line/paragraph separators, NEL, and ordinary
sentence punctuation are all clause boundaries. A candidate clause is rejected
for cancellation, refusal, inability, negation, withdrawal, or settled outcome
language. Format/default-ignorable marks and mixed Latin with Greek/Cyrillic
script also fail closed. This intentionally prefers false negatives over
incorrect authorization.

Before literal or cross-language text grounding can authorize a multimodal
global leaf, a separate local gate rejects critical exact/outcome/commitment
signatures, any decimal digit, explicit person-identification or protected-trait
phrasing, tool/shell instructions, links, and unsafe operations. The gate is
activated only for global leaves when the request-local registry contains a
visual or hybrid source; pure-text exact-substring compatibility is covered by
an explicit unchanged-behavior test. Source-bound canonical visual attachment
observations and hybrid attachment text grounding remain unchanged.

Fourth-review-fix verification:

```text
Focused prompt/grounding/result-safety matrix: 113 tests in 0.821s, OK
Expanded Task 6/provider/privacy matrix: 287 tests in 5.231s, OK
Architecture/static/mechanical/browser/documentation matrix: 228 tests in 9.432s, OK
Fresh full pinned-runtime suite: 1355 tests in 90.166s, OK (skipped=1)
OpenAI multimodal prompt: 7743/8000 characters, 257-character reserve
```

The first static matrix correctly found the touched grounding function at 52
lines. A behavior-neutral refactor restored the fixed 50-line limit, after
which the complete matrix passed. `git diff --check` exited 0 with only the
checkout's expected LF-to-CRLF warnings. No external network, provider,
browser, mailbox, API, live service, credential, or real data was accessed.

### Fifth fresh-review remediation

The fifth independent adversarial review found that contracted negatives,
conditional/reference narration, and cancellation could still authorize the
finite Chinese cross-language templates. It also found that multimodal global
literal grounding accepted additional identity/name-role claims, protected
traits, and independent shell/tool mentions when the same unsafe sentence was
present in a cited text source.

A fixed five-test RED run produced 40 expected failures. It included all nine
templates with one current positive plus contracted, conditional, and
reference/history hard negatives, the exact reported quote and urgent-support
counterexamples, end-to-end merge rejection, identity/protected-trait terms,
and independent PowerShell/cmd/shell mentions. A follow-up identity-role and
quality compatibility RED produced 11 expected failures.

A final external-draft compatibility RED produced one expected failure for the
ordinary verb phrase `Please contact us.`. Identity-role blocking was narrowed
to finite assertions, so this exact grounded draft remains usable while name,
role, identification, and person-identity assertions still fail closed.

The bridge no longer contains any arbitrary-position request/ask pattern. A
request match must be either a sentence-start direct imperative or a
sentence-start finite active role immediately followed by active
`requests`/`asks` wording and a bounded directional target. Fixed non-current
prefixes, auxiliary or contracted request negation, cancellation, and target
terms separated by comma/colon fail closed. A single anchored declarative
quality form preserves the prior safe `The packaging is damaged.` behavior;
it does not authorize arbitrary request narration.

The multimodal global prose gate now rejects a finite identity/name-role
vocabulary, including contact, representative, employee, staff, manager,
assistant, and Chinese equivalents. Its protected-trait vocabulary covers sex,
gender, pregnancy, sexual orientation, race, ethnicity, religion, disability,
medical/health, genetic, age, nationality, and citizenship in English and
Chinese. Any independent PowerShell, cmd, shell, command, script, tool, 命令,
脚本, or 工具 mention fails closed. The gate still activates only when visual or
hybrid evidence exists, so the established pure-text compatibility boundary is
unchanged.

Fifth-review-fix verification:

```text
Focused grounding/result-safety/prompt matrix: 118 tests in 1.076s, OK
Expanded Task 6/provider/privacy matrix: 344 tests in 7.917s, OK
Static/architecture/mechanical/browser/documentation matrix: 251 tests in 19.102s, OK
API/schema/database matrix: 67 tests in 0.708s, OK
Fresh full pinned-runtime suite: 1360 tests in 154.862s, OK (skipped=1)
OpenAI multimodal prompt: 7743/8000 characters, 257-character reserve
```

`git diff --check` exited 0 with only the checkout's expected LF-to-CRLF
warnings. No network, provider API, browser, mailbox, real content, credential,
`.env`, SQLite database, or live service was accessed.

### Sixth production-registry integration remediation

The sixth review integration check found that raw synthetic grounding fixtures
did not reproduce the request-local source registry. The production serializer
prefixes the first body line with `body = `, while every directional
cross-language pattern is intentionally anchored at clause start. Consequently,
all nine safe fixed templates failed through the real registry path.

The fixed RED test creates `ThreadSource` and `TimelineBuild` values and calls
`build_deepseek_untrusted_context`; it produced nine expected subtest failures.
The corresponding end-to-end model-result merge produced one expected failure
and retained the rule fallback instead of the fixed Chinese model summary.

The matcher now accepts an explicit `trusted_thread_serialization` capability.
Only `model_source_grounding` derives that capability, and only from
`source.kind == "thread"`. After NFKC normalization and case folding, the
matcher removes one exact backend-owned `body = ` prefix from each clause.
It never infers trust from text contents. `from =`, `to =`, `sent_at =`, and
`subject =` remain ineligible; a second user-supplied `body = ` prefix remains;
and attachment text containing the same marker receives no capability.

Sixth-integration-fix verification:

```text
Focused grounding/result-safety/prompt matrix: 121 tests in 1.117s, OK
Expanded Task 6/provider/privacy matrix: 356 tests in 7.778s, OK
Static/architecture/mechanical/browser/documentation matrix: 228 tests in 22.305s, OK
API/schema/database matrix: 67 tests in 0.661s, OK
Fresh full pinned-runtime suite: 1363 tests in 138.087s, OK (skipped=1)
```

The first static run correctly found the touched source-grounding function at
53 lines. A behavior-neutral signature reformat restored the fixed 50-line
limit, after which the complete matrix passed. Provider-visible grounding text,
prompts, private/public envelopes, HTTP, SQLite, and persistence schemas remain
unchanged. No network, provider API, browser, mailbox, real content, credential,
`.env`, SQLite database, or live service was accessed.

### Seventh body-provenance remediation

Fresh review found that the sixth fix granted the cross-language bridge to the
entire serialized thread whenever `source.kind == "thread"`. A subject, sender,
recipient, or sent-at value could therefore terminate its metadata clause and
place a directional English request in the next clause. The fixed RED matrix
covered four metadata fields and `.`, `!`, `;`, newline, U+2028, and U+2029.
Twenty of the 24 subcases reproduced the escape; the four dot cases were already
removed by the existing bare-host privacy sanitizer. An end-to-end merge also
reproduced the model summary incorrectly replacing the rule fallback.

`EvidenceSource` now carries a repr-hidden, default-disabled
`cross_language_grounding_text`. Only the production thread prompt builder sets
it, and it is exactly the independently sanitized body substring included in the
provider-visible source text. Metadata fields are independently sanitized and
made single-line before serialization. If metadata consumes the source budget,
the body is not sent and the bridge projection is `None`. Attachments and all
manually constructed sources keep the default `None` capability.

The grounding policy continues to use the complete serialized
`grounding_text` for exact literal matches. Only the finite cross-language bridge
uses the separate non-empty thread body projection. It no longer infers
provenance from `source.kind`, `body =` text, delimiters, or source contents.
All nine fixed first-line body templates and the positive end-to-end merge remain
accepted. Metadata injection, a user-supplied repeated `body =` marker,
attachment marker controls, unsent truncated bodies, and manually constructed
thread evidence are rejected.

Seventh-provenance-fix verification:

```text
Focused grounding/result-safety/prompt matrix: 129 tests, OK
Expanded Task 6/provider/privacy matrix: 453 tests, OK
Static/architecture/mechanical/browser/documentation matrix: 238 tests, OK
API/schema/database/server matrix: 85 tests, OK
Fresh full pinned-runtime suite: 1,371 tests in 134.554s, OK (skipped=1)
```

The projection name and value are absent from public analysis responses and
SQLite payloads, and both private text fields are excluded from repr. Public
HTTP and SQLite schemas, the provider/private envelope, prompt size, one-call
routing, DeepSeek text-only fallback, the 12-second fallback gate, and exact-fact
authority remain unchanged. No network, provider API, browser, mailbox, real
content, credential, `.env`, SQLite database, or live service was accessed.

### Final independent provenance review

The final read-only reviewer returned `CLEAN` for `24141d9..2a114ce`. Its
production-path matrix accepted all nine first-line body templates and the
end-to-end merge, while rejecting 216 metadata injection samples spanning four
metadata fields and six separators, plus repeated-body and attachment marker
controls. It confirmed that unsent bodies, default sources, and attachment
sources cannot enable the bridge, and that the projection is absent from repr,
HTTP, private/public envelopes, SQLite, and schemas.

Final independent review evidence:

```text
Focused grounding/result/prompt matrix: 129 tests, OK
Expanded route/provider/privacy matrix: 379 tests, OK
Static/architecture/mechanical matrix: 122 tests, OK
API/schema/database/server matrix: 85 tests, OK
git diff --check 24141d9..2a114ce: OK
```

Task 6 is review clean through `2a114ce2e8152d96aac401280e005c325476f7ed`.
Task 7 is the next approved implementation boundary.

## Security and scope

- No network, provider API, browser, mailbox, real email, real attachment,
  credential, `.env`, SQLite database, or live service was accessed.
- Test inputs and keys are explicitly synthetic. No provider request was made.
- DeepSeek receives no media and no marker-only visual source. Privacy
  preflight/output failures cannot enter the secondary route.
- No model can author locally authoritative identifiers, dates, amounts,
  quantities, tracking values, consequential commitments, or completed
  outcomes from visual evidence.
- No root-checkout file, deployment note, merge target, remote branch, or
  user-owned dirty state was modified.
- Pre-existing untracked `*review-package.md` files remain outside Task 6 and
  must remain unstaged.
- Project-status generation, maintenance/release scans, live smoke, Task 7,
  integration, and push remain deferred to their later approved gates.
