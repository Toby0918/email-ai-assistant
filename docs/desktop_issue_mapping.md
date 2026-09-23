# Desktop scope and retained UI issues

The merged independent desktop baseline supersedes the old migration plan.
The four UI issues below originally specify browser side-panel/local-web behavior.
Their history and unchecked acceptance remain open. Native desktop coverage is
recorded separately; it is not evidence of Tencent mailbox extraction acceptance.

## Business repair delivery, 2026-09-23

[Issue #135](https://github.com/Toby0918/email-ai-assistant/issues/135) tracks
the current-email business repairs implemented after PR #134. Their bounded
specification and verification are in `business_acceptance.md` and
`business_repair_20260922.md`. The recorded local baseline is 236 tests,
22 synthetic checkpoints, executable self-test, and 41 explicit checks across
eight selected real GUI cases. These records are distinct from hosted checks
on the delivery commit and from operator business sign-off.

Issue #135 changes bounded backend behavior, so it is a separate delivery from
the original browser-only UI tickets below. The historical browser acceptance
criteria and dependencies remain intact; this delivery does not close them.

| Issue | Desktop coverage | Remaining original scope |
| --- | --- | --- |
| [#24 Decision summary](https://github.com/Toby0918/email-ai-assistant/issues/24) | Conclusion and requested outcome appear in the advice tab; provider identity appears in status/details. | Browser priority/category/confidence hierarchy, safe optional values and fixed engine/pending messages are implemented and separately checked in [browser_decision_summary.md](browser_decision_summary.md). Live mailbox/provider and business acceptance remain separate. |
| [#25 Action queue](https://github.com/Toby0918/email-ai-assistant/issues/25) | Advice exposes next steps, key facts, must-check items and risks; a full native numbered queue remains separate. | Browser queue, owner/due/source, reply-before-checking callout and risk signals are implemented and separately checked in [browser_action_queue.md](browser_action_queue.md). Live Tencent extraction and provider/business acceptance remain unverified; #24 remains open. |
| [#26 Reviewed copy](https://github.com/Toby0918/email-ai-assistant/issues/26) | An editable native draft requires review; changes to input or draft invalidate eligibility. Copy writes visible body only and handles clipboard failure. | Read-only browser cards now retain a fixed review reminder and copy the exact visible body after current-tab/message checks. Ten synthetic regressions and real-browser fixture checks cover copying, clearing and failure behavior; see [browser evidence](browser_reviewed_copy.md). Live Tencent acceptance remains separate. Native draft editing is intentional and does not redefine the browser requirement. |
| [#27 Evidence and closure](https://github.com/Toby0918/email-ai-assistant/issues/27) | Packaged XLSX and DOCX parsing, parser limits, stale-result rejection and local test/build evidence are recorded. | Browser 0.2.5 adds guarded attachment/evidence presentation, lifecycle regressions, responsive/keyboard fixture checks and repeatable repository checks; see [browser verification](browser_verification.md). Native evidence remains JSON details. Live Tencent extraction, screen-reader speech and real provider/business quality remain separate acceptance gaps. |

All four remain status:needs-rebaseline until their outstanding browser/product
requirements receive a separate scoped decision. The 18 historical-knowledge
issues retain status:deferred. Cancelled migration issues #29, #39 and #40 remain
closed as not planned. No successful desktop check is used to mark those older
requirements completed.
