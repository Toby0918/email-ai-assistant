"""Fixed OpenAI Responses client for deidentified text and sanitized media."""

from __future__ import annotations
import asyncio
import base64
import math
import os
from collections.abc import Callable
from typing import Any

from openai import AsyncOpenAI

from .llm_errors import LlmClientError, _deepseek_failure_reason
from .model_request import MAX_MODEL_REQUEST_TEXT_CHARACTERS, ModelAnalysisRequest
from .multimodal_media import (
    MAX_PREPARED_MEDIA_ASSETS,
    MAX_PREPARED_MEDIA_BYTES,
    MAX_SANITIZED_ASSET_BYTES,
    PreparedMediaAsset,
)
from .private_analysis_route import (
    PrivateAnalysisRouteError,
    validate_private_provider_output,
)
from .private_context_gate import model_request_text_is_private_safe
from .prompt_context import OPENAI_MULTIMODAL_SYSTEM_PROMPT


OPENAI_MODEL = "gpt-5.6-sol"
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_PROVIDER_MAX_SECONDS = 35.0
OPENAI_MAX_OUTPUT_TOKENS = 2_400
_BINARY_SOURCE_MARKER = "UNTRUSTED_BINARY_SOURCE"
_UNSUPPORTED_OPENAI_ENVIRONMENT = (
    "OPENAI_ORG_ID",
    "OPENAI_PROJECT_ID",
    "OPENAI_CUSTOM_HEADERS",
    "OPENAI_ADMIN_KEY",
)


async def generate_openai_multimodal_analysis(
    request: ModelAnalysisRequest,
    *,
    api_key: str | None,
    model: str,
    timeout_seconds: float,
    client_factory: Callable[..., Any] | None = None,
) -> str:
    """Return one privacy-gated non-empty Responses output or a fixed error."""
    _validate_call(request, api_key, model)
    effective_timeout = _effective_timeout(timeout_seconds)
    _validate_sdk_environment()
    content = _validated_content_snapshot(request)
    factory = AsyncOpenAI if client_factory is None else client_factory
    try:
        response = await _request_response(
            content, api_key, effective_timeout, factory
        )
    except TimeoutError:
        raise LlmClientError(
            "OpenAI analysis request timed out.", reason_code="provider_timeout"
        ) from None
    except LlmClientError:
        raise
    except Exception as exc:
        raise LlmClientError(
            "OpenAI analysis request failed.",
            reason_code=_deepseek_failure_reason(exc),
        ) from None
    return _validated_output(response)


def _validate_call(
    request: object, api_key: object, model: object,
) -> None:
    if model != OPENAI_MODEL:
        raise LlmClientError(
            "OpenAI model is unsupported.", reason_code="unsupported_model"
        )
    if type(api_key) is not str or not api_key.strip():
        raise LlmClientError(
            "OpenAI API key is not configured for backend analysis.",
            reason_code="missing_key",
        )
    if type(request) is not ModelAnalysisRequest:
        _invalid_request()


def _validate_sdk_environment() -> None:
    if any(os.environ.get(name) for name in _UNSUPPORTED_OPENAI_ENVIRONMENT):
        _invalid_request()


async def _request_response(
    content: list[dict[str, object]],
    api_key: str,
    timeout: float,
    factory: Callable[..., Any],
) -> object:
    async with asyncio.timeout(timeout):
        async with factory(
            api_key=api_key,
            base_url=OPENAI_BASE_URL,
            max_retries=0,
            timeout=timeout,
        ) as client:
            return await client.responses.create(
                model=OPENAI_MODEL,
                instructions=OPENAI_MULTIMODAL_SYSTEM_PROMPT,
                input=[{"role": "user", "content": content}],
                text={"verbosity": "low"},
                reasoning={"effort": "low"},
                max_output_tokens=OPENAI_MAX_OUTPUT_TOKENS,
                store=False,
                stream=False,
                tools=[],
            )


def _effective_timeout(timeout_seconds: object) -> float:
    try:
        requested = float(timeout_seconds)
    except (TypeError, ValueError):
        requested = 0.0
    if not math.isfinite(requested) or requested <= 0:
        raise LlmClientError(
            "OpenAI analysis request timed out.", reason_code="provider_timeout"
        )
    return min(requested, OPENAI_PROVIDER_MAX_SECONDS)


