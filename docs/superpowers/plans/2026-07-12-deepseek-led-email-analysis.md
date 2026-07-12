---
last_update: 2026-07-12
status: active
owner: "@tobyWang"
review_cycle: weekly
source_type: operation_guide
---

# DeepSeek-Led Current Email Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make explicitly configured DeepSeek V4 the primary analyst for the user-clicked current visible email while backend-owned validation, grounding, safety union, deadlines, and deterministic fallback prevent unsupported facts, commitments, mailbox actions, and data leakage.

**Architecture:** The browser still collects only the current visible message after an Analyze click. The Python backend builds a deterministic timeline and rule result, parses attachments inside terminable worker processes, creates an ephemeral source-labelled and redacted model context, invokes DeepSeek through a dedicated backend provider branch, validates the versioned response envelope and evidence, safely merges only grounded fields, and persists only the unchanged public analysis object.

**Tech Stack:** Python 3.12.13, standard-library `unittest`, `multiprocessing`, SQLite 3.50.4, existing pinned `openai==2.45.0`, beautifulsoup4 4.15.0, openpyxl 3.1.5, pypdf 6.14.2, python-docx 1.2.0, Pillow 12.3.0, pytesseract 0.3.13, Chrome/Edge Manifest V3 JavaScript.

## Global Constraints

- Do not add an unofficial `deepseek` PyPI package. DeepSeek's official Python quick start uses the OpenAI-compatible API, and this repository already pins `openai==2.45.0`; `requirements.txt` therefore remains unchanged.
- Keep `EMAIL_AGENT_LLM_PROVIDER=disabled` and `EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative` as safe defaults. Model-led analysis requires both `deepseek` and `model_led` to be set by the backend operator.
- Use only backend `DEEPSEEK_API_KEY`; never fall back to `OPENAI_API_KEY`, expose a configurable DeepSeek base URL, or place any key in frontend code.
- Fix the endpoint to `https://api.deepseek.com`; allow only `deepseek-v4-flash` and `deepseek-v4-pro`; use JSON output, thinking disabled, temperature `0`, streaming disabled, `max_tokens=2400`, and SDK retries `0`.
- Only an explicit Analyze click may collect or analyze the currently visible message/thread and visible supported resources. Never scan another message, mailbox, folder, account, or background data source.
- Never transmit binary/base64, private download URLs, any URL/URI, credentials, cookies, tokens, paths, or active content. Expanded model context is request-memory-only and must not enter logs, API JSON, SQLite, docs, or fixtures.
- Preserve business identifiers, names, email addresses, quantities, measurements, amounts, dates, deadlines, and table relationships after redaction and within the approved bounds.
- The backend owns the complete bounded timeline skeleton, accepted attachment set/status/limitations, mandatory local safety risks, public schema, source projection, `needs_human_review=true`, and the prohibition on automatic mailbox actions and unconditional commercial/legal commitments.
- The frontend waits at most 35 seconds for the analysis POST after resource collection. The backend uses one 32-second monotonic target, an 8-second hard parser/OCR process deadline, a 25-second maximum provider deadline, a 5-second minimum provider window, and a 2-second response reserve.
- No automated test calls the live DeepSeek API. Live smoke and quality tests require a separate approval, a local key, and fully synthetic data.
- Keep each Python module below the existing 300-line guard and preserve all one-argument test injection seams.

---

### Task 1: Record the dependency decision and add backend-only DeepSeek configuration

**Files:**
- Modify: `.env.example`
- Modify: `backend/email_agent/config.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_static_linter_constraints.py`
- Modify: `docs/constraints/tooling_constraints.md`
- Modify: `docs/operations/deployment_notes.md`

**Interfaces:**
- `AppConfig.deepseek_api_key: str | None`
- `AppConfig.deepseek_model: str`
- `AppConfig.deepseek_timeout_seconds: int`
- `AppConfig.deepseek_output_mode: str`

- [ ] **Step 1: Add failing configuration and dependency-boundary tests**

```python
def test_load_config_has_safe_deepseek_defaults(self) -> None:
    with patch.dict(os.environ, {}, clear=True):
        config = load_config(dotenv_path=None)
    self.assertIsNone(config.deepseek_api_key)
    self.assertEqual(config.deepseek_model, "deepseek-v4-flash")
    self.assertEqual(config.deepseek_timeout_seconds, 25)
    self.assertEqual(config.deepseek_output_mode, "conservative")

def test_deepseek_key_does_not_fall_back_to_openai_key(self) -> None:
    with patch.dict(os.environ, {"OPENAI_API_KEY": "synthetic-openai"}, clear=True):
        config = load_config(dotenv_path=None)
    self.assertIsNone(config.deepseek_api_key)

def test_env_example_has_no_configurable_deepseek_base_url(self) -> None:
    sample = (ROOT / ".env.example").read_text(encoding="utf-8")
    self.assertIn("DEEPSEEK_API_KEY=", sample)
    self.assertIn("EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE=conservative", sample)
    self.assertNotIn("EMAIL_AGENT_DEEPSEEK_BASE_URL", sample)
```

- [ ] **Step 2: Run the focused tests and confirm missing-field failures**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_config tests.test_static_linter_constraints`

Expected: FAIL because the four DeepSeek settings and documentation checks are absent.

- [ ] **Step 3: Add safe defaults without changing `requirements.txt`**

```python
@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    deepseek_api_key: str | None
    deepseek_model: str
    deepseek_timeout_seconds: int
    deepseek_output_mode: str

