"""Security tests for bounded Office embedded-image extraction."""

from __future__ import annotations

import io
import unittest
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from PIL import Image

from backend.email_agent import attachment_safety
from backend.email_agent.multimodal_media import MediaPreparationError
from backend.email_agent.multimodal_media import PreparedMediaAsset
from backend.email_agent.office_embedded_media import (
    MAX_OFFICE_MEDIA_COUNT,
    extract_office_media,
)


def _png_bytes() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (3, 2), (12, 34, 56)).save(output, format="PNG")
    return output.getvalue()


def _package(entries: list[tuple[str, bytes]], *, compression: int = ZIP_STORED) -> bytes:
    output = io.BytesIO()
    with ZipFile(output, "w", compression=compression) as package:
        for name, content in entries:
            package.writestr(name, content)
    return output.getvalue()


def _office_package(
    attachment_type: str,
    entries: list[tuple[str, bytes]],
    *,
    compression: int = ZIP_STORED,
) -> bytes:
    root = (
        ("word/document.xml", b"<document/>")
        if attachment_type == "docx"
        else ("xl/workbook.xml", b"<workbook/>")
    )
    return _package(
        [("[Content_Types].xml", b"<Types/>"), root, *entries],
        compression=compression,
    )


def _mark_first_entry_encrypted(content: bytes) -> bytes:
    mutated = bytearray(content)
    local = mutated.index(b"PK\x03\x04")
    central = mutated.index(b"PK\x01\x02")
    mutated[local + 6] |= 0x01
    mutated[central + 8] |= 0x01
    return bytes(mutated)


def _mark_first_local_header_encrypted(content: bytes) -> bytes:
    mutated = bytearray(content)
    local = mutated.index(b"PK\x03\x04")
    mutated[local + 6] |= 0x01
    return bytes(mutated)


def _replace_entry_name(content: bytes, old: str, new: str) -> bytes:
    self_check = (old.encode("ascii"), new.encode("ascii"))
    if len(self_check[0]) != len(self_check[1]):
        raise AssertionError("ZIP test names must have equal byte lengths.")
    return content.replace(*self_check)


