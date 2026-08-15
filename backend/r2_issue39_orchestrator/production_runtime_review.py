"""Adapt the fixed Issue #39 wheel manifest into the strict Runtime contract."""

from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import replace
from pathlib import Path

from backend.cutover_managed_activation.canonical import canonical_json
from backend.cutover_managed_activation.runtime_archive import review_wheel_archive
from backend.cutover_managed_activation.runtime_policy import (
    LockedWheelV1,
    RuntimeInputReviewV1,
)

from .production_manifest import strict_object


_IMPORTS = {
    "annotated-types": "annotated_types", "anyio": "anyio",
    "beautifulsoup4": "bs4", "certifi": "certifi", "cffi": "cffi",
    "colorama": "colorama", "cryptography": "cryptography",
    "distro": "distro", "et-xmlfile": "et_xmlfile", "h11": "h11",
    "httpcore": "httpcore", "httpx": "httpx", "idna": "idna",
    "jiter": "jiter", "lxml": "lxml", "openai": "openai",
    "openpyxl": "openpyxl", "packaging": "packaging", "pillow": "PIL",
    "pycparser": "pycparser", "pydantic": "pydantic",
    "pydantic-core": "pydantic_core", "pypdf": "pypdf",
    "pytesseract": "pytesseract", "python-docx": "docx",
    "python-dotenv": "dotenv", "sniffio": "sniffio",
    "soupsieve": "soupsieve", "tqdm": "tqdm",
    "typing-extensions": "typing_extensions",
    "typing-inspection": "typing_inspection",
}
_LOCK_LINE = re.compile(
    r"([a-z0-9][a-z0-9-]*)==([^ ]+) --hash=sha256:([0-9a-f]{64})",
    re.ASCII,
)
_BASELINE_PIP_IMPORT_SHA256 = (
    "3694838dffbd25554033b6173f4bc33031e63ab45671f677394812ef1aaecf2e"
)


def review_fixed_runtime_inputs(host):
    wheelhouse = Path(r"D:\Projects\email_ai_assistant-runtime\issue39-wheelhouse")
    manifest_payload = (wheelhouse / "wheelhouse-manifest-v1.json").read_bytes()
    manifest = strict_object(manifest_payload)
    lock_path = host._layout.main / "requirements-ci-windows.lock"
    lock_payload = lock_path.read_bytes()
    locked = _parse_lock(lock_payload)
    entries = manifest["wheels"]
    if len(entries) != 31 or set(locked) != set(_IMPORTS):
        raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
    wheels = tuple(
        _wheel_review(wheelhouse / entry["name"], entry, locked)
        for entry in entries
    )
    inputs = host._prepared._inputs
    return RuntimeInputReviewV1(
        python_runtime_fingerprint=inputs.runtime_fingerprint,
        wheelhouse_fingerprint=hashlib.sha256(
            canonical_json(
                [{"wheel": item.wheel, "wheel_sha256": item.wheel_sha256}
                 for item in wheels],
                code="R2_ISSUE39_RUNTIME_REVIEW_INVALID",
            )
        ).hexdigest(),
        dependency_lock_fingerprint=hashlib.sha256(lock_payload).hexdigest(),
        source_tree_fingerprint=inputs.runtime_tree_fingerprint,
        source_entry_count=inputs.runtime_entry_count,
        source_total_bytes=inputs.runtime_total_bytes,
        source_executable_sha256=inputs.runtime_fingerprint,
        wheels=wheels,
    )


def issue39_runtime_verification_review(review):
    """Include the exact pip distribution already bound into the CPython source."""

    if type(review) is not RuntimeInputReviewV1:
        raise TypeError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
    baseline = LockedWheelV1(
        "pip", "26.1.2", "source-tree:pip",
        "0" * 64, "pip", _BASELINE_PIP_IMPORT_SHA256,
    )
    if any(item.distribution.casefold() == "pip" for item in review.wheels):
        raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
    return replace(review, wheels=(*review.wheels, baseline))


def _parse_lock(payload):
    try:
        lines = payload.decode("ascii").splitlines()
    except UnicodeError:
        raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID") from None
    result = {}
    for line in lines:
        if not line or line.startswith("#"):
            continue
        match = _LOCK_LINE.fullmatch(line)
        if match is None or match.group(1) in result:
            raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
        result[match.group(1)] = (match.group(2), match.group(3))
    return result


def _wheel_review(path, entry, locked):
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if len(payload) != entry["size_bytes"] or digest != entry["sha256"]:
        raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
    with zipfile.ZipFile(path, "r") as archive:
        infos = review_wheel_archive(archive)
        metadata_names = [
            item.filename for item in infos
            if item.filename.casefold().endswith(".dist-info/metadata")
        ]
        if len(metadata_names) != 1:
            raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
        name, version = _metadata(archive.read(metadata_names[0]))
        key = re.sub(r"[-_.]+", "-", name).casefold()
        expected = locked.get(key)
        if expected is None or expected != (version, digest):
            raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
        import_name = _IMPORTS[key]
        import_hash = _import_hash(archive, infos, import_name)
    return LockedWheelV1(name, version, path.name, digest, import_name, import_hash)


def _metadata(payload):
    header = payload.split(b"\n\n", 1)[0]
    names = [line[6:].decode("ascii") for line in header.splitlines()
             if line.startswith(b"Name: ")]
    versions = [line[9:].decode("ascii") for line in header.splitlines()
                if line.startswith(b"Version: ")]
    if len(names) != 1 or len(versions) != 1:
        raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
    return names[0], versions[0]


def _import_hash(archive, infos, import_name):
    root = import_name.replace(".", "/")
    candidates = {root + ".py", root + "/__init__.py"}
    matched = [item for item in infos if item.filename in candidates]
    if len(matched) != 1:
        raise ValueError("R2_ISSUE39_RUNTIME_REVIEW_INVALID")
    return hashlib.sha256(archive.read(matched[0])).hexdigest()