# inside load_config()
deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
deepseek_model=os.getenv("EMAIL_AGENT_DEEPSEEK_MODEL", "deepseek-v4-flash").strip() or "deepseek-v4-flash",
deepseek_timeout_seconds=min(_int_env("EMAIL_AGENT_DEEPSEEK_TIMEOUT_SECONDS", 25), 25),
deepseek_output_mode=os.getenv("EMAIL_AGENT_DEEPSEEK_OUTPUT_MODE", "conservative").strip().lower() or "conservative",
```

Document that the dedicated provider uses the already pinned OpenAI-compatible SDK and that arbitrary remote base URLs and third-party DeepSeek SDKs are forbidden.

- [ ] **Step 4: Run the focused tests**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_config tests.test_static_linter_constraints`

Expected: PASS.

- [ ] **Step 5: Commit the configuration boundary**

```powershell
git add .env.example backend/email_agent/config.py tests/test_config.py tests/test_static_linter_constraints.py docs/constraints/tooling_constraints.md docs/operations/deployment_notes.md
git commit -m "feat: configure backend DeepSeek provider"
```

### Task 2: Define one cooperative analysis budget

**Files:**
- Create: `backend/email_agent/analysis_budget.py`
- Create: `tests/test_analysis_budget.py`

**Interfaces:**
- `AnalysisBudget.start(clock=time.monotonic) -> AnalysisBudget`
- `remaining_seconds(reserve_seconds=0.0) -> float`
- `stage_deadline(maximum_seconds, reserve_seconds=0.0) -> float`
- `provider_timeout_seconds(configured_timeout_seconds) -> float | None`

- [ ] **Step 1: Write failing exact-budget tests with a fake clock**

```python
def test_provider_timeout_reserves_response_margin_and_obeys_caps(self) -> None:
    now = [100.0]
    budget = AnalysisBudget.start(clock=lambda: now[0])
    self.assertEqual(budget.deadline, 132.0)
    self.assertEqual(budget.provider_timeout_seconds(90), 25.0)
    now[0] = 126.5
    self.assertIsNone(budget.provider_timeout_seconds(25))

def test_parser_stage_uses_one_shared_eight_second_deadline(self) -> None:
    budget = AnalysisBudget(deadline=132.0, _clock=lambda: 100.0)
    self.assertEqual(budget.stage_deadline(8.0, reserve_seconds=2.0), 108.0)
```

- [ ] **Step 2: Run the test and confirm the module is missing**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_analysis_budget`

Expected: FAIL with import error.

- [ ] **Step 3: Implement the monotonic budget**

```python
BACKEND_TARGET_SECONDS = 32.0
RESPONSE_MARGIN_SECONDS = 2.0
PARSER_MAX_SECONDS = 8.0
PROVIDER_MAX_SECONDS = 25.0
PROVIDER_MIN_SECONDS = 5.0

@dataclass(frozen=True, slots=True)
class AnalysisBudget:
    deadline: float
    _clock: Callable[[], float] = field(repr=False, compare=False)

    @classmethod
    def start(cls, *, clock: Callable[[], float] = time.monotonic) -> "AnalysisBudget":
        return cls(deadline=clock() + BACKEND_TARGET_SECONDS, _clock=clock)

    def remaining_seconds(self, *, reserve_seconds: float = 0.0) -> float:
        return max(0.0, self.deadline - self._clock() - reserve_seconds)

    def stage_deadline(self, maximum_seconds: float, *, reserve_seconds: float = 0.0) -> float:
        return self._clock() + min(maximum_seconds, self.remaining_seconds(reserve_seconds=reserve_seconds))

    def provider_timeout_seconds(self, configured_timeout_seconds: float) -> float | None:
        timeout = min(configured_timeout_seconds, PROVIDER_MAX_SECONDS, self.remaining_seconds(reserve_seconds=RESPONSE_MARGIN_SECONDS))
        return timeout if timeout >= PROVIDER_MIN_SECONDS else None
```

- [ ] **Step 4: Run the budget tests**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_analysis_budget`

Expected: PASS.

- [ ] **Step 5: Commit the budget**

```powershell
git add backend/email_agent/analysis_budget.py tests/test_analysis_budget.py
git commit -m "feat: define cooperative analysis budget"
```

### Task 3: Implement the dedicated DeepSeek API client

**Files:**
- Modify: `backend/email_agent/llm_client.py`
- Modify: `tests/test_llm_client.py`

**Interfaces:**
- `generate_analysis(user_prompt, *, system_prompt="", config=None, timeout_seconds=None) -> str`
- Dedicated `deepseek` branch; no DeepSeek-to-Ollama chain.

- [ ] **Step 1: Add failing request-shape, cancellation, validation, and no-chain tests**

```python
async def _never_finishes() -> object:
    await asyncio.Future()
    return object()

def test_deepseek_rejects_unapproved_model_before_network(self) -> None:
    config = replace(load_config(dotenv_path=None), llm_provider="deepseek", deepseek_api_key="synthetic", deepseek_model="other")
    with patch("backend.email_agent.llm_client.AsyncOpenAI") as client:
        with self.assertRaisesRegex(LlmClientError, "unsupported"):
            generate_analysis("{}", system_prompt="json", config=config, timeout_seconds=5)
    client.assert_not_called()

def test_deepseek_failure_never_calls_ollama(self) -> None:
    config = replace(load_config(dotenv_path=None), llm_provider="deepseek", deepseek_api_key="synthetic")
    with patch("backend.email_agent.llm_client._generate_with_deepseek", side_effect=LlmClientError("DeepSeek analysis request failed.")):
        with patch("backend.email_agent.llm_client._generate_with_ollama") as ollama:
            with self.assertRaises(LlmClientError):
                generate_analysis("{}", system_prompt="json", config=config, timeout_seconds=5)
    ollama.assert_not_called()
```

The exact-request test must assert fixed base URL, `max_retries=0`, `response_format={"type": "json_object"}`, `temperature=0`, `stream=False`, `max_tokens=2400`, and `extra_body={"thinking": {"type": "disabled"}}`. The cancellation test uses an unresolved future and a `0.05`-second injected timeout.