class OfficeEmbeddedMediaTests(unittest.TestCase):
    def test_extracts_only_type_specific_media_with_opaque_names_and_same_source(self) -> None:
        content = _office_package("docx", [
            ("word/media/customer-supplied-name.png", _png_bytes()),
            ("xl/media/wrong-surface.png", _png_bytes()),
            ("custom/media/ignored.png", _png_bytes()),
        ])

        assets = extract_office_media(
            content,
            attachment_type="docx",
            source_id="attachment:3",
            start_index=4,
        )

        self.assertEqual(len(assets), 1)
        self.assertEqual(assets[0].source_id, "attachment:3")
        self.assertEqual(assets[0].provider_filename, "image_4.png")
        self.assertNotIn("customer-supplied-name", repr(assets[0]))

    def test_xlsx_accepts_only_xl_media(self) -> None:
        content = _office_package("xlsx", [
            ("xl/media/image1.png", _png_bytes()),
            ("word/media/image2.png", _png_bytes()),
        ])

        assets = extract_office_media(
            content, attachment_type="xlsx", source_id="attachment:1", start_index=0
        )

        self.assertEqual(len(assets), 1)

    def test_rejects_zip_without_required_ooxml_roots(self) -> None:
        with self.assertRaises(MediaPreparationError):
            extract_office_media(
                _package([("word/media/image1.png", _png_bytes())]),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )

    def test_rejects_casefold_duplicate_package_names(self) -> None:
        content = _office_package("docx", [
            ("word/media/image.png", _png_bytes()),
            ("WORD/MEDIA/IMAGE.PNG", _png_bytes()),
        ])

        with self.assertRaises(MediaPreparationError):
            extract_office_media(
                content, attachment_type="docx", source_id="attachment:0", start_index=0
            )

    def test_rejects_office_input_above_the_raw_request_limit(self) -> None:
        content = _office_package("docx", [("word/media/image.png", _png_bytes())])

        with patch(
            "backend.email_agent.attachment_safety.OFFICE_ZIP_MAX_INPUT_BYTES",
            len(content) - 1,
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                content, attachment_type="docx", source_id="attachment:0", start_index=0
            )

    def test_media_extraction_uses_the_shared_raw_package_policy(self) -> None:
        content = _office_package("docx", [("word/media/image.png", _png_bytes())])

        with patch.object(
            attachment_safety,
            "OFFICE_ZIP_MAX_INPUT_BYTES",
            len(content) - 1,
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                content, attachment_type="docx", source_id="attachment:0", start_index=0
            )

    def test_rejects_malformed_or_non_zip_office_bytes(self) -> None:
        with self.assertRaises(MediaPreparationError):
            extract_office_media(
                b"SYNTHETIC_NOT_A_ZIP",
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )

    def test_rejects_traversal_backslash_absolute_and_drive_names_anywhere(self) -> None:
        unsafe_packages = (
            ("word/media/../private.png", _office_package("docx", [("word/media/../private.png", _png_bytes())])),
            (
                r"word\media\private.png",
                _replace_entry_name(
                    _office_package("docx", [("word/media/private.png", _png_bytes())]),
                    "word/media/private.png",
                    r"word\media\private.png",
                ),
            ),
            ("/word/media/private.png", _office_package("docx", [("/word/media/private.png", _png_bytes())])),
            ("C:/word/media/private.png", _office_package("docx", [("C:/word/media/private.png", _png_bytes())])),
            ("../custom/private.xml", _office_package("docx", [("../custom/private.xml", _png_bytes())])),
        )
        for name, package in unsafe_packages:
            with self.subTest(name=name):
                with self.assertRaises(MediaPreparationError) as raised:
                    extract_office_media(
                        package,
                        attachment_type="docx",
                        source_id="attachment:99",
                        start_index=0,
                    )
                rendered = str(raised.exception)
                self.assertNotIn(name, rendered)
                self.assertNotIn("attachment:99", rendered)

    def test_rejects_encrypted_entries_before_read(self) -> None:
        encrypted = _mark_first_entry_encrypted(
            _office_package("docx", [("word/media/image1.png", _png_bytes())])
        )

        with self.assertRaises(MediaPreparationError):
            extract_office_media(
                encrypted, attachment_type="docx", source_id="attachment:0", start_index=0
            )

    def test_rejects_local_header_only_encryption_mismatch_before_media_read(self) -> None:
        inconsistent = _mark_first_local_header_encrypted(
            _office_package("docx", [("word/media/image1.png", _png_bytes())])
        )

        with patch.object(ZipFile, "read", autospec=True) as read, self.assertRaises(
            MediaPreparationError
        ):
            extract_office_media(
                inconsistent,
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )
        read.assert_not_called()

    def test_unexpected_later_sanitizer_failure_wipes_partial_assets_and_reraises(self) -> None:
        class SyntheticUnexpectedError(Exception):
            pass

        first = PreparedMediaAsset(
            source_id="attachment:0",
            provider_filename="image_0.png",
            mime_type="image/png",
            kind="image",
            detail="high",
            buffer=bytearray(b"SYNTHETIC_PARTIAL_MEDIA"),
        )
        content = _office_package("docx", [
            ("word/media/image1.png", _png_bytes()),
            ("word/media/image2.png", _png_bytes()),
        ])

        with patch(
            "backend.email_agent.office_embedded_media.sanitize_image_bytes",
            side_effect=(first, SyntheticUnexpectedError("synthetic failure")),
        ), self.assertRaises(SyntheticUnexpectedError):
            extract_office_media(
                content, attachment_type="docx", source_id="attachment:0", start_index=0
            )

        self.assertEqual(first.buffer, bytearray())

    def test_rejects_package_entry_count_per_entry_and_aggregate_bombs(self) -> None:
        with patch(
            "backend.email_agent.office_embedded_media.MAX_OFFICE_PACKAGE_ENTRIES", 1
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                _package([("word/a.xml", b"a"), ("word/b.xml", b"b")]),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )
        with patch(
            "backend.email_agent.office_embedded_media.MAX_OFFICE_ENTRY_BYTES", 2
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                _package([("word/a.xml", b"abc")]),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )
        with patch(
            "backend.email_agent.office_embedded_media.MAX_OFFICE_TOTAL_BYTES", 3
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                _package([("word/a.xml", b"ab"), ("word/b.xml", b"cd")]),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )

    def test_rejects_high_compression_ratio_bomb(self) -> None:
        content = _office_package(
            "docx",
            [("word/media/image1.png", b"0" * 20_000)], compression=ZIP_DEFLATED
        )

        with self.assertRaises(MediaPreparationError):
            extract_office_media(
                content, attachment_type="docx", source_id="attachment:0", start_index=0
            )

    def test_rejects_embedded_image_count_per_entry_and_aggregate_limits(self) -> None:
        image = _png_bytes()
        too_many = [
            (f"word/media/image{index}.png", image)
            for index in range(MAX_OFFICE_MEDIA_COUNT + 1)
        ]
        with self.assertRaises(MediaPreparationError):
            extract_office_media(
                _office_package("docx", too_many),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )
        with patch(
            "backend.email_agent.office_embedded_media.MAX_OFFICE_MEDIA_ENTRY_BYTES",
            len(image) - 1,
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                _office_package("docx", [("word/media/image1.png", image)]),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )
        with patch(
            "backend.email_agent.office_embedded_media.MAX_OFFICE_MEDIA_TOTAL_BYTES",
            len(image) * 2 - 1,
        ), self.assertRaises(MediaPreparationError):
            extract_office_media(
                _office_package("docx", [
                    ("word/media/image1.png", image),
                    ("word/media/image2.png", image),
                ]),
                attachment_type="docx",
                source_id="attachment:0",
                start_index=0,
            )

    def test_rejects_embedded_image_magic_and_extension_mismatch(self) -> None:
        for name, content in (
            ("word/media/image1.png", b"NOT_AN_IMAGE"),
            ("word/media/image2.jpg", _png_bytes()),
        ):
            with self.subTest(name=name), self.assertRaises(MediaPreparationError):
                extract_office_media(
                    _office_package("docx", [(name, content)]),
                    attachment_type="docx",
                    source_id="attachment:0",
                    start_index=0,
                )


if __name__ == "__main__":
    unittest.main()
