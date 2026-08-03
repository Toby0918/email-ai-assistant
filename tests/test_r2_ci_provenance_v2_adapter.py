"""Fixed Git-object adapter and workflow wiring tests for Issue #100."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from backend.r2_ci_provenance_v2 import R2GitObjectEntryV2
from scripts.r2_ci_provenance_support import read_git_object_source_package_v2


ROOT = Path(__file__).resolve().parents[1]


class R2CiProvenanceV2AdapterTests(unittest.TestCase):
    def test_adapter_reads_committed_git_objects_not_checkout_or_untracked_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            _git(root, "init")
            _git(root, "config", "user.email", "synthetic@example.test")
            _git(root, "config", "user.name", "Synthetic Tester")
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "agent_guardrails.yml").write_text(_workflow("ubuntu-24.04"))
            (workflow / "cleanup_agent.yml").write_text(_workflow("ubuntu-24.04"))
            (workflow / "r2_provenance.yml").write_text(
                _workflow("windows-2022", provenance=True)
            )
            for name in ("requirements-ci-linux.lock", "requirements-ci-windows.lock"):
                (root / name).write_bytes((ROOT / name).read_bytes())
            runbook = root / "docs" / "operations" / "r2_final_operator_runbook.md"
            runbook.parent.mkdir(parents=True)
            runbook.write_bytes(b"committed runbook\n")
            tracked = root / "tracked.txt"
            tracked.write_bytes(b"committed bytes\n")
            _git(root, "add", ".")
            _git(root, "commit", "-m", "test: synthetic source")

            tracked.write_bytes(b"dirty checkout bytes\n")
            (root / "private.pkeval").write_bytes(b"must not be read")
            package, lock = read_git_object_source_package_v2(root)

            committed_sha = hashlib.sha256(b"committed bytes\n").hexdigest()
            self.assertTrue(
                any(
                    type(item) is R2GitObjectEntryV2
                    and item.byte_sha256 == committed_sha
                    for item in package.entries
                )
            )
            self.assertFalse(
                any(
                    item.byte_sha256
                    == hashlib.sha256(b"dirty checkout bytes\n").hexdigest()
                    for item in package.entries
                )
            )
            self.assertEqual(package.private_content_reads, 0)
            self.assertEqual(package.workflow_lock_fingerprint, lock.lock_fingerprint)
            self.assertEqual(
                package.runbook_fingerprint,
                hashlib.sha256(
                    b"r2-operator-runbook-document-v2\0committed runbook\n"
                ).hexdigest(),
            )

    def test_committed_workflows_are_pinned_and_have_independent_provenance_jobs(self):
        workflows = tuple((ROOT / ".github" / "workflows").glob("*.yml"))
        text = "\n".join(item.read_text(encoding="utf-8") for item in workflows)
        self.assertNotIn("-latest", text)
        self.assertNotIn("continue-on-error: true", text)
        self.assertNotIn("not found; skipping", text)
        self.assertNotIn("if [ -f", text)
        self.assertRegex(text, r"actions/checkout@[0-9a-f]{40}")
        self.assertRegex(text, r"actions/setup-python@[0-9a-f]{40}")
        provenance = (ROOT / ".github" / "workflows" / "r2_provenance.yml").read_text()
        for job in (
            "portable-provenance:",
            "windows-native-provenance:",
            "windows-independent-provenance:",
            "provenance-reconciliation:",
        ):
            self.assertIn(job, provenance)
        self.assertIn("scripts/verify_r2_ci_provenance.py", provenance)
        self.assertIn("scripts/reconcile_r2_ci_provenance.py", provenance)
        self.assertEqual(provenance.count("--require-hashes"), 3)


def _workflow(runner: str, *, provenance: bool = False) -> str:
    return (
        "jobs:\n"
        "  gate:\n"
        f"    runs-on: {runner}\n"
        "    steps:\n"
        f"      - uses: actions/checkout@{'a' * 40}\n"
        + (
            "      - run: pip install --only-binary=:all: --require-hashes -r requirements-ci-linux.lock\n"
            "      - run: pip install --only-binary=:all: --require-hashes -r requirements-ci-windows.lock\n"
            "      - run: pip install --only-binary=:all: --require-hashes -r requirements-ci-windows.lock\n"
            if provenance else ""
        )
    )


def _git(root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments], cwd=root, check=True, capture_output=True
    )


if __name__ == "__main__":
    unittest.main()
