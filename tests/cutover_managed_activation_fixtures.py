"""Synthetic, content-free Issue #57 publication fixtures."""

from __future__ import annotations

import atexit
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from backend.cutover_contracts import (
    CutoverProfileV1,
    TestSandboxAuthorizationV1,
)
from backend.cutover_managed_activation.runtime_source_tree import (
    observe_source_tree,
)
from tests.cutover_contract_fixtures import valid_profile_body

EXPECTED_MASTER = "7bd2eb16bf10d847a4fbd3d691256e6ad13ad6cd"
OBSERVED_AT = 1_900_000_000
DEPENDENCIES = (
    ("beautifulsoup4", "4.15.0", "bs4"),
    ("cryptography", "49.0.0", "cryptography"),
    ("openpyxl", "3.1.5", "openpyxl"),
    ("openai", "2.45.0", "openai"),
    ("python-dotenv", "1.2.2", "dotenv"),
    ("pypdf", "6.14.2", "pypdf"),
    ("python-docx", "1.2.0", "docx"),
    ("Pillow", "12.3.0", "PIL"),
    ("pytesseract", "0.3.13", "pytesseract"),
)
_SOURCE_FIXTURE_OWNER = None
_SOURCE_FIXTURE_ROOT = None
_SOURCE_FIXTURE_OBSERVATION = None


@dataclass(slots=True)
class SyntheticManagedActivationScenario:
    owner: tempfile.TemporaryDirectory[str]
    root: Path
    marker: Path
    python_source: Path
    python_source_manifest: Path
    wheelhouse: Path
    dependency_lock: Path
    runtime_target: Path
    database_source: Path
    database_target: Path
    crx_source: Path
    crx_target: Path
    config_values: dict[str, object]
    config_target: Path

    def close(self) -> None:
        self.owner.cleanup()


def build_runtime_scenario(
    directory: Path | None = None,
) -> SyntheticManagedActivationScenario:
    owner = tempfile.TemporaryDirectory(
        prefix="issue57-synthetic-",
        dir=(
            str(directory)
            if directory is not None
            else Path(sys._base_executable).anchor
        ),
    )
    root = Path(owner.name)
    marker = root / ".codex-managed-activation-test-sandbox"
    marker.write_bytes(b"issue57-synthetic-marker-v1")
    wheelhouse = root / "wheelhouse"
    wheelhouse.mkdir()
    lock_items = [
        _build_wheel(wheelhouse, distribution, version, import_name)
        for distribution, version, import_name in DEPENDENCIES
    ]
    dependency_lock = root / "dependency-lock.json"
    dependency_lock.write_bytes(
        _canonical(
            {
                "lock_type": "managed-runtime-dependency-lock/v1",
                "packages": lock_items,
            }
        )
    )
    source_root = root / "approved-python-source"
    _mirror_source_fixture(_approved_source_fixture(), source_root)
    python_source = source_root / Path(sys._base_executable).name
    source_observation = _SOURCE_FIXTURE_OBSERVATION
    if source_observation is None:
        raise RuntimeError("synthetic source fixture is incomplete")
    python_source_manifest = root / "python-source-manifest.json"
    python_source_manifest.write_bytes(
        _canonical(
            {
                "source_type": "approved-cpython-source/v1",
                "python_version": sys.version.split()[0],
                "sqlite_version": sqlite3.sqlite_version,
                "source_tree_fingerprint": source_observation.fingerprint,
                "source_entry_count": source_observation.entry_count,
                "source_total_bytes": source_observation.total_bytes,
                "executable_name": python_source.name,
                "executable_sha256": (
                    source_observation.executable_sha256
                ),
            }
        )
    )
    runtimes = root / "Runtimes"
    runtimes.mkdir()
    local_data = root / "LocalData"
    local_data.mkdir()
    database_source = root / "legacy-analysis.sqlite3"
    connection = sqlite3.connect(database_source)
    try:
        connection.execute(
            "CREATE TABLE synthetic_analysis "
            "(id INTEGER PRIMARY KEY, status TEXT NOT NULL)"
        )
        connection.commit()
    finally:
        connection.close()
    artifacts = root / "Artifacts"
    artifacts.mkdir()
    crx_source = root / "reviewed-extension.crx"
    crx_header = b"synthetic-crx3-header"
    crx_source.write_bytes(
        b"Cr24"
        + (3).to_bytes(4, "little")
        + len(crx_header).to_bytes(4, "little")
        + crx_header
        + b"PK\x03\x04synthetic-reviewed-payload"
    )
    config_root = root / "Config"
    config_root.mkdir()
    config_values = {
        "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS": [
            "example.test",
            "internal.example",
        ],
        "EMAIL_AGENT_LOG_LEVEL": "INFO",
    }
    return SyntheticManagedActivationScenario(
        owner=owner,
        root=root,
        marker=marker,
        python_source=python_source,
        python_source_manifest=python_source_manifest,
        wheelhouse=wheelhouse,
        dependency_lock=dependency_lock,
        runtime_target=runtimes / "managed-runtime",
        database_source=database_source,
        database_target=local_data / "analysis.sqlite3",
        crx_source=crx_source,
        crx_target=artifacts / "email-ai-assistant.crx",
        config_values=config_values,
        config_target=config_root / "managed-config.json",
    )


