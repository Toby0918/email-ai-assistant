"""Synthetic DPAPI and recovery-envelope tests for the mailbox vault."""

from __future__ import annotations

import importlib
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.mailbox_ingest.dpapi import (
    CRYPTPROTECT_LOCAL_MACHINE,
    CRYPTPROTECT_UI_FORBIDDEN,
    DpapiProtector,
    NativeAllocation,
    _CtypesDpapiApi,
    _WindowsDpapiBackend,
)
from backend.mailbox_ingest.errors import VaultError
from backend.mailbox_ingest.envelope_io import write_json_atomic
from backend.mailbox_ingest.key_envelopes import (
    initialize_key_envelopes,
    open_master_key,
    open_master_key_with_recovery,
    reconcile_recovery_rewrap,
    revoke_key_envelopes,
    rewrap_recovery_key,
)
from backend.mailbox_ingest.models import SecretBuffer


class FakeDpapiBackend:
    def __init__(self) -> None:
        self.flags: list[int] = []

    def protect(self, data: bytearray, flags: int) -> SecretBuffer:
        self.flags.append(flags)
        return SecretBuffer(b"protected:" + bytes(data[::-1]))

    def unprotect(self, data: bytearray, flags: int) -> SecretBuffer:
        self.flags.append(flags)
        prefix = b"protected:"
        if not bytes(data).startswith(prefix):
            raise RuntimeError("native blob detail")
        return SecretBuffer(bytes(data[len(prefix) :][::-1]))


class FakeNativeApi:
    def __init__(
        self,
        *,
        success: bool = True,
        read_error: bool = False,
        wipe_error: bool = False,
        free_error: bool = False,
    ) -> None:
        self.success = success
        self.read_error = read_error
        self.wipe_error = wipe_error
        self.free_error = free_error
        self.events: list[str] = []

    def protect(self, data: bytearray, flags: int) -> NativeAllocation:
        self.events.append("protect")
        return NativeAllocation(self.success, object(), 4)

    def unprotect(self, data: bytearray, flags: int) -> NativeAllocation:
        self.events.append("unprotect")
        return NativeAllocation(self.success, object(), 4)

    def read(self, allocation: NativeAllocation) -> bytes:
        self.events.append("read")
        if self.read_error:
            raise RuntimeError("read leaked native detail")
        return b"data"

    def wipe(self, allocation: NativeAllocation) -> None:
        self.events.append("wipe")
        if self.wipe_error:
            raise RuntimeError("wipe leaked native detail")

    def free(self, allocation: NativeAllocation) -> None:
        self.events.append("free")
        if self.free_error:
            raise RuntimeError("free leaked native detail")


