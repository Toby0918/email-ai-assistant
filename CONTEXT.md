# Current-email assistance

This context describes a single operator reviewing one submitted email and its
selected attachments in a Windows desktop application.

## Language

**Current email**: The subject, sender, recipients, visible body and selected
attachment paths submitted for one analysis. A change makes prior results stale.
_Avoid_: Mailbox, historical corpus

**Parsed attachment**: An attachment whose bounded content was read by a parser.
This status is not evidence that every business meaning was correctly understood.
_Avoid_: Verified attachment

**Reviewed draft**: The visible reply body approved by the operator after the
latest edit and for the current email. It is eligible for copying into the mailbox.
_Avoid_: Sent reply, automatic response

**Rule fallback**: A local rule result used when no remote model is enabled or
a remote result cannot be accepted. It does not prove the remote model succeeded.

**Legacy archive**: Retired source history and encrypted historical material
retained separately from the application data, without automatic runtime access.
