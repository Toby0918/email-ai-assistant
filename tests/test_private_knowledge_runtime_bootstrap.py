"""Startup-only private-knowledge bootstrap tests using synthetic dependencies."""

from __future__ import annotations

import importlib
import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.private_knowledge.errors import PrivateKnowledgeError
from backend.private_knowledge.key_store import AuthorityKeyMaterial, SecretBytes
from backend.private_knowledge.runtime_loader import RuntimeKnowledgeLoad
from backend.private_knowledge.runtime_schema import RuntimeKnowledgeCard


PROJECT = Path("C:/Synthetic/Project")
AUTHORITY = "D:/Private/Authority"
SNAPSHOT = "E:/Private/Runtime/knowledge.pksnap"


def _card() -> RuntimeKnowledgeCard:
    return RuntimeKnowledgeCard.from_mapping(
        {
            "schema_version": "RuntimeKnowledgeCardV1",
            "card_id": "00000000-0000-4000-8000-000000000001",
            "version": 1,
            "rule_type": "classification",
            "language": "en",
            "applicability": {
                "accountability": "general",
                "direction": "any",
                "categories": ["order_followup"],
            },
            "generic_rule": "check approved status before response",
            "normalized_signals": ["deadline_signal"],
            "enum_mapping": {
                "priorities": ["high"],
                "categories": ["order_followup"],
                "risks": ["delivery_risk"],
                "actions": ["confirm"],
            },
            "safe_reply_guidance": "ask for confirmation before commitments",
        }
    )


