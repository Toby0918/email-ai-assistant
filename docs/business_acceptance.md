# Current-email business acceptance, 2026-09-21

## Scope and specification

The operator authorized turning 22 locally researched business scenarios into
repeatable acceptance checks, then fixing the highest-impact reproduced mistakes.
The research originals remain under ignored `Data/mail_research`; no mailbox,
historical corpus, customer attachment, or research database is loaded by runtime
or by the committed checks. Public fixtures use invented parties, IDs and values.

The test seam is the existing `analyze_current_email` / local rule analysis result,
followed by the actual native window and packaged executable. Providers are disabled.
Regression tests must distinguish reported state from requests and independent
verification, retain actual follow-up requests and supplied open thread work, and
preserve security checks and human review before copying a draft.

This change recognizes narrowly defined English status statements: delivery to a
receiving warehouse, payment processing, a future bank slip, reported PPAP approval
and a drawing revision, plus invoice posting with a future payment run. No generic
natural-language state model is claimed. Pure
acknowledgements and supported out-of-office notices must not invent new tasks from
the subject. An attachment or unresolved supplied thread prevents the no-reply
shortcut. Missing selected attachments must be explicit. Waiting for the sender's
approval must not be rewritten as waiting for internal approval. Explicit labeled
pickup/cutoff/ETD/ETA values keep their roles and unspecified year/timezone. A
supported supersession instruction does not prove actual attachment reconciliation.

Recognized English, Portuguese and Spanish quoted header groups must not become the
current body's request; a standalone business line beginning `From:` or `De:` must
survive. No deadline must remain blank instead of defaulting to `today`. Local
recommended steps carry `assistant_suggestion` as their source.

## The 22-case matrix

`examples/business_acceptance/cases.json` specifies one observable text checkpoint
per research scenario, together with the wider scenario scope still needing
separate acceptance. `scripts/check_business_acceptance.py` runs those checkpoints
through the production current-email entry point, saves the complete synthetic
results and a human-readable matrix under `Build/business-acceptance`, and exits
nonzero while any checkpoint fails. These known gaps are separate from the source
regression suite. A checkpoint passing is not full acceptance of its original case.

The first-round matrix deliberately included capabilities not implemented then:
invoice/PO/SKU hierarchy, prices per thousand, arbitrary spreadsheet row linkage,
cross-order allocation, document-version reconciliation, scoped PPAP/ISIR verdicts,
inventory vs defect counts, and actual logistics evidence. A missing capability is
reported as a gap rather than marked skipped or silently counted as passing.

## Verification boundary

Run `Runtime/Python3147/python.exe -B scripts/check_business_acceptance.py` for the
22-case matrix and `Runtime/Python3147/python.exe -B -m unittest discover -s tests`
for the regression suite. `scripts/build_windows.ps1` repeats required tests,
builds the Windows program and runs its offline `--self-test` through the real UI.
Source tests, offline UI smoke, simulated provider tests and a human's real-email
acceptance are distinct evidence. This work does not send, import, upload or scan
mail, and does not establish live provider or mailbox quality.

## First-round recorded verification (historical baseline)

On 2026-09-21, the full source suite passed 208 tests (22 new business regression
tests). The build script rebuilt the actual `Program/EmailAssistant/EmailAssistant.exe`
and its self-test passed, including three status notices through the native window,
the review-before-copy gate, input-change invalidation, XLSX quantity parsing and
the existing attachment/service checks. Provider calls and mailbox access were zero.
The detailed build log is `Build/business-build-20260921.log`; the EXE receipt is
`Build/desktop-self-test.json`.

The 22-case matrix produced 8 passing text checkpoints: B03, B05, B07, B08, B09,
B10, B12 and B18. The other 14 are explicitly recorded as gaps. Every case still
has `full_scenario_acceptance: NOT_ESTABLISHED`: neither these text probes nor the
22 regression tests establish complete real-email, document or image understanding.

Standards review initially found two semantic defects: selected attachments kept
an obsolete internal-review/shipping-query draft, and a later correction could
leave an earlier affirmative status promoted. Both were reproduced and corrected.
The review rechecked these fixes with no remaining actionable finding in scope.

Spec review independently identified the stale PPAP draft, then verified the fix
through `analyze_current_email` with a real synthetic selected PDF. It also
independently reproduced the 8/14 checkpoint result and found no inflated coverage
claim. Both review axes passed their bounded re-review; this does not discharge
the explicitly recorded business gaps.

