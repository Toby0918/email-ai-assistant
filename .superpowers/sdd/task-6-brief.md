### Task 6: Route OpenAI first, DeepSeek text fallback second, and rules last

**Files:**
- Modify: `backend/email_agent/analysis_route_support.py`
- Modify: `backend/email_agent/analysis_model_routes.py`
- Modify: `backend/email_agent/model_grounding.py`
- Modify: `backend/email_agent/model_result_safety.py`
- Modify: `backend/email_agent/analysis_diagnostics.py`
- Modify: `tests/test_analysis_route_support.py`
- Modify: `tests/test_analysis_model_routes.py`
- Modify: `tests/test_model_grounding.py`
- Modify: `tests/test_model_result_safety.py`
- Modify: `tests/test_analyzer.py`

**Interfaces:**
- OpenAI is model-led and uses existing private envelope parsing/evidence validation/merge.
- `EvidenceSource` gains an internal grounding mode. Visual sources may support qualitative attachment observations but never exact facts or person identification.
- A `ModelRun` records the accepted non-sensitive engine label so the public result reflects OpenAI or DeepSeek text fallback accurately.
- Fallback eligibility requires explicit provider configuration and 12 seconds remaining immediately before the DeepSeek call.

- [x] Write route RED tests for OpenAI acceptance, OpenAI early failure plus DeepSeek success, OpenAI late failure with zero DeepSeek calls, fallback disabled, both providers failing, and injected synthetic generators.
- [x] Write grounding RED tests for permitted damage/label/layout observations and rejected identity, protected trait, exact ID/date/amount/quantity/tracking, URL, tool instruction, or commitment claims.
- [x] Implement provider-neutral model-led preparation, conditional fallback, engine labeling, and sanitized diagnostics.
- [x] Preserve the full deterministic timeline, mandatory risks, exact local fact merge, attachment membership, and human-review flag.
- [x] Run routing/grounding/analyzer suites GREEN; commit `feat: route multimodal analysis with text fallback`.
