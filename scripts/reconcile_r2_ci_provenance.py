"""No-argument same-package reconciliation of three CI receipts."""

from __future__ import annotations

import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.r2_ci_provenance_v2 import (
    R2CiProvenanceBundleV2,
    R2CiProvenanceReceiptV2,
)
from scripts.r2_ci_provenance_support import read_git_object_source_package_v2


_RECEIPTS = (
    "R2_PORTABLE_PROVENANCE_RECEIPT",
    "R2_WINDOWS_NATIVE_PROVENANCE_RECEIPT",
    "R2_WINDOWS_INDEPENDENT_PROVENANCE_RECEIPT",
)


def main():
    try:
        package, lock = read_git_object_source_package_v2(ROOT)
        receipts = tuple(
            R2CiProvenanceReceiptV2.from_json(
                os.environ.get(name, "").encode("ascii"),
                source_package=package,
                workflow_lock=lock,
            )
            for name in _RECEIPTS
        )
        bundle = R2CiProvenanceBundleV2.create(
            source_package=package, workflow_lock=lock, receipts=receipts
        )
    except Exception:
        sys.stderr.write("R2_CI_PROVENANCE_INVALID\n")
        return 1
    sys.stdout.buffer.write(bundle.to_canonical_json() + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