class PrivateKnowledgeRuntimeBootstrapTests(unittest.TestCase):
    def _load(self, **overrides):
        from backend.private_knowledge.runtime_bootstrap import (
            load_configured_runtime_cards,
        )

        values = {
            "enabled": True,
            "authority_root": AUTHORITY,
            "snapshot_path": SNAPSHOT,
            "project_root": PROJECT,
            "protector_factory": Mock(return_value=object()),
            "storage_validator": Mock(),
            "snapshot_path_validator": Mock(return_value=Path(SNAPSHOT)),
            "key_opener": Mock(),
            "snapshot_loader": Mock(),
        }
        values.update(overrides)
        return load_configured_runtime_cards(**values), values

    def test_disabled_or_blank_configuration_does_not_probe_paths_or_dpapi(self) -> None:
        for enabled, authority, snapshot in (
            (False, AUTHORITY, SNAPSHOT),
            (1, AUTHORITY, SNAPSHOT),
            (True, "", SNAPSHOT),
            (True, AUTHORITY, ""),
            (True, " D:/Private/Authority ", SNAPSHOT),
        ):
            with self.subTest(enabled=enabled, authority=authority, snapshot=snapshot):
                protector = Mock()
                validator = Mock()
                cards, values = self._load(
                    enabled=enabled,
                    authority_root=authority,
                    snapshot_path=snapshot,
                    protector_factory=protector,
                    storage_validator=validator,
                )

                self.assertEqual(cards, ())
                protector.assert_not_called()
                validator.assert_not_called()
                values["key_opener"].assert_not_called()
                values["snapshot_loader"].assert_not_called()

    def test_relative_or_rejected_paths_fail_before_key_access(self) -> None:
        for authority, snapshot in (
            ("relative/authority", SNAPSHOT),
            (AUTHORITY, "relative/knowledge.pksnap"),
        ):
            with self.subTest(authority=authority, snapshot=snapshot):
                cards, values = self._load(
                    authority_root=authority,
                    snapshot_path=snapshot,
                )
                self.assertEqual(cards, ())
                values["protector_factory"].assert_not_called()

        for failure in (
            "private_storage_path_invalid",
            "snapshot_path_invalid",
        ):
            with self.subTest(failure=failure):
                storage = Mock()
                path = Mock(return_value=Path(SNAPSHOT))
                if failure == "private_storage_path_invalid":
                    storage.side_effect = PrivateKnowledgeError(failure)
                else:
                    path.side_effect = PrivateKnowledgeError(failure)
                cards, values = self._load(
                    storage_validator=storage,
                    snapshot_path_validator=path,
                )
                self.assertEqual(cards, ())
                values["protector_factory"].assert_not_called()
                values["key_opener"].assert_not_called()

    def test_success_calls_loader_once_and_wipes_mutable_key_buffers(self) -> None:
        seed = bytes(range(32))
        material = AuthorityKeyMaterial(
            SecretBytes(b"A" * 32),
            SecretBytes(b"S" * 32),
            SecretBytes(seed),
        )
        message = b"synthetic snapshot frame"
        signature = Ed25519PrivateKey.from_private_bytes(seed).sign(message)
        card = _card()

        def loader(_path, **kwargs):
            kwargs["verification_public_key"].verify(signature, message)
            self.assertIs(kwargs["encryption_key"], material.snapshot_key)
            self.assertEqual(
                kwargs["forbidden_roots"],
                (PROJECT, Path(AUTHORITY)),
            )
            return RuntimeKnowledgeLoad((card,), "snapshot_loaded")

        loader_mock = Mock(side_effect=loader)

        def private_key_factory(value):
            self.assertIs(value, material.signing_seed)
            return Ed25519PrivateKey.from_private_bytes(value)

        cards, values = self._load(
            key_opener=Mock(return_value=material),
            snapshot_loader=loader_mock,
            private_key_factory=private_key_factory,
        )

        self.assertEqual(cards, (card,))
        values["protector_factory"].assert_called_once_with()
        values["key_opener"].assert_called_once()
        loader_mock.assert_called_once()
        self.assertEqual(bytes(material.authority_key), b"\0" * 32)
        self.assertEqual(bytes(material.snapshot_key), b"\0" * 32)
        self.assertEqual(bytes(material.signing_seed), b"\0" * 32)

    def test_loader_receives_configured_snapshot_alias_and_prevalidated_target(self) -> None:
        material = AuthorityKeyMaterial(
            SecretBytes(b"A" * 32),
            SecretBytes(b"S" * 32),
            SecretBytes(bytes(range(32))),
        )
        resolved = Path("F:/Resolved/Runtime/knowledge.pksnap")
        loader = Mock(return_value=RuntimeKnowledgeLoad((), "snapshot_loaded"))

        cards, _values = self._load(
            snapshot_path_validator=Mock(return_value=resolved),
            key_opener=Mock(return_value=material),
            snapshot_loader=loader,
        )

        self.assertEqual(cards, ())
        self.assertEqual(loader.call_args.args[0], Path(SNAPSHOT))
        self.assertEqual(loader.call_args.kwargs["prevalidated_target"], resolved)

    def test_all_loader_and_dpapi_failures_are_silent_empty_fallbacks(self) -> None:
        fixed_codes = (
            "snapshot_missing",
            "snapshot_expired",
            "snapshot_signature_invalid",
            "snapshot_decrypt_invalid",
            "snapshot_schema_invalid",
            "snapshot_clock_invalid",
        )
        for code in fixed_codes:
            with self.subTest(code=code):
                material = AuthorityKeyMaterial(
                    SecretBytes(b"A" * 32),
                    SecretBytes(b"S" * 32),
                    SecretBytes(b"K" * 32),
                )
                cards, _values = self._load(
                    key_opener=Mock(return_value=material),
                    snapshot_loader=Mock(return_value=RuntimeKnowledgeLoad((), code)),
                )
                self.assertEqual(cards, ())
                self.assertEqual(bytes(material.snapshot_key), b"\0" * 32)

        private_detail = "E:/Private/Runtime/knowledge.pksnap PRIVATE_CARD_ID"
        failures = (
            ("protector_factory", RuntimeError(private_detail)),
            ("key_opener", PrivateKnowledgeError("dpapi_unprotect_failed")),
            ("snapshot_loader", RuntimeError(private_detail)),
        )
        for dependency, failure in failures:
            with self.subTest(dependency=dependency):
                output = io.StringIO()
                replacement = Mock(side_effect=failure)
                with redirect_stdout(output), redirect_stderr(output):
                    cards, _values = self._load(**{dependency: replacement})
                self.assertEqual(cards, ())
                self.assertEqual(output.getvalue(), "")

    def test_loader_success_code_cannot_release_unverified_card_values(self) -> None:
        for loaded in (
            object(),
            RuntimeKnowledgeLoad([_card()], "snapshot_loaded"),  # type: ignore[arg-type]
            RuntimeKnowledgeLoad((object(),), "snapshot_loaded"),  # type: ignore[arg-type]
            RuntimeKnowledgeLoad((replace(_card(), generic_rule=""),), "snapshot_loaded"),
        ):
            with self.subTest(loaded=type(loaded).__name__):
                material = AuthorityKeyMaterial(
                    SecretBytes(b"A" * 32),
                    SecretBytes(b"S" * 32),
                    SecretBytes(b"K" * 32),
                )
                cards, _values = self._load(
                    key_opener=Mock(return_value=material),
                    snapshot_loader=Mock(return_value=loaded),
                )
                self.assertEqual(cards, ())

    def test_import_does_not_probe_windows_dpapi_host_state(self) -> None:
        import backend.private_knowledge.dpapi as dpapi
        import backend.private_knowledge.runtime_bootstrap as bootstrap

        with patch.object(dpapi, "_load_libraries") as libraries:
            importlib.reload(bootstrap)
        libraries.assert_not_called()


if __name__ == "__main__":
    unittest.main()
