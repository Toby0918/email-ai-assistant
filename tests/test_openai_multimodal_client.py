"""Offline contract tests for the OpenAI Responses multimodal client."""

from __future__ import annotations

import asyncio
import base64
import os
import unittest
from dataclasses import fields
from types import SimpleNamespace
from unittest.mock import patch

from backend.email_agent import model_request as model_request_module
from backend.email_agent.legacy_model_analysis import build_analysis_prompt
from backend.email_agent.llm_errors import LlmClientError
from backend.email_agent.model_request import ModelAnalysisRequest
from backend.email_agent.multimodal_media import (
    MAX_PREPARED_MEDIA_ASSETS,
    MAX_SANITIZED_ASSET_BYTES,
    PreparedMediaAsset,
)
from backend.email_agent.openai_multimodal_client import (
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    generate_openai_multimodal_analysis,
)


class _ForbiddenFilesApi:
    def __getattr__(self, name: str) -> object:
        raise AssertionError(f"Files API must not be accessed: {name}")


class _FakeResponses:
    def __init__(self, response: object = None, error: BaseException | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    async def create(self, **kwargs: object) -> object:
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class _FakeAsyncClient:
    def __init__(self, responses: _FakeResponses) -> None:
        self.responses = responses
        self.files = _ForbiddenFilesApi()

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(
        self, exc_type: object, exc: object, traceback: object
    ) -> None:
        return None


class _ClientFactory:
    def __init__(
        self,
        response: object = None,
        error: BaseException | None = None,
        on_construct: object = None,
    ) -> None:
        self.responses = _FakeResponses(response, error)
        self.constructor_calls: list[dict[str, object]] = []
        self.on_construct = on_construct

    def __call__(self, **kwargs: object) -> _FakeAsyncClient:
        self.constructor_calls.append(kwargs)
        if callable(self.on_construct):
            self.on_construct()
        return _FakeAsyncClient(self.responses)


def _asset(
    *, source_id: str, provider_filename: str, mime_type: str, kind: str, data: bytes
) -> PreparedMediaAsset:
    return PreparedMediaAsset(
        source_id=source_id,
        provider_filename=provider_filename,
        mime_type=mime_type,
        kind=kind,
        detail="high",
        buffer=bytearray(data),
    )


def _completed(output_text: object = '{"summary":"synthetic"}') -> object:
    return SimpleNamespace(status="completed", output_text=output_text)


class OpenAIMultimodalClientTests(unittest.TestCase):
    def _assert_invalid_before_client(self, request: ModelAnalysisRequest) -> None:
        factory = _ClientFactory(_completed())
        with self.assertRaises(LlmClientError) as caught:
            asyncio.run(
                generate_openai_multimodal_analysis(
                    request,
                    api_key="synthetic-openai-key",
                    model=OPENAI_MODEL,
                    timeout_seconds=35,
                    client_factory=factory,
                )
            )
        self.assertEqual(caught.exception.reason_code, "invalid_request")
        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(factory.constructor_calls, [])

    def test_model_request_rejects_blank_text(self) -> None:
        for text in ("", " \r\n\t"):
            with self.subTest(text=repr(text)):
                with self.assertRaises(ValueError):
                    ModelAnalysisRequest(text, ())

    def test_model_request_text_has_fixed_inclusive_512_kib_cap(self) -> None:
        cap = 512 * 1024
        self.assertEqual(
            getattr(model_request_module, "MAX_MODEL_REQUEST_TEXT_CHARACTERS", None),
            cap,
        )
        self.assertEqual(len(ModelAnalysisRequest("x" * cap, ()).text), cap)
        with self.assertRaises(ValueError):
            ModelAnalysisRequest("x" * (cap + 1), ())

    def test_text_cap_exceeds_the_bounded_legitimate_prompt_worst_case(self) -> None:
        value = "x" * 20_000
        prompt = build_analysis_prompt(
            value, value, value,
            attachments=[{"filename": value, "type": value, "size": value}] * 8,
            recipients=[value] * 8, cc=[value] * 8, sent_at=value,
            conversation_timeline={
                **{key: value for key in (
                    "previous_context", "current_status", "status_reason",
                    "latest_external_request", "latest_internal_commitment", "confidence",
                )},
                "open_items": [{key: value for key in (
                    "item", "owner_hint", "due_hint", "source",
                )}] * 8,
            },
            attachment_insights=[{
                "filename": value, "type": value, "status": "parsed",
                "summary": value, "key_facts": [value] * 8,
                "limitations": [value] * 8,
            }] * 14,
        )
        cap = getattr(model_request_module, "MAX_MODEL_REQUEST_TEXT_CHARACTERS", 0)
        self.assertGreater(cap, len(prompt) + 4_000)

    def test_dispatch_rejects_direct_private_text_before_client_construction(self) -> None:
        probes = (
            "contact buyer@example.test",
            "open https://private.example.test/order",
            "order PO-123456",
            "sender <EMAIL_1>",
            "sender <email_1>",
        )
        for text in probes:
            with self.subTest(probe=text.split(" ", 1)[0]):
                request = ModelAnalysisRequest(text, ())
                self._assert_invalid_before_client(request)

    def test_dispatch_revalidates_every_mutable_media_boundary(self) -> None:
        def media(index: int, size: int = 1) -> PreparedMediaAsset:
            return _asset(
                source_id=f"attachment:{index}",
                provider_filename=f"image_{index}.png",
                mime_type="image/png", kind="image", data=b"x" * size,
            )

        invalid_asset_sets: list[tuple[PreparedMediaAsset, ...]] = []
        invalid_asset_sets.append(tuple(media(index) for index in range(MAX_PREPARED_MEDIA_ASSETS + 1)))
        invalid_asset_sets.append(tuple(media(index, 7 * 1024 * 1024) for index in range(3)))
        wiped = media(20)
        wiped.wipe()
        invalid_asset_sets.append((wiped,))
        wrong_buffer = media(21)
        object.__setattr__(wrong_buffer, "buffer", b"not-bytearray")
        invalid_asset_sets.append((wrong_buffer,))
        oversized = media(22)
        oversized.buffer.extend(b"x" * MAX_SANITIZED_ASSET_BYTES)
        invalid_asset_sets.append((oversized,))
        duplicate_object = media(23)
        invalid_asset_sets.append((duplicate_object, duplicate_object))
        invalid_asset_sets.append((media(24), _asset(
            source_id="attachment:25", provider_filename="image_24.png",
            mime_type="image/png", kind="image", data=b"y",
        )))

        class DerivedPreparedMediaAsset(PreparedMediaAsset):
            pass

        derived = DerivedPreparedMediaAsset(
            source_id="attachment:26", provider_filename="image_26.png",
            mime_type="image/png", kind="image", detail="high", buffer=bytearray(b"x"),
        )
        invalid_asset_sets.append((derived,))
        for index, assets in enumerate(invalid_asset_sets):
            with self.subTest(case=index):
                request = ModelAnalysisRequest("safe lower-case text", ())
                object.__setattr__(request, "media_assets", assets)
                self._assert_invalid_before_client(request)

    def test_dispatch_rejects_str_subclasses_for_every_media_metadata_field(self) -> None:
        class FormatCanary(str):
            def __format__(self, format_spec: str) -> str:
                return "PRIVATE_RAW_CANARY"

        class StringCanary(str):
            def __str__(self) -> str:
                return "PRIVATE_RAW_CANARY"

        class EqualityCanary(str):
            __hash__ = str.__hash__

            def __eq__(self, other: object) -> bool:
                return str.__eq__(self, other)

        values = {
            "source_id": "attachment:0",
            "provider_filename": "image_0.png",
            "mime_type": "image/png",
            "kind": "image",
            "detail": "high",
        }
        canaries = (FormatCanary, StringCanary, EqualityCanary)
        for field_name, raw_value in values.items():
            for canary_type in canaries:
                with self.subTest(field=field_name, hook=canary_type.__name__):
                    metadata = dict(values)
                    metadata[field_name] = canary_type(raw_value)
                    asset = PreparedMediaAsset(
                        **metadata, buffer=bytearray(b"synthetic-image"),
                    )
                    self.assertIs(type(asset), PreparedMediaAsset)
                    request = ModelAnalysisRequest("safe lower-case text", (asset,))
                    self._assert_invalid_before_client(request)

    def test_dispatch_maps_every_deleted_media_slot_to_fixed_invalid_request(self) -> None:
        slots = (
            "source_id", "provider_filename", "mime_type",
            "kind", "detail", "buffer",
        )
        for slot_name in slots:
            with self.subTest(slot=slot_name):
                asset = _asset(
                    source_id="attachment:0", provider_filename="image_0.png",
                    mime_type="image/png", kind="image", data=b"synthetic-image",
                )
                object.__delattr__(asset, slot_name)
                self.assertIs(type(asset), PreparedMediaAsset)
                factory = _ClientFactory(_completed())
                with self.assertRaises(LlmClientError) as caught:
                    asyncio.run(generate_openai_multimodal_analysis(
                        ModelAnalysisRequest("safe lower-case text", (asset,)),
                        api_key="synthetic-openai-key", model=OPENAI_MODEL,
                        timeout_seconds=35, client_factory=factory,
                    ))
                self.assertEqual(caught.exception.reason_code, "invalid_request")
                self.assertNotIn(slot_name, str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)
                self.assertEqual(factory.constructor_calls, [])

    def test_repeated_source_id_is_allowed_for_unique_assets(self) -> None:
        assets = (
            _asset(source_id="attachment:7", provider_filename="image_0.png",
                   mime_type="image/png", kind="image", data=b"first"),
            _asset(source_id="attachment:7", provider_filename="image_1.png",
                   mime_type="image/png", kind="image", data=b"second"),
        )
        factory = _ClientFactory(_completed())
        asyncio.run(generate_openai_multimodal_analysis(
            ModelAnalysisRequest("safe lower-case text", assets),
            api_key="synthetic-openai-key", model=OPENAI_MODEL,
            timeout_seconds=35, client_factory=factory,
        ))
        markers = [item.get("text") for item in factory.responses.calls[0]["input"][0]["content"]]
        self.assertEqual(markers.count("UNTRUSTED_BINARY_SOURCE attachment:7"), 2)

    def test_binary_snapshot_precedes_client_construction_and_later_mutation(self) -> None:
        original = b"snapshot-source"
        for mutation in ("wipe", "oversize"):
            with self.subTest(mutation=mutation):
                asset = _asset(
                    source_id="attachment:0", provider_filename="image_0.png",
                    mime_type="image/png", kind="image", data=original,
                )
                def mutate() -> None:
                    if mutation == "wipe":
                        asset.wipe()
                    else:
                        asset.buffer.extend(b"x" * MAX_SANITIZED_ASSET_BYTES)
                factory = _ClientFactory(_completed(), on_construct=mutate)
                asyncio.run(generate_openai_multimodal_analysis(
                    ModelAnalysisRequest("safe lower-case text", (asset,)),
                    api_key="synthetic-openai-key", model=OPENAI_MODEL,
                    timeout_seconds=35, client_factory=factory,
                ))
                content = factory.responses.calls[0]["input"][0]["content"]
                self.assertEqual(
                    content[2]["image_url"],
                    "data:image/png;base64," + base64.b64encode(original).decode("ascii"),
                )

    def test_unsupported_ambient_sdk_configuration_fails_closed(self) -> None:
        names = (
            "OPENAI_ORG_ID", "OPENAI_PROJECT_ID",
            "OPENAI_CUSTOM_HEADERS", "OPENAI_ADMIN_KEY",
        )
        cleared = {name: "" for name in names}
        for name in names:
            with self.subTest(name=name), patch.dict(
                os.environ, {**cleared, name: "PRIVATE_AMBIENT_CANARY"}, clear=False,
            ):
                request = ModelAnalysisRequest("safe lower-case text", ())
                self._assert_invalid_before_client(request)

    def test_api_key_must_be_an_exact_nonblank_string(self) -> None:
        class DerivedKey(str):
            pass

        for api_key in (" \r\n", b"synthetic-key", 1, DerivedKey("synthetic-key")):
            with self.subTest(kind=type(api_key).__name__):
                factory = _ClientFactory(_completed())
                with self.assertRaises(LlmClientError) as caught:
                    asyncio.run(generate_openai_multimodal_analysis(
                        ModelAnalysisRequest("safe lower-case text", ()),
                        api_key=api_key,  # type: ignore[arg-type]
                        model=OPENAI_MODEL, timeout_seconds=35,
                        client_factory=factory,
                    ))
                self.assertEqual(caught.exception.reason_code, "missing_key")
                self.assertEqual(factory.constructor_calls, [])

    def test_temporary_raw_snapshot_is_mutable_and_wiped_after_encoding(self) -> None:
        asset = _asset(
            source_id="attachment:0", provider_filename="image_0.png",
            mime_type="image/png", kind="image", data=b"synthetic-raw",
        )
        captured: list[object] = []
        real_b64encode = base64.b64encode

        def capture(value: object) -> bytes:
            captured.append(value)
            return real_b64encode(value)  # type: ignore[arg-type]

        factory = _ClientFactory(_completed())
        with patch(
            "backend.email_agent.openai_multimodal_client.base64.b64encode",
            side_effect=capture,
        ):
            asyncio.run(generate_openai_multimodal_analysis(
                ModelAnalysisRequest("safe lower-case text", (asset,)),
                api_key="synthetic-openai-key", model=OPENAI_MODEL,
                timeout_seconds=35, client_factory=factory,
            ))

        self.assertEqual(len(captured), 1)
        self.assertIs(type(captured[0]), bytearray)
        self.assertEqual(captured[0], bytearray())
        self.assertEqual(asset.buffer, bytearray(b"synthetic-raw"))

    def test_snapshot_encoding_failure_is_fixed_and_wipes_temporary_raw_bytes(self) -> None:
        asset = _asset(
            source_id="attachment:0", provider_filename="image_0.png",
            mime_type="image/png", kind="image", data=b"synthetic-raw",
        )
        captured: list[object] = []

        def fail(value: object) -> bytes:
            captured.append(value)
            raise RuntimeError("PRIVATE_ENCODING_DETAIL")

        factory = _ClientFactory(_completed())
        with patch(
            "backend.email_agent.openai_multimodal_client.base64.b64encode",
            side_effect=fail,
        ), self.assertRaises(LlmClientError) as caught:
            asyncio.run(generate_openai_multimodal_analysis(
                ModelAnalysisRequest("safe lower-case text", (asset,)),
                api_key="synthetic-openai-key", model=OPENAI_MODEL,
                timeout_seconds=35, client_factory=factory,
            ))

        self.assertEqual(caught.exception.reason_code, "invalid_request")
        self.assertNotIn("PRIVATE_ENCODING_DETAIL", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)
        self.assertEqual(factory.constructor_calls, [])
        self.assertEqual(captured, [bytearray()])

    def test_one_responses_request_has_exact_bounded_shape_and_adjacent_sources(self) -> None:
        image = _asset(
            source_id="attachment:0",
            provider_filename="image_0.png",
            mime_type="image/png",
            kind="image",
            data=b"synthetic-png",
        )
        pdf = _asset(
            source_id="attachment:1",
            provider_filename="attachment_1.pdf",
            mime_type="application/pdf",
            kind="file",
            data=b"%PDF-synthetic",
        )
        request = ModelAnalysisRequest("DEIDENTIFIED_TEXT", (image, pdf))
        factory = _ClientFactory(_completed())

        result = asyncio.run(
            generate_openai_multimodal_analysis(
                request,
                api_key="synthetic-openai-key",
                model=OPENAI_MODEL,
                timeout_seconds=19,
                client_factory=factory,
            )
        )

        self.assertEqual(result, '{"summary":"synthetic"}')
        self.assertEqual(
            factory.constructor_calls,
            [{
                "api_key": "synthetic-openai-key",
                "base_url": "https://api.openai.com/v1",
                "max_retries": 0,
                "timeout": 19.0,
            }],
        )
        self.assertEqual(OPENAI_BASE_URL, "https://api.openai.com/v1")
        self.assertEqual(len(factory.responses.calls), 1)
        payload = factory.responses.calls[0]
        self.assertEqual(payload["model"], "gpt-5.6-sol")
        self.assertIs(payload["store"], False)
        self.assertIs(payload["stream"], False)
        self.assertEqual(payload["tools"], [])
        self.assertEqual(payload["max_output_tokens"], 2400)
        self.assertEqual(payload["text"], {"verbosity": "low"})
        self.assertNotIn("format", payload["text"])
        self.assertEqual(payload["reasoning"], {"effort": "low"})
        self.assertIsInstance(payload["instructions"], str)
        messages = payload["input"]
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["role"], "user")
        content = messages[0]["content"]
        self.assertEqual(content[0], {"type": "input_text", "text": "DEIDENTIFIED_TEXT"})
        self.assertEqual(
            content[1],
            {"type": "input_text", "text": "UNTRUSTED_BINARY_SOURCE attachment:0"},
        )
        self.assertEqual(content[2]["type"], "input_image")
        self.assertEqual(content[2]["detail"], "high")
        self.assertEqual(
            content[2]["image_url"],
            "data:image/png;base64," + base64.b64encode(b"synthetic-png").decode("ascii"),
        )
        self.assertEqual(
            content[3],
            {"type": "input_text", "text": "UNTRUSTED_BINARY_SOURCE attachment:1"},
        )
        self.assertEqual(
            content[4],
            {
                "type": "input_file",
                "filename": "attachment_1.pdf",
                "file_data": "data:application/pdf;base64,"
                + base64.b64encode(b"%PDF-synthetic").decode("ascii"),
                "detail": "high",
            },
        )

    def test_environment_cannot_redirect_the_fixed_official_endpoint(self) -> None:
        factory = _ClientFactory(_completed())

        with patch.dict(
            os.environ,
            {"OPENAI_BASE_URL": "https://redirect.example.test/v1"},
            clear=False,
        ), patch(
            "backend.email_agent.openai_multimodal_client.AsyncOpenAI",
            new=factory,
        ):
            asyncio.run(
                generate_openai_multimodal_analysis(
                    ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()),
                    api_key="synthetic-openai-key",
                    model=OPENAI_MODEL,
                    timeout_seconds=35,
                )
            )

        self.assertEqual(
            factory.constructor_calls[0]["base_url"],
            "https://api.openai.com/v1",
        )

    def test_provider_neutral_request_has_only_text_and_prepared_media_fields(self) -> None:
        request = ModelAnalysisRequest("PRIVATE_TEXT_CANARY", ())

        self.assertEqual([item.name for item in fields(request)], ["text", "media_assets"])
        self.assertFalse(hasattr(request, "__dict__"))
        self.assertNotIn("PRIVATE_TEXT_CANARY", repr(request))

    def test_request_payload_never_uses_original_name_path_or_private_url(self) -> None:
        request = ModelAnalysisRequest(
            "DEIDENTIFIED_TEXT",
            (
                _asset(
                    source_id="attachment:7",
                    provider_filename="attachment_0.pdf",
                    mime_type="application/pdf",
                    kind="file",
                    data=b"%PDF-private-canary-free",
                ),
            ),
        )
        factory = _ClientFactory(_completed())

        asyncio.run(
            generate_openai_multimodal_analysis(
                request,
                api_key="synthetic-openai-key",
                model=OPENAI_MODEL,
                timeout_seconds=35,
                client_factory=factory,
            )
        )

        serialized = repr(factory.responses.calls)
        for forbidden in (
            "customer-original.pdf",
            r"C:\\private\\customer-original.pdf",
            "https://private.example.test/download",
            "file_id",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_timeout_is_absolute_and_capped_at_35_seconds(self) -> None:
        capped_factory = _ClientFactory(_completed())
        asyncio.run(
            generate_openai_multimodal_analysis(
                ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()),
                api_key="synthetic-openai-key",
                model=OPENAI_MODEL,
                timeout_seconds=999,
                client_factory=capped_factory,
            )
        )
        self.assertEqual(capped_factory.constructor_calls[0]["timeout"], 35.0)

        async def never_finishes(**kwargs: object) -> object:
            await asyncio.Future()
            return object()

        factory = _ClientFactory(_completed())
        factory.responses.create = never_finishes  # type: ignore[method-assign]
        request = ModelAnalysisRequest("DEIDENTIFIED_TEXT", ())

        with self.assertRaises(LlmClientError) as caught:
            asyncio.run(
                generate_openai_multimodal_analysis(
                    request,
                    api_key="synthetic-openai-key",
                    model=OPENAI_MODEL,
                    timeout_seconds=0.01,
                    client_factory=factory,
                )
            )

        self.assertEqual(caught.exception.reason_code, "provider_timeout")
        self.assertIsNone(caught.exception.__cause__)

    def test_missing_key_and_invalid_request_fail_before_client_construction(self) -> None:
        cases = (
            (ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()), None, "missing_key"),
            ("RAW_TEXT_IS_NOT_A_MODEL_REQUEST", "synthetic-openai-key", "invalid_request"),
        )
        for request, api_key, expected in cases:
            with self.subTest(expected=expected):
                factory = _ClientFactory(_completed())
                with self.assertRaises(LlmClientError) as caught:
                    asyncio.run(
                        generate_openai_multimodal_analysis(
                            request,  # type: ignore[arg-type]
                            api_key=api_key,
                            model=OPENAI_MODEL,
                            timeout_seconds=35,
                            client_factory=factory,
                        )
                    )
                self.assertEqual(caught.exception.reason_code, expected)
                self.assertEqual(factory.constructor_calls, [])

    def test_rejects_nonallowlisted_model_before_client_construction(self) -> None:
        factory = _ClientFactory(_completed())
        with self.assertRaises(LlmClientError) as caught:
            asyncio.run(
                generate_openai_multimodal_analysis(
                    ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()),
                    api_key="synthetic-openai-key",
                    model="gpt-5.6-sol-preview",
                    timeout_seconds=35,
                    client_factory=factory,
                )
            )

        self.assertEqual(caught.exception.reason_code, "unsupported_model")
        self.assertEqual(factory.constructor_calls, [])

    def test_maps_provider_incomplete_empty_and_private_output_to_fixed_codes(self) -> None:
        cases = (
            (SimpleNamespace(status="in_progress", output_text="{}"), None, "response_incomplete"),
            (_completed("   "), None, "response_empty"),
            (_completed('{"summary":"<email_1>"}'), None, "provider_output_placeholder_echo"),
            (_completed('{"private_context":"forbidden"}'), None, "safety_rejected_all"),
            (_completed("not-json"), None, "provider_output_invalid"),
            (None, RuntimeError("PRIVATE_EXCEPTION PRIVATE_URL SECRET_PROMPT"), "provider_request_failed"),
        )

        for response, error, expected in cases:
            with self.subTest(expected=expected):
                factory = _ClientFactory(response, error)
                with self.assertRaises(LlmClientError) as caught:
                    asyncio.run(
                        generate_openai_multimodal_analysis(
                            ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()),
                            api_key="synthetic-openai-key",
                            model=OPENAI_MODEL,
                            timeout_seconds=35,
                            client_factory=factory,
                        )
                    )
                self.assertEqual(caught.exception.reason_code, expected)
                self.assertNotIn("PRIVATE", str(caught.exception))
                self.assertNotIn("SECRET_PROMPT", str(caught.exception))
                self.assertIsNone(caught.exception.__cause__)

    def test_unexpected_private_output_gate_failure_is_fixed_and_content_free(self) -> None:
        factory = _ClientFactory(_completed())

        with patch(
            "backend.email_agent.openai_multimodal_client.validate_private_provider_output",
            side_effect=RuntimeError("PRIVATE_OUTPUT_GATE_DETAIL"),
        ):
            with self.assertRaises(LlmClientError) as caught:
                asyncio.run(
                    generate_openai_multimodal_analysis(
                        ModelAnalysisRequest("DEIDENTIFIED_TEXT", ()),
                        api_key="synthetic-openai-key",
                        model=OPENAI_MODEL,
                        timeout_seconds=35,
                        client_factory=factory,
                    )
                )

        self.assertEqual(caught.exception.reason_code, "provider_output_invalid")
        self.assertNotIn("PRIVATE_OUTPUT_GATE_DETAIL", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)


if __name__ == "__main__":
    unittest.main()
