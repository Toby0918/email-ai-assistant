from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)
from backend.cutover_repository_transaction.git_runner import (
    _bounded_process,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.cutover_repository_transaction.transaction import (
    run_forward_synthetic_transaction,
)
from backend.cutover_repository_transaction.transaction_types import (
    SyntheticFailureSelectorV1,
)
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    build_synthetic_repository_scenario,
    profile_for_review,
    run_fixture_git,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class RepositoryTransactionWindowsScopeTests(unittest.TestCase):
    def test_git_runner_rejects_output_overflow_and_terminates_tree(self):
        class FakeTree:
            def __init__(self):
                self.terminated = 0

            def popen_options(self):
                return {}

            def attach(self, _process):
                return None

            def finish(self, _process):
                return 0

            def terminate(self, _process):
                self.terminated += 1

        tree = FakeTree()
        process = SimpleNamespace(
            stdout=io.BytesIO(b"x" * 1_000_001),
            wait=lambda timeout: 0,
        )
        api = SimpleNamespace(
            open_existing=lambda *_args, **_kwargs: object(),
            observe=lambda _handle: SimpleNamespace(
                object_identity_fingerprint="a" * 64
            ),
            close=lambda _handle: None,
        )
        runner = SimpleNamespace(
            executable=Path("C:/synthetic/git.exe"),
            executable_identity="a" * 64,
        )
        with (
            patch(
                "backend.cutover_repository_transaction."
                "git_runner.ProcessTree.prepare",
                return_value=tree,
            ),
            patch(
                "backend.cutover_repository_transaction."
                "git_runner.WindowsHandleApi",
                return_value=api,
            ),
            patch(
                "backend.cutover_repository_transaction."
                "git_runner.subprocess.Popen",
                return_value=process,
            ),
            self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_git_runner_invalid$",
            ),
        ):
            _bounded_process(runner, Path("C:/synthetic"), ("status",))

        self.assertGreaterEqual(tree.terminated, 1)

    def test_bound_git_child_has_hosted_ci_budget_without_retry(self):
        payload, returncode, waits, starts, terminated = _run_slow_git_child()

        self.assertEqual((payload, returncode), (b"synthetic\n", 0))
        self.assertEqual(waits, [60])
        self.assertEqual(starts, 1)
        self.assertGreaterEqual(len(terminated), 1)

    def test_review_rejects_unsafe_local_git_configuration(self):
        scenario = build_synthetic_repository_scenario()
        try:
            run_fixture_git(
                scenario.source,
                "config",
                "filter.issue56.clean",
                "cmd /c exit 0",
            )

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_git_runner_invalid$",
            ):
                _review_test_sandbox(scenario)
        finally:
            scenario.close()

    def test_bound_runner_suppresses_repository_hooks(self):
        scenario = build_synthetic_repository_scenario()
        try:
            sentinel = scenario.root / "hostile-hook-fired"
            hook = scenario.source / ".git" / "hooks" / "post-checkout"
            hook.write_text(
                "#!/bin/sh\n"
                f"printf hostile > '{sentinel.as_posix()}'\n",
                "ascii",
            )
            review = _review_test_sandbox(scenario)
            profile = profile_for_review(review)
            scope = _bind_test_sandbox_transaction(
                review=review,
                profile=profile,
                authorization=authorization_for(
                    profile, review.operation_fingerprint
                ),
                observed_at_epoch=OBSERVED_AT,
            )

            run_forward_synthetic_transaction(
                scope=scope,
                failure_selector=SyntheticFailureSelectorV1.none(),
                observed_at_epoch=OBSERVED_AT,
            )

            self.assertFalse(sentinel.exists())
        finally:
            scenario.close()

    def test_scope_binds_exact_reviewed_mixed_topology(self):
        scenario = build_synthetic_repository_scenario()
        try:
            review = _review_test_sandbox(scenario)
            profile = profile_for_review(review)
            authorization = authorization_for(
                profile, review.operation_fingerprint
            )

            scope = _bind_test_sandbox_transaction(
                review=review,
                profile=profile,
                authorization=authorization,
                observed_at_epoch=OBSERVED_AT,
            )

            self.assertEqual(scope.roster.worktree_count, 11)
            self.assertEqual(scope.roster.embedded_count, 8)
            self.assertEqual(scope.roster.external_count, 3)
            self.assertNotIn(str(scenario.root), repr(scope))
        finally:
            scenario.close()

    def test_scope_rejects_dirty_worktree_after_review(self):
        scenario = build_synthetic_repository_scenario()
        try:
            review = _review_test_sandbox(scenario)
            profile = profile_for_review(review)
            authorization = authorization_for(
                profile, review.operation_fingerprint
            )
            dirty = scenario.worktrees[0].original / "dirty.txt"
            dirty.write_text("synthetic drift\n", "utf-8")

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_drift$",
            ):
                _bind_test_sandbox_transaction(
                    review=review,
                    profile=profile,
                    authorization=authorization,
                    observed_at_epoch=OBSERVED_AT,
                )
        finally:
            scenario.close()

    def test_review_rejects_unexpected_extra_worktree(self):
        scenario = build_synthetic_repository_scenario()
        try:
            extra = scenario.root / "extra-worktree"
            run_fixture_git(
                scenario.source,
                "worktree",
                "add",
                "-b",
                "unexpected-extra",
                str(extra),
            )

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_invalid$",
            ):
                _review_test_sandbox(scenario)
        finally:
            scenario.close()

    def test_review_rejects_unexpected_admin_namespace_entry(self):
        scenario = build_synthetic_repository_scenario()
        try:
            unexpected = (
                scenario.source / ".git" / "worktrees" / "unexpected-admin"
            )
            unexpected.mkdir()

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_invalid$",
            ):
                _review_test_sandbox(scenario)
        finally:
            scenario.close()


def _run_slow_git_child():
    waits = []
    terminated = []

    def wait(timeout):
        waits.append(timeout)
        if timeout < 60:
            raise TimeoutError
        return 0

    tree = SimpleNamespace(
        popen_options=lambda: {},
        attach=lambda _process: None,
        finish=lambda _process: 0,
        terminate=lambda _process: terminated.append(1),
    )
    process = SimpleNamespace(
        stdout=io.BytesIO(b"synthetic\n"),
        wait=wait,
    )
    identity = "a" * 64
    content = "b" * 64
    api = SimpleNamespace(
        open_existing=lambda *_args, **_kwargs: object(),
        observe=lambda _handle: SimpleNamespace(
            object_identity_fingerprint=identity
        ),
        close=lambda _handle: None,
    )
    runner = SimpleNamespace(
        executable=Path("C:/synthetic/git.exe"),
        executable_identity=identity,
        executable_content=content,
    )
    target = "backend.cutover_repository_transaction.git_runner"
    with (
        patch(
            f"{target}._executable_content_fingerprint", return_value=content
        ),
        patch(f"{target}.ProcessTree.prepare", return_value=tree),
        patch(f"{target}.WindowsHandleApi", return_value=api),
        patch(f"{target}.subprocess.Popen", return_value=process) as popen,
    ):
        payload, returncode = _bounded_process(
            runner, Path("C:/synthetic"), ("status",)
        )
    return payload, returncode, waits, popen.call_count, terminated


if __name__ == "__main__":
    unittest.main()
