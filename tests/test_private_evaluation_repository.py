"""Independent AES-GCM private evaluation repository tests."""

from __future__ import annotations

import json
import os
import struct
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.private_evaluation.repository import (
    DATASET_MAGIC,
    DATASET_PURPOSE,
    PrivateEvaluationError,
    read_encrypted_dataset,
    write_encrypted_dataset,
)
from backend.private_evaluation.schema import EvaluationDatasetV1
from tests.private_evaluation_fixtures import dataset_mapping, uuid4_for


class PrivateEvaluationRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "dataset.pkeval"
        self.dataset = EvaluationDatasetV1.from_mapping(dataset_mapping())
        self.key = bytearray(b"E" * 32)
        self.allow_path = patch(
            "backend.private_evaluation.repository._validate_external_dataset_path",
            return_value=self.path,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_round_trip_random_nonce_and_ciphertext_has_no_plaintext(self) -> None:
        with self.allow_path:
            write_encrypted_dataset(self.path, self.dataset, self.key)
            first = self.path.read_bytes()
            loaded = read_encrypted_dataset(self.path, self.key)
            write_encrypted_dataset(self.path, self.dataset, self.key)
            second = self.path.read_bytes()

        self.assertEqual(loaded, self.dataset)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith(DATASET_MAGIC))
        self.assertNotIn(b"Current request", first)
        self.assertNotIn(self.dataset.cases[0].case_id.encode("ascii"), first)

    def test_emitted_frame_opens_with_independent_hkdf_aesgcm_oracle(self) -> None:
        with self.allow_path:
            write_encrypted_dataset(self.path, self.dataset, self.key)
        frame = self.path.read_bytes()
        header = struct.Struct(">8sB16sQ")
        magic, version, namespace_bytes, cipher_size = header.unpack(frame[:header.size])
        nonce = frame[header.size:header.size + 12]
        ciphertext = frame[header.size + 12:]

        self.assertEqual((magic, version), (b"PKEVAL01", 1))
        self.assertEqual(uuid.UUID(bytes=namespace_bytes).version, 4)
        self.assertEqual((len(nonce), len(ciphertext)), (12, cipher_size))
        self.assertGreaterEqual(cipher_size, 16)
        derived = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=namespace_bytes,
            info=b"private-evaluation-dataset/v1",
        ).derive(bytes(self.key))
        plaintext = AESGCM(derived).decrypt(
            nonce, ciphertext, frame[:header.size] + b"private-evaluation-dataset/v1"
        )
        decoded = json.loads(plaintext.decode("utf-8"))
        self.assertEqual(decoded["dataset_namespace"], str(uuid.UUID(bytes=namespace_bytes)))

    def test_rng_failures_invalid_nonce_key_types_and_case_variant_suffix_fail_closed(self) -> None:
        for failure in (RuntimeError("secret RNG detail"), b"short", "not-bytes"):
            with self.subTest(failure=type(failure).__name__), self.allow_path, patch(
                "backend.private_evaluation.repository.os.urandom",
                side_effect=failure if isinstance(failure, Exception) else None,
                return_value=failure if not isinstance(failure, Exception) else None,
            ), self.assertRaisesRegex(
                PrivateEvaluationError, "dataset_decrypt_invalid"
            ) as caught:
                write_encrypted_dataset(self.path, self.dataset, self.key)
            self.assertNotIn("secret RNG detail", repr(caught.exception))

        for invalid in (bytearray(b"K" * 31), bytearray(b"K" * 33), True, "K" * 32):
            with (
                self.subTest(key_type=type(invalid).__name__), self.allow_path,
                self.assertRaisesRegex(PrivateEvaluationError, "evaluation_key_unavailable"),
            ):
                write_encrypted_dataset(self.path, self.dataset, invalid)  # type: ignore[arg-type]

        from backend.private_evaluation.repository import _validate_external_dataset_path

        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
            _validate_external_dataset_path(Path("C:/SyntheticExternal/private.PKEVAL"))

    def test_wrong_key_tamper_magic_version_length_namespace_and_purpose_fail_closed(self) -> None:
        with self.allow_path:
            write_encrypted_dataset(self.path, self.dataset, self.key)
            original = self.path.read_bytes()
            with self.assertRaisesRegex(PrivateEvaluationError, "dataset_decrypt_invalid"):
                read_encrypted_dataset(self.path, bytearray(b"W" * 32))

            mutations = []
            value = bytearray(original)
            value[-1] ^= 1
            mutations.append(value)
            value = bytearray(original)
            value[0:8] = b"BADMAGIC"
            mutations.append(value)
            value = bytearray(original)
            value[8] = 2
            mutations.append(value)
            value = bytearray(original)
            value[9:25] = bytes.fromhex("00112233445546778899aabbccddeeff")
            mutations.append(value)
            value = bytearray(original)
            value[25:33] = (1).to_bytes(8, "big")
            mutations.append(value)
            for payload in mutations:
                self.path.write_bytes(payload)
                with self.subTest(prefix=bytes(payload[:9])), self.assertRaisesRegex(
                    PrivateEvaluationError, "dataset_decrypt_invalid"
                ):
                    read_encrypted_dataset(self.path, self.key)

            self.path.write_bytes(original)
            with patch(
                "backend.private_evaluation.repository.DATASET_PURPOSE",
                b"private-evaluation-dataset/v2",
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_decrypt_invalid"):
                read_encrypted_dataset(self.path, self.key)

    def test_namespace_inside_payload_must_match_authenticated_header(self) -> None:
        changed = dataset_mapping()
        changed["dataset_namespace"] = uuid4_for(88_000)
        payload = json.dumps(changed, sort_keys=True, separators=(",", ":")).encode()
        with self.allow_path, patch(
            "backend.private_evaluation.repository._dataset_payload", return_value=payload
        ):
            write_encrypted_dataset(self.path, self.dataset, self.key)
            with self.assertRaisesRegex(PrivateEvaluationError, "dataset_decrypt_invalid"):
                read_encrypted_dataset(self.path, self.key)

    def test_key_size_suffix_maximum_missing_and_error_repr_are_fixed(self) -> None:
        with self.allow_path:
            with self.assertRaisesRegex(PrivateEvaluationError, "evaluation_key_unavailable"):
                write_encrypted_dataset(self.path, self.dataset, bytearray(b"short"))
            with self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable") as caught:
                read_encrypted_dataset(self.path, self.key)
            self.assertEqual(repr(caught.exception), "PrivateEvaluationError('dataset_unavailable')")

            self.path.write_bytes(os.urandom(8 * 1024 * 1024 + 1))
            with self.assertRaisesRegex(PrivateEvaluationError, "dataset_decrypt_invalid"):
                read_encrypted_dataset(self.path, self.key)

        with patch(
            "backend.private_evaluation.repository._validate_external_dataset_path"
        ) as validator:
            validator.side_effect = PrivateEvaluationError("dataset_unavailable")
            with self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                read_encrypted_dataset(self.root / "dataset.json", self.key)

    def test_external_path_policy_rejects_relative_project_temp_reparse_and_raw_vault(self) -> None:
        from backend.private_evaluation.repository import _validate_external_dataset_path

        project = Path(__file__).resolve().parents[1]
        candidates = (
            Path("relative.pkeval"),
            project / "private.pkeval",
            Path(tempfile.gettempdir()) / "private.pkeval",
            project.parent / "OneDrive" / "private.pkeval",
        )
        for candidate in candidates:
            with self.subTest(candidate=str(candidate)), self.assertRaisesRegex(
                PrivateEvaluationError, "dataset_unavailable"
            ):
                _validate_external_dataset_path(candidate)

        raw_root = self.root / "raw"
        raw_root.mkdir()
        (raw_root / "vault-index.sqlite3").write_text("marker", encoding="utf-8")
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
            _validate_external_dataset_path(raw_root / "private.pkeval")

        link = self.root / "link"
        try:
            link.symlink_to(self.root / "target", target_is_directory=True)
        except OSError:
            self.skipTest("symlink creation is unavailable")
        with self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
            _validate_external_dataset_path(link / "private.pkeval")

    def test_dataset_root_rejects_descendant_raw_vault_and_private_store_markers(self) -> None:
        from backend.private_evaluation.repository import (
            _inside_raw_vault,
            _overlaps_other_store,
        )

        nested_raw = self.root / "nested_raw"
        nested_raw.mkdir()
        (nested_raw / "vault-index.sqlite3").write_text("synthetic", encoding="utf-8")
        self.assertTrue(_inside_raw_vault(self.path))
        (nested_raw / "vault-index.sqlite3").unlink()
        (nested_raw / "candidate-store.pkcand").write_text("synthetic", encoding="utf-8")
        self.assertTrue(_overlaps_other_store(self.path))

    def test_read_is_bounded_and_detects_target_identity_swap_after_validation(self) -> None:
        replacement = self.root / "replacement.pkeval"
        with patch("tempfile.gettempdir", return_value="C:/SyntheticPolicyTemp"):
            write_encrypted_dataset(self.path, self.dataset, self.key)
            write_encrypted_dataset(replacement, self.dataset, self.key)

            swapped = False

            def swap(stage: str, _path: Path) -> None:
                nonlocal swapped
                if stage == "read_before_open" and not swapped:
                    os.replace(replacement, self.path)
                    swapped = True

            with patch(
                "backend.private_evaluation.repository._test_race_hook",
                side_effect=swap,
                create=True,
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                read_encrypted_dataset(self.path, self.key)

            self.path.write_bytes(os.urandom(8 * 1024 * 1024 + 1))
            with patch.object(
                Path, "read_bytes", side_effect=AssertionError("unbounded read")
            ), self.assertRaisesRegex(
                PrivateEvaluationError, "dataset_decrypt_invalid"
            ):
                read_encrypted_dataset(self.path, self.key)

    def test_write_detects_target_identity_swap_before_replace(self) -> None:
        intruder = self.root / "intruder.bin"
        intruder.write_bytes(b"synthetic intruder")
        with patch("tempfile.gettempdir", return_value="C:/SyntheticPolicyTemp"):
            write_encrypted_dataset(self.path, self.dataset, self.key)

            swapped = False

            def swap(stage: str, _path: Path) -> None:
                nonlocal swapped
                if stage == "write_before_replace" and not swapped:
                    os.replace(intruder, self.path)
                    swapped = True

            with patch(
                "backend.private_evaluation.repository._test_race_hook",
                side_effect=swap,
                create=True,
            ), self.assertRaisesRegex(PrivateEvaluationError, "dataset_unavailable"):
                write_encrypted_dataset(self.path, self.dataset, self.key)

    def test_constants_pin_independent_frame_contract(self) -> None:
        self.assertEqual(DATASET_MAGIC, b"PKEVAL01")
        self.assertEqual(DATASET_PURPOSE, b"private-evaluation-dataset/v1")


if __name__ == "__main__":
    unittest.main()
