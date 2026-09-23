# Issue #24 browser decision summary

This change implements the retained browser scope of
[Issue #24](https://github.com/Toby0918/email-ai-assistant/issues/24) on top of
the #25 action queue. Both the extension panel and local debug page expose
priority, category and Decision Brief confidence above the primary conclusion.
The current request immediately follows that conclusion. Existing technical
details retain the same priority/category meaning; no response field is added.

Only own string data properties supply these presentation values. Enum labels
come from fixed allowlists; unsupported values render as "未确认". Clear,
pending, failure and stale states reset the labels to "-". Inherited properties,
accessors, coercible objects and raw provider labels cannot become decision
labels. A missing conclusion uses the own string summary, then a fixed
placeholder. Missing requests use a fixed placeholder; text and URL-shaped
values remain inert and are not truncated.

Known model, DeepSeek fallback, rule fallback and unknown-engine messages keep
their existing fixed wording. Technical context-scope labels also reject
inherited map properties. The remote disclosure, Analyze click boundary,
60-second pending status, attachment truth semantics, copy-only draft and
no-mailbox-action rules are unchanged. This delivery adds no backend API,
schema, prompt, provider route, extension permission or production dependency.

## Verification scope

`tests/browser/decision_summary.test.cjs` exercises the public renderer and
actual page event handlers using synthetic fixtures and external-boundary
doubles. Its seven cases cover decision labels and clearing, unknown enums,
own-data-only reads, both pages' success/failure bindings, exact engine messages,
pending states and inert fallback text. The original eight action-queue checks
remain separate and reuse the same DOM/page harness; they now also check that
stale decisions are cleared. Both suites run through unittest discovery.

JavaScript syntax checks are used; the repository does not configure a static
JavaScript type checker. Browser visual checks and packaged executable checks
are recorded separately from live Tencent extraction and provider/business
acceptance. No real mailbox or provider call is needed for this delivery.

On 2026-09-23, the in-app browser showed the same three labels on both surfaces
at 320 pixels, with no horizontal overflow and unique label element IDs. The
conclusion remains the primary heading, and the current request follows it.
The debug page was also visually checked at 1280 pixels with no summary or page
overflow. Editing its actual Body control cleared all three labels to "-".
The synthetic fixture server was separate from the application/provider runtime.

Independent Standards and Spec reviews of the delta from #25 commit
`4a7980b3e8efba2ebe9e86ec9dc0830556736e54` reported zero findings. Both reviewers
independently ran the 15 browser behavior tests successfully.

`scripts/build_windows.ps1` completed on 2026-09-23: all 244 unittest cases
passed, including the two entries running the 15 browser checks. The actual
rebuilt executable's `--self-test` returned PASS with `provider_calls: 0` and
`live_mailbox_access: 0`. The local build log is
`RuntimeTemp/issue24/build.log`; the executable report is
`Build/desktop-self-test.json`. Existing pypdf deprecation notices and the
optional `tzdata` hidden-import warning remain outside this UI delivery.
