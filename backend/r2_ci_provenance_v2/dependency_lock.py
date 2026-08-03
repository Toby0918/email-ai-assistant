"""Hash-locked platform dependency inputs for final-master CI."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

from ._canonical import fingerprint, sha256
from .errors import R2CiProvenanceError


_EXPECTED = ("requirements-ci-linux.lock", "requirements-ci-windows.lock")
_LINE = re.compile(
    r"^([a-z0-9][a-z0-9._-]*)==([A-Za-z0-9][A-Za-z0-9._+-]*)"
    r"((?: --hash=sha256:[0-9a-f]{64})+)$"
)
_HASH = re.compile(r"--hash=sha256:([0-9a-f]{64})")


@dataclass(frozen=True, slots=True, repr=False)
class R2DependencyLockV2:
    lock_count: int
    dependency_count: int
    wheel_hash_count: int
    distributions: tuple[tuple[str, str], ...] = field(repr=False)
    platform_fingerprints: tuple[tuple[str, str], ...] = field(repr=False)
    lock_fingerprint: str = field(repr=False)

    @classmethod
    def create(cls, *, locks):
        try:
            normalized, platforms = _normalize(locks)
            dependencies = [item for _path, _content, items in normalized for item in items]
            distribution_sets = tuple(
                tuple((name, version) for name, version, _hashes in items)
                for _path, _content, items in normalized
            )
            if (
                len({name for name, _version, _hashes in dependencies}) != 31
                or distribution_sets[0] != distribution_sets[1]
            ):
                raise R2CiProvenanceError()
            state = [
                {
                    "path": path,
                    "byte_sha256": sha256(content),
                    "dependencies": [
                        {"name": name, "version": version, "hashes": list(hashes)}
                        for name, version, hashes in items
                    ],
                }
                for path, content, items in normalized
            ]
            return cls(
                2,
                31,
                sum(len(hashes) for _name, _version, hashes in dependencies),
                distribution_sets[0],
                tuple(platforms),
                fingerprint("r2-dependency-lock-v2", state),
            )
        except R2CiProvenanceError:
            raise
        except Exception:
            raise R2CiProvenanceError() from None

    def platform_fingerprint(self, platform):
        try:
            return dict(self.platform_fingerprints)[platform]
        except Exception:
            raise R2CiProvenanceError() from None


def _normalize(locks):
    if type(locks) is not tuple or len(locks) != 2:
        raise R2CiProvenanceError()
    ordered = tuple(sorted(locks))
    if tuple(path for path, _content in ordered) != _EXPECTED:
        raise R2CiProvenanceError()
    result, platforms = [], []
    for path, content in ordered:
        if type(content) is not bytes or not content.endswith(b"\n"):
            raise R2CiProvenanceError()
        items = []
        for raw in content.decode("ascii").splitlines():
            if not raw or raw.startswith("#"):
                continue
            match = _LINE.fullmatch(raw)
            if match is None:
                raise R2CiProvenanceError()
            hashes = tuple(_HASH.findall(match.group(3)))
            if not hashes or len(set(hashes)) != len(hashes):
                raise R2CiProvenanceError()
            items.append((match.group(1).replace("_", "-"), match.group(2), hashes))
        if len(items) != 31 or len({name for name, _version, _hashes in items}) != 31:
            raise R2CiProvenanceError()
        platform = "linux" if "linux" in path else "windows"
        platforms.append((platform, fingerprint("r2-platform-dependency-lock-v2", {
            "path": path, "byte_sha256": sha256(content),
        })))
        result.append((path, content, tuple(items)))
    return tuple(result), platforms
