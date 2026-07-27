"""Windows sandbox races at the complete Issue #53 composition seam."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from backend.real_host_preflight import (
    CurrentTopologyCallbacks,
    HostCheckKind,
    HostObjectKind,
    OpaqueHostCheckV1,
    PreMutationGate,
    run_current_topology_preflight,
)
from backend.real_host_preflight.windows_observation import (
    TestSandboxScopeV1,
    WindowsReadOnlyObserver,
    _issue_test_sandbox_permit,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    profile_for_role_names,
    sandbox_authorization,
    valid_profile,
)


@unittest.skipUnless(sys.platform == "win32", "Windows integration only")
class WindowsPreflightCompositionTests(unittest.TestCase):
    def test_target_appearance_before_fresh_gate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = _SandboxLayout.create(Path(temporary))
            callbacks = layout.callbacks()
            topology_receipt = _run_preflight(callbacks, layout.profile)
            profile = layout.profile
            operation = opaque_fingerprint(201)
            gate = PreMutationGate.bind(
                current_topology_receipt=topology_receipt,
                callbacks=callbacks,
                policy_fingerprint=opaque_fingerprint(407),
            )
            layout.target.mkdir()

            with self.assertRaisesRegex(
                ValueError,
                "^REAL_HOST_GATE_REJECTED$",
            ):
                gate.evaluate(
                    profile=profile,
                    authorization=sandbox_authorization(
                        profile,
                        operation_fingerprint=operation,
                    ),
                    operation_fingerprint=operation,
                    nonce="123e4567-e89b-42d3-a456-426614174000",
                    observed_at_epoch=OBSERVED_AT + 1,
                )

    def test_parent_replacement_between_complete_passes_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = _SandboxLayout.create(Path(temporary))
            callbacks = layout.callbacks(
                source_reader=_ReplacingSourceReader(layout)
            )

            with self.assertRaisesRegex(
                ValueError,
                "^REAL_HOST_TOPOLOGY_REJECTED$",
            ):
                _run_preflight(callbacks, layout.profile)

            self.assertTrue(layout.retired_parent.is_dir())
            self.assertTrue(layout.parent.is_dir())

    def test_git_drift_between_complete_passes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = _SandboxLayout.create(Path(temporary))
            callbacks = layout.callbacks(git_reader=_DriftingGitReader())

            with self.assertRaisesRegex(
                ValueError,
                "^REAL_HOST_TOPOLOGY_REJECTED$",
            ):
                _run_preflight(callbacks, layout.profile)

    def test_existing_target_cannot_be_hidden_by_decoy_absence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = _SandboxLayout.create(Path(temporary))
            layout.target.mkdir()
            decoy = layout.parent / "decoy-missing"
            callbacks = layout.callbacks(
                target_absence_reader=(
                    lambda: layout.observer.observe_absent(decoy)
                ),
            )

            with self.assertRaisesRegex(
                ValueError,
                "^REAL_HOST_TOPOLOGY_REJECTED$",
            ):
                _run_preflight(callbacks, layout.profile)


class _SandboxLayout:
    def __init__(
        self,
        root: Path,
        parent: Path,
        source: Path,
        finance: Path,
        target: Path,
        observer: WindowsReadOnlyObserver,
        volume_fingerprint: str,
        profile,
    ) -> None:
        self.root = root
        self.parent = parent
        self.source = source
        self.finance = finance
        self.target = target
        self.retired_parent = root / "retired-projects"
        self.observer = observer
        self.volume_fingerprint = volume_fingerprint
        self.profile = profile

    @classmethod
    def create(cls, root: Path) -> _SandboxLayout:
        parent = root / "projects"
        source = parent / "source"
        finance = parent / "finance"
        source.mkdir(parents=True)
        finance.mkdir()
        profile = valid_profile()
        marker = root / ".codex-preflight-test-sandbox"
        marker.touch()
        permit = _issue_test_sandbox_permit(
            root=root,
            marker=marker,
            authorization=sandbox_authorization(profile),
            observed_at_epoch=OBSERVED_AT,
        )
        scope = TestSandboxScopeV1.create(permit=permit)
        observer = WindowsReadOnlyObserver(scope)
        parent_observation = observer.observe_existing(
            parent,
            expected_kind=HostObjectKind.DIRECTORY,
        )
        source_observation = observer.observe_existing(
            source,
            expected_kind=HostObjectKind.DIRECTORY,
        )
        finance_observation = observer.observe_existing(
            finance,
            expected_kind=HostObjectKind.DIRECTORY,
        )
        absence_observation = observer.observe_absent(parent / "container")
        profile = profile_for_role_names(
            source_root=source_observation,
            target_parent=parent_observation,
            finance_root=finance_observation,
            target_absence=absence_observation,
        )
        return cls(
            root,
            parent,
            source,
            finance,
            parent / "container",
            observer,
            parent_observation.volume_fingerprint,
            profile,
        )

    def callbacks(
        self,
        *,
        source_reader=None,
        git_reader=None,
        target_absence_reader=None,
    ) -> CurrentTopologyCallbacks:
        return CurrentTopologyCallbacks(
            source_root=source_reader or (
                lambda: self._directory(self.source)
            ),
            target_parent=lambda: self._directory(self.parent),
            finance_root=lambda: self._directory(self.finance),
            target_absence=target_absence_reader
            or (lambda: self.observer.observe_absent(self.target)),
            git=git_reader or (
                lambda: _check(HostCheckKind.GIT, 405)
            ),
            acl=lambda: _check(HostCheckKind.ACL, 406),
            volume=lambda: self.observer.observe_volume(self.parent),
        )

    def _directory(self, path: Path):
        return self.observer.observe_existing(
            path,
            expected_kind=HostObjectKind.DIRECTORY,
            expected_volume_fingerprint=self.volume_fingerprint,
        )


class _ReplacingSourceReader:
    def __init__(self, layout: _SandboxLayout) -> None:
        self._layout = layout
        self._calls = 0

    def __call__(self):
        self._calls += 1
        if self._calls == 2:
            self._layout.parent.rename(self._layout.retired_parent)
            self._layout.parent.mkdir()
        return self._layout._directory(self._layout.source)


class _DriftingGitReader:
    def __init__(self) -> None:
        self._calls = 0

    def __call__(self) -> OpaqueHostCheckV1:
        self._calls += 1
        return _check(
            HostCheckKind.GIT,
            405 if self._calls == 1 else 499,
        )


def _check(kind: HostCheckKind, index: int) -> OpaqueHostCheckV1:
    return OpaqueHostCheckV1.create(
        kind=kind,
        fingerprint=opaque_fingerprint(index),
        complete=True,
        content_observed=False,
    )


def _run_preflight(callbacks: CurrentTopologyCallbacks, profile) -> object:
    operation = opaque_fingerprint(201)
    return run_current_topology_preflight(
        profile=profile,
        authorization=sandbox_authorization(
            profile,
            operation_fingerprint=operation,
        ),
        operation_fingerprint=operation,
        policy_fingerprint=opaque_fingerprint(407),
        observed_at_epoch=OBSERVED_AT,
        callbacks=callbacks,
    )


if __name__ == "__main__":
    unittest.main()
