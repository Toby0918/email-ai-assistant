"""Physical and capability guards for the Issue #110 closure module."""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest

import backend.r2_solo_maintainer_closure as closure


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "r2_solo_maintainer_closure"


class SoloMaintainerClosureArchitectureTests(unittest.TestCase):
    def test_package_and_public_surface_are_exact(self) -> None:
        self.assertEqual(
            {path.name for path in PACKAGE.glob("*.py")},
            {
                "__init__.py",
                "_canonical.py",
                "contracts.py",
                "evidence.py",
                "hosted_evidence.py",
                "github_guardrail.py",
                "local_evidence.py",
                "repository.py",
                "storage.py",
                "closure.py",
            },
        )
        self.assertEqual(
            set(closure.__all__),
            {
                "ClosureErrorCode",
                "FinalMasterBindingV1",
                "SoloMaintainerAttestationReceiptV1",
                "SoloMaintainerClosure",
                "SoloMaintainerClosureCandidateV1",
                "SoloMaintainerClosureError",
                "SoloMaintainerClosureManifestV1",
            },
        )
        self.assertEqual(tuple(inspect.signature(closure.SoloMaintainerClosure).parameters), ())
        public_methods = {
            name
            for name, value in inspect.getmembers(
                closure.SoloMaintainerClosure, inspect.isfunction
            )
            if not name.startswith("_")
        }
        self.assertEqual(public_methods, {"prepare", "confirm"})
        self.assertEqual(
            tuple(inspect.signature(closure.SoloMaintainerClosure.prepare).parameters),
            ("self",),
        )
        self.assertEqual(
            tuple(inspect.signature(closure.SoloMaintainerClosure.confirm).parameters),
            ("self", "exact_manifest_fingerprint", "exact_acknowledgement"),
        )

    def test_package_has_no_legacy_signer_or_arbitrary_target_surface(self) -> None:
        source = "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
        )
        for forbidden in (
            "backend.r2_final_master_closure",
            "backend.r2_external_artifacts_v1",
            "R2GlobalGateEvidenceV1",
            "Ed25519PrivateKey",
            "verification_public_keys",
            "signature_hex",
            "getenv(",
            "clipboard",
            "unlink(",
            "rmtree(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        legacy = "r2-final-master-closure-v1"
        self.assertNotIn(legacy, "\n".join(
            path.read_text(encoding="utf-8") for path in PACKAGE.glob("*.py")
            if path.name != "storage.py"
        ))
        self.assertIn(legacy, (PACKAGE / "storage.py").read_text(encoding="utf-8"))

    def test_network_and_publication_capabilities_are_physically_narrow(self) -> None:
        imports: dict[str, set[str]] = {}
        for path in PACKAGE.glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            imports[path.name] = {
                node.module.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom) and node.module
            } | {
                alias.name.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
        for name, roots in imports.items():
            with self.subTest(path=name):
                if roots & {"urllib", "socket"}:
                    self.assertEqual(name, "repository.py")
                if roots & {"subprocess"}:
                    self.assertIn(name, {"repository.py", "github_guardrail.py"})
                if roots & {"ctypes", "os", "stat"}:
                    self.assertIn(
                        name,
                        {"repository.py", "storage.py", "closure.py", "github_guardrail.py"},
                    )
        repository = (PACKAGE / "repository.py").read_text(encoding="utf-8")
        self.assertIn("https://api.github.com", repository)
        self.assertIn("Toby0918/email-ai-assistant", repository)
        self.assertNotIn("/rulesets", repository)
        self.assertNotIn("/branches/master/protection", repository)
        for forbidden in ("Authorization", "api.github.com/" + "{", "requests"):
            self.assertNotIn(forbidden, repository)

    def test_authenticated_guardrail_reader_is_fixed_get_only_and_token_free(self) -> None:
        source = (PACKAGE / "github_guardrail.py").read_text(encoding="utf-8")
        for marker in (
            r'C:\Program Files\GitHub CLI\gh.exe',
            '"Toby0918"',
            '"github.com"',
            '"auth", "status", "--active"',
            '"--method", "GET"',
            '"--include"',
            '"GH_PROMPT_DISABLED": "1"',
            '"GH_NO_UPDATE_NOTIFIER": "1"',
            '"GH_NO_EXTENSION_UPDATE_NOTIFIER": "1"',
            '"GH_TELEMETRY": "0"',
            '"DO_NOT_TRACK": "1"',
            "stdin=subprocess.DEVNULL",
            "stderr=subprocess.PIPE",
            "shell=False",
            "required_reviewers",
            "require_extra_approval_for_unattributed_changes",
            "allow_classic_missing",
            "_CLASSIC_MISSING_STDERR",
            "detail_id.isascii()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, source)
        for forbidden in (
            '"POST"', '"PUT"', '"PATCH"', '"DELETE"',
            '"auth", "token"', "Authorization", "GH_TOKEN", "GITHUB_TOKEN",
            "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_CONFIG_DIR",
            "GH_HOST", "GH_REPO", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "os.environ.copy", "dict(os.environ)", "urllib", "socket", "shell=True",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_backend_files_and_functions_stay_within_mechanical_limits(self) -> None:
        for path in PACKAGE.glob("*.py"):
            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertLessEqual(len(lines), 300, path.name)
            tree = ast.parse("\n".join(lines), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    self.assertLessEqual(
                        node.end_lineno - node.lineno + 1,
                        50,
                        f"{path.name}:{node.name}",
                    )

    def test_windows_publication_guards_default_streams_and_directory_streams(self) -> None:
        source = (PACKAGE / "storage.py").read_text(encoding="utf-8")
        self.assertIn("_windows_streams", source)
        self.assertIn('(("::$DATA", len(payload)),)', source)
        self.assertIn("_windows_streams(directory) != ()", source)
        repository = (PACKAGE / "repository.py").read_text(encoding="utf-8")
        self.assertIn('"fsck", "--strict", "--no-dangling", "--no-reflogs"', repository)

    def test_prepare_and_verifier_git_readers_disable_optional_locks(self) -> None:
        sources = (
            (PACKAGE / "repository.py").read_text(encoding="utf-8"),
            (ROOT / "scripts" / "verify_r2_final_master_closure.py").read_text(
                encoding="utf-8"
            ),
        )
        for source in sources:
            with self.subTest(source=source[:40]):
                self.assertIn('"GIT_OPTIONAL_LOCKS": "0"', source)

    def test_private_local_evidence_adds_only_the_approved_domain(self) -> None:
        tree = ast.parse((PACKAGE / "local_evidence.py").read_text(encoding="utf-8"))
        domains = {
            node.value for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node.value.startswith("r2-")
        }
        self.assertEqual(domains, {"r2-local-source-proof-v1"})
        self.assertNotIn("LocalSourceProofV1", closure.__all__)

    def test_publication_revalidates_inside_commit_and_rename_is_terminal(self) -> None:
        source = (PACKAGE / "storage.py").read_text(encoding="utf-8")
        self.assertIn("before_commit(*payloads)\n        _release_file_guards", source)
        self.assertIn("_release_file_guards(guards, close)\n        _require_exact", source)
        self.assertIn("parent_acl = _open_parent_guard(source, guards, close)", source)
        self.assertLess(
            source.index("before_commit(*payloads)"),
            source.index("parent_acl = _open_parent_guard(source, guards, close)"),
        )
        self.assertIn("_require_parent_guard(guards[0], parent_acl)\n        if rename(", source)
        self.assertIn("_settle_oplocks(guards[:2])", source)
        self.assertNotIn("_require_parent_guard(guards[0], source", source)
        self.assertIn(
            "_publication_conflict_names(_windows_names(parent), source.name)",
            source,
        )
        self.assertLess(
            source.index("guards[0] = (parent, *_request_oplock"),
            source.index(
                "_publication_conflict_names(_windows_names(parent), source.name)"
            ),
        )
        self.assertNotIn("_publication_conflict(common, source.name)", source)
        self.assertNotIn("_require_exact(target", source)
        self.assertNotIn("_flush_directory(common)", source)
        self.assertNotIn("renameat2", source)
        self.assertIn('os.name != "nt"', source[:source.index("_git_common_dir()")])


if __name__ == "__main__":
    unittest.main()
