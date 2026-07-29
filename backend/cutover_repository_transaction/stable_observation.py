"""Independent stable rereads held across filesystem COMMITTED publication."""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from pathlib import Path

from backend.cutover_host_mutation.windows_handles import (
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
)

from .errors import RepositoryTransactionError
from .journal_types import RepositoryMutationKind
from .windows_identity import (
    directory_identity,
    opaque_directory_fingerprint,
)


def filesystem_observation(
    path: Path,
    kind: RepositoryMutationKind,
    expected_identity: str,
) -> str:
    try:
        if directory_identity(path) != expected_identity:
            _fail()
        return _observation_value(path, kind, expected_identity)
    except RepositoryTransactionError:
        raise
    except Exception:
        _fail()


@contextmanager
def locked_filesystem_observation(
    path: Path,
    kind: RepositoryMutationKind,
):
    api = WindowsHandleApi()
    handle = None
    try:
        handle = api.open_existing(
            path,
            access=FILE_READ_ATTRIBUTES,
            share_write=False,
        )
        identity = api.observe(handle)
        if identity.reparse_tag != 0:
            _fail()
        value = _observation_value(
            path, kind, identity.object_identity_fingerprint
        )
        yield value
    except RepositoryTransactionError:
        raise
    except Exception:
        _fail()
    finally:
        if handle is not None:
            try:
                api.close(handle)
            except Exception:
                _fail()


def _observation_value(
    path: Path,
    kind: RepositoryMutationKind,
    identity: str,
) -> str:
    if kind is not RepositoryMutationKind.ADMIN_MOVE:
        return identity
    content = opaque_directory_fingerprint(path)
    return hashlib.sha256(
        b"issue56-admin-identity-content-v1\0"
        + bytes.fromhex(identity)
        + bytes.fromhex(content)
    ).hexdigest()


def _fail() -> None:
    raise RepositoryTransactionError(
        "repository_stable_reread_failed"
    ) from None
