"""Fixed no-argument entry for complete synthetic R2 verification."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.r2_synthetic_topology_support import run_verification


def main() -> int:
    if len(sys.argv) != 1:
        return 2
    try:
        result = run_verification(ROOT, Path(__file__).resolve())
    except Exception:
        result = {
            "status": "R2_SYNTHETIC_VERIFICATION_FAILED",
            "accepted": 0,
            "rejected": 1,
        }
        exit_code = 1
    else:
        exit_code = 0
    sys.stdout.write(
        json.dumps(
            result,
            ensure_ascii=True,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )
    sys.stdout.flush()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
