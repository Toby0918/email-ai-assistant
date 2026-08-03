"""No-argument final-master closure verifier; never issues approval or authority."""

import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
_REMOTE_URL = "https://github.com/Toby0918/email-ai-assistant.git"
_REMOTE_REF = "refs/heads/master"
_GIT_OPTIONS = (
    "--no-replace-objects",
    "-c", "core.fsmonitor=false",
    "-c", "core.untrackedCache=false",
    "-c", "core.sparseCheckout=false",
    "-c", "core.sparseCheckoutCone=false",
    "-c", "status.showUntrackedFiles=all",
    "-c", "http.sslVerify=true",
)


def main():
    try:
        if not sys.flags.isolated or not sys.flags.safe_path:
            raise ValueError
        success, result = _verify_fixed_repository()
    except Exception:
        success, result = False, ("BLOCKED_FROZEN_MASTER", 14, 0)
    if success:
        sys.stdout.buffer.write(result + b"\n")
        return 0
    sys.stdout.write(
        f"{result[0]} missing={result[1]} invalid={result[2]} "
        "eligibility=0 approval=0 authority=0\n"
    )
    return 2


def _verify_fixed_repository():
    head = _git("rev-parse", "HEAD^{commit}")
    remote = _git("rev-parse", "refs/remotes/origin/master^{commit}")
    if head != remote:
        raise ValueError
    with tempfile.TemporaryDirectory(prefix="r2-final-master-verified-") as directory:
        materialized = Path(directory)
        tree, descriptors = _materialize_head(head, materialized)
        _require_current_script_bytes(descriptors)
        _require_clean_index_and_worktree(descriptors)
        if remote != _fresh_remote_master():
            raise ValueError
        result = _verify_materialized(
            materialized, head, remote, tree, descriptors
        )
    if (
        head != _git("rev-parse", "HEAD^{commit}")
        or remote != _git("rev-parse", "refs/remotes/origin/master^{commit}")
    ):
        raise ValueError
    _require_current_script_bytes(descriptors)
    _require_clean_index_and_worktree(descriptors)
    return result


def _verify_materialized(materialized, head, remote, tree, descriptors):
    if any(
        name == "backend" or name.startswith("backend.")
        or name == "scripts" or name.startswith("scripts.")
        for name in sys.modules
    ):
        raise ValueError
    sys.path.insert(0, str(materialized))
    try:
        from backend.r2_final_master_closure import (
            FinalMasterBindingV1,
            R2GlobalGateEvidenceV1,
            gate_evidence_registry,
        )
        from backend.r2_final_master_closure._canonical import fingerprint
        from backend.r2_final_master_closure.final_review import (
            _assemble_review_package,
        )
        from backend.r2_final_master_closure.frozen_master import (
            _allocate as _allocate_frozen,
        )
        from backend.r2_ci_provenance_v2 import (
            R2GitObjectEntryV2,
            R2GitObjectSourcePackageV2,
        )
        from backend.r2_ci_provenance_v2._canonical import sha256
        from backend.r2_production_binding import (
            ApprovedCutoverBindingV2,
            reviewed_production_binding_receipt_v2,
        )
        from scripts.r2_ci_provenance_support import (
            _workflow_lock,
        )

        raw = {path.as_posix(): content for path, _mode, _oid, content in descriptors}
        runbook = "docs/operations/r2_final_operator_runbook.md"
        if runbook not in raw:
            raise ValueError
        lock = _workflow_lock(raw)
        entries = tuple(
            R2GitObjectEntryV2.create(
                relative_path=path.as_posix(),
                mode=mode,
                blob_oid=oid,
                content_bytes=content,
            )
            for path, mode, oid, content in descriptors
        )
        package = R2GitObjectSourcePackageV2.create(
            final_commit_oid=head,
            final_tree_oid=tree,
            observed_commit_oid=head,
            observed_tree_oid=tree,
            entries=entries,
            workflow_lock=lock,
            runbook_fingerprint=sha256(
                b"r2-operator-runbook-document-v2\0" + raw[runbook]
            ),
        )
        if package.final_commit_oid != head:
            raise ValueError
        binding = FinalMasterBindingV1.create(
            final_commit_oid=package.final_commit_oid,
            final_tree_oid=package.final_tree_oid,
            source_package_fingerprint=package.source_package_fingerprint,
            runbook_fingerprint=package.runbook_fingerprint,
            workflow_fingerprint=lock.lock_fingerprint,
        )
        frozen = _allocate_frozen(binding, {
            "observation_type": "R2FrozenRemoteMasterV1",
            "status": "FROZEN_REMOTE_MASTER_VERIFIED",
            "binding_fingerprint": binding.binding_fingerprint,
            "remote_ref_fingerprint": fingerprint("r2-frozen-remote-ref-v1", {
                "remote_url": _REMOTE_URL,
                "ref": _REMOTE_REF,
                "commit": remote,
            }),
            "final_commit_oid": binding.final_commit_oid,
            "final_tree_oid": binding.final_tree_oid,
            "source_package_fingerprint": binding.source_package_fingerprint,
            "runbook_fingerprint": binding.runbook_fingerprint,
            "workflow_fingerprint": binding.workflow_fingerprint,
            "exact_match": 1,
            "historical_master_count": 0,
            "dirty_path_count": 0,
        })
        production_result = _read_reviewed_production_binding(
            binding, ApprovedCutoverBindingV2
        )
        if not production_result[0]:
            return production_result
        production_receipt = reviewed_production_binding_receipt_v2(
            binding, production_result[1]
        )
        result = _read_external_evidence(
            binding,
            frozen,
            production_receipt,
            gate_evidence_registry(),
            R2GlobalGateEvidenceV1,
            _assemble_review_package,
        )
        _require_materialized_module_origins(materialized)
        return result
    finally:
        sys.path.remove(str(materialized))