def _validated_content_snapshot(
    request: ModelAnalysisRequest,
) -> list[dict[str, object]]:
    text = request.text
    _validate_private_text(text)
    snapshots = _validated_media_snapshots(request.media_assets)
    try:
        content: list[dict[str, object]] = [
            {"type": "input_text", "text": text}
        ]
        for source_id, filename, mime_type, kind, data in snapshots:
            content.append({
                "type": "input_text",
                "text": f"{_BINARY_SOURCE_MARKER} {source_id}",
            })
            content.append(_media_content(filename, mime_type, kind, data))
        return content
    except LlmClientError:
        raise
    except Exception:
        _invalid_request()
    finally:
        _wipe_raw_snapshots(snapshots)


def _validate_private_text(text: object) -> None:
    try:
        invalid = (
            type(text) is not str
            or not text.strip()
            or len(text) > MAX_MODEL_REQUEST_TEXT_CHARACTERS
            or not model_request_text_is_private_safe(text)
        )
    except Exception:
        _invalid_request()
    if invalid:
        _invalid_request()


def _validated_media_snapshots(
    assets: object,
) -> list[tuple[str, str, str, str, bytearray]]:
    if type(assets) is not tuple or len(assets) > MAX_PREPARED_MEDIA_ASSETS:
        _invalid_request()
    snapshots: list[tuple[str, str, str, str, bytearray]] = []
    identities: set[int] = set()
    filenames: set[str] = set()
    total_bytes = 0
    try:
        for asset in assets:
            snapshot = _validated_asset_snapshot(asset)
            snapshots.append(snapshot)
            identity, filename = id(asset), snapshot[1]
            if identity in identities or filename in filenames:
                _invalid_request()
            identities.add(identity)
            filenames.add(filename)
            total_bytes += len(snapshot[4])
            if total_bytes > MAX_PREPARED_MEDIA_BYTES:
                _invalid_request()
        return snapshots
    except Exception:
        _wipe_raw_snapshots(snapshots)
        raise


def _validated_asset_snapshot(
    asset: object,
) -> tuple[str, str, str, str, bytearray]:
    if type(asset) is not PreparedMediaAsset:
        _invalid_request()
    data = bytearray()
    try:
        if any(type(value) is not str for value in (
            asset.source_id,
            asset.provider_filename,
            asset.mime_type,
            asset.kind,
            asset.detail,
        )):
            _invalid_request()
        asset.__post_init__()
        if type(asset.buffer) is not bytearray:
            _invalid_request()
        data = bytearray(asset.buffer)
        if not data or len(data) > MAX_SANITIZED_ASSET_BYTES:
            _invalid_request()
        return (
            asset.source_id, asset.provider_filename,
            asset.mime_type, asset.kind, data,
        )
    except LlmClientError:
        _wipe_raw_buffer(data)
        raise
    except Exception:
        _wipe_raw_buffer(data)
        _invalid_request()


def _media_content(
    filename: str, mime_type: str, kind: str, data: bytearray,
) -> dict[str, object]:
    encoded = base64.b64encode(data).decode("ascii")
    if kind == "image":
        return {
            "type": "input_image",
            "image_url": f"data:{mime_type};base64,{encoded}",
            "detail": "high",
        }
    return {
        "type": "input_file",
        "filename": filename,
        "file_data": f"data:{mime_type};base64,{encoded}",
        "detail": "high",
    }


def _wipe_raw_snapshots(
    snapshots: list[tuple[str, str, str, str, bytearray]],
) -> None:
    for _source_id, _filename, _mime_type, _kind, data in snapshots:
        try:
            _wipe_raw_buffer(data)
        except Exception:
            continue


def _wipe_raw_buffer(data: bytearray) -> None:
    data[:] = bytearray(len(data))
    data.clear()


def _invalid_request() -> None:
    raise LlmClientError(
        "OpenAI analysis request is invalid.", reason_code="invalid_request"
    ) from None


def _validated_output(response: object) -> str:
    try:
        status = getattr(response, "status", None)
        output_text = getattr(response, "output_text", None)
    except Exception:
        status = None
        output_text = None
    if status != "completed":
        raise LlmClientError(
            "OpenAI analysis response was incomplete.",
            reason_code="response_incomplete",
        ) from None
    if type(output_text) is not str or not output_text.strip():
        raise LlmClientError(
            "OpenAI analysis response was empty.", reason_code="response_empty"
        ) from None
    text = output_text.strip()
    try:
        validate_private_provider_output(text)
    except PrivateAnalysisRouteError as exc:
        raise LlmClientError(
            "OpenAI analysis response was rejected.", reason_code=exc.code,
            fallback_blocked=exc.code != "provider_output_invalid",
        ) from None
    except Exception:
        raise LlmClientError(
            "OpenAI analysis response was rejected.",
            reason_code="provider_output_invalid",
        ) from None
    return text