- [ ] **Step 2: Run the client tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_llm_client`

Expected: FAIL because no DeepSeek branch or async client exists.

- [ ] **Step 3: Implement the fixed DeepSeek request and sanitized response boundary**

```python
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro"})

async def _generate_with_deepseek(system_prompt: str, user_prompt: str, config: AppConfig, timeout_seconds: float) -> str:
    if config.deepseek_model not in DEEPSEEK_MODELS:
        raise LlmClientError("DeepSeek model is unsupported.")
    effective_timeout = min(timeout_seconds, config.deepseek_timeout_seconds, 25.0)
    try:
        async with asyncio.timeout(effective_timeout):
            async with AsyncOpenAI(api_key=config.deepseek_api_key, base_url=DEEPSEEK_BASE_URL, max_retries=0, timeout=effective_timeout) as client:
                response = await client.chat.completions.create(
                    model=config.deepseek_model,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                    temperature=0,
                    stream=False,
                    max_tokens=2400,
                    extra_body={"thinking": {"type": "disabled"}},
                )
    except TimeoutError:
        raise LlmClientError("DeepSeek analysis request timed out.") from None
    except Exception:
        raise LlmClientError("DeepSeek analysis request failed.") from None
    return _parse_deepseek_response(response)
```

Accept only the first choice when `finish_reason == "stop"` and content is a non-empty string. Reject every other completion reason with a fixed incomplete-response error and suppress exception causes.

- [ ] **Step 4: Run provider and configuration regressions**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_llm_client tests.test_config`

Expected: PASS.

- [ ] **Step 5: Commit the provider**

```powershell
git add backend/email_agent/llm_client.py tests/test_llm_client.py
git commit -m "feat: add bounded DeepSeek provider client"
```

### Task 4: Build a complete bounded timeline and request-local source skeleton

**Files:**
- Modify: `backend/email_agent/thread_timeline.py`
- Modify: `tests/test_thread_timeline.py`

**Interfaces:**
- `ThreadSource`, `TimelineOpenItem`, and `TimelineBuild` frozen dataclasses.
- `build_timeline_skeleton(segments, internal_domains) -> TimelineBuild`
- Existing `build_conversation_timeline()` remains a public-wrapper compatibility seam.

- [ ] **Step 1: Write failing stable-ID and complete-open-item tests**

```python
def test_skeleton_preserves_complete_bounded_open_item_set_and_order(self) -> None:
    build = build_timeline_skeleton(self.synthetic_segments, ("cndlf.com",))
    self.assertEqual([item.open_item_id for item in build.open_items], ["open:0", "open:1"])
    self.assertEqual([source.source_id for source in build.sources], ["thread:0", "thread:1", "thread:2"])
    self.assertEqual(build.public_timeline["open_items"][0]["source"], "thread")
    self.assertNotIn("open_item_id", build.public_timeline["open_items"][0])
```

Add a 20-item test proving the complete accepted set is at most 19 factual items plus one explicit coverage/manual-review guard.

- [ ] **Step 2: Run timeline tests and confirm the current single-item projection fails**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_thread_timeline`

Expected: FAIL on missing skeleton types or incomplete open items.

- [ ] **Step 3: Add backend-owned sources and stable open-item IDs**

```python
@dataclass(frozen=True, slots=True)
class TimelineOpenItem:
    open_item_id: str
    item: str
    owner_hint: str
    due_hint: str
    source: str
    evidence_sources: tuple[str, ...]

@dataclass(frozen=True, slots=True)
class TimelineBuild:
    public_timeline: dict[str, object]
    open_items: tuple[TimelineOpenItem, ...]
    sources: tuple[ThreadSource, ...]

def build_conversation_timeline(segments: list[dict[str, str]], internal_domains: tuple[str, ...]) -> dict[str, object]:
    return build_timeline_skeleton(segments, internal_domains).public_timeline
```

Assign `thread:N` after deterministic ordering and `open:N` after deterministic pending-request ordering. Never expose internal IDs in the public timeline.

- [ ] **Step 4: Run timeline and analyzer regressions**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_thread_timeline tests.test_analyzer`

Expected: PASS.

- [ ] **Step 5: Commit the factual skeleton**

```powershell
git add backend/email_agent/thread_timeline.py tests/test_thread_timeline.py tests/test_analyzer.py
git commit -m "feat: add backend timeline source skeleton"
```

### Task 5: Build bounded ephemeral attachment model context

**Files:**
- Create: `backend/email_agent/attachment_model_context.py`
- Modify: `backend/email_agent/attachment_parser.py`
- Modify: `tests/test_attachment_parser.py`
- Create: `tests/test_attachment_model_context.py`

**Interfaces:**
- `AttachmentAnalysisBundle(display_insight, model_candidate)`
- `sanitize_remote_text(value, max_characters, link_marker=None) -> SanitizedModelText`
- `build_attachment_model_context(candidates) -> tuple[AttachmentModelContextItem, ...]`

- [ ] **Step 1: Write failing privacy, preservation, and size tests**

```python
def test_remote_attachment_text_preserves_business_facts_and_removes_secrets(self) -> None:
    raw = "PO 1013970520 qty 24 due 2026-07-20 USD 1,250 user@example.com https://private.example/a Authorization: Bearer SECRET C:\\private\\a.pdf"
    sanitized = sanitize_remote_text(raw, max_characters=6000)
    self.assertIn("PO 1013970520", sanitized.text)
    self.assertIn("USD 1,250", sanitized.text)
    self.assertIn("user@example.com", sanitized.text)
    self.assertNotIn("private.example", sanitized.text)
    self.assertNotIn("SECRET", sanitized.text)
    self.assertNotIn("C:\\private", sanitized.text)

def test_attachment_context_obeys_per_item_and_total_limits(self) -> None:
    items = build_attachment_model_context(self.synthetic_candidates)
    self.assertLessEqual(sum(len(item.text) for item in items), 24000)
    self.assertTrue(all(len(item.text) <= 6000 for item in items))
```

