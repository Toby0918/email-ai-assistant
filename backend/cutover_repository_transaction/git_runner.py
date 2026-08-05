"""Scope-bound fixed Git operations with bounded process-tree ownership."""
from __future__ import annotations

import hashlib
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from backend.cutover_host_mutation.windows_handles import (
    FILE_READ_ATTRIBUTES,
    WindowsHandleApi,
)
from backend.migration_evidence.process_tree import ProcessTree

from .errors import RepositoryTransactionError
from .git_executable import (
    executable_content_fingerprint as _executable_content_fingerprint,
    resolved_executable as _resolved_executable,
)
from .windows_identity import directory_identity, file_identity

_MAX_OUTPUT = 1_000_000
_BRANCH = re.compile(r"refs/heads/worktree_[0-9]{2}")
_UNSAFE_CONFIG = (
    "alias.",
    "credential.",
    "diff.external",
    "filter.",
    "include.",
    "includeif.",
    "pager.",
    "core.fsmonitor",
    "core.hookspath",
    "core.pager",
    "core.sshcommand",
)


@dataclass(frozen=True, slots=True, repr=False)
class _BoundSyntheticGitRunner:
    root: Path = field(repr=False)
    marker: Path = field(repr=False)
    root_identity: str = field(repr=False)
    marker_identity: str = field(repr=False)
    executable: Path = field(repr=False)
    executable_identity: str = field(repr=False)
    executable_content: str = field(repr=False)
    version_bytes: bytes = field(repr=False)
    binding_fingerprint: str = field(repr=False)

    def common_dir(self, cwd: Path) -> bytes:
        return self._run(cwd, ("rev-parse", "--path-format=absolute",
                              "--git-common-dir"))

    def git_dir(self, cwd: Path) -> bytes:
        return self._run(cwd, ("rev-parse", "--path-format=absolute",
                              "--git-dir"))

    def symbolic_ref(self, cwd: Path) -> bytes:
        return self._run(cwd, ("symbolic-ref", "-q", "HEAD"))

    def head(self, cwd: Path) -> bytes:
        return self._run(cwd, ("rev-parse", "HEAD"))

    def status(self, cwd: Path) -> bytes:
        return self._run(
            cwd,
            ("status", "--porcelain=v2", "-z", "--untracked-files=all"),
        )

    def worktree_list(self, cwd: Path) -> bytes:
        return self._run(cwd, ("worktree", "list", "--porcelain", "-z"))

    def remote_config(self, cwd: Path) -> bytes:
        return self._run(
            cwd,
            ("config", "--local", "--null", "--get-regexp", r"^remote\."),
            optional=True,
        )

    def local_refs(self, cwd: Path) -> bytes:
        return self._run(
            cwd,
            ("for-each-ref", "--format=%(refname)%00%(objectname)"),
        )

    def add_worktree(
        self, cwd: Path, target: Path, ref: str
    ) -> bytes:
        if not _BRANCH.fullmatch(ref):
            _fail()
        self._require_path(target, allow_absent=False)
        return self._run(
            cwd,
            (
                "worktree", "add", "--no-guess-remote", "--",
                str(target), ref.removeprefix("refs/heads/"),
            ),
        )

    def _run(
        self,
        cwd: Path,
        arguments: tuple[str, ...],
        *,
        optional: bool = False,
    ) -> bytes:
        resolved = self._require_path(cwd, allow_absent=False)
        _require_binding(self)
        result = _bounded_process(self, resolved, arguments)
        _require_binding(self)
        payload, returncode = result
        if returncode == 0:
            return payload
        if optional and returncode == 1:
            return b""
        _fail()

    def _require_path(self, path: Path, *, allow_absent: bool) -> Path:
        try:
            value = (
                path.resolve(strict=True)
                if not allow_absent
                else path.parent.resolve(strict=True) / path.name
            )
        except (OSError, RuntimeError):
            _fail()
        if self.root not in value.parents:
            _fail()
        return value


