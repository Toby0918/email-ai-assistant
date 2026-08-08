"""Public-seam tests for Issue #110 Solo Maintainer Closure."""

from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from backend.r2_production_composition import build_production_binding_candidate_v1
from backend.r2_solo_maintainer_closure import (
    ClosureErrorCode,
    FinalMasterBindingV1,
    SoloMaintainerAttestationReceiptV1,
    SoloMaintainerClosure,
    SoloMaintainerClosureCandidateV1,
    SoloMaintainerClosureError,
    SoloMaintainerClosureManifestV1,
)
from backend.r2_solo_maintainer_closure._canonical import canonical_json, fingerprint
from backend.r2_solo_maintainer_closure.hosted_evidence import (
    FIXED_CHECKS,
    HOSTED_STEP_KEYS,
    GitHubEvidenceSnapshotV1,
    GitHubGuardrailSnapshotV1,
    HostedCheckEvidenceV1,
    hosted_step_fingerprints,
    ruleset_configuration_v1,
)
from backend.r2_solo_maintainer_closure.local_evidence import (
    PROOF_KINDS,
    LocalSourceProofV1,
    build_local_source_proofs,
    repository_subject_names,
)
from backend.r2_solo_maintainer_closure import local_evidence as local_evidence_adapter
from backend.r2_solo_maintainer_closure.repository import (
    RepositorySnapshotV1,
)
from backend.r2_solo_maintainer_closure import repository as repository_adapter
from backend.r2_solo_maintainer_closure import storage as storage_adapter


ACK = "CONFIRM_SOLO_MAINTAINER_CLOSURE_V1_NOT_ISSUE39_AUTHORITY"
ZERO = "0" * 64


class _FakeClock:
    def __init__(self, wall: tuple[int, ...], monotonic: tuple[int, ...]) -> None:
        self._wall = iter(wall)
        self._monotonic = iter(monotonic)

    def wall_epoch(self) -> int:
        return next(self._wall)

    def monotonic_ns(self) -> int:
        return next(self._monotonic)


class _FakePort:
    def __init__(self, *values: object) -> None:
        self._values = iter(values)
        self.calls = 0

    def collect(self, *unused: object) -> object:
        self.calls += 1
        return next(self._values)


class _FakeStorage:
    def __init__(self) -> None:
        self.publications: list[tuple[bytes, bytes, str]] = []

    def publish(self, manifest: bytes, receipt: bytes, fingerprint: str,
                before_commit) -> None:
        before_commit(manifest, receipt)
        self.publications.append((manifest, receipt, fingerprint))


class _FakeConsole:
    def __init__(self, valid: bool = True) -> None:
        self.valid = valid
        self.snapshots = 0

    def snapshot(self) -> object:
        self.snapshots += 1
        if not self.valid:
            raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)
        return (11, 12, 13)

    def require_unchanged(self, snapshot: object) -> None:
        if not self.valid or snapshot != (11, 12, 13):
            raise SoloMaintainerClosureError(ClosureErrorCode.TTY_REQUIRED)


