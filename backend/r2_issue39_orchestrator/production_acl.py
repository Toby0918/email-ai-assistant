"""DACL-only fixed Project Container ACL publication and recovery."""

from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
from pathlib import Path

from backend.cutover_host_mutation.roles import AclRole
from backend.cutover_host_mutation.windows_acl_apply import (
    WindowsAclWriter,
    exact_container_policy,
    exact_inherited_policy,
)
from backend.cutover_host_mutation.windows_security import (
    WindowsSecurityApi,
    _Acl,
)
from backend.r2_main_publication.windows_dacl import apply_exact_dacl
from backend.cutover_managed_activation.runtime_tree import RuntimeTreeWindow

from .durable_io import guard_directory, read_segment, write_segment


_ROOT = Path(r"D:\IncidentArchives\email_ai_assistant\issue38")
_ZONES = (
    "Runtimes", "LocalData", "RuntimeTemp", "Logs", "Artifacts",
    "Worktrees", "Config", "OperatorPrivate",
)


def apply_fixed_acl(host):
    path = _preimage(host)
    if not os.path.lexists(path):
        payload = _capture_preimage(host)
        with guard_directory(path.parent, flush=True):
            write_segment(path, payload)
    else:
        _read_preimage(host)
    source = _read_preimage(host)
    principals, explicit, inherited = _fixed_dacls()
    security = WindowsSecurityApi()
    _apply_if_expected(
        host._layout.container, security, principals, source["container"],
        explicit, protected=True, role=AclRole.PROJECT_CONTAINER,
    )
    tree = RuntimeTreeWindow.open(host._layout.container)
    try:
        for name in _ZONES:
            tree.ensure_directory((name,))
        tree.verify_exact()
    except Exception:
        tree.close(active_error=True)
        raise
    tree.close(active_error=False)
    _apply_if_expected(
        host._layout.main, security, principals, source["main"],
        inherited, protected=False, role=AclRole.SOURCE_TREE,
    )
    if not _conforms(host, principals):
        raise ValueError("R2_ISSUE39_ACL_CONFORMANCE_FAILED")


def restore_original_acl(host):
    source = _read_preimage(host)
    security = WindowsSecurityApi()
    for name in ("container", "main"):
        item = source[name]
        path = getattr(host._layout, name)
        current = security.capture(path, role=AclRole.SOURCE_TREE)
        if current.observation.object_identity_fingerprint != item["identity"]:
            raise ValueError("R2_ISSUE39_ACL_RECOVERY_AMBIGUOUS")
        if _matches_preimage(current, item):
            continue
        apply_exact_dacl(
            path,
            expected_identity=item["identity"],
            dacl=base64.b64decode(item["dacl"], validate=True),
            protected=item["protected"],
        )


def fixed_acl_conforms(host):
    try:
        principals, _explicit, _inherited = _fixed_dacls()
        return _conforms(host, principals)
    except Exception:
        return False


def acl_partial_state(host, action):
    if action.action_name != "acl_whole_tree_conformance":
        return None
    path = _preimage(host)
    if not os.path.lexists(path):
        return None
    source = _read_preimage(host)
    principals, explicit, inherited = _fixed_dacls()
    security = WindowsSecurityApi()
    container = security.capture(host._layout.container, role=AclRole.PROJECT_CONTAINER)
    main = security.capture(host._layout.main, role=AclRole.SOURCE_TREE)
    container_allowed = _matches_preimage(container, source["container"]) or (
        container.dacl == explicit and container.observation.dacl_protected
    )
    main_allowed = _matches_preimage(main, source["main"]) or (
        main.dacl == inherited and not main.observation.dacl_protected
    )
    zones = []
    for name in _ZONES:
        target = host._layout.container / name
        if not os.path.lexists(target):
            continue
        if not exact_inherited_policy(
            security.capture(target, role=AclRole.SOURCE_TREE), principals
        ):
            raise ValueError("R2_ISSUE39_ACL_PARTIAL_INVALID")
        zones.append(name)
    if not container_allowed or not main_allowed:
        raise ValueError("R2_ISSUE39_ACL_PARTIAL_INVALID")
    if fixed_acl_conforms(host):
        return None
    return hashlib.sha256(
        b"r2-issue39-acl-partial-v1\0"
        + action.action_fingerprint.encode("ascii")
        + b"\0".join(name.encode("ascii") for name in zones)
        + bytes([container.dacl == explicit, main.dacl == inherited])
    ).hexdigest()


