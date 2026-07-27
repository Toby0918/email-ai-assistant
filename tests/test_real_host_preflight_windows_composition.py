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
    TestSandboxScopeV1,
    WindowsReadOnlyObserver,
    run_current_topology_preflight,
)
from tests.cutover_contract_fixtures import opaque_fingerprint
from tests.real_host_preflight_fixtures import (
    OBSERVED_AT,
    sandbox_authorization,
    valid_profile,
)


@unittest.skipUnless(sys.platform == "win32", "Windows integration only")
class WindowsPreflightCompositionTests(unittest.TestCase):
    def test_target_appearance_before_fresh_gate_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            layout = _SandboxLayout.create(Path(temporary))
            callbacks = layout.callbacks()
            topology_receipt = _run_preflight(callbacks)
            profile = valid_profile()
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
                _run_preflight(callbacks)

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
                _run_preflight(callbacks)


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
    ) -> None:
        self.root = root
        self.parent = parent
        self.source = source
        self.finance = finance
        self.target = target
        self.retired_parent = root / "retired-projects"
        self.observer = observer
        self.volume_fingerprint = volume_fingerprint

    @classmethod
    def create(cls, root: Path) -> _SandboxLayout:
        parent = root / "projects"
        source = parent / "source"
        finance = parent / "finance"
        source.mkdir(parents=True)
        finance.mkdir()
        profile = valid_profile()
        scope = TestSandboxScopeV1.create(
            root=root,
            authorization=sandbox_authorization(profile),
            observed_at_epoch=OBSERVED_AT,
        )
        observer = WindowsReadOnlyObserver(scope)
        volume = observer.observe_existing(
            parent,
            expected_kind=HostObjectKind.DIRECTORY,
        ).volume_fingerprint
        return cls(
            root,
            parent,
            source,
            finance,
            parent / "container",
            observer,
            volume,
        )

    def callbacks(
        self,
        *,
        source_reader=None,
        git_reader=None,
    ) -> CurrentTopologyCallbacks:
        return CurrentTopologyCallbacks(
            source_root=source_reader or (
                lambda: self._directory(self.source)
            ),
            target_parent=lambda: self._directory(self.parent),
            finance_root=lambda: self._directory(self.finance),
            target_absence=lambda: self.observer.observe_absent(
                self.target
            ),
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


def _run_preflight(callbacks: CurrentTopologyCallbacks) -> object:
    profile = valid_profile()
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
