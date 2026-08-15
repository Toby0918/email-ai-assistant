"""Fixed one-command Issue #39 Project Container cutover entry."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.r2_issue39_orchestrator.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