class SoloMaintainerClosureTests(unittest.TestCase):
    def setUp(self) -> None:
        status = (Path(__file__).resolve().parents[1]
                  / "docs/operations/project_status_log.md").read_bytes().decode("utf-8")
        self.status_builder = patch(
            "scripts.generate_project_status.build_project_status", return_value=status
        ).start()
        from scripts.maintenance_scan import Finding
        self.maintenance_scan = patch(
            "scripts.maintenance_scan.collect_findings",
            return_value=_classified_maintenance_findings(Finding),
        ).start()
        self.leakage_scan = patch(
            "scripts.repository_leakage_scan.scan_repository", return_value=()
        ).start()
        self.addCleanup(patch.stopall)

    def test_local_source_proof_has_exact_private_contract_and_domain(self) -> None:
        proof = LocalSourceProofV1.create(
            source="closure_map",
            proof_kind="CANONICAL_DERIVATION",
            final_commit_oid="1" * 40,
            final_tree_oid="a" * 40,
            source_package_fingerprint="b" * 64,
            subject_fingerprints=(("canonical:closure_map", "c" * 64),),
        )
        self.assertEqual(
            set(proof.to_mapping()),
            {
                "source", "proof_kind", "final_commit_oid", "final_tree_oid",
                "source_package_fingerprint", "subject_fingerprints",
                "verification_result", "proof_fingerprint",
            },
        )
        self.assertEqual(proof.verification_result, "VERIFIED")
        self.assertEqual(
            proof.proof_fingerprint,
            fingerprint(
                "r2-local-source-proof-v1",
                {key: value for key, value in proof.to_mapping().items()
                 if key != "proof_fingerprint"},
            ),
        )
        self.assertEqual(
            LocalSourceProofV1.from_json(
                proof.to_canonical_json()
            ).to_canonical_json(),
            proof.to_canonical_json(),
        )

    def test_local_source_proof_rejects_generic_or_empty_subjects(self) -> None:
        generic = fingerprint(
            "r2-solo-maintainer-closure-evidence-v1",
            {"source": "closure_map", "final_master_binding_fingerprint": "d" * 64,
             "source_package_fingerprint": "b" * 64},
        )
        for subjects in (
            (),
            (("source", generic),),
            (("canonical:frozen_remote_master", "c" * 64),),
        ):
            with self.subTest(subjects=subjects), self.assertRaises(
                SoloMaintainerClosureError
            ):
                LocalSourceProofV1.create(
                    source="closure_map",
                    proof_kind="CANONICAL_DERIVATION",
                    final_commit_oid="1" * 40,
                    final_tree_oid="a" * 40,
                    source_package_fingerprint="b" * 64,
                    subject_fingerprints=subjects,
                )
        with self.assertRaises(SoloMaintainerClosureError):
            LocalSourceProofV1.create(
                source="closure_map",
                proof_kind="FROZEN_GIT_OBJECT_CONTRACT",
                final_commit_oid="1" * 40,
                final_tree_oid="a" * 40,
                source_package_fingerprint="b" * 64,
                subject_fingerprints=(("canonical:closure_map", "c" * 64),),
            )

    def test_local_source_proof_kinds_and_hosted_subjects_are_exact(self) -> None:
        self.assertEqual(
            PROOF_KINDS,
            (
                "CANONICAL_DERIVATION", "FROZEN_GIT_OBJECT_CONTRACT",
                "HOSTED_CHECK_RECORD", "GITHUB_GUARDRAIL_SNAPSHOT",
                "HOSTED_TYPED_TEST_EXECUTION", "FRESH_LOCAL_OBSERVATION",
            ),
        )
        repository, github = _fixture()
        proofs = {item.source: item for item in build_local_source_proofs(
            repository, github, repository.root
        )}
        quality = proofs["quality_gate_review"]
        self.assertEqual(quality.proof_kind, "HOSTED_TYPED_TEST_EXECUTION")
        subjects = [item["subject"] for item in quality.subject_fingerprints]
        self.assertEqual(sum(name.startswith("blob:") for name in subjects), 4)
        self.assertEqual(sum(name == "hosted:quality-gates" for name in subjects), 1)
        self.assertEqual(sum(name.startswith("hosted:quality-gates:")
                             for name in subjects), 5)
        self.assertEqual(
            proofs["git_byte_state_receipt"].proof_kind,
            "HOSTED_TYPED_TEST_EXECUTION",
        )
        fresh_process_subjects = {
            item["subject"] for item in proofs["fresh_process_suite"].subject_fingerprints
        }
        self.assertIn("hosted:windows-native-provenance", fresh_process_subjects)
        self.assertIn("hosted:windows-independent-provenance", fresh_process_subjects)
        self.assertIn("blob:backend/r2_ci_provenance_v2/suites.py",
                      fresh_process_subjects)
        self.assertIn("blob:tests/test_r2_ci_provenance_v2.py",
                      fresh_process_subjects)
        generated_status_subjects = {
            item["subject"] for item in proofs["generated_status"].subject_fingerprints
        }
        self.assertIn(
            "blob:docs/operations/project_status_log.md",
            generated_status_subjects,
        )

    def test_generated_status_equivalence_normalizes_only_dynamic_snapshot_fields(self) -> None:
        root = Path(__file__).resolve().parents[1]
        frozen = (root / "docs/operations/project_status_log.md").read_bytes().decode(
            "utf-8"
        )
        branch = next(line for line in frozen.splitlines()
                      if line.startswith("| Git branch | "))
        last_update = next(line for line in frozen.splitlines()
                           if line.startswith("last_update: "))
        generated_on = next(line for line in frozen.splitlines()
                            if line.startswith("| Generated on | "))
        alternate_date = "2000-01-01"
        updated = frozen.replace(last_update, f"last_update: {alternate_date}", 1)
        updated = updated.replace(
            generated_on, f"| Generated on | {alternate_date} |", 1
        ).replace(branch, "| Git branch | not available |").replace("\r\n", "\n")
        self.status_builder.return_value = frozen
        baseline = local_evidence_adapter._fresh_subject(
            "generated_status", root, ("AGENTS.md",)
        )
        self.status_builder.return_value = updated
        self.assertEqual(
            local_evidence_adapter._fresh_subject(
                "generated_status", root, ("AGENTS.md",)
            ),
            baseline,
        )
        self.status_builder.return_value = updated.replace(
            "# Project Status Log", "# Project Status Claim"
        )
        with self.assertRaises(SoloMaintainerClosureError):
            local_evidence_adapter._fresh_subject(
                "generated_status", root, ("AGENTS.md",)
            )
        for invalid in (
            updated.replace(f"last_update: {alternate_date}\n", "", 1),
            updated.replace(
                "| Git branch | not available |",
                "| Git branch | bad|branch |",
            ),
            updated.replace(branch.replace("codex/issue-110-solo-maintainer-closure",
                                            "not available"), ""),
        ):
            self.status_builder.return_value = invalid
            with self.subTest(invalid=invalid[:30]), self.assertRaises(
                SoloMaintainerClosureError
            ):
                local_evidence_adapter._fresh_subject(
                    "generated_status", root, ("AGENTS.md",)
                )

    def test_fixed_repository_rejects_untracked_even_when_local_config_hides_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*arguments: str) -> None:
                subprocess.run(
                    ("git", *arguments), cwd=root, check=True, capture_output=True
                )

            git("init", "-q")
            git("config", "user.name", "Issue 110 Test")
            git("config", "user.email", "issue110@example.test")
            (root / "tracked.bin").write_bytes(b"tracked")
            git("add", "tracked.bin")
            git("commit", "-q", "-m", "test")
            git("update-ref", "refs/remotes/origin/master", "HEAD")
            git("config", "status.showUntrackedFiles", "no")
            (root / "untracked.bin").write_bytes(b"untracked")

            with patch.object(repository_adapter, "ROOT", root), patch.object(
                repository_adapter, "_tree_descriptors", side_effect=AssertionError
            ) as descriptors, self.assertRaises(SoloMaintainerClosureError) as caught:
                repository_adapter.FixedRepositoryPort().collect()
            self.assertEqual(caught.exception.code, ClosureErrorCode.MASTER_DRIFT)
            descriptors.assert_not_called()

    def test_fresh_observations_fail_closed_on_drift_or_unclassified_finding(self) -> None:
        root = Path(__file__).resolve().parents[1]
        tracked = ("AGENTS.md",)
        self.status_builder.return_value = "drift"
        with self.assertRaises(SoloMaintainerClosureError):
            local_evidence_adapter._fresh_subject("generated_status", root, tracked)
        self.status_builder.return_value = (
            root / "docs/operations/project_status_log.md"
        ).read_bytes().decode("utf-8")
        self.leakage_scan.return_value = (object(),)
        with self.assertRaises(SoloMaintainerClosureError):
            local_evidence_adapter._fresh_subject("repository_leakage_scan", root, tracked)
        from scripts.maintenance_scan import Finding
        self.maintenance_scan.return_value = [Finding(
            "low", "stale_doc", "docs/newly-stale.md", "fixed", "fixed",
            "docs/operations/cleanup_agent.md"
        )]
        with self.assertRaises(SoloMaintainerClosureError):
            local_evidence_adapter._fresh_subject("maintenance_scan_output", root, tracked)
        self.assertEqual(len(local_evidence_adapter._MAINTENANCE_CLASSIFICATIONS), 19)
        self.maintenance_scan.return_value = _classified_maintenance_findings(Finding)
        subject, observed = local_evidence_adapter._fresh_subject(
            "maintenance_scan_output", root, tracked
        )
        self.assertEqual(subject, "fresh:maintenance_scan_output")
        self.assertEqual(len(observed), 64)

    def test_maintenance_observation_requires_the_exact_classification_set(self) -> None:
        from scripts.maintenance_scan import Finding
        root = Path(__file__).resolve().parents[1]
        classified = _classified_maintenance_findings(Finding)
        for findings in ((), tuple(classified[:-1]), tuple(classified + classified[:1])):
            self.maintenance_scan.return_value = findings
            with self.subTest(count=len(findings)), self.assertRaises(
                SoloMaintainerClosureError
            ):
                local_evidence_adapter._fresh_subject(
                    "maintenance_scan_output", root, ("AGENTS.md",)
                )

    def test_hosted_steps_require_exact_unique_successful_job_metadata(self) -> None:
        repository, github = _fixture()
        by_job = {item.job_name: item for item in github.hosted_evidence}
        jobs = []
        for key in HOSTED_STEP_KEYS:
            job_name, step_name = key.split(":", 1)
            job = next((item for item in jobs if item["name"] == job_name), None)
            if job is None:
                job = {"id": by_job[job_name].job_id,
                       "name": job_name, "steps": []}
                jobs.append(job)
            job["steps"].append({"name": step_name, "number": len(job["steps"]) + 1,
                                 "status": "completed", "conclusion": "success"})
        values = hosted_step_fingerprints(tuple(by_job.values()), jobs)
        self.assertEqual(set(values), set(HOSTED_STEP_KEYS))
        jobs[0]["steps"][0]["conclusion"] = "failure"
        with self.assertRaises(SoloMaintainerClosureError):
            hosted_step_fingerprints(tuple(by_job.values()), jobs)
        jobs[0]["steps"][0]["conclusion"] = "success"
        jobs[0]["id"] += 1
        with self.assertRaises(SoloMaintainerClosureError):
            hosted_step_fingerprints(tuple(by_job.values()), jobs)
        jobs[0]["id"] -= 1
        with self.assertRaises(SoloMaintainerClosureError):
            hosted_step_fingerprints(tuple(by_job.values()), jobs, [dict(jobs[0])])

    def test_materialized_maintenance_path_matches_real_checkout_exactly(self) -> None:
        patch.stopall()
        from scripts import maintenance_scan, repository_leakage_scan
        root = Path(__file__).resolve().parents[1]
        tracked = tuple(sorted(repository_leakage_scan.list_git_tracked(root)))
        direct = maintenance_scan.collect_findings()
        materialized = local_evidence_adapter._materialized_findings(
            maintenance_scan, repository_leakage_scan, root, tracked
        )
        fields = tuple(maintenance_scan.Finding.__dataclass_fields__)
        normalize = lambda values: tuple(sorted(
            tuple(getattr(item, name) for name in fields) for item in values
        ))
        self.assertEqual(normalize(materialized), normalize(direct))

    def test_prepare_returns_exact_review_candidate_without_writing(self) -> None:
        repository, github = _fixture()
        ports = _ports(repository, github, wall=(1_000,), monotonic=(10_000,))

        with patch(
            "backend.r2_solo_maintainer_closure.closure._fixed_ports",
            return_value=ports,
        ):
            candidate = SoloMaintainerClosure().prepare()

        self.assertEqual(candidate.status, "AWAITING_SOLO_MAINTAINER_CONFIRMATION")
        self.assertEqual(candidate.confirmation_acknowledgement, ACK)
        self.assertEqual(candidate.confirmation_window_seconds, 300)
        self.assertEqual(candidate.expires_at_epoch, 1_300)
        self.assertEqual(candidate.confirmation_real_tty_required, 1)
        self.assertEqual(candidate.issue39_authority_count, 0)
        self.assertEqual(candidate.manifest["hosted_evidence_count"], 5)
        self.assertEqual(candidate.manifest["evidence_record_count"], 14)
        self.assertEqual(candidate.manifest["gap_proof_count"], 8)
        sources = [
            source
            for record in candidate.manifest["evidence_records"]
            for source in record["source_fingerprints"]
        ]
        self.assertTrue(all(set(item) == {"source", "proof_kind", "fingerprint"}
                            for item in sources))
        self.assertIn("quality_gate_review", {item["source"] for item in sources})
        self.assertNotIn("standards_review", {item["source"] for item in sources})
        self.assertEqual(
            [item["evidence_count"] for item in candidate.manifest["gap_proofs"]],
            [2, 1, 1, 1, 1, 1, 3, 4],
        )
        self.assertEqual(ports.storage.publications, [])
        self.assertEqual(
            SoloMaintainerClosureCandidateV1.from_json(
                candidate.to_canonical_json()
            ).to_canonical_json(),
            candidate.to_canonical_json(),
        )

    def test_confirm_freshly_rederives_and_publishes_exactly_two_files(self) -> None:
        repository, github = _fixture()
        ports = _ports(
            repository,
            github,
            repository_again=repository,
            github_again=github,
            wall=(1_000, 1_001, 1_001, 1_001),
            monotonic=(10_000, 20_000, 20_000, 20_000),
        )

        with patch(
            "backend.r2_solo_maintainer_closure.closure._fixed_ports",
            return_value=ports,
        ):
            closure = SoloMaintainerClosure()
            candidate = closure.prepare()
            receipt = closure.confirm(candidate.manifest_fingerprint, ACK)

        self.assertEqual(receipt.status, "SOLO_MAINTAINER_ATTESTATION_RECORDED")
        self.assertEqual(receipt.solo_maintainer_attestation_count, 1)
        self.assertEqual(receipt.confirmation_real_tty_count, 1)
        self.assertEqual(receipt.stdin_stdout_stderr_console_verified, 1)
        self.assertEqual(receipt.artifact_count, 2)
        self.assertEqual(receipt.created_count, 2)
        self.assertEqual(receipt.approval_count, 0)
        self.assertEqual(receipt.execution_authority_count, 0)
        self.assertEqual(receipt.issue39_authority_count, 0)
        self.assertEqual(len(ports.storage.publications), 1)
        manifest, stored_receipt, fingerprint = ports.storage.publications[0]
        self.assertEqual(fingerprint, candidate.manifest_fingerprint)
        self.assertEqual(manifest, candidate.manifest_value.to_canonical_json())
        self.assertEqual(stored_receipt, receipt.to_canonical_json())
        self.assertEqual(ports.repository.calls, 3)
        self.assertEqual(ports.github.calls, 3)

    def test_confirm_rejects_fingerprint_acknowledgement_tty_and_staleness(self) -> None:
        cases = (
            ("f" * 64, ACK, True, (1_000, 1_001), ClosureErrorCode.FINGERPRINT_REJECTED),
            (None, ACK.lower(), True, (1_000, 1_001), ClosureErrorCode.ACKNOWLEDGEMENT_REJECTED),
            (None, ACK, False, (1_000, 1_001), ClosureErrorCode.TTY_REQUIRED),
            (None, ACK, True, (1_000, 1_300), ClosureErrorCode.STALE),
        )
        for fingerprint, acknowledgement, tty, wall, expected in cases:
            with self.subTest(expected=expected.value):
                repository, github = _fixture()
                ports = _ports(
                    repository,
                    github,
                    repository_again=repository,
                    github_again=github,
                    wall=wall,
                    monotonic=(10_000, 20_000),
                    tty=tty,
                )
                with patch(
                    "backend.r2_solo_maintainer_closure.closure._fixed_ports",
                    return_value=ports,
                ):
                    closure = SoloMaintainerClosure()
                    candidate = closure.prepare()
                    supplied = fingerprint or candidate.manifest_fingerprint
                    with self.assertRaises(SoloMaintainerClosureError) as caught:
                        closure.confirm(supplied, acknowledgement)
                self.assertEqual(caught.exception.code, expected)
                self.assertEqual(ports.storage.publications, [])

    def test_confirm_rejects_any_fresh_repository_or_github_drift(self) -> None:
        repository, github = _fixture()
        drifted_repository, _unused = _fixture(commit="2" * 40)
        _unused_repository, drifted_github = _fixture(ruleset_id=778)
        cases = (
            (drifted_repository, github, ClosureErrorCode.MASTER_DRIFT),
            (repository, drifted_github, ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED),
        )
        for fresh_repository, fresh_github, expected in cases:
            with self.subTest(expected=expected.value):
                ports = _ports(
                    repository,
                    github,
                    repository_again=fresh_repository,
                    github_again=fresh_github,
                    wall=(1_000, 1_001),
                    monotonic=(10_000, 20_000),
                )
                with patch(
                    "backend.r2_solo_maintainer_closure.closure._fixed_ports",
                    return_value=ports,
                ):
                    closure = SoloMaintainerClosure()
                    candidate = closure.prepare()
                    with self.assertRaises(SoloMaintainerClosureError) as caught:
                        closure.confirm(candidate.manifest_fingerprint, ACK)
                self.assertEqual(caught.exception.code, expected)
                self.assertEqual(ports.storage.publications, [])

    def test_confirm_rechecks_both_clocks_after_fresh_evidence_derivation(self) -> None:
        repository, github = _fixture()
        ports = _ports(
            repository, github, repository_again=repository, github_again=github,
            wall=(1_000, 1_001, 1_300),
            monotonic=(10_000, 20_000, 300_000_010_000),
        )
        with patch(
            "backend.r2_solo_maintainer_closure.closure._fixed_ports",
            return_value=ports,
        ):
            closure = SoloMaintainerClosure()
            candidate = closure.prepare()
            with self.assertRaises(SoloMaintainerClosureError) as caught:
                closure.confirm(candidate.manifest_fingerprint, ACK)
        self.assertEqual(caught.exception.code, ClosureErrorCode.STALE)
        self.assertEqual(ports.storage.publications, [])

    def test_storage_commit_callback_failure_retains_stage_without_target(self) -> None:
        fingerprint_value = "7" * 64
        manifest, receipt = b"manifest", b"receipt"

        def commit(source, target, identity, payloads, before_commit):
            self.assertEqual(payloads, (manifest, receipt))
            before_commit(*payloads)

        def reject(_manifest: bytes, _receipt: bytes) -> None:
            raise SoloMaintainerClosureError(ClosureErrorCode.MASTER_DRIFT)

        with tempfile.TemporaryDirectory() as directory:
            common = Path(directory)
            stage = common / (
                ".r2-solo-maintainer-closure-v1.stage-" + fingerprint_value
            )
            target = common / "r2-solo-maintainer-closure-v1"
            with patch.object(storage_adapter, "_git_common_dir", return_value=common), \
                    patch.object(storage_adapter, "_commit_no_replace", side_effect=commit), \
                    self.assertRaises(SoloMaintainerClosureError) as caught:
                storage_adapter.CreateOnlyClosureStorage().publish(
                    manifest, receipt, fingerprint_value, reject
                )
            self.assertEqual(caught.exception.code, ClosureErrorCode.MASTER_DRIFT)
            self.assertTrue(stage.is_dir())
            self.assertFalse(target.exists())

    def test_contract_parsing_rejects_noncanonical_extra_and_duplicate_fields(self) -> None:
        repository, github = _fixture()
        ports = _ports(repository, github, wall=(1_000,), monotonic=(10_000,))
        with patch(
            "backend.r2_solo_maintainer_closure.closure._fixed_ports",
            return_value=ports,
        ):
            payload = SoloMaintainerClosure().prepare().to_canonical_json()
        mapping = SoloMaintainerClosureCandidateV1.from_json(payload).to_mapping()
        mapping["extra"] = 0
        malformed = str(mapping).encode("utf-8")
        duplicate = payload[:-1] + b',"status":"x"}'
        for rejected in (b" " + payload, malformed, duplicate):
            with self.subTest(payload=rejected[:20]), self.assertRaises(
                SoloMaintainerClosureError
            ):
                SoloMaintainerClosureCandidateV1.from_json(rejected)

    def test_manifest_rejects_forged_nested_production_and_gap_links(self) -> None:
        repository, github = _fixture()
        ports = _ports(repository, github, wall=(1_000,), monotonic=(10_000,))
        with patch(
            "backend.r2_solo_maintainer_closure.closure._fixed_ports",
            return_value=ports,
        ):
            manifest = SoloMaintainerClosure().prepare().manifest_value
        for change in ("production", "gap"):
            mapping = manifest.to_mapping()
            if change == "production":
                mapping["production_binding"]["unexpected"] = 0
            else:
                mapping["gap_proofs"][0]["evidence_fingerprints"][0] = "9" * 64
                mapping["gap_proof_set_fingerprint"] = fingerprint(
                    "r2-solo-maintainer-closure-evidence-set-v1",
                    {"set_type": "SoloMaintainerClosureGapProofSetV1",
                     "gap_proofs": mapping["gap_proofs"]},
                )
            body = {key: value for key, value in mapping.items()
                    if key != "manifest_fingerprint"}
            mapping["manifest_fingerprint"] = fingerprint(
                "r2-solo-maintainer-closure-manifest-v1", body
            )
            with self.subTest(change=change), self.assertRaises(
                SoloMaintainerClosureError
            ):
                SoloMaintainerClosureManifestV1.from_json(canonical_json(mapping))

    def test_receipt_parser_rejects_expired_confirmation_even_when_rehashed(self) -> None:
        repository, github = _fixture()
        ports = _ports(
            repository, github, repository_again=repository, github_again=github,
            wall=(1_000, 1_001, 1_001, 1_001),
            monotonic=(10_000, 20_000, 20_000, 20_000),
        )
        with patch(
            "backend.r2_solo_maintainer_closure.closure._fixed_ports",
            return_value=ports,
        ):
            closure = SoloMaintainerClosure()
            candidate = closure.prepare()
            receipt = closure.confirm(candidate.manifest_fingerprint, ACK)
        mapping = receipt.to_mapping()
        mapping["confirmed_at_epoch"] = mapping["expires_at_epoch"]
        body = {key: value for key, value in mapping.items()
                if key != "receipt_fingerprint"}
        mapping["receipt_fingerprint"] = fingerprint(
            "r2-solo-maintainer-attestation-receipt-v1", body
        )
        with self.assertRaises(SoloMaintainerClosureError):
            SoloMaintainerAttestationReceiptV1.from_json(canonical_json(mapping))

    def test_guardrail_collection_requires_only_one_ruleset_covering_master(self) -> None:
        configuration = ruleset_configuration_v1()
        listing_path = (
            "/repos/Toby0918/email-ai-assistant/rulesets?ref=refs/heads/master"
            "&includes_parents=false&per_page=100"
        )

        def get_json(path: str, allow_missing: bool = False) -> object:
            if path == listing_path:
                return [
                    {"id": 777, "target": "branch", "enforcement": "active",
                     "name": "master-solo-maintainer-closure-v1"},
                    {"id": 778, "target": "branch", "enforcement": "active",
                     "name": "unexpected-layer"},
                ]
            if path.endswith("/rulesets/777"):
                return configuration
            if path.endswith("/branches/master/protection") and allow_missing:
                return None
            raise AssertionError(path)

        with patch.object(repository_adapter, "_get_json", side_effect=get_json), \
                self.assertRaises(SoloMaintainerClosureError) as caught:
            repository_adapter._guardrail_snapshot()
        self.assertEqual(caught.exception.code, ClosureErrorCode.GITHUB_GUARDRAIL_REJECTED)

    def test_hosted_record_rejects_non_rfc3339_timestamps(self) -> None:
        with self.assertRaises(SoloMaintainerClosureError):
            HostedCheckEvidenceV1.create(
                workflow_path=FIXED_CHECKS[0][1], workflow_blob_oid="e" * 40,
                workflow_run_id=1, workflow_run_number=1, workflow_run_attempt=1,
                job_name=FIXED_CHECKS[0][0], job_id=1, check_run_id=1,
                head_sha="1" * 40, started_at_utc="Z", completed_at_utc="Z",
            )

    def test_repository_rejects_hidden_index_flags_and_checkout_byte_drift(self) -> None:
        content = b"tracked exact bytes\n"
        framed = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
        oid = hashlib.sha1(framed).hexdigest()
        descriptor = (("tracked.txt", "100644", oid, content),)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_bytes(content)
            staged = f"100644 {oid} 0\ttracked.txt\0".encode("ascii")
            for flags, replacement in ((b"S tracked.txt\0", content),
                                       (b"H tracked.txt\0", b"drift\n")):
                (root / "tracked.txt").write_bytes(replacement)

                def git(*arguments: str) -> bytes:
                    return staged if "--stage" in arguments else flags

                with self.subTest(flags=flags[:1], replacement=replacement), \
                        patch.object(repository_adapter, "ROOT", root), \
                        patch.object(repository_adapter, "_git", side_effect=git), \
                        self.assertRaises(SoloMaintainerClosureError):
                    repository_adapter._require_index_and_checkout(descriptor)

    def test_reconciliation_graph_needs_exactly_three_provenance_jobs(self) -> None:
        valid = (
            b"jobs:\n  provenance-reconciliation:\n    needs:\n"
            b"      - portable-provenance\n      - windows-native-provenance\n"
            b"      - windows-independent-provenance\n    runs-on: ubuntu-24.04\n"
        )
        repository_adapter._require_reconciliation_graph(valid)
        with self.assertRaises(SoloMaintainerClosureError):
            repository_adapter._require_reconciliation_graph(
                valid.replace(b"    runs-on:", b"      - unexpected-job\n    runs-on:")
            )

    def test_hosted_record_uses_exact_attempt_job_check_run_link(self) -> None:
        repository, _github = _fixture()
        run = {"id": 40, "run_number": 4, "run_attempt": 2,
               "head_sha": "1" * 40}
        jobs = [{"id": 50, "name": "quality-gates", "status": "completed",
                 "conclusion": "success", "started_at": "2026-08-06T01:00:00Z",
                 "completed_at": "2026-08-06T01:01:00Z",
                 "check_run_url": (
                     "https://api.github.com/repos/Toby0918/email-ai-assistant/"
                     "check-runs/60") }]
        check = {"id": 60, "name": "quality-gates", "status": "completed",
                 "conclusion": "success", "head_sha": "1" * 40,
                 "app": {"id": 15368, "slug": "github-actions"}}
        older_same_name = {**check, "id": 59}
        record = repository_adapter._record_from_run(
            run, FIXED_CHECKS[0], repository, jobs, {59: older_same_name, 60: check}
        )
        self.assertEqual(record.check_run_id, 60)

    def test_jobs_are_read_from_exact_selected_attempt(self) -> None:
        run = {"id": 40, "run_attempt": 2}
        expected = (
            "/repos/Toby0918/email-ai-assistant/actions/runs/40/attempts/2/"
            "jobs?per_page=100"
        )
        with patch.object(
            repository_adapter, "_get_json",
            side_effect=lambda path: {"total_count": 0, "jobs": []}
            if path == expected else (_ for _ in ()).throw(AssertionError(path)),
        ):
            self.assertEqual(repository_adapter._jobs_for_run(run), [])