The reproduced cause was generic keyword-to-category advice: it assigned request
language and future-action drafts to declarative messages. Quote cleaning also
missed header groups used by common Portuguese/Spanish/English replies. The fix
keeps bounded notices separate from generic request advice, checks full-clause
coverage before suppressing a reply, rejects uncertain/corrected statements, and
preserves selected-document and supplied-thread review. Conservative matching can
miss equivalent free-form wording; it is intentionally not a general state engine.

The first round's next implementation priority was B02 pricing bases and row linkage, then
B04/B11/B15/B22 quantity roles and scope, followed by B16/B19/B20/B21 scoped
inspection conclusions. B01/B06/B13/B14/B17 need their own focused state, unit or
evidence checks. Actual document version reconciliation and image/PPAP page review
remain separate from all passing text checkpoints.

## Second round: explicit prices, quantity roles and inspection scope

The operator approved implementation and inspection of all locally exported data.
The private audit rehashed both exports, re-parsed MIME parts, checked every known
asset, recovered bounded extraction gaps, enumerated missing archive members and
used local Windows OCR for images and low-text PDF pages. Its records remain under
ignored `Data/mail_research/full_audit_20260921`; this is a research workflow, not
application mailbox scanning or runtime corpus access. The professional glossary
was read as context, not used to invent units or missing approval evidence.

The selected-XLSX parser now recognizes a finite set of explicit price, currency,
quantity-basis and order-unit headers. It keeps item, organization, plant, sheet
and row together, recognizes simple ISO effective dates, resets mappings at table
boundaries and retains the original price/basis beside a Decimal-derived unit
price. Mixed currencies and bases remain separate. Zero/missing/invalid bases and
ambiguous mappings do not produce a derived price. Price facts use a separate
parser-generated channel: source prose that imitates `Price basis:` is not trusted
as a constructed fact. Scope identifiers retain privacy shape checks.

Supported current-body clauses distinguish lot quantity, all-finish inventory,
cargo gross weight and VGM; preserve proposed cross-PO allocation direction;
flag unitless and instruction-dependent lead times; separate salt-spray,
dimensional, color and per-SKU PPAP status; and retain conditional approval.
These are reported statements, not independently verified physical or payment
events. A scoped notice supplements existing complaints, RCA requests, risks and
thread work; it cannot overwrite them. Explicit retractions, cancellation,
hypotheticals, template options and conflicting result declarations are guarded.

The 22 fixed text checkpoints now pass. All 22 retain
`full_scenario_acceptance: NOT_ESTABLISHED`. Seventeen additional regression tests
exercise real selected XLSX parsing, decimal bases and precision, row linkage,
quantity and approval scope, template/retraction counterexamples, privacy and
untrusted-source impersonation. These tests do not establish arbitrary workbook,
free-form language or full real-email acceptance.

Independent Standards and Spec reviews found and drove concrete corrections:
incomplete new headers inheriting prior mappings, stale/retracted prices,
template status promotion, pending PPAP omission, loss of RCA wording,
price-scope privacy bypass and source lines impersonating parser output.
The privacy fix was also checked against short legitimate plant codes.

Runtime limits remain five selected files, 10 MiB each and 25 MiB total; XLSX
reads at most three sheets and 30 rows per sheet under the existing text budgets,
and exposes at most five attachment facts. This is not support for XLS, arbitrary
multi-level/merged headers, formula recalculation, CAD interpretation, image OCR,
checkbox-position recovery, complete version reconciliation or automatic business
approval. Decimal input with excessive source precision is conservatively omitted.
The much wider offline audit/OCR coverage must not be represented as desktop
parser capability. Human review of the resulting real-email advice and draft
remains required.

Second-round release verification on 2026-09-21 passed 225 source tests and all
22 text checkpoints. The rebuilt actual executable passed its offline self-test,
including a selected mixed USD/EA and INR/KG pricing workbook and lot/salt-spray/
dimensional scope through the native window. Review-before-copy and input-change
invalidation passed; provider calls and live mailbox access were both zero.
Standards and Spec bounded re-reviews found no remaining P1/P2 in the reviewed
changes. Evidence is retained in `Build/business-round2/build.log`,
`Build/business-round2/verification.json`, `Build/desktop-self-test.json` and the
22-case matrix. No real-provider, arbitrary-document or operator copy acceptance
is claimed by these automated checks.
