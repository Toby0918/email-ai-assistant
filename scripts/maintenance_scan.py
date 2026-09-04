"""Repository maintenance scanner for the email AI assistant project.

This script is read-only. It scans repository hygiene issues and prints a Markdown report.

Run:
    python scripts/maintenance_scan.py
    python scripts/maintenance_scan.py --output outputs/cleanup_report.md
    python scripts/maintenance_scan.py --fail-on-high
"""

from __future__ import annotations

import argparse
import ast
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath

# Support both unittest imports and direct `python scripts/maintenance_scan.py`.
try:
    from scripts.repo_utils import (
        FORBIDDEN_REPO_FILE_NAMES,
        FORBIDDEN_REPO_SUFFIXES,
        TEXT_SUFFIXES,
        has_required_front_matter,
        is_ignored_by_gitignore,
        iter_project_files,
        iter_python_files,
        load_gitignore_patterns,
        parse_front_matter,
        read_text,
    )
    from scripts.repository_leakage_scan import (
        LeakageFinding,
        scan_repository as scan_repository_for_leakage,
    )
except ModuleNotFoundError:
    from repo_utils import (
        FORBIDDEN_REPO_FILE_NAMES,
        FORBIDDEN_REPO_SUFFIXES,
        TEXT_SUFFIXES,
        has_required_front_matter,
        is_ignored_by_gitignore,
        iter_project_files,
        iter_python_files,
        load_gitignore_patterns,
        parse_front_matter,
        read_text,
    )
    from repository_leakage_scan import (
        LeakageFinding,
        scan_repository as scan_repository_for_leakage,
    )


ROOT = Path(__file__).resolve().parents[1]

MAX_BACKEND_PY_FILE_LINES = 300
MAX_FUNCTION_LINES = 50
STALE_DRAFT_DAYS = 30

TODO_PATTERN = re.compile(r"\b(TODO|FIXME)\b", re.IGNORECASE)
TODO_REFERENCE_FILES = {
    "scripts/maintenance_scan.py",
    "docs/operations/cleanup_agent.md",
    "docs/operations/codex_cleanup_task.md",
    "docs/templates/cleanup_task_template.md",
    "docs/constraints/mechanical_rule_translation.md",
}
WINDOWS_RESERVED_PATH_PARTS = frozenset({
    "con", "conin$", "conout$", "prn", "aux", "nul", "clock$",
    *(f"com{value}" for value in "0123456789"),
    *(f"lpt{value}" for value in "0123456789"),
})


@dataclass(frozen=True)
class Finding:
    severity: str
    category: str
    path: str
    message: str
    fix: str
    doc: str


@dataclass(frozen=True, slots=True, init=False, repr=False)
class StableMaintenanceFindingV1:
    severity: str
    category: str
    path: str
    doc: str

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("StableMaintenanceFindingV1 is observer-owned")

    def as_tuple(self) -> tuple[str, str, str, str]:
        return self.severity, self.category, self.path, self.doc


@dataclass(frozen=True, slots=True, init=False, repr=False)
class MaintenanceObservationV1:
    records: tuple[StableMaintenanceFindingV1, ...]
    total_count: int
    low_count: int
    medium_count: int
    high_count: int

    def __init__(self, *args: object, **kwargs: object) -> None:
        raise TypeError("MaintenanceObservationV1 is observer-owned")


class MaintenanceObservationError(Exception):
    def __init__(self, code: str) -> None:
        if type(code) is not str or code not in {
            "MAINTENANCE_OBSERVATION_SCAN_FAILED",
            "MAINTENANCE_OBSERVATION_INVALID",
            "MAINTENANCE_OBSERVATION_DUPLICATE",
        }:
            raise TypeError("MaintenanceObservationError code is invalid")
        self.code = code
        super().__init__(code)


GITIGNORE_PATTERNS = load_gitignore_patterns(ROOT)


def rel(path: Path) -> str:
    return _rel(path, ROOT)


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def scan_forbidden_files() -> list[Finding]:
    return _scan_forbidden_files(ROOT, GITIGNORE_PATTERNS)


def _scan_forbidden_files(
    root: Path, gitignore_patterns: list[str]
) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_project_files(root):
        name = path.name.lower()
        suffix = path.suffix.lower()
        if (
            name in FORBIDDEN_REPO_FILE_NAMES or suffix in FORBIDDEN_REPO_SUFFIXES
        ) and not is_ignored_by_gitignore(path, root, gitignore_patterns):
            findings.append(Finding(
                "high", "security_hygiene", _rel(path, root),
                "禁止提交未忽略的本地配置、数据库或敏感运行文件。",
                "删除该文件或加入 .gitignore；如需示例配置，使用 .env.example。",
                "docs/security/email_data_handling.md",
            ))
    return findings


def scan_backend_file_lengths() -> list[Finding]:
    return _scan_backend_file_lengths(ROOT)


