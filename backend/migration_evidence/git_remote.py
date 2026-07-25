"""Content-free local remote configuration fingerprints."""

from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlsplit

from .contract import RemoteBaseline
from .errors import MigrationEvidenceError
from .git_runner import git_output


def remote_baseline(root: Path) -> tuple[RemoteBaseline, ...]:
    """Hash every local remote URL and fetch value without exposing it."""

    payload = git_output(root, ("remote",))
    assert payload is not None
    try:
        names = tuple(
            line
            for line in payload.decode("utf-8").splitlines()
            if line
        )
    except UnicodeDecodeError:
        raise MigrationEvidenceError() from None
    if len(names) > 16 or len(set(names)) != len(names):
        raise MigrationEvidenceError()
    values: list[RemoteBaseline] = []
    for name in sorted(names):
        if not name.replace("-", "").replace("_", "").isalnum():
            raise MigrationEvidenceError()
        urls = _config_values(root, f"remote.{name}.url")
        fetch = _config_values(
            root,
            f"remote.{name}.fetch",
            optional=True,
        )
        for url in urls:
            _require_credential_free_url(url)
        values.append(
            RemoteBaseline(
                name=name,
                url_sha256=_sha256(_joined(urls)),
                fetch_sha256=_sha256(_joined(fetch)),
            )
        )
    return tuple(values)


def _config_values(
    root: Path,
    key: str,
    *,
    optional: bool = False,
) -> tuple[bytes, ...]:
    payload = git_output(
        root,
        ("config", "--local", "-z", "--get-all", key),
        optional=optional,
    )
    if payload is None:
        return ()
    if not payload.endswith(b"\0"):
        raise MigrationEvidenceError()
    values = tuple(payload[:-1].split(b"\0"))
    if not values or len(values) > 16 or any(not value for value in values):
        raise MigrationEvidenceError()
    return values


def _require_credential_free_url(payload: bytes) -> None:
    if len(payload) > 2048 or any(value < 32 for value in payload):
        raise MigrationEvidenceError()
    try:
        value = payload.decode("utf-8")
    except UnicodeDecodeError:
        raise MigrationEvidenceError() from None
    parsed = urlsplit(value)
    if parsed.scheme and (
        parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise MigrationEvidenceError()


def _joined(values: tuple[bytes, ...]) -> bytes:
    return b"\0".join(values)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
