# Issue #25 browser action queue

This delivery implements the retained browser-only scope of
[Issue #25](https://github.com/Toby0918/email-ai-assistant/issues/25), using the
Action Console hierarchy from `prototype/current-email-ui-preview@3e02b3d`.
The shared renderer serves both the extension panel and local debug page.
It does not implement the independent native desktop action queue or close
the still-open decision-summary dependency (#24).

## Presentation contract

The existing Decision Brief supplies one to four numbered steps. Each step
retains its text, an allowlisted responsible-party label, its due hint (or
"未指定"), and its source when provided. Unknown owners use "相关负责人";
inherited label-map properties cannot become role authority. Optional action
and fact fields consume own string data properties, ignoring accessors and
object-valued text.

Must-check items and missing information appear together in an always-visible
"回复前请先核查" callout. Key-fact labels and values remain complete text.
URLs and markup-shaped strings remain inert, including step sources. An
ordered list exposes the step sequence, while existing wrapping allows long
Chinese/English text and unbroken identifiers to fit narrow panels.

Risk signals come exclusively from the existing `risk_flags` collection, in
its original order, with allowlisted type and level labels. No primary risk is
chosen. Full evidence and recommendations remain in "风险依据", and all
additional suggested actions remain in "更多建议动作". Empty risk collections
display "暂无已识别风险信号", which does not assert that the email is risk-free.

Clear and failure paths reset the action, fact, check and signal fields. Local
debug input edits also invalidate pending results and clear the old draft.
The extension retains its existing current-message revalidation boundaries;
rendering exceptions now clear any partially rendered output.

The remote-processing disclosure, Analyze click boundary, 60-second pending
message, attachment truth semantics, copy-only browser draft and no-mailbox-action
rules remain unchanged. No backend API, schema, prompt, provider route, extension
permission, production persistence or dependency was added.

## Verification

`tests/test_browser_action_queue.py` runs eight Node behavior tests through
the public shared-renderer methods and actual page handlers. The boundary
doubles replace DOM, network and browser APIs; they do not replace production
rendering or lifecycle code. Tests cover ordered steps and sources, unsafe owner
values, malformed fields, all risk signals and evidence, local input changes
and pending-result invalidation, extension stale-copy/failure clearing, inert
long values and plain-text fallback. Node syntax checks also pass; this project
does not configure a JavaScript static type checker.

Browser visual checks use a temporary loopback-only server containing synthetic
fixtures, including four steps, mixed-language identifiers, a long URL-shaped
source and two risk types. This is not a live mailbox or provider test. Native
EXE smoke tests verify packaging/runtime health and do not establish browser
business acceptance or Tencent extraction correctness.

On 2026-09-23, the Codex in-app browser showed all four numbered steps at a
320-pixel viewport on both surfaces. DOM measurements found no horizontal
overflow in the action/fact/check/signal content, and no links in the work card.
The local debug page also passed the overflow check at 1280 pixels. Screenshots
were visually inspected for wrapping, numbered steps, the highlighted check
callout and full risk evidence. Editing the actual local Body control cleared
all six action/signal/detail fields and the draft. Keyboard Enter expanded the
risk-evidence disclosure. These are bounded synthetic UI checks, not exhaustive
screen-reader or live-extension acceptance.

Independent Standards and Spec reviews against starting commit
`a2305ee223d52ca1c8528f49d699a2465b9655a4` each reported zero findings.

`scripts/build_windows.ps1` completed successfully on 2026-09-23. Its required
Python 3.14.7 unittest discovery ran 243 tests successfully, including the entry
that executes the eight browser behavior tests. The rebuilt executable's actual
`--self-test` report returned PASS, with `provider_calls: 0` and
`live_mailbox_access: 0`. Every changed frontend file in the packaged `_internal`
directory was compared byte-for-byte with its source, and both disclosure
paragraphs were compared with the starting commit: all matched. The local build
log is `RuntimeTemp/issue25/build.log`; the actual EXE report is
`Build/desktop-self-test.json`. The build emitted pypdf deprecation notices and
an optional `tzdata` hidden-import warning; this delivery does not establish
additional timezone-data coverage.
