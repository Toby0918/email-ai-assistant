"""Architecture and capability guards for Issue #105 public issuance."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest

import backend.r2_external_artifacts_v1 as artifacts
from backend.r2_external_artifacts_v1 import (
    install_signed_external_artifacts_v1,
    prepare_unsigned_external_artifacts_v1,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_external_artifacts_v1"


class R2ExternalArtifactsV1ArchitectureTests(unittest.TestCase):
    def test_package_is_one_five_file_deep_module_with_small_public_interface(self):
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "review_inputs.py",
                "derivation.py",
                "unsigned_package.py",
                "installer.py",
            },
        )
        self.assertEqual(
            set(artifacts.__all__),
            {
                "R2ExternalArtifactError",
                "R2ExternalArtifactInstallResultV1",
                "R2ExternalArtifactReviewInputsV1",
                "R2GateSourceReviewV1",
                "R2UnsignedExternalArtifactPackageV1",
                "install_signed_external_artifacts_v1",
                "prepare_unsigned_external_artifacts_v1",
            },
        )
        for path in PACKAGE.glob("*.py"):
            lines = path.read_text(encoding="utf-8").splitlines()
            tree = ast.parse("\n".join(lines))
            with self.subTest(path=path.name):
                self.assertLessEqual(len(lines), 300)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        self.assertLessEqual(node.end_lineno - node.lineno + 1, 50)

    def test_public_seams_accept_no_path_key_file_or_arbitrary_fingerprint(self):
        self.assertEqual(
            tuple(inspect.signature(prepare_unsigned_external_artifacts_v1).parameters),
            (
                "frozen_master",
                "authority_verification_public_keys",
                "review_inputs",
            ),
        )
        self.assertEqual(
            tuple(inspect.signature(install_signed_external_artifacts_v1).parameters),
            (
                "unsigned_package",
                "detached_signatures",
                "confirmed_manifest_fingerprint",
            ),
        )
        forbidden = {
            "path", "root", "destination", "filename", "private_key",
            "key_file", "evidence_fingerprint", "production_role_fingerprint",
        }
        for operation in (
            prepare_unsigned_external_artifacts_v1,
            install_signed_external_artifacts_v1,
        ):
            self.assertTrue(
                set(inspect.signature(operation).parameters).isdisjoint(forbidden)
            )

    def test_production_sources_have_no_private_key_signing_or_deletion_capability(self):
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        for forbidden in (
            "Ed25519PrivateKey",
            "private_bytes",
            ".sign(",
            ".generate(",
            "os.remove(",
            "os.unlink(",
            "shutil.rmtree(",
            "os.replace(",
            ".replace(",
            "VeraCrypt",
            "M:\\",
            "clipboard",
            "key_file",
            "credential",
        ):
            self.assertNotIn(forbidden, source)
        installer = (PACKAGE / "installer.py").read_text(encoding="utf-8")
        self.assertIn("R2GlobalGateEvidenceV1.from_signed_json", installer)
        self.assertIn("R2GlobalGateCoordinatorV1.create", installer)
        self.assertIn("SetFileInformationByHandle", installer)
        self.assertIn("OpenFileById", installer)
        self.assertIn("_FILE_FLAG_OPEN_REQUIRING_OPLOCK", installer)
        self.assertIn("_FILE_FLAG_OPEN_REPARSE_POINT", installer)
        self.assertIn("_FSCTL_REQUEST_OPLOCK", installer)
        self.assertIn("_OPLOCK_LEVEL_READ", installer)
        self.assertIn("_OPLOCK_LEVEL_RWH", installer)
        self.assertIn("SetKernelObjectSecurity", installer)
        self.assertIn("D:P(A;;GRGX;;;WD)", installer)
        self.assertIn("GetFileInformationByHandleEx", installer)
        self.assertIn("_FILE_ID_INFO", installer)
        self.assertIn("_FILE_STANDARD_INFO", installer)
        self.assertIn("_FILE_STREAM_INFO", installer)
        self.assertIn('"::$DATA"', installer)
        self.assertIn("CancelIoEx", installer)
        self.assertNotIn("import threading", installer)
        self.assertNotIn("threading.Thread", installer)
        self.assertNotIn("CancelSynchronousIo", installer)
        self.assertNotIn("MoveFileExW", installer)
        self.assertIn("renameat2", installer)
        self.assertNotIn("os.rename(", installer)

    def test_only_fixed_script_allocates_frozen_master_and_reaches_git(self):
        backend_source = "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        script = (
            ROOT / "scripts" / "prepare_r2_external_artifacts.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_allocate_frozen", backend_source)
        self.assertNotIn("_materialize_head", backend_source)
        self.assertIn("_allocate_frozen", script)
        self.assertIn("_materialize_head", script)
        self.assertIn("_fresh_remote_master", script)
        self.assertNotIn("argparse", script)
        for option in ("--path", "--destination", "--key-file", "--private-key"):
            self.assertNotIn(option, script)

    def test_new_package_has_no_normal_runtime_or_protected_surface_consumer(self):
        allowed = {
            "scripts/generate_project_status.py",
            "scripts/prepare_r2_external_artifacts.py",
            "tests/test_architecture_constraints.py",
            "tests/test_generate_project_status.py",
            "tests/test_r2_external_artifacts_v1.py",
            "tests/test_r2_external_artifacts_v1_architecture.py",
            "tests/test_r2_retention_ledger_v2_architecture.py",
            "tests/test_prepare_r2_external_artifacts.py",
            "tests/test_static_linter_constraints.py",
        }
        consumers = set()
        for root_name in ("backend", "frontend", "scripts", "tests"):
            for path in (ROOT / root_name).rglob("*"):
                if path.suffix not in {".py", ".js"} or PACKAGE in path.parents:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
                if "r2_external_artifacts_v1" in text:
                    consumers.add(path.relative_to(ROOT).as_posix())
        self.assertEqual(consumers, allowed)


if __name__ == "__main__":
    unittest.main()
