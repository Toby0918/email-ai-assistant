"""Fixed public-JSON CLI adapter for Issue #105 external artifacts."""

from __future__ import annotations

import ast
import io
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.r2_final_master_closure._canonical import canonical_json
from backend.r2_production_binding import PublicKeyRoleV2
from backend.r2_external_artifacts_v1 import (
    R2ExternalArtifactError,
    R2UnsignedExternalArtifactPackageV1,
)
from scripts import prepare_r2_external_artifacts as cli
from tests.test_r2_external_artifacts_v1 import _fixture


class PrepareR2ExternalArtifactsTests(unittest.TestCase):
    def test_prepare_request_emits_canonical_unsigned_package(self):
        fixture = _fixture()
        payload = canonical_json(_prepare_request(fixture))

        result = cli._run_request_v1("prepare", payload, fixture["frozen"])

        package = R2UnsignedExternalArtifactPackageV1.from_json(
            result, frozen_master=fixture["frozen"]
        )
        self.assertEqual(package.artifact_count, 15)
        self.assertEqual(package.unsigned_gate_count, 14)
        self.assertEqual(package.signature_count, 0)
        self.assertEqual(result, package.to_canonical_json())

    def test_cli_rejects_unknown_fields_and_invalid_install_signatures(self):
        fixture = _fixture()
        request = _prepare_request(fixture)
        request["evidence_fingerprint"] = "1" * 64
        with self.assertRaises(R2ExternalArtifactError):
            cli._run_request_v1(
                "prepare", canonical_json(request), fixture["frozen"]
            )

        request = _prepare_request(fixture)
        request["reviewed_outputs"]["documentation_review"][
            "open_finding_count"
        ] = False
        with self.assertRaises(R2ExternalArtifactError):
            cli._run_request_v1(
                "prepare", canonical_json(request), fixture["frozen"]
            )

        package_json = cli._run_request_v1(
            "prepare",
            canonical_json(_prepare_request(fixture)),
            fixture["frozen"],
        )
        package = R2UnsignedExternalArtifactPackageV1.from_json(
            package_json, frozen_master=fixture["frozen"]
        )
        install_request = {
            "request_type": "R2ExternalArtifactInstallationRequestV1",
            "unsigned_package": package.to_mapping(),
            "confirmed_manifest_fingerprint": (
                package.issuance_manifest_fingerprint
            ),
            "detached_signatures": ["0" * 128] * 14,
        }
        with self.assertRaises(R2ExternalArtifactError):
            cli._run_request_v1(
                "install", canonical_json(install_request), fixture["frozen"]
            )

    def test_production_entry_has_only_two_fixed_verbs_and_no_path_or_key_option(self):
        self.assertEqual(tuple(inspect.signature(cli.main).parameters), ())
        source = Path(cli.__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        strings = {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        self.assertIn("prepare", strings)
        self.assertIn("install", strings)
        for forbidden in (
            "--path",
            "--destination",
            "--key-file",
            "--private-key",
            "M:",
            "VeraCrypt",
        ):
            self.assertNotIn(forbidden, source)

    def test_read_request_enforces_size_and_single_trailing_newline(self):
        accepted = b'{"request_type":"example"}'
        with patch.object(
            cli.sys,
            "stdin",
            SimpleNamespace(buffer=io.BytesIO(accepted + b"\n")),
        ):
            self.assertEqual(cli._read_request(), accepted)

        rejected = (
            b"x" * (cli._MAX_REQUEST_BYTES + 1),
            b"{}\n{}\n",
            b"{}",
        )
        for payload in rejected:
            with self.subTest(payload_size=len(payload)), patch.object(
                cli.sys,
                "stdin",
                SimpleNamespace(buffer=io.BytesIO(payload)),
            ), self.assertRaises(R2ExternalArtifactError):
                cli._read_request()

    def test_main_rejects_invalid_argv_before_input_or_freeze(self):
        invalid_argv = (
            ["prepare_r2_external_artifacts.py"],
            ["prepare_r2_external_artifacts.py", "unknown"],
            ["prepare_r2_external_artifacts.py", "prepare", "extra"],
        )
        for argv in invalid_argv:
            stdout = io.BytesIO()
            stderr = io.StringIO()
            with self.subTest(argv=argv), patch.object(
                cli.sys,
                "argv",
                argv,
            ), patch.object(
                cli.sys,
                "stdout",
                SimpleNamespace(buffer=stdout),
            ), patch.object(cli.sys, "stderr", stderr), patch.object(
                cli,
                "_read_request",
                side_effect=AssertionError("stdin must not be read"),
            ) as read_request, patch.object(
                cli,
                "_freeze_current_master_v1",
                side_effect=AssertionError("master must not be frozen"),
            ) as freeze:
                self.assertEqual(cli.main(), 2)

            read_request.assert_not_called()
            freeze.assert_not_called()
            self.assertEqual(
                stdout.getvalue(),
                b'{"status":"R2_EXTERNAL_ARTIFACT_INVALID"}\n',
            )
            self.assertEqual(stderr.getvalue(), "")

    def test_freeze_rechecks_local_remote_ref_after_materialization(self):
        head, moved = "1" * 40, "3" * 40
        remote = head
        with patch.object(
            cli._fixed, "_git", side_effect=(head, remote, head, moved)
        ), patch.object(
            cli._fixed, "_materialize_head", return_value=("4" * 40, ())
        ), patch.object(
            cli._fixed, "_require_current_script_bytes"
        ), patch.object(
            cli, "_require_current_adapter_bytes"
        ), patch.object(
            cli._fixed, "_require_clean_index_and_worktree"
        ), patch.object(
            cli._fixed, "_fresh_remote_master", return_value=remote
        ), patch.object(
            cli, "_frozen_from_descriptors", return_value=object()
        ), self.assertRaises(R2ExternalArtifactError):
            cli._freeze_current_master_v1()


def _prepare_request(fixture):
    inputs = fixture["review_inputs"]
    return {
        "request_type": "R2ExternalArtifactPreparationRequestV1",
        "authority_verification_public_keys": [
            {
                "role": role.value,
                "public_key_hex": fixture["authority_keys"][role].hex(),
            }
            for role in PublicKeyRoleV2
        ],
        "reviewed_outputs": {
            "closure_surface_review": inputs.closure_surface_review.to_mapping(),
            "git_byte_receipt": inputs.git_byte_receipt.to_mapping(),
            "ci_provenance_bundle": inputs.ci_provenance_bundle.to_mapping(),
            "ci_provenance_receipts": [
                item.to_mapping() for item in inputs.ci_provenance_receipts
            ],
            "runbook_receipt": inputs.runbook_receipt.to_mapping(),
            "crash_recovery_review": inputs.crash_recovery_review.to_mapping(),
            "retention_proof": inputs.retention_proof.to_mapping(),
            "documentation_review": inputs.documentation_review.to_mapping(),
            "mechanical_architecture_review": (
                inputs.mechanical_architecture_review.to_mapping()
            ),
            "leakage_review": inputs.leakage_review.to_mapping(),
            "maintenance_review": inputs.maintenance_review.to_mapping(),
        },
    }


if __name__ == "__main__":
    unittest.main()
