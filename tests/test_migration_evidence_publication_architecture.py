"""Mechanical composition and capability guards for Issue #54."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.test_architecture_constraints import (
    parse_hard_link_references,
    parse_name_bindings,
)


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "backend" / "migration_evidence_publication"
PACKAGE_MODULE = "backend.migration_evidence_publication"
EXPECTED_FILES = {
    "__init__.py",
    "canonical.py",
    "contracts_bridge.py",
    "creator_bridge.py",
    "errors.py",
    "host_baseline_bridge.py",
    "operator_entry.py",
    "package_observation.py",
    "profile_binding.py",
    "profile_git_binding.py",
    "publication.py",
    "publication_receipts.py",
    "published_scope.py",
    "receipt_set.py",
    "receipts.py",
    "review.py",
    "review_bridge.py",
    "selection.py",
    "selection_state.py",
    "synthetic_scope.py",
    "verification_composition.py",
}
EXPECTED_EXPORTS = {
    "MigrationEvidenceCreatedReceiptV1": (
        ".publication_receipts",
        "MigrationEvidenceCreatedReceiptV1",
    ),
    "MigrationEvidencePackageCountsV1": (
        ".publication_receipts",
        "MigrationEvidencePackageCountsV1",
    ),
    "MigrationEvidencePublicationError": (
        ".errors",
        "MigrationEvidencePublicationError",
    ),
    "MigrationEvidenceReceiptSetV1": (
        ".receipt_set",
        "MigrationEvidenceReceiptSetV1",
    ),
    "MigrationEvidenceReviewCountsV1": (
        ".receipts",
        "MigrationEvidenceReviewCountsV1",
    ),
    "MigrationEvidenceReviewReceiptV1": (
        ".receipts",
        "MigrationEvidenceReviewReceiptV1",
    ),
    "MigrationEvidenceVerifiedReceiptV1": (
        ".publication_receipts",
        "MigrationEvidenceVerifiedReceiptV1",
    ),
    "ProfileBoundEvidenceSelectionV1": (
        ".selection",
        "ProfileBoundEvidenceSelectionV1",
    ),
    "publish_reviewed_migration_evidence": (
        ".publication",
        "publish_reviewed_migration_evidence",
    ),
    "require_matching_migration_evidence_receipts": (
        ".receipt_set",
        "require_matching_migration_evidence_receipts",
    ),
    "review_profile_bound_migration_evidence": (
        ".review",
        "review_profile_bound_migration_evidence",
    ),
    "verify_published_migration_evidence": (
        ".verification_composition",
        "verify_published_migration_evidence",
    ),
}
PASSTHROUGH_ENV_KEYS = {
    "COMSPEC",
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "SystemRoot",
    "TEMP",
    "TMP",
    "TMPDIR",
    "WINDIR",
}


def _paths() -> tuple[Path, ...]:
    return tuple(sorted(PACKAGE.glob("*.py")))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _modules(path: Path) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            result.add("." * node.level + (node.module or ""))
    return result


def _calls(path: Path) -> set[str]:
    result: set[str] = set()
    for node in ast.walk(_tree(path)):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            result.add(node.func.id)
        elif isinstance(node.func, ast.Attribute):
            result.add(node.func.attr)
    return result


def _literal_assignment(path: Path, name: str) -> object:
    matches = [
        node.value
        for node in _tree(path).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in node.targets
        )
    ]
    if len(matches) != 1:
        raise AssertionError(name)
    return ast.literal_eval(matches[0])


def _runtime_probe(access: str, forbidden: tuple[str, ...]) -> str:
    code = (
        "import sys;"
        "import backend.migration_evidence_publication as package;"
        f"{access + ';' if access else ''}"
        f"forbidden={forbidden!r};"
        "loaded={name for name in sys.modules "
        "if any(name==item or name.startswith(item+'.') "
        "for item in forbidden)};"
        "sys.stdout.write('isolated' if not loaded else 'loaded')"
    )
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in PASSTHROUGH_ENV_KEYS
    }
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    completed = subprocess.run(
        (sys.executable, "-B", "-c", code),
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=10,
        shell=False,
    )
    if completed.returncode != 0 or completed.stderr:
        return "failed"
    return completed.stdout


def _consumes_publication(path: Path) -> bool:
    source = path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix == ".py":
        return any(
            module == PACKAGE_MODULE
            or module.startswith(PACKAGE_MODULE + ".")
            for module in _modules(path)
        )
    return "migration_evidence_publication" in source


class MigrationEvidencePublicationArchitectureTests(unittest.TestCase):
    def test_exact_files_and_lazy_public_seam(self) -> None:
        self.assertEqual({path.name for path in _paths()}, EXPECTED_FILES)
        root = PACKAGE / "__init__.py"
        self.assertEqual(
            _modules(root),
            {
                module
                for module, _attribute in EXPECTED_EXPORTS.values()
            },
        )
        tree = ast.parse(root.read_text(encoding="utf-8"))
        loader_assignment = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "_LOADERS"
                for target in node.targets
            )
        )
        self.assertIsInstance(loader_assignment.value, ast.Dict)
        exports = {
            key.value
            for key in loader_assignment.value.keys
            if isinstance(key, ast.Constant)
        }
        self.assertEqual(exports, set(EXPECTED_EXPORTS))
        self.assertTrue(
            all(
                isinstance(value, ast.Name)
                for value in loader_assignment.value.values
            )
        )
        self.assertEqual(
            set(_literal_assignment(root, "__all__")),
            set(EXPECTED_EXPORTS),
        )
        internal_modules = tuple(
            f"{PACKAGE_MODULE}.{Path(name).stem}"
            for name in EXPECTED_FILES
            if name != "__init__.py"
        )
        self.assertEqual(
            _runtime_probe(
                "",
                (
                    "backend.migration_evidence",
                    "backend.migration_evidence_verifier",
                    *internal_modules,
                ),
            ),
            "isolated",
        )

    def test_creator_import_does_not_load_or_import_verifier(self) -> None:
        creator_paths = {
            PACKAGE / "creator_bridge.py",
            PACKAGE / "package_observation.py",
            PACKAGE / "publication.py",
        }
        for path in creator_paths:
            with self.subTest(path=path.name):
                modules = _modules(path)
                self.assertNotIn(
                    "backend.migration_evidence_verifier",
                    modules,
                )
                self.assertNotIn(".verification_composition", modules)
                self.assertNotIn(
                    "verify_package_in_separate_process",
                    _calls(path),
                )
        self.assertEqual(
            _runtime_probe(
                "package.publish_reviewed_migration_evidence",
                (
                    "backend.migration_evidence_verifier",
                    f"{PACKAGE_MODULE}.verification_composition",
                ),
            ),
            "isolated",
        )

    def test_synthetic_scope_owns_exact_parent_anchor_capability(
        self,
    ) -> None:
        scope = PACKAGE / "synthetic_scope.py"
        all_references = tuple(
            (path.name, target, line, direct)
            for path in _paths()
            for target, line, direct in parse_hard_link_references(
                path
            )
        )
        benign_dynamic_getters = tuple(
            (name, target, direct)
            for name, target, _line, direct in all_references
            if target == "getattr(state, <dynamic>)" and not direct
        )
        self.assertEqual(
            benign_dynamic_getters,
            (
                (
                    "publication_receipts.py",
                    "getattr(state, <dynamic>)",
                    False,
                ),
                (
                    "receipt_set.py",
                    "getattr(state, <dynamic>)",
                    False,
                ),
            ),
        )
        link_calls = [
            node
            for node in ast.walk(_tree(scope))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "os"
            and node.func.attr == "link"
        ]
        self.assertEqual(len(link_calls), 1)
        actual_link_references = tuple(
            reference
            for reference in all_references
            if not (
                reference[1] == "getattr(state, <dynamic>)"
                and not reference[3]
            )
        )
        self.assertEqual(
            actual_link_references,
            (
                (
                    "synthetic_scope.py",
                    "os.link",
                    link_calls[0].lineno,
                    True,
                ),
            ),
        )
        bindings = parse_name_bindings(scope)
        self.assertEqual(
            tuple(
                (name, kind)
                for name, kinds in sorted(bindings.items())
                for kind in kinds
                if kind.startswith(("import:os:", "from:0:os:"))
            ),
            (("os", "import:os:"),),
        )
        self.assertEqual(
            tuple(ast.unparse(value) for value in link_calls[0].args),
            ("marker", "anchor"),
        )
        self.assertEqual(
            {
                keyword.arg: ast.unparse(keyword.value)
                for keyword in link_calls[0].keywords
            },
            {"follow_symlinks": "False"},
        )
        source = scope.read_text(encoding="utf-8")
        self.assertIn(
            '".issue-54-target-parent-anchor"',
            source,
        )
        self.assertIn("marker_metadata.st_nlink != 2", source)
        self.assertIn("anchor_metadata.st_nlink != 2", source)

    def test_verification_composition_is_read_only_and_creator_free(
        self,
    ) -> None:
        path = PACKAGE / "verification_composition.py"
        modules = _modules(path)
        self.assertEqual(
            {item for item in modules if item.startswith("backend.")},
            {"backend.migration_evidence_verifier"},
        )
        self.assertEqual(
            {item for item in modules if item.startswith(".")},
            {
                ".canonical",
                ".contracts_bridge",
                ".errors",
                ".publication_receipts",
                ".published_scope",
            },
        )
        forbidden_calls = {
            "create_migration_evidence_package",
            "mkdir",
            "observe_created_package",
            "publish_reviewed_migration_evidence",
            "remove",
            "rename",
            "replace",
            "rmtree",
            "touch",
            "unlink",
            "write_bytes",
            "write_text",
        }
        self.assertTrue(_calls(path).isdisjoint(forbidden_calls))
        self.assertEqual(
            _runtime_probe(
                "package.verify_published_migration_evidence",
                (
                    f"{PACKAGE_MODULE}.creator_bridge",
                    f"{PACKAGE_MODULE}.publication",
                    f"{PACKAGE_MODULE}.review_bridge",
                    "backend.migration_evidence.package",
                    "backend.migration_evidence.publication",
                ),
            ),
            "isolated",
        )

    def test_private_published_scope_has_only_handoff_consumers(
        self,
    ) -> None:
        consumers: dict[str, set[str]] = {}
        for path in _paths():
            for node in ast.walk(_tree(path)):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.level == 1
                    and node.module == "published_scope"
                ):
                    for alias in node.names:
                        consumers.setdefault(alias.name, set()).add(path.name)
        self.assertEqual(
            consumers,
            {
                "_claim_published_target": {
                    "verification_composition.py",
                },
                "_register_published_target": {"publication.py"},
            },
        )
        for marker, expected in consumers.items():
            text_consumers = {
                path.name
                for path in _paths()
                if path.name != "published_scope.py"
                and marker in path.read_text(encoding="utf-8")
            }
            self.assertEqual(text_consumers, expected, marker)
        self.assertTrue(
            set(EXPECTED_EXPORTS).isdisjoint(consumers)
        )

    def test_no_real_operator_consumer_cli_or_runtime(self) -> None:
        candidates = [
            path
            for path in (ROOT / "backend").rglob("*.py")
            if PACKAGE.resolve() not in path.resolve().parents
        ]
        candidates.extend(
            path
            for path in (ROOT / "scripts").rglob("*")
            if path.is_file()
            and path.suffix in {".bat", ".cmd", ".ps1", ".py", ".sh"}
        )
        candidates.extend(
            path
            for path in (ROOT / "frontend").rglob("*")
            if path.is_file()
        )
        workflows = ROOT / ".github" / "workflows"
        if workflows.exists():
            candidates.extend(
                path
                for path in workflows.rglob("*")
                if path.is_file()
            )
        candidates.extend(
            path
            for path in ROOT.iterdir()
            if path.is_file()
            and path.suffix in {".json", ".py", ".toml", ".yaml", ".yml"}
        )
        status_generator = (
            ROOT / "scripts" / "generate_project_status.py"
        ).resolve()
        consumers = {
            path.relative_to(ROOT).as_posix()
            for path in candidates
            if (
                any(
                    module == PACKAGE_MODULE
                    or module.startswith(PACKAGE_MODULE + ".")
                    for module in _modules(path)
                )
                if path.resolve() == status_generator
                else _consumes_publication(path)
            )
        }
        self.assertEqual(consumers, set())
        self.assertNotIn("__main__.py", EXPECTED_FILES)
        operator = PACKAGE / "operator_entry.py"
        self.assertEqual(
            _modules(operator),
            {"__future__", ".contracts_bridge", "dataclasses", "enum"},
        )
        self.assertTrue(
            _calls(operator).isdisjoint(
                {
                    "publish_reviewed_migration_evidence",
                    "review_profile_bound_migration_evidence",
                    "verify_published_migration_evidence",
                }
            )
        )
        self.assertNotIn(
            ".operator_entry",
            {module for module, _attribute in EXPECTED_EXPORTS.values()},
        )


if __name__ == "__main__":
    unittest.main()
