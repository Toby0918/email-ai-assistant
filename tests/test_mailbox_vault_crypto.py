"""Cryptographic frame tests use only synthetic plaintext and injected RNGs."""

from __future__ import annotations

import unittest

from backend.mailbox_ingest.errors import VaultError
from backend.mailbox_ingest.models import SecretBuffer
from backend.mailbox_ingest.vault_crypto import (
    FRAME_MAGIC,
    VaultCrypto,
)


class SequenceRng:
    def __init__(self, values: list[bytes]) -> None:
        self.values = list(values)

    def __call__(self, size: int) -> bytes:
        value = self.values.pop(0)
        if len(value) != size:
            raise AssertionError("test RNG size mismatch")
        return value


class VaultCryptoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.master = SecretBuffer(b"M" * 32)
        self.record_id = "0123456789abcdef0123456789abcdef"
        self.crypto = VaultCrypto(
            self.master,
            vault_id="11111111-2222-4333-8444-555555555555",
            rng=SequenceRng([b"N" * 12, b"O" * 12, b"P" * 12]),
            max_plaintext_size=128,
        )

    def tearDown(self) -> None:
        self.crypto.close()
        self.master.wipe()

    def test_round_trip_uses_versioned_frame_and_mutable_plaintext(self) -> None:
        frame = self.crypto.encrypt(self.record_id, b"synthetic body")

        plaintext = self.crypto.decrypt(self.record_id, frame)

        self.assertTrue(frame.startswith(FRAME_MAGIC))
        self.assertIsInstance(plaintext, SecretBuffer)
        self.assertEqual(bytes(plaintext), b"synthetic body")
        plaintext.wipe()
        self.assertEqual(bytes(plaintext), b"\x00" * len(plaintext))
        self.assertEqual(repr(plaintext), "SecretBuffer(<redacted>)")

    def test_nonce_is_unique_and_duplicate_rng_output_is_rejected(self) -> None:
        first = self.crypto.encrypt(self.record_id, b"one")
        second = self.crypto.encrypt(
            "fedcba9876543210fedcba9876543210", b"two"
        )
        self.assertNotEqual(first, second)

        duplicate = VaultCrypto(
            SecretBuffer(b"K" * 32),
            vault_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
            rng=SequenceRng([b"Q" * 12, b"Q" * 12]),
        )
        try:
            duplicate.encrypt(self.record_id, b"one")
            with self.assertRaisesRegex(VaultError, "nonce_reuse"):
                duplicate.encrypt(self.record_id, b"two")
        finally:
            duplicate.close()

    def test_record_id_is_bound_as_associated_data(self) -> None:
        frame = self.crypto.encrypt(self.record_id, b"synthetic body")

        with self.assertRaisesRegex(VaultError, "record_binding_mismatch"):
            self.crypto.decrypt("fedcba9876543210fedcba9876543210", frame)

    def test_frame_rejects_tamper_truncation_trailing_and_wrong_versions(self) -> None:
        frame = bytearray(self.crypto.encrypt(self.record_id, b"synthetic body"))
        cases = {
            "magic": bytes(b"BADMAGIC" + frame[8:]),
            "frame version": bytes(frame[:8] + b"\x7f" + frame[9:]),
            "algorithm": bytes(frame[:9] + b"\x7f" + frame[10:]),
            "key version": bytes(frame[:10] + b"\x00\x02" + frame[12:]),
            "truncated": bytes(frame[:-1]),
            "trailing": bytes(frame + b"x"),
            "ciphertext": bytes(frame[:-1] + bytes([frame[-1] ^ 1])),
        }

        for label, candidate in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(VaultError) as caught:
                    self.crypto.decrypt(self.record_id, candidate)
                self.assertRegex(caught.exception.code, r"^[a-z0-9_]+$")
                self.assertNotIn("synthetic body", repr(caught.exception))

    def test_wrong_vault_fails_closed(self) -> None:
        frame = self.crypto.encrypt(self.record_id, b"synthetic body")
        other = VaultCrypto(
            SecretBuffer(b"M" * 32),
            vault_id="99999999-8888-4777-8666-555555555555",
            rng=SequenceRng([b"Z" * 12]),
            max_plaintext_size=128,
        )
        try:
            with self.assertRaisesRegex(VaultError, "record_authentication_failed"):
                other.decrypt(self.record_id, frame)
        finally:
            other.close()

    def test_rejects_invalid_ids_input_sizes_and_rng_nonce_lengths(self) -> None:
        invalid_ids = ("", "not-hex", "0" * 31, "0" * 33, "A" * 32)
        for record_id in invalid_ids:
            with self.subTest(record_id=record_id):
                with self.assertRaisesRegex(VaultError, "invalid_record_id"):
                    self.crypto.encrypt(record_id, b"x")

        with self.assertRaisesRegex(VaultError, "record_too_large"):
            self.crypto.encrypt(self.record_id, b"x" * 129)

        bad_rng = VaultCrypto(
            SecretBuffer(b"R" * 32),
            vault_id="bbbbbbbb-cccc-4ddd-8eee-ffffffffffff",
            rng=lambda size: b"short",
        )
        try:
            with self.assertRaisesRegex(VaultError, "invalid_nonce"):
                bad_rng.encrypt(self.record_id, b"x")
        finally:
            bad_rng.close()

    def test_decrypt_rejects_oversized_declared_ciphertext_before_aead(self) -> None:
        frame = bytearray(self.crypto.encrypt(self.record_id, b"small"))
        frame[14:22] = (10_000).to_bytes(8, "big")

        with self.assertRaisesRegex(VaultError, "invalid_frame_size"):
            self.crypto.decrypt(self.record_id, bytes(frame))

    def test_encryption_and_dedup_keys_are_hkdf_separated(self) -> None:
        self.assertNotEqual(
            bytes(self.crypto._record_encryption_key),
            bytes(self.crypto._dedup_hmac_key),
        )
        digest_one = self.crypto.dedup_hmac(b"same")
        digest_two = self.crypto.dedup_hmac(b"same")
        self.assertEqual(digest_one, digest_two)
        self.assertEqual(len(digest_one), 32)
        self.assertNotIn(b"same", digest_one)

    def test_close_wipes_derived_keys_and_disables_use(self) -> None:
        encryption_key = self.crypto._record_encryption_key
        hmac_key = self.crypto._dedup_hmac_key

        self.crypto.close()

        self.assertEqual(bytes(encryption_key), b"\x00" * 32)
        self.assertEqual(bytes(hmac_key), b"\x00" * 32)
        with self.assertRaisesRegex(VaultError, "crypto_closed"):
            self.crypto.encrypt(self.record_id, b"x")


if __name__ == "__main__":
    unittest.main()
