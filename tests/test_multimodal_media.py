"""Security tests for request-local image and PDF media preparation."""

from __future__ import annotations

import io
import unittest
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image, PngImagePlugin
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
    TextStringObject,
)

from backend.email_agent.multimodal_media import (
    MAX_IMAGE_DIMENSION,
    MAX_IMAGE_FRAMES,
    MAX_IMAGE_PIXELS,
    MAX_PDF_PAGES,
    MediaPreparationError,
    PreparedMediaAsset,
    prepare_attachment_media,
    sanitize_image_bytes,
    sanitize_pdf_bytes,
    wipe_prepared_media,
)
from backend.email_agent.attachment_storage import StoredAttachment


def _image_bytes(
    image_format: str,
    *,
    size: tuple[int, int] = (8, 6),
    exif: Image.Exif | None = None,
) -> bytes:
    output = io.BytesIO()
    image = Image.new("RGB", size, (42, 84, 126))
    image.save(output, format=image_format, exif=exif)
    return output.getvalue()


def _animated_gif(frame_count: int = 2) -> bytes:
    output = io.BytesIO()
    frames = [
        Image.new("RGB", (6, 4), (index % 255, (index * 2) % 255, (index * 3) % 255))
        for index in range(frame_count)
    ]
    frames[0].save(
        output, format="GIF", save_all=True, append_images=frames[1:], duration=20, loop=0
    )
    return output.getvalue()