def _read_reviewed_production_binding(binding, binding_type):
    path = (
        _git_common_dir()
        / "r2-final-master-closure-v1"
        / "reviewed-production-binding-v2.json"
    )
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return False, ("BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING", 1, 0)
    except Exception:
        return False, ("BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING", 0, 1)
    try:
        value = binding_type.from_json(
            payload, final_master_binding=binding
        )
    except Exception:
        return False, ("BLOCKED_MISSING_REVIEWED_PRODUCTION_BINDING", 0, 1)
    return True, value


def _read_external_evidence(
    binding, frozen, production_receipt, registry, evidence_type, assemble
):
    directory = _git_common_dir() / "r2-final-master-closure-v1"
    evidence, missing, invalid = [], 0, 0
    for index, registration in enumerate(registry, start=1):
        path = directory / f"{index:02d}-{registration.gate.value}.json"
        try:
            payload = path.read_bytes()
        except FileNotFoundError:
            missing += 1
            continue
        except Exception:
            invalid += 1
            continue
        try:
            evidence.append(evidence_type.from_signed_json(payload, binding=binding))
        except Exception:
            invalid += 1
    if missing or invalid:
        return False, ("BLOCKED_MISSING_EXTERNAL_GATE_EVIDENCE", missing, invalid)
    return True, assemble(
        frozen, production_receipt, tuple(evidence)
    ).to_canonical_json()


