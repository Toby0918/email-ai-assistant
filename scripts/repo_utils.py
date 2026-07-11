"""Shared repository utility helpers."""

from __future__ import annotations

import fnmatch
import re
from pathlib import Path
from typing import Iterable


# Shared scan defaults keep tests and maintenance scripts aligned.
DEFAULT_IGNORED_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", "node_modules", "dist", "build", "outputs",
}

TEXT_SUFFIXES = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css",
    ".json", ".md", ".toml", ".yml", ".yaml", ".txt", ".xml",
}

FORBIDDEN_REPO_FILE_NAMES = {
    ".env",
    "email_agent.sqlite",
    "email_agent.sqlite3",
    "database.sqlite",
    "database.sqlite3",
}

FORBIDDEN_REPO_SUFFIXES = {".db", ".sqlite", ".sqlite3"}

_EXACT_DEPENDENCY_PIN = re.compile(
    r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[^\]]+\])?)\s*==\s*"
    r"(?P<version>[^\s;#]+)"
)
_DEPENDENCY_NAME_SEPARATOR = re.compile(r"[-_.]+")


def parse_pinned_dependency_versions(requirements: str) -> dict[str, str]:
    """Parse exact pins and reject normalized package names with conflicting versions."""
    versions: dict[str, str] = {}
    for line_number, raw_line in enumerate(requirements.splitlines(), start=1):
        match = _EXACT_DEPENDENCY_PIN.match(raw_line)
        if match is None:
            continue
        raw_name = match.group("name").split("[", 1)[0]
        name = _DEPENDENCY_NAME_SEPARATOR.sub("-", raw_name).lower()
        version = match.group("version")
        previous = versions.get(name)
        if previous is not None and previous != version:
            raise ValueError(
                f"Conflicting exact dependency pins for {name}: "
                f"{previous} and {version} (line {line_number})."
            )
        versions[name] = version
    return versions


def load_gitignore_patterns(root: Path) -> list[str]:
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return []
    patterns: list[str] = []
    for raw_line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        patterns.append(line)
    return patterns


def is_ignored_by_gitignore(path: Path, root: Path, patterns: list[str]) -> bool:
    relative = path.relative_to(root).as_posix()
    name = path.name
    for pattern in patterns:
        normalized = pattern.strip("/")
        if pattern.endswith("/"):
            if relative == normalized or relative.startswith(normalized + "/"):
                return True
        elif "/" in normalized:
            if fnmatch.fnmatch(relative, normalized):
                return True
        elif fnmatch.fnmatch(name, normalized) or fnmatch.fnmatch(relative, normalized):
            return True
    return False


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def iter_project_files(root: Path, ignored_dirs: Iterable[str] = DEFAULT_IGNORED_DIRS) -> list[Path]:
    files: list[Path] = []
    ignored = set(ignored_dirs)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignored for part in path.parts):
            continue
        files.append(path)
    return files


def iter_python_files(base: Path, ignored_dirs: Iterable[str] = DEFAULT_IGNORED_DIRS) -> list[Path]:
    if not base.exists():
        return []
    files: list[Path] = []
    ignored = set(ignored_dirs)
    for path in base.rglob("*.py"):
        if any(part in ignored for part in path.parts):
            continue
        files.append(path)
    return files


def is_text_file(path: Path, text_suffixes: Iterable[str] = TEXT_SUFFIXES) -> bool:
    return path.suffix.lower() in set(text_suffixes)


def normalized_markdown(text: str) -> str:
    return text.lstrip("\ufeff").replace("\r\n", "\n")


def parse_front_matter(text: str) -> dict[str, str]:
    # A tiny parser is enough because docs metadata uses a constrained header.
    normalized = normalized_markdown(text)
    if not normalized.startswith("---\n"):
        return {}
    end = normalized.find("\n---\n", 4)
    if end == -1:
        return {}
    header = normalized[4:end]
    data: dict[str, str] = {}
    for line in header.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip().strip('"')
    return data


def parse_front_matter_field(text: str, field: str) -> str | None:
    return parse_front_matter(text).get(field)


def has_required_front_matter(text: str) -> bool:
    meta = parse_front_matter(text)
    return all(field in meta for field in (
        "last_update", "status", "owner", "review_cycle", "source_type",
    ))
