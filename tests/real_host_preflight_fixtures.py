"""Synthetic content-free fixtures for Issue #53 tests."""

from __future__ import annotations

from collections.abc import Callable

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.real_host_preflight import (
    CurrentTopologyCallbacks,
    CurrentTopologyObservationV1,
    HostObjectKind,
    HostObjectObservationV1,
    HostCheckKind,
    MissingHostObjectObservationV1,
    OpaqueHostCheckV1,
    VolumeObservationV1,
)
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)


GOVERNING_MASTER = "aa84c92639786d77673b9a94360210dc5d0b9287"
OBSERVED_AT = 1_800_000_100


def valid_profile() -> CutoverProfileV1:
    body = valid_profile_body()
    body["governing_master_commit"] = GOVERNING_MASTER
    return CutoverProfileV1.create(body)


def sandbox_authorization(
    profile: CutoverProfileV1,
    *,
    phase: str = "current_topology_preflight",
    operation_fingerprint: str | None = None,
) -> TestSandboxAuthorizationV1:
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=(
            operation_fingerprint or opaque_fingerprint(201)
        ),
        phase=phase,
        expires_at_epoch=OBSERVED_AT + 300,
    )


def object_observation(
    index: int,
    *,
    parent_identity_fingerprint: str,
) -> HostObjectObservationV1:
    return HostObjectObservationV1.create(
        volume_fingerprint=opaque_fingerprint(301),
        file_id_128=f"{index:032x}",
        object_kind=HostObjectKind.DIRECTORY,
        parent_identity_fingerprint=parent_identity_fingerprint,
        normalized_name_fingerprint=opaque_fingerprint(320 + index),
        filesystem_name="NTFS",
        file_attributes=16,
        reparse_tag=0,
        has_reparse_point=False,
    )


def topology_components() -> dict[str, object]:
    parent = object_observation(
        1,
        parent_identity_fingerprint=opaque_fingerprint(401),
    )
    source = object_observation(
        2,
        parent_identity_fingerprint=parent.object_identity_fingerprint,
    )
    finance = object_observation(
        3,
        parent_identity_fingerprint=parent.object_identity_fingerprint,
    )
    absence = MissingHostObjectObservationV1.create(
        parent_identity_fingerprint=parent.object_identity_fingerprint,
        volume_fingerprint=opaque_fingerprint(301),
        normalized_name_fingerprint=opaque_fingerprint(404),
        filesystem_name="NTFS",
    )
    return {
        "source_root": source,
        "target_parent": parent,
        "finance_root": finance,
        "target_absence": absence,
    }


def topology_observation() -> CurrentTopologyObservationV1:
    return CurrentTopologyObservationV1.create(
        **topology_components(),
        git_fingerprint=opaque_fingerprint(405),
        acl_fingerprint=opaque_fingerprint(406),
        volume_fingerprint=opaque_fingerprint(301),
        complete=True,
        content_observed=False,
        controlled_components_reparse_free=True,
    )


def topology_callbacks(calls: list[str]) -> CurrentTopologyCallbacks:
    components = topology_components()
    return CurrentTopologyCallbacks(
        source_root=OrderedReader(
            "source_root", components["source_root"], calls
        ),
        target_parent=OrderedReader(
            "target_parent", components["target_parent"], calls
        ),
        finance_root=OrderedReader(
            "finance_root", components["finance_root"], calls
        ),
        target_absence=OrderedReader(
            "target_absence", components["target_absence"], calls
        ),
        git=OrderedReader(
            "git",
            OpaqueHostCheckV1.create(
                kind=HostCheckKind.GIT,
                fingerprint=opaque_fingerprint(405),
                complete=True,
                content_observed=False,
            ),
            calls,
        ),
        acl=OrderedReader(
            "acl",
            OpaqueHostCheckV1.create(
                kind=HostCheckKind.ACL,
                fingerprint=opaque_fingerprint(406),
                complete=True,
                content_observed=False,
            ),
            calls,
        ),
        volume=OrderedReader(
            "volume",
            VolumeObservationV1.create(
                volume_fingerprint=opaque_fingerprint(301),
                filesystem_name="NTFS",
                drive_type="fixed",
                complete=True,
            ),
            calls,
        ),
    )


class OrderedReader:
    """One deterministic zero-argument callback with a call trace."""

    def __init__(
        self,
        name: str,
        value: object,
        calls: list[str],
    ) -> None:
        self._name = name
        self._value = value
        self._calls = calls

    def __call__(self) -> object:
        self._calls.append(self._name)
        return self._value


ReaderFactory = Callable[[str, object, list[str]], OrderedReader]
