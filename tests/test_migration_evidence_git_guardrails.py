"""Fail-closed Git discovery tests for migration evidence."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.migration_evidence import prepare_migration_evidence_review
from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
)
from backend.migration_evidence.errors import MigrationEvidenceError
from backend.migration_evidence.git_discovery import git_output
from backend.migration_evidence.review import _review_dirty_entries
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
    run_git,
)


class MigrationEvidenceGitGuardrailTests(unittest.TestCase):
    def test_git_subprocess_uses_sanitized_environment_and_fsmonitor_off(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = create_repository(Path(temporary).resolve())
            observed: dict[str, object] = {}
            real_popen = subprocess.Popen

            def capture_popen(arguments, **kwargs):
                observed["arguments"] = arguments
                observed["environment"] = kwargs["env"]
                return real_popen(arguments, **kwargs)

            ambient = {
                "OPENAI_API_KEY": "provider-canary",
                "MAILBOX_PASSWORD": "mailbox-canary",
                "GIT_DIR": "C:/wrong/repository",
                "GIT_INDEX_FILE": "C:/wrong/index",
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "core.fsmonitor",
                "GIT_CONFIG_VALUE_0": "malicious-helper",
            }
            with mock.patch.dict(os.environ, ambient, clear=False):
                with mock.patch(
                    "backend.migration_evidence.git_runner.subprocess.Popen",
                    side_effect=capture_popen,
                ):
                    output = git_output(
                        repository,
                        ("rev-parse", "HEAD"),
                    )

            self.assertIsNotNone(output)
            environment = observed["environment"]
            for name, value in ambient.items():
                self.assertNotEqual(environment.get(name), value)
            arguments = observed["arguments"]
            self.assertEqual(arguments[0], "git")
            self.assertIn("core.fsmonitor=false", arguments)
            self.assertEqual(environment["GIT_CONFIG_NOSYSTEM"], "1")

    def test_git_output_kills_process_at_bounded_stdout_limit(
        self,
    ) -> None:
        class OversizedStdout:
            def read(self, limit):
                return b"x" * limit

            def close(self):
                return None

        class OversizedProcess:
            def __init__(self):
                self.stdout = OversizedStdout()
                self.killed = False
                self.returncode = None

            def poll(self):
                return self.returncode

            def kill(self):
                self.killed = True
                self.returncode = -9

            def wait(self, timeout=None):
                return self.returncode

        class FakeProcessTree:
            def popen_options(self):
                return {}

            def attach(self, _process):
                return None

            def terminate(self, target):
                if target is not None and target.poll() is None:
                    target.kill()

        process = OversizedProcess()
        with mock.patch(
            "backend.migration_evidence.git_runner.subprocess.Popen",
            return_value=process,
        ), mock.patch(
            "backend.migration_evidence.git_runner.ProcessTree.prepare",
            return_value=FakeProcessTree(),
        ):
            with self.assertRaises(MigrationEvidenceError):
                git_output(
                    Path("C:/synthetic"),
                    ("status", "--porcelain=v1"),
                    maximum=32,
                )

        self.assertTrue(process.killed)

    def test_git_timeout_terminates_descendant_holding_stdout(
        self,
    ) -> None:
        real_popen = subprocess.Popen
        real_timer = threading.Timer
        child_code = (
            "import subprocess,sys,time;"
            "subprocess.Popen([sys.executable,'-c',"
            "'import time;time.sleep(5)']);"
            "time.sleep(5)"
        )

        def launch_synthetic_parent(_arguments, **kwargs):
            return real_popen(
                (sys.executable, "-c", child_code),
                **kwargs,
            )

        def short_timer(_interval, function, args=(), kwargs=None):
            return real_timer(
                0.2,
                function,
                args=args,
                kwargs=kwargs or {},
            )

        started = time.monotonic()
        with mock.patch(
            "backend.migration_evidence.git_runner.subprocess.Popen",
            side_effect=launch_synthetic_parent,
        ), mock.patch(
            "backend.migration_evidence.git_runner.threading.Timer",
            side_effect=short_timer,
        ):
            with self.assertRaises(MigrationEvidenceError):
                git_output(
                    Path.cwd(),
                    ("status", "--porcelain=v1"),
                    maximum=32,
                )
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 2.5)

    def test_assume_unchanged_and_skip_worktree_are_rejected(
        self,
    ) -> None:
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                with tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary).resolve()
                    repository = create_repository(root)
                    run_git(
                        repository,
                        "update-index",
                        flag,
                        "backend/service.py",
                    )
                    (repository / "backend" / "service.py").write_text(
                        "VALUE = 'hidden dirty state'\n",
                        encoding="utf-8",
                    )
                    target = (
                        root
                        / "target"
                        / "hidden.migration-evidence.zip"
                    )
                    target.parent.mkdir()

                    with self.assertRaises(MigrationEvidenceError):
                        prepare_migration_evidence_review(
                            repository_root=repository,
                            target=target,
                            approved_dirty_paths=(),
                            reviewed_refs=("refs/heads/master",),
                            approved_worktrees=(repository,),
                            host_baseline=host_baseline(),
                        )

    def test_source_root_must_be_an_approved_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            linked = root / "linked"
            run_git(
                repository,
                "worktree",
                "add",
                "-b",
                "linked-only",
                str(linked),
            )
            target = root / "target" / "root.migration-evidence.zip"
            target.parent.mkdir()

            with self.assertRaises(MigrationEvidenceError):
                prepare_migration_evidence_review(
                    repository_root=repository,
                    target=target,
                    approved_dirty_paths=(),
                    reviewed_refs=("refs/heads/linked-only",),
                    approved_worktrees=(linked,),
                    host_baseline=host_baseline(),
                )

    def test_unmerged_status_is_rejected_even_when_not_approved(
        self,
    ) -> None:
        for status in ("AA", "AU", "DD", "DU", "UA", "UD", "UU"):
            with self.subTest(status=status):
                with self.assertRaises(MigrationEvidenceError):
                    _review_dirty_entries(
                        ((status, "backend/service.py"),),
                        frozenset(),
                    )

    def test_staged_deletion_of_symlink_head_entry_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            link = repository / "backend" / "link.py"
            link.write_text("synthetic-target.py", encoding="utf-8")
            oid = run_git(repository, "hash-object", "-w", "backend/link.py")
            run_git(
                repository,
                "update-index",
                "--add",
                "--cacheinfo",
                f"120000,{oid},backend/link.py",
            )
            run_git(repository, "commit", "-m", "add synthetic symlink")
            run_git(repository, "rm", "-f", "backend/link.py")
            target = root / "target" / "link.migration-evidence.zip"
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=("backend/link.py",),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )

            result = create_migration_evidence_package(
                review=review,
                confirmed_review_fingerprint=review.review_fingerprint,
            )

            self.assertEqual(
                result.status,
                MigrationEvidenceStatus.FAILED,
            )
            self.assertFalse(target.exists())

    def test_target_inside_source_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            target = (
                repository
                / "target"
                / "inside.migration-evidence.zip"
            )
            target.parent.mkdir()

            with self.assertRaises(MigrationEvidenceError):
                prepare_migration_evidence_review(
                    repository_root=repository,
                    target=target,
                    approved_dirty_paths=(),
                    reviewed_refs=("refs/heads/master",),
                    approved_worktrees=(repository,),
                    host_baseline=host_baseline(),
                )

    def test_target_reparse_ancestor_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            real_target = root / "real-target"
            real_target.mkdir()
            alias = root / "target-alias"
            try:
                alias.symlink_to(real_target, target_is_directory=True)
            except OSError as error:
                self.skipTest(f"directory symlink unavailable: {error}")
            target = alias / "reparse.migration-evidence.zip"

            with self.assertRaises(MigrationEvidenceError):
                prepare_migration_evidence_review(
                    repository_root=repository,
                    target=target,
                    approved_dirty_paths=(),
                    reviewed_refs=("refs/heads/master",),
                    approved_worktrees=(repository,),
                    host_baseline=host_baseline(),
                )


if __name__ == "__main__":
    unittest.main()