def _classified_maintenance_findings(finding_type):
    return [
        finding_type(
            severity, category, path, "fixed", "fixed", doc
        )
        for severity, category, path, doc in sorted(
            local_evidence_adapter._MAINTENANCE_CLASSIFICATIONS
        )
    ]


def _ports(
    repository: RepositorySnapshotV1,
    github: GitHubEvidenceSnapshotV1,
    *,
    repository_again: RepositorySnapshotV1 | None = None,
    github_again: GitHubEvidenceSnapshotV1 | None = None,
    wall: tuple[int, ...],
    monotonic: tuple[int, ...],
    tty: bool = True,
) -> SimpleNamespace:
    repository_values = (repository,) if repository_again is None else (
        repository, repository_again, repository_again,
    )
    github_values = (github,) if github_again is None else (
        github, github_again, github_again,
    )
    return SimpleNamespace(
        repository=_FakePort(*repository_values),
        github=_FakePort(*github_values),
        storage=_FakeStorage(),
        console=_FakeConsole(tty),
        clock=_FakeClock(wall, monotonic),
    )


def _fixture(
    *, commit: str = "1" * 40, ruleset_id: int = 777
) -> tuple[RepositorySnapshotV1, GitHubEvidenceSnapshotV1]:
    binding = FinalMasterBindingV1.create(
        final_commit_oid=commit,
        final_tree_oid="a" * 40,
        source_package_fingerprint="b" * 64,
        runbook_fingerprint="c" * 64,
        workflow_fingerprint="d" * 64,
    )
    production = build_production_binding_candidate_v1(
        final_master_binding=binding
    )
    sources = {name: hashlib.sha256(("subject:" + name).encode("ascii")).hexdigest()
               for name in repository_subject_names()}
    repository = RepositorySnapshotV1.create(
        final_master_binding=binding,
        production_binding=production,
        source_fingerprints=sources,
        workflow_blob_oids={
            ".github/workflows/agent_guardrails.yml": "e" * 40,
            ".github/workflows/r2_provenance.yml": "f" * 40,
        },
        tracked_paths=tuple(sorted(
            name.removeprefix("blob:") for name in repository_subject_names()
            if name.startswith("blob:")
        )),
    )
    records = tuple(
        HostedCheckEvidenceV1.create(
            workflow_path=path,
            workflow_blob_oid=repository.workflow_blob_oid(path),
            workflow_run_id=100 if name == "quality-gates" else 200,
            workflow_run_number=10 if name == "quality-gates" else 20,
            workflow_run_attempt=1,
            job_name=name,
            job_id=index,
            check_run_id=index,
            head_sha=commit,
            started_at_utc="2026-08-06T01:00:00Z",
            completed_at_utc="2026-08-06T01:01:00Z",
        )
        for index, (name, path) in enumerate(FIXED_CHECKS, start=1)
    )
    configuration = ruleset_configuration_v1()
    guardrail = GitHubGuardrailSnapshotV1.create(
        ruleset_id=ruleset_id,
        ruleset_configuration=configuration,
    )
    github = GitHubEvidenceSnapshotV1.create(
        remote_commit_oid=commit,
        hosted_evidence=records,
        github_guardrail_snapshot=guardrail,
        hosted_step_fingerprints={
            name: hashlib.sha256(("step:" + name).encode("ascii")).hexdigest()
            for name in HOSTED_STEP_KEYS
        },
    )
    return repository, github


if __name__ == "__main__":
    unittest.main()