def bind_synthetic_git_runner(
    root: Path, marker: Path, source: Path
) -> _BoundSyntheticGitRunner:
    executable = _resolved_executable()
    identity = file_identity(executable)
    content = _executable_content_fingerprint(executable)
    provisional = _BoundSyntheticGitRunner(
        root=root,
        marker=marker,
        root_identity=directory_identity(root),
        marker_identity=file_identity(marker),
        executable=executable,
        executable_identity=identity,
        executable_content=content,
        version_bytes=b"",
        binding_fingerprint="0" * 64,
    )
    version, code = _bounded_process(
        provisional, source.resolve(strict=True), ("--version",)
    )
    if code or not version.startswith(b"git version "):
        _fail()
    binding = _fingerprint(
        identity.encode("ascii"),
        bytes.fromhex(content),
        version,
    )
    runner = _BoundSyntheticGitRunner(
        root=root, marker=marker,
        root_identity=provisional.root_identity,
        marker_identity=provisional.marker_identity,
        executable=executable,
        executable_identity=identity,
        executable_content=content,
        version_bytes=version, binding_fingerprint=binding,
    )
    _require_safe_local_config(runner, source)
    return runner


def _bounded_process(runner, cwd, arguments):
    process = None
    tree = ProcessTree.prepare()
    api = WindowsHandleApi()
    handle = api.open_existing(
        runner.executable,
        access=FILE_READ_ATTRIBUTES,
        share_write=False,
    )
    try:
        _require_locked_executable(runner, api, handle)
        process = subprocess.Popen(
            _command(runner.executable, arguments),
            cwd=cwd, env=_environment(cwd.anchor),
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, shell=False,
            **tree.popen_options(),
        )
        tree.attach(process)
        process.wait(timeout=20)
        if process.stdout is None:
            _fail()
        payload = process.stdout.read(_MAX_OUTPUT + 1)
        if len(payload) > _MAX_OUTPUT:
            tree.terminate(process)
            _fail()
        returncode = tree.finish(process)
        _require_locked_executable(runner, api, handle)
        return payload, returncode
    except RepositoryTransactionError:
        raise
    except subprocess.TimeoutExpired:
        _fail()
    except Exception:
        _fail()
    finally:
        tree.terminate(process)
        api.close(handle)
        if process is not None and process.stdout is not None:
            process.stdout.close()


def _command(executable: Path, arguments) -> tuple[str, ...]:
    return (
        str(executable),
        "-c", "core.hooksPath=NUL",
        "-c", "core.fsmonitor=false",
        "-c", "core.untrackedCache=false",
        *arguments,
    )


def _environment(anchor: str) -> dict[str, str]:
    allowed = (
        "COMSPEC", "PATH", "PATHEXT", "SYSTEMROOT", "SystemRoot",
        "TEMP", "TMP", "WINDIR",
    )
    value = {name: os.environ[name] for name in allowed if name in os.environ}
    value.update({
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_CEILING_DIRECTORIES": anchor,
        "GIT_PAGER": "cat",
        "GIT_EDITOR": "false",
        "GIT_SEQUENCE_EDITOR": "false",
        "GCM_INTERACTIVE": "never",
        "LANG": "C",
        "LC_ALL": "C",
    })
    return value


def _require_safe_local_config(runner, source) -> None:
    payload, code = _bounded_process(
        runner, source, ("config", "--local", "--null", "--list")
    )
    if code:
        _fail()
    fields = tuple(item for item in payload.split(b"\0") if item)
    for field in fields:
        try:
            key = field.split(b"\n", 1)[0].decode("utf-8").casefold()
        except UnicodeError:
            _fail()
        if key.startswith(_UNSAFE_CONFIG):
            _fail()


def _require_binding(runner) -> None:
    if (
        directory_identity(runner.root) != runner.root_identity
        or file_identity(runner.marker) != runner.marker_identity
        or file_identity(runner.executable) != runner.executable_identity
        or _executable_content_fingerprint(runner.executable)
        != runner.executable_content
    ):
        _fail()


def _require_locked_executable(runner, api, handle) -> None:
    if (
        api.observe(handle).object_identity_fingerprint
        != runner.executable_identity
        or _executable_content_fingerprint(runner.executable)
        != runner.executable_content
    ):
        _fail()


def _fingerprint(*values: bytes) -> str:
    digest = hashlib.sha256(b"issue56-git-runner-v1\0")
    for value in values:
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return digest.hexdigest()


def _fail() -> None:
    raise RepositoryTransactionError("repository_git_runner_invalid") from None
