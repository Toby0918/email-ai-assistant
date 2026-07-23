"""Synthetic-only tests for the raw-vault to evaluation-staging boundary."""

from __future__ import annotations

import copy
import gc
import json
import os
import tempfile
import unittest
import weakref
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from backend.private_evaluation.errors import PrivateEvaluationError
from backend.private_evaluation.repository import DATASET_MAGIC, DATASET_PURPOSE
from backend.private_evaluation.schema import EvaluationCaseV1
from backend.private_evaluation.staging import stage_evaluation
from backend.private_evaluation.staging_contract import (
    StageEvaluationResult,
    StageEvaluationSelection,
    load_stage_evaluation_manifest,
)
from backend.private_evaluation.staging_repository import (
    MAX_STAGE_BYTES,
    STAGE_MAGIC,
    STAGE_PURPOSE,
    EvaluationStageV1,
    read_encrypted_stage,
    write_encrypted_stage,
)
from backend.private_knowledge.deidentifier import deidentify_private_text
from backend.private_knowledge.residual_scanner import ResidualFinding, scan_residuals
from backend.project_layout import RepositoryPlacement, StandaloneStateKind
from tests.private_evaluation_fixtures import case_mapping, uuid4_for


NOW = datetime(2026, 7, 15, 12, 30, tzinfo=timezone.utc)


def stage_selection_mapping(count: int = 200) -> dict[str, object]:
    cases: list[dict[str, object]] = []
    for index in range(count):
        source = case_mapping(index)
        for approval in source["approvals"].values():  # type: ignore[union-attr]
            if approval is not None:
                approval["approved_at"] = "2026-07-15T12:00:00Z"
        cases.append({
            "record_id": f"{index + 1:032x}",
            "case_id": source["case_id"],
            "revision": source["revision"],
            "approvals": copy.deepcopy(source["approvals"]),
            "stratum": copy.deepcopy(source["stratum"]),
            "expected": copy.deepcopy(source["expected"]),
        })
    return {
        "schema_version": "StageEvaluationSelectionV1",
        "vault_id": uuid4_for(80_000),
        "scope_fingerprint": "a" * 64,
        "inventory_fingerprint": "b" * 64,
        "window_start": "2024-07-15T00:00:00Z",
        "window_end": "2026-07-15T00:00:00Z",
        "expires_at": "2026-07-16T12:00:00Z",
        "cases": cases,
    }


def evaluation_cases() -> tuple[EvaluationCaseV1, ...]:
    return tuple(
        EvaluationCaseV1.from_mapping(case_mapping(index)) for index in range(200)
    )


class _LiveState:
    raw = 0
    mapping = 0
    maximum_raw = 0
    maximum_mapping = 0


class _RawRecord:
    __slots__ = ("text", "context", "_state")

    def __init__(self, text: str, state: _LiveState) -> None:
        self.text = text
        self.context = {"people": ["Alex Example"], "organizations": []}
        self._state = state

    def __enter__(self) -> _RawRecord:
        self._state.raw += 1
        self._state.maximum_raw = max(self._state.maximum_raw, self._state.raw)
        return self

    def __exit__(self, *_args: object) -> None:
        self.text = ""
        self.context = {}
        self._state.raw -= 1


class _TrackedDeidentified:
    __slots__ = ("_inner", "_state")

    def __init__(self, text: str, context: object, state: _LiveState) -> None:
        self._inner = deidentify_private_text(text, context)
        self._state = state

    @property
    def text(self) -> str:
        return self._inner.text

    def __enter__(self) -> _TrackedDeidentified:
        self._state.mapping += 1
        self._state.maximum_mapping = max(
            self._state.maximum_mapping, self._state.mapping
        )
        self._inner.__enter__()
        return self

    def __exit__(self, *_args: object) -> None:
        self._inner.close()
        self._state.mapping -= 1


class _ReferenceTrackedText(str):
    pass


