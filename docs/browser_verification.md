# Action Console browser delivery, Issue #27

Extension version: **0.2.5**. Review base:
`24ee9edfe3dcd190dd220c541ae8b9b950a1ab06` (merged #26).
This delivery retains the selected Action Console layout from #24–#26 and the
independent desktop product boundary. No prototype route or alternate variant
is packaged. Native desktop drafts remain editable; browser drafts are readonly.

## Evidence contract

Conversation, attachments, risk evidence, additional actions and technical
information remain separate native details, initially closed. Attachment states
are explicit: parsed, metadata only, unavailable, failed, or unknown. Only parsed
attachments expose content summaries/facts. Their reminder says bounded parsing
does not establish business correctness; missing limitations do not imply an
unrestricted parser. Other states show metadata and limitations only.

The renderer projects own data fields, ignores unknown fields/accessors and
uses inert text nodes. Attachment metadata, summaries, facts, limitations,
conversation evidence and risk evidence suppress path/URI-shaped references
and credential/diagnostic markers. This conservative display filter may hide
benign links too. It is not a general secret detector and cannot recognize an
unlabelled arbitrary secret; backend privacy checks remain necessary. Unknown
engine/provider diagnostics never become a user-facing explanation.

## Lifecycle verification

`tests/browser/evidence_lifecycle.test.cjs` covers attachment truth states,
unsafe evidence, inherited/getter fields, reading current email, reading selected
attachments, the 60-second analysis message, busy control recovery, safe extraction
errors, allowlisted backend errors, stale results, older completion cleanup, and
the local deadline with a late response. Existing suites cover model success,
eligible text fallback, rule fallback, unknown engine, input invalidation,
out-of-order results, and exact current-draft copying.

The seams remain `renderAnalysis` / `clearAnalysis` and the actual page event
handlers, with synthetic browser/API/clipboard boundaries. No real email,
provider or attachment is submitted by these tests. There is no configured
JavaScript static type checker; Node syntax checks are required instead.

## Install, update and operate

Start the desktop application, which serves the local API on 127.0.0.1:8765.
In Chrome/Edge's extensions page, enable developer mode and load
`frontend/browser_extension` as an unpacked extension. For an update, reload the
extension and refresh the existing Tencent Exmail page before analyzing again.
Open a current email and explicitly click Analyze in the side panel. Selecting
manual attachments alone does not read their bytes. Review the result and copy
the visible draft body; no send/insert/navigation/mailbox action is provided.
The exact remote-processing disclosure remains visible before Analyze.

The local debug page at http://127.0.0.1:8765/ accepts synthetic fixture text;
it does not validate Tencent extraction. Providers are disabled by default and
credentials, if configured separately by the operator, stay session-only.

## Repeatable checks and deployment

Run `Runtime/Python3147/python.exe -B scripts/check_repository.py` for generated
`Build/project-status.json`, maintenance checks and a bounded leakage-pattern
scan. It scans tracked and new non-ignored working files, checks frontend syntax,
local assets, duplicate IDs, readonly drafts, polite status, closed details,
version documentation and matching disclosures. It does not scan ignored data
or Git history and cannot prove absence of all secrets. Missing Node fails the
check, so browser checks cannot silently be skipped in delivery.

Run `scripts/build_windows.ps1` for the full unittest suite, Windows package and
actual executable self-test. CI runs the repository checks before that build,
then the existing bounded business checkpoints. Its artifacts include the
Windows package and source-status/executable receipts. Keep the whole application
folder when deploying. The extension is manually installed from its source
folder; it is not automatically installed by the desktop program.

## Recorded verification, 2026-09-23

Nine new evidence/lifecycle cases and 25 existing browser cases passed through
the focused unittest wrappers. Independent Standards and Spec reviews of the
implementation found no issues. The repository check passed, with no maintenance
or leakage-pattern findings, and generated `Build/project-status.json`.

The real in-app browser loaded production HTML/CSS/JS from an isolated localhost
server returning synthetic results; extension tab/content responses were mocked.
At actual widths 320 and 400 px the panel had no horizontal overflow or nested
content scroll owner. The debug page passed widths 320, 760, 762 and 1280 px;
only the wide layout had a scrolling result column. Textarea scrolling is an
intentional native editing-control behavior, not another layout scroll owner.
Long mixed-language evidence wrapped without clipping. All visible controls
measured at least 44 px high. The five evidence details started closed and were
keyboard operable; Enter expanded, Space collapsed, and Tab followed visual order.
The observed debug sequence was sender, recipients, timestamp, attachments, body,
Analyze, then the five details. Focus outlines were visible and analysis did not
move focus into results. Status used `aria-live="polite"`. Changing debug input
cleared evidence/draft, disabled Copy and displayed the fixed stale message.

The full source suite passed **246 tests**. `scripts/build_windows.ps1` completed
the Windows build and actual executable `--self-test` with `status: PASS`,
`provider_calls: 0` and `live_mailbox_access: 0`. Every bundled frontend file
matches its source bytes. Both disclosure paragraphs match the review base;
the extension manifest changes only its patch version. Local receipts are
`RuntimeTemp/issue27/build.log`, `Build/desktop-self-test.json` and
`Build/project-status.json`. A temporary synthetic credential-shaped probe in a
non-ignored file was rejected by the scanner without printing its contents;
after removal the repository scan passed again.

## Acceptance boundary

Browser fixture rendering, DOM semantics and keyboard checks establish only the
tested synthetic states/viewports. Screen-reader speech, all browser/OS variants,
live Tencent extraction and remote model/business quality require separate
acceptance. Issues #24–#27 retain their historical requirements; this evidence
does not change roadmap order or automatically close those issues.
