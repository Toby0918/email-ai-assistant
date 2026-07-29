from __future__ import annotations

import os
import subprocess
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.cutover_host_mutation.windows_filesystem import (
    _create_test_directory_primitive,
    _create_test_move_primitive,
)

from backend.cutover_repository_transaction.errors import (
    RepositoryTransactionError,
)
from backend.cutover_repository_transaction.durable_store import (
    _RepositoryJournalStore,
)
from backend.cutover_repository_transaction.git_inspection import (
    directory_identity,
)
from backend.cutover_repository_transaction.git_recreation import (
    observe_all_recreated,
)
from backend.cutover_repository_transaction.git_runner import (
    _require_binding,
)
from backend.cutover_repository_transaction.journal_types import (
    ReverseBoundary,
)
from backend.cutover_repository_transaction.scope_models import (
    _SyntheticWorktreePaths,
)
from backend.cutover_repository_transaction.synthetic_scope import (
    _bind_test_sandbox_transaction,
    _review_test_sandbox,
)
from backend.cutover_repository_transaction.transaction import (
    run_forward_synthetic_transaction,
    run_reverse_synthetic_transaction,
)
from backend.cutover_repository_transaction.transaction_types import (
    SyntheticCrashGap,
    SyntheticFailureSelectorV1,
    SyntheticTransactionDirection,
)
from backend.cutover_repository_transaction.verification import (
    verify_forward_topology,
    verify_reverse_topology,
)
from tests.cutover_repository_transaction_fixtures import (
    OBSERVED_AT,
    authorization_for,
    build_synthetic_repository_scenario,
    profile_for_review,
    run_fixture_git,
)


