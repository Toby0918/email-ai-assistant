from __future__ import annotations

import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import fields, replace

from backend.container_audit import (
    AclEvidence,
    AuditCounts,
    AuditStatus,
    ContainerAuditAdapters,
    ContainerAuditResult,
    FilesystemEvidence,
    SqliteExpectation,
    VolumeEvidence,
    WorktreeEvidence,
    run_container_audit,
)
from tests.container_audit_fixtures import (
    RaisingAdapter,
    first_evidence,
    opaque,
    populated_audit_inputs,
    valid_audit_inputs,
    with_adapter,
)


ADAPTER_ORDER = (
    "filesystem",
    "volume",
    "acl",
    "git",
    "worktree",
    "runtime",
    "sqlite",
)


class ExplodingIterable:
    def __init__(self) -> None:
        self.iterated = False

    def __iter__(self) -> object:
        self.iterated = True
        raise RuntimeError("private-policy-canary")


class ExplodingEquality:
    def __eq__(self, other: object) -> bool:
        raise RuntimeError("private-equality-canary")


class ContainerAuditFailClosedTests(unittest.TestCase):
    def test_public_result_schema_and_values_are_fixed(self) -> None:
        self.assertEqual(
            tuple(field.name for field in fields(ContainerAuditResult)),
            ("status", "counts"),
        )
        self.assertEqual(
            tuple(field.name for field in fields(AuditCounts)),
            ("accepted", "rejected"),
        )
        self.assertEqual(
            {status.value for status in AuditStatus},
            {"container_audit_passed", "container_audit_failed"},
        )
        policy, adapters = valid_audit_inputs()
        success = run_container_audit(policy=policy, adapters=adapters)
        invalid = replace(policy, schema_version=2)
        failure = run_container_audit(policy=invalid, adapters=adapters)
        self.assertEqual(success.counts, AuditCounts(1, 0))
        self.assertEqual(failure.counts, AuditCounts(0, 1))

    def test_malformed_policy_never_calls_an_adapter(self) -> None:
        policy, adapters = valid_audit_inputs()
        cases = {
            "schema": replace(policy, schema_version=True),
            "container_identity": replace(
                policy,
                container_identity="A" * 64,
            ),
            "acl": replace(
                policy,
                container_acl_fingerprint="not-opaque",
            ),
            "volume": replace(policy, volume_identity=opaque(1)[:-1]),
            "worktree_list": replace(
                policy,
                approved_worktrees=[],
            ),
            "worktree_duplicate": replace(
                policy,
                approved_worktrees=(opaque(6000), opaque(6000)),
            ),
            "worktree_unsorted": replace(
                policy,
                approved_worktrees=(opaque(6001), opaque(6000)),
            ),
            "worktree_over_limit": replace(
                policy,
                approved_worktrees=tuple(
                    opaque(6100 + index) for index in range(65)
                ),
            ),
            "clean_type": replace(policy, require_clean_worktrees=1),
            "sqlite_enum": replace(
                policy,
                sqlite_expectation="stopped_present",
            ),
        }

        for name, malformed in cases.items():
            with self.subTest(name=name):
                fresh_policy, fresh_adapters = valid_audit_inputs()
                result = run_container_audit(
                    policy=replace(
                        fresh_policy,
                        **{
                            field.name: getattr(malformed, field.name)
                            for field in fields(fresh_policy)
                        },
                    ),
                    adapters=fresh_adapters,
                )
                self.assertEqual(result.status, AuditStatus.FAILED)
                self.assertEqual(fresh_adapters.filesystem.calls, 0)

    def test_wrong_policy_field_type_is_not_iterated(self) -> None:
        policy, adapters = valid_audit_inputs()
        exploding = ExplodingIterable()
        malformed = replace(policy, approved_worktrees=exploding)

        result = run_container_audit(
            policy=malformed,
            adapters=adapters,
        )

        self.assertEqual(result.status, AuditStatus.FAILED)
        self.assertFalse(exploding.iterated)
        self.assertEqual(adapters.filesystem.calls, 0)

    def test_each_adapter_exception_is_content_free_and_short_circuits(
        self,
    ) -> None:
        for target_index, target in enumerate(ADAPTER_ORDER):
            with self.subTest(adapter=target):
                policy, adapters = valid_audit_inputs()
                raising = RaisingAdapter(
                    RuntimeError(f"private-{target}-canary")
                )
                adapters = replace(adapters, **{target: raising})
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    result = run_container_audit(
                        policy=policy,
                        adapters=adapters,
                    )
                rendered = repr(result) + stdout.getvalue()
                rendered += stderr.getvalue()
                self.assertEqual(result.status, AuditStatus.FAILED)
                self.assertEqual(raising.calls, 1)
                self.assertNotIn("private-", rendered)
                for later in ADAPTER_ORDER[target_index + 1 :]:
                    adapter = getattr(adapters, later)
                    self.assertEqual(adapter.calls, 0)

    def test_validator_exception_maps_to_the_same_fixed_failure(
        self,
    ) -> None:
        policy, adapters = valid_audit_inputs()
        acl = first_evidence(adapters, "acl")
        self.assertIsInstance(acl, AclEvidence)
        malformed = replace(
            acl,
            container_identity=ExplodingEquality(),
        )
        adapters = with_adapter(adapters, "acl", malformed)
        output = io.StringIO()

        with redirect_stdout(output), redirect_stderr(output):
            result = run_container_audit(
                policy=policy,
                adapters=adapters,
            )

        self.assertEqual(
            result,
            ContainerAuditResult(
                status=AuditStatus.FAILED,
                counts=AuditCounts(accepted=0, rejected=1),
            ),
        )
        self.assertNotIn("canary", output.getvalue())
        self.assertNotIn("canary", repr(result))

    def test_first_invalid_snapshot_stops_remaining_reads(self) -> None:
        policy, adapters = valid_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        self.assertIsInstance(filesystem, FilesystemEvidence)
        adapters = with_adapter(
            adapters,
            "filesystem",
            replace(filesystem, inventory_complete=False),
        )

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)
        self.assertEqual(adapters.filesystem.calls, 1)
        for name in ADAPTER_ORDER[1:]:
            self.assertEqual(getattr(adapters, name).calls, 0)

    def test_second_pass_worktree_identity_drift_fails_closed(
        self,
    ) -> None:
        policy, adapters = populated_audit_inputs()
        worktrees = first_evidence(adapters, "worktree")
        volume = first_evidence(adapters, "volume")
        self.assertIsInstance(worktrees, WorktreeEvidence)
        self.assertIsInstance(volume, VolumeEvidence)
        old_relationship = worktrees.relationships[0]
        old_identity = old_relationship.worktree.identity
        new_worktree = replace(
            old_relationship.worktree,
            identity=opaque(7000),
        )
        changed_worktrees = replace(
            worktrees,
            relationships=(
                replace(
                    old_relationship,
                    worktree=new_worktree,
                ),
            ),
        )
        changed_bindings = tuple(
            sorted(
                new_worktree.identity
                if identity == old_identity
                else identity
                for identity in volume.bound_identities
            )
        )
        changed_volume = replace(
            volume,
            bound_identities=changed_bindings,
        )
        adapters = with_adapter(
            adapters,
            "volume",
            volume,
            changed_volume,
        )
        adapters = with_adapter(
            adapters,
            "worktree",
            worktrees,
            changed_worktrees,
        )

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)
        for name in ADAPTER_ORDER:
            self.assertEqual(getattr(adapters, name).calls, 2)

    def test_non_adapter_bundle_and_noncallable_adapter_fail(self) -> None:
        policy, adapters = valid_audit_inputs()
        wrong_bundle = run_container_audit(
            policy=policy,
            adapters=object(),
        )
        noncallable = replace(adapters, filesystem=None)
        wrong_callback = run_container_audit(
            policy=policy,
            adapters=noncallable,
        )

        self.assertEqual(wrong_bundle.status, AuditStatus.FAILED)
        self.assertEqual(wrong_callback.status, AuditStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
