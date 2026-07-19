---
last_update: 2026-07-17
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# Labeled MOQ Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make a final, explicitly labeled MOQ alternative an authoritative local fact that closes only the quantity request and cannot be contradicted by accepted provider prose.

**Architecture:** One finite local parser owns MOQ recognition and canonical signatures. Deterministic facts, thread topics/outcomes, model grounding, and a clause-local consistency gate reuse that parser. Provider exact-fact authority stays unchanged and tests use only recreated values.

**Tech Stack:** Python 3.12.13, standard-library `re` and `dataclasses`, existing `unittest` suite. No dependency changes.

## Global Constraints

- Work only in `.worktrees/multimodal-plan-c` and preserve unrelated root-checkout changes.
- Use synthetic `example.test` data and recreated values such as `1200/1400`; never copy the real message values into code, tests, docs, logs, or Git.
- Keep exact quantities locally authoritative; do not allow provider-authored exact values to replace backend facts.
- Keep provider defaults, public HTTP fields, SQLite schema, and reply human-review rules unchanged.
- Run no live provider, mailbox, browser, vault, or real-data operation.

---

### Task 1: Add the strict labeled quantity parser

**Files:**
- Create: `backend/email_agent/quantity_facts.py`
- Create: `tests/test_quantity_facts.py`

**Interfaces:**
- Produces `LabeledQuantityFact(display: str, signatures: tuple[str, ...])`.
- Produces `labeled_quantity_facts(text: object) -> tuple[LabeledQuantityFact, ...]`.
- Produces `has_final_labeled_quantity_statement(text: object) -> bool`.

- [ ] **Step 1: Write failing parser tests**

```python
class LabeledQuantityFactsTests(unittest.TestCase):
    def test_strict_labeled_moq_slash_alternatives_are_canonicalized(self) -> None:
        facts = labeled_quantity_facts("Best MOQ is 1200 / 1400 pcs.")
        self.assertEqual(("MOQ 1200/1400 pcs",), tuple(item.display for item in facts))
        self.assertEqual(
            ("quantity:moq:1200/1400", "quantity:moq-unit:1200/1400:pcs"),
            facts[0].signatures,
        )

    def test_bare_slash_values_dates_ratios_and_contacts_are_rejected(self) -> None:
        for text in ("1200/1400", "2026/07/17", "ratio 1/2", "+86 1200 1400"):
            with self.subTest(text=text):
                self.assertEqual((), labeled_quantity_facts(text))

    def test_pending_moq_is_not_a_final_statement(self) -> None:
        self.assertFalse(has_final_labeled_quantity_statement("MOQ 1200/1400 is pending confirmation."))
```

- [ ] **Step 2: Run RED**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_quantity_facts -v
```

Expected: import failure for the missing `backend.email_agent.quantity_facts` module.

- [ ] **Step 3: Implement the finite parser**

```python
from __future__ import annotations

import re
from dataclasses import dataclass

_LABEL = r"(?:MOQ|minimum\s+order\s+(?:qty|quantity)|最低起订量|最低订购量)"
_VALUE = r"[1-9]\d{0,8}(?:,[0-9]{3})*"
_UNIT = r"(?:pc|pcs|pieces|unit|units|set|sets|件|个|套)"
_FACT_RE = re.compile(
    rf"(?P<prefix>\bbest\s+|最佳)?(?P<label>{_LABEL})\s*"
    rf"(?:is|are|为|是|[:=：])?\s*"
    rf"(?P<values>{_VALUE}(?:\s*/\s*{_VALUE}){{0,3}})\s*(?P<unit>{_UNIT})?",
    re.IGNORECASE,
)
_NON_FINAL_RE = re.compile(
    r"\b(?:pending|to\s+be\s+confirmed|not\s+final|unknown)\b|待确认|未明确|未最终确认",
    re.IGNORECASE,
)

@dataclass(frozen=True, slots=True)
class LabeledQuantityFact:
    display: str
    signatures: tuple[str, ...]

