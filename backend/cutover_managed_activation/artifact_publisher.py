"""Profile-bound create-only CRX byte publication."""

from __future__ import annotations

import hashlib
from pathlib import Path

from .windows_file_handles import (
    FILE_ATTRIBUTE_DIRECTORY,
    FILE_ATTRIBUTE_REPARSE_POINT,
    WindowsReadHandleApi,
)

from .canonical import canonical_json, fail
from .errors import ManagedActivationError
from .publication_scope import PublicationScopeWindow
from .receipts import CrxPublicationReceiptV1
from .scope_models import _SyntheticActivationScope

_ERROR = "crx_publication_failed"


class ArtifactPublisher:
    """Publish one exact reviewed CRX without browser or signing capability."""

    def __new__(cls, *args: object, **kwargs: object):
        raise TypeError("ArtifactPublisher exposes publish() only")

    @classmethod
    def publish(cls, *, scope: object) -> CrxPublicationReceiptV1:
        if type(scope) is not _SyntheticActivationScope:
            fail("crx_scope_invalid")
        api = WindowsReadHandleApi()
        handle = None
        try:
            source = scope.review.scenario.crx_source
            handle = api.open_existing(source, deny_write=True)
            original = api.observe(handle)
            return _publish_held(scope, api, handle, original)
        except ManagedActivationError:
            raise
        except Exception:
            fail(_ERROR)
        finally:
            if handle is not None:
                try:
                    api.close(handle)
                except Exception:
                    if not _exception_active():
                        fail(_ERROR)


def _publish_held(scope, api, handle, original):
    source = scope.review.scenario.crx_source
    _validate_source(scope, original)
    payload = _read_crx(source)
    source_hash = hashlib.sha256(payload).hexdigest()
    if (
        source_hash != scope.review.crx_sha256
        or len(payload) != scope.review.crx_size_bytes
        or _format_version(payload) != scope.review.crx_format_version
    ):
        fail("crx_source_changed")
    return _publish_target(
        scope, api, handle, original, payload, source_hash
    )


def _publish_target(scope, api, source_handle, original, payload, source_hash):
    window = None
    try:
        window = PublicationScopeWindow.open(scope=scope, role="artifact")
        window.create_target()
        window.write_all(payload)
        window.flush()
        destination = window.read_all()
        _verify_destination(destination, payload, source_hash)
        source = scope.review.scenario.crx_source
        if _read_crx(source) != payload:
            fail("crx_source_changed")
        api.require_stable(source_handle, original, source)
        window.verify_target()
        final = window.read_all()
        _verify_destination(final, payload, source_hash)
        receipt = _receipt(scope, original, source_hash, len(final))
        _verify_destination(window.read_all(), payload, source_hash)
        window.verify_target()
    except ManagedActivationError as error:
        if window is not None:
            window.close(active_error=True)
        if str(error) in {
            "crx_target_collision",
            "crx_copy_mismatch",
            "crx_source_changed",
            "managed_activation_scope_drift",
        }:
            raise
        fail(_ERROR)
    except Exception:
        if window is not None:
            window.close(active_error=True)
        fail(_ERROR)
    try:
        window.close(active_error=False)
    except ManagedActivationError:
        fail(_ERROR)
    return receipt


def _verify_destination(destination, payload, source_hash) -> None:
    if destination != payload:
        fail("crx_copy_mismatch")
    if hashlib.sha256(destination).hexdigest() != source_hash:
        fail("crx_copy_mismatch")


def _receipt(scope, original, source_hash, size):
    observation = hashlib.sha256(
        canonical_json(
            {
                "source_identity": original.object_identity_fingerprint,
                "format_version": scope.review.crx_format_version,
                "sha256": source_hash,
                "size_bytes": size,
                "flushed": True,
            },
            code=_ERROR,
        )
    ).hexdigest()
    return CrxPublicationReceiptV1.create(
        operation_fingerprint=scope.review.operation_fingerprint,
        profile_fingerprint=scope.profile.profile_fingerprint,
        governing_master_commit=scope.profile.governing_master_commit,
        authorization_fingerprint=scope.authorization_fingerprint,
        input_fingerprints=(
            scope.review.crx_artifact_fingerprint,
            source_hash,
            scope.review.crx_native_identity,
        ),
        observation_fingerprint=observation,
        counts={"published": 1, "rejected": 0},
    )


def _validate_source(scope, observed) -> None:
    if (
        observed.file_attributes & FILE_ATTRIBUTE_DIRECTORY
        or observed.file_attributes & FILE_ATTRIBUTE_REPARSE_POINT
        or observed.filesystem_name != "NTFS"
        or not observed.fixed_drive
        or observed.object_identity_fingerprint
        != scope.review.crx_native_identity
    ):
        fail("crx_source_changed")


def _read_crx(path: Path) -> bytes:
    try:
        metadata = path.lstat()
        if path.is_symlink() or not path.is_file():
            fail("crx_format_invalid")
        if not 12 <= metadata.st_size <= 1024 * 1024 * 1024:
            fail("crx_format_invalid")
        payload = path.read_bytes()
    except OSError:
        fail(_ERROR)
    _format_version(payload)
    return payload


def _format_version(payload: bytes) -> int:
    if len(payload) < 12 or payload[:4] != b"Cr24":
        fail("crx_format_invalid")
    version = int.from_bytes(payload[4:8], "little")
    if version == 2:
        if len(payload) < 16:
            fail("crx_format_invalid")
        key_size = int.from_bytes(payload[8:12], "little")
        signature_size = int.from_bytes(payload[12:16], "little")
        header_end = 16 + key_size + signature_size
    elif version == 3:
        header_size = int.from_bytes(payload[8:12], "little")
        header_end = 12 + header_size
    else:
        fail("crx_format_invalid")
    if header_end >= len(payload):
        fail("crx_format_invalid")
    return version


def _exception_active() -> bool:
    import sys

    return sys.exc_info()[0] is not None