- [ ] **Step 2: Run focused parser/context tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_attachment_model_context tests.test_attachment_parser`

Expected: FAIL because the private model projection does not exist.

- [ ] **Step 3: Implement dual projections and sanitize before truncation**

```python
MAX_MODEL_CHARACTERS_PER_ATTACHMENT = 6_000
MAX_MODEL_CHARACTERS_TOTAL = 24_000

@dataclass(frozen=True, slots=True, repr=False)
class AttachmentAnalysisBundle:
    display_insight: dict[str, object]
    model_candidate: AttachmentModelCandidate | None

def parse_attachments(items: list[StoredAttachment]) -> list[dict[str, object]]:
    return [bundle.display_insight for bundle in parse_attachment_bundles_compat(items)]
```

Remove all schemes/URI forms, bare and scheme-relative URLs, credential-labelled values, bearer/basic tokens, JWT/key shapes, cookies, Windows/UNC/POSIX/relative paths, and script/macro/active-content markers. Preserve approved business canaries, sanitize before the final bound, and never include attachment URL markers.

- [ ] **Step 4: Run attachment and static safety tests**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_attachment_model_context tests.test_attachment_parser tests.test_static_linter_constraints`

Expected: PASS.

- [ ] **Step 5: Commit dual attachment projections**

```powershell
git add backend/email_agent/attachment_model_context.py backend/email_agent/attachment_parser.py tests/test_attachment_model_context.py tests/test_attachment_parser.py
git commit -m "feat: build ephemeral attachment model context"
```

### Task 6: Isolate attachment decoding in hard-deadline worker processes

**Files:**
- Modify: `backend/email_agent/attachment_parser.py`
- Modify: `backend/email_agent/attachment_docx.py`
- Modify: `backend/email_agent/attachment_text.py`
- Create: `tests/test_attachment_parser_process.py`

**Interfaces:**
- Production `parse_attachment_bundles(items, *, deadline, clock=time.monotonic, mp_context=None)`.
- One shared deadline, one spawned worker at a time, one private `Pipe(duplex=False)` per worker.

- [ ] **Step 1: Write failing real-process timeout and crash tests**

```python
def test_spawned_hanging_worker_is_terminated_and_joined(self) -> None:
    started = time.monotonic()
    result = parse_attachment_bundles([self.synthetic_item], deadline=started + 0.3, mp_context=multiprocessing.get_context("spawn"))
    self.assertLess(time.monotonic() - started, 2.0)
    self.assertEqual(result[0].display_insight["status"], "metadata_only")
    self.assertIn("timed out", " ".join(result[0].display_insight["limitations"]).lower())

def test_no_new_worker_starts_after_shared_deadline(self) -> None:
    result = parse_attachment_bundles(self.three_items, deadline=time.monotonic() - 0.01)
    self.assertEqual(len(result), 3)
    self.assertTrue(all(item.display_insight["status"] == "metadata_only" for item in result))
```

Also test child crash, EOF, malformed one-shot messages, closed endpoints, and that no child remains alive.

- [ ] **Step 2: Run the process tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_attachment_parser_process`

Expected: FAIL because parsing still runs in-process.

- [ ] **Step 3: Implement top-level spawn targets and bounded cleanup**

```python
def _attachment_worker(item: StoredAttachment, source_id: str, deadline: float, send_connection: Connection) -> None:
    bundle = _parse_one_bundle(item, source_id=source_id, deadline=deadline)
    send_connection.send(bundle)

def parse_attachment_bundles(items: list[StoredAttachment], *, deadline: float, clock: Callable[[], float] = time.monotonic, mp_context: BaseContext | None = None) -> list[AttachmentAnalysisBundle]:
    context = mp_context or multiprocessing.get_context("spawn")
    return _parse_with_private_pipes(items, deadline=deadline, clock=clock, context=context)
```

Close the parent's send endpoint immediately after `start()`. At expiry terminate, bounded-join, close both endpoints, discard partial output, return safe metadata-only limitations, and do not start another worker. Keep OCR's internal timeout below the process deadline with one second of cleanup grace.

- [ ] **Step 4: Run process and parser regressions**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_attachment_parser_process tests.test_attachment_parser`

Expected: PASS with no live child processes.

- [ ] **Step 5: Commit process isolation**

```powershell
git add backend/email_agent/attachment_parser.py backend/email_agent/attachment_docx.py backend/email_agent/attachment_text.py tests/test_attachment_parser_process.py tests/test_attachment_parser.py
git commit -m "feat: isolate attachment parsing by deadline"
```

### Task 7: Define the versioned DeepSeek envelope and evidence contract

**Files:**
- Create: `backend/email_agent/deepseek_analysis_schema.py`
- Create: `tests/test_deepseek_analysis_schema.py`

**Interfaces:**
- `parse_deepseek_analysis_v1(raw) -> dict[str, Any]`
- `validate_deepseek_analysis_v1(value) -> dict[str, Any]`
- `canonical_json_pointer(pointer) -> tuple[str, ...]`
- `validate_envelope_evidence(envelope, sources) -> dict[str, tuple[str, ...]]`

- [ ] **Step 1: Write failing schema and RFC 6901 tests**

