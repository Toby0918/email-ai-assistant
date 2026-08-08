"""CLI contract for the fixed Issue #110 prepare/confirm adapter."""

from __future__ import annotations

import io
import inspect
import json
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from contextlib import contextmanager
from unittest.mock import Mock, patch

from backend.r2_solo_maintainer_closure import (
    ClosureErrorCode,
    SoloMaintainerClosureError,
)
from backend.r2_solo_maintainer_closure import closure as closure_adapter
from backend.r2_solo_maintainer_closure import storage as storage_adapter
from scripts import close_r2_final_master as cli
from scripts import verify_r2_final_master_closure as verifier


ACK = "CONFIRM_SOLO_MAINTAINER_CLOSURE_V1_NOT_ISSUE39_AUTHORITY"
FINGERPRINT = "1" * 64


class _Value:
    def __init__(self, payload: bytes, manifest_fingerprint: str = FINGERPRINT) -> None:
        self._payload = payload
        self.manifest_fingerprint = manifest_fingerprint

    def to_canonical_json(self) -> bytes:
        return self._payload


class _FakeClosure:
    instances: list[_FakeClosure] = []

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []
        self.instances.append(self)

    def prepare(self) -> _Value:
        self.calls.append(("prepare",))
        return _Value(
            (
                '{"confirmation_acknowledgement":"' + ACK
                + '","manifest_fingerprint":"' + FINGERPRINT + '"}'
            ).encode("ascii")
        )

    def confirm(self, fingerprint: str, acknowledgement: str) -> _Value:
        self.calls.append(("confirm", fingerprint, acknowledgement))
        return _Value(b'{"receipt":"recorded"}')


