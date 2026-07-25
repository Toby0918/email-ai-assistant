"""Mechanical exclusion tests for migration evidence sources."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.migration_evidence import (
    MigrationEvidenceStatus,
    create_migration_evidence_package,
    prepare_migration_evidence_review,
)
from backend.migration_evidence.contract import DirtyReason
from backend.migration_evidence.errors import MigrationEvidenceError
from backend.migration_evidence.policy import (
    inclusion_reason,
    require_approved_source,
)
from backend.migration_evidence.snapshot import read_checked_file
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
)


FORBIDDEN_PATHS = {
    "backend/credentials.json": DirtyReason.CREDENTIAL,
    "backend/client-secret.json": DirtyReason.CREDENTIAL,
    "backend/signing_key.json": DirtyReason.SIGNING_MATERIAL,
    "backend/private-key.json": DirtyReason.SIGNING_MATERIAL,
    "backend/state.sqlite3-wal": DirtyReason.SQLITE,
    "backend/service.log": DirtyReason.LOG,
    "backend/service.log.1": DirtyReason.LOG,
    "backend/service.pid": DirtyReason.PID_STATE,
    "backend/.tox/runtime/tool.py": DirtyReason.VIRTUAL_ENVIRONMENT,
    "frontend/node_modules/library/index.js": DirtyReason.CACHE,
    "frontend/.vs/settings.json": DirtyReason.IDE_STATE,
    "tests/private_data/customer.json": DirtyReason.PRIVATE_DATA,
    "tests/customer-data/customer.json": DirtyReason.PRIVATE_DATA,
    "backend/.coverage/cache.json": DirtyReason.CACHE,
    "tests/reports/result.json": DirtyReason.OUTPUT,
    "docs/package.migration-evidence.zip": DirtyReason.OUTPUT,
}


class MigrationEvidencePolicyTests(unittest.TestCase):
    def test_forbidden_categories_override_explicit_source_approval(
        self,
    ) -> None:
        for path, reason in FORBIDDEN_PATHS.items():
            with self.subTest(path=path):
                self.assertEqual(
                    inclusion_reason(path, ignored=False),
                    reason,
                )
                with self.assertRaises(MigrationEvidenceError):
                    require_approved_source(path)

    def test_git_ignore_semantics_and_excluded_bytes_are_not_opened(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            (repository / "docs").mkdir()
            (repository / "docs" / ".gitignore").write_text(
                "*.md\n!approved.md\n",
                encoding="utf-8",
            )
            (repository / "docs" / "baseline.txt").write_text(
                "tracked\n",
                encoding="utf-8",
            )
            subprocess_result = subprocess.run(
                ("git", "add", "docs/.gitignore", "docs/baseline.txt"),
                cwd=repository,
                check=True,
                capture_output=True,
            )
            self.assertEqual(subprocess_result.returncode, 0)
            subprocess.run(
                ("git", "commit", "-m", "add nested ignore policy"),
                cwd=repository,
                check=True,
                capture_output=True,
            )
            (repository / "backend" / "service.py").write_text(
                "VALUE = 'approved dirty'\n",
                encoding="utf-8",
            )
            (repository / "backend" / "credentials.json").write_text(
                '{"token":"excluded-canary"}\n',
                encoding="utf-8",
            )
            (repository / "docs" / "secret.md").write_text(
                "ignored-canary\n",
                encoding="utf-8",
            )
            (repository / "docs" / "approved.md").write_text(
                "approved documentation\n",
                encoding="utf-8",
            )
            target = root / "target" / "reviewed.migration-evidence.zip"
            target.parent.mkdir()
            review = prepare_migration_evidence_review(
                repository_root=repository,
                target=target,
                approved_dirty_paths=(
                    "backend/service.py",
                    "docs/approved.md",
                ),
                reviewed_refs=("refs/heads/master",),
                approved_worktrees=(repository,),
                host_baseline=host_baseline(),
            )
            entries = {item.path: item for item in review.dirty_entries}
            self.assertEqual(
                entries["docs/secret.md"].reason,
                DirtyReason.IGNORED,
            )
            self.assertEqual(
                entries["docs/approved.md"].reason,
                DirtyReason.APPROVED_SOURCE,
            )
            self.assertEqual(
                entries["backend/credentials.json"].reason,
                DirtyReason.CREDENTIAL,
            )

            with mock.patch(
                "backend.migration_evidence.snapshot.read_checked_file",
                wraps=read_checked_file,
            ) as checked_read:
                result = create_migration_evidence_package(
                    review=review,
                    confirmed_review_fingerprint=review.review_fingerprint,
                )

            self.assertEqual(
                result.status,
                MigrationEvidenceStatus.CREATED,
            )
            opened = {
                call.args[1]
                for call in checked_read.call_args_list
            }
            self.assertEqual(
                opened,
                {"backend/service.py", "docs/approved.md"},
            )


if __name__ == "__main__":
    unittest.main()
