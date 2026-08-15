"""Stable content-free identity for one fixed production input file."""

import hashlib
import json
import sys


def file_identity_fingerprint(path):
    if sys.platform == "win32":
        from backend.cutover_managed_activation.windows_file_handles import (
            WindowsReadHandleApi,
        )

        api = WindowsReadHandleApi()
        handle = api.open_existing(path, deny_write=False)
        try:
            observed = api.observe(handle)
            api.require_stable(handle, observed, path)
            return observed.object_identity_fingerprint
        finally:
            api.close(handle)
    before = path.lstat()
    after = path.lstat()
    values = (
        before.st_dev, before.st_ino, before.st_mode,
        before.st_size, before.st_mtime_ns,
    )
    if values != (
        after.st_dev, after.st_ino, after.st_mode,
        after.st_size, after.st_mtime_ns,
    ):
        raise ValueError
    return hashlib.sha256(
        b"r2-issue39-file-identity-v1\0"
        + json.dumps(values, separators=(",", ":")).encode("ascii")
    ).hexdigest()