def labeled_quantity_facts(text: object) -> tuple[LabeledQuantityFact, ...]:
    if not isinstance(text, str) or not text:
        return ()
    output: list[LabeledQuantityFact] = []
    for match in _FACT_RE.finditer(text):
        clause = _clause_containing(text, match.start(), match.end())
        if _NON_FINAL_RE.search(clause):
            continue
        values = "/".join(part.replace(",", "") for part in re.split(r"\s*/\s*", match.group("values")))
        unit = _canonical_unit(match.group("unit") or "")
        signatures = [f"quantity:moq:{values}"]
        if unit:
            signatures.append(f"quantity:moq-unit:{values}:{unit}")
        display = f"MOQ {values}{f' {unit}' if unit else ''}"
        fact = LabeledQuantityFact(display, tuple(signatures))
        if fact not in output:
            output.append(fact)
    return tuple(output)

def has_final_labeled_quantity_statement(text: object) -> bool:
    return bool(labeled_quantity_facts(text))
```

Implement `_clause_containing` with a fixed split boundary of newline, `.`, `;`, `。`, or `；`, and `_canonical_unit` with a closed mapping to `pcs`, `units`, or `sets`.

- [ ] **Step 4: Run GREEN**

Run the Task 1 command again. Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/email_agent/quantity_facts.py tests/test_quantity_facts.py
git commit -m "feat: parse labeled MOQ facts"
```

### Task 2: Integrate MOQ into facts and thread resolution

**Files:**
- Modify: `backend/email_agent/email_facts.py`
- Modify: `backend/email_agent/thread_requests.py`
- Modify: `backend/email_agent/thread_outcomes.py`
- Modify: `tests/test_email_facts.py`
- Modify: `tests/test_rule_analyzer.py`
- Modify: `tests/test_thread_timeline.py`

**Interfaces:**
- Consumes `labeled_quantity_facts` and `has_final_labeled_quantity_statement` from Task 1.
- Keeps `EmailFacts.quantities` and public timeline shapes unchanged.

- [ ] **Step 1: Write failing integration tests**

Add a fact test asserting `extract_email_facts(... clean_body="Best MOQ is 1200/1400 pcs.")` contains exactly `MOQ 1200/1400 pcs` as the labeled fact. Add timeline tests with an external request for MOQ and sample timing followed by an internal final MOQ answer; assert `current_status == "partially_resolved"`, no quantity open item remains, and the sample item remains. Add a negative case where MOQ is pending and a case proving `minimum order quantity` does not create an `order` topic.

- [ ] **Step 2: Run RED**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_email_facts tests.test_rule_analyzer tests.test_thread_timeline -v
```

Expected: labeled fact absent, quantity request unresolved, and/or duplicate order topic present.

- [ ] **Step 3: Add minimal integration**

```python
def _find_quantities(text: str) -> list[str]:
    labeled = [fact.display for fact in labeled_quantity_facts(text)]
    patterns = [
        r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\s*(?:pcs|pieces|units|pc|sets|kg)\b",
        r"\b\d+(?:\.\d+)?\s*(?:pcs|pieces|units|pc|sets|kg)\b",
    ]
    return _unique_short([*labeled, *_find_all(patterns, text)])
