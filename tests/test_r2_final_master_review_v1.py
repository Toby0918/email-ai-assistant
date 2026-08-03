"""Fixed terminal verifier and human-only final-review handoff for Issue #102."""

from pathlib import Path
import ast
import inspect
import os
import subprocess
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.r2_final_master_closure import (
    ClosureGate,
    ClosureGap,
    FinalMasterBindingV1,
    FinalMasterClosureStatus,
    FinalReviewStatusV1,
    R2FinalMasterReviewPackageV1,
    R2FrozenRemoteMasterV1,
    R2GlobalGateEvidenceV1,
    gate_evidence_registry,
    verify_final_master_closure_v1,
)
from backend.r2_final_master_closure._canonical import canonical_json, fingerprint
from backend.r2_final_master_closure.final_review import (
    R2FinalMasterClosurePendingV1,
    _assemble_review_package,
)
from backend.r2_final_master_closure.frozen_master import _allocate as _allocate_frozen
from backend.r2_final_master_closure.global_gate_evidence import ZERO_GATE_FIELDS
from backend.r2_final_master_closure.global_gate_registry import GateEvidenceRegistrationV1
from backend.r2_production_binding import (
    ApprovedCutoverBindingV2,
    OperatorRoleV2,
    ProductionRoleV2,
    PublicKeyRoleV2,
    reviewed_production_binding_receipt_v2,
)
from scripts import verify_r2_final_master_closure as fixed_verifier