def profile_for_review(review) -> CutoverProfileV1:
    body = valid_profile_body()
    body["governing_master_commit"] = EXPECTED_MASTER
    body["runtime_inputs"] = {
        "python_version": "3.12.13",
        "sqlite_version": "3.50.4",
        "python_runtime_fingerprint": review.python_runtime_fingerprint,
        "wheelhouse_fingerprint": review.wheelhouse_fingerprint,
        "dependency_lock_fingerprint": review.dependency_lock_fingerprint,
        "network_allowed": False,
        "legacy_reuse_allowed": False,
    }
    body["role_selections"]["runtimes"] = (
        review.runtime_parent_fingerprint
    )
    body["role_selections"]["local_data"] = (
        review.database_parent_fingerprint
    )
    body["sqlite_source"] = {
        "role": "legacy_analysis_database",
        "source_fingerprint": review.database_source_fingerprint,
        "schema_fingerprint": review.database_schema_fingerprint,
        "publication": "create_only",
        "requires_stopped_service": True,
        "requires_absent_sidecars": True,
    }
    body["role_selections"]["artifacts"] = (
        review.artifact_parent_fingerprint
    )
    body["crx"] = {
        "role": "reviewed_browser_extension",
        "artifact_fingerprint": review.crx_artifact_fingerprint,
        "size_bytes": review.crx_size_bytes,
        "publication": "create_only",
        "signing_allowed": False,
    }
    body["role_selections"]["config"] = (
        review.config_parent_fingerprint
    )
    body["config"] = {
        "role": "managed_non_secret_config",
        "config_fingerprint": review.config_fingerprint,
        "allowed_keys": [
            "EMAIL_AGENT_INTERNAL_EMAIL_DOMAINS",
            "EMAIL_AGENT_LOG_LEVEL",
        ],
        "provider_mode": "disabled",
        "reads_environment": False,
    }
    return CutoverProfileV1.create(body)


def authorization_for(profile, operation_fingerprint):
    return TestSandboxAuthorizationV1.create(
        profile_fingerprint=profile.profile_fingerprint,
        operation_fingerprint=operation_fingerprint,
        phase="execute",
        expires_at_epoch=OBSERVED_AT + 600,
    )


def replace_wheel_import(
    scenario: SyntheticManagedActivationScenario,
    distribution: str,
    package_bytes: bytes,
) -> None:
    lock = json.loads(scenario.dependency_lock.read_text("ascii"))
    item = next(
        package
        for package in lock["packages"]
        if package["distribution"] == distribution
    )
    path = scenario.wheelhouse / item["wheel"]
    normalized = distribution.replace("-", "_")
    dist_info = f"{normalized}-{item['version']}.dist-info"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(
            f"{item['import_name']}/__init__.py", package_bytes
        )
        archive.writestr(
            f"{dist_info}/METADATA",
            "Metadata-Version: 2.1\n"
            f"Name: {distribution}\nVersion: {item['version']}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")
    item["wheel_sha256"] = _sha256(path.read_bytes())
    item["import_sha256"] = _sha256(package_bytes)
    scenario.dependency_lock.write_bytes(_canonical(lock))


def add_locked_support_wheel(
    scenario: SyntheticManagedActivationScenario,
) -> None:
    lock = json.loads(scenario.dependency_lock.read_text("ascii"))
    item = _build_wheel(
        scenario.wheelhouse,
        "synthetic-runtime-support",
        "1.0.0",
        "runtime_support",
        filename=(
            "synthetic_runtime_support-1.0.0-"
            "cp312-cp312-win_amd64.whl"
        ),
    )
    lock["packages"].append(item)
    scenario.dependency_lock.write_bytes(_canonical(lock))