def _pdf_bytes(*, pages: int = 1, encrypted: bool = False, active: bool = False) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=100, height=100)
        if active:
            page[NameObject("/Annots")] = ArrayObject([DictionaryObject()])
            page[NameObject("/AA")] = DictionaryObject({
                NameObject("/O"): DictionaryObject({NameObject("/S"): NameObject("/JavaScript")})
            })
            page[NameObject("/A")] = DictionaryObject({NameObject("/S"): NameObject("/JavaScript")})
            page[NameObject("/Metadata")] = TextStringObject("SYNTHETIC_PAGE_METADATA")
    if active:
        writer.add_metadata({"/Title": "SYNTHETIC_PRIVATE_TITLE"})
        writer.add_js("SYNTHETIC_REAL_JAVASCRIPT")
        writer.add_attachment("synthetic-private.txt", b"SYNTHETIC_EMBEDDED_FILE")
        writer._root_object[NameObject("/OpenAction")] = DictionaryObject({
            NameObject("/S"): NameObject("/JavaScript"),
            NameObject("/JS"): TextStringObject("SYNTHETIC_SCRIPT"),
        })
        writer._root_object[NameObject("/AA")] = DictionaryObject()
        writer._root_object[NameObject("/AcroForm")] = DictionaryObject({
            NameObject("/Fields"): ArrayObject()
        })
    if encrypted:
        writer.encrypt("synthetic-password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _pdf_with_page_active_orphans() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=100, height=100)
    script = DictionaryObject({
        NameObject("/S"): NameObject("/JavaScript"),
        NameObject("/JS"): TextStringObject("SYNTHETIC_PAGE_ORPHAN_SCRIPT"),
    })
    script_ref = writer._add_object(script)
    embedded = DecodedStreamObject()
    embedded.set_data(b"SYNTHETIC_PAGE_ORPHAN_FILE")
    embedded[NameObject("/Type")] = NameObject("/EmbeddedFile")
    embedded_ref = writer._add_object(embedded)
    filespec = DictionaryObject({
        NameObject("/Type"): NameObject("/Filespec"),
        NameObject("/F"): TextStringObject("synthetic-private.txt"),
        NameObject("/EF"): DictionaryObject({NameObject("/F"): embedded_ref}),
    })
    filespec_ref = writer._add_object(filespec)
    page[NameObject("/OpenAction")] = script_ref
    page[NameObject("/Names")] = DictionaryObject({
        NameObject("/JavaScript"): DictionaryObject({
            NameObject("/Names"): ArrayObject([
                TextStringObject("synthetic-script"), script_ref,
            ])
        }),
        NameObject("/EmbeddedFiles"): DictionaryObject({
            NameObject("/Names"): ArrayObject([
                TextStringObject("synthetic-private.txt"), filespec_ref,
            ])
        }),
    })
    writer._root_object[NameObject("/OpenAction")] = script_ref
    writer._root_object[NameObject("/Names")] = page[NameObject("/Names")]
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


class PreparedMediaAssetTests(unittest.TestCase):
    def test_asset_is_frozen_repr_hidden_mutable_and_explicitly_wipeable(self) -> None:
        secret = bytearray(b"SYNTHETIC_MEDIA_SECRET")
        asset = PreparedMediaAsset(
            source_id="attachment:0",
            provider_filename="image_0.png",
            mime_type="image/png",
            kind="image",
            detail="high",
            buffer=secret,
        )

        with self.assertRaises(FrozenInstanceError):
            asset.source_id = "attachment:9"  # type: ignore[misc]
        rendered = repr(asset)
        for private in ("attachment:0", "image_0.png", "SYNTHETIC_MEDIA_SECRET"):
            self.assertNotIn(private, rendered)
        self.assertIs(asset.buffer, secret)

        wipe_prepared_media((asset,))

        self.assertEqual(secret, bytearray())

    def test_asset_rejects_non_mutable_binary_buffer_without_echoing_it(self) -> None:
        with self.assertRaises(ValueError) as raised:
            PreparedMediaAsset(
                source_id="attachment:0",
                provider_filename="image_0.png",
                mime_type="image/png",
                kind="image",
                detail="high",
                buffer=b"PRIVATE_IMMUTABLE_BYTES",  # type: ignore[arg-type]
            )

        self.assertNotIn("PRIVATE_IMMUTABLE_BYTES", str(raised.exception))

    def test_asset_rejects_crossed_contract_and_non_opaque_identifiers(self) -> None:
        invalid = (
            {"provider_filename": "image_0.png", "mime_type": "application/pdf", "kind": "file"},
            {"provider_filename": "customer-name.png", "mime_type": "image/png", "kind": "image"},
            {"provider_filename": "image_0.png", "mime_type": "image/png", "kind": "file"},
        )
        for contract in invalid:
            with self.subTest(contract=contract), self.assertRaises(ValueError):
                PreparedMediaAsset(
                    source_id="attachment:0",
                    detail="high",
                    buffer=bytearray(b"safe"),
                    **contract,
                )


class ImageSanitizationTests(unittest.TestCase):
    def test_rejects_declared_mime_and_magic_mismatch(self) -> None:
        with self.assertRaises(MediaPreparationError):
            sanitize_image_bytes(
                _image_bytes("PNG"),
                declared_mime="image/jpeg",
                source_id="attachment:0",
                asset_index=0,
            )

    def test_rejects_malformed_image_without_echoing_bytes_or_source(self) -> None:
        with self.assertRaises(MediaPreparationError) as raised:
            sanitize_image_bytes(
                b"SYNTHETIC_MALFORMED_IMAGE",
                declared_mime="image/png",
                source_id="attachment:77",
                asset_index=0,
            )

        rendered = str(raised.exception)
        self.assertNotIn("SYNTHETIC_MALFORMED_IMAGE", rendered)
        self.assertNotIn("attachment:77", rendered)

    def test_rejects_pillow_decompression_bomb(self) -> None:
        content = _image_bytes("PNG", size=(3, 3))

        with patch.object(Image, "MAX_IMAGE_PIXELS", 4), self.assertRaises(MediaPreparationError):
            sanitize_image_bytes(
                content,
                declared_mime="image/png",
                source_id="attachment:0",
                asset_index=0,
            )

    def test_rejects_pillow_decompression_bomb_warning_with_fixed_error(self) -> None:
        content = _image_bytes("PNG", size=(3, 2))

        with patch.object(Image, "MAX_IMAGE_PIXELS", 4), self.assertRaises(
            MediaPreparationError
        ) as raised:
            sanitize_image_bytes(
                content,
                declared_mime="image/png",
                source_id="attachment:0",
                asset_index=0,
            )

        self.assertEqual(str(raised.exception), "Media could not be prepared safely.")

    def test_rejects_animation_above_frame_limit(self) -> None:
        with self.assertRaises(MediaPreparationError):
            sanitize_image_bytes(
                _animated_gif(MAX_IMAGE_FRAMES + 1),
                declared_mime="image/gif",
                source_id="attachment:0",
                asset_index=0,
            )

    def test_rejects_pixel_and_dimension_bombs_before_decode(self) -> None:
        content = _image_bytes("PNG", size=(10, 10))

        with patch(
            "backend.email_agent.multimodal_media.MAX_IMAGE_PIXELS", 99
        ), self.assertRaises(MediaPreparationError):
            sanitize_image_bytes(
                content, declared_mime="image/png", source_id="attachment:0", asset_index=0
            )
        with patch(
            "backend.email_agent.multimodal_media.MAX_SOURCE_IMAGE_DIMENSION", 9
        ), self.assertRaises(MediaPreparationError):
            sanitize_image_bytes(
                content, declared_mime="image/png", source_id="attachment:0", asset_index=0
            )

    def test_flattens_animation_and_uses_opaque_fixed_output(self) -> None:
        asset = sanitize_image_bytes(
            _animated_gif(),
            declared_mime="image/gif",
            source_id="attachment:2",
            asset_index=3,
        )

        self.assertEqual(asset.source_id, "attachment:2")
        self.assertEqual(asset.provider_filename, "image_3.png")
        self.assertEqual((asset.mime_type, asset.kind, asset.detail), ("image/png", "image", "high"))
        with Image.open(io.BytesIO(asset.buffer)) as prepared:
            self.assertEqual(prepared.format, "PNG")
            self.assertEqual(getattr(prepared, "n_frames", 1), 1)

    def test_applies_exif_orientation_and_removes_metadata(self) -> None:
        exif = Image.Exif()
        exif[274] = 6
        exif[270] = "SYNTHETIC_PRIVATE_DESCRIPTION"
        content = _image_bytes("JPEG", size=(4, 7), exif=exif)

        asset = sanitize_image_bytes(
            content,
            declared_mime="image/jpeg",
            source_id="attachment:0",
            asset_index=0,
        )

        with Image.open(io.BytesIO(asset.buffer)) as prepared:
            self.assertEqual(prepared.size, (7, 4))
            self.assertEqual(dict(prepared.getexif()), {})
            serialized_info = str(prepared.info)
            self.assertNotIn("SYNTHETIC_PRIVATE_DESCRIPTION", serialized_info)
            self.assertNotIn("exif", prepared.info)

    def test_removes_png_text_icc_and_xmp_metadata(self) -> None:
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("Description", "SYNTHETIC_PRIVATE_PNG_TEXT")
        metadata.add_text("XML:com.adobe.xmp", "SYNTHETIC_PRIVATE_XMP")
        output = io.BytesIO()
        Image.new("RGB", (4, 4), (1, 2, 3)).save(
            output,
            format="PNG",
            pnginfo=metadata,
            icc_profile=b"SYNTHETIC_PRIVATE_ICC",
        )

        asset = sanitize_image_bytes(
            output.getvalue(),
            declared_mime="image/png",
            source_id="attachment:0",
            asset_index=0,
        )

        with Image.open(io.BytesIO(asset.buffer)) as prepared:
            serialized = str(prepared.info)
            for marker in ("SYNTHETIC_PRIVATE_PNG_TEXT", "SYNTHETIC_PRIVATE_XMP", "SYNTHETIC_PRIVATE_ICC"):
                self.assertNotIn(marker, serialized)
            self.assertNotIn("icc_profile", prepared.info)

    def test_rejects_sanitized_image_above_output_byte_limit(self) -> None:
        with patch(
            "backend.email_agent.multimodal_media.MAX_SANITIZED_ASSET_BYTES", 8
        ), self.assertRaises(MediaPreparationError):
            sanitize_image_bytes(
                _image_bytes("PNG"),
                declared_mime="image/png",
                source_id="attachment:0",
                asset_index=0,
            )

    def test_downscales_to_output_dimension_and_pixel_limits(self) -> None:
        content = _image_bytes("PNG", size=(3000, 1500))

        asset = sanitize_image_bytes(
            content,
            declared_mime="image/png",
            source_id="attachment:0",
            asset_index=0,
        )

        with Image.open(io.BytesIO(asset.buffer)) as prepared:
            self.assertLessEqual(max(prepared.size), MAX_IMAGE_DIMENSION)
            self.assertLessEqual(prepared.width * prepared.height, MAX_IMAGE_PIXELS)
            self.assertEqual(prepared.width, prepared.height * 2)


class PdfSanitizationTests(unittest.TestCase):
    def test_rejects_magic_mismatch_and_malformed_pdf(self) -> None:
        for content in (b"NOT_A_PDF", b"%PDF-SYNTHETIC_BROKEN"):
            with self.subTest(content=content[:4]), self.assertRaises(MediaPreparationError):
                sanitize_pdf_bytes(content, source_id="attachment:0", asset_index=0)

    def test_rejects_encrypted_pdf(self) -> None:
        with self.assertRaises(MediaPreparationError):
            sanitize_pdf_bytes(
                _pdf_bytes(encrypted=True), source_id="attachment:0", asset_index=0
            )

    def test_rejects_pdf_above_page_limit(self) -> None:
        with self.assertRaises(MediaPreparationError):
            sanitize_pdf_bytes(
                _pdf_bytes(pages=MAX_PDF_PAGES + 1),
                source_id="attachment:0",
                asset_index=0,
            )

    def test_rewrites_pdf_without_metadata_actions_forms_annotations_or_embedded_files(self) -> None:
        asset = sanitize_pdf_bytes(
            _pdf_bytes(active=True), source_id="attachment:4", asset_index=2
        )

        self.assertEqual(asset.source_id, "attachment:4")
        self.assertEqual(asset.provider_filename, "attachment_2.pdf")
        self.assertEqual((asset.mime_type, asset.kind, asset.detail), ("application/pdf", "file", "high"))
        rendered = bytes(asset.buffer)
        for private in (
            b"SYNTHETIC_PRIVATE_TITLE",
            b"SYNTHETIC_PAGE_METADATA",
            b"SYNTHETIC_SCRIPT",
            b"SYNTHETIC_REAL_JAVASCRIPT",
            b"SYNTHETIC_EMBEDDED_FILE",
            b"/JavaScript",
            b"/OpenAction",
            b"/AcroForm",
            b"/EmbeddedFiles",
        ):
            self.assertNotIn(private, rendered)
        reader = PdfReader(io.BytesIO(rendered), strict=True)
        self.assertFalse(reader.is_encrypted)
        self.assertIsNone(reader.metadata)
        root = reader.trailer["/Root"]
        for key in ("/OpenAction", "/AA", "/AcroForm", "/Names", "/Metadata"):
            self.assertNotIn(key, root)
        for page in reader.pages:
            for key in ("/Annots", "/AA", "/A", "/Metadata"):
                self.assertNotIn(key, page)

    def test_preclone_sanitation_removes_page_active_objects_and_serialized_orphans(self) -> None:
        asset = sanitize_pdf_bytes(
            _pdf_with_page_active_orphans(), source_id="attachment:0", asset_index=0
        )

        rendered = bytes(asset.buffer)
        for marker in (
            b"SYNTHETIC_PAGE_ORPHAN_SCRIPT",
            b"SYNTHETIC_PAGE_ORPHAN_FILE",
            b"synthetic-private.txt",
            b"/JavaScript",
            b"/EmbeddedFile",
            b"/Filespec",
            b"/OpenAction",
            b"/Names",
        ):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, rendered)


