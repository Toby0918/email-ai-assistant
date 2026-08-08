"""Detached Windows probe proving terminal input cannot unlock transaction."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.windows_real_tty_host import run_dormant_module


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        return 2
    target = Path(sys.argv[1])
    verb = sys.argv[2] if len(sys.argv) == 3 else "execute"
    if verb not in {"execute", "resume", "rollback"}:
        return 2
    if target.exists() or not target.parent.is_dir():
        return 3
    result = run_dormant_module(
        "backend.r2_transaction_process", verb, target.parent
    )
    target.write_text(
        json.dumps(result, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
