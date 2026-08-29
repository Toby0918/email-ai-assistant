"""Fixed one-command Issue #39 Project Container cutover entry."""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path


SCRIPT = Path(__file__).absolute()
ROOT = SCRIPT.parents[1]
FIXED_INITIAL_LAUNCHER_ROOT = Path(
    r"D:\Projects\email_ai_assistant\.worktrees\issue39-governed-enablement"
)
FIXED_INITIAL_LAUNCHER_SCRIPT = (
    FIXED_INITIAL_LAUNCHER_ROOT
    / "scripts"
    / "execute_project_container_cutover.py"
)


def _initial_launch_anchor_matches(script_path, current_directory):
    try:
        if not isinstance(script_path, Path) or not isinstance(
            current_directory, Path
        ):
            return False
        fixed = FIXED_INITIAL_LAUNCHER_ROOT.absolute()
        fixed_script = FIXED_INITIAL_LAUNCHER_SCRIPT.absolute()
        original_script = script_path.absolute()
        original_current = current_directory.absolute()
        if (
            _path_key(original_script) != _path_key(fixed_script)
            or _path_key(original_current) != _path_key(fixed)
        ):
            return False
        resolved = fixed.resolve(strict=True)
        resolved_script = fixed_script.resolve(strict=True)
        return (
            _path_key(resolved) == _path_key(fixed)
            and _path_key(resolved_script) == _path_key(fixed_script)
            and _path_key(original_script.resolve(strict=True))
            == _path_key(resolved_script)
            and _path_key(original_current.resolve(strict=True)) == _path_key(resolved)
            and _plain_directory(fixed)
            and _plain_directory(fixed_script.parent)
            and _regular_file(fixed_script)
        )
    except (OSError, RuntimeError, ValueError):
        return False


def _path_key(path):
    return os.path.normcase(os.path.normpath(str(path)))


def _plain_directory(path):
    value = path.lstat()
    return (
        stat.S_ISDIR(value.st_mode)
        and not getattr(value, "st_file_attributes", 0) & 0x400
        and not path.is_symlink()
        and not path.is_junction()
    )


def _regular_file(path):
    value = path.lstat()
    return (
        stat.S_ISREG(value.st_mode)
        and value.st_nlink == 1
        and not getattr(value, "st_file_attributes", 0) & 0x400
        and not path.is_symlink()
    )


def _blocked_launch():
    sys.stdout.write(json.dumps({
        "accepted": 0,
        "host_actions": 0,
        "rejected": 1,
        "status": "BLOCKED_ISSUE39_LAUNCH_ANCHOR",
    }, sort_keys=True, separators=(",", ":")) + "\n")
    return 2


def _run():
    if not _initial_launch_anchor_matches(SCRIPT, Path.cwd()):
        return _blocked_launch()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from backend.r2_issue39_orchestrator.cli import main

    main()
    raise AssertionError("unreachable")


if __name__ == "__main__":
    raise SystemExit(_run())