def original_acl_restored(host):
    try:
        source = _read_preimage(host)
        security = WindowsSecurityApi()
        for name in ("container", "main"):
            current = security.capture(
                getattr(host._layout, name), role=AclRole.SOURCE_TREE
            )
            item = source[name]
            if (
                current.observation.object_identity_fingerprint != item["identity"]
                or current.dacl != base64.b64decode(item["dacl"], validate=True)
                or current.observation.dacl_protected is not item["protected"]
            ):
                return False
        return True
    except Exception:
        return False


def _conforms(host, principals):
    security = WindowsSecurityApi()
    container = security.capture(
        host._layout.container, role=AclRole.PROJECT_CONTAINER
    )
    if not exact_container_policy(container, principals):
        return False
    return all(
        exact_inherited_policy(
            security.capture(
                host._layout.container / name, role=AclRole.SOURCE_TREE
            ),
            principals,
        )
        for name in ("main", *_ZONES)
    )


def _apply_if_expected(path, security, principals, original, target_dacl, *, protected, role):
    current = security.capture(path, role=role)
    target = (
        exact_container_policy(current, principals)
        if protected else exact_inherited_policy(current, principals)
    )
    if target:
        return
    if not _matches_preimage(current, original):
        raise ValueError("R2_ISSUE39_ACL_INTERMEDIATE_INVALID")
    apply_exact_dacl(
        path,
        expected_identity=current.observation.object_identity_fingerprint,
        dacl=target_dacl,
        protected=protected,
    )


def _matches_preimage(current, item):
    return (
        current.observation.object_identity_fingerprint == item["identity"]
        and current.dacl == base64.b64decode(item["dacl"], validate=True)
        and current.observation.dacl_protected is item["protected"]
    )


def _capture_preimage(host):
    security = WindowsSecurityApi()
    values = {}
    for name in ("container", "main"):
        value = security.capture(
            getattr(host._layout, name), role=AclRole.SOURCE_TREE
        )
        values[name] = {
            "identity": value.observation.object_identity_fingerprint,
            "protected": value.observation.dacl_protected,
            "dacl": base64.b64encode(value.dacl).decode("ascii"),
        }
    return _canonical({"schema": "issue39-acl-preimage-v1", **values})


def _read_preimage(host):
    payload = read_segment(_preimage(host))
    source = json.loads(payload)
    if (
        _canonical(source) != payload
        or set(source) != {"schema", "container", "main"}
        or source["schema"] != "issue39-acl-preimage-v1"
    ):
        raise ValueError("R2_ISSUE39_ACL_PREIMAGE_INVALID")
    for name in ("container", "main"):
        item = source[name]
        if (
            type(item) is not dict
            or set(item) != {"identity", "protected", "dacl"}
            or type(item["protected"]) is not bool
            or len(item["identity"]) != 64
            or not base64.b64decode(item["dacl"], validate=True)
        ):
            raise ValueError("R2_ISSUE39_ACL_PREIMAGE_INVALID")
    return source


def _fixed_dacls():
    writer = WindowsAclWriter()
    security = WindowsSecurityApi()
    principals, buffers = writer._principal_sids(security.current_token_sid())
    entries = writer._entries(buffers)
    pointer = ctypes.c_void_p()
    try:
        result = writer._advapi.SetEntriesInAclW(
            len(entries), entries, None, ctypes.byref(pointer)
        )
        if result != 0 or not pointer.value:
            raise OSError("R2_ISSUE39_ACL_BUILD_FAILED")
        size = ctypes.cast(pointer, ctypes.POINTER(_Acl)).contents.size
        explicit = ctypes.string_at(pointer, size)
    finally:
        if pointer.value:
            writer._kernel.LocalFree(pointer)
    inherited = bytearray(explicit)
    offset = 8
    ace_count = int.from_bytes(inherited[4:6], "little")
    for _index in range(ace_count):
        inherited[offset + 1] |= 0x10
        offset += int.from_bytes(inherited[offset + 2:offset + 4], "little")
    if offset != len(inherited):
        raise ValueError("R2_ISSUE39_ACL_BUILD_FAILED")
    return principals, explicit, bytes(inherited)


def _preimage(host):
    return _ROOT / (
        ".issue39-acl-preimage-" + host._closure.production.binding_fingerprint
        + ".json"
    )


def _canonical(value):
    return (json.dumps(
        value, ensure_ascii=True, allow_nan=False, sort_keys=True,
        separators=(",", ":"),
    ) + "\n").encode("ascii")
