"""Content-free projection of native Windows security observations."""

from __future__ import annotations

import hashlib

from .acl_contracts import AclDescriptorObservationV1


def descriptor_observation(
    *,
    role,
    native,
    sddl,
    descriptor_bytes,
    owner_bytes,
    group_bytes,
    dacl_bytes,
    protected,
    ace_count,
    inherited_count,
):
    return AclDescriptorObservationV1.create(
        role=role,
        object_identity_fingerprint=native.object_identity_fingerprint,
        canonical_sddl_fingerprint=_hash_text(sddl),
        binary_descriptor_fingerprint=hash_bytes(descriptor_bytes),
        owner_fingerprint=hash_bytes(owner_bytes),
        group_fingerprint=hash_bytes(group_bytes),
        dacl_fingerprint=hash_bytes(dacl_bytes),
        dacl_protected=protected,
        ace_count=ace_count,
        inherited_ace_count=inherited_count,
        complete=True,
        content_observed=False,
    )


def hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
