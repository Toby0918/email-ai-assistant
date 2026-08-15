from __future__ import annotations

import unittest
from pathlib import Path

from backend.r2_issue39_orchestrator.roster import (
    Issue39RosterStatusV1,
    _DiscoveredWorktree,
    _RosterPorts,
    _prepare_roster_v1,
    _reverify_roster_v1,
)
from backend.r2_issue39_orchestrator.roster_windows import (
    _parse_worktree_records,
)


class Issue39WorktreeRosterTest(unittest.TestCase):
    def test_complete_six_worktree_roster_binds_two_embedded_four_external(self):
        records = _records(6, embedded=2)
        bound = _prepare_roster_v1(
            root=Path("D:/Projects/email_ai_assistant"),
            ports=_RosterPorts(lambda _root: records),
        )

        self.assertEqual(bound.status, Issue39RosterStatusV1.PREPARED)
        self.assertEqual(bound.counts(), (6, 2, 4))
        self.assertEqual(
            tuple(item.role for item in bound.worktrees),
            tuple(f"worktree_{index:02d}" for index in range(1, 7)),
        )
        self.assertNotIn("D:/", repr(bound))

    def test_any_post_prepare_identity_drift_is_rejected(self):
        records = _records(6, embedded=2)
        current = [records]
        ports = _RosterPorts(lambda _root: current[0])
        bound = _prepare_roster_v1(
            root=Path("D:/Projects/email_ai_assistant"), ports=ports
        )
        current[0] = records[:-1] + (
            _DiscoveredWorktree(
                records[-1].path,
                records[-1].placement,
                "f" * 64,
                records[-1].admin_identity_fingerprint,
                records[-1].admin_content_fingerprint,
                records[-1].head_oid,
                records[-1].branch_fingerprint,
                records[-1].common_fingerprint,
                records[-1].status_fingerprint,
                True,
            ),
        )

        result = _reverify_roster_v1(bound=bound, ports=ports)

        self.assertEqual(result.status, Issue39RosterStatusV1.BLOCKED_DRIFT)
        self.assertEqual(result.counts(), (0, 0, 0))

    def test_dirty_duplicate_or_oversized_roster_fails_closed(self):
        for records in (
            _records(2, embedded=1, dirty=1),
            (_records(2, embedded=1)[0],) * 2,
            _records(17, embedded=8),
        ):
            with self.subTest(count=len(records)):
                result = _prepare_roster_v1(
                    root=Path("D:/Projects/email_ai_assistant"),
                    ports=_RosterPorts(lambda _root, value=records: value),
                )
                self.assertEqual(
                    result.status, Issue39RosterStatusV1.BLOCKED_DISCOVERY
                )

    def test_porcelain_requires_complete_unique_exact_records(self):
        valid = (
            b"worktree D:/Projects/email_ai_assistant\0"
            b"HEAD " + b"a" * 40 + b"\0branch refs/heads/master\0\0"
            b"worktree D:/Projects/wt\0"
            b"HEAD " + b"b" * 40 + b"\0detached\0\0"
        )
        records = _parse_worktree_records(valid)
        self.assertEqual(len(records), 2)
        for invalid in (
            valid + valid,
            valid.replace(b"detached\0", b"detached\0locked reason\0"),
            valid.replace(b"HEAD " + b"b" * 40 + b"\0", b""),
        ):
            with self.subTest(invalid=invalid[-32:]):
                with self.assertRaises(ValueError):
                    _parse_worktree_records(invalid)


def _records(count: int, *, embedded: int, dirty: int = 0):
    return tuple(
        _DiscoveredWorktree(
            Path(f"D:/synthetic/worktree-{index}"),
            "embedded" if index <= embedded else "external",
            f"{100 + index:064x}",
            f"{150 + index:064x}",
            f"{175 + index:064x}",
            f"{200 + index:040x}",
            f"{300 + index:064x}",
            "a" * 64,
            f"{400 + index:064x}",
            index != dirty,
        )
        for index in range(1, count + 1)
    )


if __name__ == "__main__":
    unittest.main()
