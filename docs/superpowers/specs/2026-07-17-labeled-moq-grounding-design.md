---
last_update: 2026-07-17
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: product_spec
---

# Labeled MOQ Grounding Design

## Goal

Make an explicitly labeled, final MOQ alternative in the currently visible thread an authoritative local fact. The result may still report unrelated missing attachment or sample information, but it must not describe that known MOQ as unknown or pending.

## Root cause

The current deterministic chain has four independent gaps:

1. `email_facts._find_quantities` recognizes only numbers with units.
2. `thread_requests` does not map MOQ to `quantity`, and the phrase `minimum order quantity` can also create a false `order` topic.
3. `thread_outcomes` recognizes only generic completion words, not a final labeled quantity answer.
4. `model_grounding` and `model_result_safety` cannot detect either a changed MOQ value or a qualitative contradiction such as saying a locally known MOQ is still pending.

This is a deterministic grounding defect, not a reason to give the remote model more authority.

## Strict parser

Add `backend/email_agent/quantity_facts.py` as the only parser for labeled MOQ facts.

```python
@dataclass(frozen=True, slots=True)
class LabeledQuantityFact:
    display: str
    signatures: tuple[str, ...]

def labeled_quantity_facts(text: object) -> tuple[LabeledQuantityFact, ...]: ...
def has_final_labeled_quantity_statement(text: object) -> bool: ...
```

Accepted labels are `MOQ`, `minimum order qty`, `minimum order quantity`, `最低起订量`, and `最低订购量`. Optional `best` or `最佳` and finite connectors are accepted. One to four positive integers may be separated by `/`; units are limited to `pc`, `pcs`, `pieces`, `unit`, `units`, `set`, `sets`, `件`, `个`, or `套`.

The label is mandatory. Bare slash pairs, dates, ratios, phone-like values, negative or zero values, and statements containing `pending`, `decision pending`, `to be confirmed`, `not final`, `待确认`, or `未明确` in the same clause are rejected. Tests use recreated values such as `1200/1400`, never the real message value.

Canonical display uses `MOQ <values>` with one optional canonical unit. Canonical signatures bind the full alternative set, for example `quantity:moq:1200/1400`; a single member cannot ground the full fact.

## Deterministic integration

`email_facts._find_quantities` prepends canonical labeled facts and then preserves the existing unit-quantity extraction. Duplicate strings remain deduplicated by the existing bounded helper. Rule-generated key facts continue to own exact quantities.

`thread_requests._TOPIC_PATTERNS` maps all accepted labels to `quantity`. The generic `order` pattern excludes the `minimum order quantity` phrase so one request does not become both quantity and order.

`thread_outcomes.evidence_flags` treats a final labeled MOQ statement as positive outcome evidence only for the quantity topic. A pending/non-final statement remains a blocker or neutral evidence. Existing identifier and topic matching still decides which prior request can close.

## Provider grounding and contradiction handling

`model_grounding._critical_signatures` includes the shared canonical MOQ signatures. A provider may repeat a locally sourced MOQ only when the complete alternative set is grounded by the cited text. A changed member, omitted member, or invented unit is rejected.

Add `backend/email_agent/model_known_fact_consistency.py`:

```python
def provider_claims_known_moq_unresolved(
    provider_value: object,
    local_key_facts: object,
) -> bool: ...
```

The check is clause-local. It rejects a provider clause that combines an MOQ label with unknown/pending language when the fallback key facts contain a final labeled MOQ. It does not reject a clause that says the MOQ is known while a different attachment detail remains pending. Only the conflicting public field falls back; unrelated grounded model fields remain eligible.

## Safety properties

- Exact quantity authority remains local.
- No provider is required for the fix.
- No real email value enters tests, docs, logs, or Git.
- The parser is label-bound and finite, so ordinary dates, ratios, IDs, and phone numbers do not become MOQ facts.
- A resolved MOQ does not automatically resolve samples, lead time, attachments, quotation, or any other topic.

## Acceptance

- Final labeled alternatives are canonicalized and locally surfaced.
- Pending labeled values are not final facts.
- Quantity closes independently in a mixed thread.
- Grounding rejects changed alternatives.
- Known MOQ and unresolved attachment detail can coexist without contradiction.