class CloseR2FinalMasterTests(unittest.TestCase):
    def setUp(self) -> None:
        _FakeClosure.instances.clear()

    def test_prepare_is_the_only_noninteractive_success_surface(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(cli.sys, "argv", ["close_r2_final_master.py", "prepare"]), patch.object(
            cli.sys, "stdout", stdout
        ), patch.object(cli.sys, "stderr", stderr), patch.object(
            cli, "SoloMaintainerClosure", _FakeClosure
        ):
            code = cli.main()
        self.assertEqual(code, 0)
        self.assertIn('"manifest_fingerprint":"' + FINGERPRINT + '"', stdout.getvalue())
        self.assertEqual(stderr.getvalue(), "")
        self.assertEqual(_FakeClosure.instances[0].calls, [("prepare",)])

    def test_confirm_displays_candidate_then_reads_two_visible_lines_once(self) -> None:
        stdout, stderr = io.StringIO(), io.StringIO()
        console_events: list[str] = []

        class _FakeCeremony:
            def __init__(self):
                self.lines = iter((FINGERPRINT + "\r\n", ACK + "\r\n"))

            def require_current(self):
                console_events.append("unchanged")

            def read_console_line(self, _limit):
                console_events.append("read")
                return next(self.lines)

            def require_no_pending_input(self):
                console_events.append("no-pending")

        ceremony = _FakeCeremony()

        @contextmanager
        def fake_ceremony():
            console_events.append("enter")
            yield ceremony
            console_events.append("exit")

        with patch.object(cli.sys, "argv", ["close_r2_final_master.py", "confirm"]), patch.object(
            cli.sys, "stdout", stdout
        ), patch.object(
            cli.sys, "stderr", stderr
        ), patch.object(cli, "SoloMaintainerClosure", _FakeClosure), patch.object(
            cli, "_console_ceremony", fake_ceremony, create=True
        ):
            code = cli.main()
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), '{"receipt":"recorded"}\n')
        candidate_line = (
            '{"confirmation_acknowledgement":"' + ACK
            + '","manifest_fingerprint":"' + FINGERPRINT + '"}'
        )
        self.assertEqual(stderr.getvalue(), candidate_line + "\n")
        self.assertEqual(stderr.getvalue().count(FINGERPRINT), 1)
        self.assertEqual(stderr.getvalue().count(ACK), 1)
        self.assertEqual(
            console_events,
            ["enter", "unchanged", "read", "read", "unchanged", "no-pending", "exit"],
        )
        self.assertEqual(
            _FakeClosure.instances[0].calls,
            [("prepare",), ("confirm", FINGERPRINT, ACK)],
        )

    def test_confirm_rejects_pending_third_line_before_writer(self) -> None:
        events: list[str] = []

        class _PendingCeremony:
            lines = iter((FINGERPRINT + "\r\n", ACK + "\r\n"))

            def require_current(self):
                events.append("unchanged")

            def read_console_line(self, _limit):
                return next(self.lines)

            def require_no_pending_input(self):
                events.append("pending")
                raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)

        @contextmanager
        def fake_ceremony():
            yield _PendingCeremony()

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(cli.sys, "argv", ["tool", "confirm"]), patch.object(
            cli.sys, "stdout", stdout
        ), patch.object(cli.sys, "stderr", stderr), patch.object(
            cli, "SoloMaintainerClosure", _FakeClosure
        ), patch.object(cli, "_console_ceremony", fake_ceremony, create=True):
            self.assertEqual(cli.main(), 2)
        self.assertEqual(events, ["unchanged", "unchanged", "pending"])
        self.assertEqual(_FakeClosure.instances[0].calls, [("prepare",)])
        self.assertEqual(
            stdout.getvalue(),
            '{"status":"R2_SOLO_MAINTAINER_CLOSURE_TTY_REQUIRED"}\n',
        )

    def test_verifier_rejects_any_argv_before_repository_access(self) -> None:
        stdout = io.StringIO()
        flags = SimpleNamespace(isolated=1, safe_path=True)
        with patch.object(verifier.sys, "argv", ["verifier", "extra"]), patch.object(
            verifier.sys, "flags", flags
        ), patch.object(verifier.sys, "stdout", stdout), patch.object(
            verifier, "_verify_fixed_repository"
        ) as verify:
            self.assertEqual(verifier.main(), 2)
        verify.assert_not_called()
        self.assertEqual(
            stdout.getvalue(),
            '{"status":"R2_SOLO_MAINTAINER_CLOSURE_INVALID"}\n',
        )

    def test_invalid_argv_and_content_free_errors_have_one_stdout_line(self) -> None:
        for argv in (
            ["close_r2_final_master.py"],
            ["close_r2_final_master.py", "unknown"],
            ["close_r2_final_master.py", "prepare", "extra"],
        ):
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(argv=argv), patch.object(cli.sys, "argv", argv), patch.object(
                cli.sys, "stdout", stdout
            ), patch.object(cli.sys, "stderr", stderr), patch.object(
                cli,
                "SoloMaintainerClosure",
                side_effect=AssertionError("must reject before construction"),
            ):
                self.assertEqual(cli.main(), 2)
            self.assertEqual(
                stdout.getvalue(),
                '{"status":"R2_SOLO_MAINTAINER_CLOSURE_INVALID"}\n',
            )
            self.assertEqual(stderr.getvalue(), "")

        class _Rejected(_FakeClosure):
            def prepare(self) -> _Value:
                raise SoloMaintainerClosureError(ClosureErrorCode.HOSTED_EVIDENCE_REJECTED)

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(cli.sys, "argv", ["tool", "prepare"]), patch.object(
            cli.sys, "stdout", stdout
        ), patch.object(cli.sys, "stderr", stderr), patch.object(
            cli, "SoloMaintainerClosure", _Rejected
        ):
            self.assertEqual(cli.main(), 2)
        self.assertEqual(
            stdout.getvalue(),
            '{"status":"R2_SOLO_MAINTAINER_CLOSURE_HOSTED_EVIDENCE_REJECTED"}\n',
        )
        self.assertEqual(stderr.getvalue(), "")

    def test_visible_input_removes_only_one_terminal_newline_and_rejects_controls(self) -> None:
        accepted = ((FINGERPRINT + "\n", FINGERPRINT), (ACK + "\r\n", ACK))
        for payload, expected in accepted:
            ceremony = SimpleNamespace(read_console_line=lambda _limit, value=payload: value)
            with self.subTest(payload=payload[-2:]):
                self.assertEqual(cli._read_visible_line(ceremony), expected)
        for payload in (ACK, " " + ACK + "\n", ACK + "\x00\n"):
            ceremony = SimpleNamespace(read_console_line=lambda _limit, value=payload: value)
            with self.subTest(payload=repr(payload)), self.assertRaises(
                SoloMaintainerClosureError
            ):
                cli._read_visible_line(ceremony)

    def test_nested_console_ceremony_reuses_the_exact_guard_object(self) -> None:
        class _Console:
            def snapshot(self):
                return (1, 2, 3)

            def require_unchanged(self, snapshot):
                self.assertEqual(snapshot, (1, 2, 3))

            def assertEqual(self, left, right):
                if left != right:
                    raise AssertionError((left, right))

        first_console, ignored_console = _Console(), _Console()
        with closure_adapter._console_ceremony(first_console) as first:
            with closure_adapter._console_ceremony(ignored_console) as nested:
                self.assertIs(first, nested)
                first.require_current()

    def test_storage_is_windows_only_before_git_path_access(self) -> None:
        with patch.object(storage_adapter.os, "name", "posix"), patch.object(
            storage_adapter, "_git_common_dir"
        ) as git_common, self.assertRaises(SoloMaintainerClosureError) as caught:
            storage_adapter.CreateOnlyClosureStorage().publish(
                b"manifest", b"receipt", FINGERPRINT, lambda *_payloads: None
            )
        self.assertEqual(caught.exception.code, ClosureErrorCode.PUBLICATION_REJECTED)
        git_common.assert_not_called()

    def test_storage_rejects_every_legacy_or_new_stage_before_create(self) -> None:
        conflicts = (
            "r2-solo-maintainer-closure-v1",
            "r2-final-master-closure-v1",
            "R2-FINAL-MASTER-CLOSURE-V1",
            ".r2-final-master-closure-v1.stage-legacy",
            ".R2-SOLO-MAINTAINER-CLOSURE-V1.STAGE-alias",
            ".r2-solo-maintainer-closure-v1.stage-" + "2" * 64,
        )
        for name in conflicts:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                common = Path(directory)
                (common / name).mkdir()
                with patch.object(storage_adapter.os, "name", "nt"), patch.object(
                    storage_adapter, "_git_common_dir", return_value=common
                ), patch.object(storage_adapter, "_commit_no_replace") as commit, \
                        self.assertRaises(SoloMaintainerClosureError) as caught:
                    storage_adapter.CreateOnlyClosureStorage().publish(
                        b"manifest", b"receipt", FINGERPRINT, lambda *_items: None
                    )
                self.assertEqual(caught.exception.code, ClosureErrorCode.ALREADY_EXISTS)
                commit.assert_not_called()
                self.assertFalse(
                    (common / (".r2-solo-maintainer-closure-v1.stage-" + FINGERPRINT)).exists()
                )

    def test_acl_lock_binds_each_kernel_canonicalized_descriptor(self) -> None:
        canonical = (b"file-specific-acl", b"directory-specific-acl")

        def api(name, *_arguments):
            if name == "ConvertStringSecurityDescriptorToSecurityDescriptorW":
                def convert(_sddl, _revision, descriptor, _length):
                    descriptor._obj.value = 1
                    return 1
                return convert
            if name == "SetKernelObjectSecurity":
                return lambda *_values: 1
            if name == "LocalFree":
                return lambda *_values: None
            raise AssertionError(name)

        with patch.object(storage_adapter, "_api", side_effect=api), patch.object(
            storage_adapter, "_read_locked_acl", side_effect=canonical
        ):
            self.assertEqual(
                storage_adapter._lock_read_execute_acl((10, 11)), canonical
            )

    def test_windows_commit_linearizes_at_final_parent_observation(self) -> None:
        events: list[str] = []
        identity = (1, 2, 3)
        guards = [
            (9, 19, object(), object(), object(), identity),
            (10, 20, object(), object(), object(), identity),
            (11, 21, object(), object(), object(), identity),
            (12, None, None, None, None, identity),
        ]

        def rename(*_arguments):
            events.append("rename")
            return 1

        def close(handle):
            if "rename" in events:
                events.append(f"post-close-{handle}")
                raise OSError("close must not reverse publication")
            events.append(f"checked-close-{handle}")
            return 1

        def open_guards(_source, _payloads, _identity, opened, _close):
            opened.extend(guards)
            return b"parent-acl"

        def settle(selected):
            events.append("settled-parent" if len(selected) == 1 else "settled-children")

        helpers = (
            patch.object(storage_adapter, "_prepare_windows_terminal", return_value=(rename, object(), 1, close)),
            patch.object(storage_adapter, "_open_windows_guards", side_effect=open_guards),
            patch.object(storage_adapter, "_lock_read_execute_acl", return_value=b"acl"),
            patch.object(storage_adapter, "_require_exact"),
            patch.object(storage_adapter, "_require_windows_guards"),
            patch.object(storage_adapter, "_require_locked_acl"),
            patch.object(storage_adapter, "_require_parent_guard", side_effect=lambda *_args: events.append("parent-check")),
            patch.object(storage_adapter, "_settle_oplocks", side_effect=settle),
            patch.object(storage_adapter, "_flush_windows_guards", side_effect=lambda _guards: events.append("flushed")),
            patch.object(storage_adapter, "_identity", return_value=identity),
            patch.object(storage_adapter.os, "lstat", return_value=object()),
            patch.object(storage_adapter.os.path, "lexists", return_value=False),
        )
        with helpers[0], helpers[1], helpers[2], helpers[3], helpers[4], helpers[5], \
                helpers[6], helpers[7], helpers[8], helpers[9], helpers[10], helpers[11]:
            storage_adapter._windows_guarded_commit(
                Path("C:/stage"), Path("C:/target"), identity,
                (b"manifest", b"receipt"),
                lambda *_payloads: events.append("callback"),
            )
        self.assertEqual(events[:10], [
            "settled-children", "flushed", "parent-check", "callback",
            "checked-close-20", "checked-close-10", "checked-close-21",
            "checked-close-11", "parent-check", "rename",
        ])
        self.assertEqual(
            events[10:], ["post-close-19", "post-close-9", "post-close-12"]
        )

    def test_parent_guard_failure_after_callback_blocks_rename(self) -> None:
        identity = (1, 2, 3)
        guards = [(value, value + 10, object(), object(), object(), identity)
                  for value in (9, 10, 11, 12)]
        rename = Mock(return_value=1)
        checks = Mock(side_effect=(None, SoloMaintainerClosureError()))

        def open_guards(_source, _payloads, _identity, opened, _close):
            opened.extend(guards)
            return b"parent-acl"

        with patch.object(storage_adapter, "_prepare_windows_terminal", return_value=(rename, object(), 1, Mock())), \
                patch.object(storage_adapter, "_open_windows_guards", side_effect=open_guards), \
                patch.object(storage_adapter, "_lock_read_execute_acl", return_value=b"acl"), \
                patch.object(storage_adapter, "_require_exact"), \
                patch.object(storage_adapter, "_require_windows_guards"), \
                patch.object(storage_adapter, "_require_locked_acl"), \
                patch.object(storage_adapter, "_require_parent_guard", checks), \
                patch.object(storage_adapter, "_settle_oplocks"), \
                patch.object(storage_adapter, "_flush_windows_guards"), \
                patch.object(storage_adapter, "_release_file_guards"), \
                patch.object(storage_adapter, "_identity", return_value=identity), \
                patch.object(storage_adapter.os, "lstat", return_value=object()), \
                patch.object(storage_adapter.os.path, "lexists", return_value=False), \
                self.assertRaises(SoloMaintainerClosureError):
            storage_adapter._windows_guarded_commit(
                Path("C:/stage"), Path("C:/target"), identity,
                (b"manifest", b"receipt"), lambda *_payloads: None,
            )
        self.assertEqual(checks.call_count, 2)
        rename.assert_not_called()

    def test_windows_callback_failure_retains_stage_and_never_renames(self) -> None:
        source = inspect.getsource(storage_adapter._windows_guarded_commit)
        self.assertIn("before_commit(*payloads)\n        _release_file_guards", source)
        self.assertIn("_require_parent_guard(guards[0], source, parent_acl)\n        if rename(", source)
        self.assertNotIn("renameat2", inspect.getsource(storage_adapter))
        with tempfile.TemporaryDirectory() as directory:
            common = Path(directory)
            stage = common / (".r2-solo-maintainer-closure-v1.stage-" + FINGERPRINT)
            target = common / "r2-solo-maintainer-closure-v1"

            def commit(_source, _target, _identity, payloads, before_commit):
                before_commit(*payloads)

            def reject(*_payloads):
                raise SoloMaintainerClosureError(ClosureErrorCode.MASTER_DRIFT)

            with patch.object(storage_adapter.os, "name", "nt"), \
                    patch.object(storage_adapter, "_git_common_dir", return_value=common), \
                    patch.object(storage_adapter, "_commit_no_replace", side_effect=commit), \
                    self.assertRaises(SoloMaintainerClosureError) as caught:
                storage_adapter.CreateOnlyClosureStorage().publish(
                    b"manifest", b"receipt", FINGERPRINT, reject
                )
            self.assertEqual(caught.exception.code, ClosureErrorCode.MASTER_DRIFT)
            self.assertTrue(stage.is_dir())
            self.assertFalse(target.exists())

    @unittest.skipUnless(os.name == "nt", "Windows real TTY proof")
    def test_windows_real_console_cli_proves_exact_two_reads_and_one_guard(self) -> None:
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "closure-cli-proof.json"
            completed = subprocess.run(
                (
                    os.fsdecode(Path(os.sys.executable)), "-B", "-m",
                    "tests.windows_real_tty_host", "--closure-cli-proof", str(target),
                ),
                cwd=Path(__file__).resolve().parents[1],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                startupinfo=startup,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
            self.assertEqual(completed.returncode, 0)
            self.assertEqual(
                json.loads(target.read_text(encoding="utf-8")),
                {
                    "acknowledgement_count": 1,
                    "candidate_line_count": 1,
                    "exit_code": 0,
                    "fingerprint_count": 1,
                    "pending_check_count": 1,
                    "read_count": 2,
                    "receipt_line_count": 1,
                    "same_guard_object": 1,
                    "stable_console": 1,
                    "stderr_write_count": 1,
                    "stdout_write_count": 1,
                },
            )

    def test_entry_signature_and_verbs_are_closed(self) -> None:
        self.assertEqual(tuple(inspect.signature(cli.main).parameters), ())
        self.assertEqual(cli.VERBS, ("prepare", "confirm"))

    def test_verifier_cross_checks_every_receipt_manifest_link(self) -> None:
        linked = {
            "manifest_fingerprint": "1" * 64,
            "final_master_binding_fingerprint": "2" * 64,
            "final_commit_oid": "3" * 40,
            "final_tree_oid": "4" * 40,
            "source_package_fingerprint": "5" * 64,
            "production_binding_fingerprint": "6" * 64,
            "github_guardrail_snapshot_fingerprint": "7" * 64,
            "hosted_evidence_set_fingerprint": "8" * 64,
            "evidence_set_fingerprint": "9" * 64,
            "gap_proof_set_fingerprint": "a" * 64,
        }
        manifest = SimpleNamespace(**linked)
        receipt = SimpleNamespace(**linked, candidate_fingerprint="b" * 64)
        candidate = SimpleNamespace(candidate_fingerprint="b" * 64)
        verifier._require_receipt_links(manifest, receipt, candidate)
        for name in linked:
            forged = SimpleNamespace(**{**linked, name: "f" * len(linked[name])},
                                      candidate_fingerprint="b" * 64)
            with self.subTest(name=name), self.assertRaises(ValueError):
                verifier._require_receipt_links(manifest, forged, candidate)

    def test_verifier_rejects_case_insensitive_incident_siblings(self) -> None:
        conflicts = (
            "R2-FINAL-MASTER-CLOSURE-V1",
            ".R2-FINAL-MASTER-CLOSURE-V1.STAGE-legacy",
            ".R2-SOLO-MAINTAINER-CLOSURE-V1.STAGE-late",
        )
        for conflict in conflicts:
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as directory:
                common = Path(directory)
                target = common / "r2-solo-maintainer-closure-v1"
                target.mkdir()
                for name in (
                    "solo-maintainer-closure-manifest-v1.json",
                    "solo-maintainer-attestation-receipt-v1.json",
                ):
                    (target / name).write_bytes(b"{}")
                (common / conflict).mkdir()
                with patch.object(verifier, "_git_common_dir", return_value=common), \
                        self.assertRaises(ValueError):
                    verifier._read_new_artifacts()


if __name__ == "__main__":
    unittest.main()