def add_startup_member(
    scenario: SyntheticManagedActivationScenario,
    distribution: str,
) -> None:
    lock = json.loads(scenario.dependency_lock.read_text("ascii"))
    item = next(
        package
        for package in lock["packages"]
        if package["distribution"] == distribution
    )
    path = scenario.wheelhouse / item["wheel"]
    payload = wheel_bytes_with_extra_member(
        path,
        "network-attempt.pth",
        b"import socket; socket.socket()\n",
    )
    path.write_bytes(payload)
    item["wheel_sha256"] = _sha256(payload)
    scenario.dependency_lock.write_bytes(_canonical(lock))


def wheel_bytes_with_extra_member(
    path: Path,
    member: str,
    payload: bytes,
) -> bytes:
    owner = tempfile.TemporaryDirectory(prefix="issue57-wheel-race-")
    try:
        output = Path(owner.name) / "replacement.whl"
        with zipfile.ZipFile(path, "r") as source:
            entries = [
                (info, source.read(info.filename))
                for info in source.infolist()
            ]
        with zipfile.ZipFile(
            output, "x", compression=zipfile.ZIP_STORED
        ) as archive:
            for info, content in entries:
                archive.writestr(info, content)
            archive.writestr(member, payload)
        return output.read_bytes()
    finally:
        owner.cleanup()


def _build_wheel(
    wheelhouse: Path,
    distribution: str,
    version: str,
    import_name: str,
    *,
    filename: str | None = None,
) -> dict[str, object]:
    normalized = distribution.replace("-", "_")
    if filename is None:
        filename = f"{normalized}-{version}-py3-none-any.whl"
    path = wheelhouse / filename
    package_bytes = (
        f'"""Synthetic {distribution} fixture."""\n'
        f'__version__ = "{version}"\n'
    ).encode("ascii")
    dist_info = f"{normalized}-{version}.dist-info"
    with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_STORED) as archive:
        archive.writestr(f"{import_name}/__init__.py", package_bytes)
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n",
        )
        archive.writestr(
            f"{dist_info}/WHEEL",
            "Wheel-Version: 1.0\nRoot-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )
        archive.writestr(f"{dist_info}/RECORD", "")
    return {
        "distribution": distribution,
        "version": version,
        "wheel": filename,
        "wheel_sha256": _sha256(path.read_bytes()),
        "import_name": import_name,
        "import_sha256": _sha256(package_bytes),
    }


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=True,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _approved_source_fixture() -> Path:
    global _SOURCE_FIXTURE_OWNER, _SOURCE_FIXTURE_ROOT
    global _SOURCE_FIXTURE_OBSERVATION
    if _SOURCE_FIXTURE_ROOT is not None:
        return _SOURCE_FIXTURE_ROOT
    owner = tempfile.TemporaryDirectory(
        prefix="issue57-approved-python-source-",
        dir=Path(sys._base_executable).anchor,
    )
    root = Path(owner.name)
    _copy_approved_source(Path(sys.base_prefix), root)
    executable = root / Path(sys._base_executable).name
    _SOURCE_FIXTURE_OBSERVATION = observe_source_tree(executable)
    _SOURCE_FIXTURE_OWNER = owner
    _SOURCE_FIXTURE_ROOT = root
    atexit.register(owner.cleanup)
    return root


def _copy_approved_source(source: Path, target: Path) -> None:
    for child in source.iterdir():
        if child.is_file() and not child.is_symlink():
            shutil.copy2(child, target / child.name)
    for name in ("DLLs", "Lib"):
        _copy_tree(source / name, target / name, copy_function=shutil.copy2)


def _mirror_source_fixture(source: Path, target: Path) -> None:
    _copy_tree(source, target, copy_function=os.link)


def _copy_tree(source: Path, target: Path, *, copy_function) -> None:
    target.mkdir()
    for directory, names, files in os.walk(source):
        relative = Path(directory).relative_to(source)
        names[:] = [
            name
            for name in names
            if name not in {"__pycache__", "site-packages"}
        ]
        destination = target / relative
        destination.mkdir(exist_ok=True)
        for name in files:
            origin = Path(directory) / name
            if not origin.is_symlink():
                copy_function(origin, destination / name)