```python
def test_duplicate_raw_json_keys_fail_closed(self) -> None:
    with self.assertRaises(DeepSeekEnvelopeError):
        parse_deepseek_analysis_v1('{"schema_version":"deepseek_analysis_v1","schema_version":"other"}')

def test_evidence_pointers_are_resolved_from_envelope_root(self) -> None:
    envelope = valid_envelope()
    envelope["field_evidence"] = {"/analysis/summary": ["thread:0"]}
    evidence = validate_envelope_evidence(envelope, self.sources)
    self.assertEqual(evidence["/analysis/summary"], ("thread:0",))
```

Add cases for valid `~0`/`~1`, malformed escapes, leading-zero indexes, `-`, unknown paths, container targets, out-of-scope fields, normalized duplicates, unknown sources, wrong version, and wrong nested types.

- [ ] **Step 2: Run the contract tests and confirm the module is missing**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_deepseek_analysis_schema`

Expected: FAIL with import error.

- [ ] **Step 3: Implement duplicate-key parsing and fail-closed pointer validation**

```python
class DeepSeekEnvelopeError(ValueError):
    pass

def parse_deepseek_analysis_v1(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_object_without_duplicate_keys)
    except (json.JSONDecodeError, UnicodeDecodeError, DeepSeekEnvelopeError):
        raise DeepSeekEnvelopeError("DeepSeek analysis envelope is invalid.") from None
    return validate_deepseek_analysis_v1(value)
```

Require exact `schema_version == "deepseek_analysis_v1"`. Evaluate pointers against the full envelope root; allow only approved model-led text leaves; reject malformed/unknown/container/out-of-scope/noncanonical/duplicate pointers and any unknown evidence source.

- [ ] **Step 4: Run envelope tests**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_deepseek_analysis_schema`

Expected: PASS.

- [ ] **Step 5: Commit the internal response contract**

```powershell
git add backend/email_agent/deepseek_analysis_schema.py tests/test_deepseek_analysis_schema.py
git commit -m "feat: define DeepSeek analysis envelope"
```

### Task 8: Build the source-labelled prompt and validate grounding across every model field

**Files:**
- Modify: `backend/email_agent/prompt_context.py`
- Create: `backend/email_agent/model_grounding.py`
- Modify: `tests/test_prompt_context.py`
- Create: `tests/test_model_grounding.py`

**Interfaces:**
- `EvidenceSource(source_id, kind, grounding_text, public_source, attachment_index, parsed)`.
- `build_deepseek_untrusted_context(...) -> tuple[str, dict[str, EvidenceSource]]`.
- `find_grounding_violations(envelope, evidence, sources) -> tuple[GroundingViolation, ...]`.

- [ ] **Step 1: Write failing positive/negative context and all-leaf grounding tests**

```python
def test_deepseek_context_keeps_business_facts_but_never_links_or_tokens(self) -> None:
    prompt, sources = build_deepseek_untrusted_context(**self.synthetic_context)
    self.assertIn("1013970520", prompt)
    self.assertIn("thread:0", prompt)
    self.assertNotIn("https://", prompt)
    self.assertNotIn("PRIVATE_TOKEN", prompt)
    self.assertNotIn("content_base64", prompt)
    self.assertIn("thread:0", sources)

def test_unsupported_amount_in_reply_body_is_a_grounding_violation(self) -> None:
    envelope = valid_envelope(reply_body="We confirm USD 9,999.")
    violations = find_grounding_violations(envelope, self.evidence, self.sources)
    self.assertEqual(violations[0].pointer, "/analysis/reply_draft/body")
```

Use table-driven tests for identifiers, amounts, dates, deadlines, quantities, measurements, completion/outcome claims, consequential commitments, negated completion, facts in the wrong source, and safe procedural review/check wording in every approved text-leaf family.

- [ ] **Step 2: Run prompt and grounding tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_prompt_context tests.test_model_grounding`

Expected: FAIL because the expanded source registry and grounding checker are absent.

- [ ] **Step 3: Implement the two-role prompt and normalized source checks**

```python
@dataclass(frozen=True, slots=True)
class EvidenceSource:
    source_id: str
    kind: Literal["thread", "attachment"]
    grounding_text: str
    public_source: str
    attachment_index: int | None = None
    parsed: bool = False

@dataclass(frozen=True, slots=True)
class GroundingViolation:
    pointer: str
    reason: str
```

The fixed system prompt must require JSON and include the complete compact envelope example. The user message contains one bounded JSON context whose values are explicitly untrusted. Prefer visible thread sources over duplicating the current body. Resource limitations never receive evidence IDs. Require each critical claim to normalize into every claimed source's grounding text.

- [ ] **Step 4: Run prompt, grounding, and privacy regressions**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_prompt_context tests.test_model_grounding tests.test_attachment_model_context`

Expected: PASS.

- [ ] **Step 5: Commit prompt and grounding**

```powershell
git add backend/email_agent/prompt_context.py backend/email_agent/model_grounding.py tests/test_prompt_context.py tests/test_model_grounding.py
git commit -m "feat: validate DeepSeek field grounding"
```

### Task 9: Safely merge model-led analysis into backend-owned invariants

**Files:**
- Create: `backend/email_agent/model_result_safety.py`
- Modify: `backend/email_agent/analysis_schema.py`
- Modify: `backend/email_agent/rule_analyzer.py`
- Create: `tests/test_model_result_safety.py`
- Modify: `tests/test_analysis_schema.py`
- Modify: `tests/test_rule_analyzer.py`

**Interfaces:**
- `merge_deepseek_analysis_v1(...) -> SafeMergeResult`.
- Final output retains the unchanged public schema.

- [ ] **Step 1: Write failing safe-merge, mandatory-risk, timeline, and schema tests**

