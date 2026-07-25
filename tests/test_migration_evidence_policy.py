"""Mechanical exclusion tests for migration evidence sources."""

from __future__ import annotations

import os
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
from backend.migration_evidence.verification_snapshot import _selection_entry
from tests.test_migration_evidence_review import (
    create_repository,
    host_baseline,
)


FORBIDDEN_PATHS = {
    "backend/credentials.json": DirtyReason.CREDENTIAL,
    "backend/client-secret.json": DirtyReason.CREDENTIAL,
    "backend/api_key.json": DirtyReason.CREDENTIAL,
    "backend/client_secret.json": DirtyReason.CREDENTIAL,
    "backend/refresh_token.json": DirtyReason.CREDENTIAL,
    "backend/credentials/settings.json": DirtyReason.CREDENTIAL,
    "backend/secrets/config.py": DirtyReason.CREDENTIAL,
    "backend/signing_key.json": DirtyReason.SIGNING_MATERIAL,
    "backend/private-key.json": DirtyReason.SIGNING_MATERIAL,
    "backend/signing_key/key.py": DirtyReason.SIGNING_MATERIAL,
    "backend/state.sqlite3-wal": DirtyReason.SQLITE,
    "backend/service.log": DirtyReason.LOG,
    "backend/service.log.1": DirtyReason.LOG,
    "backend/service.pid": DirtyReason.PID_STATE,
    "backend/.tox/runtime/tool.py": DirtyReason.VIRTUAL_ENVIRONMENT,
    "frontend/node_modules/library/index.js": DirtyReason.CACHE,
    "frontend/.vs/settings.json": DirtyReason.IDE_STATE,
    "tests/private_data/customer.json": DirtyReason.PRIVATE_DATA,
    "tests/customer-data/customer.json": DirtyReason.PRIVATE_DATA,
    "docs/private_data.md": DirtyReason.PRIVATE_DATA,
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

    def test_forbidden_directory_approval_stops_before_source_read(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = create_repository(root)
            forbidden = repository / "backend" / "secrets" / "config.py"
            forbidden.parent.mkdir()
            forbidden.write_text(
                "SYNTHETIC_CREDENTIAL = 'never-read'\n",
                encoding="utf-8",
            )
            target = (
                root
                / "target"
                / "forbidden.migration-evidence.zip"
            )
            target.parent.mkdir()

            with mock.patch(
                "backend.migration_evidence.snapshot.read_checked_file",
            ) as checked_read:
                with self.assertRaises(MigrationEvidenceError):
                    prepare_migration_evidence_review(
                        repository_root=repository,
                        target=target,
                        approved_dirty_paths=(
                            "backend/secrets/config.py",
                        ),
                        reviewed_refs=("refs/heads/master",),
                        approved_worktrees=(repository,),
                        host_baseline=host_baseline(),
                    )

            checked_read.assert_not_called()

    def test_checked_reader_rejects_reparse_source_parent(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            real = root / "real"
            real.mkdir()
            (real / "source.py").write_text(
                "VALUE = 'synthetic'\n",
                encoding="utf-8",
            )
            alias = root / "alias"
            if os.name == "nt":
                completed = subprocess.run(
                    (
                        os.environ.get("COMSPEC", "cmd.exe"),
                        "/c",
                        "mklink",
                        "/J",
                        str(alias),
                        str(real),
                    ),
                    check=False,
                    capture_output=True,
                )
                if completed.returncode != 0:
                    self.skipTest("temporary junction unavailable")
            else:
                alias.symlink_to(real, target_is_directory=True)

            with self.assertRaises(MigrationEvidenceError):
                read_checked_file(root, "alias/source.py")

    def test_independent_verifier_rechecks_forbidden_source_policy(
        self,
    ) -> None:
        for path in (
            "backend/client-secret.json",
            "backend/credentials/settings.json",
            "tests/private_data/customer.json",
        ):
            with self.subTest(path=path):
                with self.assertRaises(MigrationEvidenceError):
                    _selection_entry(
                        {
                            "path": path,
                            "status": "??",
                            "tracked": False,
                            "ignored": False,
                            "disposition": "included",
                            "reason": "approved_source",
                        }
                    )

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