def _scan_backend_file_lengths(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    backend = root / "backend"
    if not backend.exists():
        return findings

    for path in iter_python_files(backend):
        line_count = len(read_text(path).splitlines())
        if line_count > MAX_BACKEND_PY_FILE_LINES:
            findings.append(Finding(
                "medium", "oversized_file", _rel(path, root),
                f"Python 文件 {line_count} 行，超过 {MAX_BACKEND_PY_FILE_LINES} 行限制。",
                "拆分模块；保持单文件职责单一。",
                "docs/constraints/mechanical_rule_translation.md",
            ))
    return findings


def scan_backend_function_lengths() -> list[Finding]:
    return _scan_backend_function_lengths(ROOT)


def _scan_backend_function_lengths(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    backend = root / "backend"
    if not backend.exists():
        return findings

    for path in iter_python_files(backend):
        try:
            tree = ast.parse(read_text(path))
        except SyntaxError as exc:
            findings.append(Finding(
                "high", "linter_failure", _rel(path, root),
                f"Python 语法错误：{exc}",
                "先修复语法错误，再运行清理扫描。",
                "docs/constraints/mechanical_rule_translation.md",
            ))
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_lineno = getattr(node, "end_lineno", None)
                if end_lineno is None:
                    continue
                length = end_lineno - node.lineno + 1
                if length > MAX_FUNCTION_LINES:
                    findings.append(Finding(
                        "medium", "oversized_function", _rel(path, root),
                        f"函数 {node.name} 第 {node.lineno}-{end_lineno} 行，共 {length} 行，超过 {MAX_FUNCTION_LINES} 行限制。",
                        "拆分函数；分离输入校验、业务逻辑、外部调用和响应构造。",
                        "docs/constraints/mechanical_rule_translation.md",
                    ))
    return findings


def scan_todo_fixme() -> list[Finding]:
    return _scan_todo_fixme(ROOT)


def _scan_todo_fixme(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for path in iter_project_files(root):
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if _rel(path, root) in TODO_REFERENCE_FILES:
            continue
        for index, line in enumerate(read_text(path).splitlines(), start=1):
            if TODO_PATTERN.search(line):
                findings.append(Finding(
                    "low", "todo_fixme", f"{_rel(path, root)}:{index}",
                    "发现 TODO/FIXME 标记。",
                    "判断是否需要创建清理任务；超过 30 天未处理的应进入 cleanup PR。",
                    "docs/operations/cleanup_agent.md",
                ))
    return findings


def scan_docs_metadata_and_staleness() -> list[Finding]:
    return _scan_docs_metadata_and_staleness(ROOT)


def _scan_docs_metadata_and_staleness(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    docs = root / "docs"
    if not docs.exists():
        return findings

    today = date.today()
    for path in docs.rglob("*.md"):
        text = read_text(path)
        if not has_required_front_matter(text):
            findings.append(Finding(
                "medium", "other", _rel(path, root),
                "docs Markdown 缺少标准 YAML front matter。",
                "补充 last_update、status、owner、review_cycle、source_type。",
                "docs/operations/documentation_rules.md",
            ))
            continue

        meta = parse_front_matter(text)
        if meta.get("status") != "draft":
            continue

        last_update = meta.get("last_update")
        if not last_update:
            continue

        try:
            updated = datetime.strptime(last_update, "%Y-%m-%d").date()
        except ValueError:
            findings.append(Finding(
                "medium", "other", _rel(path, root),
                "last_update 不是 YYYY-MM-DD 格式。",
                "修正日期格式。",
                "docs/operations/documentation_rules.md",
            ))
            continue

        age = (today - updated).days
        if age > STALE_DRAFT_DAYS:
            findings.append(Finding(
                "low", "stale_doc", _rel(path, root),
                f"draft 文档已 {age} 天未更新。",
                "确认是否转为 active、更新内容，或标记为 deprecated。",
                "docs/operations/cleanup_agent.md",
            ))
    return findings


def scan_repository_leakage(
    *, scan=scan_repository_for_leakage,
) -> list[Finding]:
    """Convert aggregate leakage codes without exposing source content or paths."""
    return _leakage_findings(scan())


def _leakage_findings(items: object) -> list[Finding]:
    findings: list[Finding] = []
    for item in items:
        findings.append(Finding(
            "high",
            "repository_leakage",
            f"[{item.scope}]",
            f"code={item.code} count={item.count}",
            "Stop release and inspect the named scope locally without copying content.",
            "docs/operations/testing_checklist.md",
        ))
    return findings


def collect_findings() -> list[Finding]:
    # Scans are read-only: collect independent findings, then render a report.
    return _collect_findings_at(ROOT, GITIGNORE_PATTERNS, None)


def _collect_findings_at(
    root: Path,
    gitignore_patterns: list[str],
    tracked_paths: tuple[str, ...] | None,
) -> list[Finding]:
    findings: list[Finding] = []
    findings.extend(_scan_forbidden_files(root, gitignore_patterns))
    findings.extend(_scan_backend_file_lengths(root))
    findings.extend(_scan_backend_function_lengths(root))
    findings.extend(_scan_todo_fixme(root))
    findings.extend(_scan_docs_metadata_and_staleness(root))
    findings.extend(_leakage_findings(
        scan_repository_for_leakage(root, tracked_files=tracked_paths)
    ))
    return findings


def collect_stable_observation() -> MaintenanceObservationV1:
    try:
        findings = collect_findings()
    except Exception:
        raise MaintenanceObservationError(
            "MAINTENANCE_OBSERVATION_SCAN_FAILED"
        ) from None
    return _stable_observation_from_findings(findings)


def _collect_materialized_stable_observation(
    root: Path,
    tracked_paths: tuple[str, ...],
) -> MaintenanceObservationV1:
    try:
        valid_input = (
            isinstance(root, Path)
            and root.is_dir()
            and type(tracked_paths) is tuple
            and all(_safe_tracked_path(path) for path in tracked_paths)
            and tuple(sorted(set(tracked_paths))) == tracked_paths
        )
    except Exception:
        valid_input = False
    if not valid_input:
        raise MaintenanceObservationError("MAINTENANCE_OBSERVATION_INVALID")
    try:
        findings = _collect_findings_at(
            root,
            load_gitignore_patterns(root),
            tracked_paths,
        )
    except Exception:
        raise MaintenanceObservationError(
            "MAINTENANCE_OBSERVATION_SCAN_FAILED"
        ) from None
    return _stable_observation_from_findings(findings)


def _safe_tracked_path(value: object) -> bool:
    if (
        type(value) is not str
        or not 1 <= len(value.encode("utf-8")) <= 4096
    ):
        return False
    path = PurePosixPath(value)
    windows_path = PureWindowsPath(value)
    if not (
        value == path.as_posix()
        and not path.is_absolute()
        and not windows_path.drive
        and not windows_path.root
        and "\\" not in value
        and value not in {"", "."}
        and all(part not in {"", ".", ".."} for part in path.parts)
    ):
        return False
    for part in path.parts:
        normalized = unicodedata.normalize("NFKC", part)
        device = normalized.split(".", 1)[0].rstrip(" .").casefold()
        if (
            normalized.endswith((" ", "."))
            or any(
                ord(character) < 32
                or ord(character) == 127
                or character in '<>:"|?*'
                for character in normalized
            )
            or device in WINDOWS_RESERVED_PATH_PARTS
            or len(normalized.encode("utf-16-le")) // 2 > 255
        ):
            return False
    return True


def _stable_observation_from_findings(
    findings: object,
) -> MaintenanceObservationV1:
    if type(findings) is not list or any(
        type(item) is not Finding
        or type(item.severity) is not str
        or item.severity not in {"low", "medium", "high"}
        or any(
            type(value) is not str or not value
            for value in (item.category, item.path, item.doc)
        )
        for item in findings
    ):
        raise MaintenanceObservationError("MAINTENANCE_OBSERVATION_INVALID")
    records = tuple(
        _stable_record(
            item.severity, item.category, item.path, item.doc
        )
        for item in findings
    )
    records = tuple(sorted(records, key=StableMaintenanceFindingV1.as_tuple))
    if len({item.as_tuple() for item in records}) != len(records):
        raise MaintenanceObservationError("MAINTENANCE_OBSERVATION_DUPLICATE")
    return _observation(records)


def _stable_record(
    severity: str, category: str, path: str, doc: str
) -> StableMaintenanceFindingV1:
    value = object.__new__(StableMaintenanceFindingV1)
    for name, item in (
        ("severity", severity),
        ("category", category),
        ("path", path),
        ("doc", doc),
    ):
        object.__setattr__(value, name, item)
    return value


def _observation(
    records: tuple[StableMaintenanceFindingV1, ...],
) -> MaintenanceObservationV1:
    value = object.__new__(MaintenanceObservationV1)
    for name, item in (
        ("records", records),
        ("total_count", len(records)),
        ("low_count", sum(record.severity == "low" for record in records)),
        ("medium_count", sum(record.severity == "medium" for record in records)),
        ("high_count", sum(record.severity == "high" for record in records)),
    ):
        object.__setattr__(value, name, item)
    return value


def render_report(findings: list[Finding]) -> str:
    lines = ["# Cleanup Agent Report", "", f"Generated on: {date.today().isoformat()}", ""]
    if not findings:
        lines.extend(["No cleanup findings detected.", ""])
        return "\n".join(lines)

    lines.extend(["| Severity | Category | File | Problem | Suggested Fix | Reference |", "|---|---|---|---|---|---|"])
    for item in findings:
        lines.append(
            f"| {item.severity} | {item.category} | `{item.path}` | {item.message} | {item.fix} | `{item.doc}` |"
        )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--fail-on-high", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    findings = collect_findings()
    report = render_report(findings)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        print(report)

    if args.fail_on_high and any(item.severity == "high" for item in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
