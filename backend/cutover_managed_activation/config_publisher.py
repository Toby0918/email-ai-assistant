"""Create-only durable publication of canonical non-secret Config bytes."""

from __future__ import annotations

import hashlib

from .canonical import canonical_json, fail
from .config_contract import ManagedConfigV1
from .errors import ManagedActivationError
from .publication_scope import PublicationScopeWindow
from .receipts import ConfigPublicationReceiptV1
from .scope_models import _SyntheticActivationScope

_ERROR = "config_publication_failed"


class ConfigPublisher:
    """Publish only the exact profile-bound canonical Config."""

    def __new__(cls, *args: object, **kwargs: object):
        raise TypeError("ConfigPublisher exposes publish() only")

    @classmethod
    def publish(
        cls,
        *,
        scope: object,
        config: object,
    ) -> ConfigPublicationReceiptV1:
        if (
            type(scope) is not _SyntheticActivationScope
            or type(config) is not ManagedConfigV1
        ):
            fail("config_scope_invalid")
        payload, payload_hash = _review_payload(scope, config)
        return _publish(scope, payload, payload_hash)


def _review_payload(scope, config) -> tuple[bytes, str]:
    payload = config.to_canonical_bytes()
    payload_hash = hashlib.sha256(payload).hexdigest()
    if (
        payload_hash != scope.review.config_sha256
        or len(payload) != scope.review.config_size_bytes
    ):
        fail("config_expected_value_mismatch")
    return payload, payload_hash


def _publish(scope, payload, payload_hash):
    window = None
    try:
        window = PublicationScopeWindow.open(scope=scope, role="config")
        window.create_target()
        window.write_all(payload)
        window.flush()
        reread = window.read_all()
        _verify_copy(reread, payload, payload_hash)
        window.verify_target()
        receipt = _receipt(scope, payload, payload_hash)
    except ManagedActivationError as error:
        if window is not None:
            window.close(active_error=True)
        _map_error(error)
    except Exception:
        if window is not None:
            window.close(active_error=True)
        fail(_ERROR)
    try:
        window.close(active_error=False)
    except ManagedActivationError:
        fail(_ERROR)
    return receipt


def _verify_copy(reread, payload, payload_hash) -> None:
    if reread != payload:
        fail("config_copy_mismatch")
    if hashlib.sha256(reread).hexdigest() != payload_hash:
        fail("config_copy_mismatch")


def _map_error(error: ManagedActivationError) -> None:
    code = str(error)
    if code in {
        "config_target_collision",
        "config_copy_mismatch",
        "managed_activation_scope_drift",
    }:
        raise error
    fail(_ERROR)


def _receipt(scope, payload, payload_hash):
    observation = hashlib.sha256(
        canonical_json(
            {
                "config_fingerprint": scope.review.config_fingerprint,
                "sha256": payload_hash,
                "size_bytes": len(payload),
                "flushed": True,
            },
            code=_ERROR,
        )
    ).hexdigest()
    return ConfigPublicationReceiptV1.create(
        operation_fingerprint=scope.review.operation_fingerprint,
        profile_fingerprint=scope.profile.profile_fingerprint,
        governing_master_commit=scope.profile.governing_master_commit,
        authorization_fingerprint=scope.authorization_fingerprint,
        input_fingerprints=(
            scope.review.config_fingerprint,
            payload_hash,
        ),
        observation_fingerprint=observation,
        counts={"published": 1, "rejected": 0},
    )
