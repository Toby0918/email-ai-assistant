"""Content-free repository leakage guard contracts for Task 7."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repository_leakage_scan.py"


class RepositoryLeakageScanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_script_module(SCRIPT, "repository_leakage_scan")

    def test_synthetic_allowlists_and_public_sources_are_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fixture = root / "fixture.txt"
            fixture.write_text(
                "sender@example.test\n"
                "buyer@example.com\n"
                "reviewer@synthetic.internal\n"
                "https://learn.microsoft.com/en-us/windows/win32/api/dpapi/\n",
                encoding="utf-8",
            )

            findings = self.module.scan_file_set(
                root,
                (self.module.ScopedFile("git_tracked", "fixture.txt"),),
            )

        self.assertEqual(findings, ())

    def test_nonreserved_company_domain_is_not_allowlisted(self) -> None:
        identity = "staff" + "@" + "cndlf.com"
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            fixture = root / "status.md"
            fixture.write_text(identity, encoding="utf-8")

            findings = self.module.scan_file_set(
                root,
                (self.module.ScopedFile("generated_status", fixture.name),),
            )

        self.assertEqual(
            findings,
            (self.module.LeakageFinding("LEAK_PRIVATE_IDENTIFIER", "generated_status", 1),),
        )

    def test_findings_expose_only_fixed_codes_counts_and_scope_categories(self) -> None:
        secret = "sk-" + "A" * 36
        identity = "private.user" + "@" + "corp.invalid"
        raw_mail = "\n".join(
            (
                "From: " + identity,
                "To: reviewer@example.test",
                "Subject: synthetic private canary",
                "Message-ID: <opaque@corp.invalid>",
            )
        )
        derived = "[[PRIVATE" + "-DERIVED]] synthetic canary prose"
        attachment = "X-Private-Attachment" + "-Name: BoardPack.pdf"
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            path = root / "do-not-render-this-name.txt"
            path.write_text(
                "DEEPSEEK_API_KEY=" + secret + "\n"
                + identity + "\n"
                + raw_mail + "\n"
                + derived + "\n"
                + attachment,
                encoding="utf-8",
            )
            findings = self.module.scan_file_set(
                root,
                (self.module.ScopedFile("git_tracked", path.name),),
            )
            rendered = self.module.render_summary(findings)

        codes = {item.code for item in findings}
        self.assertEqual(
            codes,
            {
                "LEAK_SECRET_VALUE",
                "LEAK_PRIVATE_IDENTIFIER",
                "LEAK_RAW_MAIL",
                "LEAK_ATTACHMENT_NAME",
                "LEAK_REAL_DERIVED_PROSE",
            },
        )
        self.assertTrue(all(item.scope == "git_tracked" for item in findings))
        self.assertTrue(all(item.count >= 1 for item in findings))
        self.assertNotIn(secret, rendered)
        self.assertNotIn(identity, rendered)
        self.assertNotIn(path.name, rendered)
        self.assertNotIn("BoardPack", rendered)
        self.assertNotIn("canary prose", rendered)
        self.assertEqual(
            set(json.loads(self.module.summary_as_json(findings))),
            {"findings", "total"},
        )

    def test_binary_vault_material_is_reported_without_opening_external_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.bin"
            tracked.write_bytes(b"PKVAULT01" + bytes(range(64)))
            external = root.parent / "external-private.pkeval"
            external.write_bytes(b"PKEVAL01" + bytes(range(64)))
            try:
                findings = self.module.scan_file_set(
                    root,
                    (self.module.ScopedFile("git_tracked", tracked.name),),
                )
            finally:
                external.unlink(missing_ok=True)

        self.assertEqual(
            findings,
            (self.module.LeakageFinding("LEAK_VAULT_MATERIAL", "git_tracked", 1),),
        )

    def test_private_evaluation_files_are_rejected_from_scope_without_reading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            private_case = root / "private.pkeval"
            private_case.write_bytes(b"PKEVAL01" + b"not-opened")

            findings = self.module.scan_file_set(
                root,
                (self.module.ScopedFile("git_tracked", private_case.name),),
            )

        self.assertEqual(
            findings,
            (self.module.LeakageFinding("LEAK_FORBIDDEN_PRIVATE_DATASET", "git_tracked", 1),),
        )

    def test_repo_local_private_dataset_is_named_but_never_opened(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            outputs = root / "outputs"
            outputs.mkdir()
            private_case = outputs / "private.pkeval"
            private_case.write_bytes(b"PKEVAL01" + b"synthetic")

            scoped = self.module.collect_default_scope(root, tracked_files=())
            findings = self.module.scan_file_set(root, scoped)

        self.assertEqual(
            findings,
            (self.module.LeakageFinding("LEAK_FORBIDDEN_PRIVATE_DATASET", "test_output", 1),),
        )

    def test_git_scope_failure_is_fixed_and_fail_closed(self) -> None:
        def fail(_command, _cwd):
            raise OSError("native path and source detail")

        with self.assertRaisesRegex(
            self.module.LeakageScanError, "leakage_scope_unavailable"
        ) as raised:
            self.module.list_git_tracked(ROOT, runner=fail)

        self.assertNotIn("native path", str(raised.exception))

    def test_repository_logs_test_outputs_and_public_sqlite_are_scanned(self) -> None:
        identity = "private.user" + "@" + "corp.invalid"
        secret = "tok_" + "B" * 36
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "service.log").write_text(identity, encoding="utf-8")
            (root / "test-result.txt").write_text(
                "access_token=" + secret, encoding="utf-8"
            )
            database = root / "public.sqlite"
            connection = sqlite3.connect(database)
            try:
                connection.execute("CREATE TABLE fixture (body TEXT)")
                connection.execute("INSERT INTO fixture VALUES (?)", (identity,))
                connection.commit()
            finally:
                connection.close()

            findings = self.module.scan_file_set(
                root,
                (
                    self.module.ScopedFile("repository_log", "service.log"),
                    self.module.ScopedFile("test_output", "test-result.txt"),
                    self.module.ScopedFile("public_sqlite", "public.sqlite"),
                ),
            )

        observed = {(item.code, item.scope) for item in findings}
        self.assertIn(("LEAK_PRIVATE_IDENTIFIER", "repository_log"), observed)
        self.assertIn(("LEAK_SECRET_VALUE", "test_output"), observed)
        self.assertIn(("LEAK_PRIVATE_IDENTIFIER", "public_sqlite"), observed)

    def test_default_scope_is_repo_local_and_content_free(self) -> None:
        tracked = self.module.list_git_tracked(
            ROOT,
            runner=lambda _command, _cwd: "AGENTS.md\0docs/README.md\0",
        )
        self.assertEqual(tracked, ("AGENTS.md", "docs/README.md"))

        scoped = self.module.collect_default_scope(ROOT, tracked_files=tracked)
        self.assertTrue(scoped)
        self.assertTrue(all(item.scope in self.module.ALLOWED_SCOPES for item in scoped))
        self.assertTrue(all(not item.relative_path.lower().endswith(".pkeval") for item in scoped))
        self.assertTrue(all(".." not in Path(item.relative_path).parts for item in scoped))


if __name__ == "__main__":
    unittest.main()