class StoredAttachmentMediaTests(unittest.TestCase):
    def test_preparation_keeps_parent_source_index_when_an_earlier_asset_fails(self) -> None:
        with TemporaryDirectory() as directory:
            broken = self._stored(directory, "private-original.png", "image", b"broken")
            valid = self._stored(directory, "customer-original.png", "image", _image_bytes("PNG"))

            assets = prepare_attachment_media([broken, valid])

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].source_id, "attachment:1")
        self.assertEqual(assets[0].provider_filename, "image_0.png")
        rendered = repr(assets[0])
        self.assertNotIn("customer-original", rendered)
        self.assertNotIn(directory, rendered)

    def test_preparation_enforces_request_global_asset_and_byte_limits(self) -> None:
        with TemporaryDirectory() as directory:
            items = [
                self._stored(directory, f"image-{index}.png", "image", _image_bytes("PNG"))
                for index in range(2)
            ]
            with patch(
                "backend.email_agent.multimodal_media.MAX_PREPARED_MEDIA_ASSETS", 1
            ):
                assets = prepare_attachment_media(items)
            self.assertEqual(len(assets), 1)

            with patch(
                "backend.email_agent.multimodal_media.MAX_PREPARED_MEDIA_BYTES", 1
            ):
                no_assets = prepare_attachment_media(items[:1])
            self.assertEqual(no_assets, ())

    def test_office_embedded_images_share_the_existing_parent_source(self) -> None:
        package = io.BytesIO()
        with __import__("zipfile").ZipFile(package, "w") as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
            archive.writestr("word/document.xml", b"<document/>")
            archive.writestr("word/media/first.png", _image_bytes("PNG"))
            archive.writestr("word/media/second.png", _image_bytes("PNG"))
        with TemporaryDirectory() as directory:
            item = self._stored(directory, "customer-original.docx", "docx", package.getvalue())

            assets = prepare_attachment_media([item])

        self.assertEqual(len(assets), 2)
        self.assertEqual({asset.source_id for asset in assets}, {"attachment:0"})
        self.assertEqual(
            [asset.provider_filename for asset in assets],
            ["image_0.png", "image_1.png"],
        )

    def test_request_cap_keeps_only_the_bounded_prefix_of_one_office_package(self) -> None:
        package = io.BytesIO()
        with __import__("zipfile").ZipFile(package, "w") as archive:
            archive.writestr("[Content_Types].xml", b"<Types/>")
            archive.writestr("word/document.xml", b"<document/>")
            for index in range(3):
                archive.writestr(f"word/media/image{index}.png", _image_bytes("PNG"))
        with TemporaryDirectory() as directory:
            item = self._stored(directory, "customer-original.docx", "docx", package.getvalue())

            with patch(
                "backend.email_agent.multimodal_media.MAX_PREPARED_MEDIA_ASSETS", 2
            ):
                assets = prepare_attachment_media([item])

        self.assertEqual(len(assets), 2)
        self.assertEqual(
            [asset.provider_filename for asset in assets], ["image_0.png", "image_1.png"]
        )

    def test_unexpected_preparation_failure_wipes_already_accepted_assets(self) -> None:
        accepted = PreparedMediaAsset(
            source_id="attachment:0",
            provider_filename="image_0.png",
            mime_type="image/png",
            kind="image",
            detail="high",
            buffer=bytearray(b"SYNTHETIC_REQUEST_MEDIA"),
        )
        with TemporaryDirectory() as directory:
            items = [
                self._stored(directory, f"image-{index}.png", "image", _image_bytes("PNG"))
                for index in range(2)
            ]
            with patch(
                "backend.email_agent.multimodal_media.sanitize_image_bytes",
                side_effect=(accepted, RuntimeError("SYNTHETIC_INTERNAL_FAILURE")),
            ), self.assertRaises(RuntimeError):
                prepare_attachment_media(items)

        self.assertEqual(accepted.buffer, bytearray())

    @staticmethod
    def _stored(directory: str, filename: str, attachment_type: str, content: bytes) -> StoredAttachment:
        path = Path(directory) / filename
        path.write_bytes(content)
        return StoredAttachment(
            safe_filename=filename,
            type=attachment_type,
            path=path,
            byte_size=len(content),
            expires_at=datetime.now(UTC),
        )


if __name__ == "__main__":
    unittest.main()
