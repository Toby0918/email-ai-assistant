from __future__ import annotations

import unittest
from dataclasses import replace

from backend.container_audit import (
    AuditObjectKind,
    AuditStatus,
    SqliteEvidence,
    SqliteExpectation,
    VolumeEvidence,
    run_container_audit,
)
from tests.container_audit_fixtures import (
    first_evidence,
    opaque,
    populated_audit_inputs,
    valid_audit_inputs,
    with_adapter,
)


class ContainerAuditSqliteTests(unittest.TestCase):
    def assert_sqlite_fails(
        self,
        sqlite: SqliteEvidence,
        *,
        populated: bool,
        policy_expectation: SqliteExpectation | None = None,
    ) -> None:
        factory = populated_audit_inputs if populated else valid_audit_inputs
        policy, adapters = factory()
        if policy_expectation is not None:
            policy = replace(
                policy,
                sqlite_expectation=policy_expectation,
            )
        adapters = with_adapter(adapters, "sqlite", sqlite)

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_expected_absent_state_rejects_present_metadata(self) -> None:
        policy, adapters = valid_audit_inputs()
        sqlite = first_evidence(adapters, "sqlite")
        self.assertIsInstance(sqlite, SqliteEvidence)
        cases = {
            "database": replace(
                sqlite,
                database=first_evidence(
                    populated_audit_inputs()[1],
                    "sqlite",
                ).database,
            ),
            "size": replace(sqlite, size_bytes=1),
            "sidecar": replace(
                sqlite,
                sidecars=("email_agent.sqlite3-wal",),
            ),
            "integrity": replace(sqlite, integrity_ok=True),
            "schema": replace(sqlite, schema_complete=True),
            "aggregate": replace(sqlite, aggregate_row_count=1),
            "service_running": replace(
                sqlite,
                service_stopped=False,
            ),
            "present_flag": replace(sqlite, present=True),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_sqlite_fails(changed, populated=False)

    def test_stopped_present_state_rejects_bad_database_metadata(
        self,
    ) -> None:
        policy, adapters = populated_audit_inputs()
        sqlite = first_evidence(adapters, "sqlite")
        self.assertIsInstance(sqlite, SqliteEvidence)
        cases = {
            "wrong_root": replace(
                sqlite,
                local_data_identity=opaque(5000),
            ),
            "incomplete": replace(
                sqlite,
                inventory_complete=False,
            ),
            "service_running": replace(
                sqlite,
                service_stopped=False,
            ),
            "wrong_filename": replace(
                sqlite,
                filename="other.sqlite3",
            ),
            "no_database": replace(sqlite, database=None),
            "wrong_kind": replace(
                sqlite,
                database=replace(
                    sqlite.database,
                    kind=AuditObjectKind.DIRECTORY,
                ),
            ),
            "unreadable": replace(
                sqlite,
                database=replace(
                    sqlite.database,
                    readable=False,
                ),
            ),
            "reparse": replace(
                sqlite,
                database=replace(
                    sqlite.database,
                    has_reparse_component=True,
                ),
            ),
            "wrong_location": replace(
                sqlite,
                database_location_exact=False,
            ),
            "empty": replace(sqlite, size_bytes=0),
            "oversize": replace(sqlite, size_bytes=1 << 63),
            "sidecar": replace(
                sqlite,
                sidecars=("email_agent.sqlite3-shm",),
            ),
            "integrity": replace(sqlite, integrity_ok=False),
            "schema": replace(sqlite, schema_complete=False),
            "negative_count": replace(
                sqlite,
                aggregate_row_count=-1,
            ),
            "oversize_count": replace(
                sqlite,
                aggregate_row_count=1 << 63,
            ),
            "rows_observed": replace(sqlite, rows_observed=True),
            "not_query_only": replace(sqlite, query_only=False),
        }

        for name, changed in cases.items():
            with self.subTest(name=name):
                self.assert_sqlite_fails(changed, populated=True)

    def test_policy_phase_and_observed_phase_must_match(self) -> None:
        absent_policy, absent_adapters = valid_audit_inputs()
        absent = first_evidence(absent_adapters, "sqlite")
        present_policy, present_adapters = populated_audit_inputs()
        present = first_evidence(present_adapters, "sqlite")
        self.assertIsInstance(absent, SqliteEvidence)
        self.assertIsInstance(present, SqliteEvidence)

        self.assert_sqlite_fails(
            absent,
            populated=False,
            policy_expectation=SqliteExpectation.STOPPED_PRESENT,
        )
        self.assert_sqlite_fails(
            present,
            populated=True,
            policy_expectation=SqliteExpectation.ABSENT_EXPECTED,
        )

    def test_present_database_requires_exact_volume_binding(self) -> None:
        policy, adapters = populated_audit_inputs()
        sqlite = first_evidence(adapters, "sqlite")
        volume = first_evidence(adapters, "volume")
        self.assertIsInstance(sqlite, SqliteEvidence)
        self.assertIsInstance(volume, VolumeEvidence)
        missing_database_binding = replace(
            volume,
            bound_identities=tuple(
                identity
                for identity in volume.bound_identities
                if identity != sqlite.database.identity
            ),
        )
        adapters = with_adapter(
            adapters,
            "volume",
            missing_database_binding,
        )

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)

    def test_database_identity_cannot_alias_other_zone_metadata(
        self,
    ) -> None:
        policy, adapters = populated_audit_inputs()
        filesystem = first_evidence(adapters, "filesystem")
        sqlite = first_evidence(adapters, "sqlite")
        volume = first_evidence(adapters, "volume")
        self.assertIsInstance(sqlite, SqliteEvidence)
        self.assertIsInstance(volume, VolumeEvidence)
        aliased_sqlite = replace(
            sqlite,
            database=filesystem.config.settings_file,
        )
        aliased_volume = replace(
            volume,
            bound_identities=tuple(
                identity
                for identity in volume.bound_identities
                if identity != sqlite.database.identity
            ),
        )
        adapters = with_adapter(adapters, "sqlite", aliased_sqlite)
        adapters = with_adapter(adapters, "volume", aliased_volume)

        result = run_container_audit(policy=policy, adapters=adapters)

        self.assertEqual(result.status, AuditStatus.FAILED)


if __name__ == "__main__":
    unittest.main()
