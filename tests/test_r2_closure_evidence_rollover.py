"""Contract tests for historical Solo Maintainer Closure evidence rollover."""

from __future__ import annotations

from dataclasses import replace
import ctypes
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from backend.r2_closure_evidence_rollover import (
    ClosureEvidenceRollover,
    ClosureEvidenceRolloverCandidateV1,
    ClosureEvidenceRolloverError,
    RolloverErrorCode,
)
from backend.r2_closure_evidence_rollover.repository import RolloverRepositorySnapshotV1
from backend.r2_closure_evidence_rollover import repository as repository_adapter
from backend.r2_closure_evidence_rollover.storage import ClosureEvidenceObservationV1
from backend.r2_closure_evidence_rollover import storage as storage_adapter
from backend.r2_solo_maintainer_closure import storage as closure_storage_adapter
from tests.windows_reparse_fixtures import create_test_junction


OLD_COMMIT = "9" * 40
OLD_TREE = "a" * 40
CURRENT_COMMIT = "f" * 40
CURRENT_TREE = "b" * 40
MANIFEST_FINGERPRINT = "3" * 64
RECEIPT_FINGERPRINT = "4" * 64
TARGET = (
    "r2-solo-maintainer-closure-v1.historical-"
    + OLD_COMMIT[:16]
    + "-"
    + MANIFEST_FINGERPRINT[:16]
)


class _Clock:
    def __init__(self, *epochs: int, monotonic: tuple[int, ...] | None = None) -> None:
        self._values = iter(epochs)
        self._monotonic = iter(monotonic or tuple(epoch * 1_000_000_000 for epoch in epochs))

    def wall_epoch(self) -> int:
        return next(self._values)

    def monotonic_ns(self) -> int:
        return next(self._monotonic)


class _Repository:
    def __init__(self, *snapshots: RolloverRepositorySnapshotV1) -> None:
        self._snapshots = iter(snapshots)
        self.calls = 0

    def collect(self, old_commit_oid: str, old_tree_oid: str) -> RolloverRepositorySnapshotV1:
        self.calls += 1
        self.last_old = (old_commit_oid, old_tree_oid)
        return next(self._snapshots)


class _Storage:
    def __init__(self, *observations: ClosureEvidenceObservationV1) -> None:
        self._observations = iter(observations)
        self.calls = 0
        self.commits = 0

    def collect(self) -> ClosureEvidenceObservationV1:
        self.calls += 1
        return next(self._observations)

    def commit(self, observation: ClosureEvidenceObservationV1, before_commit) -> None:
        self.commits += 1
        before_commit()
        self.committed = observation


def _repository_snapshot() -> RolloverRepositorySnapshotV1:
    return RolloverRepositorySnapshotV1.create(
        current_commit_oid=CURRENT_COMMIT,
        current_tree_oid=CURRENT_TREE,
        historical_commit_oid=OLD_COMMIT,
        historical_tree_oid=OLD_TREE,
    )


def _observation(identity: str = "5" * 64) -> ClosureEvidenceObservationV1:
    return storage_adapter._create_observation(
        manifest=b'{"synthetic":"manifest"}',
        receipt=b'{"synthetic":"receipt"}',
        historical_commit_oid=OLD_COMMIT,
        historical_tree_oid=OLD_TREE,
        manifest_fingerprint=MANIFEST_FINGERPRINT,
        receipt_fingerprint=RECEIPT_FINGERPRINT,
        evidence_identity_fingerprint=identity,
        parent_identity_fingerprint="6" * 64,
        parent_dacl_sha256="7" * 64,
        historical_target_name=TARGET,
        source=None,
    )