class DpapiTests(unittest.TestCase):
    def test_unprotect_does_not_request_unused_native_description_allocation(self) -> None:
        source = inspect.getsource(_CtypesDpapiApi._call)

        self.assertNotIn("description =", source)
        self.assertNotIn("byref(description)", source)

    def test_current_user_ui_forbidden_flags_and_mutable_unprotect(self) -> None:
        backend = FakeDpapiBackend()
        protector = DpapiProtector(backend=backend)

        ciphertext = protector.protect(b"synthetic secret")
        plaintext = protector.unprotect(ciphertext)

        self.assertEqual(bytes(plaintext), b"synthetic secret")
        self.assertIsInstance(plaintext, SecretBuffer)
        self.assertTrue(all(flag & CRYPTPROTECT_UI_FORBIDDEN for flag in backend.flags))
        self.assertTrue(all(not flag & CRYPTPROTECT_LOCAL_MACHINE for flag in backend.flags))

    def test_native_output_is_wiped_and_localfreed_on_every_branch(self) -> None:
        cases = (
            ({}, None),
            ({"success": False}, "dpapi_protect_failed"),
            ({"read_error": True}, "dpapi_protect_failed"),
            ({"wipe_error": True}, "dpapi_cleanup_failed"),
            ({"free_error": True}, "dpapi_cleanup_failed"),
        )
        for options, expected_code in cases:
            api = FakeNativeApi(**options)
            backend = _WindowsDpapiBackend(api_loader=lambda: api)
            with self.subTest(options=options):
                if expected_code is None:
                    result = backend.protect(bytearray(b"x"), CRYPTPROTECT_UI_FORBIDDEN)
                    self.assertEqual(bytes(result), b"data")
                else:
                    with self.assertRaisesRegex(VaultError, expected_code) as caught:
                        backend.protect(
                            bytearray(b"x"), CRYPTPROTECT_UI_FORBIDDEN
                        )
                    self.assertNotIn("native detail", repr(caught.exception))
                self.assertIn("wipe", api.events)
                self.assertIn("free", api.events)
                self.assertLess(api.events.index("wipe"), api.events.index("free"))

    def test_dpapi_module_import_does_not_load_windll(self) -> None:
        module_name = "backend.mailbox_ingest.dpapi"
        with mock.patch("ctypes.WinDLL", create=True) as win_dll:
            imported = importlib.reload(sys.modules[module_name])

        self.assertIsNotNone(imported)
        win_dll.assert_not_called()

    def test_backend_failures_return_fixed_safe_errors(self) -> None:
        class ExplodingBackend:
            def protect(self, data: bytearray, flags: int) -> SecretBuffer:
                raise RuntimeError("secret native path C:/hidden")

        with self.assertRaises(VaultError) as caught:
            DpapiProtector(backend=ExplodingBackend()).protect(b"top secret")

        self.assertEqual(caught.exception.code, "dpapi_protect_failed")
        self.assertEqual(str(caught.exception), "dpapi_protect_failed")
        self.assertNotIn("hidden", repr(caught.exception))
        self.assertNotIn("top secret", repr(caught.exception))


class SequenceRng:
    def __init__(self, values: list[bytes]) -> None:
        self.values = list(values)

    def __call__(self, size: int) -> bytes:
        value = self.values.pop(0)
        if len(value) != size:
            raise AssertionError(f"expected {size}, got {len(value)}")
        return value


class KeyEnvelopeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.old_recovery = self.root / "recovery-a" / "offline.key"
        self.new_recovery = self.root / "recovery-b" / "offline.key"
        self.old_recovery.parent.mkdir()
        self.new_recovery.parent.mkdir()
        self.dpapi = DpapiProtector(backend=FakeDpapiBackend())
        self.master = b"M" * 32
        self.recovery_kek = b"R" * 32
        self.nonce = b"N" * 12

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _distinct(_vault: Path, _recovery: Path) -> bool:
        return True

    def _initialize(self) -> None:
        initialize_key_envelopes(
            self.vault,
            self.old_recovery,
            self.dpapi,
            rng=SequenceRng([self.master, self.recovery_kek, self.nonce]),
            distinct_volume_check=self._distinct,
            vault_id="11111111-2222-4333-8444-555555555555",
        )

    def test_initialize_and_open_with_dpapi_or_explicit_recovery(self) -> None:
        self._initialize()

        dpapi_master = open_master_key(self.vault, self.dpapi)
        recovery_master = open_master_key_with_recovery(
            self.vault, self.old_recovery
        )

        self.assertEqual(bytes(dpapi_master), self.master)
        self.assertEqual(bytes(recovery_master), self.master)
        self.assertIsInstance(dpapi_master, SecretBuffer)
        self.assertEqual(repr(dpapi_master), "SecretBuffer(<redacted>)")
        dpapi_master.wipe()
        recovery_master.wipe()

    def test_envelope_filesystem_errors_are_fixed_and_path_safe(self) -> None:
        with mock.patch.object(
            Path, "mkdir", side_effect=OSError(f"denied {self.vault}")
        ):
            with self.assertRaises(VaultError) as caught:
                write_json_atomic(self.vault / "keys" / "state.json", {"v": 1})

        self.assertEqual(caught.exception.code, "key_envelope_write_failed")
        self.assertNotIn(str(self.vault), repr(caught.exception))

    def test_recovery_key_uses_exclusive_creation_and_separate_volume(self) -> None:
        self.old_recovery.write_bytes(b"do-not-overwrite")

        with self.assertRaisesRegex(VaultError, "recovery_key_exists"):
            self._initialize()
        self.assertEqual(self.old_recovery.read_bytes(), b"do-not-overwrite")

        self.old_recovery.unlink()
        with self.assertRaisesRegex(VaultError, "recovery_volume_not_separate"):
            initialize_key_envelopes(
                self.vault,
                self.old_recovery,
                self.dpapi,
                rng=SequenceRng([self.master, self.recovery_kek, self.nonce]),
                distinct_volume_check=lambda _a, _b: False,
                vault_id="11111111-2222-4333-8444-555555555555",
            )

    def test_rewrap_refuses_a_preexisting_unstaged_recovery_key(self) -> None:
        self._initialize()
        self.new_recovery.write_bytes(b"preexisting-untrusted-material")

        with self.assertRaisesRegex(VaultError, "recovery_key_exists"):
            rewrap_recovery_key(
                self.vault,
                self.old_recovery,
                self.new_recovery,
                rng=SequenceRng([b"C" * 32, b"D" * 12]),
                distinct_volume_check=self._distinct,
            )

        self.assertEqual(
            self.new_recovery.read_bytes(), b"preexisting-untrusted-material"
        )
        state = json.loads(
            (self.vault / "keys" / "recovery-state.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(state["state"], "stable")

    def test_envelope_tamper_and_wrong_vault_binding_fail_closed(self) -> None:
        self._initialize()
        recovery_envelope = self.vault / "keys" / "recovery.1.json"
        data = json.loads(recovery_envelope.read_text(encoding="utf-8"))
        data["vault_id"] = "99999999-8888-4777-8666-555555555555"
        recovery_envelope.write_text(json.dumps(data), encoding="utf-8")

        with self.assertRaises(VaultError) as caught:
            open_master_key_with_recovery(self.vault, self.old_recovery)
        self.assertIn(
            caught.exception.code,
            {"invalid_key_envelope", "recovery_authentication_failed"},
        )
        self.assertNotIn(self.master.decode(), repr(caught.exception))
        self.assertNotIn(str(self.old_recovery), repr(caught.exception))

    def test_revoke_removes_vault_envelopes_but_not_offline_recovery(self) -> None:
        self._initialize()

        revoke_key_envelopes(self.vault)

        self.assertTrue(self.old_recovery.exists())
        self.assertFalse((self.vault / "keys" / "dpapi.json").exists())
        self.assertFalse(
            (self.vault / "keys" / "recovery-state.json").exists()
        )
        self.assertEqual(list((self.vault / "keys").glob("recovery.*.json")), [])

    def test_rewrap_is_crash_recoverable_at_each_durable_state(self) -> None:
        crash_states = ("staged", "verified", "activated")
        for crash_state in crash_states:
            with self.subTest(crash_state=crash_state):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    root = Path(tmp_dir)
                    vault = root / "vault"
                    old_path = root / "old" / "offline.key"
                    new_path = root / "new" / "offline.key"
                    vault.mkdir()
                    old_path.parent.mkdir()
                    new_path.parent.mkdir()
                    initialize_key_envelopes(
                        vault,
                        old_path,
                        self.dpapi,
                        rng=SequenceRng([self.master, b"A" * 32, b"B" * 12]),
                        distinct_volume_check=self._distinct,
                        vault_id="aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
                    )

                    def crash_hook(state: str) -> None:
                        if state == crash_state:
                            raise RuntimeError("simulated crash")

                    with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                        rewrap_recovery_key(
                            vault,
                            old_path,
                            new_path,
                            rng=SequenceRng([b"C" * 32, b"D" * 12]),
                            distinct_volume_check=self._distinct,
                            crash_hook=crash_hook,
                        )

                    reconcile_recovery_rewrap(
                        vault,
                        old_path,
                        new_path,
                        distinct_volume_check=self._distinct,
                    )
                    reopened = open_master_key_with_recovery(vault, new_path)
                    self.assertEqual(bytes(reopened), self.master)
                    reopened.wipe()
                    state = json.loads(
                        (vault / "keys" / "recovery-state.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    self.assertEqual(state["state"], "stable")
                    self.assertEqual(state["active_generation"], 2)
                    self.assertTrue(old_path.exists())
                    self.assertFalse((vault / "keys" / "recovery.1.json").exists())

    def test_rewrap_reconciles_unrecorded_staged_envelope(self) -> None:
        self._initialize()

        def crash_before_state(state: str) -> None:
            if state == "envelope_staged":
                raise RuntimeError("simulated crash")

        with self.assertRaisesRegex(RuntimeError, "simulated crash"):
            rewrap_recovery_key(
                self.vault,
                self.old_recovery,
                self.new_recovery,
                rng=SequenceRng([b"C" * 32, b"D" * 12]),
                distinct_volume_check=self._distinct,
                crash_hook=crash_before_state,
            )

        reconcile_recovery_rewrap(
            self.vault,
            self.old_recovery,
            self.new_recovery,
            distinct_volume_check=self._distinct,
        )
        reopened = open_master_key_with_recovery(self.vault, self.new_recovery)
        self.assertEqual(bytes(reopened), self.master)
        reopened.wipe()

    def test_rewrap_recovers_key_created_before_envelope_idempotently(self) -> None:
        from backend.mailbox_ingest import recovery_rewrap as implementation

        self._initialize()
        original_write_key = implementation._write_recovery_key

        def write_after_prepared(path: Path, key: SecretBuffer) -> str:
            state = json.loads(
                (self.vault / "keys" / "recovery-state.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(state["state"], "prepared")
            self.assertEqual(state["active_generation"], 1)
            self.assertEqual(state["staged_generation"], 2)
            expected_key_id = state["prepared_recovery_key_id"]
            written_key_id = original_write_key(path, key)
            self.assertEqual(written_key_id, expected_key_id)
            return written_key_id

        def crash_after_key(state: str) -> None:
            if state == "recovery_key_created":
                raise RuntimeError("simulated crash")

        with mock.patch.object(
            implementation, "_write_recovery_key", side_effect=write_after_prepared
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                rewrap_recovery_key(
                    self.vault,
                    self.old_recovery,
                    self.new_recovery,
                    rng=SequenceRng([b"C" * 32]),
                    distinct_volume_check=self._distinct,
                    crash_hook=crash_after_key,
                )

        self.assertTrue(self.new_recovery.exists())
        self.assertFalse((self.vault / "keys" / "recovery.2.json").exists())
        still_active = open_master_key_with_recovery(
            self.vault, self.old_recovery
        )
        self.assertEqual(bytes(still_active), self.master)
        still_active.wipe()

        reconcile_recovery_rewrap(
            self.vault,
            self.old_recovery,
            self.new_recovery,
            rng=SequenceRng([b"D" * 12]),
            distinct_volume_check=self._distinct,
        )
        reconcile_recovery_rewrap(
            self.vault,
            self.old_recovery,
            self.new_recovery,
            rng=SequenceRng([]),
            distinct_volume_check=self._distinct,
        )

        reopened = open_master_key_with_recovery(self.vault, self.new_recovery)
        self.assertEqual(bytes(reopened), self.master)
        reopened.wipe()
        state = json.loads(
            (self.vault / "keys" / "recovery-state.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(state["state"], "stable")
        self.assertEqual(state["active_generation"], 2)
        self.assertIsNone(state["prepared_recovery_key_id"])
        self.assertTrue(self.old_recovery.exists())


if __name__ == "__main__":
    unittest.main()
