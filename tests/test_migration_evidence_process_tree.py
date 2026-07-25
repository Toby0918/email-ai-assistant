"""Process-tree identity tests for bounded migration-evidence Git reads."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from backend.migration_evidence.git_discovery import git_output
from backend.migration_evidence.errors import MigrationEvidenceError
from backend.migration_evidence.process_tree import ProcessTree


class MigrationEvidenceProcessTreeTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows Job Object test")
    def test_windows_descendant_cannot_run_before_job_attach(self) -> None:
        real_popen = subprocess.Popen
        with tempfile.TemporaryDirectory() as temporary:
            marker = Path(temporary) / "descendant-ran.txt"
            descendant = (
                "from pathlib import Path;"
                f"Path({str(marker)!r}).write_text("
                "'ran', encoding='utf-8')"
            )
            parent = (
                "import subprocess,sys;"
                "subprocess.run("
                f"[sys.executable,'-c',{descendant!r}],check=True)"
            )
            observed: dict[str, bool] = {}

            def launch_synthetic_parent(_arguments, **kwargs):
                process = real_popen(
                    (sys.executable, "-c", parent),
                    **kwargs,
                )
                time.sleep(0.3)
                observed["before_attach"] = marker.exists()
                return process

            with mock.patch(
                "backend.migration_evidence.git_runner.subprocess.Popen",
                side_effect=launch_synthetic_parent,
            ):
                output = git_output(
                    Path.cwd(),
                    ("status", "--porcelain=v1"),
                    maximum=32,
                )

            self.assertEqual(output, b"")
            self.assertFalse(observed["before_attach"])
            self.assertTrue(marker.exists())

    @unittest.skipUnless(os.name == "nt", "Windows Job Object test")
    def test_windows_attach_failures_reap_suspended_parent(self) -> None:
        for failed_step in ("assign", "resume"):
            with self.subTest(failed_step=failed_step):
                with tempfile.TemporaryDirectory() as temporary:
                    marker = Path(temporary) / "parent-ran.txt"
                    code = (
                        "from pathlib import Path;"
                        f"Path({str(marker)!r}).write_text("
                        "'ran', encoding='utf-8')"
                    )
                    process_tree = ProcessTree.prepare()
                    process = None
                    try:
                        process = subprocess.Popen(
                            (sys.executable, "-c", code),
                            stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            **process_tree.popen_options(),
                        )
                        patch_target = (
                            "_assign_windows_job"
                            if failed_step == "assign"
                            else "_resume_windows_process"
                        )
                        with mock.patch(
                            "backend.migration_evidence.process_tree."
                            + patch_target,
                            return_value=False,
                        ):
                            with self.assertRaises(
                                MigrationEvidenceError
                            ):
                                process_tree.attach(process)
                    finally:
                        process_tree.terminate(process)

                    self.assertIsNotNone(process)
                    self.assertIsNotNone(process.returncode)
                    self.assertFalse(marker.exists())

    @unittest.skipUnless(os.name == "nt", "Windows Job Object test")
    def test_windows_close_failure_retains_job_identity(self) -> None:
        class SyntheticProcess:
            returncode = 0

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                return self.returncode

        process_tree = ProcessTree(41038)
        with mock.patch(
            "backend.migration_evidence.process_tree._close_windows_job",
            return_value=False,
        ):
            with self.assertRaises(MigrationEvidenceError):
                process_tree.terminate(SyntheticProcess())

        self.assertEqual(process_tree._job_handle, 41038)

    def test_posix_group_is_closed_before_parent_reap(self) -> None:
        events: list[str] = []

        class SyntheticProcess:
            pid = 41035
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                events.append("reap-parent")
                self.returncode = 0
                return self.returncode

        process = SyntheticProcess()
        process_tree = ProcessTree(None)
        process_tree._process_group = process.pid

        with mock.patch(
            "backend.migration_evidence.process_tree.os.name",
            "posix",
        ), mock.patch(
            "backend.migration_evidence.process_tree."
            "_wait_posix_parent_without_reap",
            side_effect=lambda _process: events.append(
                "wait-parent-no-reap"
            ),
            create=True,
        ), mock.patch(
            "backend.migration_evidence.process_tree._kill_posix_group",
            side_effect=lambda _group: events.append("kill-group"),
        ):
            returncode = process_tree.finish(process)

        self.assertEqual(returncode, 0)
        self.assertEqual(
            events,
            [
                "wait-parent-no-reap",
                "kill-group",
                "reap-parent",
            ],
        )
        process_tree.terminate(process)
        self.assertEqual(events.count("kill-group"), 1)

    def test_posix_cleanup_error_clears_group_identity(self) -> None:
        class SyntheticProcess:
            pid = 41036
            returncode = None

            def wait(self):
                self.returncode = 0
                return self.returncode

        process = SyntheticProcess()
        process_tree = ProcessTree(None)
        process_tree._process_group = process.pid

        with mock.patch(
            "backend.migration_evidence.process_tree.os.name",
            "posix",
        ), mock.patch(
            "backend.migration_evidence.process_tree."
            "_wait_posix_parent_without_reap",
        ), mock.patch(
            "backend.migration_evidence.process_tree.os.killpg",
            side_effect=PermissionError,
            create=True,
        ), mock.patch(
            "backend.migration_evidence.process_tree.signal.SIGKILL",
            9,
            create=True,
        ):
            with self.assertRaises(MigrationEvidenceError):
                process_tree.finish(process)

        self.assertIsNone(process_tree._process_group)

    def test_posix_pre_attach_cleanup_uses_reserved_parent_pid(self) -> None:
        killed_groups: list[int] = []

        class SyntheticProcess:
            pid = 41037
            returncode = None

            def poll(self):
                return self.returncode

            def kill(self):
                self.returncode = -9

            def wait(self, timeout=None):
                return self.returncode

        process = SyntheticProcess()
        process_tree = ProcessTree(None)

        with mock.patch(
            "backend.migration_evidence.process_tree.os.name",
            "posix",
        ), mock.patch(
            "backend.migration_evidence.process_tree._kill_posix_group",
            side_effect=killed_groups.append,
        ):
            process_tree.terminate(process)
            process_tree.terminate(process)

        self.assertEqual(killed_groups, [process.pid])


if __name__ == "__main__":
    unittest.main()
