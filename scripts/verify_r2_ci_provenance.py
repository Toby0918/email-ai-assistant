"""No-argument CI entry for one fixed Issue #100 provenance kind."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.r2_ci_provenance_v2 import CiProvenanceKindV2
from scripts.r2_ci_provenance_support import create_ci_receipt_v2


def main():
    try:
        kind = CiProvenanceKindV2(os.environ.get("R2_CI_PROVENANCE_KIND", ""))
        receipt = create_ci_receipt_v2(ROOT, kind)
    except Exception:
        sys.stderr.write("R2_CI_PROVENANCE_INVALID\n")
        return 1
    sys.stdout.buffer.write(receipt.to_canonical_json() + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
