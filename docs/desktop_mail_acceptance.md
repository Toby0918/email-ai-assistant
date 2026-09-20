# Desktop current-email acceptance

Approved scope: build on merged desktop baseline PR #133, commit
08b97bbbebf96e91a3fa043bdf0f07c80ad4b08a. Exercise a synthetic current email
and one XLSX attachment through the native window, inspect facts and limits,
edit the draft, review and copy it. The operator selected DeepSeek for a later
live check, with the key entered only in the application settings.

## Acceptance contract

Analysis starts only on an explicit click. Before that click, file selection
carries paths without reading attachment bytes. The ordinary local service and
isolated attachment worker must parse a bounded XLSX fixture and return its
explicit quantity, with a human-reviewed draft and no mailbox actions.

Changing the subject, sender, recipients, body or selected attachments invalidates
the displayed analysis, draft and review. An in-flight result for an earlier
input revision must not restore them, even when the user changes a field back.
Editing the draft requires another review. Clipboard access writes only the
visible reviewed body; clipboard errors retain the draft and show a fixed message.

The real SDK must serialize the DeepSeek request to the official HTTPS endpoint,
with no retries, bounded time/tokens, JSON output and thinking disabled. Its
current default model name is `deepseek-flash`; older explicit configuration
aliases remain accepted. Local HTTP mocks establish SDK compatibility, not a
successful provider connection or answer quality.

## XLSX limit discovered during this acceptance

A first fixture used columns Product, Material, Quantity, Delivery followed by
a row containing the numeric value 1200. The parser read that file but returned
no structured facts: current rules do not associate arbitrary table headers with
subsequent rows. That capability remains unimplemented. The acceptance fixture
uses explicit label/value rows, including Quantity / 1200 pcs. Passing that fixture
does not establish general spreadsheet understanding. Formula evaluation, merged
headers and arbitrary table layouts also require separate validation.

## Reproducible local checks

`tests/test_desktop_window.py` drives actual Tk controls and the actual loopback
service. Only the file chooser, clipboard boundary and delayed-service timing are
substituted. This neither reads nor overwrites the operator's clipboard.
`tests/test_sdk_compatibility.py` drives the real SDK with a synthetic HTTP transport.
The executable self-test additionally exercises XLSX window analysis, stale draft
rejection, DOCX parsing, cleanup and restart persistence using temporary data.

## First live DeepSeek observation and required retest

The operator's 2026-09-19 screenshot showed an accepted `ai_model` result labelled
DeepSeek Flash and the XLSX quantity 1200 pcs. Connection/result acceptance was
observed, but semantic acceptance failed: the delivery request was called a quote
because of “No price has been agreed”, and “before promising” became a deadline.
Both errors reproduced without a provider. The conservative DeepSeek route retains
the local decision brief and draft while accepting limited AI augmentation, so
those deterministic errors survived a successful model call.

The corrected acceptance requires the delivery brief to remain delivery-focused
when price is merely unset, action prerequisites to stay out of deadline facts,
and actual weekday deadlines and separate quotation requests to remain intact.
Native status must distinguish AI supplementation from rule-generated advice,
display a readable engine name, and stay visible alongside the remote-content
notice and Analyze button at the supported minimum window size.

Source regressions cover both the rule boundary and conservative provider merge
with a synthetic model response. A new live run of the corrected executable is
still needed before accepting business quality.

Open the freshly built program, choose DeepSeek in AI settings and enter the key
there. Use `examples/desktop_acceptance/email.txt` and the generated synthetic
XLSX. `email.txt` contains only the body; headers and expected results are separate
in `examples/desktop_acceptance/README.md`. Keep expected results out of the body.
The operator must click Analyze after reviewing the remote-content notice.
Check that the result engine identifies DeepSeek, rather than Rule fallback.
Confirm the attachment quantity is 1200 pcs, delivery remains unconfirmed, and
the draft makes no invented price or delivery commitment. Edit and review it,
then copy it; change the input and verify the old draft disappears.

This manual retest is not complete until the corrected actual provider result is inspected.
A fallback, timeout, blocked output or syntactically successful request alone does
not pass semantic acceptance. Tencent mailbox extraction remains separately pending.

The second live screenshot confirmed the readable engine/footer and no false
deadline, but included the old fixture's Expected review section in the body.
The quotation conclusion persisted. A provider-disabled comparison using the
actual local service and XLSX reproduced that conclusion only with the added
review instructions; the clean body returned order_followup. The fixture is now
split to prevent accidental mixed input. Broader price-mention false positives
remain a rule limitation. Clean-input live semantic acceptance remains pending.

Official model/request references checked on 2026-09-19:
[Models & Pricing](https://api-docs.deepseek.com/quick_start/pricing/),
[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/).