```python
def test_mandatory_local_risk_cannot_be_removed_or_downgraded(self) -> None:
    result = merge_deepseek_analysis_v1(self.model_without_risk, fallback=self.fallback_with_security_risk, sources=self.sources, timeline=self.timeline, evidence=self.evidence)
    self.assertEqual(result.analysis["risk_flags"][0], self.fallback_with_security_risk["risk_flags"][0])

def test_unknown_or_omitted_open_item_ids_restore_backend_items_in_order(self) -> None:
    result = merge_deepseek_analysis_v1(self.model_with_unknown_open_id, fallback=self.fallback, sources=self.sources, timeline=self.timeline, evidence=self.evidence)
    self.assertEqual(result.analysis["conversation_timeline"]["open_items"], self.fallback["conversation_timeline"]["open_items"])
```

Cover safe full merge, every fallback unit, invalid action list, unsafe draft, `needs_human_review=false`, invalid attachment augmentation, non-parsed sources, public source projection, and recursive absence of provider-only fields.

- [ ] **Step 2: Run safety/schema/rule tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_model_result_safety tests.test_analysis_schema tests.test_rule_analyzer`

Expected: FAIL because the hard-safety merge and deterministic `security_risk` are absent.

- [ ] **Step 3: Implement the fallback matrix and strengthen nested public types**

```python
@dataclass(frozen=True, slots=True)
class SafeMergeResult:
    analysis: dict[str, Any]
    used_model: bool
    fallback_fields: tuple[str, ...]
```

Replace `summary` and `priority_reason` individually. Replace the entire Decision Brief or action list when a nested field fails. Keep deterministic timeline order/source/owner/due and join wording only by known `open_item_id`. Preserve exact mandatory local prompt-injection, security, and commitment risks first; append only safe nonduplicates. Replace unsafe drafts and force human review. Fall back completely on malformed envelope, global source integrity, language, or final-schema failure.

Strengthen `analysis_schema.py` so tags, risk evidence/recommendation, action description/owner/due, draft subject/body, and review reasons are all strings. Add local detection for explicit credential, password, API-key, authorization, cookie, or token disclosure requests.

- [ ] **Step 4: Run safety and full public-schema regressions**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_model_result_safety tests.test_analysis_schema tests.test_rule_analyzer tests.test_database`

Expected: PASS and provider-only fields are absent from storage.

- [ ] **Step 5: Commit hard-safety merge**

```powershell
git add backend/email_agent/model_result_safety.py backend/email_agent/analysis_schema.py backend/email_agent/rule_analyzer.py tests/test_model_result_safety.py tests/test_analysis_schema.py tests/test_rule_analyzer.py tests/test_database.py
git commit -m "feat: safely merge DeepSeek analysis"
```

### Task 10: Route the provider, parser, config, and deadline through the request path

**Files:**
- Modify: `backend/email_agent/analyzer.py`
- Modify: `backend/email_agent/api.py`
- Modify: `backend/email_agent/server.py`
- Modify: `tests/test_analyzer.py`
- Modify: `tests/test_api.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- `handle_analyze_current_email(payload, analyzer=None, config=None, *, budget=None)`.
- `analyze_current_email(email, llm_generate=None, analysis_engine_label=None, *, config=None, budget=None)`.

- [ ] **Step 1: Write failing propagation, model-led, fallback, and no-chain tests**

```python
def test_api_passes_same_config_and_budget_to_default_analyzer(self) -> None:
    budget = AnalysisBudget.start()
    with patch("backend.email_agent.api.analyze_current_email", return_value=valid_analysis()) as analyze:
        handle_analyze_current_email({"user_confirmed": True}, config=self.config, budget=budget)
    self.assertIs(analyze.call_args.kwargs["config"], self.config)
    self.assertIs(analyze.call_args.kwargs["budget"], budget)

def test_injected_analyzer_remains_one_argument(self) -> None:
    seen = []
    handle_analyze_current_email({"user_confirmed": True}, analyzer=lambda payload: seen.append(payload) or valid_analysis(), config=self.config)
    self.assertEqual(len(seen), 1)
```

Add tests for a safe partial model merge labelled `ai_model`, full rule fallback when no model field survives, provider skip below five seconds, and DeepSeek failure never invoking Ollama.

- [ ] **Step 2: Run request-path tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_analyzer tests.test_api tests.test_server`

Expected: FAIL because config/budget propagation and model-led orchestration are absent.

- [ ] **Step 3: Implement orchestration while preserving injection seams**

```python
def handle_analyze_current_email(payload: dict[str, Any], analyzer: Callable[[dict[str, Any]], dict[str, Any]] | None = None, config: AppConfig | None = None, *, budget: AnalysisBudget | None = None) -> dict[str, Any]:
    current_config = config or load_config()
    current_budget = budget or AnalysisBudget.start()
    analysis = analyzer(analysis_payload) if analyzer is not None else analyze_current_email(analysis_payload, config=current_config, budget=current_budget)
    return {"ok": True, "request_id": f"local-{uuid4().hex}", "analysis": analysis}
```

Start the budget in `server.py` before reading request JSON. Production `analyzer.py` uses the shared parser deadline, builds deterministic fallback and sources first, invokes DeepSeek only when provider/output flags and remaining time allow, parses/grounds/merges the envelope, validates the final public result, and otherwise returns complete rule fallback. Keep the existing conservative/Ollama repair path unchanged.

- [ ] **Step 4: Run backend request-path and provider tests**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_analyzer tests.test_api tests.test_server tests.test_llm_client tests.test_attachment_parser_process`

Expected: PASS.

- [ ] **Step 5: Commit end-to-end backend routing**

```powershell
git add backend/email_agent/analyzer.py backend/email_agent/api.py backend/email_agent/server.py tests/test_analyzer.py tests/test_api.py tests/test_server.py
git commit -m "feat: route DeepSeek-led email analysis"
```

### Task 11: Bound SQLite persistence inside the response margin

**Files:**
- Modify: `backend/email_agent/database.py`
- Modify: `backend/email_agent/server.py`
- Modify: `tests/test_database.py`
- Modify: `tests/test_server.py`

**Interfaces:**
- `connect(path=None, *, busy_timeout_seconds=0.5)`.
- `save_analysis(..., *, busy_timeout_ms=500)`.

- [ ] **Step 1: Write failing SQLite and Python-lock contention tests**

```python
def test_connect_default_busy_timeout_is_below_two_seconds(self) -> None:
    connection = connect(":memory:")
    timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
    self.assertLessEqual(timeout, 500)