class ClosureEvidenceRolloverTests(unittest.TestCase):
    def _build(self, repository, storage, clock):
        with patch(
            "backend.r2_closure_evidence_rollover.rollover.FixedRolloverRepository",
            return_value=repository,
        ), patch(
            "backend.r2_closure_evidence_rollover.rollover.FixedClosureEvidenceStorage",
            return_value=storage,
        ), patch(
            "backend.r2_closure_evidence_rollover.rollover._WallClock",
            return_value=clock,
        ):
            return ClosureEvidenceRollover()

    def test_prepare_and_execute_are_exact_single_use_and_zero_authority(self) -> None:
        observation = _observation()
        repository = _Repository(
            _repository_snapshot(), _repository_snapshot(), _repository_snapshot()
        )
        storage = _Storage(observation, observation, observation)
        rollover = self._build(repository, storage, _Clock(100, 101, 102))

        candidate = rollover.prepare()

        self.assertIs(type(candidate), ClosureEvidenceRolloverCandidateV1)
        self.assertEqual(candidate.status, "AWAITING_CLOSURE_EVIDENCE_ROLLOVER")
        self.assertEqual(candidate.prepared_at_epoch, 100)
        self.assertEqual(candidate.expires_at_epoch, 400)
        self.assertEqual(candidate.historical_target_name, TARGET)
        self.assertEqual(candidate.approval_count, 0)
        self.assertEqual(candidate.execution_authority_count, 0)
        self.assertEqual(candidate.issue39_authority_count, 0)

        receipt = rollover.execute(candidate.candidate_fingerprint)

        self.assertEqual(receipt.status, "HISTORICAL_CLOSURE_EVIDENCE_RETAINED")
        self.assertEqual(receipt.candidate_fingerprint, candidate.candidate_fingerprint)
        self.assertEqual(receipt.historical_target_name, TARGET)
        self.assertEqual(receipt.retained_count, 1)
        self.assertEqual(receipt.rename_count, 1)
        self.assertEqual(receipt.copy_count, 0)
        self.assertEqual(receipt.deletion_count, 0)
        self.assertEqual(receipt.overwrite_count, 0)
        self.assertEqual(receipt.cleanup_count, 0)
        self.assertEqual(receipt.approval_count, 0)
        self.assertEqual(receipt.execution_authority_count, 0)
        self.assertEqual(receipt.issue39_authority_count, 0)
        self.assertEqual(storage.commits, 1)
        with self.assertRaises(ClosureEvidenceRolloverError) as caught:
            rollover.execute(candidate.candidate_fingerprint)
        self.assertEqual(caught.exception.code, RolloverErrorCode.STATE_REJECTED)

    def test_execute_rejects_wrong_fingerprint_before_fresh_observation(self) -> None:
        observation = _observation()
        repository = _Repository(_repository_snapshot())
        storage = _Storage(observation)
        rollover = self._build(repository, storage, _Clock(100, 101))
        rollover.prepare()

        with self.assertRaises(ClosureEvidenceRolloverError) as caught:
            rollover.execute("0" * 64)

        self.assertEqual(caught.exception.code, RolloverErrorCode.FINGERPRINT_REJECTED)
        self.assertEqual(repository.calls, 1)
        self.assertEqual(storage.calls, 1)
        self.assertEqual(storage.commits, 0)

    def test_execute_rejects_expired_candidate(self) -> None:
        observation = _observation()
        repository = _Repository(_repository_snapshot())
        storage = _Storage(observation)
        rollover = self._build(repository, storage, _Clock(100, 400))
        candidate = rollover.prepare()

        with self.assertRaises(ClosureEvidenceRolloverError) as caught:
            rollover.execute(candidate.candidate_fingerprint)

        self.assertEqual(caught.exception.code, RolloverErrorCode.STALE)
        self.assertEqual(storage.commits, 0)

    def test_execute_rejects_wall_clock_rollback_after_monotonic_expiry(self) -> None:
        observation = _observation()
        storage = _Storage(observation)
        rollover = self._build(
            _Repository(_repository_snapshot()),
            storage,
            _Clock(100, 101, monotonic=(1_000, 300_000_001_000)),
        )
        candidate = rollover.prepare()

        with self.assertRaises(ClosureEvidenceRolloverError) as caught:
            rollover.execute(candidate.candidate_fingerprint)

        self.assertEqual(caught.exception.code, RolloverErrorCode.STALE)
        self.assertEqual(storage.commits, 0)

    def test_commit_boundary_rejects_monotonic_expiry_despite_valid_wall(self) -> None:
        observation = _observation()
        storage = _Storage(observation, observation, observation)
        rollover = self._build(
            _Repository(
                _repository_snapshot(), _repository_snapshot(), _repository_snapshot()
            ),
            storage,
            _Clock(
                100, 101, 102,
                monotonic=(1_000, 2_000, 300_000_001_000),
            ),
        )
        candidate = rollover.prepare()

        with self.assertRaises(ClosureEvidenceRolloverError) as caught:
            rollover.execute(candidate.candidate_fingerprint)

        self.assertEqual(caught.exception.code, RolloverErrorCode.STALE)
        self.assertEqual(storage.commits, 1)

    def test_execute_rejects_repository_or_evidence_drift(self) -> None:
        cases = (
            (
                _Repository(
                    _repository_snapshot(),
                    replace(_repository_snapshot(), current_tree_oid="c" * 40),
                ),
                _Storage(_observation(), _observation()),
            ),
            (
                _Repository(_repository_snapshot(), _repository_snapshot()),
                _Storage(_observation(), _observation("6" * 64)),
            ),
        )
        for repository, storage in cases:
            with self.subTest(repository=repository, storage=storage):
                rollover = self._build(repository, storage, _Clock(100, 101))
                candidate = rollover.prepare()
                with self.assertRaises(ClosureEvidenceRolloverError) as caught:
                    rollover.execute(candidate.candidate_fingerprint)
                self.assertEqual(caught.exception.code, RolloverErrorCode.STATE_REJECTED)
                self.assertEqual(storage.commits, 0)

    def test_candidate_round_trip_is_strict_canonical_json(self) -> None:
        rollover = self._build(
            _Repository(_repository_snapshot()), _Storage(_observation()), _Clock(100)
        )
        candidate = rollover.prepare()
        parsed = ClosureEvidenceRolloverCandidateV1.from_json(
            candidate.to_canonical_json()
        )
        self.assertEqual(parsed.to_canonical_json(), candidate.to_canonical_json())
        with self.assertRaises(ClosureEvidenceRolloverError):
            ClosureEvidenceRolloverCandidateV1.from_json(
                candidate.to_canonical_json()[:-1] + b',"status":"forged"}'
            )

    def test_repository_requires_clean_exact_master_and_strict_ancestor(self) -> None:
        outputs = {
            ("rev-parse", "HEAD^{commit}"): (CURRENT_COMMIT + "\n").encode("ascii"),
            ("rev-parse", "refs/remotes/origin/master^{commit}"): (
                CURRENT_COMMIT + "\n"
            ).encode("ascii"),
            ("rev-parse", "HEAD^{tree}"): (CURRENT_TREE + "\n").encode("ascii"),
            ("rev-parse", OLD_COMMIT + "^{commit}"): (OLD_COMMIT + "\n").encode("ascii"),
            ("rev-parse", OLD_COMMIT + "^{tree}"): (OLD_TREE + "\n").encode("ascii"),
        }

        def fake_git(*arguments: str) -> bytes:
            if arguments[:2] == ("-c", "status.showUntrackedFiles=all"):
                return b""
            return outputs[arguments]

        with patch.object(repository_adapter, "_git", side_effect=fake_git), patch.object(
            repository_adapter, "_is_ancestor", return_value=True
        ):
            snapshot = repository_adapter.FixedRolloverRepository().collect(
                OLD_COMMIT, OLD_TREE
            )
        self.assertEqual(snapshot, _repository_snapshot())

        def dirty_git(*arguments: str) -> bytes:
            if arguments[:2] == ("-c", "status.showUntrackedFiles=all"):
                return b"?? untracked\0"
            return outputs[arguments]

        with patch.object(repository_adapter, "_git", side_effect=dirty_git), patch.object(
            repository_adapter, "_is_ancestor", return_value=True
        ), self.assertRaises(ClosureEvidenceRolloverError) as caught:
            repository_adapter.FixedRolloverRepository().collect(OLD_COMMIT, OLD_TREE)
        self.assertEqual(caught.exception.code, RolloverErrorCode.STATE_REJECTED)

        rejected = (
            ({("rev-parse", "HEAD^{commit}"): ("e" * 40 + "\n").encode("ascii")}, True),
            ({("rev-parse", OLD_COMMIT + "^{tree}"): ("e" * 40 + "\n").encode("ascii")}, True),
            ({}, False),
        )
        for replacements, ancestor in rejected:
            with self.subTest(replacements=replacements, ancestor=ancestor):
                changed = {**outputs, **replacements}
                def rejected_git(*arguments: str) -> bytes:
                    if arguments[:2] == ("-c", "status.showUntrackedFiles=all"):
                        return b""
                    return changed[arguments]
                with patch.object(repository_adapter, "_git", side_effect=rejected_git), patch.object(
                    repository_adapter, "_is_ancestor", return_value=ancestor
                ), self.assertRaises(ClosureEvidenceRolloverError):
                    repository_adapter.FixedRolloverRepository().collect(OLD_COMMIT, OLD_TREE)

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_storage_collects_only_valid_cross_bound_active_evidence(self) -> None:
        copied = {
            "manifest_fingerprint": MANIFEST_FINGERPRINT,
            "final_commit_oid": OLD_COMMIT,
            "final_tree_oid": OLD_TREE,
            "final_master_binding_fingerprint": "6" * 64,
            "source_package_fingerprint": "7" * 64,
            "production_binding_fingerprint": "8" * 64,
            "github_guardrail_snapshot_fingerprint": "a" * 64,
            "hosted_evidence_set_fingerprint": "b" * 64,
            "evidence_set_fingerprint": "c" * 64,
            "gap_proof_set_fingerprint": "d" * 64,
        }
        manifest = SimpleNamespace(**copied)
        receipt = SimpleNamespace(
            **copied,
            receipt_fingerprint=RECEIPT_FINGERPRINT,
            prepared_at_epoch=100,
            candidate_fingerprint="e" * 64,
        )
        with tempfile.TemporaryDirectory() as directory:
            common = Path(directory)
            source = common / "r2-solo-maintainer-closure-v1"
            source.mkdir()
            (source / "solo-maintainer-closure-manifest-v1.json").write_bytes(b"manifest")
            (source / "solo-maintainer-attestation-receipt-v1.json").write_bytes(b"receipt")
            candidate = SimpleNamespace(candidate_fingerprint="e" * 64)
            with patch.object(storage_adapter, "_git_common_dir", return_value=common), patch.object(
                storage_adapter.SoloMaintainerClosureManifestV1,
                "from_json",
                return_value=manifest,
            ), patch.object(
                storage_adapter.SoloMaintainerAttestationReceiptV1,
                "from_json",
                return_value=receipt,
            ), patch.object(
                repository_adapter.SoloMaintainerClosureCandidateV1,
                "create",
                return_value=candidate,
            ), patch.object(
                storage_adapter,
                "_observe_identity",
                return_value=("5" * 64, "6" * 64, "7" * 64),
            ):
                observed = storage_adapter.FixedClosureEvidenceStorage().collect()
                self.assertEqual(observed.historical_target_name, TARGET)
                self.assertEqual(observed.source, source)
                (common / TARGET).mkdir()
                with self.assertRaises(ClosureEvidenceRolloverError) as caught:
                    storage_adapter.FixedClosureEvidenceStorage().collect()
                self.assertEqual(caught.exception.code, RolloverErrorCode.STATE_REJECTED)

                (common / TARGET).rmdir()
                (common / TARGET.upper()).mkdir()
                with self.assertRaises(ClosureEvidenceRolloverError):
                    storage_adapter.FixedClosureEvidenceStorage().collect()

                receipt.candidate_fingerprint = "f" * 64
                with self.assertRaises(ClosureEvidenceRolloverError):
                    storage_adapter._require_cross_binding(manifest, receipt)

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_storage_commit_preserves_bytes_identity_and_never_clobbers(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
            common = Path(directory)
            source = common / "r2-solo-maintainer-closure-v1"
            source.mkdir()
            payloads = (b'{"synthetic":"manifest"}', b'{"synthetic":"receipt"}')
            for name, payload in zip(storage_adapter._FILES, payloads, strict=True):
                (source / name).write_bytes(payload)
            close = storage_adapter._api("CloseHandle", (ctypes.c_void_p,))
            handles = []
            try:
                for path, flags in (
                    (source, 0x02200000),
                    (source / storage_adapter._FILES[0], 0x00200000),
                    (source / storage_adapter._FILES[1], 0x00200000),
                ):
                    handles.append(
                        storage_adapter._windows_open(path, 0x00060080, 0x7, flags)
                    )
                closure_storage_adapter._lock_read_execute_acl(tuple(handles))
            finally:
                for handle in reversed(handles):
                    close(handle)
            identity, parent_identity, parent_dacl = storage_adapter._observe_identity(
                common, source, payloads
            )
            observation = storage_adapter._create_observation(
                manifest=payloads[0],
                receipt=payloads[1],
                historical_commit_oid=OLD_COMMIT,
                historical_tree_oid=OLD_TREE,
                manifest_fingerprint=MANIFEST_FINGERPRINT,
                receipt_fingerprint=RECEIPT_FINGERPRINT,
                evidence_identity_fingerprint=identity,
                parent_identity_fingerprint=parent_identity,
                parent_dacl_sha256=parent_dacl,
                historical_target_name=TARGET,
                source=source,
            )
            callbacks = []
            try:
                storage_adapter.FixedClosureEvidenceStorage().commit(
                    observation, lambda: callbacks.append("before")
                )
                target = common / TARGET
                self.assertEqual(callbacks, ["before"])
                self.assertFalse(source.exists())
                self.assertEqual(
                    tuple((target / name).read_bytes() for name in storage_adapter._FILES),
                    payloads,
                )
            finally:
                for candidate in (common / TARGET, source):
                    if candidate.exists():
                        _grant_cleanup_access(candidate)

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_storage_commit_preserves_dacls_without_parent_delete_child(self) -> None:
        common, source, payloads, observation, owner = _native_observation(
            parent_sddl="D:P(A;;GRGWGX;;;WD)"
        )
        target = common / TARGET
        parent_dacl = _read_path_dacl(common)
        source_dacl = _read_path_dacl(source)
        try:
            storage_adapter.FixedClosureEvidenceStorage().commit(
                observation, lambda: None
            )
            self.assertFalse(source.exists())
            self.assertTrue(target.exists())
            self.assertEqual(tuple(path.name for path in common.iterdir()), (TARGET,))
            self.assertEqual(_read_path_dacl(common), parent_dacl)
            self.assertEqual(_read_path_dacl(target), source_dacl)
            self.assertEqual(
                tuple((target / name).read_bytes() for name in storage_adapter._FILES),
                payloads,
            )
        finally:
            _set_path_dacl(common, "D:P(A;;FA;;;WD)")
            for candidate in (source, target):
                if candidate.exists():
                    _grant_cleanup_access(candidate)
            owner.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_temporary_delete_dacl_readback_failure_restores_source(self) -> None:
        common, source, _payloads, observation, owner = _native_observation(
            parent_sddl="D:P(A;;GRGWGX;;;WD)"
        )
        original_dacl = _read_path_dacl(source)
        fixed_dacl = storage_adapter._fixed_dacl

        def reject_after_temporary_apply(handle, sddl, *, apply):
            result = fixed_dacl(handle, sddl, apply=apply)
            if sddl == storage_adapter._OWNER_DELETE_DACL:
                raise ClosureEvidenceRolloverError(
                    RolloverErrorCode.PUBLICATION_REJECTED
                )
            return result

        try:
            with patch.object(
                storage_adapter, "_fixed_dacl", side_effect=reject_after_temporary_apply
            ), self.assertRaises(ClosureEvidenceRolloverError):
                storage_adapter.FixedClosureEvidenceStorage().commit(
                    observation, lambda: None
                )
            self.assertTrue(source.exists())
            self.assertFalse((common / TARGET).exists())
            self.assertEqual(_read_path_dacl(source), original_dacl)
        finally:
            _set_path_dacl(common, "D:P(A;;FA;;;WD)")
            if source.exists():
                _grant_cleanup_access(source)
            owner.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_terminal_target_collision_preserves_source_and_competitor(self) -> None:
        common, source, payloads, observation, owner = _native_observation()
        target = common / TARGET
        sentinel = b"synthetic competitor"
        parent_dacl, source_dacl = _read_path_dacl(common), _read_path_dacl(source)
        def collide() -> None:
            target.mkdir()
            (target / "competitor.bin").write_bytes(sentinel)
        try:
            with self.assertRaises(ClosureEvidenceRolloverError):
                storage_adapter.FixedClosureEvidenceStorage().commit(observation, collide)
            self.assertEqual(tuple((source / name).read_bytes() for name in storage_adapter._FILES), payloads)
            self.assertEqual((target / "competitor.bin").read_bytes(), sentinel)
            self.assertEqual(_read_path_dacl(common), parent_dacl)
            self.assertEqual(_read_path_dacl(source), source_dacl)
        finally:
            for candidate in (source, target):
                if candidate.exists():
                    _grant_cleanup_access(candidate)
            owner.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_parent_dacl_drift_fails_before_rename(self) -> None:
        common, source, payloads, observation, owner = _native_observation()
        try:
            with self.assertRaises(ClosureEvidenceRolloverError):
                storage_adapter.FixedClosureEvidenceStorage().commit(
                    observation, lambda: _set_full_access(common)
                )
            self.assertTrue(source.exists())
            self.assertFalse((common / TARGET).exists())
            self.assertEqual(tuple((source / name).read_bytes() for name in storage_adapter._FILES), payloads)
        finally:
            _set_full_access(common)
            if source.exists():
                _grant_cleanup_access(source)
            owner.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_hard_link_ads_and_reparse_are_rejected(self) -> None:
        cases = ("hard_link", "ads", "reparse")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as raw:
                common = Path(raw)
                source = common / "r2-solo-maintainer-closure-v1"
                source.mkdir()
                payloads = (b"manifest", b"receipt")
                for name, payload in zip(storage_adapter._FILES, payloads, strict=True):
                    (source / name).write_bytes(payload)
                if case == "hard_link":
                    os.link(source / storage_adapter._FILES[0], common / "linked.bin")
                elif case == "ads":
                    Path(str(source / storage_adapter._FILES[0]) + ":synthetic").write_bytes(b"ads")
                else:
                    real = common / "real"
                    source.rename(real)
                    create_test_junction(source, real)
                if case == "ads":
                    verifier = lambda: storage_adapter._observe_identity(
                        common, source, payloads
                    )
                else:
                    verifier = lambda: storage_adapter._require_exact(source, payloads)
                with self.assertRaises(Exception):
                    verifier()

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_identity_observation_excludes_concurrent_writers(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            common = Path(raw)
            source = common / "r2-solo-maintainer-closure-v1"
            source.mkdir()
            payloads = (b"manifest", b"receipt")
            for name, payload in zip(storage_adapter._FILES, payloads, strict=True):
                (source / name).write_bytes(payload)
            original, attempts = storage_adapter._read_handle, []
            def read_with_attempt(handle, expected_size, **kwargs):
                if not attempts:
                    try:
                        (source / storage_adapter._FILES[0]).write_bytes(b"X" * len(payloads[0]))
                    except OSError:
                        attempts.append("denied")
                    else:
                        attempts.append("allowed")
                return original(handle, expected_size, **kwargs)
            with patch.object(storage_adapter, "_read_handle", side_effect=read_with_attempt):
                storage_adapter._observe_identity(common, source, payloads)
            self.assertEqual(attempts, ["denied"])
            self.assertEqual((source / storage_adapter._FILES[0]).read_bytes(), payloads[0])

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_file_write_and_parent_identity_drift_fail_before_rename(self) -> None:
        for case in ("file_write", "source_dacl", "parent_identity"):
            common, source, payloads, observation, owner = _native_observation()
            try:
                if case == "file_write":
                    callback = lambda: (source / storage_adapter._FILES[0]).write_bytes(
                        b"X" * len(payloads[0])
                    )
                elif case == "source_dacl":
                    callback = lambda: _set_full_access(source)
                else:
                    callback = lambda: None
                identity_patch = patch.object(
                    storage_adapter, "_handle_identity_fingerprint", return_value="f" * 64
                ) if case == "parent_identity" else patch.object(
                    storage_adapter, "_handle_identity_fingerprint",
                    wraps=storage_adapter._handle_identity_fingerprint,
                )
                with identity_patch, self.assertRaises(ClosureEvidenceRolloverError):
                    storage_adapter.FixedClosureEvidenceStorage().commit(observation, callback)
                self.assertTrue(source.exists())
                self.assertFalse((common / TARGET).exists())
                self.assertEqual(
                    tuple((source / name).read_bytes() for name in storage_adapter._FILES),
                    payloads,
                )
            finally:
                if source.exists():
                    _grant_cleanup_access(source)
                owner.cleanup()

    @unittest.skipUnless(os.name == "nt", "Windows NTFS sandbox required")
    def test_cross_parent_target_rejected_without_callback(self) -> None:
        common, source, payloads, _observation_value, owner = _native_observation()
        callback = []
        other = tempfile.TemporaryDirectory()
        try:
            with self.assertRaises(ClosureEvidenceRolloverError):
                storage_adapter._guarded_rollover(
                    source, Path(other.name) / TARGET, storage_adapter._identity(os.lstat(source)),
                    payloads, "6" * 64, "7" * 64, lambda: callback.append(1),
                )
            self.assertEqual(callback, [])
            self.assertTrue(source.exists())
        finally:
            _grant_cleanup_access(source)
            owner.cleanup()
            other.cleanup()


def _native_observation(*, parent_sddl: str | None = None):
    owner = tempfile.TemporaryDirectory()
    common = Path(owner.name)
    source = common / "r2-solo-maintainer-closure-v1"
    source.mkdir()
    payloads = (b'{"synthetic":"manifest"}', b'{"synthetic":"receipt"}')
    for name, payload in zip(storage_adapter._FILES, payloads, strict=True):
        (source / name).write_bytes(payload)
    _protect_closure(source)
    if parent_sddl is not None:
        _set_path_dacl(common, parent_sddl)
    identity, parent_identity, parent_dacl = storage_adapter._observe_identity(common, source, payloads)
    observation = storage_adapter._create_observation(
        manifest=payloads[0], receipt=payloads[1], historical_commit_oid=OLD_COMMIT,
        historical_tree_oid=OLD_TREE, manifest_fingerprint=MANIFEST_FINGERPRINT,
        receipt_fingerprint=RECEIPT_FINGERPRINT, evidence_identity_fingerprint=identity,
        parent_identity_fingerprint=parent_identity, parent_dacl_sha256=parent_dacl,
        historical_target_name=TARGET, source=source,
    )
    return common, source, payloads, observation, owner


def _protect_closure(source: Path) -> None:
    close = storage_adapter._api("CloseHandle", (ctypes.c_void_p,))
    handles = []
    try:
        for path, flags in ((source, 0x02200000), *((source / name, 0x00200000) for name in storage_adapter._FILES)):
            handles.append(storage_adapter._windows_open(path, 0x00060080, 0x7, flags))
        closure_storage_adapter._lock_read_execute_acl(tuple(handles))
    finally:
        for handle in reversed(handles):
            close(handle)


def _set_full_access(path: Path) -> None:
    _grant_cleanup_access(path)


def _read_path_dacl(path: Path) -> bytes:
    flags = 0x02200000 if path.is_dir() else 0x00200000
    handle = storage_adapter._windows_open(path, 0x00020080, 0x7, flags)
    close = storage_adapter._api("CloseHandle", (ctypes.c_void_p,))
    try:
        return storage_adapter._read_locked_acl(handle, False)
    finally:
        close(handle)


def _set_path_dacl(path: Path, sddl: str) -> None:
    convert = storage_adapter._api(
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        (
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint32),
        ),
        ctypes.c_int,
        "advapi32",
    )
    secure = storage_adapter._api(
        "SetKernelObjectSecurity",
        (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p),
        ctypes.c_int,
        "advapi32",
    )
    descriptor, length = ctypes.c_void_p(), ctypes.c_uint32()
    close = storage_adapter._api("CloseHandle", (ctypes.c_void_p,))
    handle = None
    try:
        if convert(sddl, 1, ctypes.byref(descriptor), ctypes.byref(length)) != 1:
            raise OSError(ctypes.get_last_error())
        flags = 0x02200000 if path.is_dir() else 0x00200000
        handle = storage_adapter._windows_open(path, 0x00060080, 0x7, flags)
        if secure(handle, 0x80000004, descriptor) != 1:
            raise OSError(ctypes.get_last_error())
    finally:
        if handle is not None:
            close(handle)
        if descriptor.value:
            storage_adapter._api(
                "LocalFree", (ctypes.c_void_p,), ctypes.c_void_p
            )(descriptor)


def _grant_cleanup_access(directory: Path) -> None:
    convert = storage_adapter._api(
        "ConvertStringSecurityDescriptorToSecurityDescriptorW",
        (
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(ctypes.c_uint32),
        ),
        ctypes.c_int,
        "advapi32",
    )
    secure = storage_adapter._api(
        "SetKernelObjectSecurity",
        (ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p),
        ctypes.c_int,
        "advapi32",
    )
    descriptor, length = ctypes.c_void_p(), ctypes.c_uint32()
    handles = []
    close = storage_adapter._api("CloseHandle", (ctypes.c_void_p,))
    try:
        if convert(
            "D:P(A;;FA;;;WD)", 1, ctypes.byref(descriptor), ctypes.byref(length)
        ) != 1:
            return
        for path, flags in (
            *((directory / name, 0x00200000) for name in storage_adapter._FILES),
            (directory, 0x02200000),
        ):
            if path.exists():
                handle = storage_adapter._windows_open(path, 0x00040000, 0x7, flags)
                handles.append(handle)
                if secure(handle, 0x80000004, descriptor) != 1:
                    raise OSError(ctypes.get_last_error())
    finally:
        for handle in reversed(handles):
            close(handle)
        if descriptor.value:
            storage_adapter._api(
                "LocalFree", (ctypes.c_void_p,), ctypes.c_void_p
            )(descriptor)


if __name__ == "__main__":
    unittest.main()
