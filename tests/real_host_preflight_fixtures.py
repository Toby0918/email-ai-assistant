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
from backend.real_host_preflight.canonical import (
    is_fingerprint,
    role_selection_fingerprint,
)
from tests.cutover_contract_fixtures import (
    opaque_fingerprint,
    valid_profile_body,
)


GOVERNING_MASTER = "aa84c92639786d77673b9a94360210dc5d0b9287"
OBSERVED_AT = 1_800_000_100


def valid_profile() -> CutoverProfileV1:
    return profile_for_role_names(
        source_root=opaque_fingerprint(322),
        target_parent=opaque_fingerprint(321),
        finance_root=opaque_fingerprint(323),
        target_absence=opaque_fingerprint(404),
    )


def profile_for_role_names(
    *,
    source_root: object,
    target_parent: object,
    finance_root: object,
    target_absence: object,
) -> CutoverProfileV1:
    names = {
        "source_root": _normalized_name(source_root),
        "target_parent": _normalized_name(target_parent),
        "finance_root": _normalized_name(finance_root),
        "target_absence": _normalized_name(target_absence),
    }
    body = valid_profile_body()
    body["governing_master_commit"] = GOVERNING_MASTER
    role_selections = body["role_selections"]
    profile_roles = {
        "source_root": "repository_root",
        "target_parent": "projects_parent",
        "finance_root": "finance_project",
        "target_absence": "project_container",
    }
    for role, profile_role in profile_roles.items():
        role_selections[profile_role] = role_selection_fingerprint(
            role,
            names[role],
        )
    return CutoverProfileV1.create(body)


def _normalized_name(value: object) -> str:
    if is_fingerprint(value):
        return value
    if type(value) in (
        HostObjectObservationV1,
        MissingHostObjectObservationV1,
    ) and is_fingerprint(value.normalized_name_fingerprint):
        return value.normalized_name_fingerprint
    raise ValueError("synthetic normalized name fingerprint required")


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


def topology_callbacks(
    calls: list[str],
    *,
    components: dict[str, object] | None = None,
) -> CurrentTopologyCallbacks:
    selected = components or topology_components()
    return CurrentTopologyCallbacks(
        source_root=OrderedReader(
            "source_root", selected["source_root"], calls
        ),
        target_parent=OrderedReader(
            "target_parent", selected["target_parent"], calls
        ),
        finance_root=OrderedReader(
            "finance_root", selected["finance_root"], calls
        ),
        target_absence=OrderedReader(
            "target_absence", selected["target_absence"], calls
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


class MutatingReader:
    """A synthetic callback that mutates one caller-owned object first."""

    def __init__(
        self,
        target: object,
        field: str,
        value: object,
        reader: Callable[[], object],
    ) -> None:
        self._target = target
        self._field = field
        self._value = value
        self._reader = reader

    def __call__(self) -> object:
        object.__setattr__(self._target, self._field, self._value)
        return self._reader()


ReaderFactory = Callable[[str, object, list[str]], OrderedReader]