class _ReferenceTrackedContext(dict):
    pass


class _ReferenceTrackedRawRecord:
    def __init__(self, text: str, context: object) -> None:
        self.text = text
        self.context = context

    def __enter__(self) -> _ReferenceTrackedRawRecord:
        return self

    def __exit__(self, *_args: object) -> None:
        self.text = ""
        self.context = {}


class PrivateEvaluationStagingTests(unittest.TestCase):
    def test_manifest_is_exact_200_unique_scope_bound_reviewed_and_repr_hidden(self) -> None:
        value = stage_selection_mapping()
        selected = StageEvaluationSelection(value)

        self.assertEqual(len(selected.cases), 200)
        self.assertEqual(selected.vault_id, value["vault_id"])
        self.assertEqual(selected.scope_fingerprint, "a" * 64)
        self.assertEqual(selected.cases[0].record_id, "0" * 31 + "1")
        selected.require_current(NOW)
        rendered = repr(selected)
        self.assertEqual(rendered, "StageEvaluationSelection(<redacted>)")
        self.assertNotIn(selected.cases[0].record_id, rendered)
        self.assertNotIn(selected.cases[0].case_id, rendered)

    def test_manifest_requires_a_separate_reviewed_inventory_fingerprint(self) -> None:
        value = stage_selection_mapping()
        selected = StageEvaluationSelection(value)
        self.assertEqual(selected.scope_fingerprint, "a" * 64)
        self.assertEqual(selected.inventory_fingerprint, "b" * 64)

        missing = copy.deepcopy(value)
        missing.pop("inventory_fingerprint")
        invalid = copy.deepcopy(value)
        invalid["inventory_fingerprint"] = "not-an-inventory-fingerprint"
        for candidate in (missing, invalid):
            with self.subTest(candidate_fields=sorted(candidate)), self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_selection_invalid"
            ):
                StageEvaluationSelection(candidate)

    def test_manifest_rejects_count_duplicates_unknown_content_and_scope_window(self) -> None:
        invalid_values: list[dict[str, object]] = []
        invalid_values.extend((stage_selection_mapping(199), stage_selection_mapping(201)))

        duplicate_record = stage_selection_mapping()
        duplicate_record["cases"][1]["record_id"] = duplicate_record["cases"][0]["record_id"]  # type: ignore[index]
        invalid_values.append(duplicate_record)

        duplicate_case = stage_selection_mapping()
        duplicate_case["cases"][1]["case_id"] = duplicate_case["cases"][0]["case_id"]  # type: ignore[index]
        invalid_values.append(duplicate_case)

        raw_content = stage_selection_mapping()
        raw_content["cases"][0]["subject"] = "forbidden source content"  # type: ignore[index]
        invalid_values.append(raw_content)

        bad_scope = stage_selection_mapping()
        bad_scope["scope_fingerprint"] = "not-a-fingerprint"
        invalid_values.append(bad_scope)

        long_window = stage_selection_mapping()
        long_window["window_start"] = "2024-07-12T00:00:00Z"
        invalid_values.append(long_window)

        unknown = stage_selection_mapping()
        unknown["unknown"] = True
        invalid_values.append(unknown)

        for value in invalid_values:
            with self.subTest(value_type=len(value.get("cases", []))), self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_selection_invalid"
            ):
                StageEvaluationSelection(value)

    def test_manifest_reuses_case_approval_enum_and_revision_semantics(self) -> None:
        invalid_values: list[dict[str, object]] = []
        same_actor = stage_selection_mapping()
        same_actor["cases"][0]["approvals"]["privacy"]["actor_ref"] = (  # type: ignore[index]
            same_actor["cases"][0]["approvals"]["business"]["actor_ref"]  # type: ignore[index]
        )
        invalid_values.append(same_actor)

        stale_revision = stage_selection_mapping()
        stale_revision["cases"][0]["approvals"]["business"]["case_revision"] = 2  # type: ignore[index]
        invalid_values.append(stale_revision)

        wrong_pair_role = stage_selection_mapping()
        wrong_pair_role["cases"][0]["approvals"]["pro_pair"]["role"] = "business"  # type: ignore[index]
        invalid_values.append(wrong_pair_role)

        bad_enum = stage_selection_mapping()
        bad_enum["cases"][0]["stratum"]["category"] = "other"  # type: ignore[index]
        invalid_values.append(bad_enum)

        for value in invalid_values:
            with self.subTest(), self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_selection_invalid"
            ):
                StageEvaluationSelection(value)

        optional_pair = stage_selection_mapping()
        optional_pair["cases"][0]["approvals"]["pro_pair"] = None  # type: ignore[index]
        self.assertIsNone(
            StageEvaluationSelection(optional_pair).cases[0].approvals.pro_pair
        )

    def test_manifest_expiry_is_after_latest_required_review_and_at_most_24_hours(self) -> None:
        too_late = stage_selection_mapping()
        too_late["expires_at"] = "2026-07-16T12:00:01Z"
        with self.assertRaisesRegex(
            PrivateEvaluationError, "evaluation_stage_selection_invalid"
        ):
            StageEvaluationSelection(too_late)

        selected = StageEvaluationSelection(stage_selection_mapping())
        with self.assertRaisesRegex(
            PrivateEvaluationError, "evaluation_stage_selection_expired"
        ):
            selected.require_current(
                datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
            )

    def test_manifest_load_is_bounded_absolute_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            manifest = root / "selection.json"
            manifest.write_text(json.dumps(stage_selection_mapping()), encoding="utf-8")
            selected = load_stage_evaluation_manifest(manifest, now=NOW)
            self.assertEqual(len(selected.cases), 200)

            with self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_selection_invalid"
            ):
                load_stage_evaluation_manifest(Path("relative.json"), now=NOW)

            oversized = root / "oversized.json"
            oversized.write_bytes(b"{" + b"x" * (1024 * 1024) + b"}")
            with self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_selection_invalid"
            ):
                load_stage_evaluation_manifest(oversized, now=NOW)

            link = root / "selection-link.json"
            try:
                link.symlink_to(manifest)
            except OSError:
                return
            with self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_selection_invalid"
            ):
                load_stage_evaluation_manifest(link, now=NOW)

    def test_stage_releases_raw_and_mapping_before_next_record_and_single_write(self) -> None:
        selected = StageEvaluationSelection(stage_selection_mapping())
        state = _LiveState()
        state.raw = state.mapping = state.maximum_raw = state.maximum_mapping = 0
        writes: list[tuple[EvaluationCaseV1, ...]] = []

        def writer(cases: tuple[EvaluationCaseV1, ...]) -> None:
            self.assertEqual((state.raw, state.mapping), (0, 0))
            self.assertEqual(len(cases), 200)
            self.assertTrue(all(case.deidentified_email.attachments == () for case in cases))
            self.assertEqual(cases[0].deidentified_email.subject, "Deidentified message")
            self.assertEqual(cases[0].deidentified_email.sender, "Deidentified sender")
            self.assertEqual(cases[0].deidentified_email.recipients, ("Deidentified recipient",))
            self.assertEqual(cases[0].deidentified_email.sent_at, "Deidentified time")
            self.assertIn("<PERSON_1>", cases[0].deidentified_email.thread_text)
            self.assertNotIn("Alex Example", repr(cases))
            writes.append(cases)

        result = stage_evaluation(
            selected,
            read_one_record=lambda _record_id: _RawRecord(
                "Alex Example requested a safe reply.", state
            ),
            deidentify=lambda text, context: _TrackedDeidentified(
                text, context, state
            ),
            scan_residuals=scan_residuals,
            write_encrypted_stage=writer,
        )

        self.assertEqual(
            result.to_dict(),
            {
                "ok": True,
                "code": "evaluation_stage_complete",
                "accepted_count": 200,
                "rejected_count": 0,
            },
        )
        self.assertEqual((state.maximum_raw, state.maximum_mapping), (1, 1))
        self.assertEqual((state.raw, state.mapping), (0, 0))
        self.assertEqual(len(writes), 1)

    def test_stage_drops_raw_local_references_before_opening_next_record(self) -> None:
        selected = StageEvaluationSelection(stage_selection_mapping())
        references: list[tuple[weakref.ReferenceType, weakref.ReferenceType]] = []
        retained_before_next: list[bool] = []

        def read_one_record(_record_id: str) -> _ReferenceTrackedRawRecord:
            gc.collect()
            if references:
                retained_before_next.append(any(ref() is not None for ref in references[-1]))
            text = _ReferenceTrackedText("Alex Example requested a safe reply.")
            context = _ReferenceTrackedContext(
                {"people": ["Alex Example"], "organizations": []}
            )
            references.append((weakref.ref(text), weakref.ref(context)))
            return _ReferenceTrackedRawRecord(text, context)

        result = stage_evaluation(
            selected,
            read_one_record=read_one_record,
            deidentify=deidentify_private_text,
            scan_residuals=scan_residuals,
            write_encrypted_stage=lambda _cases: None,
        )

        gc.collect()
        self.assertEqual(result.code, "evaluation_stage_complete")
        self.assertEqual(len(retained_before_next), 199)
        self.assertFalse(any(retained_before_next))
        self.assertTrue(all(ref() is None for pair in references for ref in pair))

    def test_residual_or_callback_failure_rejects_batch_without_partial_write(self) -> None:
        selected = StageEvaluationSelection(stage_selection_mapping())
        state = _LiveState()
        state.raw = state.mapping = state.maximum_raw = state.maximum_mapping = 0
        writes: list[object] = []
        scans = 0

        def residuals(_value: object) -> tuple[ResidualFinding, ...]:
            nonlocal scans
            scans += 1
            return () if scans == 1 else (ResidualFinding("residual_email", 1),)

        blocked = stage_evaluation(
            selected,
            read_one_record=lambda _record_id: _RawRecord(
                "Alex Example requested a safe reply.", state
            ),
            deidentify=lambda text, context: _TrackedDeidentified(text, context, state),
            scan_residuals=residuals,
            write_encrypted_stage=lambda cases: writes.append(cases),
        )
        self.assertEqual(
            blocked,
            StageEvaluationResult("evaluation_stage_residual_blocked", 0, 200),
        )
        self.assertEqual(writes, [])
        self.assertEqual((state.raw, state.mapping), (0, 0))

        failed = stage_evaluation(
            selected,
            read_one_record=lambda _record_id: (_ for _ in ()).throw(
                RuntimeError("SENSITIVE-CANARY")
            ),
            deidentify=deidentify_private_text,
            scan_residuals=scan_residuals,
            write_encrypted_stage=lambda _cases: None,
        )
        self.assertEqual(failed.code, "evaluation_stage_callback_failed")
        self.assertNotIn("SENSITIVE-CANARY", repr(failed))
        self.assertNotIn(selected.cases[0].record_id, repr(failed))

    def test_stage_repository_round_trip_random_nonce_and_distinct_contract(self) -> None:
        cases = evaluation_cases()
        key = bytearray(b"S" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "cases.pkevalstage"
            allow_path = patch(
                "backend.private_evaluation.staging_repository._validate_external_stage_path",
                return_value=path,
            )
            with allow_path:
                write_encrypted_stage(path, cases, key)
                first = path.read_bytes()
                loaded = read_encrypted_stage(path, key)
                write_encrypted_stage(path, cases, key)
                second = path.read_bytes()

        self.assertIsInstance(loaded, EvaluationStageV1)
        self.assertEqual(loaded.cases, cases)
        self.assertNotEqual(first, second)
        self.assertTrue(first.startswith(STAGE_MAGIC))
        self.assertNotIn(b"Current request", first)
        self.assertNotIn(cases[0].case_id.encode("ascii"), first)
        self.assertNotEqual(STAGE_MAGIC, DATASET_MAGIC)
        self.assertNotEqual(STAGE_PURPOSE, DATASET_PURPOSE)

    def test_stage_repository_real_validator_excludes_only_its_own_target(self) -> None:
        from backend.private_evaluation.staging_repository import (
            _validate_external_stage_path,
        )

        cases = evaluation_cases()
        key = bytearray(b"V" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            target = root / "cases.pkevalstage"
            with patch(
                "backend.private_evaluation.repository_path.tempfile.gettempdir",
                return_value="C:/SyntheticPolicyTemp",
            ):
                write_encrypted_stage(target, cases, key)
                first = read_encrypted_stage(target, key)
                write_encrypted_stage(target, cases, key)
                second = read_encrypted_stage(target, key)
                self.assertEqual(first.cases, cases)
                self.assertEqual(second.cases, cases)

                with self.assertRaisesRegex(
                    PrivateEvaluationError, "evaluation_stage_unavailable"
                ):
                    _validate_external_stage_path(root / "peer.pkevalstage")

                target.unlink()
                nested = root / "nested"
                nested.mkdir()
                (nested / "other.pkevalstage").write_bytes(b"synthetic")
                with self.assertRaisesRegex(
                    PrivateEvaluationError, "evaluation_stage_unavailable"
                ):
                    _validate_external_stage_path(root / "new.pkevalstage")

    def test_stage_repository_rejects_wrong_key_tamper_invalid_key_and_oversize(self) -> None:
        cases = evaluation_cases()
        key = bytearray(b"S" * 32)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / "cases.pkevalstage"
            allow_path = patch(
                "backend.private_evaluation.staging_repository._validate_external_stage_path",
                return_value=path,
            )
            with allow_path:
                write_encrypted_stage(path, cases, key)
                original = path.read_bytes()
                with self.assertRaisesRegex(
                    PrivateEvaluationError, "evaluation_stage_decrypt_invalid"
                ):
                    read_encrypted_stage(path, bytearray(b"W" * 32))

                tampered = bytearray(original)
                tampered[-1] ^= 1
                path.write_bytes(tampered)
                with self.assertRaisesRegex(
                    PrivateEvaluationError, "evaluation_stage_decrypt_invalid"
                ):
                    read_encrypted_stage(path, key)

                for invalid in (bytearray(b"K" * 31), True, "K" * 32):
                    with self.subTest(key_type=type(invalid).__name__), self.assertRaisesRegex(
                        PrivateEvaluationError, "evaluation_key_unavailable"
                    ):
                        write_encrypted_stage(path, cases, invalid)  # type: ignore[arg-type]

                path.write_bytes(os.urandom(MAX_STAGE_BYTES + 1))
                with self.assertRaisesRegex(
                    PrivateEvaluationError, "evaluation_stage_decrypt_invalid"
                ):
                    read_encrypted_stage(path, key)

    def test_stage_path_is_absolute_exact_suffix_external_and_store_separated(self) -> None:
        from backend.private_evaluation.staging_repository import (
            _validate_external_stage_path,
        )

        project = Path(__file__).resolve().parents[1]
        for candidate in (
            Path("relative.pkevalstage"),
            project / "private.pkevalstage",
            Path(tempfile.gettempdir()) / "private.pkevalstage",
            project.parent / "OneDrive" / "private.pkevalstage",
            project.parent / "private.pkeval",
            project.parent / "private.PKEVALSTAGE",
        ):
            with self.subTest(candidate=str(candidate)), self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_unavailable"
            ):
                _validate_external_stage_path(candidate)

        with tempfile.TemporaryDirectory() as temporary, patch(
            "tempfile.gettempdir", return_value="C:/SyntheticPolicyTemp"
        ):
            root = Path(temporary).resolve()
            raw = root / "raw"
            raw.mkdir()
            (raw / "vault-index.sqlite3").write_text("synthetic", encoding="utf-8")
            with self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_unavailable"
            ):
                _validate_external_stage_path(raw / "private.pkevalstage")

            isolated = root / "isolated"
            isolated.mkdir()
            (isolated / "dataset.pkeval").write_text("synthetic", encoding="utf-8")
            with self.assertRaisesRegex(
                PrivateEvaluationError, "evaluation_stage_unavailable"
            ):
                _validate_external_stage_path(isolated / "private.pkevalstage")

    def test_stage_path_rejects_every_project_container_zone(self) -> None:
        from backend.private_evaluation import repository_path
        from backend.private_evaluation.staging_repository import (
            _validate_external_stage_path,
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            container = root / "managed" / "email_ai_assistant"
            repository = container / "main"
            repository.mkdir(parents=True)
            zones = (
                container,
                repository,
                container / "Runtimes",
                container / "LocalData",
                container / "RuntimeTemp",
                container / "Logs",
                container / "Artifacts",
                container / "Worktrees",
                container / "Config",
                container / "OperatorPrivate",
            )

            with patch.object(
                repository_path,
                "_PROJECT_CONTEXT",
                repository,
            ), patch(
                "backend.private_evaluation.repository_path.tempfile.gettempdir",
                return_value="C:/SyntheticPolicyTemp",
            ):
                for zone in zones:
                    with self.subTest(zone=zone), self.assertRaisesRegex(
                        PrivateEvaluationError,
                        "evaluation_stage_unavailable",
                    ):
                        _validate_external_stage_path(
                            zone / "nested" / "cases.pkevalstage"
                        )

                external = root / "external" / "cases.pkevalstage"
                external.parent.mkdir()
                self.assertEqual(
                    _validate_external_stage_path(external),
                    external,
                )

    def test_stage_path_honors_explicit_standalone_state_root(self) -> None:
        from backend.private_evaluation import repository_path
        from backend.private_evaluation.staging_repository import (
            _validate_external_stage_path,
        )

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            repository = root / "portable-repository"
            state = root / "standalone-state"
            external = root / "standalone-external"
            repository.mkdir()
            state.mkdir()
            external.mkdir()
            placement = RepositoryPlacement.standalone(
                repository_root=repository,
                state_root=state,
                state_kind=StandaloneStateKind.SYNTHETIC,
            )

            with patch.object(
                repository_path,
                "_PROJECT_CONTEXT",
                placement,
            ), patch(
                "backend.private_evaluation.repository_path.tempfile.gettempdir",
                return_value="C:/SyntheticPolicyTemp",
            ):
                with self.assertRaisesRegex(
                    PrivateEvaluationError,
                    "evaluation_stage_unavailable",
                ):
                    _validate_external_stage_path(
                        state / "cases.pkevalstage"
                    )
                self.assertEqual(
                    _validate_external_stage_path(
                        external / "cases.pkevalstage"
                    ),
                    external / "cases.pkevalstage",
                )

    def test_result_and_errors_are_content_free(self) -> None:
        result = StageEvaluationResult("evaluation_stage_callback_failed", 0, 200)
        self.assertEqual(
            result.to_dict(),
            {
                "ok": False,
                "code": "evaluation_stage_callback_failed",
                "accepted_count": 0,
                "rejected_count": 200,
            },
        )
        with self.assertRaisesRegex(
            PrivateEvaluationError, "evaluation_stage_unavailable"
        ) as caught:
            from backend.private_evaluation.staging_repository import (
                _validate_external_stage_path,
            )

            _validate_external_stage_path(Path("SENSITIVE-CANARY.pkevalstage"))
        self.assertNotIn("SENSITIVE-CANARY", repr(caught.exception))


if __name__ == "__main__":
    unittest.main()
