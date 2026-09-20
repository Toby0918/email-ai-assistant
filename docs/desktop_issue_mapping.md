# Desktop scope and retained UI issues

The merged independent desktop baseline supersedes the old migration plan.
The four UI issues below originally specify browser side-panel/local-web behavior.
Their history and unchecked acceptance remain open. Native desktop coverage is
recorded separately; it is not evidence of Tencent mailbox extraction acceptance.

| Issue | Desktop coverage | Remaining original scope |
| --- | --- | --- |
| [#24 Decision summary](https://github.com/Toby0918/email-ai-assistant/issues/24) | Conclusion and requested outcome appear in the advice tab; provider identity appears in status/details. | Browser shared-renderer hierarchy, allowlisted priority/category/confidence presentation and pending/unknown-engine states need their original verification. |
| [#25 Action queue](https://github.com/Toby0918/email-ai-assistant/issues/25) | Advice exposes next steps, key facts, must-check items and risks. | A numbered queue with owner, due hint and source plus the browser layout/accessibility cases is not established by native tests. |
| [#26 Reviewed copy](https://github.com/Toby0918/email-ai-assistant/issues/26) | An editable native draft requires review; changes to input or draft invalidate eligibility. Copy writes visible body only and handles clipboard failure. | Original read-only browser card and revalidation of live Tencent tab/message fingerprint remain separate. Native draft editing is intentional and does not redefine the browser requirement. |
| [#27 Evidence and closure](https://github.com/Toby0918/email-ai-assistant/issues/27) | Packaged XLSX and DOCX parsing, parser limits, stale-result rejection and local test/build evidence are recorded. | Native evidence remains JSON details; semantic quality, the full browser lifecycle, layout, keyboard/accessibility and real mailbox extraction are not accepted. |

All four remain status:needs-rebaseline until their outstanding browser/product
requirements receive a separate scoped decision. The 18 historical-knowledge
issues retain status:deferred. Cancelled migration issues #29, #39 and #40 remain
closed as not planned. No successful desktop check is used to mark those older
requirements completed.