def _materialize_head(head, target):
    if not target.is_dir() or any(target.iterdir()):
        raise ValueError
    commit = _read_git_object("commit", head)
    tree_oid = _commit_tree_oid(commit)
    descriptors = _tree_descriptors(tree_oid)
    for path, mode, oid, content in descriptors:
        destination = target.joinpath(*path.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        if destination.read_bytes() != content:
            raise ValueError
        if mode == "100755":
            destination.chmod(destination.stat().st_mode | 0o111)
    return tree_oid, tuple(descriptors)


def _read_git_object(kind, oid):
    _require_oid(oid)
    if kind not in {"blob", "commit", "tree"}:
        raise ValueError
    content = _git_bytes("cat-file", kind, oid)
    framed = kind.encode("ascii") + b" " + str(len(content)).encode("ascii")
    framed += b"\0" + content
    if hashlib.sha1(framed).hexdigest() != oid:
        raise ValueError
    return content


def _require_oid(oid):
    if (
        type(oid) is not str
        or len(oid) != 40
        or any(item not in "0123456789abcdef" for item in oid)
    ):
        raise ValueError


def _commit_tree_oid(content):
    first_line = content.split(b"\n", 1)[0]
    if not first_line.startswith(b"tree "):
        raise ValueError
    try:
        oid = first_line.removeprefix(b"tree ").decode("ascii")
    except UnicodeDecodeError:
        raise ValueError from None
    _require_oid(oid)
    return oid


def _tree_descriptors(tree_oid):
    observed_paths, observed_directories, descriptors = set(), set(), []

    def visit(oid, prefix):
        content = _read_git_object("tree", oid)
        cursor = 0
        while cursor < len(content):
            separator = content.find(b" ", cursor)
            terminator = content.find(b"\0", separator + 1)
            if separator <= cursor or terminator <= separator + 1:
                raise ValueError
            mode = content[cursor:separator]
            raw_name = content[separator + 1:terminator]
            raw_oid = content[terminator + 1:terminator + 21]
            if len(raw_oid) != 20:
                raise ValueError
            cursor = terminator + 21
            try:
                name = raw_name.decode("utf-8")
            except UnicodeDecodeError:
                raise ValueError from None
            if not name or "/" in name or "\\" in name:
                raise ValueError
            path = prefix / name
            relative = path.as_posix()
            alias = _windows_tree_alias(relative)
            child_oid = raw_oid.hex()
            if mode == b"40000":
                if alias in observed_directories or alias in observed_paths:
                    raise ValueError
                observed_directories.add(alias)
                visit(child_oid, path)
                continue
            if mode not in {b"100644", b"100755"}:
                raise ValueError
            if alias in observed_paths or alias in observed_directories:
                raise ValueError
            observed_paths.add(alias)
            blob = _read_git_object("blob", child_oid)
            descriptors.append((path, mode.decode("ascii"), child_oid, blob))
        if cursor != len(content):
            raise ValueError

    visit(tree_oid, PurePosixPath())
    return descriptors


def _require_clean_index_and_worktree(descriptors):
    expected = {
        _windows_tree_alias(path.as_posix()): (path, mode, oid, content)
        for path, mode, oid, content in descriptors
    }
    if len(expected) != len(descriptors):
        raise ValueError
    index = {}
    for record in _nul_records(_git_bytes("ls-files", "--stage", "-z")):
        header, raw_path = record.split(b"\t", 1)
        mode, raw_oid, stage = header.split(b" ")
        if stage != b"0":
            raise ValueError
        try:
            relative = raw_path.decode("utf-8")
            oid = raw_oid.decode("ascii")
            text_mode = mode.decode("ascii")
        except UnicodeDecodeError:
            raise ValueError from None
        alias = _windows_tree_alias(relative)
        if alias in index:
            raise ValueError
        index[alias] = (PurePosixPath(relative), text_mode, oid)
    expected_index = {
        alias: (path, mode, oid)
        for alias, (path, mode, oid, _content) in expected.items()
    }
    if index != expected_index:
        raise ValueError
    flags = {}
    for record in _nul_records(_git_bytes("ls-files", "-v", "-z")):
        if len(record) < 3 or record[1:2] != b" ":
            raise ValueError
        try:
            relative = record[2:].decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError from None
        alias = _windows_tree_alias(relative)
        if record[:1] != b"H" or alias in flags:
            raise ValueError
        flags[alias] = PurePosixPath(relative)
    if flags != {alias: item[0] for alias, item in expected.items()}:
        raise ValueError
    if _git_bytes(
        "status", "--porcelain=v1", "-z",
        "--untracked-files=all", "--ignored=no",
    ):
        raise ValueError
    _require_exact_worktree(expected)


def _require_current_script_bytes(descriptors):
    relative = PurePosixPath("scripts/verify_r2_final_master_closure.py")
    matches = [item for item in descriptors if item[0] == relative]
    if len(matches) != 1:
        raise ValueError
    _path, mode, oid, reviewed = matches[0]
    if mode not in {"100644", "100755"}:
        raise ValueError
    framed = b"blob " + str(len(reviewed)).encode("ascii") + b"\0" + reviewed
    if hashlib.sha1(framed).hexdigest() != oid:
        raise ValueError
    expected_path = ROOT.joinpath(*relative.parts)
    if os.path.normcase(os.path.abspath(__file__)) != os.path.normcase(
        os.path.abspath(expected_path)
    ):
        raise ValueError
    _read_exact_tracked_file(ROOT, relative, reviewed)


def _nul_records(payload):
    records = payload.split(b"\0")
    if not records or records[-1] != b"" or any(not item for item in records[:-1]):
        raise ValueError
    return records[:-1]


def _require_exact_worktree(expected):
    root = ROOT
    for relative, mode, _oid, content in expected.values():
        _path, identities = _require_safe_tracked_path(root, relative)
        if os.name != "nt" and bool(identities[-1][2] & 0o111) != (mode == "100755"):
            raise ValueError
        _read_exact_tracked_file(root, relative, content, identities)


def _read_exact_tracked_file(root, relative, expected, before=None):
    if before is None:
        path, before = _require_safe_tracked_path(root, relative)
    else:
        path = ROOT.joinpath(*relative.parts)
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            observed = stream.read(len(expected) + 1)
    except Exception:
        raise ValueError from None
    _path, after = _require_safe_tracked_path(root, relative)
    if (
        not stat.S_ISREG(opened.st_mode)
        or before != after
        or before[-1] != _file_identity(opened)
        or observed != expected
    ):
        raise ValueError
    return observed


def _require_safe_tracked_path(root, relative):
    if root != ROOT or not root.is_absolute():
        raise ValueError
    current = root
    parts = relative.parts
    if not parts:
        raise ValueError
    metadata = _safe_component_metadata(current, stat.S_ISDIR)
    identities = [_file_identity(metadata)]
    for index, part in enumerate(parts):
        current = current / part
        expected_type = stat.S_ISREG if index == len(parts) - 1 else stat.S_ISDIR
        metadata = _safe_component_metadata(current, expected_type)
        identities.append(_file_identity(metadata))
    return current, tuple(identities)


def _safe_component_metadata(path, expected_type):
    try:
        metadata = os.lstat(path)
        is_reparse = bool(
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        if (
            path.is_symlink()
            or path.is_junction()
            or is_reparse
            or not expected_type(metadata.st_mode)
        ):
            raise ValueError
    except ValueError:
        raise
    except Exception:
        raise ValueError from None
    return metadata


def _file_identity(value):
    return value.st_dev, value.st_ino, value.st_mode, value.st_size


def _windows_tree_alias(relative):
    if type(relative) is not str or not 1 <= len(relative.encode("utf-8")) <= 4096:
        raise ValueError
    raw_parts = relative.split("/")
    path = PurePosixPath(relative)
    if (
        path.is_absolute()
        or "\\" in relative
        or any(part in {"", ".", ".."} for part in raw_parts)
    ):
        raise ValueError
    aliases = []
    reserved = {
        "con", "prn", "aux", "nul", "clock$",
        *(f"com{value}" for value in "123456789¹²³"),
        *(f"lpt{value}" for value in "123456789¹²³"),
    }
    for part in raw_parts:
        normalized = unicodedata.normalize("NFKC", part)
        if (
            part in {"", ".", ".."}
            or normalized.endswith((" ", "."))
            or any(ord(item) < 32 or item in '<>:"|?*' for item in normalized)
            or "~" in normalized
            or normalized.casefold() == ".git"
            or len(normalized.encode("utf-16-le")) // 2 > 255
        ):
            raise ValueError
        device = normalized.split(".", 1)[0].rstrip(" .").casefold()
        if device in reserved:
            raise ValueError
        aliases.append(normalized.casefold())
    return "/".join(aliases)


def _git_bytes(*arguments):
    result = subprocess.run(
        ("git", *_GIT_OPTIONS, *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=60,
        env=_git_environment(),
    )
    if result.stderr:
        raise ValueError
    return result.stdout


def _require_materialized_module_origins(materialized):
    root = materialized.resolve(strict=True)
    for name, module in tuple(sys.modules.items()):
        if not (
            name == "backend" or name.startswith("backend.")
            or name == "scripts" or name.startswith("scripts.")
        ):
            continue
        origin = getattr(module, "__file__", None)
        if origin is not None:
            try:
                Path(origin).resolve(strict=True).relative_to(root)
            except Exception:
                raise ValueError from None
            continue
        paths = tuple(getattr(module, "__path__", ()))
        if not paths:
            raise ValueError
        for path in paths:
            try:
                Path(path).resolve(strict=True).relative_to(root)
            except Exception:
                raise ValueError from None


def _fresh_remote_master():
    result = subprocess.run(
        (
            "git", *_GIT_OPTIONS, "ls-remote", "--exit-code",
            _REMOTE_URL, _REMOTE_REF,
        ),
        cwd=ROOT.parent,
        check=True,
        capture_output=True,
        timeout=30,
        env=_git_environment(),
    )
    if result.stderr:
        raise ValueError
    line = result.stdout.decode("ascii")
    suffix = f"\t{_REMOTE_REF}\n"
    if not line.endswith(suffix) or line.count("\n") != 1:
        raise ValueError
    oid = line[:-len(suffix)]
    if len(oid) != 40 or any(character not in "0123456789abcdef" for character in oid):
        raise ValueError
    return oid


def _git(*arguments):
    result = subprocess.run(
        ("git", *_GIT_OPTIONS, *arguments),
        cwd=ROOT,
        check=True,
        capture_output=True,
        timeout=30,
        env=_git_environment(),
    )
    if result.stderr:
        raise ValueError
    return result.stdout.decode("ascii").strip()


def _git_environment():
    environment = {
        name: os.environ[name]
        for name in (
            "PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP",
        )
        if name in os.environ
    }
    environment.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "GCM_INTERACTIVE": "Never",
        "LC_ALL": "C",
    })
    return environment


def _git_common_dir():
    value = Path(_git("rev-parse", "--git-common-dir"))
    if not value.is_absolute():
        value = ROOT / value
    return value.resolve()


if __name__ == "__main__":
    raise SystemExit(main())