def test_database_lock_contention_returns_within_bounded_stage(self) -> None:
    started = time.monotonic()
    response = self.invoke_while_database_lock_is_held()
    self.assertLess(time.monotonic() - started, 2.0)
    self.assertFalse(response["ok"])
```

- [ ] **Step 2: Run database/server tests and confirm the five-second default violates the contract**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_database tests.test_server`

Expected: FAIL on busy timeout or bounded contention.

- [ ] **Step 3: Implement dynamic bounded persistence**

```python
def connect(path: str | None = None, *, busy_timeout_seconds: float = 0.5) -> sqlite3.Connection:
    return sqlite3.connect(path or load_config().sqlite_path, timeout=busy_timeout_seconds)

def save_analysis(connection: sqlite3.Connection, subject: str, sender: str, analysis: dict[str, Any], *, busy_timeout_ms: int = 500) -> int:
    connection.execute(f"PRAGMA busy_timeout = {max(0, busy_timeout_ms)}")
    return _insert_analysis(connection, subject, sender, analysis)
```

At persistence, create a 0.5-second stage deadline with a 0.25-second response floor, acquire the Python database lock only for the remaining stage duration, recompute the remaining milliseconds, set `PRAGMA busy_timeout` while holding the lock, and return a generic persistence error on expiry. Never persist provider-only fields or expanded context.

- [ ] **Step 4: Run database, server, and recursive-privacy tests**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_database tests.test_server tests.test_api`

Expected: PASS.

- [ ] **Step 5: Commit bounded persistence**

```powershell
git add backend/email_agent/database.py backend/email_agent/server.py tests/test_database.py tests/test_server.py
git commit -m "fix: bound analysis persistence waits"
```

### Task 12: Align frontend wait and persistent remote-processing disclosure

**Files:**
- Modify: `frontend/browser_extension/shared/api_client.js`
- Modify: `frontend/browser_extension/popup.html`
- Modify: `frontend/browser_extension/popup.js`
- Modify: `frontend/local_debug_page/index.html`
- Modify: `frontend/local_debug_page/app.js`
- Modify: `tests/test_browser_extension_task6_contracts.py`
- Modify: `tests/test_browser_extension_static.py`
- Modify: `tests/test_frontend_local_debug.py`

**Interfaces:**
- `MAX_ANALYZE_TIMEOUT_MS = 35000` for the analysis POST only.
- Persistent pre-click text says a configured remote AI provider receives the bounded current visible message/thread and supported attachment text.

- [ ] **Step 1: Write failing timeout, disclosure, and forbidden-frontend tests**

```python
def test_analysis_post_wait_is_35_seconds_and_resource_collection_stays_20_seconds(self) -> None:
    source = API_CLIENT.read_text(encoding="utf-8")
    self.assertIn("MAX_ANALYZE_TIMEOUT_MS = 35000", source)
    self.assertIn("RESOURCE_COLLECTION_TIMEOUT_MS = 20000", source)

def test_frontend_never_contains_deepseek_key_or_direct_endpoint(self) -> None:
    source = all_frontend_source()
    self.assertNotIn("DEEPSEEK_API_KEY", source)
    self.assertNotIn("api.deepseek.com", source)
```

Add assertions that caller overrides remain capped at 35 seconds and that the notice is visible before the Analyze click in both UIs.

- [ ] **Step 2: Run frontend contract tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_task6_contracts tests.test_browser_extension_static tests.test_frontend_local_debug`

Expected: FAIL on the existing 15-second timeout and absent notice.

- [ ] **Step 3: Apply bounded wait and generic disclosure**

```javascript
const MAX_ANALYZE_TIMEOUT_MS = 35000;

function boundedAnalyzeTimeout(requestedTimeoutMs) {
  const requested = Number.isFinite(requestedTimeoutMs) ? requestedTimeoutMs : MAX_ANALYZE_TIMEOUT_MS;
  return Math.min(Math.max(requested, 1), MAX_ANALYZE_TIMEOUT_MS);
}
```

Keep resource collection separately capped at 20 seconds. The disclosure names a configured remote AI provider, not the backend key, provider endpoint, or secret configuration.

- [ ] **Step 4: Run JavaScript syntax and frontend behavior tests**

Run: `node --check frontend/browser_extension/shared/api_client.js`

Run: `node --check frontend/browser_extension/popup.js`

