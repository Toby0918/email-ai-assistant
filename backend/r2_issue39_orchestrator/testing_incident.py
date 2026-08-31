"""Test-owned Windows fixture for the incident disposition adapter."""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from backend.cutover_host_mutation.windows_handles import (
    FILE_READ_ATTRIBUTES,
    READ_CONTROL,
    WRITE_DAC,
    WindowsHandleApi,
)
from .incident_binding import _ArtifactBinding, _IncidentBinding
from .archive_parent_windows import (
    _observe_archive_parent_readiness_v1,
    _provision_archive_parent_v1,
)
from .incident_windows import (
    _capture_dacl_sddl,
    _dispose_incident_stage_v1,
    _set_dacl,
)


_PAYLOADS = (
    ("solo-maintainer-attestation-receipt-v1.json", b"synthetic-receipt\n"),
    ("solo-maintainer-closure-manifest-v1.json", b"synthetic-manifest\n"),
)
_SOURCE_DACL = "D:PAI(A;;0x1200a9;;;WD)"


class SyntheticIncidentStageV1:
    __slots__ = (
        "_owner",
        "source",
        "destination",
        "binding",
        "_collision",
        "_source_sddl",
    )

    def __init__(self, *args, **kwargs):
        raise TypeError("SyntheticIncidentStageV1 requires create()")

    @classmethod
    def create(
        cls,
        *,
        destination_collision=False,
        artifact_drift=False,
        missing_destination_parent=False,
    ):
        owner = tempfile.TemporaryDirectory(prefix="issue39-incident-")
        root = Path(owner.name)
        source_parent = root / "source"
        destination_parent = (
            root / "archive-root" / "IncidentArchives"
            / "email_ai_assistant" / "issue38"
        )
        source_parent.mkdir()
        (root / "archive-root").mkdir()
        source = source_parent / ".fixed-stage"
        destination = destination_parent / ".fixed-stage"
        artifacts = _create_source(source, artifact_drift)
        _apply_sddl(source, _SOURCE_DACL)
        value = object.__new__(cls)
        value._owner = owner
        value.source = source
        value.destination = destination
        value.binding = _IncidentBinding(
            source,
            destination,
            root / "archive-root",
            ("IncidentArchives", "email_ai_assistant", "issue38"),
            tuple(artifacts),
            _SOURCE_DACL,
        )
        value._collision = destination_collision
        value._source_sddl = _SOURCE_DACL
        if not missing_destination_parent and not _provision_archive_parent_v1(
            value.binding
        ):
            value.close()
            raise RuntimeError("synthetic archive parent provisioning failed")
        if destination_collision:
            destination.mkdir()
            (destination / "competitor.bin").write_bytes(b"competitor\n")
        return value

    def dispose(self):
        readiness = _observe_archive_parent_readiness_v1(self.binding)
        return _dispose_incident_stage_v1(self.binding, readiness)

    def source_exists(self):
        return self.source.is_dir()

    def destination_exists(self):
        return self.destination.is_dir()

    def artifacts_match(self):
        return all(
            (self.destination / name).read_bytes() == payload
            for name, payload in _PAYLOADS
        )

    def final_dacl_matches(self):
        return _capture_sddl(self.destination) == self._source_sddl

    def source_dacl_restored(self):
        return _capture_sddl(self.source) == self._source_sddl

    def competitor_preserved(self):
        return (
            self._collision
            and (self.destination / "competitor.bin").read_bytes()
            == b"competitor\n"
        )

    def close(self):
        for path in (self.source, self.destination):
            if path.exists():
                try:
                    _apply_sddl(path, "D:P(A;OICI;FA;;;WD)")
                    for child in path.iterdir():
                        _apply_sddl(child, "D:P(A;;FA;;;WD)")
                except Exception:
                    pass
        current = self.binding.archive_anchor
        archive_paths = []
        for component in self.binding.archive_components:
            current /= component
            archive_paths.append(current)
        for path in reversed(archive_paths):
            if path.exists():
                try:
                    _apply_sddl(path, "D:P(A;OICI;FA;;;WD)")
                except Exception:
                    pass
        self._owner.cleanup()


def _apply_sddl(path, sddl):
    api = WindowsHandleApi()
    handle = api.open_existing(
        path,
        access=READ_CONTROL | WRITE_DAC | FILE_READ_ATTRIBUTES,
        share_delete=True,
    )
    try:
        _set_dacl(handle, sddl)
    finally:
        api.close(handle)


def _create_source(source, artifact_drift):
    source.mkdir()
    artifacts = []
    for name, payload in _PAYLOADS:
        artifact_path = source / name
        artifact_path.write_bytes(payload)
        if artifact_drift and name == _PAYLOADS[0][0]:
            artifact_path.write_bytes(b"drift\n")
        _apply_sddl(artifact_path, "D:P(A;;GR;;;WD)")
        artifacts.append(
            _ArtifactBinding(
                name,
                len(payload),
                hashlib.sha256(payload).hexdigest(),
            )
        )
    return artifacts


def _capture_sddl(path):
    api = WindowsHandleApi()
    handle = api.open_existing(
        path,
        access=READ_CONTROL | FILE_READ_ATTRIBUTES,
        share_delete=True,
    )
    try:
        return _capture_dacl_sddl(handle)
    finally:
        api.close(handle)