```

Change the quantity topic to include the accepted MOQ labels. Change the order topic so `order` inside `minimum order quantity` is excluded. In `evidence_flags`, combine the existing outcome result with `has_final_labeled_quantity_statement(text)` and preserve the existing blocker/negation precedence.

- [ ] **Step 4: Run GREEN and regression**

Run the Task 2 command, then:

```powershell
& $py -B -m unittest tests.test_golden_email_analysis tests.test_analysis_schema -v
```

Expected: all tests pass with unchanged public shapes.

- [ ] **Step 5: Commit**

```powershell
git add backend/email_agent/email_facts.py backend/email_agent/thread_requests.py backend/email_agent/thread_outcomes.py tests/test_email_facts.py tests/test_rule_analyzer.py tests/test_thread_timeline.py
git commit -m "fix: resolve answered MOQ requests"
```

### Task 3: Ground the full MOQ and reject known-fact contradictions

**Files:**
- Create: `backend/email_agent/model_known_fact_consistency.py`
- Modify: `backend/email_agent/model_grounding.py`
- Modify: `backend/email_agent/model_result_safety.py`
- Create: `tests/test_model_known_fact_consistency.py`
- Modify: `tests/test_model_grounding.py`
- Modify: `tests/test_model_result_safety.py`
- Modify: `tests/test_analyzer.py`

**Interfaces:**
- Consumes canonical MOQ signatures from Task 1.
- Produces `provider_claims_known_moq_unresolved(provider_value, local_key_facts) -> bool`.
- Falls back only conflicting fields; exact local `decision_brief.key_facts` remain unchanged.

- [ ] **Step 1: Write failing grounding and consistency tests**

Use synthetic source text `Best MOQ is 1200/1400 pcs.`. Assert the full matching model phrase is grounded as one fact, while `MOQ 1200/1500 pcs` and `MOQ 1200 pcs` are rejected. Assert a model field saying MOQ remains pending falls back when local key facts contain the final MOQ, while `MOQ is known; attachment details remain pending` stays eligible.

- [ ] **Step 2: Run RED**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest tests.test_model_grounding tests.test_model_known_fact_consistency tests.test_model_result_safety tests.test_analyzer -v
```

Expected: missing module and accepted mismatch/contradiction failures.

- [ ] **Step 3: Add canonical signatures and clause-local consistency**

In `_critical_signatures`, append every `fact.signatures` item from `labeled_quantity_facts(text)` before returning the deduplicated tuple.

```python
def provider_claims_known_moq_unresolved(
    provider_value: object,
    local_key_facts: object,
) -> bool:
    known = _known_moq_signatures(local_key_facts)
    if not known:
        return False
    for clause in _public_text_clauses(provider_value):
        if _MOQ_LABEL_RE.search(clause) and _UNRESOLVED_RE.search(clause):
            if not _KNOWN_RE.search(clause):
                return True
    return False
```

Call this check during safe merge after ordinary grounding and before final validation. Restore only the conflicting top-level field from `fallback`, add that field to `kept`, and preserve unrelated accepted fields.

- [ ] **Step 4: Run GREEN and end-to-end regression**

Run the Task 3 command. Expected: all tests pass, local key fact survives, and no result claims it is pending.

- [ ] **Step 5: Commit**

```powershell
git add backend/email_agent/model_known_fact_consistency.py backend/email_agent/model_grounding.py backend/email_agent/model_result_safety.py tests/test_model_known_fact_consistency.py tests/test_model_grounding.py tests/test_model_result_safety.py tests/test_analyzer.py
git commit -m "fix: keep known MOQ facts consistent"
```

### Task 4: Synchronize contracts and run release gates

**Files:**
- Modify: `docs/operations/current_email_grounding_and_attachment_repair_task_brief.md`
- Modify: `docs/operations/project_status_log.md`
- Modify: `docs/operations/testing_checklist.md`
- Modify: relevant documentation-contract/status tests

- [ ] **Step 1: Update active documentation from implemented behavior**

Record the finite labels, negative cases, local exact-fact authority, and independent resolution behavior. Do not include the real observed quantity.

- [ ] **Step 2: Run full verification**

```powershell
$py = 'C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$env:PYTHONPATH = "$(Get-Location);C:\Users\33506\OneDrive\文档\DELIFU\email-ai-assistant\.venv\Lib\site-packages;C:\Users\33506\AppData\Local\Programs\Python\Python312\Lib\site-packages"
& $py -B -m unittest discover -s tests
& $py -B scripts/generate_project_status.py --output docs/operations/project_status_log.md
& $py -B -m unittest discover -s tests
& $py -B scripts/maintenance_scan.py
& $py -B scripts/repository_leakage_scan.py
git diff --check
```

Expected: full suite passes, scans exit 0, and no real-derived value or sensitive artifact is found.

- [ ] **Step 3: Commit**

```powershell
git add docs/operations/current_email_grounding_and_attachment_repair_task_brief.md docs/operations/project_status_log.md docs/operations/testing_checklist.md tests
git commit -m "docs: record MOQ grounding verification"
```
