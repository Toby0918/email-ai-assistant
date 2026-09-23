# Issue #26 browser review-and-copy draft card

This delivery implements the retained browser-only requirements of
[Issue #26](https://github.com/Toby0918/email-ai-assistant/issues/26). Both the
extension panel and local debug page keep one card with subject, read-only
textarea, a fixed "需要人工审核" reminder, review reasons and Copy control.
The reminder is beside the card heading and is associated with the textarea
and Copy control for assistive technology. The control starts disabled and is
disabled again whenever the displayed draft is empty or cleared.

Draft subject/body/reasons use own data properties. Object-valued, inherited
or accessor-backed draft text cannot populate the card. The body preserves its
whitespace; Copy writes only the textarea's visible value, never the subject,
review reasons or hidden response metadata. The backend's review flag cannot
remove the human-review reminder. No browser editor, approval checkbox, Send,
Reply, Insert or other mailbox action is introduced.

## Copy boundary

Each extension Copy click captures the visible body and its analysis generation
and message context. It checks the active tab and asks the existing content
script to revalidate the message fingerprint. After that asynchronous response,
it checks the active tab again, including its URL, and rejects changed draft
text or an obsolete analysis generation before calling the clipboard API.
Stale context clears analysis and draft with "Email changed; analyze again".

The final tab check closes the observed gap where the operator switched tabs
while the old tab's fingerprint response was returning. These browser API
checks are not an atomic lock on the mailbox: they verify context at their
checkpoints. A clipboard write already handed to the browser cannot be revoked
if the operator changes context afterward. Its later success/failure callback
therefore cannot replace a newer analysis or stale-state status.

Local debug copies the visible body only and uses its existing input-generation
invalidation. It does not claim to validate Tencent extraction. Both surfaces
retain the fixed "No draft to copy", "Copy failed" and "Draft copied" statuses;
raw clipboard exceptions are never displayed. Missing clipboard APIs fail safely.

The exact remote-processing disclosure, Analyze click boundary, attachment
byte-read boundary, backend schema and provider-disabled defaults are unchanged.
No backend, provider, extension-permission or persistence change is required.

## Verification

Ten synthetic cases in `tests/browser/reviewed_copy.test.cjs` exercise the public
renderer and actual page event handlers at the clipboard and browser-API
boundaries. They cover whitespace-preserving rendering, fixed review status,
unsafe draft values, exact body-only writes, active-tab changes during message
revalidation, later clipboard success/failure, message changes and unavailable
browser context, empty drafts, missing/failing clipboard APIs, changed visible
drafts, superseding analyses, and inert long subject/reason text. The existing
15 action-queue and decision-summary tests also pass. The older partial-render
failure check now raises a DOM write error because draft getters are ignored.

Node syntax checks pass. This repository has no configured JavaScript static
type checker. Real mailbox extraction, exhaustive accessibility behavior and
provider/business quality remain distinct from this synthetic browser work.

The real in-app browser loaded both pages from an isolated localhost fixture
server with synthetic API results and mocked extension tab/message responses.
At 320 px, both pages retained read-only drafts without horizontal page overflow;
the debug page also passed the 1280 px layout check. Long subjects and review
URLs wrapped as inert text. Clicking Copy on each page produced browser clipboard
text exactly equal to the displayed body, including leading spaces and newlines.
Changing the debug email cleared the draft, disabled Copy and displayed the
fixed stale status. The temporary clipboard was cleared after these checks.
This is real browser rendering/copy verification with synthetic context, not
live Tencent mailbox acceptance.

Independent Standards and Spec reviews against
`a4bce3b6ea88eac9fab2a3d45ba77e49e7b7dc7a` found no issues. Both reviewers
independently ran the 25 browser tests successfully.

`scripts/build_windows.ps1` passed all 245 unittest cases, built the Windows
executable, and ran that executable's `--self-test` successfully on Python
3.14.7. The receipt reports `status: PASS`, `provider_calls: 0` and
`live_mailbox_access: 0`. All six changed frontend assets in the executable
bundle match their source text. Both disclosure strings match the review base
exactly. Local build output is retained under `RuntimeTemp/issue26/build.log`
and the executable receipt under `Build/desktop-self-test.json` (both ignored).