@unittest.skipUnless(sys.platform == "win32", "Windows sandbox required")
class RepositoryTransactionFailClosedTests(unittest.TestCase):
    def test_reverse_rejects_drifted_failed_admin_evidence(self):
        scenario, scope = _bound_scenario()
        try:
            _forward(scope)
            selector = SyntheticFailureSelectorV1.create(
                direction=SyntheticTransactionDirection.REVERSE,
                boundary=ReverseBoundary.PHYSICAL_WORKTREES_RESTORED,
                mutation_index=41,
                gap=SyntheticCrashGap.AFTER_COMMITTED,
            )
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_transaction_interrupted$",
            ):
                run_reverse_synthetic_transaction(
                    scope=scope,
                    failure_selector=selector,
                    observed_at_epoch=OBSERVED_AT,
                )
            drift = (
                scenario.rollback_root
                / "new-admin"
                / "worktree_01"
                / "opaque-drift"
            )
            drift.write_bytes(b"synthetic")

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_topology_verification_failed$",
            ):
                run_reverse_synthetic_transaction(
                    scope=scope,
                    failure_selector=SyntheticFailureSelectorV1.none(),
                    observed_at_epoch=OBSERVED_AT,
                )
        finally:
            scenario.close()

    def test_reverse_resume_rejects_failed_evidence_before_any_mutation(self):
        scenario, scope = _bound_scenario()
        try:
            _forward(scope)
            selector = SyntheticFailureSelectorV1.create(
                direction=SyntheticTransactionDirection.REVERSE,
                boundary=ReverseBoundary.NEW_STATE_PRESERVED,
                mutation_index=18,
                gap=SyntheticCrashGap.AFTER_COMMITTED,
            )
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_transaction_interrupted$",
            ):
                run_reverse_synthetic_transaction(
                    scope=scope,
                    failure_selector=selector,
                    observed_at_epoch=OBSERVED_AT,
                )
            drift = (
                scenario.rollback_root
                / "new-admin"
                / "worktree_01"
                / "opaque-drift"
            )
            drift.write_bytes(b"synthetic")
            journal_count = len(tuple(scenario.journal_root.glob("*.json")))

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_topology_verification_failed$",
            ):
                run_reverse_synthetic_transaction(
                    scope=scope,
                    failure_selector=SyntheticFailureSelectorV1.none(),
                    observed_at_epoch=OBSERVED_AT,
                )

            self.assertEqual(
                len(tuple(scenario.journal_root.glob("*.json"))),
                journal_count,
            )
            self.assertFalse(scenario.source.exists())
            self.assertTrue(
                (scenario.failed_container / "main").is_dir()
            )
        finally:
            scenario.close()

    def test_untrusted_filesystem_observation_is_not_journaled(self):
        scenario, scope = _bound_scenario()
        try:
            def invalid_observation_factory(**values):
                primitive = _create_test_move_primitive(**values)

                def move_object(**arguments):
                    primitive.move_object(**arguments)
                    return object()

                return SimpleNamespace(
                    expectation=primitive.expectation,
                    move_object=move_object,
                )

            with patch(
                "backend.cutover_repository_transaction."
                "mutation_executor._create_test_move_primitive",
                side_effect=invalid_observation_factory,
            ):
                with self.assertRaisesRegex(
                    RepositoryTransactionError,
                    "^repository_observation_invalid$",
                ):
                    _forward(scope)

            self.assertEqual(
                len(tuple(scenario.journal_root.glob("*.json"))), 4
            )
            self.assertEqual(
                directory_identity(
                    scenario.worktree_preservation / "worktree_01"
                ),
                scope.review.observations[0].physical_identity,
            )
        finally:
            scenario.close()

    def test_committed_requires_independent_stable_reread(self):
        cases = (
            (
                2,
                lambda scenario: _replace_directory_root(
                    scenario.worktree_preservation / "worktree_01"
                ),
            ),
            (
                13,
                lambda scenario: (
                    scenario.admin_preservation
                    / "worktree_01"
                    / "opaque-drift"
                ).write_bytes(b"synthetic"),
            ),
            (
                37,
                lambda scenario: run_fixture_git(
                    scenario.worktrees[0].target,
                    "commit",
                    "--allow-empty",
                    "-m",
                    "synthetic stable reread drift",
                ),
            ),
        )
        original = _RepositoryJournalStore.append_observed
        for mutation_index, mutate in cases:
            with self.subTest(mutation_index=mutation_index):
                scenario, scope = _bound_scenario()
                changed = False

                def append_then_mutate(store, intent, actual):
                    nonlocal changed
                    observed = original(store, intent, actual)
                    if (
                        not changed
                        and intent.direction == "forward"
                        and intent.mutation_index == mutation_index
                    ):
                        mutate(scenario)
                        changed = True
                    return observed

                try:
                    with patch.object(
                        _RepositoryJournalStore,
                        "append_observed",
                        new=append_then_mutate,
                    ):
                        with self.assertRaises(
                            RepositoryTransactionError
                        ):
                            _forward(scope)
                    self.assertTrue(changed)
                    records = _RepositoryJournalStore.open_verified(
                        scope
                    ).verified_records()
                    self.assertFalse(
                        any(
                            record.direction == "forward"
                            and record.event == "committed"
                            and record.mutation_index == mutation_index
                            for record in records
                        )
                    )
                finally:
                    scenario.close()

    def test_target_collision_is_rejected_without_clobber(self):
        scenario, scope = _bound_scenario()
        try:
            collision = scenario.worktrees[0].target
            collision.mkdir(parents=True)
            collision_identity = directory_identity(collision)

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_drift$",
            ):
                _forward(scope)

            self.assertEqual(
                directory_identity(collision), collision_identity
            )
            self.assertFalse(any(scenario.journal_root.iterdir()))
        finally:
            scenario.close()

    def test_final_zone_inventory_drift_is_rejected(self):
        scenario, scope = _bound_scenario()
        try:
            _forward(scope)
            unexpected = scenario.source / "Config" / "unexpected.txt"
            unexpected.write_bytes(b"synthetic")
            recreated = observe_all_recreated(
                scope, scenario.source / "main"
            )

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_container_audit_policy_failed$",
            ):
                verify_forward_topology(scope, recreated)
        finally:
            scenario.close()

    def test_container_root_identity_replacement_is_rejected(self):
        scenario, scope = _bound_scenario()
        try:
            _forward(scope)
            _replace_directory_root(scenario.source)
            recreated = observe_all_recreated(
                scope, scenario.source / "main"
            )

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_container_audit_policy_failed$",
            ):
                verify_forward_topology(scope, recreated)
        finally:
            scenario.close()

    def test_reverse_failed_container_root_replacement_is_rejected(self):
        scenario, scope = _bound_scenario()
        try:
            _forward(scope)
            run_reverse_synthetic_transaction(
                scope=scope,
                failure_selector=SyntheticFailureSelectorV1.none(),
                observed_at_epoch=OBSERVED_AT,
            )
            _replace_directory_root(scenario.failed_container)

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_container_audit_policy_failed$",
            ):
                verify_reverse_topology(scope)
        finally:
            scenario.close()

    def test_forward_final_git_selection_drift_is_rejected(self):
        drift_actions = (
            lambda main: run_fixture_git(
                main,
                "commit",
                "--allow-empty",
                "-m",
                "synthetic final ref drift",
            ),
            lambda main: run_fixture_git(
                main,
                "config",
                "remote.synthetic.url",
                "https://example.test/synthetic.git",
            ),
        )
        for drift in drift_actions:
            with self.subTest(drift=drift.__code__.co_firstlineno):
                scenario, scope = _bound_scenario()
                try:
                    _forward(scope)
                    main = scenario.source / "main"
                    drift(main)
                    recreated = observe_all_recreated(scope, main)
                    with self.assertRaisesRegex(
                        RepositoryTransactionError,
                        "^repository_topology_verification_failed$",
                    ):
                        verify_forward_topology(scope, recreated)
                finally:
                    scenario.close()

    def test_reverse_original_git_selection_drift_is_rejected(self):
        scenario, scope = _bound_scenario()
        try:
            _forward(scope)
            run_reverse_synthetic_transaction(
                scope=scope,
                failure_selector=SyntheticFailureSelectorV1.none(),
                observed_at_epoch=OBSERVED_AT,
            )
            run_fixture_git(
                scenario.source,
                "config",
                "remote.synthetic.url",
                "https://example.test/synthetic.git",
            )

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_topology_verification_failed$",
            ):
                verify_reverse_topology(scope)
        finally:
            scenario.close()

    def test_admin_preservation_collision_stops_before_effect(self):
        scenario, scope = _bound_scenario()
        try:
            collision = scenario.admin_preservation / "worktree_01"
            collision.mkdir()
            collision_identity = directory_identity(collision)
            original = directory_identity(
                scenario.worktrees[0].original
            )

            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_transaction_failed$",
            ):
                _forward(scope)

            self.assertEqual(
                directory_identity(collision), collision_identity
            )
            self.assertEqual(
                directory_identity(scenario.worktrees[0].original),
                original,
            )
            self.assertEqual(
                len(tuple(scenario.journal_root.glob("*.json"))), 1
            )
        finally:
            scenario.close()

    def test_target_race_after_durable_intent_is_no_clobber(self):
        scenario, scope = _bound_scenario()
        try:
            original_identity = directory_identity(scenario.source)
            barrier = threading.Barrier(2)
            racer = None

            def racing_factory(**values):
                nonlocal racer
                if Path(values["target"]) != scenario.source:
                    return _create_test_directory_primitive(**values)
                racer = threading.Thread(target=publish_collision)
                racer.start()
                return _create_test_directory_primitive(
                    **values,
                    _target_race_barrier=barrier,
                )

            def publish_collision():
                barrier.wait(timeout=5)
                scenario.source.mkdir()
                barrier.wait(timeout=5)

            with patch(
                "backend.cutover_repository_transaction."
                "mutation_executor._create_test_directory_primitive",
                side_effect=racing_factory,
            ):
                with self.assertRaisesRegex(
                    RepositoryTransactionError,
                    "^repository_transaction_failed$",
                ):
                        _forward(scope)
            self.assertIsNotNone(racer)
            racer.join(timeout=5)

            self.assertFalse(racer.is_alive())
            self.assertEqual(
                directory_identity(scenario.legacy), original_identity
            )
            self.assertNotEqual(
                directory_identity(scenario.source), original_identity
            )
            self.assertEqual(
                len(tuple(scenario.journal_root.glob("*.json"))),
                76,
            )
        finally:
            scenario.close()

    def test_ref_and_admin_content_drift_are_rejected(self):
        drift_actions = (
            lambda scenario, review: run_fixture_git(
                scenario.worktrees[0].original,
                "commit",
                "--allow-empty",
                "-m",
                "synthetic ref drift",
            ),
            lambda _scenario, review: (
                review.observations[0].admin / "opaque-drift"
            ).write_bytes(b"synthetic opaque drift"),
        )
        for drift in drift_actions:
            with self.subTest(drift=drift.__code__.co_firstlineno):
                scenario, scope = _bound_scenario()
                try:
                    drift(scenario, scope.review)
                    with self.assertRaisesRegex(
                        RepositoryTransactionError,
                        "^repository_scope_drift$",
                    ):
                        _forward(scope)
                    self.assertFalse(any(scenario.journal_root.iterdir()))
                finally:
                    scenario.close()

    def test_physical_identity_and_git_executable_drift_are_rejected(self):
        scenario, scope = _bound_scenario()
        try:
            original = scenario.worktrees[0].original
            saved = original.parent / "saved-original-01"
            original.rename(saved)
            original.mkdir()
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_drift$",
            ):
                _forward(scope)
        finally:
            scenario.close()

        scenario, scope = _bound_scenario()
        original_path = os.environ["PATH"]
        try:
            fake = scenario.root / "git.cmd"
            fake.write_text("@exit /b 1\n", "ascii")
            os.environ["PATH"] = str(scenario.root) + os.pathsep + original_path
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_drift$",
            ):
                _forward(scope)
        finally:
            os.environ["PATH"] = original_path
            scenario.close()

    def test_identity_stable_git_executable_content_drift_is_rejected(self):
        scenario, scope = _bound_scenario()
        try:
            with patch(
                "backend.cutover_repository_transaction.git_runner."
                "_executable_content_fingerprint",
                return_value="f" * 64,
            ):
                with self.assertRaisesRegex(
                    RepositoryTransactionError,
                    "^repository_git_runner_invalid$",
                ):
                    _require_binding(scope.review.git_runner)
        finally:
            scenario.close()

    def test_locked_git_content_drift_is_rejected_before_popen(self):
        scenario, scope = _bound_scenario()
        try:
            with (
                patch(
                    "backend.cutover_repository_transaction.git_runner."
                    "_require_binding",
                    return_value=None,
                ),
                patch(
                    "backend.cutover_repository_transaction.git_runner."
                    "_executable_content_fingerprint",
                    return_value="f" * 64,
                ),
                patch(
                    "backend.cutover_repository_transaction.git_runner."
                    "subprocess.Popen",
                ) as popen,
            ):
                with self.assertRaisesRegex(
                    RepositoryTransactionError,
                    "^repository_git_runner_invalid$",
                ):
                    scope.review.git_runner.status(scenario.source)
                popen.assert_not_called()
        finally:
            scenario.close()

    def test_reparse_and_out_of_root_volume_binding_fail_closed(self):
        scenario, scope = _bound_scenario()
        try:
            target = scenario.worktrees[0].target
            target.parent.mkdir(parents=True)
            try:
                os.symlink(
                    scenario.external_target_parent,
                    target,
                    target_is_directory=True,
                )
            except OSError:
                completed = subprocess.run(
                    [
                        os.environ["COMSPEC"],
                        "/d",
                        "/c",
                        "mklink",
                        "/J",
                        str(target),
                        str(scenario.external_target_parent),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=10,
                    check=False,
                    shell=False,
                )
                self.assertEqual(completed.returncode, 0)
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_drift$",
            ):
                _forward(scope)
        finally:
            scenario.close()

        scenario = build_synthetic_repository_scenario()
        try:
            first = scenario.worktrees[0]
            scenario.worktrees = (
                _SyntheticWorktreePaths(
                    role=first.role,
                    placement=first.placement,
                    original=first.original,
                    target=Path("Z:/issue56-synthetic-absent"),
                    preservation=first.preservation,
                ),
                *scenario.worktrees[1:],
            )
            with self.assertRaisesRegex(
                RepositoryTransactionError,
                "^repository_scope_invalid$",
            ):
                _review_test_sandbox(scenario)
        finally:
            scenario.close()


def _bound_scenario():
    scenario = build_synthetic_repository_scenario()
    review = _review_test_sandbox(scenario)
    profile = profile_for_review(review)
    authorization = authorization_for(profile, review.operation_fingerprint)
    scope = _bind_test_sandbox_transaction(
        review=review,
        profile=profile,
        authorization=authorization,
        observed_at_epoch=OBSERVED_AT,
    )
    return scenario, scope


def _forward(scope):
    return run_forward_synthetic_transaction(
        scope=scope,
        failure_selector=SyntheticFailureSelectorV1.none(),
        observed_at_epoch=OBSERVED_AT,
    )


def _replace_directory_root(root: Path) -> None:
    saved = root.with_name(root.name + "-saved")
    root.rename(saved)
    root.mkdir()
    for child in tuple(saved.iterdir()):
        child.rename(root / child.name)


if __name__ == "__main__":
    unittest.main()
