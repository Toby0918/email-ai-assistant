from __future__ import annotations

import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.r2_issue39_orchestrator.action_catalog import (
    build_fixed_production_action_catalog_v1,
)
from backend.r2_issue39_orchestrator.production_handlers import (
    build_fixed_action_handlers_v1,
)
from backend.r2_issue39_orchestrator.production_host import (
    FixedIssue39WindowsHostV1,
)
from backend.r2_issue39_orchestrator.production_action_evidence import (
    action_evidence,
)
from backend.r2_issue39_orchestrator.production_host_state import (
    observe_action,
    seal_action,
)
from backend.r2_issue39_orchestrator.production_legacy_service import (
    _ensure_recovery_intent,
    _launch_legacy,
    legacy_recovery_observation,
)
from backend.r2_issue39_orchestrator.production_service_windows import (
    ProcessObservation,
)
from tests.test_r2_issue39_action_runner_windows import _prepared


@unittest.skipUnless(os.name == "nt", "Windows production recovery boundaries")
class Issue39RecoveryBoundaryWindowsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = build_fixed_production_action_catalog_v1(_prepared())
        self.handlers = build_fixed_action_handlers_v1(self.catalog)

    def test_rule_fallback_post_write_crash_observes_effect_present(self):
        database = self.root / "email.sqlite3"
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "CREATE TABLE email_analysis (id INTEGER PRIMARY KEY, "
                "subject TEXT, sender TEXT, analysis_json TEXT)"
            )
            connection.commit()
        finally:
            connection.close()
        action = self._action("rule_fallback_analysis")
        host = self._host(database=database, legacy_status="STOPPED")

        self.assertEqual(observe_action(host, action), action.pre_state_fingerprint)
        connection = sqlite3.connect(database)
        try:
            connection.execute(
                "INSERT INTO email_analysis VALUES(1,?,?,?)",
                (
                    "Synthetic delivery question",
                    "buyer@example.test",
                    json.dumps({"analysis_engine": {"source": "rule_fallback"}}),
                ),
            )
            connection.commit()
        finally:
            connection.close()

        self.assertEqual(observe_action(host, action), action.post_state_fingerprint)

    def test_running_legacy_post_stop_crash_observes_effect_present(self):
        action = self._action("legacy_service_quiescence")
        host = self._host(database=self.root / "unused", legacy_status="RUNNING")
        stopped = {
            "status": "STOPPED", "image": "synthetic",
            "command_hash": "a" * 64, "creation_time": 0,
        }

        with patch(
            "backend.r2_issue39_orchestrator.production_service.observe_legacy_service",
            return_value=stopped,
        ):
            self.assertEqual(
                observe_action(host, action), action.post_state_fingerprint
            )

    def test_already_stopped_legacy_marker_distinguishes_forward_noop(self):
        action = self._action("legacy_service_quiescence")
        host = self._host(database=self.root / "unused", legacy_status="STOPPED")
        stopped = {
            "status": "STOPPED", "image": "synthetic",
            "command_hash": "a" * 64, "creation_time": 0,
        }

        with patch(
            "backend.r2_issue39_orchestrator.production_service.observe_legacy_service",
            return_value=stopped,
        ):
            self.assertEqual(
                observe_action(host, action), action.pre_state_fingerprint
            )
            seal_action(host, action, "forward")
            self.assertEqual(
                observe_action(host, action), action.post_state_fingerprint
            )

    def test_container_reverse_post_effect_pre_marker_is_exact(self):
        action = self._action("container_publication")
        container = self.root / "Container"
        failed = self.root / "failed"
        legacy = self.root / "legacy"
        container.mkdir()
        legacy.mkdir()
        host = self._host(database=self.root / "unused", legacy_status="STOPPED")
        host._layout.container = container
        host._layout.failed = failed
        host._layout.legacy = legacy
        seal_action(host, action, "forward")

        os.rename(container, failed)

        self.assertEqual(
            observe_action(host, action), action.pre_state_fingerprint
        )

    def test_retained_main_reverse_is_sealed_and_accepted_by_host(self):
        action = self._action("main_publication")
        main = self.root / "main"
        main.mkdir()
        host = self._host(database=self.root / "unused", legacy_status="STOPPED")
        host._layout.main = main
        seal_action(host, action, "forward")

        FixedIssue39WindowsHostV1.apply(host, action, "rollback", "e" * 64)

        self.assertEqual(
            observe_action(host, action), action.pre_state_fingerprint
        )

    def test_legacy_recovery_intent_prefix_survives_fresh_resume_claim(self):
        action = self._action("legacy_service_quiescence")
        source = self.root / "email_ai_assistant"
        (source / ".venv" / "Scripts").mkdir(parents=True)
        (source / "outputs").mkdir()
        host = self._host(
            database=self.root / "unused", legacy_status="RUNNING", source=source
        )

        first = _ensure_recovery_intent(host, action, "b" * 64)
        resumed = _ensure_recovery_intent(host, action, "c" * 64)

        self.assertEqual(resumed, first)
        self.assertEqual(resumed["attempt_fingerprint"], "b" * 64)

    def test_absent_effect_can_issue_classification_evidence(self):
        action = self._action("container_publication")
        host = self._host(database=self.root / "unused", legacy_status="STOPPED")
        host._layout.container = self.root / "Container"
        host._layout.failed = self.root / "failed"
        host._layout.legacy = self.root / "legacy"

        evidence = action_evidence(
            host, action, "forward", action.pre_state_fingerprint
        )

        self.assertRegex(evidence, r"^[0-9a-f]{64}$")

    def test_audit_facts_change_durable_action_evidence(self):
        action = self._action("final_running_audit")
        host = self._host(database=self.root / "unused", legacy_status="STOPPED")
        observations = ({"topology": "a" * 64}, {"topology": "b" * 64})
        with patch(
            "backend.r2_issue39_orchestrator.production_audit.validation_audit_facts",
            side_effect=observations,
        ):
            first = action_evidence(
                host, action, "forward", action.post_state_fingerprint
            )
            second = action_evidence(
                host, action, "forward", action.post_state_fingerprint
            )

        self.assertNotEqual(first, second)

    def test_running_legacy_recovery_binds_disabled_config_nonce_and_new_process(self):
        action = self._action("legacy_service_quiescence")
        source = self.root / "email_ai_assistant"
        (source / ".venv" / "Scripts").mkdir(parents=True)
        (source / "outputs").mkdir()
        host = self._host(
            database=self.root / "unused", legacy_status="RUNNING", source=source
        )
        intent = _ensure_recovery_intent(host, action, "b" * 64)
        (source / "outputs" / "local_debug_service.pid").write_text(
            "222\n", encoding="ascii"
        )
        observed = ProcessObservation(
            222,
            str(source / ".venv" / "Scripts" / "python.exe"),
            intent["command_hash"],
            333,
        )

        with (
            patch(
                "backend.r2_issue39_orchestrator.production_legacy_service.port_owner",
                return_value=222,
            ),
            patch(
                "backend.r2_issue39_orchestrator.production_legacy_service.observe_process",
                return_value=observed,
            ),
            patch(
                "backend.r2_issue39_orchestrator.production_legacy_service.health",
                return_value=True,
            ),
        ):
            result = legacy_recovery_observation(host)

        self.assertEqual(result["creation_time"], 333)
        self.assertNotEqual(result["creation_time"], host._legacy_service["creation_time"])
        self.assertEqual(result["nonce"], intent["nonce"])
        self.assertEqual(result["llm_provider"], "disabled")
        self.assertEqual(result["text_fallback_provider"], "disabled")

    def test_legacy_launcher_does_not_inherit_unreviewed_environment(self):
        source = self.root / "email_ai_assistant"
        (source / "outputs").mkdir(parents=True)
        intent = {"nonce": "c" * 64}
        sentinel = object()
        with (
            patch.dict(os.environ, {"SYSTEMROOT": r"C:\Windows", "UNSAFE": "x"}, clear=True),
            patch(
                "backend.r2_issue39_orchestrator.production_legacy_service.subprocess.Popen",
                return_value=sentinel,
            ) as popen,
        ):
            self.assertIs(_launch_legacy(source, intent), sentinel)
        command = popen.call_args.args[0]
        environment = popen.call_args.kwargs["env"]
        self.assertIn("--issue39-legacy-recovery-nonce", command)
        self.assertNotIn("UNSAFE", environment)
        self.assertEqual(environment["EMAIL_AGENT_LLM_PROVIDER"], "disabled")
        self.assertEqual(
            environment["EMAIL_AGENT_TEXT_FALLBACK_PROVIDER"], "disabled"
        )
        self.assertEqual(
            environment["EMAIL_AGENT_PRIVATE_KNOWLEDGE_ENABLED"], "false"
        )

    def _action(self, name):
        return next(item for item in self.catalog.actions if item.action_name == name)

    def _host(self, *, database, legacy_status, source=None):
        source = source or self.root / "source"
        state_root = self.root / "incident"
        state_root.mkdir(exist_ok=True)
        closure = SimpleNamespace(
            production=SimpleNamespace(binding_fingerprint="d" * 64)
        )
        host = SimpleNamespace(
            _catalog=self.catalog,
            _handlers=self.handlers,
            _closure=closure,
            _layout=SimpleNamespace(source=source, legacy=self.root / "legacy",
                                    database_target=database),
            _legacy_service={
                "status": legacy_status,
                "image": str(source / ".venv" / "Scripts" / "python.exe"),
                "command_hash": "e" * 64,
                "creation_time": 111 if legacy_status == "RUNNING" else 0,
            },
        )
        host._handler = lambda action: host._handlers[action.action_fingerprint]
        self.enterContext(patch(
            "backend.r2_issue39_orchestrator.production_host_state._ROOT",
            state_root,
        ))
        directory = state_root / (".issue39-host-state-" + "d" * 64)
        directory.mkdir(exist_ok=True)
        return host


@unittest.skipUnless(os.name == "nt", "Windows retained anchor path")
class Issue39AnchorPathWindowsTest(unittest.TestCase):
    def test_anchor_copy_outside_fixed_parent_is_rejected(self):
        from backend.r2_issue39_orchestrator import anchor_context, production_evidence

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "canonical"
            accepted = canonical / ("evidence-" + "a" * 64)
            copied = root / "copied" / ("evidence-" + "a" * 64)
            accepted.mkdir(parents=True)
            copied.mkdir(parents=True)
            accepted_runner = accepted / production_evidence._RUNNER_FILE
            copied_runner = copied / production_evidence._RUNNER_FILE
            accepted_runner.write_bytes(b"anchor")
            copied_runner.write_bytes(b"anchor")
            with patch.object(production_evidence, "_EVIDENCE_PARENT", canonical):
                with patch.object(anchor_context.sys, "argv", [str(accepted_runner)]):
                    self.assertTrue(anchor_context.current_process_is_fixed_anchor_v1())
                with patch.object(anchor_context.sys, "argv", [str(copied_runner)]):
                    self.assertFalse(anchor_context.current_process_is_fixed_anchor_v1())