class R2FinalMasterReviewV1Tests(unittest.TestCase):
    def test_public_verifier_is_fixed_no_argument_and_fails_closed_before_freeze(self):
        self.assertEqual(tuple(inspect.signature(verify_final_master_closure_v1).parameters), ())
        result = verify_final_master_closure_v1()
        self.assertIsInstance(result, R2FinalMasterClosurePendingV1)
        self.assertIs(
            result.status,
            FinalReviewStatusV1.BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING,
        )
        self.assertEqual(result.eligibility_receipt_count, 0)
        self.assertEqual(result.approval_count, 0)
        self.assertEqual(result.execution_authority_count, 0)

    def test_missing_reviewed_production_binding_remains_human_intervention(self):
        result = verify_final_master_closure_v1()
        self.assertIs(
            result.status,
            FinalReviewStatusV1.BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING,
        )
        self.assertEqual(result.missing_reviewed_production_binding_count, 1)
        self.assertEqual(result.missing_external_gate_evidence_count, 0)
        self.assertEqual(result.eligibility_receipt_count, 0)
        self.assertEqual(result.human_intervention_required, 1)

    def test_fourteen_valid_external_signatures_are_required_before_handoff(self):
        binding = _binding()
        frozen = _frozen(binding)
        production_binding = _production_binding(binding)
        keys = tuple(Ed25519PrivateKey.generate() for _ in range(14))
        registry = tuple(
            GateEvidenceRegistrationV1(
                item.gate, item.producer, item.review_domain,
                key.public_key().public_bytes_raw(),
            )
            for item, key in zip(gate_evidence_registry(), keys, strict=True)
        )
        with patch(
            "backend.r2_final_master_closure.global_gate_evidence.gate_evidence_registry",
            return_value=registry,
        ):
            evidence = _signed_evidence(
                binding, production_binding, registry, keys
            )
        receipt = reviewed_production_binding_receipt_v2(
            binding, production_binding
        )
        package = _assemble_review_package(frozen, receipt, evidence)
        self.assertIsInstance(package, R2FinalMasterReviewPackageV1)
        self.assertIs(package.status, FinalReviewStatusV1.AWAITING_SINGLE_HUMAN_FINAL_REVIEW)
        self.assertIs(
            package.terminal_status,
            FinalMasterClosureStatus.ELIGIBLE_FOR_SINGLE_FINAL_MASTER_REVIEW,
        )
        self.assertEqual((package.gap_proof_count, package.gate_receipt_count), (8, 14))
        self.assertEqual(package.human_review_completed, 0)
        self.assertEqual(package.approval_count, 0)
        self.assertEqual(package.execution_authority_count, 0)
        self.assertEqual(
            package.production_binding_fingerprint,
            production_binding.binding_fingerprint,
        )
        self.assertEqual(
            package.public_key_registry_fingerprint,
            production_binding.public_key_registry_fingerprint,
        )
        self.assertEqual(
            package.production_role_registry_fingerprint,
            production_binding.production_role_registry_fingerprint,
        )
        self.assertEqual(
            package.production_binding_receipt.production_binding_fingerprint,
            production_binding.binding_fingerprint,
        )

    def test_gap_proofs_partition_all_gate_receipts_by_semantic_owner(self):
        binding = _binding()
        frozen = _frozen(binding)
        production_binding = _production_binding(binding)
        keys = tuple(Ed25519PrivateKey.generate() for _ in range(14))
        registry = tuple(
            GateEvidenceRegistrationV1(
                item.gate, item.producer, item.review_domain,
                key.public_key().public_bytes_raw(),
            )
            for item, key in zip(gate_evidence_registry(), keys, strict=True)
        )
        with patch(
            "backend.r2_final_master_closure.global_gate_evidence.gate_evidence_registry",
            return_value=registry,
        ):
            evidence = _signed_evidence(
                binding, production_binding, registry, keys
            )
        receipt = reviewed_production_binding_receipt_v2(
            binding, production_binding
        )
        package = _assemble_review_package(frozen, receipt, evidence)
        receipt_by_gate = {item.gate: item for item in package.gate_receipts}
        ownership = {
            ClosureGap.TERMINAL_CONTRACT: (
                ClosureGate.FINAL_MASTER_BINDING,
                ClosureGate.CLOSURE_SURFACE_COMPLETENESS,
            ),
            ClosureGap.PRODUCTION_COMPOSITION: (ClosureGate.PRODUCTION_COMPOSITION,),
            ClosureGap.GIT_BYTE_REPRODUCIBILITY: (ClosureGate.GIT_BYTES,),
            ClosureGap.CRASH_RECOVERY: (ClosureGate.CRASH_RECOVERY,),
            ClosureGap.RETENTION_NO_DELETION: (ClosureGate.RETENTION_NO_DELETION,),
            ClosureGap.RUNBOOK_SEMANTIC_CLOSURE: (ClosureGate.RUNBOOK_SEMANTICS,),
            ClosureGap.WINDOWS_CI_PROVENANCE: (
                ClosureGate.DEPENDENCY_ACTION_PROVENANCE,
                ClosureGate.WINDOWS_NATIVE,
                ClosureGate.PORTABLE_FULL_SUITE,
            ),
            ClosureGap.GLOBAL_GATES: (
                ClosureGate.DOCUMENTATION,
                ClosureGate.MECHANICAL_ARCHITECTURE,
                ClosureGate.LEAKAGE,
                ClosureGate.MAINTENANCE_SCOPE,
            ),
        }
        owned_gates = [gate for gates in ownership.values() for gate in gates]
        self.assertEqual(len(owned_gates), len(ClosureGate))
        self.assertEqual(set(owned_gates), set(ClosureGate))
        for proof in package.gap_proofs:
            gates = ownership[proof.gap]
            expected = fingerprint(
                "r2-closure-gap-completion-evidence-v1",
                {
                    "gap": proof.gap.value,
                    "coordinator_receipt_fingerprint": (
                        package.coordinator_receipt_fingerprint
                    ),
                    "gate_receipts": [
                        {
                            "gate": gate.value,
                            "receipt_fingerprint": (
                                receipt_by_gate[gate].receipt_fingerprint
                            ),
                        }
                        for gate in gates
                    ],
                },
            )
            self.assertEqual(proof.evidence_fingerprint, expected)

    def test_review_package_rejects_wrong_or_unsigned_production_binding(self):
        binding = _binding()
        frozen = _frozen(binding)
        production_binding = _production_binding(binding)
        other = FinalMasterBindingV1.create(
            final_commit_oid="9" * 40,
            final_tree_oid="8" * 40,
            source_package_fingerprint="7" * 64,
            runbook_fingerprint="6" * 64,
            workflow_fingerprint="5" * 64,
        )
        wrong_production_binding = _production_binding(other)
        keys = tuple(Ed25519PrivateKey.generate() for _ in range(14))
        registry = tuple(
            GateEvidenceRegistrationV1(
                item.gate, item.producer, item.review_domain,
                key.public_key().public_bytes_raw(),
            )
            for item, key in zip(gate_evidence_registry(), keys, strict=True)
        )
        with patch(
            "backend.r2_final_master_closure.global_gate_evidence.gate_evidence_registry",
            return_value=registry,
        ):
            wrong_evidence = _signed_evidence(
                binding, wrong_production_binding, registry, keys
            )
            correct_evidence = _signed_evidence(
                binding, production_binding, registry, keys
            )
        with self.assertRaises(Exception):
            _assemble_review_package(
                frozen,
                reviewed_production_binding_receipt_v2(
                    other, wrong_production_binding
                ),
                correct_evidence,
            )
        with self.assertRaises(Exception):
            _assemble_review_package(
                frozen,
                reviewed_production_binding_receipt_v2(
                    binding, production_binding
                ),
                wrong_evidence,
            )

    def test_public_values_cannot_be_directly_constructed_or_self_certified(self):
        for kind in (
            R2FrozenRemoteMasterV1,
            R2GlobalGateEvidenceV1,
            R2FinalMasterReviewPackageV1,
        ):
            with self.assertRaises(TypeError):
                kind()
        self.assertFalse(hasattr(R2FrozenRemoteMasterV1, "create"))
        self.assertFalse(hasattr(R2GlobalGateEvidenceV1, "create"))
        self.assertFalse(hasattr(R2FinalMasterReviewPackageV1, "create"))

    def test_review_package_has_no_approval_execution_or_authority_api(self):
        for name in ("approve", "merge", "execute", "issue_authority", "authorize"):
            self.assertFalse(hasattr(R2FinalMasterReviewPackageV1, name))

    def test_normative_docs_keep_final_review_and_issue38_human_only(self):
        root = Path(__file__).resolve().parents[1]
        expected = {
            "docs/security/project_container_cutover_contracts.md": "AWAITING_SINGLE_HUMAN_FINAL_REVIEW",
            "docs/constraints/architecture_constraints.md": "no approve",
            "docs/constraints/linter_constraints.md": "human_review_completed",
            "docs/constraints/mechanical_rule_translation.md": "exactly eight gap proofs",
        }
        for relative, phrase in expected.items():
                self.assertIn(phrase, (root / relative).read_text(encoding="utf-8"))

    def test_fixed_verifier_bootstraps_only_stdlib_before_git_object_materialization(self):
        path = Path(fixed_verifier.__file__)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        top_imports = {
            node.module.split(".")[0]
            for node in tree.body
            if isinstance(node, ast.ImportFrom) and node.module
        }
        top_imports.update(
            alias.name.split(".")[0]
            for node in tree.body if isinstance(node, ast.Import)
            for alias in node.names
        )
        self.assertLessEqual(
            top_imports,
            {
                "hashlib", "os", "pathlib", "subprocess", "sys",
                "stat", "tempfile", "unicodedata",
            },
        )
        source = path.read_text(encoding="utf-8")
        self.assertIn('"status.showUntrackedFiles=all"', source)
        self.assertNotIn('"--untracked-files=no"', source)
        self.assertNotIn('"ls-tree", "-rz", "--full-tree"', source)
        self.assertIn('_read_git_object("commit", head)', source)
        self.assertIn('_read_git_object("tree", oid)', source)
        self.assertIn('_read_git_object("blob", child_oid)', source)
        self.assertIn("_require_current_script_bytes", source)
        self.assertIn("_require_clean_index_and_worktree", source)
        self.assertIn("_require_materialized_module_origins", source)
        self.assertIn("https://github.com/Toby0918/email-ai-assistant.git", source)
        self.assertIn("sys.flags.isolated", source)
        self.assertIn("sys.flags.safe_path", source)
        self.assertIn('name.startswith("backend.")', source)
        self.assertIn('name.startswith("scripts.")', source)

    def test_remote_observation_uses_one_fixed_public_ref_without_local_config(self):
        completed = subprocess.CompletedProcess(
            (), 0, stdout=(b"a" * 40 + b"\trefs/heads/master\n"), stderr=b""
        )
        with patch.object(fixed_verifier.subprocess, "run", return_value=completed) as run:
            self.assertEqual(fixed_verifier._fresh_remote_master(), "a" * 40)
        arguments = run.call_args.args[0]
        options = run.call_args.kwargs
        self.assertEqual(
            arguments,
            (
                "git", *fixed_verifier._GIT_OPTIONS,
                "ls-remote", "--exit-code",
                "https://github.com/Toby0918/email-ai-assistant.git",
                "refs/heads/master",
            ),
        )
        self.assertEqual(options["env"]["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(options["env"]["GIT_CONFIG_GLOBAL"], __import__("os").devnull)

    def test_local_trust_checks_precede_fresh_remote_observation(self):
        events = []
        head = "a" * 40
        descriptors = ()

        def record(name, result=None):
            def callback(*_args, **_kwargs):
                events.append(name)
                return result
            return callback

        with patch.object(
            fixed_verifier,
            "_git",
            side_effect=(head, head, head, head),
        ), patch.object(
            fixed_verifier,
            "_materialize_head",
            side_effect=record("materialize", ("b" * 40, descriptors)),
        ), patch.object(
            fixed_verifier,
            "_require_current_script_bytes",
            side_effect=record("script"),
        ), patch.object(
            fixed_verifier,
            "_require_clean_index_and_worktree",
            side_effect=record("worktree"),
        ), patch.object(
            fixed_verifier,
            "_fresh_remote_master",
            side_effect=record("remote", head),
        ), patch.object(
            fixed_verifier,
            "_verify_materialized",
            return_value=b"verified",
        ):
            self.assertEqual(
                fixed_verifier._verify_fixed_repository(), b"verified"
            )

        self.assertLess(events.index("script"), events.index("remote"))
        self.assertLess(events.index("worktree"), events.index("remote"))

    def test_all_git_commands_strip_inherited_git_state_and_disable_replacements(self):
        completed = subprocess.CompletedProcess(
            (), 0, stdout=b"a" * 40 + b"\n", stderr=b""
        )
        inherited = {
            "GIT_DIR": "attacker",
            "GIT_WORK_TREE": "attacker",
            "GIT_INDEX_FILE": "attacker",
            "GIT_OBJECT_DIRECTORY": "attacker",
            "GIT_ALTERNATE_OBJECT_DIRECTORIES": "attacker",
            "GIT_REPLACE_REF_BASE": "refs/attacker/",
            "GIT_CONFIG_PARAMETERS": "'core.fsmonitor=attacker'",
        }
        with patch.dict(os.environ, inherited, clear=False), patch.object(
            fixed_verifier.subprocess, "run", return_value=completed
        ) as run:
            self.assertEqual(fixed_verifier._git("rev-parse", "HEAD"), "a" * 40)
        arguments = run.call_args.args[0]
        environment = run.call_args.kwargs["env"]
        self.assertIn("--no-replace-objects", arguments)
        self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(environment["GIT_CONFIG_GLOBAL"], os.devnull)
        for name in inherited:
            self.assertNotIn(name, environment)

    def test_fixed_verifier_requires_exact_reviewed_production_binding_artifact(self):
        import tempfile

        binding = _binding()
        production_binding = _production_binding(binding)
        with tempfile.TemporaryDirectory() as temporary:
            common = Path(temporary)
            with patch.object(fixed_verifier, "_git_common_dir", return_value=common):
                missing = fixed_verifier._read_reviewed_production_binding(
                    binding, ApprovedCutoverBindingV2
                )
                self.assertEqual(
                    missing,
                    (False, ("BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING", 1, 0)),
                )
                directory = common / "r2-final-master-closure-v1"
                directory.mkdir()
                path = directory / "reviewed-production-binding-v2.json"
                path.write_bytes(production_binding.to_canonical_json())
                loaded = fixed_verifier._read_reviewed_production_binding(
                    binding, ApprovedCutoverBindingV2
                )
                self.assertIs(loaded[0], True)
                self.assertEqual(
                    loaded[1].binding_fingerprint,
                    production_binding.binding_fingerprint,
                )
                path.write_bytes(b"{}")
                invalid = fixed_verifier._read_reviewed_production_binding(
                    binding, ApprovedCutoverBindingV2
                )
                self.assertEqual(
                    invalid,
                    (False, ("BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING", 0, 1)),
                )

    def test_materialization_uses_exact_git_blobs_not_archive_attributes(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            target = Path(temporary) / "target"
            root.mkdir()
            target.mkdir()
            _git_for_test(root, "init")
            _git_for_test(root, "config", "user.email", "synthetic@example.test")
            _git_for_test(root, "config", "user.name", "Synthetic Tester")
            (root / ".gitattributes").write_text(
                "hidden.py export-ignore\nsubstituted.txt export-subst\n",
                encoding="utf-8",
            )
            (root / "hidden.py").write_bytes(b"EXACT_HIDDEN_BLOB\n")
            (root / "substituted.txt").write_bytes(b"$Format:%H$\n")
            _git_for_test(root, "add", ".")
            _git_for_test(root, "commit", "-m", "test: exact blobs")
            head = _git_for_test(root, "rev-parse", "HEAD").strip()
            with patch.object(fixed_verifier, "ROOT", root):
                fixed_verifier._materialize_head(head, target)
            self.assertEqual((target / "hidden.py").read_bytes(), b"EXACT_HIDDEN_BLOB\n")
            self.assertEqual((target / "substituted.txt").read_bytes(), b"$Format:%H$\n")

    def test_materialization_independently_reads_commit_tree_and_blob_objects(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            target = Path(temporary) / "target"
            root.mkdir()
            target.mkdir()
            _git_for_test(root, "init")
            _git_for_test(root, "config", "user.email", "synthetic@example.test")
            _git_for_test(root, "config", "user.name", "Synthetic Tester")
            (root / "value.txt").write_bytes(b"EXACT\n")
            _git_for_test(root, "add", ".")
            _git_for_test(root, "commit", "-m", "test: raw objects")
            head = _git_for_test(root, "rev-parse", "HEAD").strip()
            tree = _git_for_test(root, "rev-parse", "HEAD^{tree}").strip()
            read = fixed_verifier._git_bytes
            with patch.object(fixed_verifier, "ROOT", root), patch.object(
                fixed_verifier, "_git_bytes", wraps=read
            ) as git_bytes:
                fixed_verifier._materialize_head(head, target)
            calls = {item.args for item in git_bytes.call_args_list}
            self.assertIn(("cat-file", "commit", head), calls)
            self.assertIn(("cat-file", "tree", tree), calls)
            self.assertTrue(any(
                arguments[:2] == ("cat-file", "blob")
                for arguments in calls
            ))

    def test_materialization_ignores_git_replacement_objects(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            target = Path(temporary) / "target"
            root.mkdir()
            target.mkdir()
            _git_for_test(root, "init")
            _git_for_test(root, "config", "user.email", "synthetic@example.test")
            _git_for_test(root, "config", "user.name", "Synthetic Tester")
            path = root / "value.txt"
            path.write_bytes(b"ORIGINAL\n")
            _git_for_test(root, "add", ".")
            _git_for_test(root, "commit", "-m", "test: original")
            original = _git_for_test(root, "rev-parse", "HEAD").strip()
            path.write_bytes(b"REPLACEMENT\n")
            _git_for_test(root, "add", ".")
            _git_for_test(root, "commit", "-m", "test: replacement")
            replacement = _git_for_test(root, "rev-parse", "HEAD").strip()
            _git_for_test(root, "replace", original, replacement)
            with patch.object(fixed_verifier, "ROOT", root):
                fixed_verifier._materialize_head(original, target)
            self.assertEqual((target / "value.txt").read_bytes(), b"ORIGINAL\n")

    def test_hidden_index_flags_and_worktree_drift_are_rejected(self):
        import tempfile

        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary) / "source"
                target = Path(temporary) / "target"
                root.mkdir()
                target.mkdir()
                _git_for_test(root, "init")
                _git_for_test(root, "config", "user.email", "synthetic@example.test")
                _git_for_test(root, "config", "user.name", "Synthetic Tester")
                path = root / "value.txt"
                path.write_bytes(b"REVIEWED\n")
                _git_for_test(root, "add", ".")
                _git_for_test(root, "commit", "-m", "test: hidden index flag")
                head = _git_for_test(root, "rev-parse", "HEAD").strip()
                with patch.object(fixed_verifier, "ROOT", root):
                    _, descriptors = fixed_verifier._materialize_head(head, target)
                    _git_for_test(root, "update-index", flag, "value.txt")
                    path.write_bytes(b"UNREVIEWED\n")
                    with self.assertRaises(ValueError):
                        fixed_verifier._require_clean_index_and_worktree(descriptors)

    def test_ignored_residue_is_neither_enumerated_nor_read(self):
        import tempfile

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            target = Path(temporary) / "target"
            root.mkdir()
            target.mkdir()
            (root / ".gitignore").write_bytes(b".venv/\n")
            (root / "value.txt").write_bytes(b"REVIEWED\n")
            _git_for_test(root, "init")
            _git_for_test(root, "config", "user.email", "synthetic@example.test")
            _git_for_test(root, "config", "user.name", "Synthetic Tester")
            _git_for_test(root, "add", ".gitignore", "value.txt")
            _git_for_test(root, "commit", "-m", "test: ignored residue")
            head = _git_for_test(root, "rev-parse", "HEAD").strip()
            (root / ".venv").mkdir()
            (root / ".venv" / "private.bin").write_bytes(b"DO_NOT_READ")
            with patch.object(fixed_verifier, "ROOT", root):
                _, descriptors = fixed_verifier._materialize_head(head, target)
                fixed_verifier._require_clean_index_and_worktree(descriptors)
                (root / "untracked.txt").write_bytes(b"UNREVIEWED\n")
                with self.assertRaises(ValueError):
                    fixed_verifier._require_clean_index_and_worktree(descriptors)

    def test_expected_worktree_path_rejects_a_junction_before_reading(self):
        import tempfile
        from pathlib import PurePosixPath

        content = b"REVIEWED\n"
        relative = PurePosixPath("package/value.py")
        expected = {
            fixed_verifier._windows_tree_alias(relative.as_posix()): (
                relative,
                "100644",
                _blob_oid(content),
                content,
            )
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            (package / "value.py").write_bytes(content)

            def is_junction(path):
                return path.name == "package"

            with patch.object(fixed_verifier, "ROOT", root), patch.object(
                Path, "is_junction", autospec=True, side_effect=is_junction
            ):
                with self.assertRaises(ValueError):
                    fixed_verifier._require_exact_worktree(expected)

    def test_expected_worktree_path_rejects_parent_identity_drift(self):
        import tempfile
        from pathlib import PurePosixPath
        from types import SimpleNamespace

        content = b"REVIEWED\n"
        relative = PurePosixPath("package/value.py")
        expected = {
            fixed_verifier._windows_tree_alias(relative.as_posix()): (
                relative,
                "100644",
                _blob_oid(content),
                content,
            )
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            package = root / "package"
            package.mkdir()
            (package / "value.py").write_bytes(content)
            real_lstat = os.lstat
            for drifting_path in (root, package):
                with self.subTest(path=drifting_path):
                    calls = 0

                    def drifting_lstat(path):
                        nonlocal calls
                        observed = real_lstat(path)
                        if Path(path) != drifting_path:
                            return observed
                        calls += 1
                        if calls == 1:
                            return observed
                        return SimpleNamespace(
                            st_dev=observed.st_dev,
                            st_ino=observed.st_ino + 1,
                            st_mode=observed.st_mode,
                            st_size=observed.st_size,
                            st_file_attributes=getattr(
                                observed, "st_file_attributes", 0
                            ),
                        )

                    with patch.object(
                        fixed_verifier, "ROOT", root
                    ), patch.object(
                        fixed_verifier.os, "lstat", side_effect=drifting_lstat
                    ), patch.object(
                        Path, "is_symlink", autospec=True, return_value=False
                    ), patch.object(
                        Path, "is_junction", autospec=True, return_value=False
                    ):
                        with self.assertRaises(ValueError):
                            fixed_verifier._require_exact_worktree(expected)

    def test_bootstrap_script_must_match_the_verified_git_blob(self):
        import tempfile

        reviewed = b"print('reviewed')\n"
        descriptors = ((
            __import__("pathlib").PurePosixPath(
                "scripts/verify_r2_final_master_closure.py"
            ),
            "100644",
            _blob_oid(reviewed),
            reviewed,
        ),)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            script = root / "scripts" / "verify_r2_final_master_closure.py"
            script.parent.mkdir()
            script.write_bytes(reviewed)
            with patch.object(fixed_verifier, "ROOT", root), patch.object(
                fixed_verifier, "__file__", str(script)
            ):
                with patch.object(
                    Path,
                    "read_bytes",
                    autospec=True,
                    side_effect=AssertionError("unsafe direct read"),
                ):
                    fixed_verifier._require_current_script_bytes(descriptors)
                script.write_bytes(b"print('unreviewed')\n")
                with self.assertRaises(ValueError):
                    fixed_verifier._require_current_script_bytes(descriptors)

    def test_windows_aliases_are_rejected_before_materialization_writes(self):
        import tempfile

        first, second = b"FIRST\n", b"SECOND\n"
        first_oid = _blob_oid(first)
        second_oid = _blob_oid(second)
        tree_content = (
            b"100644 victim.py\0" + bytes.fromhex(first_oid)
            + b"100644 victim.py.\0" + bytes.fromhex(second_oid)
        )
        tree_oid = _git_object_oid("tree", tree_content)
        commit_content = f"tree {tree_oid}\n\nsynthetic\n".encode("ascii")
        head = _git_object_oid("commit", commit_content)

        def git_bytes(*arguments):
            return {
                ("commit", head): commit_content,
                ("tree", tree_oid): tree_content,
                ("blob", first_oid): first,
                ("blob", second_oid): second,
            }[(arguments[1], arguments[2])]

        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            with patch.object(fixed_verifier, "_git_bytes", side_effect=git_bytes):
                with self.assertRaises(ValueError):
                    fixed_verifier._materialize_head(head, target)
            self.assertEqual(tuple(target.iterdir()), ())
        for relative in (
            "stream.py:payload", "CON.py", "aux", "folder /value.py",
            "trailing./value.py", "COM1.txt", "name~1.py",
        ):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                fixed_verifier._windows_tree_alias(relative)


def _git_for_test(root, *arguments):
    result = subprocess.run(
        ("git", *arguments), cwd=root, check=True, capture_output=True
    )
    return result.stdout.decode("ascii")


def _blob_oid(content):
    return _git_object_oid("blob", content)


def _git_object_oid(kind, content):
    import hashlib

    frame = kind.encode("ascii") + b" "
    frame += str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(frame).hexdigest()


def _binding():
    return FinalMasterBindingV1.create(
        final_commit_oid="a" * 40,
        final_tree_oid="b" * 40,
        source_package_fingerprint="c" * 64,
        runbook_fingerprint="d" * 64,
        workflow_fingerprint="e" * 64,
    )


def _frozen(binding):
    body = {
        "observation_type": "R2FrozenRemoteMasterV1",
        "status": "FROZEN_REMOTE_MASTER_VERIFIED",
        "binding_fingerprint": binding.binding_fingerprint,
        "remote_ref_fingerprint": "1" * 64,
        "final_commit_oid": binding.final_commit_oid,
        "final_tree_oid": binding.final_tree_oid,
        "source_package_fingerprint": binding.source_package_fingerprint,
        "runbook_fingerprint": binding.runbook_fingerprint,
        "workflow_fingerprint": binding.workflow_fingerprint,
        "exact_match": 1,
        "historical_master_count": 0,
        "dirty_path_count": 0,
    }
    return _allocate_frozen(binding, body)


def _signed_evidence(binding, production_binding, registry, keys):
    result = []
    for index, (registration, key) in enumerate(zip(registry, keys, strict=True)):
        producer = fingerprint("r2-gate-producer-v1", {
            "producer": registration.producer.value,
            "verification_public_key_hex": registration.verification_public_key.hex(),
        })
        evidence_fingerprint = f"{index + 20:064x}"
        if registration.gate is ClosureGate.PRODUCTION_COMPOSITION:
            evidence_fingerprint = fingerprint(
                "r2-reviewed-production-composition-evidence-v2",
                {
                    "final_master_binding_fingerprint": binding.binding_fingerprint,
                    "production_binding_fingerprint": (
                        production_binding.binding_fingerprint
                    ),
                    "operator_role_registry_fingerprint": (
                        production_binding.operator_role_registry_fingerprint
                    ),
                    "command_domain_registry_fingerprint": (
                        production_binding.command_domain_registry_fingerprint
                    ),
                    "public_key_registry_fingerprint": (
                        production_binding.public_key_registry_fingerprint
                    ),
                    "production_role_registry_fingerprint": (
                        production_binding.production_role_registry_fingerprint
                    ),
                },
            )
        body = {
            "evidence_type": "R2SignedGlobalGateEvidenceV1",
            "binding_fingerprint": binding.binding_fingerprint,
            "gate": registration.gate.value,
            "producer": registration.producer.value,
            "review_domain": registration.review_domain.value,
            "evidence_fingerprint": evidence_fingerprint,
            "producer_fingerprint": producer,
            "verified": 1,
            "self_certified": 0,
            **{name: 0 for name in ZERO_GATE_FIELDS},
        }
        payload = canonical_json({
            **body, "signature_hex": key.sign(canonical_json(body)).hex()
        })
        result.append(R2GlobalGateEvidenceV1.from_signed_json(payload, binding=binding))
    return tuple(result)


def _production_binding(final_master):
    return ApprovedCutoverBindingV2.create(
        final_master_binding=final_master,
        operation_fingerprint="f" * 64,
        operator_role_fingerprints={
            role: f"{index + 30:064x}"
            for index, role in enumerate(OperatorRoleV2)
        },
        verification_public_keys={
            role: bytes([index + 1]) * 32
            for index, role in enumerate(PublicKeyRoleV2)
        },
        production_role_fingerprints={
            role: f"{index + 40:064x}"
            for index, role in enumerate(ProductionRoleV2)
        },
    )


if __name__ == "__main__":
    unittest.main()
