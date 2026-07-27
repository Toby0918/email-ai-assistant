"""Content-free projection from native metadata into portable evidence."""

from .contracts import HostObjectKind, HostObjectObservationV1
from .windows_api import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    _NativeObservation,
    _text_fingerprint,
    _volume_fingerprint,
)


ROOT_PARENT_FINGERPRINT = _text_fingerprint(
    "real-host-volume-root-parent-v1"
)


def to_host_observation(
    native: _NativeObservation,
    parent_identity_fingerprint: str,
) -> HostObjectObservationV1:
    is_directory = bool(native.file_attributes & FILE_ATTRIBUTE_DIRECTORY)
    kind = HostObjectKind.DIRECTORY if is_directory else HostObjectKind.FILE
    return HostObjectObservationV1.create(
        volume_fingerprint=_volume_fingerprint(native.volume_serial_number),
        file_id_128=native.file_id_128.hex(),
        object_kind=kind,
        parent_identity_fingerprint=parent_identity_fingerprint,
        normalized_name_fingerprint=_text_fingerprint(native.normalized_path),
        filesystem_name=native.filesystem_name,
        file_attributes=native.file_attributes,
        reparse_tag=native.reparse_tag,
        has_reparse_point=bool(
            native.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        ),
    )
