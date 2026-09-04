"""Tests for scripts/maintenance_scan.py.

Run:
    python -m unittest discover -s tests -p "test_maintenance_scan.py"
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from tests.support import load_script_module


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "maintenance_scan.py"


class MaintenanceScanTests(unittest.TestCase):
    def test_script_exists(self) -> None:
        # The cleanup automation depends on this script staying runnable.
        self.assertTrue(SCRIPT.exists(), "scripts/maintenance_scan.py should exist")

    def test_report_rendering(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan")
        report = module.render_report([])
        self.assertIn("# Cleanup Agent Report", report)
        self.assertIn("No cleanup findings detected.", report)

    def test_front_matter_parser_accepts_required_fields(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan")
        text = """---
last_update: 2026-06-29
status: active
owner: "@tobyWang"
review_cycle: monthly
source_type: operation_guide
---

# Example
"""
        self.assertTrue(module.has_required_front_matter(text))

    def test_front_matter_parser_accepts_bom_and_crlf(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan")
        text = "\ufeff---\r\nlast_update: 2026-06-29\r\nstatus: active\r\nowner: \"@tobyWang\"\r\nreview_cycle: monthly\r\nsource_type: operation_guide\r\n---\r\n"
        self.assertTrue(module.has_required_front_matter(text))

    def test_script_runs_directly(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("# Cleanup Agent Report", result.stdout)

    def test_reviewed_setup_checklist_is_not_a_stale_draft(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_setup_checklist")

        classifications = {
            (finding.category, finding.path)
            for finding in module.scan_docs_metadata_and_staleness()
        }

        self.assertNotIn(
            ("stale_doc", "docs/operations/setup_checklist.md"),
            classifications,
        )

    def test_leakage_findings_are_content_free(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_leakage")
        synthetic = module.LeakageFinding(
            code="LEAK_SECRET_VALUE",
            scope="test_output",
            count=2,
        )

        findings = module.scan_repository_leakage(scan=lambda: (synthetic,))
        report = module.render_report(findings)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].path, "[test_output]")
        self.assertEqual(findings[0].category, "repository_leakage")
        self.assertIn("LEAK_SECRET_VALUE", report)
        self.assertIn("count=2", report)
        self.assertNotIn("secret", report.lower().replace("leak_secret_value", ""))
        self.assertNotIn("matched", report.lower())

    def test_stable_observation_excludes_rendered_message_and_fix(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_stable_observation")
        baseline = module.Finding(
            "low",
            "stale_doc",
            "docs/example.md",
            "draft document has been stale for 30 days",
            "review the document lifecycle",
            "docs/operations/cleanup_agent.md",
        )
        calendar_changed = module.Finding(
            "low",
            "stale_doc",
            "docs/example.md",
            "draft document has been stale for 31 days",
            "choose an updated document status",
            "docs/operations/cleanup_agent.md",
        )

        with patch.object(module, "collect_findings", return_value=[baseline]):
            first = module.collect_stable_observation()
        with patch.object(
            module, "collect_findings", return_value=[calendar_changed]
        ):
            second = module.collect_stable_observation()

        self.assertEqual(first, second)
        self.assertEqual(first.total_count, 1)
        self.assertEqual(first.low_count, 1)
        self.assertEqual(first.medium_count, 0)
        self.assertEqual(first.high_count, 0)
        self.assertEqual(
            first.records[0].as_tuple(),
            (
                "low",
                "stale_doc",
                "docs/example.md",
                "docs/operations/cleanup_agent.md",
            ),
        )

    def test_stable_observation_rejects_duplicate_records(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_duplicate_observation")
        duplicate = module.Finding(
            "low",
            "stale_doc",
            "docs/example.md",
            "dynamic message",
            "dynamic fix",
            "docs/operations/cleanup_agent.md",
        )

        with patch.object(
            module, "collect_findings", return_value=[duplicate, duplicate]
        ), self.assertRaises(module.MaintenanceObservationError) as caught:
            module.collect_stable_observation()

        self.assertEqual(
            caught.exception.code,
            "MAINTENANCE_OBSERVATION_DUPLICATE",
        )
        self.assertEqual(
            str(caught.exception),
            "MAINTENANCE_OBSERVATION_DUPLICATE",
        )
        self.assertNotIn("docs/example.md", repr(caught.exception))

    def test_stable_observation_rejects_malformed_finding(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_invalid_observation")

        with patch.object(
            module, "collect_findings", return_value=[object()]
        ), self.assertRaises(module.MaintenanceObservationError) as caught:
            module.collect_stable_observation()

        self.assertEqual(
            caught.exception.code,
            "MAINTENANCE_OBSERVATION_INVALID",
        )
        self.assertEqual(
            str(caught.exception),
            "MAINTENANCE_OBSERVATION_INVALID",
        )

    def test_stable_observation_rejects_unhashable_severity(self) -> None:
        module = load_script_module(
            SCRIPT, "maintenance_scan_unhashable_severity"
        )
        malformed = module.Finding(
            [], "stale_doc", "docs/example.md", "message", "fix", "rules.md"
        )

        with patch.object(
            module, "collect_findings", return_value=[malformed]
        ), self.assertRaises(module.MaintenanceObservationError) as caught:
            module.collect_stable_observation()

        self.assertEqual(
            caught.exception.code,
            "MAINTENANCE_OBSERVATION_INVALID",
        )

    def test_stable_observation_maps_scanner_failure_to_fixed_error(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_failed_observation")

        with patch.object(
            module,
            "collect_findings",
            side_effect=RuntimeError("private scanner detail"),
        ), self.assertRaises(module.MaintenanceObservationError) as caught:
            module.collect_stable_observation()

        self.assertEqual(
            caught.exception.code,
            "MAINTENANCE_OBSERVATION_SCAN_FAILED",
        )
        self.assertEqual(
            str(caught.exception),
            "MAINTENANCE_OBSERVATION_SCAN_FAILED",
        )
        self.assertNotIn("private scanner detail", repr(caught.exception))

    def test_stable_observation_sorts_records_deterministically(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_sorted_observation")
        first = module.Finding(
            "low", "stale_doc", "docs/a.md", "message", "fix", "docs/rules.md"
        )
        second = module.Finding(
            "medium", "other", "docs/z.md", "message", "fix", "docs/rules.md"
        )

        with patch.object(
            module, "collect_findings", return_value=[second, first]
        ):
            observation = module.collect_stable_observation()

        self.assertEqual(
            tuple(item.path for item in observation.records),
            ("docs/a.md", "docs/z.md"),
        )

    def test_materialized_observation_uses_explicit_gitless_root(self) -> None:
        module = load_script_module(
            SCRIPT, "maintenance_scan_materialized_observation"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "README.md").write_text("synthetic\n", encoding="utf-8")

            observation = module._collect_materialized_stable_observation(
                root,
                ("README.md",),
            )

        self.assertEqual(observation.records, ())
        self.assertEqual(observation.total_count, 0)
        self.assertEqual(observation.high_count, 0)

    def test_materialized_observation_rejects_unsafe_tracked_paths(self) -> None:
        module = load_script_module(
            SCRIPT, "maintenance_scan_unsafe_materialized_paths"
        )
        invalid_values = (
            (1, "README.md"),
            ("C:/outside.txt",),
            ("..\\outside.txt",),
            ("foo:bar",),
            ("CON",),
            ("CONIN$",),
            ("CONOUT$.log",),
            ("COM0",),
            ("LPT0",),
            ("dir/aux.txt",),
            ("COM¹.txt",),
            ("ＣＯＭ１.txt",),
            ("control\x00.md",),
            ("control\n.md",),
            ("control\x7f.md",),
            ("README.md", "README.md"),
            ("z.md", "a.md"),
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for tracked_paths in invalid_values:
                with self.subTest(tracked_paths=tracked_paths):
                    with self.assertRaises(
                        module.MaintenanceObservationError
                    ) as caught:
                        module._collect_materialized_stable_observation(
                            root,
                            tracked_paths,
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "MAINTENANCE_OBSERVATION_INVALID",
                    )

    def test_materialized_observation_maps_root_probe_failure(self) -> None:
        module = load_script_module(
            SCRIPT, "maintenance_scan_materialized_root_probe"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(
                type(root), "is_dir", side_effect=OSError("private path detail")
            ), self.assertRaises(module.MaintenanceObservationError) as caught:
                module._collect_materialized_stable_observation(root, ())

        self.assertEqual(
            caught.exception.code,
            "MAINTENANCE_OBSERVATION_INVALID",
        )
        self.assertNotIn("private path detail", repr(caught.exception))

    def test_stable_observation_values_are_observer_owned(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_observer_owned")

        with self.assertRaises(TypeError):
            module.StableMaintenanceFindingV1(
                "low", "stale_doc", "docs/a.md", "docs/rules.md"
            )
        with self.assertRaises(TypeError):
            module.MaintenanceObservationV1((), 0, 0, 0, 0)

    def test_maintenance_observation_error_codes_are_closed(self) -> None:
        module = load_script_module(SCRIPT, "maintenance_scan_closed_errors")

        with self.assertRaises(TypeError):
            module.MaintenanceObservationError("UNREVIEWED_ERROR")


if __name__ == "__main__":
    unittest.main()