Run: `node --check frontend/local_debug_page/app.js`

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_task6_contracts tests.test_browser_extension_static tests.test_frontend_local_debug`

Expected: PASS.

- [ ] **Step 5: Commit frontend timeout and disclosure**

```powershell
git add frontend/browser_extension/shared/api_client.js frontend/browser_extension/popup.html frontend/browser_extension/popup.js frontend/local_debug_page/index.html frontend/local_debug_page/app.js tests/test_browser_extension_task6_contracts.py tests/test_browser_extension_static.py tests/test_frontend_local_debug.py
git commit -m "fix: align remote analysis wait and disclosure"
```

### Task 13: Add a synthetic quality gate and synchronize contracts

**Files:**
- Create: `tests/fixtures/deepseek_eval/cases.json`
- Create: `scripts/evaluate_deepseek_analysis.py`
- Create: `tests/test_evaluate_deepseek_analysis.py`
- Modify: `docs/prompts/analyzer_prompt.md`
- Modify: `docs/data/analysis_result_schema.md`
- Modify: `docs/api/backend_api_contract.md`
- Modify: `docs/security/email_data_handling.md`
- Create: `docs/decisions/0005-deepseek-led-analysis.md`
- Modify: `docs/operations/deepseek_api_analysis_task_brief.md`
- Modify: `docs/superpowers/specs/2026-07-12-deepseek-led-email-analysis-design.md`

**Interfaces:**
- Offline evaluation consumes 50 synthetic cases and recorded rule/model public results; it never requires a live key.
- Quality gate reports schema pass rate, mandatory-risk retention, unsupported-critical-fact count, commitment/action violations, fallback rate, and latency samples when present.

- [ ] **Step 1: Write failing evaluation and documentation tests**

```python
def test_evaluation_rejects_unsupported_critical_fact(self) -> None:
    report = evaluate_cases([self.case_with_unsupported_amount])
    self.assertEqual(report["unsupported_critical_fact_count"], 1)

def test_fixture_contains_50_synthetic_cases(self) -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    self.assertEqual(len(cases), 50)
    self.assertTrue(all("synthetic" in case["provenance"] for case in cases))
```

- [ ] **Step 2: Run evaluation and static documentation tests and confirm red**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_evaluate_deepseek_analysis tests.test_static_linter_constraints`

Expected: FAIL because the harness, fixtures, and synchronized contracts are absent.

- [ ] **Step 3: Implement deterministic offline evaluation and update docs**

```python
def evaluate_cases(cases: list[dict[str, object]]) -> dict[str, object]:
    count = len(cases)
    return {
        "case_count": count,
        "schema_pass_rate": _ratio(cases, "schema_passed"),
        "mandatory_risk_retention_rate": _ratio(cases, "mandatory_risks_retained"),
        "unsupported_critical_fact_count": _count_false(cases, "critical_facts_grounded"),
        "commitment_action_violation_count": _count_false(cases, "commitment_action_safe"),
        "fallback_rate": _ratio(cases, "used_fallback"),
    }
```

Update prompt, internal-envelope/public-schema separation, API invariants, remote-processing/caching disclosure, rollback flags, fixed endpoint/models, deadline semantics, dependency decision, and synthetic-only test policy. Set design and task brief to `active` and mark written review complete.

- [ ] **Step 4: Run evaluation and documentation guards**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_evaluate_deepseek_analysis tests.test_static_linter_constraints tests.test_architecture_constraints tests.test_mechanical_rule_constraints`

Expected: PASS.

- [ ] **Step 5: Commit evaluation and synchronized contracts**

```powershell
git add tests/fixtures/deepseek_eval/cases.json scripts/evaluate_deepseek_analysis.py tests/test_evaluate_deepseek_analysis.py docs/prompts/analyzer_prompt.md docs/data/analysis_result_schema.md docs/api/backend_api_contract.md docs/security/email_data_handling.md docs/decisions/0005-deepseek-led-analysis.md docs/operations/deepseek_api_analysis_task_brief.md docs/superpowers/specs/2026-07-12-deepseek-led-email-analysis-design.md
git commit -m "docs: align DeepSeek analysis contracts"
```

### Task 14: Regenerate project status and complete release verification

**Files:**
- Modify: `docs/operations/project_status_log.md`
- Modify: `docs/operations/deepseek_api_analysis_task_brief.md`

- [ ] **Step 1: Run the complete focused DeepSeek suite**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_config tests.test_analysis_budget tests.test_llm_client tests.test_thread_timeline tests.test_attachment_model_context tests.test_attachment_parser_process tests.test_deepseek_analysis_schema tests.test_prompt_context tests.test_model_grounding tests.test_model_result_safety tests.test_analyzer tests.test_api tests.test_server tests.test_database tests.test_evaluate_deepseek_analysis`

Expected: PASS.

- [ ] **Step 2: Regenerate the project status log**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -B scripts/generate_project_status.py --output docs/operations/project_status_log.md`

Expected: exit `0` and an updated 2026-07-12 status entry.

- [ ] **Step 3: Run the full Python suite and maintenance scan after status generation**

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest discover -s tests`

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -B scripts/maintenance_scan.py`

Expected: all tests PASS and maintenance scan reports no unresolved findings.

- [ ] **Step 4: Run all frontend and mechanical release checks**

Run: `node --check frontend/browser_extension/content/current_message_collector.js`

Run: `node --check frontend/browser_extension/content/exmail_adapter.js`

Run: `node --check frontend/browser_extension/shared/api_client.js`

Run: `node --check frontend/browser_extension/shared/render_analysis.js`

Run: `node --check frontend/browser_extension/popup.js`

Run: `node --check frontend/browser_extension/background.js`

Run: `node --check frontend/local_debug_page/app.js`

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -c "import json, pathlib; json.loads(pathlib.Path('frontend/browser_extension/manifest.json').read_text(encoding='utf-8')); print('manifest json: OK')"`

Run: `C:\Users\33506\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -m unittest tests.test_browser_extension_manifest tests.test_architecture_constraints tests.test_static_linter_constraints`

Expected: every command exits `0`.

- [ ] **Step 5: Inspect the final diff, mark the task brief record complete, and commit status**

Run: `git diff --check`

Run: `git status --short`

Update the task brief execution record with actual files, test counts, and any explicitly deferred live/synthetic API checks. Then run:

```powershell
git add docs/operations/project_status_log.md docs/operations/deepseek_api_analysis_task_brief.md
git commit -m "chore: record DeepSeek analysis completion"
```

Expected: clean diff checks, no secret/local database/real mail files staged, and a bounded handoff that requires separate approval for any live DeepSeek or real Tencent Exmail test.
