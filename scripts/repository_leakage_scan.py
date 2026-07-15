"""Read-only, content-free repository leakage guard.

The scanner never traverses outside the supplied repository root and never
opens private evaluation datasets. Public results contain only fixed codes,
coarse scope categories, and counts.
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
MAX_SCAN_BYTES = 8 * 1024 * 1024
ALLOWED_SCOPES = frozenset(
    {"git_tracked", "repository_log", "test_output", "public_sqlite", "generated_status"}
)
ALLOWED_CODES = frozenset(
    {
        "LEAK_SECRET_VALUE",
        "LEAK_PRIVATE_IDENTIFIER",
        "LEAK_RAW_MAIL",
        "LEAK_ATTACHMENT_NAME",
        "LEAK_VAULT_MATERIAL",
        "LEAK_REAL_DERIVED_PROSE",
        "LEAK_FORBIDDEN_PRIVATE_DATASET",
        "LEAK_SCOPE_ESCAPE",
        "LEAK_SCAN_UNREADABLE",
    }
)

_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b")
_SECRET = re.compile(
    r"(?i)\b(?:(?:[a-z0-9]+[_-])*api[_-]?key|access[_-]?token|password|secret|private[_-]?key|"
    r"recovery[_-]?key)[\t ]*[:=][\t ]*[\"']?([A-Z0-9+/_-]{20,})"
)
_PEM = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
_RAW_HEADERS = tuple(
    re.compile(rf"(?im)^{name}:[^\r\n]+")
    for name in ("From", "To", "Subject", "Message-ID")
)
_ATTACHMENT_MARKER = "X-Private-" + "Attachment-Name:"
_DERIVED_MARKER = "[[" + "PRIVATE-DERIVED" + "]]"
_BINARY_MAGICS = (b"PKVAULT01", b"PKAUTH01", b"PKIMPORT01", b"PKSNAP01")
_PRIVATE_DATASET_SUFFIX = ".pkeval"
_SYNTHETIC_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "example.test",
        "synthetic.internal",
        "synthetic.external",
    }
)
_PLACEHOLDER_PREFIXES = (
    "your_",
    "example",
    "placeholder",
    "dummy",
    "synthetic",
    "test_",
)
_SYNTHETIC_SECRET_VALUES = frozenset(
    {"private-password", "private-api-key", "private-access-token", "provider-secret-current-request"}
)


@dataclass(frozen=True)
class ScopedFile:
    scope: str
    relative_path: str


@dataclass(frozen=True)
class LeakageFinding:
    code: str
    scope: str
    count: int


Runner = Callable[[Sequence[str], Path], str]


class LeakageScanError(RuntimeError):
    """Fixed-code scope discovery failure with no native detail."""


def _default_runner(command: Sequence[str], cwd: Path) -> str:
    try:
        completed = subprocess.run(
            list(command), cwd=cwd, check=False, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise LeakageScanError("leakage_scope_unavailable") from None
    if completed.returncode != 0:
        raise LeakageScanError("leakage_scope_unavailable")
    return completed.stdout


def list_git_tracked(root: Path, *, runner: Runner = _default_runner) -> tuple[str, ...]:
    try:
        output = runner(("git", "ls-files", "-z"), root)
    except Exception:
        raise LeakageScanError("leakage_scope_unavailable") from None
    return tuple(item for item in output.split("\0") if item)


def _artifact_files(root: Path, tracked: set[str]) -> Iterable[ScopedFile]:
    directories = (("outputs", "test_output"), ("test-results", "test_output"), ("reports", "test_output"))
    for directory, default_scope in directories:
        base = root / directory
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(root).as_posix()
            if relative in tracked:
                continue
            if path.suffix.lower() == ".log":
                scope = "repository_log"
            elif path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                scope = "public_sqlite"
            else:
                scope = default_scope
            yield ScopedFile(scope, relative)
    fixture_root = root / "tests" / "fixtures"
    if fixture_root.is_dir():
        for path in fixture_root.rglob("*"):
            relative = path.relative_to(root).as_posix()
            if path.is_file() and relative not in tracked and path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
                yield ScopedFile("public_sqlite", relative)


def collect_default_scope(
    root: Path, *, tracked_files: Sequence[str] | None = None,
) -> tuple[ScopedFile, ...]:
    tracked = tuple(tracked_files) if tracked_files is not None else list_git_tracked(root)
    scoped = [
        ScopedFile(
            "generated_status" if item == "docs/operations/project_status_log.md" else "git_tracked",
            item,
        )
        for item in tracked
        if not item.lower().endswith(_PRIVATE_DATASET_SUFFIX)
    ]
    scoped.extend(_artifact_files(root, set(tracked)))
    return tuple(scoped)


def _is_synthetic_domain(domain: str) -> bool:
    value = domain.lower().rstrip(".")
    return value in _SYNTHETIC_DOMAINS or value.endswith((".test", ".example"))


def _scan_text(text: str, *, check_identifiers: bool = True) -> Counter[str]:
    counts: Counter[str] = Counter()
    secret_values = [match.group(1).lower() for match in _SECRET.finditer(text)]
    counts["LEAK_SECRET_VALUE"] += sum(
        not value.startswith(_PLACEHOLDER_PREFIXES)
        and value not in _SYNTHETIC_SECRET_VALUES
        for value in secret_values
    )
    counts["LEAK_SECRET_VALUE"] += len(_PEM.findall(text))
    if check_identifiers:
        counts["LEAK_PRIVATE_IDENTIFIER"] += sum(
            not _is_synthetic_domain(match.group(1)) for match in _EMAIL.finditer(text)
        )
    if all(pattern.search(text) for pattern in _RAW_HEADERS):
        counts["LEAK_RAW_MAIL"] += 1
    counts["LEAK_ATTACHMENT_NAME"] += text.count(_ATTACHMENT_MARKER)
    counts["LEAK_REAL_DERIVED_PROSE"] += text.count(_DERIVED_MARKER)
    return +counts


def _sqlite_text(path: Path) -> str:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        names = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        parts: list[str] = []
        for (name,) in names:
            quoted = '"' + str(name).replace('"', '""') + '"'
            for row in connection.execute(f"SELECT * FROM {quoted} LIMIT 10000"):
                parts.extend(value for value in row if isinstance(value, str))
        return "\n".join(parts)
    finally:
        connection.close()


def _safe_candidate(root: Path, relative_path: str) -> Path | None:
    candidate = Path(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return None
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    return resolved if resolved == resolved_root or resolved_root in resolved.parents else None


def _scan_one(root: Path, item: ScopedFile) -> Counter[str]:
    counts: Counter[str] = Counter()
    if item.scope not in ALLOWED_SCOPES:
        counts["LEAK_SCOPE_ESCAPE"] += 1
        return counts
    if item.relative_path.lower().endswith(_PRIVATE_DATASET_SUFFIX):
        counts["LEAK_FORBIDDEN_PRIVATE_DATASET"] += 1
        return counts
    path = _safe_candidate(root, item.relative_path)
    if path is None:
        counts["LEAK_SCOPE_ESCAPE"] += 1
        return counts
    try:
        if item.scope == "public_sqlite" or path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            return _scan_text(_sqlite_text(path))
        if not path.is_file() or path.stat().st_size > MAX_SCAN_BYTES:
            counts["LEAK_SCAN_UNREADABLE"] += 1
            return counts
        raw = path.read_bytes()
    except (OSError, sqlite3.Error):
        counts["LEAK_SCAN_UNREADABLE"] += 1
        return counts
    if path.suffix.lower() not in {".py", ".md", ".txt", ".json", ".js", ".html", ".css", ".yml", ".yaml", ".cmd"}:
        counts["LEAK_VAULT_MATERIAL"] += sum(raw.startswith(magic) for magic in _BINARY_MAGICS)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return +counts
    relative = Path(item.relative_path)
    is_test_source = relative.suffix.lower() == ".py" and relative.parts[:1] == ("tests",)
    counts.update(_scan_text(text, check_identifiers=not is_test_source))
    return +counts


def scan_file_set(root: Path, files: Sequence[ScopedFile]) -> tuple[LeakageFinding, ...]:
    aggregate: Counter[tuple[str, str]] = Counter()
    for item in files:
        for code, count in _scan_one(root, item).items():
            aggregate[(code, item.scope)] += count
    return tuple(
        LeakageFinding(code, scope, count)
        for (code, scope), count in sorted(aggregate.items())
        if code in ALLOWED_CODES and count > 0
    )


def scan_repository(
    root: Path = ROOT, *, tracked_files: Sequence[str] | None = None,
) -> tuple[LeakageFinding, ...]:
    tracked = tuple(tracked_files) if tracked_files is not None else list_git_tracked(root)
    findings = list(scan_file_set(root, collect_default_scope(root, tracked_files=tracked)))
    private_count = sum(item.lower().endswith(_PRIVATE_DATASET_SUFFIX) for item in tracked)
    if private_count:
        findings.append(LeakageFinding("LEAK_FORBIDDEN_PRIVATE_DATASET", "git_tracked", private_count))
    return tuple(sorted(findings, key=lambda item: (item.code, item.scope)))


def render_summary(findings: Sequence[LeakageFinding]) -> str:
    lines = ["Repository leakage summary"]
    lines.extend(f"code={item.code} scope={item.scope} count={item.count}" for item in findings)
    lines.append(f"total={sum(item.count for item in findings)}")
    return "\n".join(lines)


def summary_as_json(findings: Sequence[LeakageFinding]) -> str:
    return json.dumps(
        {"findings": [asdict(item) for item in findings], "total": sum(item.count for item in findings)},
        sort_keys=True,
        separators=(",", ":"),
    )
