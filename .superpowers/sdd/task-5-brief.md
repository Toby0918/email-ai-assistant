### Task 5: Implement the OpenAI Responses multimodal client

**Files:**
- Create: `backend/email_agent/model_request.py`
- Create: `backend/email_agent/openai_multimodal_client.py`
- Modify: `backend/email_agent/llm_client.py`
- Modify: `backend/email_agent/prompt_context.py`
- Modify: `backend/email_agent/private_context_gate.py`
- Modify: `tests/test_llm_client.py`
- Create: `tests/test_openai_multimodal_client.py`
- Modify: `tests/test_prompt_context.py`
- Modify: `tests/test_private_context_gate.py`

**Interfaces:**
- `ModelAnalysisRequest` contains only locally deidentified text plus request-local sanitized media assets.
- OpenAI input is one user message whose content starts with `input_text`; every media item is immediately preceded by an opaque `UNTRUSTED_BINARY_SOURCE` marker and followed by `input_image` or PDF `input_file`.
- Remote filenames are `attachment_0.pdf` or equivalent opaque names.
- Responses call uses `gpt-5.6-sol`, fixed official endpoint, JSON-object mode, `store=false`, `stream=false`, `max_retries=0`, no tools, `detail=high`, low output verbosity, bounded reasoning, 2,400 output tokens, and at most 35 seconds.
- The client returns only non-empty `response.output_text` or a fixed `LlmClientError.reason_code`.

- [x] Write an async-client fake and RED tests for exact request shape, source/media adjacency, fixed model/endpoint, no Files API, no private URL/path/original filename, and all timeout/empty/incomplete/provider error mappings.
- [x] Add RED tests proving media cannot bypass text privacy failure and that output crosses the existing private-output gate.
- [x] Implement the request builder and Responses call without adding a dependency.
- [x] Keep the existing DeepSeek Chat Completions request unchanged and text-only.
- [x] Run client/prompt/privacy tests GREEN; commit `feat: add OpenAI multimodal analysis client`.
